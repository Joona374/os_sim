from enum import Enum
from webbrowser import Opera

NUM_REGISTERS = 4

class Opcode(Enum):
    # 0x00 is deliberately unassigned, so running into zeroed memory faults
    HALT = 0x01
    LOAD = 0x02
    STORE = 0x03
    JUMP = 0x04
    CMP = 0x05
    JZ = 0x06
    ADD = 0x07
    SUB = 0x08
    LDR = 0x09
    PUSH = 0x0A
    POP = 0x0B
    CALL = 0x0C
    RET = 0x0D

PRIVLIDGED_OPERATIONS = {Opcode.HALT}

class Operand(Enum):
    REG = "register"  # 1 byte: register number
    IMM8 = "imm8"  # 1 byte: constant
    ADDR16 = "addr16"  # 2 bytes: address, high byte first


# Which operands follow each opcode, in order.
LAYOUT: dict[Opcode, list[Operand]] = {
    Opcode.HALT: [],
    Opcode.LOAD: [Operand.REG, Operand.IMM8],  # Target Reg, Immediate Value
    Opcode.STORE: [Operand.REG, Operand.ADDR16],  # Source Reg, Target addr
    Opcode.JUMP: [Operand.ADDR16],  # PC to Addr
    Opcode.CMP: [Operand.REG, Operand.REG],  # REG_A - REG_B, if == 0 set zero_flag
    Opcode.JZ: [Operand.ADDR16],  # IF zero_flag jump to Addr
    Opcode.ADD: [Operand.REG, Operand.REG],  # REG_A += REG_B
    Opcode.SUB: [Operand.REG, Operand.REG],  # REG_A -= REG_B
    Opcode.LDR: [Operand.REG, Operand.REG, Operand.REG],  # Target Reg, HI_REG, LO_REG
    Opcode.PUSH: [Operand.REG],  # Source reg
    Opcode.POP: [Operand.REG],  # Target reg
    Opcode.CALL: [Operand.ADDR16],  # store current PC on to stack and jump to addr
    Opcode.RET: [],  # Jump back to address stored in to stack by CALL
}

OPERAND_SIZE: dict[Operand, int] = {
    Operand.REG: 1,
    Operand.IMM8: 1,
    Operand.ADDR16: 2,
}
