"""Host-side tool: assembly source text -> machine code bytes."""

import re
import sys

from isa import LAYOUT, NUM_REGISTERS, OPERAND_SIZE, Opcode, Operand

# Address where the program will sit in the CPU's address space. Labels become
# absolute addresses, so this must match where the program is actually mapped.
ORIGIN = 0x0000


class AssemblerError(ValueError):
    """A mistake in the assembly source. A tool error, not a MachineFault."""

    def __init__(self, line_no: int, message: str) -> None:
        super().__init__(f"line {line_no}: {message}")


# Splits a line into tokens. Alternatives are tried in this order at each position.
TOKEN = re.compile(
    r"""
      '(?:\\.|[^'\\])'       # character literal: 'A' or '\n'
    | "(?:\\.|[^"\\])*"      # string literal: "HELLO WORLD\n"
    | ;.*                    # comment, runs to end of line
    | =                      # constant definition: NAME = value
    | [^\s,;'"=]+            # word: label, mnemonic, register, number, name, >label, <label
    | ,                      # operand separator
    | ['"]                   # stray quote (unterminated literal), kept so it gets reported
""",
    re.VERBOSE,
)

ESCAPES = {"\\n": 10, "\\t": 9, "\\0": 0, "\\\\": 92, "\\'": 39, '\\"': 34}


def parse_line(raw: str) -> tuple[str | None, str | None, list[str]]:
    """Returns (label, mnemonic, operand_texts). Any of them may be empty.

    A constant definition "NAME = value" comes back as mnemonic "=" with operands [NAME, value].
    """
    tokens = [t for t in TOKEN.findall(raw) if not t.startswith(";")]

    label = None
    if tokens and tokens[0].endswith(":"):
        label = tokens.pop(0)[:-1]

    if not tokens:
        return label, None, []

    if len(tokens) >= 2 and tokens[1] == "=":
        return label, "=", [tokens[0], *tokens[2:]]

    mnemonic = tokens[0].upper()
    operands = [t for t in tokens[1:] if t != ","]
    return label, mnemonic, operands


def define_symbol(symbols: dict[str, int], name: str, value: int, line_no: int) -> None:
    """Records a label or constant. They share one namespace."""
    if not name.isidentifier() or re.fullmatch(r"[rR]\d+", name):
        raise AssemblerError(line_no, f"bad name {name!r}")
    if name in symbols:
        raise AssemblerError(line_no, f"{name!r} defined twice")
    symbols[name] = value


def parse_value(text: str, symbols: dict[str, int], line_no: int) -> int:
    """A number (0x41, 65), a character ('A', '\\n'), a label or constant name,
    or >name / <name for the high / low byte of a 16-bit value."""
    if len(text) > 1 and text[0] in "<>":
        value = parse_value(text[1:], symbols, line_no)
        if not 0 <= value <= 0xFFFF:
            raise AssemblerError(line_no, f"{value} is not a valid 16-bit value for {text[0]}")
        return value >> 8 if text[0] == ">" else value & 0xFF
    if len(text) >= 3 and text[0] == "'" and text[-1] == "'":
        body = text[1:-1]
        if body in ESCAPES:
            return ESCAPES[body]
        if len(body) == 1:
            return ord(body)
        raise AssemblerError(line_no, f"bad character literal {text}")
    if text in symbols:
        return symbols[text]
    try:
        return int(text, 0)
    except ValueError:
        raise AssemblerError(line_no, f"{text!r} is not a number, character or known name") from None


def parse_string(operands: list[str], line_no: int) -> bytes:
    """The bytes of a "quoted string" operand, escapes resolved, WITHOUT a terminator."""
    if len(operands) != 1 or len(operands[0]) < 2 or operands[0][0] != '"' or operands[0][-1] != '"':
        raise AssemblerError(line_no, '.string takes exactly one "quoted string"')
    body = operands[0][1:-1]
    data = bytearray()
    i = 0
    while i < len(body):
        if body[i] == "\\":
            pair = body[i : i + 2]
            if pair not in ESCAPES:
                raise AssemblerError(line_no, f"unknown escape {pair!r}")
            data.append(ESCAPES[pair])
            i += 2
        else:
            if ord(body[i]) > 0xFF:
                raise AssemblerError(line_no, f"character {body[i]!r} does not fit in a byte")
            data.append(ord(body[i]))
            i += 1
    return bytes(data)


def encode_operand(kind: Operand, text: str, symbols: dict[str, int], line_no: int) -> bytes:
    if kind is Operand.REG:
        match = re.fullmatch(r"[rR](\d+)", text)
        if match is None or int(match.group(1)) >= NUM_REGISTERS:
            raise AssemblerError(line_no, f"{text!r} is not a register (r0..r{NUM_REGISTERS - 1})")
        return bytes([int(match.group(1))])

    value = parse_value(text, symbols, line_no)

    if kind is Operand.IMM8:
        if not 0 <= value <= 0xFF:
            raise AssemblerError(line_no, f"{value} does not fit in a byte")
        return bytes([value])

    if kind is Operand.ADDR16:
        if not 0 <= value <= 0xFFFF:
            raise AssemblerError(line_no, f"{value} is not a valid 16-bit address")
        return bytes([value >> 8, value & 0xFF])  # big-endian: must mirror CPU._fetch_word

    raise AssemblerError(line_no, f"internal error: unhandled operand kind {kind}")


def instruction_size(opcode: Opcode) -> int:
    return 1 + sum(OPERAND_SIZE[kind] for kind in LAYOUT[opcode])


def directive_size(name: str, operands: list[str], line_no: int) -> int:
    """How many bytes a directive emits. Needed in pass 1, before labels are all known."""
    if name == ".BYTE":
        if not operands:
            raise AssemblerError(line_no, ".byte needs at least one value")
        return len(operands)  # one byte per operand
    if name == ".STRING":
        return len(parse_string(operands, line_no)) + 1  # +1 for the zero terminator
    raise AssemblerError(line_no, f"unknown directive {name.lower()!r}")


def encode_directive(name: str, operands: list[str], symbols: dict[str, int], line_no: int) -> bytes:
    if name == ".BYTE":
        data = bytearray()
        for text in operands:
            data += encode_operand(Operand.IMM8, text, symbols, line_no)
        return bytes(data)
    if name == ".STRING":
        return parse_string(operands, line_no) + b"\x00"
    raise AssemblerError(line_no, f"unknown directive {name.lower()!r}")


def assemble(source: str) -> list[bytes]:
    """Returns one bytes object per instruction or data directive."""
    # ---- Pass 1: work out where every label lives and what every constant is ----
    symbols: dict[str, int] = {}  # labels and constants share one namespace
    items: list[tuple[int, Opcode | str, list[str]]] = []  # (line number, opcode or directive name, operand texts)
    address = ORIGIN

    for line_no, raw in enumerate(source.splitlines(), start=1):
        label, mnemonic, operands = parse_line(raw)

        if label is not None:
            define_symbol(symbols, label, address, line_no)

        if mnemonic is None:
            continue

        if mnemonic == "=":  # NAME = value: defines a name, emits no bytes
            if len(operands) != 2:
                raise AssemblerError(line_no, "a constant is written NAME = value")
            name, value_text = operands
            define_symbol(symbols, name, parse_value(value_text, symbols, line_no), line_no)
            continue

        if mnemonic.startswith("."):  # directive: emits data, takes up space
            items.append((line_no, mnemonic, operands))
            address += directive_size(mnemonic, operands, line_no)
            continue

        try:
            opcode = Opcode[mnemonic]
        except KeyError:
            raise AssemblerError(line_no, f"unknown instruction {mnemonic!r}") from None

        items.append((line_no, opcode, operands))
        address += instruction_size(opcode)

    # ---- Pass 2: encode, now that every name is known ----
    encoded: list[bytes] = []
    for line_no, what, operands in items:
        if isinstance(what, str):
            encoded.append(encode_directive(what, operands, symbols, line_no))
            continue

        opcode = what
        kinds = LAYOUT[opcode]
        if len(operands) != len(kinds):
            raise AssemblerError(line_no, f"{opcode.name} takes {len(kinds)} operand(s), got {len(operands)}")
        code = bytearray([opcode.value])
        for kind, text in zip(kinds, operands):
            code += encode_operand(kind, text, symbols, line_no)
        encoded.append(bytes(code))
    return encoded


def main() -> None:
    if len(sys.argv) == 2:
        src_path, out_path = f"asm/{sys.argv[1]}.asm", f"hex/{sys.argv[1]}.hex"
    elif len(sys.argv) == 3:
        src_path, out_path = f"asm/{sys.argv[1]}.asm", f"hex/{sys.argv[2]}.hex"
    else:  
        sys.exit("usage: python assembler.py <in_and_out_filename> OR python assembler.py <input> <output>")

    with open(src_path) as f:
        try:
            instructions = assemble(f.read())
        except AssemblerError as err:
            sys.exit(f"{src_path}: {err}")

    with open(out_path, "w") as f:
        for instruction in instructions:  # one instruction or data item per line, easy to eyeball
            f.write(" ".join(f"{b:02X}" for b in instruction) + "\n")


if __name__ == "__main__":
    main()
