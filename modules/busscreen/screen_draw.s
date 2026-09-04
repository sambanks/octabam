| BUS SCREEN handlers -- two pages of six, cursor + level knob (the native OT
| effect-setup idiom: the stock EFFECT 2 SETUP encoder handler also acts only
| on the level encoder and edits the selected row; physical-encoder-per-param
| is a main-page feature menu states do not receive).
|
| PAGE (0/1) and CURSOR (0..5) select the visible slot = PAGE*6 + CURSOR.
| The draw shows six rows for PAGE; up/down move the cursor and CARRY ACROSS
| the page boundary (down past row 5 -> page 2 row 0; up past row 0 -> page 1
| row 5), so all twelve navigate with no scroll and no page key. Two CONTROL
| rows, REVERB and DELAY, each scan the per-track FX2 ids for their engine,
| select that track, and open the screen; the label set then follows the id.
|
|   value arrays (same as the writers, so edit is visible):
|     page 1 (slot 0..5):  DB + part*6322 + 0x8ee9a + track*24 + 18 + slot
|     page 2 (slot 6..11): DB + part*6322 + 0x8ef5a + track*30 + 18 + slot
|   DRAW_STRING(context, window, x, y, flags, string) @ 0x40012bd8
|   sprintf(buf, fmt, arg)                            @ 0x40013a08
|   0x40054cd8(track, flat, value)  page-1 writer; 0x4003a474(slot2, delta) page-2
|
| Self-refs the build patches (0x40bad000..18): VERBTAB DLYTAB FMT SCRATCH
| CURSOR GT PAGE.

        .set    VERBTAB, 0x40bad000
        .set    DLYTAB,  0x40bad004
        .set    FMT,     0x40bad008
        .set    SCRATCH, 0x40bad00c
        .set    CURSOR,  0x40bad010
        .set    GT,      0x40bad014
        .set    PAGE,    0x40bad018
        .set    VERBSEL, 0x40bad01c    | per-slot select records, verb
        .set    DLYSEL,  0x40bad020    | per-slot select records, delay
        .set    DRAW_STRING, 0x40012bd8
        .set    SPRINTF, 0x40013a08
        .set    P1WRITE, 0x40054cd8
        .set    P2EDIT,  0x4003a474
        .set    PAGEGLOB, 0x460d5c30
        .set    CONTEXT, 0x400ba876
        .set    DBPTR,   0x46c82456
        .set    PARTB,   0x80000003
        .set    TRACKB,  0x80000000
        .set    IDBASE,  0x80000ecc         | per-track FX2 ids (8 bytes)
        .set    STATEG,  0x400cbf40
        .set    VIEWG,   0x400cbd9c
        .set    P1OFF,   0x8ee9a
        .set    P2OFF,   0x8ef5a
        .set    IDOFF,   0x8ed88
        .set    PGROWS, 6

        .text
| ---- draw(window) --------------------------------------------------------
draw:   lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        moveal  %sp@(48),%a4
        tstl    %a4
        beq     ddone
        movel   DBPTR,%d7
        beq     ddone
        moveq   #0,%d0
        moveb   PARTB,%d0
        movel   #6322,%d1
        mulu.l  %d1,%d0
        addl    %d0,%d7                 | DB + part*6322
        moveq   #0,%d6
        moveb   TRACKB,%d6              | track
        movel   %d7,%a0
        addal   #IDOFF,%a0
        addal   %d6,%a0
        moveq   #0,%d0
        moveb   %a0@,%d0
        lea     VERBTAB,%a5
        lea     VERBSEL,%a6
        moveq   #6,%d1
        cmpl    %d0,%d1
        bne.s   1f
        lea     DLYTAB,%a5
        lea     DLYSEL,%a6
1:      | page-1 base -> a3 (a3 + slot), page-2 base -> a2 (a2 + slot)
        movel   %d6,%d0
        moveq   #24,%d1
        mulu.l  %d1,%d0
        movel   %d7,%a3
        addal   #P1OFF,%a3
        addal   %d0,%a3
        addal   #18,%a3
        movel   %d6,%d0
        moveq   #30,%d1
        mulu.l  %d1,%d0
        movel   %d7,%a2
        addal   #P2OFF,%a2
        addal   %d0,%a2
        addal   #18,%a2
        | base slot for this page = PAGE*6
        movel   PAGE,%d7                | reuse d7 = page
        moveq   #6,%d0
        muls.l  %d0,%d7                 | d7 = PAGE*6
        moveq   #0,%d3                  | row 0..5
dloop:  movel   %d3,%d4
        lsll    #3,%d4
        addql   #8,%d4                  | y = 8 + row*8
        movel   %d3,%d5
        addl    %d7,%d5                 | slot = PAGE*6 + row
        | cursor marker
        movel   CURSOR,%d0
        cmpl    %d3,%d0
        bne.s   2f
        pea     GT
        pea     0xffffffff
        movel   %d4,%sp@-
        pea     1
        movel   %a4,%sp@-
        pea     CONTEXT
        jsr     DRAW_STRING
        lea     %sp@(24),%sp
2:      | name at x=10 (a5[slot*4])
        movel   %a5@(0,%d5:l:4),%d2
        movel   %d2,%sp@-
        pea     0xffffffff
        movel   %d4,%sp@-
        pea     10
        movel   %a4,%sp@-
        pea     CONTEXT
        jsr     DRAW_STRING
        lea     %sp@(24),%sp
        | value at x=54: raw byte from page-1 or page-2 array
        moveq   #0,%d0
        moveq   #6,%d1
        cmpl    %d5,%d1
        bgt.s   3f
        moveb   %a2@(0,%d5:l),%d0
        bra.s   4f
3:      moveb   %a3@(0,%d5:l),%d0
4:      | select? a6[slot] is a record {count, labelptr...} or 0 for a knob
        movel   %a6@(0,%d5:l:4),%a1
        movel   %a1,%d1
        beq.s   5f                      | 0 -> plain number
        | clamp value to count-1, fetch the label
        movel   %a1@,%d1                | count
        subql   #1,%d1                  | max index
        cmpl    %d1,%d0
        ble.s   6f
        movel   %d1,%d0                 | clamp high
6:      tstl    %d0
        bge.s   7f
        moveq   #0,%d0                  | clamp low
7:      movel   %a1@(4,%d0:l:4),%d2     | label pointer
        bra.s   8f
5:      | plain number: sprintf %d into SCRATCH
        movel   %d0,%sp@-
        pea     FMT
        pea     SCRATCH
        jsr     SPRINTF
        lea     %sp@(12),%sp
        movel   #SCRATCH,%d2
8:      | draw d2 (label or number) at x=54
        movel   %d3,%d4
        lsll    #3,%d4
        addql   #8,%d4
        movel   %d2,%sp@-
        pea     0xffffffff
        movel   %d4,%sp@-
        pea     54
        movel   %a4,%sp@-
        pea     CONTEXT
        jsr     DRAW_STRING
        lea     %sp@(24),%sp
        addql   #1,%d3
        moveq   #PGROWS,%d0
        cmpl    %d3,%d0
        bgt     dloop
ddone:  movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| ---- key(keycode): up/down move the cursor, crossing pages ----------------
| The physical arrows are position-dependent (Sam: LEFT=0x33, UP=0x34). To be
| robust to which code DOWN/RIGHT send, UP is 0x33 OR 0x34 and DOWN is 0x35 OR
| 0x36 -- so the UP arrow moves up and the DOWN arrow moves down whichever of
| the pair it is, with left/right as bonus up/down.
key:    movel   %sp@(4),%d0
        movel   CURSOR,%d1
        movel   PAGE,%d2
        | is it an UP key (0x33 or 0x34)?
        moveq   #0x33,%d3
        cmpl    %d0,%d3
        beq.s   kup
        moveq   #0x34,%d3
        cmpl    %d0,%d3
        beq.s   kup
        | a DOWN key (0x35 or 0x36)?
        moveq   #0x35,%d3
        cmpl    %d0,%d3
        beq.s   kdn
        moveq   #0x36,%d3
        cmpl    %d0,%d3
        beq.s   kdn
        bra.s   kdone
kup:    tstl    %d1
        beq.s   kup0
        subql   #1,%d1
        bra.s   kstore
kup0:   tstl    %d2
        beq.s   kdone
        subql   #1,%d2
        moveq   #PGROWS-1,%d1
        bra.s   kstore
kdn:    moveq   #PGROWS-1,%d3
        cmpl    %d1,%d3
        beq.s   kdn5
        addql   #1,%d1
        bra.s   kstore
kdn5:   moveq   #1,%d3
        cmpl    %d2,%d3
        beq.s   kdone
        addql   #1,%d2
        moveq   #0,%d1
kstore: movel   %d1,CURSOR
        movel   %d2,PAGE
kdone:  rts

| ---- enter actions: select the host track, open the screen ----------------
enter_rev: moveq  #7,%d0               | BusVerb id
        bra.s   ecom
enter_dly: moveq  #6,%d0               | BusDelay id
ecom:   lea     IDBASE,%a0
        moveq   #0,%d1                  | track
esc:    moveb   %a0@+,%d2
        andl    #0xff,%d2
        cmpl    %d0,%d2
        beq.s   efound
        addql   #1,%d1
        moveq   #8,%d2
        cmpl    %d1,%d2
        bgt.s   esc
        bra.s   eopen                   | not hosted: leave track as-is
efound: moveb   %d1,TRACKB              | select the host track
eopen:  moveq   #0,%d0
        movel   %d0,CURSOR
        movel   %d0,PAGE
        moveq   #16,%d0
        movel   %d0,STATEG
        moveq   #13,%d0
        movel   %d0,VIEWG
        rts

| ---- enc(index, delta): edit the visible slot ----------------------------
enc:    lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        movel   %sp@(52),%d5            | delta
        movel   PAGE,%d3
        moveq   #6,%d0
        muls.l  %d0,%d3
        movel   CURSOR,%d0
        addl    %d0,%d3                 | slot = PAGE*6 + CURSOR
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
        bgt.s   xp1                     | slot < 6 -> page 1
        moveq   #4,%d0
        movel   %d0,PAGEGLOB
        movel   %d3,%d0
        subq.l  #6,%d0
        movel   %d5,%sp@-
        movel   %d0,%sp@-
        jsr     P2EDIT
        addql   #8,%sp
        bra.s   xdone
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
