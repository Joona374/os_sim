from cpu import CPU
from device import RAM, Terminal, ROM
from bus import Bus
from tps import KB, CpuMode

class Machine():

    def __init__(self, image_path: str, trace_mode: bool = False, start_mode: CpuMode = CpuMode.KERNEL, handle_machine_faults: bool = False) -> None:
        self.bus = Bus()

        image = self.load_image(image_path)
        self.rom = ROM(image)
        self.bus.register_device(0 * KB, KB, self.rom)  # 0x0000 - 0x03FF

        self.ram = RAM()
        self.bus.register_device(1 * KB, KB, self.ram)  # 0x400 - 0x07FF

        self.terminal = Terminal(trace_mode)
        self.bus.register_device(2 * KB, KB, self.terminal)  # 0x800 (prints), nothing else used YET

        self.cpu = CPU(self.bus, trace_mode=trace_mode, start_mode=start_mode, handle_machine_faults=handle_machine_faults)

    def load_image(self, path: str) -> bytes:
        with open(path) as f:
            return bytes.fromhex(f.read())  # ignores spaces and newlines
