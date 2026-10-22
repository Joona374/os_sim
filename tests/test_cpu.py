from pathlib import Path
import re

import pytest

from cpu import CPU
from exceptions import InvalidCpuRegister, MachineFault
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


@pytest.mark.parametrize(
    ("register_value", "immediate", "initial_flag", "expected_flag"),
    [
        (0x00, 0x00, False, True),
        (0x00, 0xFF, True, False),
        (0xFF, 0xFF, False, True),
        (0xFF, 0x00, True, False),
    ],
    ids=["zero-equal", "zero-unequal-clears", "max-equal", "max-unequal-clears"],
)
def test_cmpi_sets_zero_flag_without_changing_registers(
    register_value: int, immediate: int, initial_flag: bool, expected_flag: bool
) -> None:
    cpu, _ = build_machine(bytes([Opcode.CMPI.value, 0, immediate]))
    cpu.regs = [register_value, 0x12, 0x34, 0x56]
    registers = cpu.regs.copy()
    cpu.zero_flag = initial_flag

    cpu.step()

    assert cpu.regs == registers
    assert cpu.zero_flag is expected_flag
    assert cpu.PC == 3


@pytest.mark.parametrize(
    ("initial", "immediate", "expected", "initial_flag", "expected_flag"),
    [
        (7, 5, 12, False, False),
        (0xFF, 1, 0, False, True),
        (0, 0, 0, False, True),
        (2, 1, 3, True, False),
    ],
    ids=["normal-add", "wraps-to-zero", "zero-plus-zero", "clears-set-zero"],
)
def test_addi_wraps_result_sets_zero_flag_and_preserves_other_registers(
    initial: int, immediate: int, expected: int, initial_flag: bool, expected_flag: bool
) -> None:
    cpu, _ = build_machine(bytes([Opcode.ADDI.value, 1, immediate]))
    cpu.regs = [0x11, initial, 0x33, 0x44]
    cpu.zero_flag = initial_flag

    cpu.step()

    assert cpu.regs == [0x11, expected, 0x33, 0x44]
    assert cpu.zero_flag is expected_flag
    assert cpu.PC == 3


@pytest.mark.parametrize("zero_flag", [False, True], ids=["taken", "not-taken"])
def test_jnz_consumes_address_without_changing_zero_flag(zero_flag: bool) -> None:
    cpu, _ = build_machine(bytes([Opcode.JNZ.value, 0, 6, Opcode.HALT.value, Opcode.HALT.value, Opcode.HALT.value, Opcode.HALT.value]))
    cpu.zero_flag = zero_flag

    cpu.step()

    assert cpu.PC == (3 if zero_flag else 6)
    assert cpu.zero_flag is zero_flag


@pytest.mark.parametrize("opcode", [Opcode.CMPI, Opcode.ADDI], ids=["CMPI", "ADDI"])
def test_new_instruction_invalid_register_fault_is_side_effect_free(opcode: Opcode) -> None:
    cpu, _ = build_machine(bytes([opcode.value, 4, 0xA5]))
    cpu.regs = [0x11, 0x22, 0x33, 0x44]
    cpu.zero_flag = True
    cpu.SP -= 2
    registers = cpu.regs.copy()
    memory = [cpu.bus.read(address) for address in range(0x0400, 0x0800)]
    initial = (cpu.SP, cpu.mode, cpu.zero_flag, cpu.regs.copy())

    with pytest.raises(InvalidCpuRegister):
        cpu.step()

    assert cpu.PC == 0
    assert (cpu.SP, cpu.mode, cpu.zero_flag, cpu.regs) == initial
    assert cpu.regs == registers
@pytest.mark.parametrize("zero_flag", [False, True], ids=["clear", "set"])
def test_mov_copies_register_without_changing_source_or_zero_flag(zero_flag: bool) -> None:
    cpu, _ = build_machine(bytes([Opcode.MOV.value, 0, 1]))
    cpu.regs = [0x11, 0xA5, 0x33, 0x44]
    cpu.zero_flag = zero_flag

    cpu.step()

    assert cpu.regs == [0xA5, 0xA5, 0x33, 0x44]
    assert cpu.zero_flag is zero_flag
    assert cpu.PC == 3


def test_mov_same_register_is_valid_and_cmp_branch_flag_survives_mov() -> None:
    program = bytes(
        [0x02, 0, 7, 0x02, 1, 7, 0x05, 0, 1, Opcode.MOV.value, 2, 2,
         0x06, 0, 18, 0x02, 3, 0xEE, 0x01]
    )
    cpu = run_program(program)

    assert cpu.regs == [7, 7, 0, 0]
    assert cpu.zero_flag is True


@pytest.mark.parametrize(
    ("destination", "source"),
    [(0, 4), (4, 0)],
    ids=["invalid-source", "valid-source-invalid-destination"],
)
def test_mov_invalid_register_fault_is_side_effect_free(destination: int, source: int) -> None:
    cpu, _ = build_machine(bytes([Opcode.MOV.value, destination, source]))
    cpu.regs = [0x11, 0x22, 0x33, 0x44]
    cpu.zero_flag = True
    cpu.SP -= 2
    registers = cpu.regs.copy()
    memory = [cpu.bus.read(address) for address in range(0x0400, 0x0800)]
    initial = (cpu.SP, cpu.mode, cpu.zero_flag, cpu.regs.copy())

    with pytest.raises(InvalidCpuRegister):
        cpu.step()

    assert cpu.PC == 0
    assert (cpu.SP, cpu.mode, cpu.zero_flag, cpu.regs) == initial
    assert [cpu.bus.read(address) for address in range(0x0400, 0x0800)] == memory


    assert [cpu.bus.read(address) for address in range(0x0400, 0x0800)] == memory


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

    docs = Path(__file__).resolve().parents[1] / "docs" / "ISA.md"
    rows = {
        mnemonic: int(opcode, 16)
        for mnemonic, opcode in re.findall(
            r"^\| `([A-Z]+)` \| `([0-9A-F]{2})` \|", docs.read_text(), re.MULTILINE
        )
    }
    assert rows == {opcode.name: opcode.value for opcode in Opcode}