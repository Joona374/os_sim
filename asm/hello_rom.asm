TERMINAL = 0x0800

main:
    LOAD  R2, >msg
    LOAD  R3, <msg
loop:
    LDR   R0, R2, R3
    LOAD  R1, 0
    CMP   R0, R1
    JZ    end
    STORE R0, TERMINAL
    LOAD  R1, 1
    ADD   R3, R1
    JUMP  loop
end:
    HALT

msg:
    .string "HELLO!\n"