from cpu import CPU
from device import RAM, Terminal, ROM, Keyboard
from bus import Bus
from tps import KB, CpuMode
from memmap import KEYBOARD_END, KEYBOARD_START, RAM_SIZE, RAM_START, ROM_SIZE, ROM_START, TERMINAL_START

class Machine:

    def __init__(
        self,
        image_path: str,
        trace_mode: bool = False,
        start_mode: CpuMode = CpuMode.KERNEL,
        handle_machine_faults: bool = False,
        keyboard_buffer: bytearray | bytes | str | None = None,
        slow_mode: bool = False,
    ) -> None:
        self.bus = Bus()

        image = self.load_image(image_path)
        self.rom = ROM(image, ROM_SIZE // KB)
        self.bus.register_device(ROM_START, ROM_SIZE, self.rom)  # 0x0000-0x0FFF

        self.ram = RAM(RAM_SIZE // KB)
        self.bus.register_device(RAM_START, RAM_SIZE, self.ram)  # 0x1000-0x1FFF

        self.terminal = Terminal(trace_mode)
        self.bus.register_device(TERMINAL_START, KB, self.terminal)  # 0xF000-0xF3FF

        self.keyboard = Keyboard(keyboard_buffer)
        self.bus.register_device(KEYBOARD_START, KB, self.keyboard)  # 0xF400-0xF7FF

        self.cpu = CPU(self, self.bus, trace_mode=trace_mode, start_mode=start_mode, handle_machine_faults=handle_machine_faults, slow_mode=slow_mode)

    def load_image(self, path: str) -> bytes:
        with open(path) as f:
            return bytes.fromhex(f.read())  # ignores spaces and newlines
