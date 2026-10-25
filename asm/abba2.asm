.include "kernel.asm"

main_a:
    LOAD R2, 0x02           ; A prints "A" twice, then exits
    LOAD R1, 0x41
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
    LOAD R1, 0x42           ; "B"
    LOAD R2, 0x02           ; phase 1: two prints, yielding directly (stack depth 0)
b_direct_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL
    LOAD R0, SYS_YIELD
    SYSCALL
    SUBI R2, 0x01
    JNZ b_direct_loop

    LOAD R2, 0x03           ; phase 2: three prints, yielding from inside a CALL (depth 2)
b_sub_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL
    CALL b_yielder
    CMPI R0, 0x00           ; self-check: a yield must return SUCCESS_CODE (0)
    JZ b_result_ok
    LOAD R1, 0x21           ; otherwise print "!" ...
    LOAD R0, SYS_PRINT_R1
    SYSCALL
    LOAD R1, 0x42           ; ... and restore "B"
b_result_ok:
    SUBI R2, 0x01
    JNZ b_sub_loop
    LOAD R0, SYS_EXIT
    SYSCALL

b_yielder:
    LOAD R0, SYS_YIELD
    SYSCALL
    RET