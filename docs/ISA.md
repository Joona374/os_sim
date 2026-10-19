# CPU ISA and Assembly Reference

This describes the behavior implemented by the CPU and assembler. Programs are assembled at address `0x0000`; labels therefore resolve to addresses relative to the start of the image.

## 1. Machine Model

| Part | Behavior |
|---|---|
| Registers | `R0`–`R3`, each 8-bit and initially zero |
| `PC` | 16-bit program counter, starts at `0x0000` |
| `SP` | 16-bit stack pointer, starts at `0x0800` |
| Mode | Starts in kernel mode unless `start_mode` selects user mode. |
| Zero flag (`Z`) | Starts clear. `CMP`/`CMPI` set it for equal values; `ADD`/`ADDI`/`SUB` set it when the 8-bit result is zero. Trap frames save and restore it. |
| Word byte order | Big-endian: high byte first, then low byte |

Default address map:

| Addresses | Device | Behavior |
|---|---|---|
| `0x0000`–`0x03FF` | 1 KiB ROM | Program image, zero-padded; writes fault |
| `0x0400`–`0x07FF` | 1 KiB RAM | Read/write memory; stack is placed here |
| `0x0800`–`0x0BFF` | 1 KiB terminal device | Writes print a character; reads return `0x00` |
| Everything else | Unmapped | Access faults |

The stack grows down from `SP = 0x0800`. `PUSH` writes at `SP - 1`; `POP` reads at `SP` then advances it. Thus `0x0800` is a valid empty-stack boundary, not a RAM byte. Stack bytes occupy `0x0400`–`0x07FF`.

The CPU starts at `PC = 0x0000`. ROM begins with five three-byte absolute `JUMP` vectors; boot code begins at `0x000F`:

| Address | Purpose |
|---:|---|
| `0x0000` | Reset |
| `0x0003` | Syscall |
| `0x0006` | Privilege fault |
| `0x0009` | Bus fault |
| `0x000C` | Other machine fault |
| `0x000F` | Boot code begins after the vector slots |

`HALT` and `RETI` are privileged instructions; they fault in user mode. User-mode data accesses and instruction fetches at or above `0x0800` fault, while ROM and RAM below that address remain accessible. Kernel mode has no such address restriction.

## 2. Assembly Syntax

- One instruction, directive, or constant definition per line. A label may precede a statement (`loop: ADD R0, R1`) or appear alone. A semicolon starts a comment outside quoted literals.
- Mnemonics are case-insensitive (`load` is parsed as `LOAD`). Registers are case-insensitive (`r0` or `R0`). Labels and constants are case-sensitive.
- Operands may be comma-separated; commas are optional. Registers are `R0` through `R3`.
- Numeric values use Python's `int(text, 0)` forms: decimal (`42`), hexadecimal (`0x2A`), binary (`0b101010`), and octal (`0o52`), with signs/underscores as accepted by Python. A leading zero does not mean octal: `010` is invalid; write `0o10`.
- Character literals are one character in single quotes, such as `'A'`, or one supported escape: `\n`, `\t`, `\0`, `\\`, `\'`, `\"`. Values used as bytes must fit in `0..255`.
- String literals use double quotes and the same escapes. String characters must fit in one byte.
- Constants use `NAME = value`, emit no bytes, and share one global namespace with labels. A name can be defined only once. A constant definition can use an already-defined symbol (constant or label), but not a symbol defined later. Labels (including forward labels) can be used in instruction/directive operands because those are encoded in the second pass.
- `>value` selects the high byte and `<value` the low byte of a 16-bit value. They work with numbers, labels, and constants; the input must be in `0..65535`.
- `.byte value, ...` emits one byte per value and requires at least one value.
- `.string "text"` emits the string followed by a zero byte (`0x00`).

Directives place data directly in the image; the CPU does not skip it. Put data after a `HALT` or elsewhere execution cannot reach, or the CPU may interpret data as instructions.

## 3. Instruction Reference

Sizes include the opcode byte. `Z` is the only flag.

| Mnemonic | Opcode | Operands | Size | Flags affected | Privileged | Description |
|---|---:|---|---:|---|---|---|
| `HALT` | `01` | — | 1 | — | Yes | Stop execution. |
| `LOAD` | `02` | register, imm8 | 3 | — | No | Load an 8-bit constant into a register. |
| `STORE` | `03` | register, addr16 | 4 | — | No | Write a register byte to an absolute address. |
| `JUMP` | `04` | addr16 | 3 | — | No | Set `PC` to an absolute address. |
| `CMP` | `05` | register, register | 3 | `Z` | No | Set `Z` if the two register values are equal. |
| `JZ` | `06` | addr16 | 3 | — | No | Jump if `Z` is set. |
| `ADD` | `07` | register, register | 3 | `Z` | No | Add the second register into the first, modulo 256. |
| `SUB` | `08` | register, register | 3 | `Z` | No | Subtract the second register from the first, modulo 256. |
| `LDR` | `09` | target, high-address, low-address registers | 4 | — | No | Load a byte from the address formed by the two address registers. |
| `PUSH` | `0A` | register | 2 | — | No | Push one byte onto the descending stack. |
| `POP` | `0B` | register | 2 | — | No | Pop one byte into a register. |
| `CALL` | `0C` | addr16 | 3 | — | No | Push the return address, then jump. |
| `RET` | `0D` | — | 1 | — | No | Pop a return address into `PC`. |
| `SYSCALL` | `0E` | — | 1 | — | No | Syscall semantics are not specified in this reference yet. |
| `RETI` | `0F` | — | 1 | `Z` restored | Yes | Restore mode, `Z`, and `PC` from the three-byte trap frame. |
| `JNZ` | `10` | addr16 | 3 | — | No | Jump if `Z` is clear. |
| `CMPI` | `11` | register, imm8 | 3 | `Z` | No | Set `Z` if the register equals the immediate byte. |
| `ADDI` | `12` | register, imm8 | 3 | `Z` | No | Add the immediate byte modulo 256 and set `Z` if the result is zero. |

For `STORE`, `JUMP`, `JZ`, `JNZ`, and `CALL`, `addr16` is encoded high byte first. `LDR` forms its address as `(high_register << 8) | low_register`. `CALL` also saves the return address high byte at the new `SP`, then the low byte at `SP + 1`; `RET` reads them in that order.

Each example below was passed to the project assembler; the bytes shown are its output.

### `HALT`

Layout: `01`

Example: `HALT` → `01`

### `LOAD`

Layout: opcode, destination register, immediate byte.

Example: `LOAD R0, 0x2A` → `02 00 2A`

### `STORE`

Layout: opcode, source register, address high byte, address low byte.

Example: `STORE R1, 0x0400` → `03 01 04 00`

### `JUMP`

Layout: opcode, address high byte, address low byte.

Example: `JUMP 0x1234` → `04 12 34`

### `CMP`

Layout: opcode, first register, second register.

Example: `CMP R0, R1` → `05 00 01`

### `JZ`

Layout: opcode, address high byte, address low byte.

Example: `JZ 0x0010` → `06 00 10`

### `JNZ`

Layout: opcode, address high byte, address low byte.

Example: `JNZ 0x0010` → `10 00 10`

### `CMPI`

Layout: opcode, register, immediate byte.

Example: `CMPI R0, 0x2A` → `11 00 2A`

### `ADDI`

Layout: opcode, destination/source register, immediate byte.

Example: `ADDI R0, 1` → `12 00 01`

### `ADD`

Layout: opcode, destination/source register, second source register.

Example: `ADD R0, R1` → `07 00 01`

### `SUB`

Layout: opcode, destination/source register, subtrahend register.

Example: `SUB R0, R1` → `08 00 01`

### `LDR`

Layout: opcode, destination register, address-high register, address-low register.

Example: `LDR R0, R2, R3` → `09 00 02 03`

### `PUSH`

Layout: opcode, source register.

Example: `PUSH R0` → `0A 00`

### `POP`

Layout: opcode, destination register.

Example: `POP R1` → `0B 01`

### `CALL`

Layout: opcode, target address high byte, target address low byte.

Example: `CALL 0x1234` → `0C 12 34`

### `RET`

Layout: `0D`

Example: `RET` → `0D`

### `SYSCALL`

Layout: `0E`

Example: `SYSCALL` → `0E`

### `RETI`

Layout: `0F`

Example: `RETI` → `0F`

## 4. Faults and Traps

Guest-caused CPU faults are `MachineFault` exceptions. When trap handling is enabled, each fault class enters the corresponding ROM vector:

| Fault class and kinds | Trigger | Vector |
|---|---|---|
| `PrivilegeViolation`: `PrivilegedOperationViolation`, `PrivilegedMemoryAccessViolation` | Privileged operation in user mode, or user-mode fetch/read/write at or above `0x0800` | `0x0006` |
| `BusFault`: `WriteToRomError`, `BusFaultUnmappedAddress` | Write to ROM, or access to an unmapped address | `0x0009` |
| Other `MachineFault`: `IllegalInstruction`, `InvalidCpuRegister`, `StackPointerOutsideRam` | Illegal opcode (including `0x00`), invalid register, or stack operation/frame outside RAM bounds | `0x000C` |

Each trap uses the shared RAM stack. If the old stack pointer is `SP`, the new pointer is `SP - 3`; the frame is stored in increasing-address order:

```text
new SP       new SP + 1   new SP + 2
+------------+------------+------------+
| Flags      | PC high    | PC low     |
+------------+------------+------------+
```

In the flags byte, bit 0 stores the previous mode (`0` kernel, `1` user), bit 1 stores `Z`, and the remaining bits are unused. `RETI` restores mode, `Z`, and `PC` from this frame, then advances `SP` by three.

The saved `PC` depends on the trap kind. A machine-fault frame stores the address of the first byte of the faulting instruction, so resuming with `RETI` retries that instruction. A syscall frame stores the address of the next instruction, so returning continues after the trap instruction. For example, a user `JUMP 0x0800` succeeds; the following instruction fetch faults and records `0x0800`.

Instructions follow a “validate everything, then commit” rule: validate registers, permissions, addresses, and stack bounds and complete required reads before changing registers, flags, `SP`, memory, or mode. If an instruction raises a `MachineFault`, `PC` is restored to that instruction's first byte and its effects are not committed. With `handle_machine_faults=False` (the default), the fault propagates from `step()` or `run()`. With it enabled, the CPU saves the pre-fault mode and `Z`, enters kernel mode at the matching vector, and continues. Exceptions that are not `MachineFault` are simulator errors and propagate rather than becoming traps.

If creating the three-byte trap frame itself faults, the CPU raises `DoubleFault` and halts rather than trying to trap again. A frame ending exactly at the bottom of RAM is valid; one that cannot fit is a double fault. `DoubleFault` is not a `MachineFault`.

Assembler errors are **tool errors, not machine faults**. `AssemblerError` reports the source line for unknown mnemonics/directives, wrong operand counts, invalid names or registers, malformed literals/escapes, unknown names, duplicate definitions, and values outside the operand's byte/address range. The CLI reports these while assembling, before a program runs. A program image larger than ROM raises `ProgramDoesntFitOnRom` during machine setup; that is also not a CPU `MachineFault`.

Stack faults from `RETI` leave the frame, `SP`, mode, flags, and registers unchanged. The `step()` wrapper restores `PC` to the first byte of the faulting instruction.

## 5. Conventions (Not Enforced)

- The kernel's `print_string` routine takes a zero-terminated string pointer in `R1:R2` (`R1` high byte, `R2` low byte). It clobbers `R0`, advances `R1` and `R2`, and leaves `R3` untouched; when `R2` wraps to zero, it increments `R1`. This is a software convention, not an ISA rule.
- `asm/hello_rom.asm` uses a different convention: its pointer is in `R2:R3` (`R2` high byte, `R3` low byte), and its loop increments only `R3`. That sample loop does not handle strings crossing a 256-byte boundary.
- A routine must restore the stack to its entry position before `RET`. `RET` always consumes exactly two bytes; an unbalanced push/pop sequence makes it read the wrong return address.

## 6. Worked Examples

### Print a zero-terminated ROM string

This is the loop assembled from `asm/hello_rom.asm`. The pointer begins at the label `msg`; the loop reads and prints bytes until it reads the terminator. The final jump skips the inline string data.

```asm
TERMINAL = 0x0800

main:
    LOAD  R2, >msg
    LOAD  R3, <msg
loop:
    LDR   R0, R2, R3
    LOAD  R1, 0
    CMP   R0, R1
    JZ    end
    STORE R0, TERMINAL
    LOAD  R1, 1
    ADD   R3, R1
    JUMP  loop
end:
    HALT

msg:
    .string "HELLO!\n"
```

Assembler output by statement:

```text
02 02 00 | 02 03 21 | 09 00 02 03 | 02 01 00 | 05 00 01
06 00 20 | 03 00 08 00 | 02 01 01 | 07 03 01 | 04 00 06 | 01
48 45 4C 4C 4F 21 0A 00
```

The program prints `HELLO!` followed by a newline. `msg` is at `0x0021`. This increment changes only the low pointer byte, so this particular loop is suitable for a string that does not cross a 256-byte boundary.

### Walk a pointer across a 256-byte boundary

The kernel's pointer-walking loop uses `ADDI` on the low byte followed immediately by `JNZ`. When the low byte wraps, `ADDI` sets `Z`; `JNZ` then falls through to increment the high byte. No instruction may change `Z` between those two instructions.

```asm
TERMINAL = 0x0800
LOAD R1, >msg
LOAD R2, <msg
loop:
    LDR R0, R1, R2
    CMPI R0, 0
    JZ done
    STORE R0, TERMINAL
    ADDI R2, 1
    JNZ loop
    ADDI R1, 1
    JUMP loop
done:
    HALT
msg:
    .string "A"
```

Assembler output by statement:

```text
02 01 00 | 02 02 21 | 09 00 01 02 | 11 00 00 | 06 00 20
03 00 08 00 | 12 02 01 | 10 00 06 | 12 01 01 | 04 00 06 | 01
41 00
```

Here `msg` is at `0x0021`; the same loop continues correctly when the string crosses a page boundary.

### Call a subroutine twice

The same `emit` routine is called with two different values. Each call pushes the address after its `CALL`; `RET` restores it. The subroutine does not use extra stack space, and the stack returns to `0x0800` after each call.

```asm
TERMINAL = 0x0800
LOAD R0, 'A'
CALL emit
LOAD R0, 'B'
CALL emit
HALT

emit:
    STORE R0, TERMINAL
    RET
```

Assembler output by statement:

```text
02 00 41 | 0C 00 0D | 02 00 42 | 0C 00 0D | 01
03 00 08 00 | 0D
```

This prints `AB`; `emit` is at `0x000D`.

## 7. Limitations

- Arithmetic is 8-bit and wraps modulo 256. There is no carry, borrow, or signedness flag.
- The only flag is `Z`; conditional jumps are `JZ` and `JNZ`.
- `ADDI` and `CMPI` provide immediate forms; there is no `SUBI`. The low-byte wrap technique works only for increments of `+1`: `ADDI low, 1` must be followed immediately by `JNZ` so `Z` can signal the wrap. There is still no carry flag; other pointer increments need explicit handling in software.
- `LDR` uses two 8-bit registers for an address. Arithmetic on those registers does not carry between bytes.
- There are no indirect jumps/calls, stack-frame instructions, or general-purpose 16-bit registers.
- There is no automatic kernel/handler installation: the program image must provide its vector and any boot code needed to enter user mode.
- Trap frames use the same RAM stack as `PUSH`/`CALL`; nested traps consume another three bytes each.
- No instruction reads `SP`, so a handler cannot locate the saved `PC` relative to the current stack pointer using only the ISA. User stack overflow can prevent delivery of the resulting stack fault and cause a `DoubleFault`.
- `Terminal.read` returns `0x00`.

## 8. Adding an Instruction

Keep these pieces in sync:

1. Add the opcode value to `Opcode` in `isa.py`.
2. Add its ordered operands to `LAYOUT` (and sizes to `OPERAND_SIZE` only if introducing a new operand kind).
3. Implement the CPU handler in `cpu.py`.
4. Register the handler in `operation_to_handler`.
5. Add assembler/CPU tests, including encoding and behavior or fault cases.
6. Update this document's instruction table, layout, and assembled example.
