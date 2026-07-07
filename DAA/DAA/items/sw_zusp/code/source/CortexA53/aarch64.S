.section .text
.global aarch64_get_cntfrq_el0
.global aarch64_get_cntpct_el0
.global aarch64_get_cntp_ctl_el0
.global aarch64_get_affinity_el1

aarch64_get_cntfrq_el0:
    mrs x0, CNTFRQ_EL0
    ret


aarch64_get_cntpct_el0:
    mrs x0, CNTPCT_EL0
    ret
aarch64_get_cntp_ctl_el0:
    mrs x0, CNTP_CTL_EL0
    ret

aarch64_get_affinity_el1:
    mrs x0, MPIDR_EL1
    mov x1, #3
    and x0, x0, x1
    mov x1, #0
    ret
