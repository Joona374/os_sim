from tps import Address, Byte


class MachineFault(Exception):
    """Event inside the simulated machine; the CPU may later turn these into traps."""


class BusFault(MachineFault):
    pass


class BusFaultUnmappedAddress(BusFault):
    """Raised when an access hits an address no device claims."""
    def __init__(self, address: Address) -> None:
        super().__init__(f"unmapped address: 0x{address:04X}")
        self.address = address


class WriteToRomError(BusFault):
    """Raised when trying to write to the ROM memory."""

    def __init__(self) -> None:
        super().__init__(f"You cant write to the ROM Memory")


class IllegalInstruction(MachineFault):
    """Raised when an illegal instruction is encountered."""

    def __init__(self, op_code: Byte) -> None:
        super().__init__(f"Opcode: 0X{op_code:02X} isnt recognized as part of the ISA")
        self.value = op_code


class InvalidCpuRegister(MachineFault):
    """Raised when an invalid CPU register is accessed."""

    def __init__(self, register: Byte) -> None:
        super().__init__(f"Register {register} isnt pointing to a valid cpu reqister")
        self.value = register


class InvalidByteValue(ValueError):
    """Raised when tryng to insert a byte value larger than expected."""
    def __init__(self, value: Byte) -> None:
        super().__init__(f"Too large value: 0x{value:04X}")
        self.value = value


class ProgramDoesntFitOnRom(ValueError):
    """Raised when the program is larger than the available ROM size."""

    def __init__(self, program_size: int, rom_size: int) -> None:
        super().__init__(f"Program size {program_size} bytes is larger than the ROM size {rom_size} bytes")
        self.program_size = program_size
        self.rom_size = rom_size
