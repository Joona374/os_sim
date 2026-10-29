TERMINAL = 0xF000
KERNEL_DATA_END = 0x1400
STACK_A_END = 0x1800
STACK_B_END = 0x1C00
BOOT_STACK_END = 0x2000

CURRENT_PID = 0x1000
A_SP_HIGH = 0x1001
A_SP_LOW = 0x1002
A_STATE = 0x1003
B_SP_HIGH = 0x1004
B_SP_LOW = 0x1005
B_STATE = 0x1006

A_PROCESS_PID = 0x00
B_PROCESS_PID = 0x01

STATE_ALIVE = 0x01
STATE_DEAD = 0x00

SYS_PRINT_R1 = 1
SYS_EXIT = 2
SYS_PRINT_STRING = 3
SYS_READ_CHAR = 4
SYS_YIELD = 5
SYS_KEY_READY = 6

INVALID_SYSCALL_ERROR = 0xEE

KEYBOARD_BUFFER = 0xF400
KEYBOARD_FLAGS = 0xF401
NULL_CHAR = 0x00

SUCCESS_CODE = 0x00
ERROR_CODE = 0x01

JUMP boot
JUMP syscall
JUMP priv_fault
JUMP bus_fault
JUMP machine_fault

boot:
    ; B Process
    LOAD R0 >STACK_B_END    ; Set SP to b stack
    LOAD R1 <STACK_B_END
    SETSP R0, R1

    LOAD R2, <main_b        ; Load stack frame for main_b program
    PUSH R2
    LOAD R2, >main_b
    PUSH R2
    LOAD R2, 1
    PUSH R2

    LOAD R3, 0x00           ; Pre set R1-R3 values
    PUSH R3
    PUSH R3
    PUSH R3

    GETSP R0, R1
    STORE R0, B_SP_HIGH     ; Add process b to the process table
    STORE R1, B_SP_LOW
    LOAD R3, STATE_ALIVE    ; Alive
    STORE R3, B_STATE


    ; A Process
    LOAD R0 >STACK_A_END    ; Set SP to a stack
    LOAD R1 <STACK_A_END
    SETSP R0, R1

    LOAD R2, <main_a        ; Load stack frame for main_a program
    PUSH R2
    LOAD R2, >main_a
    PUSH R2
    LOAD R2, 1
    PUSH R2

    LOAD R3, 0x00           ; Pre set R1-R3 values
    PUSH R3
    PUSH R3
    PUSH R3

    GETSP R0, R1            ; Add process a to the process table
    STORE R0, A_SP_HIGH     
    STORE R1, A_SP_LOW
    LOAD R3, STATE_ALIVE    ; Alive
    STORE R3, A_STATE

    LOAD R3, A_PROCESS_PID  ; Make A active process
    STORE R3, CURRENT_PID   
    JUMP resume_process

syscall:
    PUSH R1
    PUSH R2
    PUSH R3
    
    CMPI R0, SYS_PRINT_R1
    JZ print_r1

    CMPI R0, SYS_EXIT
    JZ exit

    CMPI R0, SYS_PRINT_STRING
    JZ sys_print_string

    CMPI R0, SYS_READ_CHAR
    JZ poll_char

    CMPI R0, SYS_YIELD
    JZ yield

    CMPI R0, SYS_KEY_READY
    JZ check_key_ready
    
    LOAD R0, INVALID_SYSCALL_ERROR      ; this is an error code (that im too lazy to check for :D)
    JUMP trap_done

trap_done:
    POP R3
    POP R2
    POP R1
    RETI

print_r1:                   ; SYS_PRINT_R1
    STORE R1, TERMINAL
    LOAD R0, 0
    JUMP trap_done

exit:                       ; SYS_EXIT
    LDA R0, CURRENT_PID

    CMPI R0, A_PROCESS_PID
    JZ exit_a

    CMPI R0, B_PROCESS_PID
    JZ exit_b

    JUMP machine_fault

exit_a:
    LOAD R1, STATE_DEAD
    STORE R1, A_STATE

    LDA R1, B_STATE
    CMPI R1, STATE_ALIVE
    JZ switch_to_b

    LOAD R0, 0x45           ; print E just to show we exited
    STORE R0, TERMINAL
    HALT

exit_b:
    LOAD R1, STATE_DEAD
    STORE R1, B_STATE

    LDA R1, A_STATE
    CMPI R1, STATE_ALIVE
    JZ switch_to_a

    LOAD R0, 0x45           ; print E just to show we exited
    STORE R0, TERMINAL
    HALT

sys_print_string:           ; SYS_PRINT_STRING
    CALL print_string
    LOAD R0, 0
    JUMP trap_done

print_string:
    LDR R0, R1, R2
    CMPI R0, NULL_CHAR
    JZ exit_print

    STORE R0, TERMINAL    
    ADDI R2, 0x01

    JNZ print_string

    ADDI R1, 0x01
    JUMP print_string

exit_print:
    RET

poll_char:                  ; SYS_READ_CHAR
    LDA R3, KEYBOARD_FLAGS

    CMPI R3, NULL_CHAR
    JZ poll_char

    LDA R0, KEYBOARD_BUFFER
    JUMP trap_done

yield:                      ; SYS_YIELD
    LDA R1, CURRENT_PID     ; R1 holds the currently active PID

    GETSP R2, R3

    CMPI R1, A_PROCESS_PID
    JZ yield_from_a

    CMPI R1, B_PROCESS_PID
    JZ yield_from_b

    JUMP machine_fault

yield_from_a:
    LDA R1, B_STATE
    CMPI R1, STATE_DEAD
    JZ cancel_yield

    STORE R2, A_SP_HIGH
    STORE R3, A_SP_LOW

    JUMP switch_to_b

yield_from_b:
    LDA R1, A_STATE
    CMPI R1, STATE_DEAD
    JZ cancel_yield

    STORE R2, B_SP_HIGH
    STORE R3, B_SP_LOW

    JUMP switch_to_a

cancel_yield:
    LOAD R0, SUCCESS_CODE
    JUMP trap_done

switch_to_b:
    LOAD R1, B_PROCESS_PID
    STORE R1, CURRENT_PID
    JUMP resume_process

switch_to_a:
    LOAD R1, A_PROCESS_PID
    STORE R1, CURRENT_PID
    JUMP resume_process

resume_process:
    LDA R1, CURRENT_PID

    CMPI R1, A_PROCESS_PID
    JZ resume_a

    CMPI R1, B_PROCESS_PID
    JZ resume_b

    JUMP machine_fault

check_key_ready:
    LDA R0, KEYBOARD_FLAGS
    JUMP trap_done

resume_a:
    LDA R1, A_SP_HIGH
    LDA R2, A_SP_LOW
    SETSP R1, R2
    LOAD R0, SUCCESS_CODE
    JUMP trap_done

resume_b:
    LDA R1, B_SP_HIGH
    LDA R2, B_SP_LOW
    SETSP R1, R2
    LOAD R0, SUCCESS_CODE
    JUMP trap_done

; FAULT HANDLERS

priv_fault:
    LOAD R1, >priv_fault_string
    LOAD R2, <priv_fault_string 
    CALL print_string
    HALT

bus_fault:
    LOAD R1, >bus_fault_string
    LOAD R2, <bus_fault_string
    CALL print_string
    HALT

machine_fault:
    LOAD R1, >machine_fault_string
    LOAD R2, <machine_fault_string
    CALL print_string
    HALT

; KERNEL ROM STRINGS

priv_fault_string:
    .string "PRIVILEGE FAULT"

bus_fault_string:
    .string "BUS FAULT"

machine_fault_string:
    .string "MACHINE FAULT"
