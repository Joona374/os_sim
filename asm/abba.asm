.include "kernel.asm"

main_a:
    LOAD R2, 0x02       ; COunter 2 -> 0
    LOAD R1, 0x41       ; The char to print ("A")
main_a_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R2, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL

    CMPI R2, 0x00
    JNZ main_a_loop

    LOAD R0, SYS_EXIT
    SYSCALL



main_b:
    LOAD R2, 0x04       ; COunter 5 -> 0
    LOAD R1, 0x42       ; The char to print ("B")
main_b_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R2, 0x01
    
    CALL b_yielder_function

    CMPI R2, 0x00
    JNZ main_b_loop

    LOAD R0, SYS_EXIT
    SYSCALL

b_yielder_function:
    LOAD R0, SYS_YIELD
    SYSCALL

    RET