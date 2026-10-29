from pathlib import Path
import re

import pytest

from assembler import assemble
from memmap import KEYBOARD_START, RAM_END, STACK_A_END, TERMINAL_START
from machine import Machine
from tps import CpuMode
from conftest import CANONICAL_UNMAPPED_ADDRESS

KERNEL_PATH = Path(__file__).resolve().parents[1] / "asm" / "kernel.asm"


def kernel_source(
    main_body: str,
    initial_flags: int = 1,
    main_b_body: str = "LOAD R0, SYS_EXIT\nSYSCALL",
) -> str:
    source = KERNEL_PATH.read_text() + "\nmain_a:\n" + main_body + "\nmain_b:\n" + main_b_body
    return source.replace(
        "LOAD R2, 1\n    PUSH R2",
        f"LOAD R2, {initial_flags}\n    PUSH R2",
        1,
    )


def assemble_kernel(
    main_body: str,
    message: str | None = None,
    message_address: int | None = None,
    main_b_body: str = "LOAD R0, SYS_EXIT\nSYSCALL",
) -> bytes:
    def render(padding: int, include_probe: bool) -> str:
        body = main_body + "\nJUMP after_test\n"
        if message is not None:
            if padding:
                body += ".byte " + ", ".join("0" for _ in range(padding)) + "\n"
            body += f'message:\n.string "{message}"\n'
        body += "after_test:\nJUMP after_test\n"
        source = kernel_source(body, main_b_body=main_b_body)
        return source + ("\nprobe:\nJUMP message\n" if include_probe else "")

    if message_address is None:
        return b"".join(assemble(render(0, False)))

    assert message is not None
    unpadded = b"".join(assemble(render(0, True)))
    unpadded_address = int.from_bytes(unpadded[-2:], "big")
    padding = message_address - unpadded_address
    assert padding >= 0
    image = b"".join(assemble(render(padding, True)))
    assert int.from_bytes(image[-2:], "big") == message_address
    return image


def build_kernel(
    tmp_path: Path,
    main_body: str,
    message: str | None = None,
    message_address: int | None = None,
    keyboard_buffer: bytearray | bytes | str | None = None,
    main_b_body: str = "LOAD R0, SYS_EXIT\nSYSCALL",
) -> tuple[Machine, bytes]:
    image = assemble_kernel(main_body, message, message_address, main_b_body)
    image_path = tmp_path / "kernel_test.hex"
    image_path.write_text(image.hex(" "))
    return Machine(str(image_path), handle_machine_faults=True, keyboard_buffer=keyboard_buffer), image


def build_printer(tmp_path: Path, keyboard_buffer: bytes | str) -> Machine:
    source_path = Path(__file__).resolve().parents[1] / "asm" / "printer.asm"
    image = b"".join(
        assemble(
            source_path.read_text(),
            filename=str(source_path),
            base_dir=str(source_path.parent),
        )
    )
    image_path = tmp_path / "printer_test.hex"
    image_path.write_text(image.hex(" "))
    return Machine(str(image_path), handle_machine_faults=True, keyboard_buffer=keyboard_buffer)


def assert_cpu_is_polling(cpu, steps: int = 2000) -> None:
    pcs = []
    for _ in range(steps):
        pcs.append(cpu.PC)
        cpu.step()
    assert cpu.halted is False
    assert pcs[-3:] == pcs[-6:-3]


def run_until_syscall_returns(machine: Machine, returns: int = 1) -> None:
    cpu = machine.cpu
    booted = False
    completed = 0
    for _ in range(20000):
        previous_mode = cpu.mode
        cpu.step()
        if cpu.mode == CpuMode.USER:
            if not booted:
                booted = True
            elif previous_mode != CpuMode.USER:
                completed += 1
                if completed == returns:
                    return
        if cpu.halted:
            break
    pytest.fail(f"kernel did not return from {returns} syscall(s)")


def print_string_main(calls: int = 1, zero_flag: bool | None = None) -> str:
    lines = []
    if zero_flag is not None:
        lines.extend(["LOAD R0, 0", f"LOAD R3, {0 if zero_flag else 1}", "CMP R0, R3"])
    lines.extend(
        [
            "LOAD R1, >message",
            "LOAD R2, <message",
            "LOAD R3, 0xA5",
            "LOAD R0, SYS_PRINT_STRING",
            "SYSCALL",
        ]
    )
    if calls == 2:
        lines.extend(["LOAD R0, SYS_PRINT_STRING", "SYSCALL"])
    return "\n".join(lines)


def test_kernel_print_string_short_empty_and_preserves_user_state(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    machine, image = build_kernel(tmp_path, print_string_main(), "hello")

    run_until_syscall_returns(machine)

    assert capsys.readouterr().out == "hello"
    message_address = image.index(b"hello\x00")
    assert machine.cpu.regs == [0, message_address >> 8, message_address & 0xFF, 0xA5]
    assert machine.cpu.SP == STACK_A_END


def test_kernel_print_string_empty_returns_zero_without_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    machine, _ = build_kernel(tmp_path, print_string_main(), "")

    run_until_syscall_returns(machine)

    assert capsys.readouterr().out == ""
    assert machine.cpu.regs[0] == 0
    assert machine.cpu.SP == STACK_A_END


@pytest.mark.parametrize("length", [300, 520], ids=["crosses-one-boundary", "crosses-two-boundaries"])
def test_kernel_print_string_walks_across_boundaries(tmp_path: Path, capsys: pytest.CaptureFixture[str], length: int) -> None:
    text = "A" * length
    machine, _ = build_kernel(tmp_path, print_string_main(), text)

    run_until_syscall_returns(machine)

    assert capsys.readouterr().out == text
    assert machine.cpu.regs[0] == 0


@pytest.mark.parametrize(
    ("message_address", "text", "boundary_bytes"),
    [
        (0x02FF, "ABC", {0x02FF: ord("A"), 0x0300: ord("B"), 0x0301: ord("C"), 0x0302: 0}),
        (0x02FF, "A", {0x02FF: ord("A"), 0x0300: 0}),
        (0x02FE, "AB", {0x02FE: ord("A"), 0x02FF: ord("B"), 0x0300: 0}),
    ],
    ids=["first-byte-at-00ff", "terminator-at-0100", "last-character-at-00ff"],
)
def test_kernel_print_string_boundary_edges_are_at_expected_addresses(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    message_address: int,
    text: str,
    boundary_bytes: dict[int, int],
) -> None:
    machine, image = build_kernel(
        tmp_path,
        print_string_main(),
        text,
        message_address,
    )

    for address, value in boundary_bytes.items():
        assert image[address] == value

    run_until_syscall_returns(machine)

    assert capsys.readouterr().out == text
    assert machine.cpu.regs[0] == 0


@pytest.mark.parametrize("zero_flag", [False, True], ids=["zero-clear", "zero-set"])
def test_kernel_syscall_preserves_zero_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str], zero_flag: bool) -> None:
    machine, _ = build_kernel(tmp_path, print_string_main(zero_flag=zero_flag), "x")

    run_until_syscall_returns(machine)

    assert capsys.readouterr().out == "x"
    assert machine.cpu.zero_flag is zero_flag


def test_kernel_prints_string_twice_after_reloading_only_r0(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    machine, _ = build_kernel(tmp_path, print_string_main(calls=2), "twice")

    run_until_syscall_returns(machine, returns=2)

    assert capsys.readouterr().out == "twicetwice"
    assert machine.cpu.regs[0] == 0
    assert machine.cpu.SP == STACK_A_END


def test_kernel_print_r1_returns_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    machine, _ = build_kernel(
        tmp_path,
        "LOAD R1, 'Q'\nLOAD R0, SYS_PRINT_R1\nSYSCALL",
    )

    run_until_syscall_returns(machine)

    assert capsys.readouterr().out == "Q"
    assert machine.cpu.regs == [0, ord("Q"), 0, 0]


@pytest.mark.parametrize("zero_flag", [False, True], ids=["clear", "set"])
def test_kernel_read_char_returns_key_and_preserves_state(tmp_path: Path, zero_flag: bool) -> None:
    comparison = "CMP R1, R1" if zero_flag else "CMP R1, R2"
    body = "LOAD R1, 0x11\nLOAD R2, 0x22\nLOAD R3, 0x33\n" + comparison + "\nLOAD R0, SYS_READ_CHAR\nSYSCALL"
    machine, _ = build_kernel(tmp_path, body, keyboard_buffer=b"K")

    run_until_syscall_returns(machine)

    assert machine.cpu.regs == [ord("K"), 0x11, 0x22, 0x33]
    assert machine.cpu.SP == STACK_A_END
    assert machine.cpu.zero_flag is zero_flag


def test_kernel_read_char_returns_queued_keys_in_order(tmp_path: Path) -> None:
    body = "LOAD R1, 0x11\nLOAD R2, 0x22\nLOAD R3, 0x33\nCMP R1, R1\n"
    body += "LOAD R0, SYS_READ_CHAR\nSYSCALL\nLOAD R0, SYS_READ_CHAR\nSYSCALL"
    machine, _ = build_kernel(tmp_path, body, keyboard_buffer=b"AB")

    run_until_syscall_returns(machine, returns=2)

    assert machine.cpu.regs == [ord("B"), 0x11, 0x22, 0x33]
    assert machine.cpu.SP == STACK_A_END
    assert machine.cpu.zero_flag is True


def test_kernel_read_char_returns_queued_nul(tmp_path: Path) -> None:
    machine, _ = build_kernel(tmp_path, "LOAD R0, SYS_READ_CHAR\nSYSCALL", keyboard_buffer=b"\x00")

    run_until_syscall_returns(machine)

    assert machine.cpu.regs[0] == 0
    assert machine.cpu.SP == STACK_A_END


def test_kernel_read_char_with_empty_queue_keeps_polling(tmp_path: Path) -> None:
    machine, _ = build_kernel(tmp_path, "LOAD R0, SYS_READ_CHAR\nSYSCALL")

    assert_cpu_is_polling(machine.cpu)


def test_printer_echoes_keys_through_newline_then_exits(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    machine = build_printer(tmp_path, "hi\n")

    machine.cpu.run()

    # The kernel's E exit marker is temporary.
    assert capsys.readouterr().out == "hi\nPE"
    assert machine.cpu.halted is True


def test_printer_echo_does_not_treat_nul_as_empty_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    machine = build_printer(tmp_path, b"\x00\n")

    machine.cpu.run()

    # The kernel's E exit marker is temporary.
    assert capsys.readouterr().out == "\x00\nPE"
    assert machine.cpu.halted is True


def test_printer_without_newline_echoes_then_keeps_polling(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    machine = build_printer(tmp_path, "hi")

    assert_cpu_is_polling(machine.cpu)

    assert capsys.readouterr().out == "hi"


def test_user_keyboard_read_faults_without_consuming_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    machine, _ = build_kernel(
        tmp_path,
        f"LOAD R0, {KEYBOARD_START >> 8}\nLOAD R1, {KEYBOARD_START & 0xFF}\nLDR R2, R0, R1",
        keyboard_buffer=b"K",
    )

    machine.cpu.run()

    assert "PRIVILEGE FAULT" in capsys.readouterr().out
    assert machine.cpu.halted is True
    assert machine.keyboard.read(1) == 1
    assert machine.keyboard.read(0) == ord("K")


def test_kernel_exit_halts_and_prints_temporary_debug_marker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    machine, _ = build_kernel(tmp_path, "LOAD R0, SYS_EXIT\nSYSCALL")

    machine.cpu.run()

    # The E output is a temporary kernel debug marker.
    assert capsys.readouterr().out == "E"
    assert machine.cpu.halted is True


def test_unknown_kernel_syscall_returns_error_without_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    machine, _ = build_kernel(
        tmp_path,
        "LOAD R1, 0x12\nLOAD R2, 0x34\nLOAD R3, 0x56\nLOAD R0, 0x77\nSYSCALL",
    )

    run_until_syscall_returns(machine)

    assert capsys.readouterr().out == ""
    assert machine.cpu.regs == [0xEE, 0x12, 0x34, 0x56]


def test_hostile_string_pointer_faults_in_kernel_and_halts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    machine, _ = build_kernel(
        tmp_path,
        f"LOAD R1, {CANONICAL_UNMAPPED_ADDRESS >> 8}\n" f"LOAD R2, {CANONICAL_UNMAPPED_ADDRESS & 0xFF}\n" "LOAD R0, SYS_PRINT_STRING\nSYSCALL",
    )

    machine.cpu.run()

    assert "BUS FAULT" in capsys.readouterr().out
    assert machine.cpu.halted is True


def test_terminal_pointer_reads_zero_and_prints_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    machine, _ = build_kernel(
        tmp_path,
        f"LOAD R1, {TERMINAL_START >> 8}\nLOAD R2, {TERMINAL_START & 0xFF}\n" "LOAD R0, SYS_PRINT_STRING\nSYSCALL",
    )

    run_until_syscall_returns(machine)

    assert capsys.readouterr().out == ""
    assert machine.cpu.regs[0] == 0


def test_kernel_string_pointer_reads_and_consumes_keyboard_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    machine, _ = build_kernel(
        tmp_path,
        f"LOAD R1, {KEYBOARD_START >> 8}\nLOAD R2, {KEYBOARD_START & 0xFF}\n" "LOAD R0, SYS_PRINT_STRING\nSYSCALL",
        keyboard_buffer=b"K",
    )

    run_until_syscall_returns(machine)

    # A direct kernel pointer currently bypasses user isolation; roadmap isolation is expected to change this.
    assert capsys.readouterr().out == "K"
    assert machine.cpu.regs[0] == 0
    assert machine.keyboard.read(1) == 0


def test_kernel_terminal_constant_matches_memmap() -> None:
    source = KERNEL_PATH.read_text()
    terminal = re.search(r"(?m)^TERMINAL\s*=\s*(\S+)", source)

    assert terminal is not None
    assert int(terminal.group(1), 0) == TERMINAL_START


def test_two_processes_alternate_with_yield_and_last_exit_halts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main_a = """
LOAD R1, 'A'
LOAD R2, 2
a_loop:
LOAD R0, SYS_PRINT_R1
SYSCALL
SUBI R2, 1
LOAD R0, SYS_YIELD
SYSCALL
CMPI R2, 0
JNZ a_loop
LOAD R0, SYS_EXIT
SYSCALL
"""
    main_b = """
LOAD R1, 'B'
LOAD R2, 2
b_loop:
LOAD R0, SYS_PRINT_R1
SYSCALL
SUBI R2, 1
LOAD R0, SYS_YIELD
SYSCALL
CMPI R2, 0
JNZ b_loop
LOAD R0, SYS_EXIT
SYSCALL
"""
    machine, _ = build_kernel(tmp_path, main_a, main_b_body=main_b)

    machine.cpu.run()

    assert capsys.readouterr().out == "ABABE"
    assert machine.cpu.halted is True


def test_lone_yield_returns_success_after_other_process_exits(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main_a = """
LOAD R0, SYS_YIELD
SYSCALL
LOAD R0, SYS_YIELD
SYSCALL
CMPI R0, 0
JNZ failed
LOAD R1, 'A'
LOAD R0, SYS_PRINT_R1
SYSCALL
LOAD R0, SYS_EXIT
SYSCALL
failed:
LOAD R1, '!'
LOAD R0, SYS_PRINT_R1
SYSCALL
LOAD R0, SYS_EXIT
SYSCALL
"""
    machine, _ = build_kernel(tmp_path, main_a)

    machine.cpu.run()

    assert capsys.readouterr().out == "AE"
    assert machine.cpu.halted is True


def test_mixed_depth_yields_return_zero_after_partner_exits(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main_a = """
LOAD R2, 2
LOAD R1, 'A'
a_loop:
LOAD R0, SYS_PRINT_R1
SYSCALL
SUBI R2, 1
LOAD R0, SYS_YIELD
SYSCALL
CMPI R2, 0
JNZ a_loop
LOAD R0, SYS_EXIT
SYSCALL
"""
    main_b = """
LOAD R1, 'B'
LOAD R2, 2
b_direct_loop:
LOAD R0, SYS_PRINT_R1
SYSCALL
LOAD R0, SYS_YIELD
SYSCALL
SUBI R2, 1
JNZ b_direct_loop
LOAD R2, 3
b_sub_loop:
LOAD R0, SYS_PRINT_R1
SYSCALL
CALL b_yielder
CMPI R0, 0
JZ b_result_ok
LOAD R1, '!'
LOAD R0, SYS_PRINT_R1
SYSCALL
LOAD R1, 'B'
b_result_ok:
SUBI R2, 1
JNZ b_sub_loop
LOAD R0, SYS_EXIT
SYSCALL
b_yielder:
LOAD R0, SYS_YIELD
SYSCALL
RET
"""
    machine, _ = build_kernel(tmp_path, main_a, main_b_body=main_b)

    machine.cpu.run()

    output = capsys.readouterr().out
    assert output == "ABABBBBE"
    assert "!" not in output
    assert machine.cpu.halted is True


def test_key_ready_and_read_char_interleave_with_other_process(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main_a = """
LOAD R3, 0
poll_key:
LOAD R0, SYS_KEY_READY
SYSCALL
CMPI R0, 1
JNZ yield_and_poll
LOAD R0, SYS_READ_CHAR
SYSCALL
MOV R1, R0
LOAD R0, SYS_PRINT_R1
SYSCALL
ADDI R3, 1
CMPI R3, 2
JZ finish
LOAD R0, SYS_YIELD
SYSCALL
JUMP poll_key
yield_and_poll:
LOAD R0, SYS_YIELD
SYSCALL
JUMP poll_key
finish:
LOAD R0, SYS_EXIT
SYSCALL
"""
    main_b = """
LOAD R1, 'B'
LOAD R0, SYS_PRINT_R1
SYSCALL
LOAD R0, SYS_YIELD
SYSCALL
LOAD R0, SYS_EXIT
SYSCALL
"""
    machine, _ = build_kernel(
        tmp_path,
        main_a,
        keyboard_buffer=b"ab",
        main_b_body=main_b,
    )

    for _ in range(2000):
        machine.cpu.step()
        if machine.keyboard.read(1) == 0:
            break
    else:
        pytest.fail("kernel did not consume the first keyboard key")

    machine.keyboard._ticks_per_keypress = 100
    machine.keyboard._ticks_left_till_keypress = 100
    machine.cpu.run()

    output = capsys.readouterr().out
    assert output == "aBbE"
    assert output.index("a") < output.index("B") < output.index("b")
    assert machine.cpu.halted is True
