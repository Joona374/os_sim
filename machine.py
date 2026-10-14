from cpu import CPU
from device import RAM, Terminal, ROM
from bus import Bus
from tps import KB

class Machine():
    def __init__(self, image_path: str, trace_mode: bool = False) -> None:
        self.bus = Bus()

        image = self.load_image(image_path)
        self.rom = ROM(image)
        self.bus.register_device(0*KB, KB, self.rom)

        self.ram = RAM()
        self.bus.register_device(1 * KB, KB, self.ram)

        self.terminal = Terminal(trace_mode)
        self.bus.register_device(2*KB, KB, self.terminal)

        self.cpu = CPU(self.bus, trace_mode=trace_mode)

    def load_image(self, path: str) -> bytes:
        with open(path) as f:
            return bytes.fromhex(f.read())  # ignores spaces and newlines
