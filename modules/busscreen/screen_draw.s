| BUS SCREEN handlers -- draw (name + live value, cursor), key (move cursor),
| enter (a CONTROL row action), enc (edit the cursor row).
|
| VALUES live in the Part, in the arrays the firmware writers use, so the draw
| and the edit stay consistent by construction:
|   page 1 (rows 0..5):  DB + part*6322 + 0x8ee9a + track*24 + 18 + slot
|   page 2 (rows 6..11): DB + part*6322 + 0x8ef5a + track*30 + 24 + (slot-6)
| DB = *0x46c82456, part = byte 0x80000003, track = byte 0x80000000 -- the
| pair the page-2 editor 0x4003a474 itself keys off.
|
|   DRAW_STRING(context, window, x, y, flags, string)   @ 0x40012bd8
|   sprintf(buf, fmt, arg)                              @ 0x40013a08
|   0x40054cd8(track, flat, value)  -- page-1 writer, self-contained
|   0x4003a474(slot2, delta)        -- page-2 editor (flash question, 9c-ii)
|
| Self-references the build patches (0x40bad000..14): VERBTAB DLYTAB FMT
| SCRATCH CURSOR GT.

        .set    VERBTAB, 0x40bad000
        .set    DLYTAB,  0x40bad004
        .set    FMT,     0x40bad008
        .set    SCRATCH, 0x40bad00c
        .set    CURSOR,  0x40bad010
        .set    GT,      0x40bad014
        .set    DRAW_STRING, 0x40012bd8
        .set    SPRINTF, 0x40013a08
        .set    P1WRITE, 0x40054cd8
        .set    P2EDIT,  0x4003a474
        .set    PAGEGLOB, 0x460d5c30
        .set    CONTEXT, 0x400ba876
        .set    DBPTR,   0x46c82456
        .set    PARTB,   0x80000003
        .set    TRACKB,  0x80000000
        .set    P1OFF,   0x8ee9a
        .set    P2OFF,   0x8ef5a
        .set    IDOFF,   0x8ed88
        .set    NROWS, 12

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
        addl    %d0,%d7                 | d7 = DB + part*6322
        moveq   #0,%d6
        moveb   TRACKB,%d6              | track
        | label table by FX2 id
        movel   %d7,%a0
        addal   #IDOFF,%a0
        addal   %d6,%a0
        moveq   #0,%d0
        moveb   %a0@,%d0
        lea     VERBTAB,%a5
        moveq   #6,%d1
        cmpl    %d0,%d1
        bne.s   1f
        lea     DLYTAB,%a5
1:      | page-1 value base -> a3
        movel   %d6,%d0
        moveq   #24,%d1
        mulu.l  %d1,%d0
        movel   %d7,%a3
        addal   #P1OFF,%a3
        addal   %d0,%a3
        addal   #18,%a3                 | a3+slot (slot 0..5)
        | page-2 value base -> a2  (a2 + slot for slot 6..11)
        movel   %d6,%d0
        moveq   #30,%d1
        mulu.l  %d1,%d0
        movel   %d7,%a2
        addal   #P2OFF,%a2
        addal   %d0,%a2
        addal   #18,%a2                 | +24-6 = +18
        moveq   #0,%d3
dloop:  movel   %d3,%d4
        lsll    #3,%d4
        addql   #8,%d4                  | y = 8 + slot*8
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
2:      | name at x=10
        movel   %a5@(0,%d3:l:4),%d2
        movel   %d2,%sp@-
        pea     0xffffffff
        movel   %d4,%sp@-
        pea     10
        movel   %a4,%sp@-
        pea     CONTEXT
        jsr     DRAW_STRING
        lea     %sp@(24),%sp
        | value at x=54: choose page-1 or page-2 array by slot
        moveq   #0,%d0
        moveq   #6,%d1
        cmpl    %d3,%d1
        bgt.s   3f
        moveb   %a2@(0,%d3:l),%d0       | page-2 value
        bra.s   4f
3:      moveb   %a3@(0,%d3:l),%d0       | page-1 value
4:      movel   %d0,%sp@-
        pea     FMT
        pea     SCRATCH
        jsr     SPRINTF
        lea     %sp@(12),%sp
        movel   %d3,%d4
        lsll    #3,%d4
        addql   #8,%d4
        pea     SCRATCH
        pea     0xffffffff
        movel   %d4,%sp@-
        pea     54
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

| ---- key(keycode) --------------------------------------------------------
key:    movel   %sp@(4),%d0
        movel   CURSOR,%d1
        moveq   #0x33,%d2
        cmpl    %d0,%d2
        bne.s   3f
        tstl    %d1
        beq.s   kdone
        subql   #1,%d1
        bra.s   kstore
3:      moveq   #0x34,%d2
        cmpl    %d0,%d2
        bne.s   kdone
        moveq   #NROWS-1,%d2
        cmpl    %d1,%d2
        beq.s   kdone
        addql   #1,%d1
kstore: movel   %d1,CURSOR
kdone:  rts

| ---- enter() -- a CONTROL row action -------------------------------------
enter:  moveq   #16,%d0
        movel   %d0,0x400cbf40          | MENU_STATE
        moveq   #13,%d0
        movel   %d0,0x400cbd9c          | MENU_VIEWPORT
        rts

| ---- enc(index, delta) -- edit the cursor row ----------------------------
enc:    lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        movel   %sp@(52),%d5            | delta
        movel   CURSOR,%d3              | slot
        moveq   #0,%d6
        moveb   TRACKB,%d6
        moveq   #0,%d0
        moveb   PARTB,%d0
        movel   #6322,%d1
        mulu.l  %d1,%d0
        movel   DBPTR,%d7
        addl    %d0,%d7                 | DB + part*6322
        moveq   #6,%d0
        cmpl    %d3,%d0
        bgt.s   ep1                     | slot < 6 -> page 1
        | ---- page 2 (flash question) ----
        moveq   #4,%d0
        movel   %d0,PAGEGLOB
        movel   %d3,%d0
        subq.l  #6,%d0
        movel   %d5,%sp@-
        movel   %d0,%sp@-
        jsr     P2EDIT
        addql   #8,%sp
        bra.s   edone
ep1:    | cur = page1[track*24 + 18 + slot]
        movel   %d6,%d0
        moveq   #24,%d1
        mulu.l  %d1,%d0
        movel   %d7,%a0
        addal   #P1OFF,%a0
        addal   %d0,%a0
        addal   #18,%a0
        addal   %d3,%a0
        moveq   #0,%d0
        moveb   %a0@,%d0
        addl    %d5,%d0                 | + delta
        bge.s   ep2
        moveq   #0,%d0
ep2:    moveq   #127,%d1
        cmpl    %d0,%d1
        bge.s   ep3
        movel   %d1,%d0
ep3:    movel   %d3,%d1
        addl    #24,%d1                 | flat = 24 + slot
        movel   %d0,%sp@-
        movel   %d1,%sp@-
        movel   %d6,%sp@-
        jsr     P1WRITE                 | 0x40054cd8(track, flat, value)
        lea     %sp@(12),%sp
edone:  movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts
