.include "kernel.asm"

init:
    LOAD R2, >main_a
    LOAD R3, <main_a
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_b
    LOAD R3, <main_b
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_c
    LOAD R3, <main_c
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_d
    LOAD R3, <main_d
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_e
    LOAD R3, <main_e
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_f
    LOAD R3, <main_f
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_g
    LOAD R3, <main_g
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_h
    LOAD R3, <main_h
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_i
    LOAD R3, <main_i
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_j
    LOAD R3, <main_j
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_k
    LOAD R3, <main_k
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_l
    LOAD R3, <main_l
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_m
    LOAD R3, <main_m
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_n
    LOAD R3, <main_n
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_o
    LOAD R3, <main_o
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R2, >main_p
    LOAD R3, <main_p
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R0, SYS_EXIT
    SYSCALL


main_a:
    LOAD R1, 0x41
    LOAD R3, 0x010

main_a_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_a_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL

main_b:
    LOAD R1, 0x42
    LOAD R3, 0x07

main_b_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_b_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL


main_c:
    LOAD R1, 0x43
    LOAD R3, 0x04 

main_c_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_c_loop
    
    LOAD R2, >main_n
    LOAD R3, <main_n
    LOAD R0, SYS_SPAWN
    SYSCALL

    LOAD R0, SYS_EXIT
    SYSCALL

main_d:
    LOAD R1, 0x44
    LOAD R3, 0x04 

main_d_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_d_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL

main_e:
    LOAD R1, 0x45
    LOAD R3, 0x04 

main_e_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_e_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL

main_f:
    LOAD R1, 0x46
    LOAD R3, 0x04 

main_f_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_f_loop

    LOAD R2, >main_o
    LOAD R3, <main_o
    LOAD R0, SYS_SPAWN
    SYSCALL
    
    LOAD R0, SYS_EXIT
    SYSCALL

main_g:
    LOAD R1, 0x47
    LOAD R3, 0x04 

main_g_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_g_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL

main_h:
    LOAD R1, 0x48
    LOAD R3, 0x04 

main_h_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_h_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL

main_i:
    LOAD R1, 0x49
    LOAD R3, 0x04 

main_i_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_i_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL

main_j:
    LOAD R1, 0x4A
    LOAD R3, 0x04 

main_j_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_j_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL

main_k:
    LOAD R1, 0x4B
    LOAD R3, 0x04 

main_k_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_k_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL

main_l:
    LOAD R1, 0x4C
    LOAD R3, 0x04 

main_l_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_l_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL

main_m:
    LOAD R1, 0x4D
    LOAD R3, 0x04 

main_m_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_m_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL

main_n:
    LOAD R1, 0x4E
    LOAD R3, 0x04 

main_n_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_n_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL

main_o:
    LOAD R1, 0x4F
    LOAD R3, 0x04 

main_o_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_o_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL

main_p:
    LOAD R1, 0x50   
    LOAD R3, 0x04 

main_p_loop:
    LOAD R0, SYS_PRINT_R1
    SYSCALL

    SUBI R3, 0x01
    
    LOAD R0, SYS_YIELD
    SYSCALL
    
    CMPI R3, 0x00
    JNZ main_p_loop
    
    LOAD R0, SYS_EXIT
    SYSCALL