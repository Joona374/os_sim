TERMINAL = 0xF000

CURRENT_PROCESS = 0x1000    ; PID = 0x10 or 0x14 or 0x18 etc. Stores the LOW Byte of the adress where the record is on the process map
N_OF_PROCS = 0x1001
TABLE_END = 0x1002          ; Low byte of address to the state byte of the first unused process

FIRST_PROC_LO_BYTE = 0x10
PROC_TABLE_HI_BYTE = 0x10
PROCESS_LIMIT = 0x48

PROC_START_FLAGS = 0x01     ; 01 Zero cleared, User mode bit
STATE_ALIVE = 0x01
STATE_DEAD = 0x00

SYS_PRINT_R1 = 1
SYS_EXIT = 2
SYS_PRINT_STRING = 3
SYS_READ_CHAR = 4
SYS_YIELD = 5
SYS_KEY_READY = 6
SYS_SPAWN = 7

INVALID_SYSCALL_ERROR = 0xEE

BOOT_RET_HI_SP_ADDR = 0x1200
BOOT_RET_LO_SP_ADDR = 0x1201
CURRENT_PROC_TABLE_ADDR_LO = 0x1202

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
    LOAD R1, 0x10
    STORE R1, TABLE_END ; We want to store the address for the first unusued / un-inited process in the proc table

    LOAD R2, >init
    LOAD R3, <init
    LOAD R0, SYS_SPAWN
    SYSCALL
        
    LOAD R1, 0x10               ; Start with the first process (First entry in process )
    STORE R1, CURRENT_PROCESS  
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

    CMPI R0, SYS_SPAWN
    JZ setup_proc
    
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
    LOAD R0, 0x45           ; print E just to show we exited
    STORE R0, TERMINAL

    LOAD R1, STATE_DEAD
    LOAD R2, PROC_TABLE_HI_BYTE
    LDA R3, CURRENT_PROCESS
    STR R1, R2, R3

    JUMP save_context_for_process

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

save_context_for_process:
    ; 0. We would have needed to enter a trap similar to syscall so that PC LO, PC HI and Flags are already writen to stack, an SP moved to point to this. (Open question is if R1-R3 should also be pushed here?)
    ; 1. Load CURRENT_PROCESS to register (value = eg. 0x10, 0x14, low byte of address for the entry in process table)
    LOAD R0, PROC_TABLE_HI_BYTE
    LDA R1, CURRENT_PROCESS

    ; 2. GET SP into registers
    GETSP R2, R3

    ; 3. Write SP HI into process table entry add + 1
    ADDI R1, 0x01
    STR R2, R0, R1

    ; 5. Write SP LO into process table entry add + 2. These can later be used to return to this process.
    ADDI R1, 0x01
    STR R3, R0, R1

    ; TODO: Figure out how to find the next process, increment CURRENT_PROCESS, and then call / jump to resume_process.
    CALL find_and_set_next_process
    JUMP resume_process

    

find_and_set_next_process:
    ; 1. Load current process (0x10, 0x14, 0x18...)
    LDA R0, CURRENT_PROCESS
    LOAD R2, PROC_TABLE_HI_BYTE       ; We need this just so that we can do LDR PROC_TABLE_HI_BYTE + CURRENT_PROCESS to check process state

    ; 2. Load max address  
    LDA R1, TABLE_END

    ; 3. Copy the starting process pid, so we know when we have checked every process and should quit
    MOV R3, R0

find_and_set_next_process_loop:
    PUSH R3

    ; 3. Increment current process += 4
    ADDI R0, 0x04

    ; 4. Compare current process and max address, if equal, jump to loopback 
    CMP R0, R1
    JZ find_and_set_next_process_loopback

    ; 5. Get process state (PROC_TABLE_HI_BYTE + CURRENT_PROCESS)
    LDR R3, R2, R0

    ; 6. If state is NOT STATE_ALIVE jump back to top of loop
    CMPI R3, STATE_ALIVE
    POP R3
    JZ find_and_set_next_process_loop_ret

    ; 7. Check if we have checked every process and none was ALIVE
    CMP R0, R3
    JNZ find_and_set_next_process_loop
    
    ; 8. Entering here means we just checked the original process and it wasnt alive either, so there is no more alive processes and we should halt the whole machine / cpu
    HALT

find_and_set_next_process_loopback:
    POP R3
    LOAD R0, FIRST_PROC_LO_BYTE         ; Load the 0x10 which first processes state
    SUBI R0, 0x04                       ; Then imemdiately subtract 4 because we will add 4 again at the start of next loop
    JUMP find_and_set_next_process_loop

find_and_set_next_process_loop_ret:
    ; 7. If state is alive, return from this "function"
    STORE R0, CURRENT_PROCESS 
    RET

resume_process:
    ; 1. Find the address that stores the stack frame (that we get by yielding)
    LOAD R0, PROC_TABLE_HI_BYTE
    LDA R1, CURRENT_PROCESS

    ; 2. Load SP HI to a register
    ADDI R1, 0x01
    LDR R2, R0, R1

    ; 3. Load SP LO to a register
    ADDI R1, 0x01
    LDR R3, R0, R1

    ; 6. SET SP, this now points to the stack frame for CURRENT_PROCESS
    SETSP R2, R3

    ; 7. LOAD R0, SUCCESS_CODE (OPTIONAL)
    LOAD R0, SUCCESS_CODE

    ; 8. Call trap_done to recover R1-R3, flags and finally CP to next instruction for CURRENT_PROCESS
    JUMP trap_done

check_key_ready:
    LDA R0, KEYBOARD_FLAGS
    JUMP trap_done

yield:                      ; SYS_YIELD
    JUMP save_context_for_process


; SETUP PROC (R2 and R3 store the address of the program in memory, eg R2 >main, R3 <main)
setup_proc:
    GETSP R0, R1                ; We need to store the SP to return back to since during this call we will use SETSP that messes up CALL -> RET stack
    STORE R0, BOOT_RET_HI_SP_ADDR
    STORE R1, BOOT_RET_LO_SP_ADDR

    PUSH R2                     ; R2-R3 (Hi-Lo) contains the starting address of a process
    PUSH R3                     ; PUsh to store them while we need the registers for work

    JUMP find_first_empty_process_slot  

find_first_empty_process_slot:
    LOAD R0, PROC_TABLE_HI_BYTE
    LOAD R1, FIRST_PROC_LO_BYTE
    LDA R2, TABLE_END

find_first_empty_process_slot_loop:
    CMP R1, R2
    JZ start_table_entry

    LDR R3, R0, R1              ; Load the status of process at R0+R1 = 0x1010 etc
    
    CMPI R3, STATE_ALIVE
    JNZ start_table_entry       ; if a process in this slot is NOT alive, start new entry here

    ADDI R1, 0x04
    CMPI R1, PROCESS_LIMIT      ; 0x48 = 68 = 0x10 + 13 * 4 + 4 = First process address plus 13 more 4 bit entries + one more slot to the first invalid process
    JZ raise_for_too_many_processes

    JUMP find_first_empty_process_slot_loop

raise_for_too_many_processes:    
    LOAD R1, >too_many_processes
    LOAD R2, <too_many_processes
    CALL print_string

    POP R3                      ; Pop leftovers from setup_proc to balance stack
    POP R2

    LOAD R0, ERROR_CODE
    JUMP trap_done

start_table_entry:              ; R1 holds the low byte for first address of this proc entry in the table
    STORE R1, CURRENT_PROC_TABLE_ADDR_LO    ; Hold on to the low byte of address where this process' entry is stored in the process table
    
    LOAD R2, STATE_ALIVE
    STR R2, R0, R1              ; Write alive to first bit of entry

    ADDI R1, 0x08               ; R1 now holds the end of stack for process in table 0x10 (0x1400-0x17FF) (starting SP) HI byte 0x18
    LOAD R3, 0x00               ; R1 + R3 = SP like 0x1800 = End of first process stack

    ; 4th byte for procc is unused for now

build_stack_frame:
    MOV R0, R1                  ; Move the SP to other registers to make way for POP
    MOV R1, R3

    POP R3                      ; Program start LO byte
    POP R2                      ; Program start HI byte

    SETSP R0, R1                ; Only set SP after POP so we dont loose the address for start of proc

    PUSH R3                     ; Load stack frame for program, PC LO
    PUSH R2                     ; PC HI
    LOAD R2, PROC_START_FLAGS
    PUSH R2                     ; 01 bit flags Zero, Mode

    LOAD R3, 0x00               ; Pre set R1-R3 values
    PUSH R3
    PUSH R3
    PUSH R3

update_the_process_table:
    GETSP R0, R1                ; SP High byte for 0th process is now 0x17, LO is 0xFA = 250
    
    LOAD R2, PROC_TABLE_HI_BYTE ; 0x10
    LDA R3, CURRENT_PROC_TABLE_ADDR_LO ; This now points to this entry in the table

    ADDI R3, 0x01               ; Table entry for 0th process SP hi byte is 0x11
    STR R0, R2, R3              ; Store the SP Hi 0x13 at 0x1011

    ADDI R3, 0x01               ; Table entry for 0th process SP low byte is 0x12
    STR R1, R2, R3              ; Store the SP Lo 0xFA at 0x1012

    LDA R0, BOOT_RET_HI_SP_ADDR
    LDA R1, BOOT_RET_LO_SP_ADDR
    SETSP R0, R1

    LDA R3, CURRENT_PROC_TABLE_ADDR_LO
    LDA R0, TABLE_END
    CMP R0, R3
    JZ increment_table_end

    JUMP return_from_setup_proc

increment_table_end:
    LDA R3, TABLE_END
    ADDI R3, 0x04
    STORE R3,TABLE_END
    JUMP return_from_setup_proc

return_from_setup_proc:
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

; Utils
r0_times_r1:                    ; This will mess R2, so push that first if needed
    CMPI R0, 0x00               ; If either r0 or r1 == 0, return early as N x 0 = 0
    JZ r0_times_r1_ret_zero
    CMPI R1, 0x00
    JZ r0_times_r1_ret_zero

    MOV R2, R0                  ; We keep adding R2 to R0 r1 times
    LOAD R0, 0x00

r0_times_r1_loop:
    CMPI R1, 0x00
    JZ r0_times_r1_ret

    ADD R0, R2
    SUBI R1, 0x01
    JUMP r0_times_r1_loop

r0_times_r1_ret_zero:
    LOAD R0, 0x00
    RET

r0_times_r1_ret:
    RET

; KERNEL ROM STRINGS

priv_fault_string:
    .string "PRIVILEGE FAULT"

bus_fault_string:
    .string "BUS FAULT"

machine_fault_string:
    .string "MACHINE FAULT"

test_string:
    .string "TEST STRING!\n"

too_many_processes:
    .string "SOS"

; too_many_processes:
;    .string "ERROR: Unable to spawn a new process, max number of processes already reached\n"