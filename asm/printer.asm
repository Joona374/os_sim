.include "kernel.asm"

init:
    LOAD R2, >main_b
    LOAD R3, <main_b
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_c
    LOAD R3, <main_c
    LOAD R0, SYS_SPAWN
    SYSCALL

    JUMP main_a

main_a:
    LOAD R0, SYS_READ_CHAR
    SYSCALL
    MOV R1, R0
    LOAD R0, SYS_PRINT_R1
    SYSCALL
    CMPI R1, '\n'
    JNZ main_a

    LOAD R1, 'P'
    LOAD R0, SYS_PRINT_R1
    SYSCALL
    LOAD R0, SYS_EXIT
    SYSCALL

main_b:
    LOAD R0, SYS_EXIT
    SYSCALL

main_c:
    LOAD R0, SYS_EXIT
    SYSCALL