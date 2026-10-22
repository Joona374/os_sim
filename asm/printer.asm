.include "kernel.asm"

main:
    LOAD R0, SYS_READ_CHAR
    SYSCALL
    MOV R1, R0
    LOAD R0, SYS_PRINT_R1
    SYSCALL
    CMPI R1, 0x0A
    JNZ main
    
    LOAD R0,SYS_EXIT
    SYSCALL
