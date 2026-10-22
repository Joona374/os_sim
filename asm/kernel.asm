TERMINAL = 0x0800
SYS_PRINT_R1 = 1
SYS_EXIT = 2
SYS_PRINT_STRING = 3
SYS_READ_CHAR = 4

INVALID_SYSCALL_ERROR = 0xEE

JUMP boot
JUMP syscall
JUMP priv_fault
JUMP bus_fault
JUMP machine_fault

boot:
    LOAD R0, <main
    PUSH R0
    LOAD R1, >main
    PUSH R1
    LOAD R2, 1
    PUSH R2
    RETI

main:
    <TODO>

syscall:
    PUSH R1
    PUSH R2
    PUSH R3
    
    CMPI R0, SYS_PRINT_R1
    JZ print_r1

    CMPI R0, SYS_EXIT
    JZ exit

    CMPI R0, SYS_PRINT_STRING
    JZ sys_print_string

    CMPI R0, SYS_READ_CHAR
    JZ poll_char
    
    LOAD R0, INVALID_SYSCALL_ERROR      ; this is an error code (that im too lazy to check for :D)
    JUMP trap_done

trap_done:
    POP R3
    POP R2
    POP R1
    RETI

print_r1:
    STORE R1, TERMINAL
    LOAD R0, 0
    JUMP trap_done

sys_print_string:
    CALL print_string
    LOAD R0, 0
    JUMP trap_done

priv_fault:
    LOAD R1, >priv_fault_string
    LOAD R2, <priv_fault_string 
    CALL print_string
    HALT

bus_fault:
    LOAD R1, >bus_fault_string
    LOAD R2, <bus_fault_string
    CALL print_string
    HALT

machine_fault:
    LOAD R1, >machine_fault_string
    LOAD R2, <machine_fault_string
    CALL print_string
    HALT

print_string:
    LDR R0, R1, R2
    CMPI R0, 0x00
    JZ exit_print

    STORE R0, TERMINAL    
    ADDI R2, 0x01

    JNZ print_string

    ADDI R1, 0x01
    JUMP print_string

exit_print:
    RET

poll_char:
    LOAD R1, 0x10
    LOAD R2, 0x01
    LDR R3, R1, R2

    CMPI R3, 0x00
    JZ poll_char

    LOAD R2, 0x00
    LDR R0, R1, R2
    JUMP trap_done

exit:
    LOAD R0, 0x45           ; print E just to show we exited
    STORE R0, TERMINAL
    HALT

priv_fault_string:
    .string "PRIVILEGE FAULT"

bus_fault_string:
    .string "BUS FAULT"

machine_fault_string:
    .string "MACHINE FAULT"
