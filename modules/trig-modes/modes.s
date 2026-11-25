/* Shared MIDI playing-mode boundaries. Client callbacks use the C ABI.
 * The native audio modes and grid key/LED paths retain their continuations. */
    .include "remix.inc"
    .text
    .global tm_list_names,tm_bar_names,tm_cursor,tm_row
    .global tm_key,tm_leds,tm_guide,tm_release,tm_grid,tm_octave

tm_list_names:
    move.l #0x400beb72,%d6
    tst.l 0x80000012
    beq.s .list_done
    move.l #tm_names,%d6
.list_done:
    tst.l %d6
    jmp 0x40035a00

tm_bar_names:
    lea -8(%sp),%sp
    move.l %d0,(%sp)
    move.w %sr,%d0
    move.l %d0,4(%sp)
    lea 0x400beb72,%a0
    tst.l 0x80000012
    beq.s .bar_done
    lea tm_names,%a0
.bar_done:
    move.l 4(%sp),%d0
    move.w %d0,%ccr
    movem.l (%sp),%d0
    lea 8(%sp),%sp
    jmp 0x4003604c

/* d0 native mode ID -> d0 its MIDI menu row. Unknown IDs select TRACKS.
 * IDs and rows are deliberately separate: mode 6 is not necessarily row 6. */
tm_row:
    lea -8(%sp),%sp
    movem.l %d1/%a0,(%sp)
    lea tm_modes,%a0
    moveq #0,%d1
.row_next:
    cmp.l (%a0)+,%d0
    beq.s .row_found
    addq.l #1,%d1
    cmpi.l #TM_ROWS,%d1
    bcs.s .row_next
    moveq #0,%d1
.row_found:
    move.l %d1,%d0
    movem.l (%sp),%d1/%a0
    lea 8(%sp),%sp
    rts

tm_cursor:
    move.l 0x460d16f0,%d0
    tst.l 0x80000012
    beq.s .cursor_push
    bsr.s tm_row
.cursor_push:
    move.l %d0,-(%sp)
    jmp 0x40058748

tm_key:
    tst.l 0x80000012
    beq.s .key_stock
    move.l 0x460d16f0,%d0
    tm_dispatch_key
.key_stock:
    move.l %d2,-(%sp)
    move.l 8(%sp),%a0
    jmp 0x400501de

/* The native key tail redraws the guide and LEDs and restores d2. Keep
 * one refresh boundary for every registered playing mode. */
.key_refresh:
    move.l %d2,-(%sp)
    jmp 0x400502d4

tm_leds:
    tst.l 0x80000012
    beq.s .led_stock
    tm_overlays
    tst.l 0x460d1736
    bne.s .led_stock
    move.l 0x460d16f0,%d0
    tm_dispatch_leds
.led_stock:
    lea -68(%sp),%sp
    movem.l %d2-%d6/%a2-%a5,(%sp)
    jmp 0x40043fe4

tm_guide:
    tst.l 0x80000012
    beq.s .guide_stock
    move.l 0x460d16f0,%d0
    tm_dispatch_guide
.guide_stock:
    lea -44(%sp),%sp
    movem.l %d2-%d7/%a2-%fp,(%sp)
    jmp 0x40044928

/* Native cleanup can arrive after the mode/track has changed. Notify every
 * selected client with the original track; each releases only what it owns.
 * Arguments, registers and CCR survive before the native prologue runs. */
tm_release:
    lea -64(%sp),%sp
    movem.l %d0-%d7/%a0-%a6,(%sp)
    move.w %sr,%d0
    move.l %d0,60(%sp)
    tm_releases
    move.l 60(%sp),%d0
    move.w %d0,%ccr
    movem.l (%sp),%d0-%d7/%a0-%a6
    lea 64(%sp),%sp
    lea -16(%sp),%sp
    movem.l %d2-%d3/%a2-%a3,(%sp)
    jmp 0x40043730

tm_grid:
    tst.l 0x80000012
    beq.s .grid_stock
    tst.l 0x460d1736
    bne.s .grid_stock
    move.l 0x460d16f0,%d0
    tm_registered
    bra.s .grid_stock
.grid_release:
    lea -16(%sp),%sp
    movem.l %d0-%d1/%a0-%a1,(%sp)
    jsr 0x400438dc
    movem.l (%sp),%d0-%d1/%a0-%a1
    lea 16(%sp),%sp
.grid_stock:
    lea 0x4007e998,%a0
    jmp 0x40048790

tm_octave:
    lea -4(%sp),%sp
    move.l %d1,(%sp)
    move.l 0x460d16f0,%d1
    tst.l 0x80000012
    beq.w .octave_compare
    tm_octaves
.octave_compare:
    cmp.l %d1,%d0
    movem.l (%sp),%d1
    lea 4(%sp),%sp
    rts

    tm_tables
