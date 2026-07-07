.section .text
.global init_cores

init_cores: 

    mrs x0, MPIDR_EL1
    mov x1, #3
    and x0, x0, x1
    mov x1, #0
    ret
