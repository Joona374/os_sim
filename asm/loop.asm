loop:
    LOAD  r0, 'A'
    STORE r0, 0x0800     ; terminal
    JUMP  loop