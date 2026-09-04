| SELECT-ARRAY READOUT -- a display formatter, not a writer (4 Sep 2026)
|
| THE QUESTION IT SETTLES. docs/MAINMENU.md 9c-ii decoded where a page-2
| SELECT's value lives:
|
|     DB + part*6322 + 0x8f04a + track*30 + page*6 + slot
|
| and drove the firmware's own two-phase editor into writing that array --
| but on a machine with NO PROJECT LOADED the write landed at offset zero,
| so the track/page/slot terms are decoded but UNCONFIRMED. Every local
| attempt to confirm them hit the same wall: the emulator boots with no CF
| card, so the project DB and everything hanging off it are empty.
|
| This settles it from the other side and needs no writer at all. It PRINTS
| the byte that formula addresses, on a real unit with a real project. Turn
| a page-2 select on the panel: if the number here follows it, the formula
| is right; if it does not, the formula is wrong and the printed value says
| how far off.
|
| WHERE IT DRAWS. Registered as HELLO WORLD's GAIN formatter, the same
| readout slot modules/cfprobe uses -- so the two are MUTUALLY EXCLUSIVE in
| one image, and remixes/selprobe.py carries this one alone.
|
| WHAT THE KNOB CHOOSES. GAIN's own value picks what is shown, so one knob
| reads the whole block:
|
|     0..20    slot 0        the first page-2 select of the current track
|     21..41   slot 1
|     42..62   slot 2
|     63..83   slot 3
|     84..104  slot 4
|     105..127 slot 5
|
| PAGE is fixed at 4 (FX2), the page docs/MAINMENU.md 9c measured as the FX2
| one from the page-1 writer's own arithmetic.
|
| ⚠️ READ-ONLY BY CONSTRUCTION. It calls nothing and stores nothing; the
| only thing it writes is the caller's sprintf buffer. A formatter runs
| inside a redraw, and the firmware's own select editor ENDS in redraw
| calls, so a formatter that invoked it would re-enter the drawing code --
| which is why this probe reads rather than writes.
|
| Clobbers d0/d1/a0/a1 like every stock formatter; saves the rest.

        .text
fmt:    lea     -16(%sp),%sp
        movem.l %d2-%d4,(%sp)           | 12 bytes: buf 20(sp), value 24(sp)
| ---- GAIN encodes PAGE and SLOT, not slot alone -------------------------
| The first build read FX2's page only, and the image it shipped in hides
| every effect that HAS an FX2 page-2 select -- so there was nothing on the
| unit to turn and nothing the probe could ever see move. One knob now reads
| the whole space instead of assuming a page:
|
|     slot = value mod 6,  page = value div 6,  clamped to page 4
|
| so GAIN 0..5 is page 0, 6..11 page 1, 12..17 page 2, 18..23 page 3 (FX1),
| 24..29 page 4 (FX2), and anything above 29 pins to page 4 slot 5.
        move.l  24(%sp),%d0             | GAIN 0..127
        moveq   #29,%d1
        cmp.l   %d0,%d1
        bge.s   1f
        move.l  %d1,%d0                 | above 29: pin to page 4, slot 5
1:      moveq   #6,%d1
        divu.l  %d1,%d0                 | d0 = page, remainder in the pair
        move.l  24(%sp),%d3
        moveq   #29,%d1
        cmp.l   %d3,%d1
        bge.s   2f
        move.l  %d1,%d3
2:      moveq   #6,%d1
        divu.l  %d1,%d3
        move.l  %d3,%d4                 | d4 = page (again, for the address)
        move.l  %d3,%d1
        moveq   #6,%d3
        mulu.l  %d3,%d1
        move.l  24(%sp),%d2
        moveq   #29,%d3
        cmp.l   %d2,%d3
        bge.s   3f
        move.l  %d3,%d2
3:      sub.l   %d1,%d2                 | d2 = slot = value - page*6

        move.l  0x46c82456,%d3          | the project DB base
        beq.s   none                    | no project: nothing to read
        moveq   #0,%d0
        move.b  0x100b14cf,%d0          | current part
        move.l  #6322,%d1
        mulu.l  %d1,%d0
        add.l   %d0,%d3
        moveq   #0,%d0
        move.b  0x100b14cc,%d0          | current track
        move.l  #30,%d1
        mulu.l  %d1,%d0                 | track*30
        add.l   %d0,%d3
        add.l   #0x8f04a,%d3            | the select array
        move.l  %d4,%d0
        moveq   #6,%d1
        mulu.l  %d1,%d0
        add.l   %d0,%d3                 | + page*6
        add.l   %d2,%d3                 | + slot
        move.l  %d3,%a0
        moveq   #0,%d1
        move.b  (%a0),%d1               | the byte the formula addresses

| ---- THE BYTE COMES FIRST -------------------------------------------------
| Printed page*4096 + slot*256 + byte, a MODE step moved the number by ONE in
| five digits -- 12544 to 12545 -- which on the unit was unreadable, and the
| operator could not tell "it did not move" from "I could not see it move".
| The byte is what the measurement is ABOUT, so it leads:
|
|     byte*256 + page*16 + slot
|
| A MODE step is now a jump of 256: 49, 305, 561, 817, 1073 for MODE 0..4 on
| page 3 slot 1. The row is still visible in the last two digits, so a
| knob that slipped is still distinguishable from a byte that changed.
        move.l  %d1,%d0
        lsl.l   #4,%d0
        add.l   %d4,%d0
        lsl.l   #4,%d0
        add.l   %d2,%d0
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
