#!/usr/bin/env bash
# Assemble asm/<name>.asm into hex/<name>.hex, then run it on the simulator.
# Usage: ./run.sh <program_name> [--trace] [--user] [--handle-faults]
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "usage: ./run.sh <program_name> [--trace] [--user] [--handle-faults] [--slow-mode]" >&2
    exit 2
fi

cd "$(dirname "$(readlink -f "$0")")"    # project root, even when called through a symlink

if [ -x .venv/bin/python ]; then
    PY=.venv/bin/python
else
    PY=python3
fi

name=$1
shift                   # what is left in "$@" are the flags for main.py

"$PY" assembler.py "$name"
"$PY" main.py "$name" "$@"