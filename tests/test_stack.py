import pytest

from assembler import assemble
from cpu import RAM_END, RAM_START
from exceptions import InvalidCpuRegister, MachineFault, StackPointerOutsideRam

from conftest import build_machine, run_cpu


def assembled(source: str) -> bytes:
    return b"".join(assemble(source))


def test_push_then_pop_restores_value_and_stack_pointer() -> None:
    program = assembled("LOAD R0, 0xA5\nPUSH R0\nPOP R1\nHALT")
    cpu, _ = build_machine(program)
    run_cpu(cpu)

    assert cpu.regs[1] == 0xA5
    assert cpu.SP == RAM_END


def test_stack_returns_three_values_in_lifo_order() -> None:
    source = """
LOAD R0, 0x11
PUSH R0
LOAD R0, 0x22
PUSH R0
LOAD R0, 0x33
PUSH R0
POP R1
POP R2
POP R3
HALT
"""
    cpu, _ = build_machine(assembled(source))
    run_cpu(cpu)

    assert cpu.regs[1:4] == [0x33, 0x22, 0x11]
    assert cpu.SP == RAM_END


def test_push_writes_below_ram_end_and_pop_can_use_another_register() -> None:
    source = "LOAD R0, 0xA5\nPUSH R0\nLOAD R1, 0\nPOP R1\nHALT"
    cpu, _ = build_machine(assembled(source))
    cpu.step()
    cpu.step()

    assert cpu.SP == RAM_END - 1
    assert cpu.bus.read(RAM_END - 1) == 0xA5
    assert cpu.regs[0] == 0xA5

    run_cpu(cpu)
    assert cpu.regs[1] == 0xA5
    assert cpu.regs[0] == 0xA5


def test_push_with_invalid_register_raises_without_changing_state() -> None:
    cpu, _ = build_machine(bytes([0x0A, 4]))
    initial_sp = cpu.SP
    initial_regs = cpu.regs.copy()

    with pytest.raises(InvalidCpuRegister):
        cpu.step()

    assert cpu.SP == initial_sp
    assert cpu.regs == initial_regs


def test_pop_with_invalid_register_raises_without_changing_state() -> None:
    cpu, _ = build_machine(bytes([0x0B, 4]))
    cpu.SP = RAM_END - 1
    cpu.bus.write(cpu.SP, 0xA5)
    initial_sp = cpu.SP
    initial_regs = cpu.regs.copy()

    with pytest.raises(InvalidCpuRegister):
        cpu.step()

    assert cpu.SP == initial_sp
    assert cpu.regs == initial_regs


def test_pop_on_empty_stack_raises_without_changing_state() -> None:
    cpu, _ = build_machine(assembled("POP R0"))
    initial_sp = cpu.SP
    initial_regs = cpu.regs.copy()

    with pytest.raises(StackPointerOutsideRam):
        cpu.step()

    assert cpu.SP == initial_sp
    assert cpu.regs == initial_regs


def test_push_at_ram_start_raises_without_changing_state() -> None:
    cpu, _ = build_machine(assembled("PUSH R0"))
    cpu.SP = RAM_START
    initial_regs = cpu.regs.copy()

    with pytest.raises(StackPointerOutsideRam):
        cpu.step()

    assert cpu.SP == RAM_START
    assert cpu.regs == initial_regs


def test_push_at_last_free_stack_byte_succeeds() -> None:
    cpu, _ = build_machine(assembled("PUSH R0"))
    cpu.SP = RAM_START + 1
    cpu.regs[0] = 0x5A

    cpu.step()

    assert cpu.SP == RAM_START
    assert cpu.bus.read(RAM_START) == 0x5A


def test_call_jumps_and_ret_resumes_after_call() -> None:
    source = """
TERMINAL = 0x0800
CALL routine
LOAD R0, 'A'
STORE R0, TERMINAL
HALT
routine:
LOAD R0, 'B'
STORE R0, TERMINAL
RET
"""
    cpu, recorder = build_machine(assembled(source))
    run_cpu(cpu)

    assert bytes(value for _, value in recorder.writes) == b"BA"


def test_call_stores_high_then_low_return_address_on_stack() -> None:
    cpu, _ = build_machine(assembled("CALL target\nHALT\ntarget:\nRET"))

    cpu.step()

    assert cpu.SP == RAM_END - 2
    assert cpu.bus.read(cpu.SP) == 0
    assert cpu.bus.read(cpu.SP + 1) == 3


def test_ret_restores_stack_pointer_after_call() -> None:
    cpu, _ = build_machine(assembled("CALL target\nHALT\ntarget:\nRET"))
    cpu.step()
    assert cpu.SP == RAM_END - 2

    cpu.step()

    assert cpu.PC == 3
    assert cpu.SP == RAM_END


def test_nested_calls_use_two_stack_frames_and_return_in_order() -> None:
    source = """
TERMINAL = 0x0800
CALL routine_a
LOAD R0, 'D'
STORE R0, TERMINAL
HALT
routine_a:
LOAD R0, 'A'
STORE R0, TERMINAL
CALL routine_b
LOAD R0, 'C'
STORE R0, TERMINAL
RET
routine_b:
LOAD R0, 'B'
STORE R0, TERMINAL
RET
"""
    cpu, recorder = build_machine(assembled(source))
    cpu.step()
    assert cpu.SP == RAM_END - 2

    cpu.step()
    cpu.step()
    cpu.step()
    assert cpu.SP == RAM_END - 4

    run_cpu(cpu)
    assert bytes(value for _, value in recorder.writes) == b"ABCD"


def test_same_routine_returns_to_both_call_sites() -> None:
    source = """
TERMINAL = 0x0800
CALL routine
LOAD R0, 'A'
STORE R0, TERMINAL
CALL routine
LOAD R0, 'B'
STORE R0, TERMINAL
HALT
routine:
LOAD R0, 'X'
STORE R0, TERMINAL
RET
"""
    cpu, recorder = build_machine(assembled(source))
    run_cpu(cpu)

    assert bytes(value for _, value in recorder.writes) == b"XAXB"


def test_routine_can_save_and_restore_caller_registers() -> None:
    source = """
LOAD R0, 0x11
LOAD R1, 0x22
CALL routine
HALT
routine:
PUSH R0
PUSH R1
LOAD R0, 0xAA
LOAD R1, 0xBB
POP R1
POP R0
RET
"""
    cpu, _ = build_machine(assembled(source))
    run_cpu(cpu)

    assert cpu.regs[:2] == [0x11, 0x22]
    assert cpu.SP == RAM_END


def test_ret_on_empty_stack_raises_without_changing_state() -> None:
    cpu, _ = build_machine(assembled("RET"))
    initial_sp = cpu.SP
    initial_regs = cpu.regs.copy()

    with pytest.raises(StackPointerOutsideRam):
        cpu.step()

    assert cpu.SP == initial_sp
    assert cpu.regs == initial_regs


def test_call_at_ram_start_raises_without_changing_state() -> None:
    cpu, _ = build_machine(assembled("CALL target\nHALT\ntarget:\nRET"))
    cpu.SP = RAM_START
    initial_regs = cpu.regs.copy()

    with pytest.raises(StackPointerOutsideRam):
        cpu.step()

    assert cpu.SP == RAM_START
    assert cpu.regs == initial_regs


def test_stack_pointer_fault_is_a_machine_fault() -> None:
    assert issubclass(StackPointerOutsideRam, MachineFault)


def test_assembler_encodes_call_push_pop_and_ret() -> None:
    source = "CALL target\nPUSH R1\nPOP R2\nRET\ntarget:\nHALT"
    assert assembled(source) == bytes([0x0C, 0, 8, 0x0A, 1, 0x0B, 2, 0x0D, 0x01])


def test_string_printing_program_outputs_hello_world_and_xy() -> None:
    source = """
TERMINAL = 0x0800
main:
    LOAD R0, 0x58
    LOAD R1, 0x59
    LOAD R2, >msg1
    LOAD R3, <msg1
    CALL print_string
    LOAD R2, >msg2
    LOAD R3, <msg2
    CALL print_string
    STORE R0, TERMINAL
    STORE R1, TERMINAL
    HALT

print_string:
    PUSH R0
    PUSH R1
print_loop:
    LDR R0, R2, R3
    LOAD R1, 0x00
    CMP R0, R1
    JZ done
    STORE R0, TERMINAL
    LOAD R1, 0x01
    ADD R3, R1
    JUMP print_loop
done:
    POP R1
    POP R0
    RET

msg1:
    .string "HELLO "
msg2:
    .string "WORLD\\n"
"""
    cpu, recorder = build_machine(assembled(source))
    run_cpu(cpu)

    assert bytes(value for _, value in recorder.writes) == b"HELLO WORLD\nXY"