import pytest

import isa
from assembler import assemble
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
from memmap import (
    KERNEL_ONLY_START,
    RAM_END,
    RAM_START,
    TERMINAL_START,
)
from tps import CpuMode

from conftest import CANONICAL_UNMAPPED_ADDRESS, build_machine

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
    cpu, recording_device = build_machine(assembled(f"LOAD R0, 0x5A\nSTORE R0, {TERMINAL_START:#06x}"))
    cpu.step()
    cpu.step()

    assert recording_device.writes == [(0, 0x5A)]


def test_kernel_mode_can_load_from_recording_device() -> None:
    cpu, recording_device = build_machine(assembled(f"LOAD R0, {TERMINAL_START >> 8}\nLOAD R1, 0\nLDR R2, R0, R1"))
    recording_device.memory[0] = 0xA5

    cpu.step()
    cpu.step()
    cpu.step()

    assert cpu.regs[2] == 0xA5
    assert recording_device.reads == 1


def test_halt_is_a_privileged_operation() -> None:
    assert Opcode.HALT in isa.PRIVILEGED_OPERATIONS


@pytest.mark.parametrize(
    ("opcode", "operands"),
    [(Opcode.GETSP, bytes([0, 1])), (Opcode.SETSP, bytes([0, 1]))],
    ids=["getsp", "setsp"],
)
def test_user_mode_stack_pointer_instructions_fault_without_side_effects(opcode: Opcode, operands: bytes) -> None:
    cpu, _ = build_machine(bytes([opcode.value]) + operands, start_mode=CpuMode.USER)
    cpu.regs = [0x12, 0x34, 0x56, 0x78]
    cpu.SP = RAM_END - 4
    cpu.zero_flag = True
    registers = cpu.regs.copy()
    initial_sp = cpu.SP
    frame = [cpu.bus.read(initial_sp + offset) for offset in range(4)]

    with pytest.raises(PrivilegedOperationViolation) as error:
        cpu.step()

    assert error.value.operation == opcode
    assert (cpu.PC, cpu.SP, cpu.mode, cpu.zero_flag, cpu.regs) == (0, initial_sp, CpuMode.USER, True, registers)
    assert [cpu.bus.read(initial_sp + offset) for offset in range(4)] == frame


def test_user_lda_cannot_read_keyboard_region() -> None:
    cpu, _ = build_machine(
        bytes([Opcode.LDA.value, 2, 0xF4, 0x00]),
        start_mode=CpuMode.USER,
    )
    cpu.regs = [0x11, 0x22, 0xA5, 0x44]

    with pytest.raises(PrivilegedMemoryAccessViolation) as error:
        cpu.step()

    assert error.value.address == 0xF400
    assert cpu.PC == 0
    assert cpu.regs == [0x11, 0x22, 0xA5, 0x44]


def test_cpu_run_ticks_once_for_each_executed_instruction() -> None:
    cpu, device = build_machine(assembled("LOAD R0, 1\nHALT"))

    cpu.run()

    assert device.ticks == 2


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
    last_ram_address = RAM_END - 1
    cpu, _ = build_machine(
        assembled(f"LOAD R0, 0x5A\nSTORE R0, {last_ram_address:#06x}"),
        start_mode=CpuMode.USER,
    )
    cpu.step()
    cpu.step()

    assert cpu.bus.read(last_ram_address) == 0x5A


def test_user_mode_store_to_device_faults_before_device_write() -> None:
    cpu, recording_device = build_machine(
        assembled(f"LOAD R0, 0x5A\nSTORE R0, {TERMINAL_START:#06x}"),
        start_mode=CpuMode.USER,
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
    last_ram_address = RAM_END - 1
    cpu.regs[0] = last_ram_address >> 8
    cpu.regs[1] = last_ram_address & 0xFF
    cpu.bus.write(last_ram_address, 0xA5)

    cpu.step()

    assert cpu.regs[2] == 0xA5


def test_user_mode_load_from_device_faults_before_device_read() -> None:
    cpu, recording_device = build_machine(
        assembled("LDR R2, R0, R1"), start_mode=CpuMode.USER
    )
    cpu.regs[0] = TERMINAL_START >> 8
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
    cpu, _ = build_machine(assembled(f"JUMP {TERMINAL_START:#06x}"), start_mode=CpuMode.USER)
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
    cpu, recording_device = build_machine(assembled(f"LOAD R0, 0x5A\nSTORE R0, {TERMINAL_START:#06x}"))
    cpu.step()
    cpu.step()

    assert recording_device.writes == [(0, 0x5A)]


def test_kernel_mode_can_load_from_protected_region() -> None:
    cpu, recording_device = build_machine(assembled("LDR R2, R0, R1"))
    cpu.regs[0] = TERMINAL_START >> 8
    cpu.regs[1] = 0
    recording_device.memory[0] = 0xA5

    cpu.step()

    assert cpu.regs[2] == 0xA5
    assert recording_device.reads == 1


@pytest.mark.parametrize(
    ("program", "start_mode", "fault_type", "fault_pc", "attribute", "value", "stack_pointer"),
    [
        (assembled(".byte 0xFF"), CpuMode.KERNEL, IllegalInstruction, 0, "value", 0xFF, None),
        (bytes([Opcode.LOAD.value, 4, 1]), CpuMode.KERNEL, InvalidCpuRegister, 0, "value", 4, None),
        (
            assembled(f"LOAD R0, {CANONICAL_UNMAPPED_ADDRESS >> 8}\n" f"LOAD R1, {CANONICAL_UNMAPPED_ADDRESS & 0xFF}\nLDR R2, R0, R1"),
            CpuMode.KERNEL,
            BusFaultUnmappedAddress,
            6,
            "address",
            CANONICAL_UNMAPPED_ADDRESS,
            None,
        ),
        (assembled("LOAD R0, 1\nSTORE R0, 0"), CpuMode.KERNEL, WriteToRomError, 3, None, None, None),
        (assembled("POP R0"), CpuMode.KERNEL, StackPointerOutsideRam, 0, "sp", RAM_END + 1, None),
        (assembled("HALT"), CpuMode.USER, PrivilegedOperationViolation, 0, "operation", Opcode.HALT, None),
        (
            assembled(f"STORE R0, {TERMINAL_START:#06x}"),
            CpuMode.USER,
            PrivilegedMemoryAccessViolation,
            0,
            "address",
            KERNEL_ONLY_START,
            None,
        ),
        (assembled("SYSCALL"), CpuMode.USER, StackPointerOutsideRam, 0, "sp", RAM_START - 1, RAM_START + 2),
        (assembled("RETI"), CpuMode.KERNEL, StackPointerOutsideRam, 0, "sp", RAM_END + 3, None),
    ],
    ids=["illegal-opcode", "invalid-register", "unmapped-address", "write-to-rom", "stack-boundary", "privileged-op", "privileged-memory", "syscall-stack-overflow", "reti-empty-stack"],
)
def test_machine_fault_restores_pc_to_instruction_start(
    program: bytes,
    start_mode: CpuMode,
    fault_type: type[Exception],
    fault_pc: int,
    attribute: str | None,
    value: object,
    stack_pointer: int | None,
) -> None:
    cpu, _ = build_machine(program, start_mode=start_mode)
    if stack_pointer is not None:
        cpu.SP = stack_pointer
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
        assembled(f"STORE R0, {TERMINAL_START:#06x}"),
        start_mode=CpuMode.USER,
        trace_mode=True,
    )

    with pytest.raises(PrivilegedMemoryAccessViolation):
        cpu.step()

    output = capsys.readouterr().out
    assert "M=U" in output
    assert "STORE" in output
