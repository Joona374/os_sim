TERMINAL = 0x0800
SYS_PRINT_R1 = 1
SYS_EXIT = 2

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
    LOAD R2, 0
    PUSH R2
    RETI

main:
    STORE R0, 0x0000

syscall:
    PUSH R3                 ; hold on to value in stack
    
    LOAD R3, SYS_PRINT_R1
    CMP R0, R3
    JZ print_r1

    LOAD R3, SYS_EXIT
    CMP R0, R3
    JZ exit
    
    LOAD R0, 0xEE           ; this is an error code (that im too lazy to check for :D)
    JUMP trap_done

trap_done:
    POP R3                  ; lastly return r3
    RETI

print_r1:
    STORE R1, TERMINAL
    LOAD R0, 0
    JUMP trap_done

exit:
    LOAD R0, 0x45           ; print E just to show we exited
    STORE R0, TERMINAL
    HALT

priv_fault:
    LOAD R2, >priv_fault_string
    LOAD R3, <priv_fault_string 
    CALL print_string
    HALT

bus_fault:
    LOAD R2, >bus_fault_string
    LOAD R3, <bus_fault_string
    CALL print_string
    HALT

machine_fault:
    LOAD R2, >machine_fault_string
    LOAD R3, <machine_fault_string
    CALL print_string
    HALT

print_string:
print_loop:
    LDR R0, R2, R3
    LOAD R1, 0x00
    CMP R0, R1
    JZ exit_print

    STORE R0, TERMINAL    
    LOAD R1, 0x01
    ADD R3, R1
    JUMP print_loop

exit_print:
    RET


priv_fault_string:
    .string "PRIVILEGE FAULT"

bus_fault_string:
    .string "BUS FAULT"

machine_fault_string:
    .string "MACHINE FAULT"

