from bus import Bus
from cpu import CPU
from device import RAM, ROM


class RecordingDevice:
    def __init__(self) -> None:
        self.memory: dict[int, int] = {}
        self.writes: list[tuple[int, int]] = []

    def read(self, offset: int) -> int:
        return self.memory.get(offset, 0)

    def write(self, offset: int, value: int) -> None:
        self.writes.append((offset, value))
        self.memory[offset] = value


def build_machine(program: bytes) -> tuple[CPU, RecordingDevice]:
    bus = Bus()
    bus.register_device(0x0000, 0x0400, ROM(program))
    bus.register_device(0x0400, 0x0400, RAM())
    recording_device = RecordingDevice()
    bus.register_device(0x0800, 0x0400, recording_device)
    return CPU(bus), recording_device


def run_program(program: bytes) -> CPU:
    cpu, _ = build_machine(program)
    for _ in range(1000):
        if cpu.halted:
            return cpu
        cpu.step()
    assert cpu.halted, "program did not reach HALT within 1000 instructions"
    return cpu