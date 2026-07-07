     .globl   spin_lock
     .p2align 2
     .type    spin_lock,%function
spin_lock:              // Function "spin_lock" entry point.
     .cfi_startproc
     // send ourselves an event, so we don't stick on the wfe at the
     // top of the loop

     mov w3, #1
     sevl
spin_loop:
     wfe
     dc ivac, x0                        //   Invalidate 'x0' cache value and take it from RAM
     isb                                //   Assure change in register
     ldaxr w1, [x0]
     cmp w1, #0
     bne spin_loop
     stlxr w2, w3, [x0]
     cbnz w2, spin_loop
     dc cvac, x0              //   Invalidate 'x0' cache value, but pushing it from local cache before
     ret                      //   Return by branching to the address in the link register.
     .cfi_endproc

     .globl   spin_unlock
     .p2align 2
     .type    spin_unlock,%function
spin_unlock:
     .cfi_startproc                // Function "spin_unlock" entry point.
     mov w1, #0
     strb w1, [x0]                 // Store 0 in the spin_lock variable
     sev                           // Send sev
     dc cvac, x0                   //   Invalidate 'x0' cache value, but pushing it from local cache before
     ret                           // Return by branching to the address in the link register.
     .cfi_endproc