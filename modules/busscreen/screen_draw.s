| BUS SCREEN draw handler (step 3) -- twelve rows: name + live value, and the
| label set follows the host effect (BusVerb id 7, BusDelay id 6).
|
| draw(window_handle): the handle is at sp@(48) after the 11-register prologue.
| For each of twelve slots we draw the parameter NAME and its current VALUE,
| read from the per-track displayed-value array in the Part
| (DB + part*6322 + 0x8f084 + track*30 + slot; DB = *0x46c82456, part byte at
| 0x80000003, track at 0x80000000 -- the pair the editor 0x4003a474 uses). The value is turned into text with the firmware sprintf.
|
|   DRAW_STRING(context, window, x, y, flags, string)   @ 0x40012bd8
|   sprintf(buf, fmt, arg)                              @ 0x40013a08
|
| Four self-references the build patches to cave addresses: VERBTAB, DLYTAB
| (the two twelve-entry name pointer tables), FMT ("%d"), SCRATCH (an 8-byte
| number buffer). Placeholders 0x40bad000/4/8/c. Everything else is OS
| absolutes.

        .set    VERBTAB, 0x40bad000
        .set    DLYTAB,  0x40bad004
        .set    FMT,     0x40bad008
        .set    SCRATCH, 0x40bad00c
        .set    DRAW_STRING, 0x40012bd8
        .set    SPRINTF, 0x40013a08
        .set    CONTEXT, 0x400ba876
        .set    DBPTR,   0x46c82456
        .set    PARTB,   0x80000003     | current part (byte) -- the pair 0x4003a474 uses
        .set    TRACKB,  0x80000000     | current audio track (byte)
        .set    VALOFF,  0x8f084
        .set    IDOFF,   0x8ed88
        .set    NROWS, 12

        .text
draw:   lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@     | 11 regs -> arg at sp@(48)
        moveal  %sp@(48),%a4             | the window handle
        tstl    %a4
        beq     ddone

        movel   DBPTR,%d7                | d7 = DB base
        beq     ddone                    | no project -> draw nothing
        moveq   #0,%d0
        moveb   PARTB,%d0                | part (byte)
        movel   #6322,%d1
        mulu.l  %d1,%d0                   | part*6322
        addl    %d0,%d7                   | d7 = DB + part*6322
        moveq   #0,%d6
        moveb   TRACKB,%d6               | d6 = track (byte)

        | pick the label table from this track's FX2 effect id
        movel   %d7,%a0
        addal   #IDOFF,%a0
        addal   %d6,%a0
        moveq   #0,%d0
        moveb   %a0@,%d0                 | FX2 id
        lea     VERBTAB,%a5
        moveq   #6,%d1
        cmpl    %d0,%d1
        bne.s   1f
        lea     DLYTAB,%a5               | id 6 -> BusDelay names
1:
        | value base: a3 = d7 + 0x8f084 + track*30
        movel   %d6,%d0
        moveq   #30,%d1
        mulu.l  %d1,%d0                   | track*30
        movel   %d7,%a3
        addal   #VALOFF,%a3
        addal   %d0,%a3

        moveq   #0,%d3                   | slot 0..11
dloop:  movel   %d3,%d4
        lsll    #3,%d4
        addql   #8,%d4                   | y = 8 + slot*8

        | ---- name at x=8 ----
        movel   %a5@(0,%d3:l:4),%d2      | name pointer
        movel   %d2,%sp@-
        pea     0xffffffff
        movel   %d4,%sp@-
        pea     8
        movel   %a4,%sp@-
        pea     CONTEXT
        jsr     DRAW_STRING
        lea     %sp@(24),%sp

        | ---- value at x=52 ----
        moveq   #0,%d0
        moveb   %a3@(0,%d3:l),%d0        | current value byte
        movel   %d0,%sp@-                | sprintf arg
        pea     FMT
        pea     SCRATCH
        jsr     SPRINTF
        lea     %sp@(12),%sp
        movel   %d3,%d4
        lsll    #3,%d4
        addql   #8,%d4                   | y again (sprintf clobbered nothing kept, recompute)
        pea     SCRATCH
        pea     0xffffffff
        movel   %d4,%sp@-
        pea     52
        movel   %a4,%sp@-
        pea     CONTEXT
        jsr     DRAW_STRING
        lea     %sp@(24),%sp

        addql   #1,%d3
        moveq   #NROWS,%d0
        cmpl    %d3,%d0
        bgt     dloop
ddone:  movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts
