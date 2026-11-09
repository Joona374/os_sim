from enum import Enum

from machine import Machine

class Command(Enum):
    STEP = ""
    QUIT = "q"

class Debugger:
    def __init__(self, machine: Machine) -> None:
        self.machine = machine
        self.steps = 0

    def run(self):
        while not self.machine.cpu.halted:
            command = self.prompt()
            if command == Command.STEP:
                self.machine.cpu.step()
                self.steps += 1
            elif command == Command.QUIT:
                self.machine.cpu.halted = True
                print("--- SIMULATION STOPPED ---")
            else:
                pass

    def prompt(self) -> Command | None:
        try:
            choice = input(f"{self.steps:04d} > ").strip()
            return Command(choice)
        except:
            print("unknown command")
            return None
