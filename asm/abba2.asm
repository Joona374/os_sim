.include "kernel.asm"

main_a:
    LOAD R1, 0x41
    LOAD R3, 0x010

main_a_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_a_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL

main_b:
    LOAD R1, 0x42
    LOAD R3, 0x07

main_b_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_b_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL


main_c:
    LOAD R1, 0x43
    LOAD R3, 0x04 

main_c_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_c_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL
