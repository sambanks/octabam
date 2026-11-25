/* STORE copy extension: protect retained MIDI padding only in CS1. */
    .text
    .global store_retained_copy
store_retained_copy:
    /* Only CS1 pattern copies need the protected pool path. The ROM
     * entry remains cold-safe until store_part_activate publishes this unit. */
    move.l 4(%sp),%d0
    cmpi.l #0x100a4ece,%d0
    bcc.s .pool_source
    cmpi.l #0x1001614e,%d0
    bcc.s .pool_copy
    add.l 12(%sp),%d0
    cmpi.l #0x1001614e,%d0
    bhi.s .pool_copy
.pool_source:
    move.l 8(%sp),%d0
    cmpi.l #0x100a4ece,%d0
    bcc.s .pool_no_copy
    cmpi.l #0x1001614e,%d0
    bcc.s .pool_copy
    add.l 12(%sp),%d0
    cmpi.l #0x1001614e,%d0
    bhi.s .pool_copy
.pool_no_copy:
    move.l %d2,-(%sp)
    move.l 8(%sp),%a1
    jmp 0x4002089e

.pool_copy:
    jmp store_retained_native_copy
