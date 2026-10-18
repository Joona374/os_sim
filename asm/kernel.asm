JUMP boot
JUMP syscall
JUMP priv_fault
JUMP bus_fault
JUMP machine_fault

boot:
    ...

syscall:
    ...

priv_fault:
    LOAD R2, >priv_fault_string
    LOAD R3, <priv_fault_string 
    CALL print_string

bus_fault:
    CALL print_string

machine_fault:
    CALL print_string

print_string:
    
    RET

priv_fault_string:
    .string "PRIVILLEGE FAULT"

bus_fault_string:
    .string "BUS FAULT"

machine_fault_string:
    .string "MACHINE FAULT"

