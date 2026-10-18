import pytest

from assembler import assemble
from cpu import RAM_END, RAM_START, SYSCALL_TRAP_VECTOR
from exceptions import PrivilegedMemoryAccessViolation, PrivilegedOperationViolation, StackPointerOutsideRam
from isa import LAYOUT, Opcode, PRIVILEGED_OPERATIONS
from tps import CpuMode

from conftest import build_machine, run_cpu


def assembled(source: str) -> bytes:
    return b"".join(assemble(source))


def user_program(user: str, handler: str) -> str:
    return (
        "JUMP boot\nJUMP handler\nboot:\n"
        "LOAD R2, <user_main\nPUSH R2\nLOAD R1, >user_main\nPUSH R1\n"
        "LOAD R0, 1\nPUSH R0\nRETI\nhandler:\n"
        + handler
        + "\nuser_main:\n"
        + user
    )


KERNEL = (
    "TERMINAL = 0x0800\nSYS_PRINT_R1 = 1\nSYS_EXIT = 2\n"
    "JUMP boot\nJUMP dispatcher\nboot:\n"
    "LOAD R2, <main\nPUSH R2\nLOAD R1, >main\nPUSH R1\n"
    "LOAD R0, 1\nPUSH R0\nRETI\ndispatcher:\nPUSH R3\n"
    "LOAD R3, SYS_PRINT_R1\nCMP R0, R3\nJZ print_r1\n"
    "LOAD R3, SYS_EXIT\nCMP R0, R3\nJZ exit\n"
    "LOAD R0, 0xEE\nJUMP trap_done\ntrap_done:\nPOP R3\nRETI\n"
)
KERNEL_TAIL = (
    "exit:\nLOAD R0, 'E'\nSTORE R0, TERMINAL\nHALT\n"
    "print_r1:\nSTORE R1, TERMINAL\nLOAD R0, 0\nJUMP trap_done\n"
)


def end_to_end_program(user: str) -> bytes:
    return assembled(KERNEL + "main:\n" + user + "\n" + KERNEL_TAIL)


def test_syscall_and_reti_encoding_layout_and_privilege() -> None:
    assert assembled("SYSCALL\nRETI") == bytes([0x0E, 0x0F])
    assert LAYOUT[Opcode.SYSCALL] == LAYOUT[Opcode.RETI] == []
    assert Opcode.RETI in PRIVILEGED_OPERATIONS
    assert Opcode.SYSCALL not in PRIVILEGED_OPERATIONS


def test_user_syscall_enters_kernel_at_trap_vector_and_saves_pc() -> None:
    cpu, _ = build_machine(assembled("SYSCALL"), start_mode=CpuMode.USER)
    cpu.step()
    assert (cpu.mode, cpu.PC, cpu.SP) == (CpuMode.KERNEL, SYSCALL_TRAP_VECTOR, RAM_END - 3)
    assert [cpu.bus.read(cpu.SP + i) for i in range(3)] == [1, 0, 1]


def test_syscall_saves_kernel_mode_when_called_from_kernel() -> None:
    cpu, _ = build_machine(assembled("SYSCALL"))
    cpu.step()
    assert cpu.bus.read(cpu.SP) & 1 == 0
    assert cpu.mode == CpuMode.KERNEL


@pytest.mark.parametrize("flag", [False, True], ids=["clear", "set"])
def test_syscall_preserves_registers_and_saves_zero_flag(flag: bool) -> None:
    cpu, _ = build_machine(assembled("SYSCALL"), start_mode=CpuMode.USER)
    cpu.regs = [0x11, 0x22, 0x33, 0x44]
    registers = cpu.regs.copy()
    cpu.zero_flag = flag
    cpu.step()
    assert cpu.regs == registers
    assert cpu.zero_flag is flag
    assert cpu.bus.read(cpu.SP) == 1 | (2 if flag else 0)


def test_syscall_frame_contains_high_and_low_bytes_of_saved_pc() -> None:
    cpu, _ = build_machine(bytes(0xFF) + bytes([Opcode.SYSCALL.value]), start_mode=CpuMode.USER)
    cpu.PC = 0xFF
    cpu.step()
    assert [cpu.bus.read(cpu.SP + i) for i in range(3)] == [1, 1, 0]


def test_syscall_frame_can_exactly_fill_ram() -> None:
    cpu, _ = build_machine(assembled("SYSCALL"), start_mode=CpuMode.USER)
    cpu.SP = RAM_START + 3
    cpu.step()
    assert cpu.SP == RAM_START
    assert [cpu.bus.read(a) for a in range(RAM_START, RAM_START + 3)] == [1, 0, 1]


def test_syscall_reti_round_trip_restores_user_mode_stack_and_registers() -> None:
    source = user_program("LOAD R3, 0x33\nSYSCALL\nLOAD R2, 0x55\nJUMP done\ndone:\nJUMP done", "RETI")
    cpu, _ = build_machine(assembled(source))
    for _ in range(40):
        cpu.step()
        if cpu.mode == CpuMode.USER and cpu.regs[2] == 0x55:
            break
    assert (cpu.mode, cpu.SP, cpu.regs[2:]) == (CpuMode.USER, RAM_END, [0x55, 0x33])


@pytest.mark.parametrize("flag", [False, True], ids=["clear", "set"])
def test_reti_restores_zero_flag_after_handler_cmp(flag: bool) -> None:
    user_cmp = "0" if flag else "1"
    handler_cmp = "1" if flag else "0"
    user = f"LOAD R0, 0\nLOAD R1, {user_cmp}\nCMP R0, R1\nSYSCALL\nJUMP done\ndone:\nJUMP done"
    handler = f"LOAD R0, 0\nLOAD R1, {handler_cmp}\nCMP R0, R1\nRETI"
    source = user_program(user, handler)
    instructions = assemble(source)
    idx = next(i for i, item in enumerate(instructions) if item == bytes([Opcode.SYSCALL.value]))
    return_pc = sum(len(item) for item in instructions[:idx + 1])
    cpu, _ = build_machine(b"".join(instructions))
    for _ in range(60):
        cpu.step()
        if cpu.mode == CpuMode.USER and cpu.PC == return_pc:
            break
    assert (cpu.mode, cpu.PC, cpu.zero_flag) == (CpuMode.USER, return_pc, flag)


@pytest.mark.parametrize(
    ("status", "mode", "flag"),
    [(0, CpuMode.KERNEL, False), (1, CpuMode.USER, False), (2, CpuMode.KERNEL, True),
     (3, CpuMode.USER, True), (0xFF, CpuMode.USER, True), (0xFC, CpuMode.KERNEL, False)],
)
def test_reti_decodes_status_bits_and_ignores_others(status: int, mode: CpuMode, flag: bool) -> None:
    cpu, _ = build_machine(assembled("RETI"))
    cpu.SP = RAM_END - 3
    for i, value in enumerate([status, 0x12, 0x34]):
        cpu.bus.write(cpu.SP + i, value)
    cpu.step()
    assert (cpu.mode, cpu.zero_flag, cpu.PC, cpu.SP) == (mode, flag, 0x1234, RAM_END)


def test_reti_reads_frame_pc_high_byte_first() -> None:
    cpu, _ = build_machine(assembled("RETI"))
    cpu.SP = RAM_END - 3
    for i, value in enumerate([0, 0xAB, 0xCD]):
        cpu.bus.write(cpu.SP + i, value)
    cpu.step()
    assert cpu.PC == 0xABCD


def test_kernel_can_boot_into_user_mode_with_hand_built_frame() -> None:
    source = "LOAD R2, <target\nPUSH R2\nLOAD R1, >target\nPUSH R1\nLOAD R0, 1\nPUSH R0\nRETI\ntarget:\nJUMP target"
    program = assembled(source)
    target = len(program) - 3
    cpu, _ = build_machine(program)
    for _ in range(7):
        cpu.step()
    assert (cpu.mode, cpu.PC, cpu.SP) == (CpuMode.USER, target, RAM_END)


def test_user_reti_fault_does_not_consume_frame() -> None:
    cpu, _ = build_machine(assembled("RETI"), start_mode=CpuMode.USER)
    cpu.SP = RAM_END - 3
    frame = [2, 0x12, 0x34]
    for i, value in enumerate(frame):
        cpu.bus.write(cpu.SP + i, value)
    registers, flag = cpu.regs.copy(), cpu.zero_flag
    with pytest.raises(PrivilegedOperationViolation) as error:
        cpu.step()
    assert error.value.operation == Opcode.RETI
    assert (cpu.SP, cpu.mode, cpu.PC, cpu.zero_flag, cpu.regs) == (RAM_END - 3, CpuMode.USER, 0, flag, registers)
    assert [cpu.bus.read(cpu.SP + i) for i in range(3)] == frame


def test_nested_syscalls_unwind_inner_kernel_then_outer_user_frame() -> None:
    source = (
        "JUMP boot\nJUMP dispatcher\nboot:\nLOAD R2, <user_main\nPUSH R2\n"
        "LOAD R1, >user_main\nPUSH R1\nLOAD R0, 1\nPUSH R0\nRETI\n"
        "dispatcher:\nLOAD R0, 0\nCMP R3, R0\nJZ first_trap\nRETI\n"
        "first_trap:\nLOAD R3, 1\nSYSCALL\nRETI\n"
        "user_main:\nSYSCALL\nJUMP done\ndone:\nJUMP done"
    )
    cpu, _ = build_machine(assembled(source))
    for _ in range(60):
        cpu.step()
        if cpu.SP == RAM_END - 6:
            break
    assert (cpu.SP, cpu.mode) == (RAM_END - 6, CpuMode.KERNEL)
    for _ in range(30):
        cpu.step()
        if cpu.SP == RAM_END - 3 and cpu.regs[3] == 1:
            break
    assert (cpu.SP, cpu.mode) == (RAM_END - 3, CpuMode.KERNEL)
    assert cpu.bus.read(cpu.PC) == Opcode.RETI.value
    cpu.step()
    assert (cpu.SP, cpu.mode) == (RAM_END, CpuMode.USER)


def test_syscall_stack_fault_is_side_effect_free_and_restores_pc() -> None:
    cpu, _ = build_machine(assembled("SYSCALL"), start_mode=CpuMode.USER)
    cpu.SP, cpu.zero_flag, cpu.regs = RAM_START + 2, True, [1, 2, 3, 4]
    for a, value in zip(range(RAM_START, RAM_START + 3), [0xA1, 0xB2, 0xC3]):
        cpu.bus.write(a, value)
    memory, regs = [cpu.bus.read(a) for a in range(RAM_START, RAM_START + 3)], cpu.regs.copy()
    with pytest.raises(StackPointerOutsideRam) as error:
        cpu.step()
    assert error.value.sp == RAM_START - 1
    assert (cpu.PC, cpu.SP, cpu.mode, cpu.zero_flag, cpu.regs) == (0, RAM_START + 2, CpuMode.USER, True, regs)
    assert [cpu.bus.read(a) for a in range(RAM_START, RAM_START + 3)] == memory


@pytest.mark.parametrize("sp", [RAM_END, RAM_END - 2], ids=["empty", "two-byte-frame"])
def test_reti_stack_fault_is_side_effect_free_and_restores_pc(sp: int) -> None:
    cpu, _ = build_machine(assembled("RETI"))
    cpu.SP, cpu.zero_flag, cpu.regs = sp, True, [0x11, 0x22, 0x33, 0x44]
    regs = cpu.regs.copy()
    ram = [cpu.bus.read(a) for a in range(RAM_START, RAM_END)]
    with pytest.raises(StackPointerOutsideRam) as error:
        cpu.step()
    assert error.value.sp == sp + 3
    assert (cpu.PC, cpu.SP, cpu.mode, cpu.zero_flag, cpu.regs) == (0, sp, CpuMode.KERNEL, True, regs)
    assert [cpu.bus.read(a) for a in range(RAM_START, RAM_END)] == ram


def test_kernel_device_write_works_but_user_device_write_faults_after_reti() -> None:
    source = (
        "TERMINAL = 0x0800\nJUMP boot\nJUMP handler\nboot:\n"
        "LOAD R2, <user_main\nPUSH R2\nLOAD R1, >user_main\nPUSH R1\n"
        "LOAD R0, 1\nPUSH R0\nRETI\nhandler:\nSTORE R1, TERMINAL\nRETI\n"
        "user_main:\nLOAD R1, 'D'\nSYSCALL\nSTORE R1, TERMINAL"
    )
    cpu, device = build_machine(assembled(source))
    for _ in range(40):
        if device.writes and cpu.mode == CpuMode.USER:
            break
        cpu.step()
    fault_pc = cpu.PC
    with pytest.raises(PrivilegedMemoryAccessViolation) as error:
        cpu.step()
    assert error.value.address == 0x0800
    assert (cpu.PC, cpu.mode, device.writes) == (fault_pc, CpuMode.USER, [(0, ord("D"))])


def test_kernel_user_print_exit_program_outputs_de_and_halts() -> None:
    user = "LOAD R3, 0x69\nLOAD R1, 0x44\nLOAD R0, SYS_PRINT_R1\nSYSCALL\nLOAD R3, 0x70\nLOAD R0, SYS_EXIT\nSYSCALL"
    cpu, device = build_machine(end_to_end_program(user))
    run_cpu(cpu)
    assert bytes(value for _, value in device.writes) == b"DE"
    assert cpu.halted is True
    assert cpu.mode == CpuMode.KERNEL


def test_user_registers_survive_syscall_and_can_be_stored_in_ram() -> None:
    user = "LOAD R3, 0x69\nLOAD R1, 0x44\nLOAD R0, SYS_PRINT_R1\nSYSCALL\nSTORE R3, 0x0500\nLOAD R0, SYS_EXIT\nSYSCALL"
    cpu, _ = build_machine(end_to_end_program(user))
    run_cpu(cpu)
    assert cpu.bus.read(0x0500) == 0x69


def test_user_zero_flag_survives_syscall_return() -> None:
    source = user_program(
        "LOAD R0, 7\nLOAD R1, 7\nCMP R0, R1\nSYSCALL\nJUMP done\ndone:\nJUMP done",
        "LOAD R0, 1\nLOAD R1, 2\nCMP R0, R1\nRETI",
    )
    instructions = assemble(source)
    idx = next(i for i, item in enumerate(instructions) if item == bytes([Opcode.SYSCALL.value]))
    return_pc = sum(len(item) for item in instructions[:idx + 1])
    cpu, _ = build_machine(b"".join(instructions))
    for _ in range(50):
        cpu.step()
        if cpu.mode == CpuMode.USER and cpu.PC == return_pc:
            break
    assert (cpu.mode, cpu.PC, cpu.zero_flag) == (CpuMode.USER, return_pc, True)
