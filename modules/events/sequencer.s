/* Notification-only contracts; no callback may emit MIDI or re-enter these
 * boundaries. Unsubscribed events emit no code and install no detours. */
    .text
    .include "modules/events/frame.inc"
    .include "remix.inc"
    .if ev_transport_start_count
    .global seq_start
seq_start:
    move.l %d0,0x800065b8
    EV_SAVE
    ev_transport_start
    EV_RESTORE
    jmp 0x4009c3da
    .endif
    .if ev_transport_resume_count
    .global seq_resume
seq_resume:
    move.l %d0,0x800065b8
    EV_SAVE
    ev_transport_resume
    EV_RESTORE
    jmp 0x4009c4da
    .endif
    .if ev_midi_note_accepted_count
    .global seq_sent_a,seq_sent_b
seq_sent_a:
    bsr.w seq_sent
    move.b 0x400d807c,%d1
    extb.l %d1
    jmp 0x4009fbb8
seq_sent_b:
    bsr.w seq_sent
    move.b 0x400d807c,%d0
    extb.l %d0
    jmp 0x4009fd00
seq_sent:
    EV_SAVE
    cmpi.l #7,%d7
    bhi.w seq_sent_done
    move.l %d7,%d0
    moveq #10,%d1
    mulu.l %d7,%d1
    lea 0x46c77b1e,%a0
    move.b (%a0,%d1.l),%d1
    andi.l #255,%d1
    moveq #0,%d2
    move.b 0x400d807e,%d2
    moveq #0,%d3
    move.b 0x400d807d,%d3
    /* Keep the notification payload separate from the native register frame. */
    lea -16(%sp),%sp
    movem.l %d0-%d3,(%sp)
    ev_midi_note_accepted
    lea 16(%sp),%sp
seq_sent_done:
    EV_RESTORE
    rts
    .endif
