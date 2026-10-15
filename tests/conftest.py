from bus import Bus
from cpu import CPU, RAM_END, RAM_START
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
    bus.register_device(0x0000, RAM_START, ROM(program))
    bus.register_device(RAM_START, RAM_END - RAM_START, RAM())
    recording_device = RecordingDevice()
    bus.register_device(RAM_END, RAM_END - RAM_START, recording_device)
    return CPU(bus), recording_device


def run_cpu(cpu: CPU, max_steps: int = 1000) -> CPU:
    for _ in range(max_steps):
        if cpu.halted:
            return cpu
        cpu.step()
    assert cpu.halted, f"program did not reach HALT within {max_steps} instructions"
    return cpu


def run_program(program: bytes) -> CPU:
    cpu, _ = build_machine(program)
    return run_cpu(cpu)
