TERMINAL_ADDR = 0x08

HELLO_PROGRAM = [
    0x02, 0x00, 0x48,                   # Write ord("H") to reg0 
    0x03, 0x00, TERMINAL_ADDR, 0x00,      # Write value from reg0 to TERMINAL_ADDR00 aka temrinal
    0x02, 0x00, 0x45,                   # Write ord("E") to reg0 
    0x03, 0x00, TERMINAL_ADDR, 0x00,      # Write value from reg0 to TERMINAL_ADDR00 aka temrinal
    0x02, 0x00, 0x4C,                   # Write ord("L") to reg0 
    0x03, 0x00, TERMINAL_ADDR, 0x00,      # Write value from reg0 to TERMINAL_ADDR00 aka temrinal
    0x02, 0x00, 0x4C,                   # Write ord("L") to reg0 
    0x03, 0x00, TERMINAL_ADDR, 0x00,      # Write value from reg0 to TERMINAL_ADDR00 aka temrinal
    0x02, 0x00, 0x4F,                   # Write ord("O") to reg0 
    0x03, 0x00, TERMINAL_ADDR, 0x00,      # Write value from reg0 to TERMINAL_ADDR00 aka temrinal
    0x02, 0x00, 0x0A,                   # Write ord("\n") to reg0 
    0x03, 0x00, TERMINAL_ADDR, 0x00,      # Write value from reg0 to 0x0800 aka temrinal
    0x01                                # Halt
]

TEST_JUMP = [
    0x02, 0x00, 0x42,
    0x03, 0x00, TERMINAL_ADDR, 0x00,
    0x04, 0x00, 0x00
]