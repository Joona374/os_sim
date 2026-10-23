from bus import Bus
from cpu import CPU
from device import RAM, ROM
from memmap import (
    RAM_SIZE,
    RAM_START,
    ROM_SIZE,
    ROM_START,
    TERMINAL_END,
    TERMINAL_START,
)
from tps import CpuMode, KB

CANONICAL_UNMAPPED_ADDRESS = 0x8000


class RecordingDevice:
    def __init__(self) -> None:
        self.memory: dict[int, int] = {}
        self.writes: list[tuple[int, int]] = []
        self.reads: int = 0

    def read(self, offset: int) -> int:
        self.reads += 1
        return self.memory.get(offset, 0)

    def write(self, offset: int, value: int) -> None:
        self.writes.append((offset, value))
        self.memory[offset] = value


def build_machine(
    program: bytes,
    start_mode: CpuMode = CpuMode.KERNEL,
    trace_mode: bool = False,
    handle_machine_faults: bool = False,
) -> tuple[CPU, RecordingDevice]:
    bus = Bus()
    bus.register_device(ROM_START, ROM_SIZE, ROM(program, ROM_SIZE // KB))
    bus.register_device(RAM_START, RAM_SIZE, RAM(RAM_SIZE // KB))
    recording_device = RecordingDevice()
    bus.register_device(TERMINAL_START, TERMINAL_END - TERMINAL_START, recording_device)
    return (
        CPU(
            bus,
            trace_mode=trace_mode,
            start_mode=start_mode,
            handle_machine_faults=handle_machine_faults,
        ),
        recording_device,
    )


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
