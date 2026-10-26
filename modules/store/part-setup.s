/* Refresh only live client fields before native NOTE SETUP YES. */
    .include "remix.inc"
    .text
    .global store_part_note_confirm
store_part_note_confirm:
    lea -16(%sp),%sp
    movem.l %d0-%d2/%a0,(%sp)
    jsr store_part_ui_context
    move.l %d0,%d1
    STORE_PART_NOTE_REFRESH
    movem.l (%sp),%d0-%d2/%a0
    lea 16(%sp),%sp
    lea -44(%sp),%sp
    movem.l %d2-%d7/%a2-%fp,(%sp)
    jmp 0x4004af28
