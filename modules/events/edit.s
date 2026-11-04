/* edit.held selects the first owner; edit.copy_pre/post notify all clients.
 * The generated macros reload arguments independently before every callback.
 * Native stack frames, copy arguments and return values stay native. */
    .text
    .include "modules/events/frame.inc"
    .include "remix.inc"
    .if ev_edit_copy_pre_count + ev_edit_copy_post_count
    .global ed_copy
ed_copy:
    EV_SAVE
    ev_edit_copy_pre
    EV_RESTORE
    .if ev_edit_copy_post_count
    /* Copy the original arguments; keep every native output register and CCR
     * across post notifications. No shared return slot or second copy. */
    move.l 12(%sp),-(%sp)
    move.l 12(%sp),-(%sp)
    move.l 12(%sp),-(%sp)
    jsr 0x40020898
    lea 12(%sp),%sp
    EV_SAVE
    ev_edit_copy_post
    EV_RESTORE
    rts
    .else
    /* With no post client, retain the native tail call and entry frame. */
    jmp 0x40020898
    .endif
    .endif
    .if ev_edit_held_count
    .global ed_held
ed_held:
    EV_SAVE
    ev_edit_held
    EV_RESTORE
    lea -80(%sp),%sp
    movem.l %d2-%d7/%a2-%fp,(%sp)
    jmp 0x400508ec
    .endif
