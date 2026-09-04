| BUS SCREEN handlers (step 4a) -- draw with a cursor highlight, and a key
| handler that moves the cursor.
|
| Two entry points, both members of the 17th menu-state entry:
|   draw(window_handle)  -- window at sp@(48) after the 11-register prologue
|   key(keycode)         -- keycode at sp@(12) after the 2-register prologue
|
| CURSOR is a word in the cave (0..11), the selected row. The draw prefixes a
| ">" on that row; the key handler moves it: 0x33 up, 0x34 down (the pair the
| stock tree handler at 0x40064e64 treats specially), clamped 0..11. The exact
| panel up/down keycodes and the [NO]/exit key are confirmed on the flash;
| the handler LOGIC is what the emulator proves here.
|
|   DRAW_STRING(context, window, x, y, flags, string)   @ 0x40012bd8
|   sprintf(buf, fmt, arg)                              @ 0x40013a08
|
| Self-references the build patches (placeholders 0x40bad000..14):
|   VERBTAB DLYTAB FMT SCRATCH CURSOR GT (the ">" glyph string).

        .set    VERBTAB, 0x40bad000
        .set    DLYTAB,  0x40bad004
        .set    FMT,     0x40bad008
        .set    SCRATCH, 0x40bad00c
        .set    CURSOR,  0x40bad010
        .set    GT,      0x40bad014
        .set    DRAW_STRING, 0x40012bd8
        .set    SPRINTF, 0x40013a08
        .set    CONTEXT, 0x400ba876
        .set    DBPTR,   0x46c82456
        .set    PARTB,   0x80000003
        .set    TRACKB,  0x80000000
        .set    VALOFF,  0x8f084
        .set    IDOFF,   0x8ed88
        .set    NROWS, 12

        .text
| ---- draw(window) --------------------------------------------------------
draw:   lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@     | 11 regs -> arg at sp@(48)
        moveal  %sp@(48),%a4
        tstl    %a4
        beq     ddone
        movel   DBPTR,%d7
        beq     ddone
        moveq   #0,%d0
        moveb   PARTB,%d0
        movel   #6322,%d1
        mulu.l  %d1,%d0
        addl    %d0,%d7                  | d7 = DB + part*6322
        moveq   #0,%d6
        moveb   TRACKB,%d6               | d6 = track
        movel   %d7,%a0
        addal   #IDOFF,%a0
        addal   %d6,%a0
        moveq   #0,%d0
        moveb   %a0@,%d0                 | FX2 id
        lea     VERBTAB,%a5
        moveq   #6,%d1
        cmpl    %d0,%d1
        bne.s   1f
        lea     DLYTAB,%a5
1:      movel   %d6,%d0
        moveq   #30,%d1
        mulu.l  %d1,%d0
        movel   %d7,%a3
        addal   #VALOFF,%a3
        addal   %d0,%a3                  | a3 = &value[0] for this track
        moveq   #0,%d3                   | slot 0..11
dloop:  movel   %d3,%d4
        lsll    #3,%d4
        addql   #8,%d4                   | y = 8 + slot*8
        | cursor marker on the selected row
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
        | value at x=54
        moveq   #0,%d0
        moveb   %a3@(0,%d3:l),%d0
        movel   %d0,%sp@-
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
key:    movel   %sp@(4),%d0              | keycode
        movel   CURSOR,%d1
        moveq   #0x33,%d2                | up
        cmpl    %d0,%d2
        bne.s   3f
        tstl    %d1
        beq.s   kdone
        subql   #1,%d1
        bra.s   kstore
3:      moveq   #0x34,%d2                | down
        cmpl    %d0,%d2
        bne.s   kdone
        moveq   #NROWS-1,%d2
        cmpl    %d1,%d2
        beq.s   kdone
        addql   #1,%d1
kstore: movel   %d1,CURSOR
kdone:  rts

| ---- enter() -- a CONTROL row action: show the screen ---------------------
| Called as action(0) from the id-0 row path. Sets the menu state to ours and
| a full viewport, then returns; the menu loop redraws, landing on state 16.
| (State 16 is past the id-path's 1..15 bounds check, so a row's id cannot
| reach it -- the action-fn path is the only way in, docs/MAINMENU.md 7.)
enter:  moveq   #16,%d0
        movel   %d0,0x400cbf40          | MENU_STATE = our state
        moveq   #13,%d0
        movel   %d0,0x400cbd9c          | MENU_VIEWPORT = show all rows
        rts
