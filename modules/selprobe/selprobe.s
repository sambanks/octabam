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
        move.l  24(%sp),%d0             | GAIN 0..127
        move.l  #21,%d1
        divu.l  %d1,%d0                 | slot = value / 21
        moveq   #5,%d1
        cmp.l   %d0,%d1
        bge.s   1f
        move.l  %d1,%d0                 | the top band is 105..127
1:      move.l  %d0,%d2                 | d2 = slot 0..5

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
        add.l   #24,%d3                 | page 4 -> +4*6
        add.l   %d2,%d3                 | + slot
        move.l  %d3,%a0
        moveq   #0,%d1
        move.b  (%a0),%d1               | the byte the formula addresses

        move.l  %d2,%d0
        lsl.l   #8,%d0
        add.l   %d1,%d0                 | print as slot*256 + value
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
