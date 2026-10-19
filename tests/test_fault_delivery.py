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
    BusFaultUnmappedAddress,
    DoubleFault,
    IllegalInstruction,
    InvalidCpuRegister,
    MachineFault,
    PrivilegedOperationViolation,
    StackPointerOutsideRam,
)
from isa import Opcode
from machine import Machine
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
        (assembled("RETI"), CpuMode.USER, 0, 0, PRIV_FAULT_VECTOR),
        (assembled("STORE R0, 0x0800"), CpuMode.USER, 0, 0, PRIV_FAULT_VECTOR),
        (assembled("LOAD R1, 0x5A\nSTORE R1, 0x0C00"), CpuMode.KERNEL, 1, 3, BUS_FAULT_VECTOR),
        (assembled("STORE R1, 0x0010"), CpuMode.KERNEL, 0, 0, BUS_FAULT_VECTOR),
        (assembled(".byte 0x00"), CpuMode.KERNEL, 0, 0, MACHINE_FAULT_VECTOR),
        (bytes([Opcode.LOAD.value, 7, 1]), CpuMode.KERNEL, 0, 0, MACHINE_FAULT_VECTOR),
        (bytes([Opcode.CMPI.value, 7, 1]), CpuMode.KERNEL, 0, 0, MACHINE_FAULT_VECTOR),
        (bytes([Opcode.ADDI.value, 7, 1]), CpuMode.KERNEL, 0, 0, MACHINE_FAULT_VECTOR),
        (assembled("POP R0"), CpuMode.KERNEL, 0, 0, MACHINE_FAULT_VECTOR),
    ],
    ids=[
        "user-halt", "user-reti", "user-device-store", "unmapped-store", "rom-store",
        "illegal-opcode", "invalid-load-register", "invalid-cmpi-register", "invalid-addi-register", "empty-pop",
    ],
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
def test_machine_fault_handling_disabled_still_raises_and_restores_pc(program: bytes, mode: CpuMode) -> None:
    cpu, _ = build_machine(program, start_mode=mode, handle_machine_faults=False)
    with pytest.raises(MachineFault):
        cpu.step()
    assert cpu.PC == 0


def test_machine_fault_handling_disabled_propagates_from_run() -> None:
    cpu, _ = build_machine(assembled("STORE R0, 0x0C00"))

    with pytest.raises(BusFaultUnmappedAddress):
        cpu.run()

    assert cpu.PC == 0


@pytest.mark.parametrize("mode", [CpuMode.KERNEL, CpuMode.USER], ids=["kernel", "user"])
@pytest.mark.parametrize("zero_flag", [False, True], ids=["zero-clear", "zero-set"])
def test_fault_frame_saves_mode_and_zero_flag(mode: CpuMode, zero_flag: bool) -> None:
    cpu, _ = build_machine(assembled(".byte 0x00"), start_mode=mode, handle_machine_faults=True)
    cpu.zero_flag = zero_flag

    cpu.step()

    assert cpu.SP == RAM_END - 3
    assert cpu.bus.read(cpu.SP) == int(mode) | (2 if zero_flag else 0)
    assert [cpu.bus.read(cpu.SP + 1), cpu.bus.read(cpu.SP + 2)] == [0, 0]
    assert cpu.mode == CpuMode.KERNEL


def test_fault_after_user_jump_saves_fetch_address() -> None:
    cpu, _ = build_machine(
        assembled("JUMP 0x0800"),
        start_mode=CpuMode.USER,
        handle_machine_faults=True,
    )
    cpu.step()
    assert cpu.PC == 0x0800

    cpu.step()

    assert cpu.PC == PRIV_FAULT_VECTOR
    assert [cpu.bus.read(cpu.SP + offset) for offset in range(3)] == [1, 0x08, 0x00]


@pytest.mark.parametrize("mode", [CpuMode.KERNEL, CpuMode.USER], ids=["kernel", "user"])
@pytest.mark.parametrize("zero_flag", [False, True], ids=["zero-clear", "zero-set"])
def test_reti_restores_fault_frame_mode_flag_pc_and_stack(mode: CpuMode, zero_flag: bool) -> None:
    image = bytearray(MACHINE_FAULT_VECTOR + 1)
    image[0] = 0x00
    image[MACHINE_FAULT_VECTOR] = Opcode.RETI.value
    cpu, _ = build_machine(bytes(image), start_mode=mode, handle_machine_faults=True)
    cpu.zero_flag = zero_flag
    cpu.step()
    assert cpu.PC == MACHINE_FAULT_VECTOR

    cpu.step()

    assert (cpu.PC, cpu.SP, cpu.mode, cpu.zero_flag) == (
        0,
        RAM_END,
        mode,
        zero_flag,
    )


def test_multibyte_store_fault_restores_pc_and_leaves_state_unchanged() -> None:
    cpu, device = build_machine(assembled("STORE R0, 0x0C00"))
    cpu.regs = [0xA5, 0x12, 0x34, 0x56]
    cpu.zero_flag = True
    registers = cpu.regs.copy()
    ram = [cpu.bus.read(address) for address in range(RAM_START, RAM_END)]
    initial = (cpu.SP, cpu.mode, cpu.zero_flag, registers)

    with pytest.raises(BusFaultUnmappedAddress):
        cpu.step()

    assert cpu.PC == 0
    assert (cpu.SP, cpu.mode, cpu.zero_flag, cpu.regs) == initial
    assert [cpu.bus.read(address) for address in range(RAM_START, RAM_END)] == ram
    assert device.writes == []


def test_ldr_validates_target_before_faulting_bus_read() -> None:
    cpu, _ = build_machine(bytes([Opcode.LDR.value, 7, 0, 1]))
    cpu.regs = [0x0C, 0x00, 0xA5, 0x5A]

    with pytest.raises(InvalidCpuRegister):
        cpu.step()

    assert cpu.PC == 0
    assert cpu.regs == [0x0C, 0x00, 0xA5, 0x5A]


def test_non_machine_exception_from_handler_is_not_trapped() -> None:
    cpu, _ = build_machine(assembled("HALT"), handle_machine_faults=True)

    def fail_with_value_error() -> None:
        raise ValueError("handler bug")

    cpu.operation_to_handler[Opcode.HALT] = fail_with_value_error
    with pytest.raises(ValueError, match="handler bug"):
        cpu.step()
    assert (cpu.SP, cpu.mode, cpu.halted) == (RAM_END, CpuMode.KERNEL, False)


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
    assert "Original: Opcode: 0XFF" in message
    assert "secondary: Stack Pointer" in message
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


def test_fault_frame_that_exactly_fits_ram_is_delivered() -> None:
    cpu, _ = build_machine(assembled(".byte 0x00"), handle_machine_faults=True)
    cpu.SP = RAM_START + 3

    cpu.step()

    assert (cpu.PC, cpu.SP, cpu.halted) == (
        MACHINE_FAULT_VECTOR,
        RAM_START,
        False,
    )
    assert [cpu.bus.read(RAM_START + offset) for offset in range(3)] == [0, 0, 0]


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


@pytest.mark.parametrize(
    ("snippet", "initial_flags", "output"),
    [
        ("HALT", 1, "PRIVILEGE FAULT"),
        ("RETI", 1, "PRIVILEGE FAULT"),
        ("STORE R0, 0x0800", 1, "PRIVILEGE FAULT"),
        ("STORE R0, 0x0010", 0, "BUS FAULT"),
        ("STORE R0, 0x0C00", 0, "BUS FAULT"),
        (".byte 0x00", 1, "MACHINE FAULT"),
        (".byte 0x02, 0x07, 0x01", 0, "MACHINE FAULT"),
    ],
    ids=["user-halt", "user-reti", "user-device-store", "rom-write", "unmapped-access", "illegal-opcode", "invalid-register"],
)
def test_rom_kernel_prints_fault_message_and_halts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    snippet: str,
    initial_flags: int,
    output: str,
) -> None:
    kernel_path = Path(__file__).resolve().parents[1] / "asm" / "kernel.asm"
    source = kernel_path.read_text()
    main_start = source.index("main:\n") + len("main:\n")
    syscall_start = source.index("\nsyscall:\n", main_start)
    source = source[:main_start] + snippet + source[syscall_start:]
    source = source.replace(
        "LOAD R2, 1\n    PUSH R2",
        f"LOAD R2, {initial_flags}\n    PUSH R2",
        1,
    )
    image = b"".join(assemble(source))
    hex_dir = tmp_path / "hex"
    hex_dir.mkdir()
    hex_path = hex_dir / "kernel_demo.hex"
    hex_path.write_text(image.hex(" "))
    machine = Machine(str(hex_path), handle_machine_faults=True)

    machine.cpu.run()

    assert output in capsys.readouterr().out
    assert machine.cpu.halted is True


def test_main_normal_halt_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hex_dir = tmp_path / "hex"
    hex_dir.mkdir()
    (hex_dir / "normal.hex").write_text(assembled("HALT").hex(" "))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["main.py", "normal"])

    with pytest.raises(SystemExit) as error:
        main.main()

    assert error.value.code == 0


def test_main_parses_and_removes_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeCpu:
        def run(self) -> None:
            pass

    class FakeMachine:
        def __init__(
            self,
            path: str,
            trace_mode: bool,
            start_mode: CpuMode,
            handle_machine_faults: bool,
        ) -> None:
            captured.update(
                path=path,
                trace_mode=trace_mode,
                start_mode=start_mode,
                handle_machine_faults=handle_machine_faults,
            )
            self.cpu = FakeCpu()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main, "Machine", FakeMachine)
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "flags", "--trace", "--user", "--handle-faults"],
    )

    with pytest.raises(SystemExit) as error:
        main.main()

    assert error.value.code == 0
    assert sys.argv == ["main.py", "flags"]
    assert captured == {
        "path": "hex/flags.hex",
        "trace_mode": True,
        "start_mode": CpuMode.USER,
        "handle_machine_faults": True,
    }


def test_main_wrong_argument_count_exits_with_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["main.py", "one", "two"])

    with pytest.raises(SystemExit) as error:
        main.main()

    assert error.value.code == "usage: python3 main.py <program_name>"


def test_main_reports_double_fault_with_nonzero_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    hex_dir = tmp_path / "hex"
    hex_dir.mkdir()
    image = bytearray(MACHINE_FAULT_VECTOR + 1)
    image[0] = 0x00
    image[MACHINE_FAULT_VECTOR] = 0x00
    (hex_dir / "double_fault.hex").write_text(bytes(image).hex(" "))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["main.py", "double_fault", "--handle-faults"])

    with pytest.raises(SystemExit) as error:
        main.main()

    output = capsys.readouterr().out
    assert error.value.code == 1
    assert "DoubleFault" in output
    assert "At: 0x000C" in output
    assert "Original:" in output
    assert "secondary:" in output
