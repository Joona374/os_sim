from pathlib import Path

import pytest

from assembler import AssemblerError, assemble

from conftest import build_machine


def test_hello_program_matches_supplied_golden_bytes() -> None:
    source_path = Path(__file__).resolve().parents[1] / "asm" / "hello_rom.asm"
    source = source_path.read_text()
    expected = bytes.fromhex(
        "02 02 00 02 03 21 09 00 02 03 02 01 00 05 00 01 06 00 20 "
        "03 00 08 00 02 01 01 07 03 01 04 00 06 01 48 45 4C 4C 4F 21 0A 00"
    )
    program = b"".join(assemble(source))
    assert program == expected


def test_existing_hello_program_outputs_expected_text() -> None:
    source_path = Path(__file__).resolve().parents[1] / "asm" / "hello_rom.asm"
    program = b"".join(assemble(source_path.read_text()))
    cpu, recording_device = build_machine(program)
    cpu.run()
    assert bytes(value for _, value in recording_device.writes) == b"HELLO!\n"


def test_forward_label_reference_resolves() -> None:
    program = b"".join(assemble("JUMP target\nHALT\ntarget:\nHALT"))
    assert program == bytes([0x04, 0x00, 0x04, 0x01, 0x01])


@pytest.mark.parametrize(
    "source",
    ["MISSING\n", "LOAD R0\n", "LOAD R0, 256\n", "LOAD RX, 1\n"],
    ids=["unknown-mnemonic", "wrong-operand-count", "immediate-too-large", "bad-register"],
)
def test_assembler_errors_include_source_line(source: str) -> None:
    with pytest.raises(AssemblerError, match=r"line 1:"):
        assemble(source)


def test_byte_emits_numbers_characters_constants_and_label_bytes() -> None:
    program = b"".join(assemble("VALUE = 0x43\n.byte 65, 'B', VALUE, >target, <target\ntarget:\nHALT"))
    assert program == bytes([65, 66, 67, 0, 5, 0x01])


@pytest.mark.parametrize("source", [".byte 256\n", ".byte\n"], ids=["too-large", "empty-list"])
def test_byte_rejects_invalid_values(source: str) -> None:
    with pytest.raises(AssemblerError, match=r"line 1:"):
        assemble(source)


def test_string_emits_plain_text_and_empty_string_terminator() -> None:
    assert b"".join(assemble('.string "hello"')) == b"hello\x00"
    assert b"".join(assemble('.string ""')) == b"\x00"


def test_string_decodes_each_supported_escape() -> None:
    source = '.string "' + r"\n\t\0\\\"\'" + '"'
    assert b"".join(assemble(source)) == bytes([10, 9, 0, 92, 34, 39, 0])


def test_string_keeps_spaces_commas_semicolons_and_equals_as_data() -> None:
    assert b"".join(assemble('.string "a b,c;d=e"')) == b"a b,c;d=e\x00"


@pytest.mark.parametrize("source", ['.string "unfinished\n', ".string\n"], ids=["unterminated", "missing-operand"])
def test_string_rejects_missing_or_unterminated_operand(source: str) -> None:
    with pytest.raises(AssemblerError, match=r"line 1:"):
        assemble(source)


def test_labels_account_for_byte_and_string_directive_sizes() -> None:
    source = "JUMP after_byte\n.byte 0\nafter_byte:\nJUMP after_string\n.string \"x\"\nafter_string:\nHALT"
    program = b"".join(assemble(source))
    assert program == bytes([0x04, 0, 4, 0, 0x04, 0, 9, ord("x"), 0, 1])


def test_constants_work_forward_in_operands_and_byte_directives() -> None:
    source = "LOAD R0, VALUE\n.byte VALUE\nVALUE = 0x2A\nHALT"
    assert b"".join(assemble(source)) == bytes([0x02, 0, 0x2A, 0x2A, 0x01])


def test_constants_without_spaces_can_reference_earlier_constants() -> None:
    source = "BASE=0x20\nNEXT=BASE\nLOAD R0,NEXT\nHALT"
    assert b"".join(assemble(source)) == bytes([0x02, 0, 0x20, 0x01])


def test_new_instruction_encodings_accept_constants_and_label_bytes() -> None:
    source = (
        "SOME_CONSTANT = 0xA5\n"
        "CMPI R0, SOME_CONSTANT\n"
        "ADDI R1, >target\n"
        "CMPI R2, <target\n"
        "JNZ target\n"
        "HALT\n"
        "target:\n"
        "HALT"
    )
    assert b"".join(assemble(source)) == bytes(
        [0x11, 0, 0xA5, 0x12, 1, 0, 0x11, 2, 0x0D, 0x10, 0, 0x0D, 0x01, 0x01]
    )


@pytest.mark.parametrize(
    "source",
    [
        "CMPI R0, 256\n",
        "CMPI R0, -1\n",
        "ADDI R0, 256\n",
        "ADDI R0, -1\n",
        "CMPI R4, 1\n",
        "ADDI R4, 1\n",
        "JNZ\n",
        "CMPI R0\n",
        "ADDI R0, 1, 2\n",
        "JNZ 0, 1\n",
    ],
    ids=[
        "cmpi-too-large", "cmpi-negative", "addi-too-large", "addi-negative",
        "cmpi-bad-register", "addi-bad-register", "jnz-missing-operand",
        "cmpi-missing-operand", "addi-extra-operand", "jnz-extra-operand",
    ],
)
def test_new_instructions_reject_invalid_operands(source: str) -> None:
    with pytest.raises(AssemblerError, match=r"line 1:"):
        assemble(source)


@pytest.mark.parametrize(
    ("source", "line_no"),
    [
        ("A=1\nA=2\n", 2),
        ("LOAD R0, UNKNOWN\n", 1),
        ("r1=2\n", 1),
        ("BROKEN =\n", 1),
        ("same:\nsame=1\n", 2),
        ("A = LATER\nLATER=1\n", 1),
    ],
    ids=["redefinition", "unknown-name", "register-like-name", "malformed", "shared-namespace", "forward-value"],
)
def test_invalid_constant_definitions_raise_line_numbered_error(source: str, line_no: int) -> None:
    with pytest.raises(AssemblerError, match=rf"line {line_no}:"):
        assemble(source)


def test_high_and_low_operators_resolve_labels_above_255() -> None:
    source = ".byte 0\n" * 0x100 + "target:\n.byte >target, <target"
    assert b"".join(assemble(source))[-2:] == bytes([0x01, 0x00])


def test_high_and_low_operators_resolve_numbers_and_constants() -> None:
    source = "VALUE=0xABCD\n.byte >0x1234, <0x1234, >VALUE, <VALUE"
    assert b"".join(assemble(source)) == bytes([0x12, 0x34, 0xAB, 0xCD])