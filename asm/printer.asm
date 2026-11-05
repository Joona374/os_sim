.include "kernel.asm"

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