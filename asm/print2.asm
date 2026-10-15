TERMINAL = 0x0800

main:
    LOAD R0, 0x58          ; 'X', a sentinel
    LOAD R1, 0x59          ; 'Y', a sentinel

    LOAD R2, >msg1
    LOAD R3, <msg1
    CALL print_string

    LOAD R2, >msg2         ; reload both: the routine advanced R3
    LOAD R3, <msg2
    CALL print_string

    STORE R0, TERMINAL     ; should still print X
    STORE R1, TERMINAL     ; should still print Y
    HALT

print_string:
    PUSH R0                ; save R0 and R1
    PUSH R1

print_loop:
    LDR R0, R2, R3         ; Load a char to R0

    LOAD R1, 0x00          ; 0 is used compate to null terminator
    CMP R0, R1             ; 0 set null flag if end of string

    JZ done

    STORE R0, TERMINAL     ; prints char

    LOAD R1, 0x01          ; 1 is used to increment char address
    ADD R3, R1             ; step char pointer 

    JUMP print_loop ; repeat for second letter

done:
    POP R1 ; restore R1 and R0 (reverse order)
    POP R0
    RET

msg1:
    .string "HELLO "
msg2:
    .string "WORLD\n"