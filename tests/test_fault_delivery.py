import inspect
import subprocess
import sys
from pathlib import Path

import main
import pytest

from assembler import assemble
from cpu import (
    BUS_FAULT_VECTOR,
    MACHINE_FAULT_VECTOR,
    PRIV_FAULT_VECTOR,
    RAM_END,
    RAM_START,
)
from exceptions import (
    DoubleFault,
    IllegalInstruction,
    MachineFault,
    PrivilegedOperationViolation,
    StackPointerOutsideRam,
)
from isa import Opcode
from tps import CpuMode

from conftest import build_machine


def assembled(source: str) -> bytes:
    return b"".join(assemble(source))


def test_machine_fault_handling_defaults_to_disabled() -> None:
    cpu, _ = build_machine(assembled(".byte 0xFF"))
    assert cpu.handle_machine_faults is False


@pytest.mark.parametrize(
    ("program", "mode", "pre_steps", "fault_pc", "vector"),
    [
        (assembled("HALT"), CpuMode.USER, 0, 0, PRIV_FAULT_VECTOR),
        (assembled("STORE R0, 0x0800"), CpuMode.USER, 0, 0, PRIV_FAULT_VECTOR),
        (assembled("LOAD R1, 0x5A\nSTORE R1, 0x0C00"), CpuMode.KERNEL, 1, 3, BUS_FAULT_VECTOR),
        (assembled("STORE R1, 0x0010"), CpuMode.KERNEL, 0, 0, BUS_FAULT_VECTOR),
        (assembled(".byte 0xFF"), CpuMode.KERNEL, 0, 0, MACHINE_FAULT_VECTOR),
        (bytes([Opcode.LOAD.value, 4, 1]), CpuMode.KERNEL, 0, 0, MACHINE_FAULT_VECTOR),
        (assembled("POP R0"), CpuMode.KERNEL, 0, 0, MACHINE_FAULT_VECTOR),
    ],
    ids=["user-halt", "user-device-store", "unmapped-store", "rom-store", "illegal-opcode", "invalid-register", "empty-pop"],
)
def test_machine_fault_is_delivered_to_its_vector(
    program: bytes,
    mode: CpuMode,
    pre_steps: int,
    fault_pc: int,
    vector: int,
) -> None:
    cpu, _ = build_machine(program, start_mode=mode, handle_machine_faults=True)
    cpu.regs = [0x10, 0x20, 0x30, 0x40]
    cpu.zero_flag = True
    for _ in range(pre_steps):
        cpu.step()
    registers = cpu.regs.copy()
    original_flag = cpu.zero_flag

    cpu.step()

    assert cpu.PC == vector
    assert cpu.SP == RAM_END - 3
    assert cpu.mode == CpuMode.KERNEL
    assert [cpu.bus.read(cpu.SP + offset) for offset in range(3)] == [
        int(mode) | 0b10,
        fault_pc >> 8,
        fault_pc & 0xFF,
    ]
    assert cpu.regs == registers
    assert cpu.zero_flag is original_flag
    assert cpu.halted is False


@pytest.mark.parametrize(
    ("program", "mode"),
    [(assembled(".byte 0xFF"), CpuMode.KERNEL), (assembled("HALT"), CpuMode.USER)],
    ids=["illegal-opcode", "user-halt"],
)
def test_machine_fault_handling_disabled_still_raises_and_restores_pc(
    program: bytes, mode: CpuMode
) -> None:
    cpu, _ = build_machine(program, start_mode=mode, handle_machine_faults=False)
    with pytest.raises(MachineFault):
        cpu.step()
    assert cpu.PC == 0


def test_non_machine_exception_from_handler_is_not_trapped() -> None:
    cpu, _ = build_machine(assembled("HALT"), handle_machine_faults=True)

    def fail_with_value_error() -> None:
        raise ValueError("handler bug")

    cpu.operation_to_handler[Opcode.HALT] = fail_with_value_error
    with pytest.raises(ValueError, match="handler bug"):
        cpu.step()


@pytest.mark.parametrize("stack_pointer", [RAM_START, RAM_START + 2], ids=["no-room", "two-bytes-room"])
def test_fault_delivery_stack_failure_raises_double_fault_without_partial_state(
    stack_pointer: int,
) -> None:
    cpu, _ = build_machine(assembled(".byte 0xFF"), handle_machine_faults=True)
    cpu.SP = stack_pointer
    cpu.regs = [0x11, 0x22, 0x33, 0x44]
    cpu.zero_flag = True
    registers = cpu.regs.copy()
    initial_ram = [cpu.bus.read(address) for address in range(RAM_START, RAM_END)]

    with pytest.raises(DoubleFault) as error:
        cpu.step()

    message = str(error.value)
    assert "Opcode: 0XFF" in message
    assert "Stack Pointer" in message
    assert "At: 0x0000" in message
    assert cpu.halted is True
    assert (cpu.PC, cpu.SP, cpu.mode, cpu.zero_flag, cpu.regs) == (
        0,
        stack_pointer,
        CpuMode.KERNEL,
        True,
        registers,
    )
    assert [cpu.bus.read(address) for address in range(RAM_START, RAM_END)] == initial_ram


def test_double_fault_is_not_a_machine_fault() -> None:
    assert not issubclass(DoubleFault, MachineFault)


def test_user_stack_overflow_double_faults_after_1024_pushes() -> None:
    cpu, _ = build_machine(
        assembled("loop:\nPUSH R0\nJUMP loop"),
        start_mode=CpuMode.USER,
        handle_machine_faults=True,
    )
    pushes = 0
    for _ in range(2048):
        old_sp = cpu.SP
        cpu.step()
        if cpu.SP == old_sp - 1:
            pushes += 1

    assert pushes == 1024
    assert cpu.SP == RAM_START
    with pytest.raises(DoubleFault):
        cpu.step()
    assert cpu.halted is True
    assert cpu.SP == RAM_START
    assert cpu.PC == 0
    assert cpu.mode == CpuMode.USER


def test_faulting_generic_vector_retraps_until_stack_exhaustion() -> None:
    image = bytearray(MACHINE_FAULT_VECTOR + 1)
    image[0] = 0xFF
    image[MACHINE_FAULT_VECTOR] = 0xFF
    cpu, _ = build_machine(bytes(image), handle_machine_faults=True)
    cpu.step()
    assert cpu.SP == RAM_END - 3
    assert cpu.PC == MACHINE_FAULT_VECTOR

    for _ in range(400):
        try:
            cpu.step()
        except DoubleFault as error:
            assert "At: 0x000C" in str(error)
            break
    else:
        pytest.fail("repeated generic faults did not exhaust the trap stack")

    assert cpu.halted is True
    assert cpu.PC == MACHINE_FAULT_VECTOR
    assert cpu.SP == RAM_START + 1
    assert cpu.mode == CpuMode.KERNEL


FAULT_KERNEL = """
TERMINAL = 0x0800
JUMP boot
JUMP syscall_entry
JUMP fault_privilege
JUMP fault_bus
JUMP fault_generic
boot:
LOAD R2, <user_main
PUSH R2
LOAD R1, >user_main
PUSH R1
LOAD R0, 1
PUSH R0
RETI
syscall_entry:
RETI
fault_privilege:
LOAD R0, 0x50
STORE R0, TERMINAL
HALT
fault_bus:
LOAD R0, 0x42
STORE R0, TERMINAL
HALT
fault_generic:
LOAD R0, 0x47
STORE R0, TERMINAL
HALT
user_main:
"""


@pytest.mark.parametrize(
    ("user_code", "output"),
    [
        ("HALT", b"P"),
        ("STORE R0, 0x0800", b"P"),
        ("STORE R0, 0x0010", b"B"),
        (".byte 0xFF", b"G"),
        ("POP R0", b"G"),
    ],
    ids=["privileged-operation", "privileged-memory", "rom-write", "illegal-opcode", "empty-pop"],
)
def test_real_kernel_delivers_user_faults_and_halts(
    user_code: str, output: bytes
) -> None:
    kernel_size = len(assembled(FAULT_KERNEL))
    program = assembled(FAULT_KERNEL + user_code)
    cpu, device = build_machine(program, handle_machine_faults=True)

    cpu.run()

    assert bytes(value for _, value in device.writes) == output
    assert cpu.halted is True
    assert cpu.mode == CpuMode.KERNEL
    assert cpu.SP == RAM_END - 3
    assert [cpu.bus.read(cpu.SP + offset) for offset in range(3)] == [
        1,
        kernel_size >> 8,
        kernel_size & 0xFF,
    ]


_main_source = inspect.getsource(main)
_main_catches_double_fault = "except DoubleFault" in _main_source


@pytest.mark.skipif(not _main_catches_double_fault, reason="main.py does not catch DoubleFault")
def test_main_reports_double_fault_with_nonzero_exit(tmp_path: Path) -> None:
    hex_dir = tmp_path / "hex"
    hex_dir.mkdir()
    image = bytes([0xFF]) + bytes(MACHINE_FAULT_VECTOR - 1) + bytes([0xFF])
    (hex_dir / "double_fault.hex").write_text(image.hex(" "))
    main_path = Path(__file__).resolve().parents[1] / "main.py"
    result = subprocess.run(
        [sys.executable, str(main_path), "double_fault", "--handle-faults"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "DoubleFault" in result.stdout + result.stderr