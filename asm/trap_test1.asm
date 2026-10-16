JUMP boot
JUMP trap_entry

boot:
    LOAD R0, 1
    LOAD R1, >user_program
    LOAD R2, <user_program
    
    PUSH R2
    PUSH R1
    PUSH R0

    RETI

trap_entry:
    STORE R3, 0x0800
    RETI

user_program:
    LOAD R3, 0x44
    STORE R1, 0x0500
    SYSCALL
    HALT