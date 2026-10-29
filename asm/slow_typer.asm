.include "kernel.asm"

main_a:
    LOAD R0, SYS_KEY_READY
    SYSCALL

    CMPI R0, 0x00
    JZ yield_a

    LOAD R0, SYS_READ_CHAR
    SYSCALL

    MOV R1,R0

    LOAD R0, SYS_PRINT_R1
    SYSCALL

    CMPI R1, 0x0A
    JNZ main_a
    
    LOAD R0, SYS_EXIT
    SYSCALL

yield_a:
    LOAD R0, SYS_YIELD
    SYSCALL
    JUMP main_a

main_b:
    LOAD R2, 0x23

loop_b:
    LOAD R1, 0x2E
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    LOAD R0, SYS_YIELD
    SYSCALL

    SUBI R2, 0x01
    CMPI R2, 0x00
    JNZ loop_b

    LOAD R0, SYS_EXIT
    SYSCALL