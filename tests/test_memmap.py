from pathlib import Path
import re

import pytest

from conftest import build_machine
from device import ROM
from exceptions import ProgramDoesntFitOnRom
from memmap import (
    BUS_FAULT_VECTOR,
    DEVICE_REGION_START,
    KERNEL_ONLY_START,
    KEYBOARD_END,
    KERNEL_DATA_END,
    KERNEL_DATA_SIZE,
    KERNEL_DATA_START,
    KEYBOARD_START,
    MACHINE_FAULT_VECTOR,
    PRIV_FAULT_VECTOR,
    RAM_END,
    RAM_SIZE,
    RAM_START,
    STACK_A_END,
    STACK_A_SIZE,
    STACK_A_START,
    STACK_B_END,
    STACK_B_SIZE,
    STACK_B_START,
    BOOT_STACK_END,
    BOOT_STACK_SIZE,
    BOOT_STACK_START,
    RESET_VECTOR,
    ROM_END,
    ROM_SIZE,
    ROM_START,
    SYSCALL_TRAP_VECTOR,
    TERMINAL_END,
    TERMINAL_START,
)
from tps import KB


def test_memmap_regions_and_vectors_are_consistent() -> None:
    assert ROM_END == ROM_START + ROM_SIZE
    assert RAM_END == RAM_START + RAM_SIZE
    assert TERMINAL_END == TERMINAL_START + KB
    assert KEYBOARD_END == KEYBOARD_START + KB

    assert ROM_END <= RAM_START
    assert RAM_END <= DEVICE_REGION_START
    assert TERMINAL_START == DEVICE_REGION_START
    assert KERNEL_ONLY_START == DEVICE_REGION_START
    assert TERMINAL_END <= KEYBOARD_START or KEYBOARD_END <= TERMINAL_START

    vectors = [
        RESET_VECTOR,
        SYSCALL_TRAP_VECTOR,
        PRIV_FAULT_VECTOR,
        BUS_FAULT_VECTOR,
        MACHINE_FAULT_VECTOR,
    ]
    assert all(ROM_START <= vector and vector + 3 <= ROM_END for vector in vectors)
    assert all(right - left == 3 for left, right in zip(vectors, vectors[1:]))


def test_cpu_starts_at_reset_vector_with_empty_stack() -> None:
    cpu, _ = build_machine(bytes([0x01]))

    assert cpu.SP == RAM_END
    assert cpu.PC == RESET_VECTOR


def test_memory_regions_are_ordered_and_do_not_overlap() -> None:
    regions = sorted(
        [
            (ROM_START, ROM_END),
            (RAM_START, RAM_END),
            (TERMINAL_START, TERMINAL_END),
            (KEYBOARD_START, KEYBOARD_END),
        ]
    )

    assert regions == [
        (ROM_START, ROM_END),
        (RAM_START, RAM_END),
        (TERMINAL_START, TERMINAL_END),
        (KEYBOARD_START, KEYBOARD_END),
    ]
    assert all(left[1] <= right[0] for left, right in zip(regions, regions[1:]))
    assert RAM_END <= 0x8000 < DEVICE_REGION_START


def test_kernel_ram_blocks_are_contiguous_and_fill_ram() -> None:
    assert [KERNEL_DATA_SIZE, STACK_A_SIZE, STACK_B_SIZE, BOOT_STACK_SIZE] == [KB] * 4
    assert KERNEL_DATA_START == RAM_START
    assert KERNEL_DATA_END == STACK_A_START
    assert STACK_A_END == STACK_B_START
    assert STACK_B_END == BOOT_STACK_START
    assert BOOT_STACK_END == RAM_END


def test_kernel_device_constants_match_memory_map() -> None:
    source = (Path(__file__).resolve().parents[1] / "asm" / "kernel.asm").read_text()
    values = {name: int(value, 0) for name, value in re.findall(r"(?m)^(TERMINAL|KEYBOARD_BUFFER|KEYBOARD_FLAGS)\s*=\s*(\S+)", source)}

    assert values == {
        "TERMINAL": TERMINAL_START,
        "KEYBOARD_BUFFER": KEYBOARD_START,
        "KEYBOARD_FLAGS": KEYBOARD_START + 1,
    }


def test_program_larger_than_rom_raises_program_doesnt_fit() -> None:
    with pytest.raises(ProgramDoesntFitOnRom):
        ROM(bytes(ROM_SIZE + 1), ROM_SIZE // KB)
