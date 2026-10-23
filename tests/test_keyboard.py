from pathlib import Path

import pytest

from assembler import assemble
from device import Keyboard, Terminal
from exceptions import BusFaultUnmappedAddress, PrivilegedMemoryAccessViolation
from machine import Machine
from memmap import KEYBOARD_START
from tps import CpuMode
from conftest import CANONICAL_UNMAPPED_ADDRESS


def assembled(source: str) -> bytes:
    return b"".join(assemble(source))


def build_machine(tmp_path: Path, program: bytes, keyboard_buffer=None, start_mode=CpuMode.KERNEL) -> Machine:
    image_path = tmp_path / "keyboard_test.hex"
    image_path.write_text(program.hex(" "))
    return Machine(str(image_path), keyboard_buffer=keyboard_buffer, start_mode=start_mode)


def test_keyboard_data_and_status_register_drain_queue_in_order() -> None:
    keyboard = Keyboard(bytearray(b"abc"))

    assert keyboard.read(1) == 1
    assert keyboard.read(1) == 1
    assert [keyboard.read(0), keyboard.read(0), keyboard.read(0)] == list(b"abc")
    assert keyboard.read(1) == 0
    assert keyboard.read(0) == 0
    assert keyboard.read(1) == 0


@pytest.mark.parametrize("buffer", [b"xy", bytearray(b"xy"), "xy"])
def test_keyboard_accepts_bytes_bytearray_and_ascii_string(buffer) -> None:
    keyboard = Keyboard(buffer)
    assert keyboard.read(0) == ord("x")
    assert keyboard.read(0) == ord("y")
    assert keyboard.read(0) == 0


def test_keyboard_nul_is_distinguished_by_status() -> None:
    keyboard = Keyboard(b"\x00")

    assert keyboard.read(1) == 1
    assert keyboard.read(0) == 0
    assert keyboard.read(1) == 0


def test_keyboard_ignores_all_writes_and_unknown_reads_return_zero() -> None:
    keyboard = Keyboard(b"k")
    for offset in (0, 1, 2, 0x3FF):
        keyboard.write(offset, 0xA5)

    assert keyboard.read(1) == 1
    assert keyboard.read(2) == 0
    assert keyboard.read(0) == ord("k")
    assert keyboard.read(1) == 0
    assert keyboard.read(0x3FF) == 0


def test_keyboard_copies_caller_buffer_for_each_instance() -> None:
    source = bytearray(b"keys")
    first = Keyboard(source)
    second = Keyboard(source)

    source[0] = ord("X")
    assert [first.read(0) for _ in range(4)] == list(b"keys")
    assert [second.read(0) for _ in range(4)] == list(b"keys")


def test_machine_forwards_keyboard_buffer_to_cpu_reads(tmp_path: Path) -> None:
    program = assembled("LDR R2, R0, R1\nLDR R3, R0, R1\nLDR R2, R0, R1")
    machine = build_machine(tmp_path, program, bytearray(b"Q"))
    machine.cpu.regs[:2] = [KEYBOARD_START >> 8, 1]

    machine.cpu.step()
    assert machine.cpu.regs[2] == 1
    machine.cpu.regs[1] = 0
    machine.cpu.step()
    assert machine.cpu.regs[3] == ord("Q")
    machine.cpu.regs[1] = 1
    machine.cpu.step()
    assert machine.cpu.regs[2] == 0


def test_machine_keyboard_defaults_to_empty(tmp_path: Path) -> None:
    machine = build_machine(tmp_path, assembled("HALT"))
    assert machine.keyboard.read(1) == 0
    assert machine.keyboard.read(0) == 0


@pytest.mark.parametrize("offset", [0, 1], ids=["data-register", "status-register"])
def test_user_cpu_cannot_read_keyboard(tmp_path: Path, offset: int) -> None:
    machine = build_machine(
        tmp_path,
        assembled("LDR R2, R0, R1"),
        b"K",
        start_mode=CpuMode.USER,
    )
    machine.cpu.regs[:2] = [KEYBOARD_START >> 8, offset]

    with pytest.raises(PrivilegedMemoryAccessViolation):
        machine.cpu.step()

    assert machine.cpu.PC == 0
    assert machine.keyboard.read(1) == 1
    assert machine.keyboard.read(0) == ord("K")


def test_machine_unmapped_address_in_gap_faults(tmp_path: Path) -> None:
    machine = build_machine(tmp_path, assembled("LDR R2, R0, R1"))
    address = CANONICAL_UNMAPPED_ADDRESS
    machine.cpu.regs[:2] = [address >> 8, address & 0xFF]

    with pytest.raises(BusFaultUnmappedAddress):
        machine.cpu.step()

    assert machine.cpu.PC == 0


def test_terminal_reads_zero_and_writes_print(capsys: pytest.CaptureFixture[str]) -> None:
    terminal = Terminal(tracing_mode=False)
    assert terminal.read(0) == 0
    terminal.write(0, ord("T"))
    assert capsys.readouterr().out == "T"
