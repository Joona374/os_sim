from isa import Opcode
from tps import Address, Byte


class DoubleFault(Exception):
    pass

    def __init__(self, original_fault: Exception, seconday_fault: Exception, PC: Address) -> None:
        super().__init__(f"The machine double faulted. At: 0x{PC:04X} | Original: {original_fault} | secondary: {seconday_fault}")


class MachineFault(Exception):
    """Event inside the simulated machine; the CPU turns these into traps."""

class BusFault(MachineFault):
    pass


class PrivilegeViolation(MachineFault):
    pass


class PrivilegedOperationViolation(PrivilegeViolation):
    """Raised when trying to execute a priviledged operation in user mode"""

    def __init__(self, operation: Opcode) -> None:
        super().__init__(f"Tried to execute: {operation} in user mode")
        self.operation = operation


class PrivilegedMemoryAccessViolation(PrivilegeViolation):
    """Raised when trying to access priviledged memory in user mode"""

    def __init__(self, address: Address) -> None:
        super().__init__(f"Tried access address: 0x{address:04X} in user mode")
        self.address = address


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


class StackPointerOutsideRam(MachineFault):
    def __init__(self, sp: Address, ram_start: Address, ram_end: Address) -> None:
        super().__init__(f"Stack Pointer: 0x{sp:04X} is outside of RAM 0x{ram_start:04X}-0x{ram_end:04X}.")
        self.sp = sp
        self.ram_start = ram_start
        self.ram_end = ram_end


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
