| BUS SCREEN handlers -- double-wide: two columns of six show all twelve
| controls at once (no scroll, no page). Cursor + level knob, the native OT
| effect-setup idiom.
|
|   left column  = slots 0..5  (page 1): name x=3,  value x=32,  bar x 2..58
|   right column = slots 6..11 (page 2): name x=61, value x=90,  bar x 60..116
|   row = slot mod 6, STOCK pitch: bar y = 4 + row*7, text at bar_y+1. The
|   cursor row is an INVERTED BAR drawn after its text with the firmware's
|   own rect-invert 0x40012254(window, x1, y1, x2, y2, -1) -- exactly what
|   the stock menu lists do -- not a marker glyph.
|
| Values from the Part arrays the writers use (so edits are visible):
|   page 1 (0..5):  DB + part*6322 + 0x8ee9a + track*24 + 18 + slot
|   page 2 (6..11): DB + part*6322 + 0x8ef5a + track*30 + 18 + slot
| Selects render as WORDS via per-engine label records (a6). DB=*0x46c82456,
| part=byte 0x80000003, track=byte 0x80000000 (the pair 0x4003a474 uses).
|
| Arrows are position-dependent; CONFIRMED reaching this handler (tag 86):
| 0x34 (UP) and 0x33 (LEFT). UP arrow -> up, LEFT arrow -> down, and 0x35/0x36
| accepted as down too if the physical DOWN/RIGHT arrow sends one.
|
| Two CONTROL rows REVERB/DELAY scan the per-track FX2 ids (0x80000ecc) for
| their engine, select that track, open the screen. Self-refs the build
| patches (0x40bad000..20): VERBTAB DLYTAB FMT SCRATCH CURSOR GT VERBSEL DLYSEL.

        .set    VERBTAB, 0x40bad000
        .set    DLYTAB,  0x40bad004
        .set    FMT,     0x40bad008
        .set    SCRATCH, 0x40bad00c
        .set    CURSOR,  0x40bad010
        .set    VERBSEL, 0x40bad014
        .set    DLYSEL,  0x40bad018
        .set    DRAW_STRING, 0x40012bd8
        .set    INVERT,  0x40012254     | invert_rect(window,x1,y1,x2,y2,flags)
        .set    SPRINTF, 0x40013a08
        .set    P1WRITE, 0x40054cd8
        .set    P2EDIT,  0x4003a474
        .set    PAGEGLOB, 0x460d5c30
        .set    CONTEXT, 0x400ba876
        .set    DBPTR,   0x46c82456
        .set    PARTB,   0x80000003
        .set    TRACKB,  0x80000000
        .set    IDBASE,  0x80000ecc
        .set    STATEG,  0x400cbf40
        .set    VIEWG,   0x400cbd9c
        .set    P1OFF,   0x8ee9a
        .set    P2OFF,   0x8ef5a
        .set    IDOFF,   0x8ed88
        .set    NSLOTS, 12

        .text
| ---- draw(window) --------------------------------------------------------
draw:   lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        moveal  %sp@(48),%a4
        tstl    %a4
        beq     ddone
        movel   DBPTR,%d0
        beq     ddone
        moveq   #0,%d1
        moveb   PARTB,%d1
        movel   #6322,%d2
        mulu.l  %d2,%d1
        addl    %d1,%d0                 | d0 = DB + part*6322
        moveq   #0,%d1
        moveb   TRACKB,%d1              | track
        | label + select tables by FX2 id
        movel   %d0,%a0
        addal   #IDOFF,%a0
        addal   %d1,%a0
        moveq   #0,%d2
        moveb   %a0@,%d2
        lea     VERBTAB,%a5
        lea     VERBSEL,%a6
        moveq   #6,%d3
        cmpl    %d2,%d3
        bne.s   1f
        lea     DLYTAB,%a5
        lea     DLYSEL,%a6
1:      | page-1 base a3 (a3+slot), page-2 base a2 (a2+slot)
        movel   %d1,%d2
        moveq   #24,%d3
        mulu.l  %d3,%d2
        movel   %d0,%a3
        addal   #P1OFF,%a3
        addal   %d2,%a3
        addal   #18,%a3
        movel   %d1,%d2
        moveq   #30,%d3
        mulu.l  %d3,%d2
        movel   %d0,%a2
        addal   #P2OFF,%a2
        addal   %d2,%a2
        addal   #18,%a2
        moveq   #0,%d3                  | slot 0..11
dloop:  | column geometry: d6=name_x d7=val_x, d5=bar_y (text at d5+1)
        moveq   #6,%d0
        movel   %d3,%d4
        cmpl    %d3,%d0
        bgt.s   dleft
        subql   #6,%d4                  | right column: row = slot-6
        moveq   #61,%d6
        moveq   #90,%d7
        bra.s   drow
dleft:  moveq   #3,%d6
        moveq   #32,%d7
drow:   movel   %d4,%d5
        moveq   #7,%d0
        muls.l  %d0,%d5
        addql   #4,%d5                  | bar_y = 4 + row*7
        | name at (name_x, bar_y+1)
        movel   %a5@(0,%d3:l:4),%d2
        movel   %d5,%d1
        addql   #1,%d1
        movel   %d2,%sp@-
        pea     0xffffffff
        movel   %d1,%sp@-
        movel   %d6,%sp@-
        movel   %a4,%sp@-
        pea     CONTEXT
        jsr     DRAW_STRING
        lea     %sp@(24),%sp
        | value byte (page-1 vs page-2 array)
        moveq   #0,%d0
        moveq   #6,%d1
        cmpl    %d3,%d1
        bgt.s   dp1
        moveb   %a2@(0,%d3:l),%d0
        bra.s   dsel
dp1:    moveb   %a3@(0,%d3:l),%d0
dsel:   movel   %a6@(0,%d3:l:4),%a1     | select record or 0
        movel   %a1,%d1
        beq.s   dnum
        movel   %a1@,%d1
        subql   #1,%d1
        cmpl    %d1,%d0
        ble.s   dcl
        movel   %d1,%d0
dcl:    tstl    %d0
        bge.s   dgl
        moveq   #0,%d0
dgl:    movel   %a1@(4,%d0:l:4),%d2     | label pointer
        bra.s   ddv
dnum:   movel   %d0,%sp@-
        pea     FMT
        pea     SCRATCH
        jsr     SPRINTF
        lea     %sp@(12),%sp
        movel   #SCRATCH,%d2
ddv:    movel   %d5,%d1
        addql   #1,%d1
        movel   %d2,%sp@-
        pea     0xffffffff
        movel   %d1,%sp@-
        movel   %d7,%sp@-
        movel   %a4,%sp@-
        pea     CONTEXT
        jsr     DRAW_STRING
        lea     %sp@(24),%sp
        | cursor row: invert the bar AFTER its text, as stock does
        movel   CURSOR,%d0
        cmpl    %d3,%d0
        bne.s   dnext
        pea     0xffffffff              | flags
        movel   %d5,%d1
        addql   #6,%d1
        movel   %d1,%sp@-               | y2 = bar_y+6
        movel   %d7,%d1
        addl    #26,%d1
        movel   %d1,%sp@-               | x2 = val_x+26
        movel   %d5,%sp@-               | y1 = bar_y
        movel   %d6,%d1
        subql   #1,%d1
        movel   %d1,%sp@-               | x1 = name_x-1
        movel   %a4,%sp@-               | window
        jsr     INVERT
        lea     %sp@(24),%sp
dnext:  addql   #1,%d3
        moveq   #NSLOTS,%d0
        cmpl    %d3,%d0
        bgt     dloop
ddone:  movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| ---- key(keycode): up/down through 0..11, WRAPPING (infinite scroll) -----
| Confirmed on hardware (tags 86-89): 0x34 moves UP and 0x33 moves DOWN --
| the key Sam has under his thumb as "left" sends 0x33 and it is the one that
| goes down; nothing in 0x32/0x35/0x36 moved the cursor. Kept as-is per Sam.
key:    movel   %sp@(4),%d0
        movel   CURSOR,%d1
        moveq   #0x34,%d2               | UP arrow -> up
        cmpl    %d0,%d2
        beq.s   kup
        moveq   #0x33,%d2               | the key that moves DOWN on the unit
        cmpl    %d0,%d2
        beq.s   kdn
        moveq   #0x32,%d2               | (other candidates, harmless)
        cmpl    %d0,%d2
        beq.s   kdn
        moveq   #0x35,%d2
        cmpl    %d0,%d2
        beq.s   kdn
        moveq   #0x36,%d2
        cmpl    %d0,%d2
        beq.s   kdn
        bra.s   kdone
kup:    tstl    %d1
        bne.s   kup1
        moveq   #NSLOTS-1,%d1           | wrap 0 -> 11
        bra.s   kstore
kup1:   subql   #1,%d1
        bra.s   kstore
kdn:    moveq   #NSLOTS-1,%d2
        cmpl    %d1,%d2
        bne.s   kdn1
        moveq   #0,%d1                  | wrap 11 -> 0
        bra.s   kstore
kdn1:   addql   #1,%d1
kstore: movel   %d1,CURSOR
kdone:  rts

| ---- enter actions: select the host track, open the screen ----------------
enter_rev: moveq  #7,%d0
        bra.s   ecom
enter_dly: moveq  #6,%d0
ecom:   lea     IDBASE,%a0
        moveq   #0,%d1
esc:    moveb   %a0@+,%d2
        andl    #0xff,%d2
        cmpl    %d0,%d2
        beq.s   efound
        addql   #1,%d1
        moveq   #8,%d2
        cmpl    %d1,%d2
        bgt.s   esc
        bra.s   eopen
efound: moveb   %d1,TRACKB
eopen:  moveq   #0,%d0
        movel   %d0,CURSOR
        moveq   #16,%d0
        movel   %d0,STATEG
        moveq   #13,%d0
        movel   %d0,VIEWG
        rts

| ---- enc(index, delta): edit the cursor slot -----------------------------
enc:    lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        movel   %sp@(52),%d5            | delta
        movel   CURSOR,%d3              | slot 0..11
        moveq   #0,%d6
        moveb   TRACKB,%d6
        moveq   #0,%d0
        moveb   PARTB,%d0
        movel   #6322,%d1
        mulu.l  %d1,%d0
        movel   DBPTR,%d7
        addl    %d0,%d7
        moveq   #6,%d0
        cmpl    %d3,%d0
        bgt     xp1                     | slot < 6 -> page 1
        | ---- page 2 ----
        | select record for this slot: a6 = engine's table, a5 = rec or 0
        movel   %d7,%a0
        addal   #IDOFF,%a0
        addal   %d6,%a0
        moveq   #0,%d0
        moveb   %a0@,%d0
        lea     VERBSEL,%a6
        moveq   #6,%d1
        cmpl    %d0,%d1
        bne.s   x1
        lea     DLYSEL,%a6
x1:     movel   %a6@(0,%d3:l:4),%a5
        | a2 = &Part[slot] = DB+part*6322 + 0x8ef5a + track*30 + 18 + slot
        movel   %d6,%d0
        moveq   #30,%d1
        mulu.l  %d1,%d0
        movel   %d7,%a2
        addal   #P2OFF,%a2
        addal   %d0,%a2
        addal   #18,%a2
        addal   %d3,%a2
        moveq   #0,%d4
        moveb   %a2@,%d4                | d4 = value BEFORE the edit
        moveq   #4,%d0
        movel   %d0,PAGEGLOB
        movel   %d3,%d2
        subq.l  #6,%d2                  | d2 = slot within page 2
        movel   %d5,%sp@-
        movel   %d2,%sp@-
        jsr     P2EDIT                  | the editor: all its stores + dirty bits
        addql   #8,%sp
        | The editor clamps against whatever descriptor its page table holds,
        | which this screen never stages -- so its clamp is STALE (it squashed
        | GATE/DRV to 0..3 and ramped selects to 127). Never trust it: set the
        | value ourselves for EVERY page-2 slot, count = 128 for a knob or the
        | select record's count. new = clamp(before + delta, 0..count-1) into
        | Part, the live byte the DSP frame reads, and the working mirror.
        movel   %a5,%d1
        beq.s   xknob
        movel   %a5@,%d1                | a select: its count
        bra.s   xcnt
xknob:  movel   #128,%d1                | a knob: 0..127
xcnt:   subql   #1,%d1                  | count-1
        movel   %d4,%d0
        addl    %d5,%d0
        cmpl    %d1,%d0
        ble.s   x2
        movel   %d1,%d0
x2:     tstl    %d0
        bge.s   x3
        moveq   #0,%d0
x3:     moveb   %d0,%a2@                | Part (what the screen reads/saves)
        lea     0x80000950,%a0
        moveb   %d0,%a0@(0,%d2:l)       | live byte the DSP frame reads
        lea     0x100a5138,%a0
        moveb   %d0,%a0@(0,%d2:l)       | working mirror
        bra     xdone
xp1:    movel   %d6,%d0
        moveq   #24,%d1
        mulu.l  %d1,%d0
        movel   %d7,%a0
        addal   #P1OFF,%a0
        addal   %d0,%a0
        addal   #18,%a0
        addal   %d3,%a0
        moveq   #0,%d0
        moveb   %a0@,%d0
        addl    %d5,%d0
        bge.s   xp2
        moveq   #0,%d0
xp2:    moveq   #127,%d1
        cmpl    %d0,%d1
        bge.s   xp3
        movel   %d1,%d0
xp3:    movel   %d3,%d1
        addl    #24,%d1
        movel   %d0,%sp@-
        movel   %d1,%sp@-
        movel   %d6,%sp@-
        jsr     P1WRITE
        lea     %sp@(12),%sp
xdone:  movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts
