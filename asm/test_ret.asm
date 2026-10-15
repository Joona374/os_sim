LOAD  R0, 0x49
CALL print
HALT

print:
    LOAD  R1, 0x48
    STORE R0, 0x0800
    RET