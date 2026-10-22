import sys

from exceptions import DoubleFault
from machine import Machine
from tps import CpuMode

DEFAULT_PROGRAM = "hex/loop.hex"

def main():
    TRACKING_ENABLED = False
    START_MODE = CpuMode.KERNEL
    HANDLE_MACHINE_FAULTS = False

    if "--trace" in sys.argv:
        TRACKING_ENABLED = True
        sys.argv.remove("--trace")

    if "--user" in sys.argv:
        START_MODE = CpuMode.USER
        sys.argv.remove("--user")

    if "--handle-faults" in sys.argv:
        HANDLE_MACHINE_FAULTS = True
        sys.argv.remove("--handle-faults")

    if len(sys.argv) == 1:
        program_path = DEFAULT_PROGRAM
    elif len(sys.argv) == 2:
        program_path = f"hex/{sys.argv[1]}.hex"
    else:
        sys.exit("usage: python3 main.py <program_name>")

    machine = Machine(program_path, trace_mode=TRACKING_ENABLED, start_mode=START_MODE, handle_machine_faults=HANDLE_MACHINE_FAULTS, keyboard_buffer="TESTI\n")
    try:
        machine.cpu.run()
    except DoubleFault as fault:
        print(fault)
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    sys.exit(main())
