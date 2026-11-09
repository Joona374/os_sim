# Kernel Reference

This document describes the kernel assembled from [`asm/kernel.asm`](../asm/kernel.asm). The CPU address map and trap-frame format are covered in [ISA.md](ISA.md).

## Boot and Process Startup

The image begins with five three-byte jumps for reset, syscall, privilege-fault, bus-fault, and machine-fault vectors. Reset enters `boot` at `0x000F`; the other vectors enter the syscall dispatcher or a fault-message handler.

Boot initializes `TABLE_END` to `0x10`, passes the address of `init` in `R2:R3` (high byte first), and invokes `SYS_SPAWN`. It then sets `CURRENT_PROCESS` to the first record at `0x10` and resumes that process. Every program that includes this kernel must define `init`; it need not define any other entry labels.

Each process starts in user mode with a synthetic trap frame on its own stack. The saved entry PC and user-mode flags are followed by zero values for `R1`–`R3`. The first dispatch uses the same restore path as a syscall return, which sets `R0` to the success value `0`. Thus all four registers begin at zero. The kernel assumes its initial spawn of `init` succeeds.

## Process Table and Stacks

The memory allocation is defined in `memmap.py`:

| Range | Size | Use |
|---|---:|---|
| `0x1000`–`0x13FF` | 1 KiB | Kernel data |
| `0x1400`–`0x4BFF` | 14 KiB | Process-stack pool |
| `0x4C00`–`0x4FFF` | 1 KiB | Boot stack |

Fourteen four-byte records fit in page `0x10`, beginning at `0x1010`. Their low address bytes are `0x10`, `0x14`, through `0x44`; `0x48` is the first byte after the table.

| Record offset | Meaning |
|---:|---|
| `+0` | State: `0x01` alive, `0x00` dead |
| `+1` | Saved `SP`, high byte |
| `+2` | Saved `SP`, low byte |
| `+3` | Spare, currently unused |

| Address | Name | Meaning |
|---:|---|---|
| `0x1000` | `CURRENT_PROCESS` | Low byte of the currently running record address |
| `0x1001` | `N_OF_PROCS` | Defined but unused |
| `0x1002` | `TABLE_END` | Low byte of the first never-used record |
| `0x1010` onward | Process table | Fourteen records maximum |
| `0x1200` | `BOOT_RET_HI_SP_ADDR` | Temporary saved stack-pointer high byte during spawn |
| `0x1201` | `BOOT_RET_LO_SP_ADDR` | Temporary saved stack-pointer low byte during spawn |
| `0x1202` | `CURRENT_PROC_TABLE_ADDR_LO` | Temporary record address during spawn |

For a record whose low address byte is `x`, the kernel derives that process's stack top as `((x + 0x08) << 8)`. This gives `0x1800` for the first process, `0x1C00` for the second, and so on, up to `0x4C00` for the fourteenth. Each process has a 1 KiB descending stack; the empty-stack top is the byte immediately after its stack region. The initial synthetic frame occupies six bytes below that top.

`TABLE_END` advances by four only when a never-used record is allocated. Spawning first scans records below `TABLE_END` and reuses the first dead record. If no dead record exists, it allocates the record at `TABLE_END`. The table holds at most fourteen records total, including `init`, even after a process exits. If every record is live and the table is full, spawn prints `SOS`, returns `R0 = 1`, and does not create a process.

## Scheduling and Exit

`YIELD` saves the current kernel stack pointer in the active record, then scans from the next record in table order up to (but not including) `TABLE_END`. It wraps to the first record and skips dead records. The selected process resumes from its saved stack through the shared register-restore and `RETI` path. If the caller is the only live process, a full scan selects it again. If no live process remains, the kernel executes privileged `HALT`.

`EXIT` prints the demo marker `E`, marks the current record dead, saves its context, and schedules the next live process. It does not return to the exiting process. `init` has no special status: its exit does not stop other live processes.

## System Calls

The syscall number is passed in `R0`. The dispatcher saves and restores `R1`–`R3`; returning calls replace `R0` with their result and restore the caller's mode and zero flag. Therefore, `R1`–`R3` and `Z` are preserved across returning syscalls. `EXIT` does not return.

| Number | Name | Inputs (besides number in `R0`) | Result in `R0` | Clobbers | Blocking and other effects |
|---:|---|---|---|---|---|
| `1` | `PRINT_R1` | Character in `R1` | `0x00` | `R0` | Writes one character to the terminal; does not wait. |
| `2` | `EXIT` | None | Does not return | No return to caller | Prints `E`, marks the current process dead, and schedules another process or halts. |
| `3` | `PRINT_STRING` | Pointer in `R1:R2` (high:low) | `0x00` | `R0` | Reads and prints bytes through the zero terminator using kernel privileges; does not wait. |
| `4` | `READ_CHAR` | None | Consumed keyboard byte | `R0` | Busy-polls keyboard status in the kernel until a byte is ready; other processes do not run while it polls. Reading data consumes the byte. |
| `5` | `YIELD` | None | `0x00` when the caller resumes | `R0` | Saves context and runs the next live process, or resumes the caller if it is alone. |
| `6` | `KEY_READY` | None | Keyboard status (`0` or `1`) | `R0` | Reads status without consuming data; does not wait. |
| `7` | `SPAWN` | Entry address in `R2:R3` (high:low) | `0x00` success, `0x01` failure | `R0` | Creates a user-mode process with zeroed `R0`–`R3`; does not wait. Failure prints `SOS`. No PID is returned. |

The implementation also returns `0xEE` in `R0` for an unknown syscall number and produces no output for that case. Syscalls do not otherwise change `R1`–`R3` or `Z` when they return.

## Known Limitations

- Spawn accepts a raw entry address without validation. Processes have no isolation from each other or kernel RAM.
- A failed spawn prints the placeholder string `SOS` and returns only an error code; it does not return a PID.
- `EXIT` prints `E` as a demonstration marker.
- `READ_CHAR` busy-polls in the kernel, so other processes do not run while a process waits for keyboard input.
- User pointers passed to `PRINT_STRING` are followed with kernel privileges and are not validated. Invalid or unterminated pointers may read device memory, print unintended data, or fault the machine.
- The kernel has no blocked/waiting process state. A process in `READ_CHAR` remains the running process until input arrives.
- `N_OF_PROCS` is defined but unused.