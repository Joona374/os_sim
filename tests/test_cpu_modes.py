import pytest

import isa
from assembler import assemble
from cpu import KERNEL_ONLY_START, RAM_END, RAM_START
from exceptions import (
    BusFaultUnmappedAddress,
    IllegalInstruction,
    InvalidCpuRegister,
    PrivilegedMemoryAccessViolation,
    PrivilegedOperationViolation,
    StackPointerOutsideRam,
    WriteToRomError,
)
from isa import Opcode
from tps import CpuMode

from conftest import build_machine


def assembled(source: str) -> bytes:
    return b"".join(assemble(source))


def test_cpu_defaults_to_kernel_mode() -> None:
    cpu, _ = build_machine(assembled("HALT"))

    assert cpu.mode == CpuMode.KERNEL


def test_cpu_can_start_in_user_mode() -> None:
    cpu, _ = build_machine(assembled("LOAD R0, 1"), start_mode=CpuMode.USER)

    assert cpu.mode == CpuMode.USER


def test_halt_runs_in_kernel_mode() -> None:
    cpu, _ = build_machine(assembled("HALT"))

    cpu.step()

    assert cpu.halted is True


def test_kernel_mode_can_store_to_recording_device() -> None:
    cpu, recording_device = build_machine(assembled("LOAD R0, 0x5A\nSTORE R0, 0x0800"))
    cpu.step()
    cpu.step()

    assert recording_device.writes == [(0, 0x5A)]


def test_kernel_mode_can_load_from_recording_device() -> None:
    cpu, recording_device = build_machine(
        assembled("LOAD R0, 0x08\nLOAD R1, 0\nLDR R2, R0, R1")
    )
    recording_device.memory[0] = 0xA5

    cpu.step()
    cpu.step()
    cpu.step()

    assert cpu.regs[2] == 0xA5
    assert recording_device.reads == 1


def test_halt_is_a_privileged_operation() -> None:
    assert getattr(isa, "PRIVILEGED_OPERATIONS", None) == {Opcode.HALT}


def test_user_mode_halt_faults_without_halting_or_advancing_pc() -> None:
    cpu, _ = build_machine(assembled("HALT"), start_mode=CpuMode.USER)

    with pytest.raises(PrivilegedOperationViolation) as error:
        cpu.step()

    assert error.value.operation == Opcode.HALT
    assert cpu.halted is False
    assert cpu.PC == 0


def test_user_program_computes_and_uses_stack_and_calls_before_halt_fault() -> None:
    source = """
LOAD R0, 2
LOAD R1, 3
ADD R0, R1
LOAD R2, 5
CMP R0, R2
JZ equal
LOAD R3, 0xEE
equal:
PUSH R0
LOAD R0, 0
POP R0
CALL routine
HALT
routine:
LOAD R1, 7
RET
"""
    cpu, _ = build_machine(assembled(source), start_mode=CpuMode.USER)
    instructions = assemble(source)
    halt_index = next(index for index, instruction in enumerate(instructions) if instruction == bytes([Opcode.HALT.value]))
    halt_address = sum(len(instruction) for instruction in instructions[:halt_index])

    for _ in range(20):
        if cpu.PC == halt_address:
            break
        cpu.step()

    assert cpu.PC == halt_address
    with pytest.raises(PrivilegedOperationViolation):
        cpu.step()

    assert cpu.regs == [5, 7, 5, 0]
    assert cpu.SP == RAM_END
    assert cpu.halted is False


def test_user_mode_can_store_to_last_ram_address() -> None:
    cpu, _ = build_machine(assembled("LOAD R0, 0x5A\nSTORE R0, 0x07FF"), start_mode=CpuMode.USER)
    cpu.step()
    cpu.step()

    assert cpu.bus.read(0x07FF) == 0x5A


def test_user_mode_store_to_device_faults_before_device_write() -> None:
    cpu, recording_device = build_machine(
        assembled("LOAD R0, 0x5A\nSTORE R0, 0x0800"), start_mode=CpuMode.USER
    )
    cpu.step()
    initial_registers = cpu.regs.copy()
    initial_sp = cpu.SP
    initial_flag = cpu.zero_flag

    with pytest.raises(PrivilegedMemoryAccessViolation) as error:
        cpu.step()

    assert error.value.address == KERNEL_ONLY_START
    assert recording_device.writes == []
    assert cpu.regs == initial_registers
    assert cpu.SP == initial_sp
    assert cpu.zero_flag == initial_flag
    assert cpu.PC == 3


def test_user_mode_can_load_from_last_ram_address() -> None:
    cpu, _ = build_machine(assembled("LDR R2, R0, R1"), start_mode=CpuMode.USER)
    cpu.regs[0] = 0x07
    cpu.regs[1] = 0xFF
    cpu.bus.write(0x07FF, 0xA5)

    cpu.step()

    assert cpu.regs[2] == 0xA5


def test_user_mode_load_from_device_faults_before_device_read() -> None:
    cpu, recording_device = build_machine(
        assembled("LDR R2, R0, R1"), start_mode=CpuMode.USER
    )
    cpu.regs[0] = 0x08
    cpu.regs[1] = 0
    cpu.regs[2] = 0xCC
    recording_device.memory[0] = 0xA5

    with pytest.raises(PrivilegedMemoryAccessViolation) as error:
        cpu.step()

    assert error.value.address == KERNEL_ONLY_START
    assert cpu.regs[2] == 0xCC
    assert recording_device.reads == 0
    assert cpu.PC == 0


def test_user_jump_to_device_region_faults_on_next_instruction_fetch() -> None:
    cpu, _ = build_machine(assembled("JUMP 0x0800"), start_mode=CpuMode.USER)
    cpu.step()

    assert cpu.PC == KERNEL_ONLY_START
    with pytest.raises(PrivilegedMemoryAccessViolation) as error:
        cpu.step()

    assert error.value.address == KERNEL_ONLY_START
    assert cpu.PC == KERNEL_ONLY_START


def test_user_pop_on_empty_stack_raises_stack_fault_first() -> None:
    cpu, _ = build_machine(assembled("POP R0"), start_mode=CpuMode.USER)

    with pytest.raises(StackPointerOutsideRam):
        cpu.step()

    assert cpu.PC == 0


def test_user_mode_stack_operations_work_with_stack_in_ram() -> None:
    source = """
LOAD R0, 0x55
PUSH R0
LOAD R1, 0
POP R1
CALL routine
JUMP done
routine:
LOAD R2, 0x66
RET
done:
LOAD R3, 1
"""
    cpu, _ = build_machine(assembled(source), start_mode=CpuMode.USER)

    for _ in range(9):
        cpu.step()

    assert cpu.regs == [0x55, 0x55, 0x66, 1]
    assert cpu.SP == RAM_END


def test_kernel_mode_can_store_to_protected_region() -> None:
    cpu, recording_device = build_machine(assembled("LOAD R0, 0x5A\nSTORE R0, 0x0800"))
    cpu.step()
    cpu.step()

    assert recording_device.writes == [(0, 0x5A)]


def test_kernel_mode_can_load_from_protected_region() -> None:
    cpu, recording_device = build_machine(assembled("LDR R2, R0, R1"))
    cpu.regs[0] = 0x08
    cpu.regs[1] = 0
    recording_device.memory[0] = 0xA5

    cpu.step()

    assert cpu.regs[2] == 0xA5
    assert recording_device.reads == 1


@pytest.mark.parametrize(
    ("program", "start_mode", "fault_type", "fault_pc", "attribute", "value"),
    [
        (assembled(".byte 0xFF"), CpuMode.KERNEL, IllegalInstruction, 0, "value", 0xFF),
        (bytes([Opcode.LOAD.value, 4, 1]), CpuMode.KERNEL, InvalidCpuRegister, 0, "value", 4),
        (
            assembled("LOAD R0, 0x0C\nLOAD R1, 0\nLDR R2, R0, R1"),
            CpuMode.KERNEL,
            BusFaultUnmappedAddress,
            6,
            "address",
            0x0C00,
        ),
        (assembled("LOAD R0, 1\nSTORE R0, 0"), CpuMode.KERNEL, WriteToRomError, 3, None, None),
        (assembled("POP R0"), CpuMode.KERNEL, StackPointerOutsideRam, 0, "sp", RAM_END + 1),
        (assembled("HALT"), CpuMode.USER, PrivilegedOperationViolation, 0, "operation", Opcode.HALT),
        (
            assembled("STORE R0, 0x0800"),
            CpuMode.USER,
            PrivilegedMemoryAccessViolation,
            0,
            "address",
            KERNEL_ONLY_START,
        ),
    ],
    ids=["illegal-opcode", "invalid-register", "unmapped-address", "write-to-rom", "stack-boundary", "privileged-op", "privileged-memory"],
)
def test_machine_fault_restores_pc_to_instruction_start(
    program: bytes,
    start_mode: CpuMode,
    fault_type: type[Exception],
    fault_pc: int,
    attribute: str | None,
    value: object,
) -> None:
    cpu, _ = build_machine(program, start_mode=start_mode)
    for _ in range(fault_pc // 3 + 1):
        if cpu.PC == fault_pc:
            break
        cpu.step()

    with pytest.raises(fault_type) as error:
        cpu.step()

    assert cpu.PC == fault_pc
    if attribute is not None:
        assert getattr(error.value, attribute) == value


def test_trace_includes_kernel_mode(capsys: pytest.CaptureFixture[str]) -> None:
    cpu, _ = build_machine(assembled("HALT"), trace_mode=True)

    cpu.step()

    assert "M=K" in capsys.readouterr().out


def test_trace_includes_user_mode_and_faulting_instruction(capsys: pytest.CaptureFixture[str]) -> None:
    cpu, _ = build_machine(
        assembled("STORE R0, 0x0800"), start_mode=CpuMode.USER, trace_mode=True
    )

    with pytest.raises(PrivilegedMemoryAccessViolation):
        cpu.step()

    output = capsys.readouterr().out
    assert "M=U" in output
    assert "STORE" in output
