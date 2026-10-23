/* Stack-local native frame. Callbacks may clobber all d/a registers except SP,
 * and must preserve the interrupt mask. LEA/MOVEM leave CCR unchanged. */
    .macro EV_SAVE
    lea -64(%sp),%sp
    movem.l %d0-%d7/%a0-%a6,(%sp)
    move.w %sr,%d1
    move.w %d1,60(%sp)
    .endm
    .macro EV_RESTORE
    move.w 60(%sp),%d1
    move.w %d1,%sr
    movem.l (%sp),%d0-%d7/%a0-%a6
    lea 64(%sp),%sp
    .endm
