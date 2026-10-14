from abc import ABC, abstractmethod
from exceptions import ProgramDoesntFitOnRom, WriteToRomError
from tps import Byte, Address, Program, Word, KB

class Device(ABC):
    @abstractmethod
    def read(self, offset: Address) -> Byte:
        ...

    @abstractmethod
    def write(self, offset: Address, value: Byte) -> None:
        ...

class ROM(Device):
    def __init__(self, program: bytes, size_in_kb: int = 1) -> None:
        rom_size = size_in_kb * KB

        if len(program) > rom_size:
            raise ProgramDoesntFitOnRom(len(program), rom_size)

        self.memory = program + bytes(rom_size - len(program))

    def read(self, offset) -> Byte:
        return self.memory[offset]

    def write(self, offset, value) -> None:
        raise WriteToRomError


class RAM(Device):
    def __init__(self, size_in_kb: int = 1) -> None:
        self.memory = bytearray(size_in_kb * KB)

    def read(self, offset) -> Byte:
        return self.memory[offset]

    def write(self, offset, value) -> None:
        self.memory[offset] = value

class Terminal(Device):
    def __init__(self, tracing_mode: bool) -> None:
        self.TRACING_MODE = tracing_mode

    def read(self, offset):
        pass

    def write(self, offset, value):
        print(chr(value), end="")
        
        if self.TRACING_MODE:
            print("") # Print line break after each character in tracing mode
            # so that it doesnt mix with the tracing output of the CPU