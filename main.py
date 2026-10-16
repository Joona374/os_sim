import sys

from machine import Machine
from tps import CpuMode

DEFAULT_PROGRAM = "hex/loop.hex"

def main():
    TRACKING_ENABLED = False
    START_MODE = CpuMode.KERNEL

    if "--trace" in sys.argv:
        TRACKING_ENABLED = True
        sys.argv.remove("--trace")

    if "--user" in sys.argv:
        START_MODE = CpuMode.USER
        sys.argv.remove("--user")

    if len(sys.argv) == 1:
        program_path = DEFAULT_PROGRAM
    elif len(sys.argv) == 2:
        program_path = f"hex/{sys.argv[1]}.hex"
    else:
        sys.exit("usage: python3 main.py <program_name>")

    machine = Machine(program_path, trace_mode=TRACKING_ENABLED, start_mode=START_MODE)
    machine.cpu.run()

if __name__ == "__main__":
    main()
