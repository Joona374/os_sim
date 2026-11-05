# Kernel Reference

This document describes the kernel assembled from [`asm/kernel.asm`](../asm/kernel.asm). The ISA-level memory map and trap-frame format are in [ISA.md](ISA.md).

## Boot and Process Startup

The image starts with five three-byte jumps at the reset, syscall, privilege-fault, bus-fault, and machine-fault vectors. The reset vector enters `boot` at `0x000F`; the other vectors enter the syscall dispatcher or their fault-message handlers.

Boot initializes `TABLE_END`, then calls `setup_proc` for `main_a`, `main_b`, and `main_c`, passing each entry address in `R2:R3` (high byte first). It sets `CURRENT_PROCESS` to the first record and jumps to `resume_process`. Every process starts in user mode with a synthetic trap frame on its own stack. The frame contains the entry PC and user-mode flags, with initial saved values for `R1`–`R3`; the first dispatch uses the same `trap_done`/`RETI` path as a later syscall return. Initial `R0` is set to the success code, zero.

Any image including the kernel must define all three entry labels, even when a process body only exits immediately. Boot currently creates exactly these three processes; there is no dynamic process creation.

## Process Table and Stacks

The memory allocation comes from `memmap.py`:

| Range | Size | Use |
|---|---:|---|
| `0x1000`–`0x13FF` | 1 KiB | Kernel data |
| `0x1400`–`0x4BFF` | 14 KiB | Process-stack pool |
| `0x4C00`–`0x4FFF` | 1 KiB | Boot stack |

The CPU starts with `SP = 0x5000`, the empty-stack boundary at the top of the boot stack. `setup_proc` uses four-byte process-table records beginning at `0x1010`:

| Record offset | Meaning |
|---:|---|
| `+0` | State: `0x01` alive, `0x00` dead |
| `+1` | Saved `SP`, high byte |
| `+2` | Saved `SP`, low byte |
| `+3` | Spare, currently unused |

`CURRENT_PROCESS` at `0x1000` stores the low byte of the active record address (`0x10`, `0x14`, `0x18` for the three boot processes). `TABLE_END` at `0x1002` stores the low byte of the first unused record; after boot it is `0x1C`. The scheduler does not inspect records at or above this value.

For a record whose low address byte is `x`, setup derives its stack top as `(x + 8) << 8`. The three boot-process tops are therefore `0x1800`, `0x1C00`, and `0x2000`; each process receives a 1 KiB descending stack. The remaining process-stack pool is available to later records, but the current boot sequence does not create them.

Kernel data addresses defined in the assembly:

| Address | Name | Use |
|---:|---|---|
| `0x1000` | `CURRENT_PROCESS` | Active record's low address byte |
| `0x1001` | `N_OF_PROCS` | Defined but not currently used |
| `0x1002` | `TABLE_END` | Low byte of first unused record |
| `0x1010` onward | Process table | Four-byte records |
| `0x1200` | `BOOT_RET_HI_SP_ADDR` | Temporary saved boot `SP`, high byte |
| `0x1201` | `BOOT_RET_LO_SP_ADDR` | Temporary saved boot `SP`, low byte |
| `0x1202` | `BOOT_PROC_TABLE_ENTRY_ADDR` | Defined but not currently used |

The terminal is at `0xF000`; keyboard data and status are at `0xF400` and `0xF401`.

## Scheduling

`YIELD` saves the current kernel stack pointer into the active process record, scans records in table order after the current one, wraps to the first record at `TABLE_END`, and skips dead records. The selected process resumes from its saved stack through `trap_done` and `RETI`. A live process can select itself after a full scan, so yielding with no other live process resumes that same process. If a full scan finds no live process, the kernel executes privileged `HALT`.

`EXIT` prints its demo marker, marks the current record dead, then invokes `YIELD` to schedule another process or halt when none remain.

## System Calls

The syscall number is passed in `R0`. The dispatcher saves and restores `R1`–`R3`, and the trap return restores the caller's mode and zero flag. Thus the syscall result is in `R0`; `R1`–`R3` and `Z` are preserved. Device and memory effects are not rolled back.

| Number | Name | Inputs | Result in `R0` | Other effects / blocking |
|---:|---|---|---|---|
| `1` | `PRINT_R1` | Character in `R1` | `0x00` | Writes one character to the terminal. |
| `2` | `EXIT` | None | Does not return to the exiting process | Prints `E`, marks the process dead, and schedules another process. |
| `3` | `PRINT_STRING` | Pointer high byte in `R1`, low byte in `R2` | `0x00` | Prints bytes through the zero terminator. The pointer registers are preserved on return. |
| `4` | `READ_CHAR` | None | Consumed keyboard byte | Busy-polls keyboard status inside the kernel until a byte is ready; other processes do not run while this syscall is polling. Reading data consumes the byte. |
| `5` | `YIELD` | None | `0x00` when the process resumes | Saves context and runs the next live process in table order, or resumes the caller if it is the only live process. |
| `6` | `KEY_READY` | None | Keyboard status (`0` or `1`) | Checks status without consuming data. |
| Other | Unknown | Number in `R0` | `0xEE` | No terminal output. |

`PRINT_STRING` follows its pointer using kernel-mode reads. It increments the low byte and carries into the high byte when the low byte wraps. The pointer is expected to address a zero-terminated byte string.

## Known Limitations

- `setup_proc` has no capacity check. It derives stacks in 1 KiB steps and can eventually overlap the boot stack or exceed the process-stack pool.
- There is no `spawn` syscall or runtime process creation; boot hard-wires three entries.
- `EXIT` prints `E` as a demonstration marker.
- `READ_CHAR` busy-polls in the kernel, so the scheduler cannot run another process until a key arrives.
- User pointers passed to `PRINT_STRING` are followed with kernel privileges and are not validated. Invalid or unterminated pointers can read device memory, print unintended data, or fault the machine.
- The kernel has no process wait state; a process blocked in `READ_CHAR` remains the running process.
- `N_OF_PROCS` and `BOOT_PROC_TABLE_ENTRY_ADDR` are defined but unused by the current implementation.