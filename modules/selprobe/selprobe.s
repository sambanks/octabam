| SELECT-ARRAY READOUT, fourth build -- designed around the PANEL (4 Sep 2026)
|
| Three flashes taught what a probe on this panel has to respect:
|
|   * A knob's VALUE is shown only while that knob is TURNING. So the readout
|     is visible only while GAIN moves, and GAIN is also what chooses the
|     row. Therefore the row bands must be WIDE enough that a wiggle stays
|     inside one: ten values per band. Wiggle GAIN, read the number, stay in
|     the band.
|   * Turning a NEIGHBOURING knob redraws only that knob's label. A "refresh
|     knob" does nothing. Removed.
|   * The image that carries this hides every FX2 effect with a page-2
|     select, so the turnable selects are on FX1 (Spectrum's MODE/ROUT/SRC).
|     The probe covers BOTH FX1 and FX2 so the page term is tested too.
|   * The byte being measured must DOMINATE the number: hundreds and up.
|
| GAIN picks the row:
|     0..59    FX1 (page 3)    slot = GAIN / 10
|     60..119  FX2 (page 4)    slot = (GAIN - 60) / 10
|     120+     pinned to FX2 slot 5
|
| The number shown is   byte*100 + page*10 + slot
|     e.g. FX1 MODE (page 3, slot 1) reads 31, 131, 231, 331, 431 for MODE
|     positions 1..5. Hundreds = the byte. Tens = page. Units = slot.
|
| Reads    DB + part*6322 + 0x8f04a + track*30 + page*6 + slot
| for the CURRENT track (0x100b14cc) and part (0x100b14cf). It writes
| nothing but the caller's sprintf buffer. Registered on HELLO WORLD's GAIN.

        .text
fmt:    lea     -16(%sp),%sp
        movem.l %d2-%d4,(%sp)           | buf 20(sp), value 24(sp)
        move.l  24(%sp),%d0             | GAIN 0..127
        moveq   #119,%d1
        cmp.l   %d0,%d1
        bge.s   1f
        move.l  %d1,%d0                 | pin 120+ to 119
1:      moveq   #3,%d4                  | page 3 = FX1
        moveq   #59,%d1
        cmp.l   %d0,%d1
        bge.s   2f
        sub.l   #60,%d0                 | 60..119 -> FX2
        moveq   #4,%d4
2:      moveq   #10,%d1
        divu.l  %d1,%d0                 | slot = band / 10, 0..5
        move.l  %d0,%d2                 | d2 = slot

        move.l  0x46c82456,%d3          | project DB base
        beq.s   none
        moveq   #0,%d0
        move.b  0x100b14cf,%d0          | current part
        move.l  #6322,%d1
        mulu.l  %d1,%d0
        add.l   %d0,%d3
        moveq   #0,%d0
        move.b  0x100b14cc,%d0          | current track
        moveq   #30,%d1
        mulu.l  %d1,%d0
        add.l   %d0,%d3                 | + track*30
        add.l   #0x8f04a,%d3            | the select array
        move.l  %d4,%d0
        moveq   #6,%d1
        mulu.l  %d1,%d0
        add.l   %d0,%d3                 | + page*6
        add.l   %d2,%d3                 | + slot
        move.l  %d3,%a0
        moveq   #0,%d1
        move.b  (%a0),%d1               | the byte

        move.l  #100,%d0
        mulu.l  %d0,%d1                 | byte*100
        move.l  %d4,%d0
        moveq   #10,%d3
        mulu.l  %d3,%d0                 | page*10
        add.l   %d0,%d1
        add.l   %d2,%d1                 | + slot
        move.l  %d1,%d0
        movem.l (%sp),%d2-%d4
        lea     16(%sp),%sp
        move.l  %d0,-(%sp)
        pea     0x400b465d              | "%d"
        move.l  12(%sp),-(%sp)          | buf
        jsr     0x40013a08
        lea     12(%sp),%sp
        rts

none:   movem.l (%sp),%d2-%d4
        lea     16(%sp),%sp
        pea     nostr(%pc)
        move.l  8(%sp),-(%sp)
        jsr     0x40013a08
        addq.l  #8,%sp
        rts

nostr:  .asciz  "-"
        .balign 4
