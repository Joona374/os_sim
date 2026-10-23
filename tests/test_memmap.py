from conftest import build_machine
from memmap import (
    BUS_FAULT_VECTOR,
    DEVICE_REGION_START,
    KERNEL_ONLY_START,
    KEYBOARD_END,
    KEYBOARD_START,
    MACHINE_FAULT_VECTOR,
    PRIV_FAULT_VECTOR,
    RAM_END,
    RAM_SIZE,
    RAM_START,
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
