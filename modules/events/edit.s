/* edit.held selects the first owner; edit.copy_pre notifies all clients.
 * The generated macros reload arguments independently before every callback.
 * Native stack frames, copy arguments and return values stay native. */
    .text
    .include "modules/events/frame.inc"
    .include "remix.inc"
    .if ev_edit_copy_pre_count
    .global ed_copy
ed_copy:
    EV_SAVE
    ev_edit_copy_pre
    EV_RESTORE
    /* Tail-call native memcpy once, with its original stack and arguments. */
    jmp 0x40020898
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
