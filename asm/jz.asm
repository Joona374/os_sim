LOAD R0, 0x05
LOAD R1, 0x01
loop:
    LOAD R2, 0x30
    ADD R2, R0
    SUB R0, R1
    STORE R2, 0x0800     ; terminal
    JZ end
    JUMP loop
end:
    HALT