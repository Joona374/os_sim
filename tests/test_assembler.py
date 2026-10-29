from pathlib import Path
import sys

import pytest

import assembler as assembler_module
from assembler import AssemblerError, assemble
from memmap import TERMINAL_START

def test_printer_source_assembles_with_kernel_vectors_first() -> None:
    source_path = Path(__file__).resolve().parents[1] / "asm" / "printer.asm"
    program = b"".join(assemble(
        source_path.read_text(), filename=str(source_path), base_dir=str(source_path.parent)
    ))

    assert program[0:15:3] == bytes([0x04] * 5)
    assert bytes([0x13, 1, 0]) in program


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
        "MOV R2, R3\n"
        "HALT\n"
        "target:\n"
        "HALT"
    )
    assert b"".join(assemble(source)) == bytes(
        [0x11, 0, 0xA5, 0x12, 1, 0, 0x11, 2, 0x10, 0x10, 0, 0x10,
         0x13, 2, 3, 0x01, 0x01]
    )


def test_stack_pointer_and_absolute_memory_instruction_encodings() -> None:
    source = "GETSP R0, R1\nSETSP R2, R3\nLDA R1, 0xABCD\nSUBI R2, 0xFE"
    assert b"".join(assemble(source)) == bytes([0x15, 0, 1, 0x14, 2, 3, 0x16, 1, 0xAB, 0xCD, 0x17, 2, 0xFE])


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
        "cmpi-too-large",
        "cmpi-negative",
        "addi-too-large",
        "addi-negative",
        "cmpi-bad-register",
        "addi-bad-register",
        "jnz-missing-operand",
        "cmpi-missing-operand",
        "addi-extra-operand",
        "jnz-extra-operand",
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


def test_include_places_kernel_first_and_exports_its_constants(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    (tmp_path / "kernel.asm").write_text((repository / "asm" / "kernel.asm").read_text())
    main_path = tmp_path / "main.asm"
    source = '.include "kernel.asm"\nmain_b:\nHALT\nmain_a:\nSTORE R0, TERMINAL\nLOAD R0, SYS_READ_CHAR\n'

    program = b"".join(assemble(source, filename=str(main_path), base_dir=str(tmp_path)))

    assert program[0:15:3] == bytes([0x04] * 5)
    assert program[-7:] == bytes(
        [0x03, 0, TERMINAL_START >> 8, TERMINAL_START & 0xFF, 0x02, 0, 4]
    )


def test_include_paths_are_relative_to_each_file_and_may_nest(tmp_path: Path) -> None:
    nested = tmp_path / "sub" / "nested"
    nested.mkdir(parents=True)
    (nested / "second.asm").write_text(".byte 1\n")
    (tmp_path / "sub" / "first.asm").write_text('.include "nested/second.asm"\n.byte 2\n')
    main_path = tmp_path / "main.asm"

    program = assemble('.InClUdE "sub/first.asm"\n.byte 3\n', str(main_path), str(tmp_path))

    assert b"".join(program) == bytes([1, 2, 3])


def test_include_inside_comment_is_ignored() -> None:
    assert b"".join(assemble('; .include "missing.asm"\n.byte 7')) == bytes([7])


@pytest.mark.parametrize(
    "source",
    [
        ".include\n",
        ".include missing.asm\n",
        '.include "one.asm" "two.asm"\n',
        'label: .include "one.asm"\n',
    ],
    ids=["missing-operand", "unquoted-name", "two-operands", "label-on-directive"],
)
def test_include_rejects_malformed_directives(tmp_path: Path, source: str) -> None:
    path = tmp_path / "main.asm"
    with pytest.raises(AssemblerError) as error:
        assemble(source, filename=str(path), base_dir=str(tmp_path))
    assert error.value.filename == str(path)
    assert error.value.line_no == 1


def test_missing_include_names_source_file_and_read_error(tmp_path: Path) -> None:
    path = tmp_path / "main.asm"

    with pytest.raises(AssemblerError, match="cannot read include file") as error:
        assemble('.include "absent.asm"', str(path), str(tmp_path))

    assert error.value.filename == str(path)
    assert error.value.line_no == 1


def test_circular_include_reports_the_include_chain(tmp_path: Path) -> None:
    first = tmp_path / "a.asm"
    second = tmp_path / "b.asm"
    first.write_text('.include "b.asm"\n')
    second.write_text('.include "a.asm"\n')

    with pytest.raises(AssemblerError, match="circular include") as error:
        assemble(first.read_text(), str(first), str(tmp_path))

    assert "a.asm" in str(error.value)
    assert "b.asm" in str(error.value)


def test_errors_in_included_file_keep_that_files_line_and_name(tmp_path: Path) -> None:
    included = tmp_path / "included.asm"
    included.write_text("HALT\nLOAD R0\n")

    with pytest.raises(AssemblerError) as error:
        assemble('.include "included.asm"\n', str(tmp_path / "main.asm"), str(tmp_path))

    assert error.value.filename == str(included)
    assert error.value.line_no == 2


def test_error_after_include_keeps_including_files_line_and_name(tmp_path: Path) -> None:
    (tmp_path / "included.asm").write_text("HALT\n")
    main_path = tmp_path / "main.asm"

    with pytest.raises(AssemblerError) as error:
        assemble('.include "included.asm"\nUNKNOWN\n', str(main_path), str(tmp_path))

    assert error.value.filename == str(main_path)
    assert error.value.line_no == 2


def test_duplicate_definition_reports_second_files_location(tmp_path: Path) -> None:
    included = tmp_path / "included.asm"
    included.write_text("shared:\nHALT\n")
    main_path = tmp_path / "main.asm"

    with pytest.raises(AssemblerError) as error:
        assemble('.include "included.asm"\nshared:\nHALT\n', str(main_path), str(tmp_path))

    assert error.value.filename == str(main_path)
    assert error.value.line_no == 2


def test_assembler_errors_without_filename_keep_legacy_line_format() -> None:
    with pytest.raises(AssemblerError, match=r"^line 1:") as error:
        assemble("LOAD R0\n")
    assert error.value.filename is None


def test_assembler_cli_resolves_includes_and_writes_hex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    asm_dir = tmp_path / "asm"
    hex_dir = tmp_path / "hex"
    asm_dir.mkdir()
    hex_dir.mkdir()
    (asm_dir / "part.asm").write_text("LOAD R0, 5\n")
    (asm_dir / "demo.asm").write_text('.include "part.asm"\nHALT\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["assembler.py", "demo"])

    assembler_module.main()

    assert (hex_dir / "demo.hex").read_text() == "02 00 05\n01\n"


def test_assembler_cli_reports_included_file_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    asm_dir = tmp_path / "asm"
    hex_dir = tmp_path / "hex"
    asm_dir.mkdir()
    hex_dir.mkdir()
    (asm_dir / "bad.asm").write_text("HALT\nLOAD R0\n")
    (asm_dir / "demo.asm").write_text('.include "bad.asm"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["assembler.py", "demo"])

    with pytest.raises(SystemExit) as error:
        assembler_module.main()

    assert "asm/bad.asm: line 2" in str(error.value)
