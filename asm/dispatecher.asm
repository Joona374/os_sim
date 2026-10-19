TERMINAL = 0x800
SYS_PRINT_R1 = 1
SYS_EXIT = 2

JUMP boot
JUMP dispatcher

boot:
    LOAD R2, <main          ; low byte
    PUSH R2
    LOAD R1, >main          ; high byte
    PUSH R1
    LOAD R0, 1              ; USER MODE
    PUSH R0

    RETI


dispatcher:
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

main:
    LOAD R3, 0x69           ; lets try and hold on to this
    LOAD R1, 0x44           ; this is what we want to print
    LOAD R0, SYS_PRINT_R1   ; specify which syscall
    SYSCALL

    LOAD R3, 0x70           ; update just for the hell of it

    LOAD R0, SYS_EXIT       ; lets exit the program
    SYSCALL



print_r1:
    STORE R1, TERMINAL
    LOAD R0, 0
    JUMP trap_done
