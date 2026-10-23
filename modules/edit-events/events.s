/* EDIT EVENTS uses stack-local frames. Notification callbacks may clobber
 * every d/a register except SP. Preserve interrupt mask; no reentrant edits.
 * copy_pre: d0=destination, d1=source, d2=length.
 * held claim: d0=encoder, d1=delta; return d0=0 to pass, nonzero to own.
 * held handler: native function entry frame, including original stack args.
 */
    .text
    .global ed_copy,ed_held
    .macro SAVE
    lea -64(%sp),%sp
    movem.l %d0-%d7/%a0-%a6,(%sp)
    move.w %sr,%d1
    move.w %d1,60(%sp)
    .endm
    .macro REST
    move.w 60(%sp),%d1
    move.w %d1,%sr
    movem.l (%sp),%d0-%d7/%a0-%a6
    lea 64(%sp),%sp
    .endm
ed_copy:
    SAVE
    move.l 68(%sp),%d0
    move.l 72(%sp),%d1
    move.l 76(%sp),%d2
    lea ed_ev_copy_pre,%a0
    bsr.w ed_fire
    /* Native copy runs exactly once, with the original arguments. */
    move.l 76(%sp),-(%sp)
    move.l 76(%sp),-(%sp)
    move.l 76(%sp),-(%sp)
    jsr 0x40020898
    lea 12(%sp),%sp
    move.w %sr,%d1
    move.w %d1,60(%sp)
    move.l %d0,(%sp)
    REST
    rts
ed_fire:
    lea -16(%sp),%sp
    movem.l %d0-%d2/%a0,(%sp)
ed_fire_next:
    move.l 12(%sp),%a0
    move.l (%a0)+,%d0
    beq.s ed_fire_done
    move.l %a0,12(%sp)
    move.l %d0,%a1
    movem.l (%sp),%d0-%d2
    jsr (%a1)
    bra.s ed_fire_next
ed_fire_done:
    lea 16(%sp),%sp
    rts
ed_held:
    /* Reserve a tail-jump slot before saving the native register frame. */
    lea -4(%sp),%sp
    SAVE
    lea ed_ev_held,%a0
ed_claim_next:
    move.l (%a0)+,%d0
    beq.s ed_native
    move.l %a0,64(%sp)
    move.l %d0,%a1
    move.l 72(%sp),%d0
    move.l 76(%sp),%d1
    jsr (%a1)
    tst.l %d0
    bne.s ed_claimed
    move.l 64(%sp),%a0
    addq.l #4,%a0
    bra.s ed_claim_next
ed_claimed:
    move.l 64(%sp),%a0
    move.l (%a0),64(%sp)
    REST
    rts /* consumes tail target; handler sees the untouched native frame */
ed_native:
    REST
    lea 4(%sp),%sp
    lea -80(%sp),%sp
    movem.l %d2-%d7/%a2-%fp,(%sp)
    jmp 0x400508ec
    .balign 4
    .include "remix.inc"
