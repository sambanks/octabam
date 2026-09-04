| BUS SCREEN handlers -- double-wide (two columns of six), cursor + level
| knob, plus a 13th RETURN row when the master hosts the Character station.
|
|   left column  = slots 0..5:  name x=3,  value x=32,  bar x 2..58
|   right column = slots 6..11: name x=61, value x=90,  bar x 60..116
|   row = slot mod 6, stock pitch: bar_y = 4 + row*7, text at bar_y+1; the
|   cursor row is an INVERTED BAR (0x40012254) drawn after its text.
|   slot 12 (row 6, left) = the bus's RETURN LEVEL at the master, T8's FX1
|   Character in BUS mode: RVRB = its CRSH (page 1 slot 2), DLY = its RING
|   (page 2 index 2). Present only when T8's FX1 id is CHARACTER (0x1c);
|   NSLOT (12 or 13) is set on enter and bounds the cursor and the draw.
|
| Values live in the Part arrays the writers use:
|   page 1: DB + part*6322 + 0x8ee9a + track*24 + 18 + slot
|   page 2: DB + part*6322 + 0x8ef5a + track*30 + 18 + slot
|   RVRB:   DB + part*6322 + 0x8ef50   (T8 FX1 p1 slot 2 = flat 20)
|   DLY:    DB + part*6322 + 0x8f040   (T8 FX1 p2 idx 2; live 0x80000a2a,
|                                        mirror 0x100a518e -- traced 4 Sep)
| Edits: page 1 via 0x40054cd8(track, flat, value); page 2 via 0x4003a474
| then the value set here, count-clamped (its clamp is stale outside a staged
| page, docs/MAINMENU.md 9c-ii). Keys: 0x34 up, 0x33 down (the key that goes
| down on this unit), 0x32/35/36 also down; wraps.
| Self-refs patched by the build (0x40bad000..24): VERBTAB DLYTAB FMT SCRATCH
| CURSOR VERBSEL DLYSEL RVRBSTR DLYSTR NSLOT.

        .set    VERBTAB, 0x40bad000
        .set    DLYTAB,  0x40bad004
        .set    FMT,     0x40bad008
        .set    SCRATCH, 0x40bad00c
        .set    CURSOR,  0x40bad010
        .set    VERBSEL, 0x40bad014
        .set    DLYSEL,  0x40bad018
        .set    RVRBSTR, 0x40bad01c
        .set    DLYSTR,  0x40bad020
        .set    NSLOT,   0x40bad024
        .set    DRAW_STRING, 0x40012bd8
        .set    INVERT,  0x40012254
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
        .set    FX1IDOFF, 0x8ed80
        .set    RVRBOFF, 0x8ef50
        .set    DLYOFF,  0x8f040
        .set    DLYLIVE, 0x80000a2a
        .set    DLYMIRR, 0x100a518e
        .set    CHARID,  0x1c
        .set    MASTER,  7

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
1:      movel   %d1,%d2
        moveq   #24,%d3
        mulu.l  %d3,%d2
        movel   %d0,%a3
        addal   #P1OFF,%a3
        addal   %d2,%a3
        addal   #18,%a3                 | a3 + slot, slots 0..5
        movel   %d1,%d2
        moveq   #30,%d3
        mulu.l  %d3,%d2
        movel   %d0,%a2
        addal   #P2OFF,%a2
        addal   %d2,%a2
        addal   #18,%a2                 | a2 + slot, slots 6..11
        moveq   #0,%d3
dloop:  moveq   #12,%d0
        cmpl    %d3,%d0
        beq     dret                    | slot 12: the return row
        moveq   #6,%d0
        movel   %d3,%d4
        cmpl    %d3,%d0
        bgt.s   dleft
        subql   #6,%d4
        moveq   #61,%d6
        moveq   #90,%d7
        bra.s   drow
dleft:  moveq   #3,%d6
        moveq   #32,%d7
drow:   movel   %d4,%d5
        moveq   #7,%d0
        muls.l  %d0,%d5
        addql   #4,%d5                  | bar_y
        movel   %a5@(0,%d3:l:4),%d2     | name
        bsr     dtext                   | draw d2 at (d6, bar_y+1)
        moveq   #0,%d0
        moveq   #6,%d1
        cmpl    %d3,%d1
        bgt.s   dp1
        moveb   %a2@(0,%d3:l),%d0
        bra.s   dsel
dp1:    moveb   %a3@(0,%d3:l),%d0
dsel:   movel   %a6@(0,%d3:l:4),%a1
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
dgl:    movel   %a1@(4,%d0:l:4),%d2
        bra.s   ddv
dnum:   bsr     dfmt                    | d0 -> SCRATCH, d2 = SCRATCH
ddv:    bsr     dvalue                  | draw d2 at (d7, bar_y+1)
        bsr     dbar                    | invert the bar if cursor == d3
dnext:  addql   #1,%d3
        movel   NSLOT,%d0
        cmpl    %d3,%d0
        bgt     dloop
        bra     ddone
dret:   | the return row: row 6, left column
        moveq   #6,%d4
        moveq   #3,%d6
        moveq   #32,%d7
        movel   %d4,%d5
        moveq   #7,%d0
        muls.l  %d0,%d5
        addql   #4,%d5
        movel   #RVRBSTR,%d2
        cmpal   #VERBTAB,%a5
        beq.s   2f
        movel   #DLYSTR,%d2
2:      bsr     dtext
        | value: DB + part*6322 + (RVRBOFF | DLYOFF)
        movel   DBPTR,%d0
        moveq   #0,%d1
        moveb   PARTB,%d1
        movel   #6322,%d2
        mulu.l  %d2,%d1
        addl    %d1,%d0
        movel   %d0,%a0
        cmpal   #VERBTAB,%a5
        bne.s   3f
        addal   #RVRBOFF,%a0
        bra.s   4f
3:      addal   #DLYOFF,%a0
4:      moveq   #0,%d0
        moveb   %a0@,%d0
        bsr     dfmt
        bsr     dvalue
        bsr     dbar
        bra     dnext
| helpers (d3-d7/a2-a6 preserved by the firmware calls; d0-d2/a0-a1 scratch)
dtext:  movel   %d5,%d1
        addql   #1,%d1
        movel   %d2,%sp@-
        pea     0xffffffff
        movel   %d1,%sp@-
        movel   %d6,%sp@-
        movel   %a4,%sp@-
        pea     CONTEXT
        jsr     DRAW_STRING
        lea     %sp@(24),%sp
        rts
dvalue: movel   %d5,%d1
        addql   #1,%d1
        movel   %d2,%sp@-
        pea     0xffffffff
        movel   %d1,%sp@-
        movel   %d7,%sp@-
        movel   %a4,%sp@-
        pea     CONTEXT
        jsr     DRAW_STRING
        lea     %sp@(24),%sp
        rts
dfmt:   movel   %d0,%sp@-
        pea     FMT
        pea     SCRATCH
        jsr     SPRINTF
        lea     %sp@(12),%sp
        movel   #SCRATCH,%d2
        rts
dbar:   movel   CURSOR,%d0
        cmpl    %d3,%d0
        bne.s   5f
        pea     0xffffffff
        movel   %d5,%d1
        addql   #6,%d1
        movel   %d1,%sp@-
        movel   %d7,%d1
        addl    #26,%d1
        movel   %d1,%sp@-
        movel   %d5,%sp@-
        movel   %d6,%d1
        subql   #1,%d1
        movel   %d1,%sp@-
        movel   %a4,%sp@-
        jsr     INVERT
        lea     %sp@(24),%sp
5:      rts
ddone:  movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| ---- key(keycode): up/down through 0..NSLOT-1, wrapping --------------------
key:    movel   %sp@(4),%d0
        movel   CURSOR,%d1
        moveq   #0x34,%d2
        cmpl    %d0,%d2
        beq.s   kup
        moveq   #0x33,%d2
        cmpl    %d0,%d2
        beq.s   kdn
        moveq   #0x32,%d2
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
        movel   NSLOT,%d1
kup1:   subql   #1,%d1
        bra.s   kstore
kdn:    movel   NSLOT,%d2
        subql   #1,%d2
        cmpl    %d1,%d2
        bne.s   kdn1
        moveq   #0,%d1
        bra.s   kstore
kdn1:   addql   #1,%d1
kstore: movel   %d1,CURSOR
kdone:  rts

| ---- enter actions: select the host track, size the screen, open ---------
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
eopen:  | NSLOT = 13 if T8's FX1 is the Character station, else 12
        movel   DBPTR,%d0
        moveq   #0,%d1
        moveb   PARTB,%d1
        movel   #6322,%d2
        mulu.l  %d2,%d1
        addl    %d1,%d0
        movel   %d0,%a0
        addal   #FX1IDOFF,%a0
        addal   #MASTER,%a0
        moveq   #0,%d1
        moveb   %a0@,%d1
        moveq   #12,%d0
        moveq   #CHARID,%d2
        cmpl    %d1,%d2
        bne.s   6f
        moveq   #13,%d0
6:      movel   %d0,NSLOT
        moveq   #0,%d0
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
        movel   CURSOR,%d3              | slot
        moveq   #0,%d6
        moveb   TRACKB,%d6              | host track
        moveq   #0,%d0
        moveb   PARTB,%d0
        movel   #6322,%d1
        mulu.l  %d1,%d0
        movel   DBPTR,%d7
        addl    %d0,%d7                 | d7 = DB + part*6322
        moveq   #12,%d0
        cmpl    %d3,%d0
        beq     eret                    | the return row
        moveq   #6,%d0
        cmpl    %d3,%d0
        bgt     xp1                     | slot < 6 -> page 1
        | ---- page 2: the editor, then the value set here -----------------
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
        movel   %d6,%d0
        moveq   #30,%d1
        mulu.l  %d1,%d0
        movel   %d7,%a2
        addal   #P2OFF,%a2
        addal   %d0,%a2
        addal   #18,%a2
        addal   %d3,%a2
        moveq   #0,%d4
        moveb   %a2@,%d4                | before
        moveq   #4,%d0
        movel   %d0,PAGEGLOB
        movel   %d3,%d2
        subq.l  #6,%d2
        movel   %d5,%sp@-
        movel   %d2,%sp@-
        jsr     P2EDIT
        addql   #8,%sp
        movel   %a5,%d1
        beq.s   xknob
        movel   %a5@,%d1
        bra.s   xcnt
xknob:  movel   #128,%d1
xcnt:   subql   #1,%d1
        movel   %d4,%d0
        addl    %d5,%d0
        cmpl    %d1,%d0
        ble.s   x2
        movel   %d1,%d0
x2:     tstl    %d0
        bge.s   x3
        moveq   #0,%d0
x3:     moveb   %d0,%a2@
        lea     0x80000950,%a0
        moveb   %d0,%a0@(0,%d2:l)
        lea     0x100a5138,%a0
        moveb   %d0,%a0@(0,%d2:l)
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
        bra     xdone
eret:   | which engine? the host's FX2 id
        movel   %d7,%a0
        addal   #IDOFF,%a0
        addal   %d6,%a0
        moveq   #0,%d0
        moveb   %a0@,%d0
        moveq   #6,%d1
        cmpl    %d0,%d1
        beq.s   edly
        | RVRB: T8 FX1 page-1 slot 2 = flat 20, the self-contained writer
        movel   %d7,%a0
        addal   #RVRBOFF,%a0
        moveq   #0,%d0
        moveb   %a0@,%d0
        addl    %d5,%d0
        bge.s   7f
        moveq   #0,%d0
7:      moveq   #127,%d1
        cmpl    %d0,%d1
        bge.s   8f
        movel   %d1,%d0
8:      movel   %d0,%sp@-
        pea     20
        pea     MASTER
        jsr     P1WRITE
        lea     %sp@(12),%sp
        bra     xdone
edly:   | DLY: T8 FX1 page-2 idx 2 -- the editor on (track 7, page 3), then
        | the value set here into its Part, live and mirror bytes
        movel   %d7,%a2
        addal   #DLYOFF,%a2
        moveq   #0,%d4
        moveb   %a2@,%d4                | before
        moveq   #MASTER,%d0
        moveb   %d0,TRACKB              | the editor keys off the track global
        moveq   #3,%d0
        movel   %d0,PAGEGLOB            | page kind 3 = FX1
        movel   %d5,%sp@-
        pea     2
        jsr     P2EDIT
        addql   #8,%sp
        moveb   %d6,TRACKB              | back to the host track
        movel   %d4,%d0
        addl    %d5,%d0
        bge.s   9f
        moveq   #0,%d0
9:      moveq   #127,%d1
        cmpl    %d0,%d1
        bge.s   10f
        movel   %d1,%d0
10:     moveb   %d0,%a2@
        lea     DLYLIVE,%a0
        moveb   %d0,%a0@
        lea     DLYMIRR,%a0
        moveb   %d0,%a0@
xdone:  movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts
