from abc import ABC, abstractmethod
from exceptions import ProgramDoesntFitOnRom, WriteToRomError
from tps import Byte, Address, KB

class Device(ABC):
    @abstractmethod
    def read(self, offset: Address) -> Byte: ...

    @abstractmethod
    def write(self, offset: Address, value: Byte) -> None: ...

    @abstractmethod
    def tick(self) -> None: ...


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

    def tick(self) -> None:
        pass


class RAM(Device):
    def __init__(self, size_in_kb: int = 1) -> None:
        self.memory = bytearray(size_in_kb * KB)

    def read(self, offset) -> Byte:
        return self.memory[offset]

    def write(self, offset, value) -> None:
        self.memory[offset] = value

    def tick(self) -> None:
        pass


class Terminal(Device):
    def __init__(self, tracing_mode: bool) -> None:
        self.TRACING_MODE = tracing_mode

    def read(self, offset):
        return 0x00  # Success message

    def write(self, offset, value):
        if offset == 0x00:  # Only the first device offset prints.
            print(chr(value), end="")

            if self.TRACING_MODE:
                print("")  # Print line break after each character in tracing mode
                # so that it doesnt mix with the tracing output of the CPU

    def tick(self) -> None:
        pass


class Keyboard(Device):
    QUEUE_EMPTY = 0x00
    READY_FOR_READ = 0x01
    DATA_REGISTER = 0x0000
    STATUS_REGISTER = 0x0001

    def __init__(self, test_buffer: bytearray | bytes | str | None = None, ticks_per_action: int = 1000) -> None:
        self.memory = bytearray(KB)
        self.buffer = self._init_buffer(test_buffer)
        # self._write_buffer_head_to_memory()

        self._ticks_per_keypress = ticks_per_action
        self._ticks_left_till_keypress = ticks_per_action

    def _init_buffer(self, test_buffer: bytearray | bytes | str | None):
        if isinstance(test_buffer, str):
            return bytearray(test_buffer.encode("ascii"))
        elif isinstance(test_buffer, (bytearray, bytes)):
            return bytearray(test_buffer)
        else:
            return bytearray()

    def _write_buffer_head_to_memory(self):
        if len(self.buffer) == 0:
            return

        first_byte = self.buffer[0]
        del self.buffer[0]

        self.memory[self.DATA_REGISTER] = first_byte
        self._update_status(self.READY_FOR_READ)

    def _update_status(self, status: Byte) -> None:
        self.memory[self.STATUS_REGISTER] = status

    def read(self, offset: Address) -> Byte:
        if offset == self.DATA_REGISTER:
            value = self.memory[offset]
            self.memory[offset] = 0x00  # clear after read not to hold phantom data
            self._update_status(self.QUEUE_EMPTY)
            return value

        elif offset == self.STATUS_REGISTER:
            return self.memory[offset]

        else:
            return 0x00

    def write(self, offset: Address, value: Byte) -> None:
        return

    def tick(self) -> None:
        if self._ticks_left_till_keypress > 0:
            self._ticks_left_till_keypress -= 1

        if self._ticks_left_till_keypress == 0 and self.memory[self.STATUS_REGISTER] == self.QUEUE_EMPTY:
            self._write_buffer_head_to_memory()
            self._ticks_left_till_keypress = self._ticks_per_keypress
