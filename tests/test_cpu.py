import pytest

from cpu import CPU
from exceptions import MachineFault
from isa import LAYOUT, Opcode

from conftest import build_machine, run_program


def test_load_sets_register() -> None:
    cpu = run_program(bytes([0x02, 0x01, 0xA5, 0x01]))
    assert cpu.regs[1] == 0xA5


def test_store_writes_register_to_address() -> None:
    cpu = run_program(bytes([0x02, 0x02, 0xA5, 0x03, 0x02, 0x04, 0x00, 0x01]))
    assert cpu.bus.read(0x0400) == 0xA5


def test_jump_skips_code_and_supports_nonzero_high_byte() -> None:
    skipped = run_program(bytes([0x02, 0x00, 0xAA, 0x04, 0x00, 0x09, 0x02, 0x00, 0xBB, 0x01]))
    assert skipped.regs[0] == 0xAA

    image = bytes([0x04, 0x01, 0x20]) + bytes(0x0120 - 3) + bytes([0x01])
    high_address = run_program(image)
    assert high_address.halted
    assert high_address.PC == 0x0121


def test_cmp_sets_zero_flag_when_registers_are_equal() -> None:
    cpu = run_program(bytes([0x02, 0x00, 7, 0x02, 0x01, 7, 0x05, 0x00, 0x01, 0x01]))
    assert cpu.zero_flag is True


def test_cmp_clears_zero_flag_after_unequal_comparison() -> None:
    program = bytes([0x02, 0x00, 1, 0x02, 0x01, 1, 0x05, 0, 1, 0x02, 0x01, 2, 0x05, 0, 1, 1])
    cpu = run_program(program)
    assert cpu.zero_flag is False


def test_jz_jumps_when_zero_flag_is_set_and_falls_through_when_clear() -> None:
    set_program = bytes([0x02, 0, 1, 0x02, 1, 1, 0x05, 0, 1, 0x06, 0, 15, 0x02, 2, 0xAA, 1])
    clear_program = bytes([0x02, 0, 1, 0x02, 1, 2, 0x05, 0, 1, 0x06, 0, 15, 0x02, 2, 0xAA, 1])

    assert run_program(set_program).regs[2] == 0
    assert run_program(clear_program).regs[2] == 0xAA


def test_add_and_sub_produce_normal_results() -> None:
    added = run_program(bytes([0x02, 0, 2, 0x02, 1, 3, 0x07, 0, 1, 1]))
    subtracted = run_program(bytes([0x02, 0, 7, 0x02, 1, 2, 0x08, 0, 1, 1]))
    assert added.regs[0] == 5
    assert subtracted.regs[0] == 5


def test_add_wraps_255_plus_1_and_sets_zero_flag() -> None:
    cpu = run_program(bytes([0x02, 0, 255, 0x02, 1, 1, 0x07, 0, 1, 1]))
    assert cpu.regs[0] == 0
    assert cpu.zero_flag is True


def test_sub_wraps_0_minus_1_and_clears_zero_flag() -> None:
    cpu = run_program(bytes([0x02, 0, 0, 0x02, 1, 1, 0x08, 0, 1, 1]))
    assert cpu.regs[0] == 255
    assert cpu.zero_flag is False


def test_subtracting_equal_values_sets_zero_flag() -> None:
    cpu = run_program(bytes([0x02, 0, 5, 0x02, 1, 5, 0x08, 0, 1, 1]))
    assert cpu.regs[0] == 0
    assert cpu.zero_flag is True


def test_ldr_reads_from_ram_and_rom() -> None:
    ram_program = bytes([0x02, 1, 0xAB, 0x03, 1, 0x04, 0x00, 0x02, 2, 4, 0x02, 3, 0, 0x09, 0, 2, 3, 1])
    rom_program = bytes([0x02, 2, 0, 0x02, 3, 11, 0x09, 0, 2, 3, 0x01, 0xAB])

    assert run_program(ram_program).regs[0] == 0xAB
    assert run_program(rom_program).regs[0] == 0xAB


@pytest.mark.parametrize("opcode", [0x00, 0xFF])
def test_unassigned_or_unknown_opcode_raises_machine_fault(opcode: int) -> None:
    cpu, _ = build_machine(bytes([opcode]))
    with pytest.raises(MachineFault):
        cpu.step()


@pytest.mark.parametrize(
    "instruction",
    [bytes([0x02, 4, 0, 1]), bytes([0x05, 4, 0, 1]), bytes([0x07, 4, 0, 1]), bytes([0x08, 4, 0, 1])],
    ids=["LOAD", "CMP", "ADD", "SUB"],
)
def test_invalid_register_raises_machine_fault(instruction: bytes) -> None:
    cpu, _ = build_machine(instruction)
    with pytest.raises(MachineFault):
        cpu.step()


def test_store_into_rom_raises_machine_fault() -> None:
    cpu, _ = build_machine(bytes([0x02, 0, 0xAA, 0x03, 0, 0, 0, 1]))
    with pytest.raises(MachineFault):
        cpu.run()


def test_fetch_and_ldr_read_from_unmapped_addresses_raise_machine_fault() -> None:
    fetch_cpu, _ = build_machine(bytes([0x04, 0x0C, 0x00]))
    with pytest.raises(MachineFault):
        fetch_cpu.run()

    read_program = bytes([0x02, 2, 0x0C, 0x02, 3, 0, 0x09, 0, 2, 3])
    read_cpu, _ = build_machine(read_program)
    with pytest.raises(MachineFault):
        read_cpu.run()


def test_each_opcode_has_layout_and_cpu_handler() -> None:
    cpu, _ = build_machine(bytes([Opcode.HALT.value]))
    assert set(LAYOUT) == set(Opcode)
    assert set(cpu.operation_to_handler) == set(Opcode)