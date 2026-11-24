| TEMPO BUS -- the TEMPO window carries the bus engines' knobs.
|
| The TEMPO key opens the stock TEMPO window at the menu window's size;
| its draw is replaced by a stock-style settings screen: the header
| ("TEMPO 121.2" at the left, then the key: the four arrows, "A" and the
| font's knob glyph; the rule) and two titled boxes, DELAY and REVERB, each
| listing its engine's named parameters with values printed by the
| engine's own formatters. UP/DOWN move the cursor in the focused box; A
| (or B) edits the selected parameter on the host track, LEFT/RIGHT move
| between the boxes, C-F are held while the window is open. LEVEL steps
| whole BPM (the stock handler) and 0.1 BPM while FUNC is held (the step UP/DOWN made in the stock window). YES/NO/
| TEMPO (close) stay the stock window's.
|
| Every drawing call is one the stock CONTROL INPUT and MIDI SYNC screens
| make (0x40065674, 0x4006730c): header text and width, rule, titled
| box, row text at a 7-pixel pitch, the invert bar; the key's dial is the
| parameter pages' (0x400479b4) and its arrows are stock icons. Edits go through the
| firmware's page-1 writer (FX2 flat 24..29) and, for page 2, the FX2
| page-2 editor's stores (CC MAP's write path), then MODE DEFAULTS'
| re-default when that module is in the image. The rows (each engine's
| named slots) come from the manifests, generated per remix (remix.inc).
| engine, getval and setval are helpers.s, linked first.
        .set    WINH,     0x460d16a0   | long: TEMPO window handle, 0 = closed
        .set    SCRDIRTY, 0x46c7c72c   | long: screen refresh request
        .set    CLEAR,    0x40035624   | (surface): the stock TEMPO draw's first call
        .set    FONT,     0x400ba876   | the small UI font
        .set    TEXT,     0x40012bd8   | (font, surf, x, y, limit, str)
        .set    TWIDTH,   0x40012f30   | (font, limit, str) -> pixels
        .set    RULE,     0x40011910   | (surf, x, y, x2, 1)
        .set    BOX,      0x4007efd0   | (surf, x, y, w, h, title, 0, focused)
        .set    INVERT,   0x40012254   | (surf, x1, y1, x2, y2, -1)
        .set    ICON,     0x400128a8   | (icon, surf, x, y)
        .set    ARRUP,    0x400b9d8c   | stock icons, 7 x 5: the up triangle
        .set    ARRDN,    0x400b9da0   | and the down one
        .set    KEYX,     70           | the key's left edge (it ends at x 112)
        .set    SPRINTF,  0x40013a08   | (buf, fmt, ...)
        .set    TEMPOGET, 0x4009c5f4   | (&whole, &tenths)
        .set    LPUSH,    0x40031494   | (layer): register an input layer
        .set    LPOP,     0x4003146c   | (layer): unregister it
        .set    PUSHED,   0x4003171c   | (key): nonzero while that key is held
        .set    KROWS,    0x46100b18   | bytes: the panel's held keys, code = row*8 + bit
        .set    KFUNC,    0x2d         | FUNCTION: row 5, bit 5
        .set    KUP,      0x33
        .set    KREC,     0x29         | STOP is 0x27 (docs/firmware/PANEL.md)
        .set    TSTEP,    0x4004b824   | (whole, tenths): the stock tempo step, redraws
        .set    TLEVEL,   0x4004b918   | (index, delta): the stock LEVEL handler, whole BPM
        .set    P1WRITE,  0x40054cd8   | (track, flat, value): page-1 writer
        .set    LAYERS,   0x460d165c   | long: the input layer list, bottom first
        .set    SCENE_HELD, 0x460d169c | long: 1 = scene A held, 2 = B
        .set    MIDIMODE, 0x80000012   | long: nonzero = the MIDI tracks
        .set    KPUSHB,   0x39         | knob B's push (A's is 0x38)
        | DESC2 (the FX2 descriptor table [id] -> P) comes from remix.inc
        .set    DBPTR,    0x46c82456   | long: Part DB base
        .set    PARTB,    0x80000003   | byte: the current part
        .set    IDOFF,    0x8ed88      | Part: FX2 id per track
        .set    P1OFF,    0x8ee9a      | Part: page-1 values, track*24, FX2 at +18
        .set    P2OFF,    0x8f084      | Part: FX2 page-2 values, track*30
        .set    SHADOW,   0x100a51d2   | FX2 page-2 shadow: +part*6322+track*30+slot2
        .set    LIVEB,    0x80000810   | live block, 72 B per track; FX2 page 2 at +0x38
        .set    CHGBITS,  0x95048      | DB+: |= 1<<part
        .set    MODBITS,  0x100b145e   | byte: |= 1<<part
        .set    CHGFLAG,  0x9b332      | DB+: long = 1
        .set    GCHG,     0x100f8598   | long = 1
        .set    NAMES,    0x16         | P+: twelve 6-byte names
        .set    MINS,     0x6a         | P+: twelve u32 minimums
        .set    COUNTS,   0x9a         | P+: twelve u32 value counts
        .set    FMTS,     0xca         | P+: twelve formatter pointers, 0 = plain
        .set    ROWS,     5            | rows visible per box
        .set    BOXW,     53
        .set    BOXH,     41           | from y 4; 3 px under the rule


        .text
        .globl  tb_open, tb_draw, tb_close

| ---- 0x40059f2c: the TEMPO opener's `jmp 0x4004b528` lands here ----------
| The window exists and the stock layer is registered; ours goes on top.
tb_open:
        pea     TB_LAYER
        jsr     LPUSH
        addql   #4,%sp
        bra.w   tb_draw

| ---- 0x40056930: the TEMPO close, entry replayed after ours comes off -----
tb_close:
        tstl    WINH
        beq.s   1f
        bsr.s   lpop
1:      tstl    WINH
        jmp     0x40056936
lpop:   pea     TB_LAYER
        jsr     LPOP
        addql   #4,%sp
        rts

| ---- encoders: (index, delta). The window gone takes the layer off. ------
tb_enc:
        tstl    WINH
        beq.s   lpop
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        movel   %sp@(48),%d0           | index
        movel   %sp@(52),%d7           | delta
        moveq   #0,%d1
        moveb   FOCUS,%d1              | d1 = box
        lea     SEL,%a2
        addal   %d1,%a2                | a2 = &SEL[box]
        moveq   #1,%d3
        moveb   %d3,TURNED             | a push released after this clears nothing
        cmpl    %d3,%d0
        bhi.w   edone                  | C-F: held
| A, B: the value, x7 while that knob is pushed (the stock fast turn)
        addil   #0x38,%d0              | the knob's push key
        movel   %d0,%sp@-
        jsr     PUSHED
        addql   #4,%sp
        tstl    %d0
        beq.s   1f
        movel   %d7,%d0
        lsll    #3,%d0
        subl    %d7,%d0
        movel   %d0,%d7
1:      moveq   #0,%d1
        moveb   FOCUS,%d1
        moveq   #0,%d0
        moveb   %a2@,%d0
        bsr.w   slotof                 | d6 = slot, or -1
        tstl    %d6
        bmi.s   edone
        movel   %d1,%d0
        jsr     engine                 | d4 = track or -1, a3 = P, a4, d5
        tstl    %d4
        bmi.s   edone
        jsr     getval                 | d2 = value
        movel   %d6,%d0
        lsll    #2,%d0
        movel   %a3@(MINS,%d0:l),%d3   | min
        lea     %a3@(COUNTS),%a0
        movel   %a0@(0,%d0:l),%d1
        addl    %d3,%d1
        subql   #1,%d1                 | max
        movel   %d2,%d0
        addl    %d7,%d0
        cmpl    %d3,%d0
        bge.s   2f
        movel   %d3,%d0
2:      cmpl    %d1,%d0
        ble.s   3f
        movel   %d1,%d0
3:      cmpl    %d2,%d0
        beq.s   edone
        movel   %d0,%d2                | d2 = new value
        clrb    UST                    | an edit ends the paste's undo
        jsr     setval
edone:  movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        bra.w   tb_draw

| ---- the scene keys: (code, down). Stock's press pushes the scene's input
| layer (the key record's sub-map, 0x400bb2a2 for A, 0x400bb2b6 for B) on
| top of this one before the press handler runs (0x40031734), and that
| layer takes every encoder and encoder push for the page underneath: with
| the window open a turn wrote a lock on a knob the window hides. This
| record's press runs stock's (the layers below) and then puts this layer
| back on top, so the window's knobs edit the held scene's locks
| (helpers.s, lockset). The release runs stock's and redraws the values.
tb_scn: movel   %sp@(4),%d0
        moveq   #2,%d1                 | press
        tstl    %sp@(8)
        bne.s   1f
        moveq   #6,%d1                 | release
1:      bsr.w   below
        cmpal   #0,%a0
        beq.s   2f
        movel   %sp@(8),%sp@-
        movel   %sp@(8),%sp@-
        jsr     %a0@
        addql   #8,%sp
2:      tstl    WINH
        beq.s   3f
        tstl    %sp@(8)
        beq.s   4f
        bsr.w   lpop                   | the press: this layer on top again
        pea     TB_LAYER
        jsr     LPUSH
        addql   #4,%sp
4:      bra.w   tb_draw
3:      rts

| ---- encoder pushes: (code, down). With a scene held the scene's layer
| has them (0x4005435c / 0x40053a68: a release with no turn since the press
| clears the lock of the knob under it, on the page the window hides). Here
| a release of A or B with no turn since the press clears the held scene's
| lock on the selected row; C-F and LEVEL do nothing. With no scene held the
| press goes on to the layers below, as before.
tb_push:
        movel   %sp@(4),%d0
        tstl    SCENE_HELD
        beq.s   pbelow
        tstl    MIDIMODE
        bne.s   pbelow
        tstl    %sp@(8)
        beq.s   1f
        moveb   %d0,PUSHK              | the press: remember it, no turn yet
        clrb    TURNED
        rts
1:      moveq   #0,%d1
        moveb   PUSHK,%d1
        cmpl    %d1,%d0
        bne.s   2f
        tstb    TURNED
        bne.s   2f
        moveq   #KPUSHB,%d1
        cmpl    %d1,%d0
        bhi.s   2f                     | C-F, LEVEL
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        moveq   #0,%d1
        moveb   FOCUS,%d1
        moveq   #0,%d0
        lea     SEL,%a0
        moveb   %a0@(0,%d1:l),%d0
        bsr.w   slotof                 | d6 = the selected row's slot
        tstl    %d6
        bmi.s   3f
        movel   %d1,%d0
        jsr     engine                 | d4 = track, a4, d5
        tstl    %d4
        bmi.s   3f
        jsr     lockclr
3:      movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        bra.w   tb_draw
2:      clrb    PUSHK
        rts
pbelow: moveq   #2,%d1
        tstl    %sp@(8)
        bne.s   1f
        moveq   #6,%d1
1:      bsr.s   below
        cmpal   #0,%a0
        beq.s   2f
        movel   %sp@(8),%sp@-
        movel   %sp@(8),%sp@-
        jsr     %a0@
        addql   #8,%sp
2:      rts

| below: d0 = key code, d1 = 2 (press) or 6 (release) -> a0 = the handler
| the layers under this one give that key (the last record naming it whose
| field is not -1), or 0. Walks the list head (bottom) to this layer.
below:  lea     %sp@(-12),%sp
        movem.l %d2/%a1-%a2,%sp@
        suba.l  %a0,%a0
        moveal  LAYERS,%a1
bl1:    cmpal   #0,%a1
        beq.s   blx
        cmpal   #TB_LAYER,%a1
        beq.s   blx
        movel   %a1@(4),%d2
        beq.s   bln
        moveal  %d2,%a2
bl2:    moveq   #0,%d2
        moveb   %a2@,%d2
        cmpil   #0xff,%d2
        beq.s   bln
        cmpl    %d0,%d2
        bne.s   bl3
        movel   %a2@(0,%d1:l),%d2
        moveq   #-1,%d0
        cmpl    %d0,%d2
        beq.s   bl4
        moveal  %d2,%a0
bl4:    moveq   #0,%d0
        moveb   %a2@,%d0               | d0 = the code again
bl3:    lea     %a2@(26),%a2
        bra.s   bl2
bln:    moveal  %a1@,%a1
        bra.s   bl1
blx:    movem.l %sp@,%d2/%a1-%a2
        lea     %sp@(12),%sp
        rts

| ---- FUNC+REC copies the window's values, FUNC+STOP pastes them, and a
| paste again undoes it (the stock copy, paste and undo keys). (code, down).
| The record is in TB_FLAYER, which exists while FUNC is held; with a scene
| held the key does nothing.
| The clipboard is this module's: CLIP, 10 slots a box (2..11, the ones the
| engine names; DEL and REV are the host page's). Copy and paste cover both
| boxes; a box whose engine is on no track of the Part is skipped. The release
| of a key this record took is dropped.
tb_fn:  tstl    %sp@(8)
        beq.w   fnrel
        moveq   #0,%d0
        moveb   KROWS+(KFUNC>>3),%d0
        btst    #(KFUNC&7),%d0
        beq.w   pbelow
        movel   %sp@(4),%d0
        moveb   %d0,FNK
        tstl    SCENE_HELD
        bne.w   fnnop                  | a held scene: nothing to copy
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        cmpil   #KREC,%d0
        bne.s   fnpaste
        lea     CLIP,%a5
        clrb    XDIR
        bsr.w   xfer
        clrb    UST
        bra.s   fnend
fnpaste:
        tstw    CLIP+24
        beq.s   fnend                  | nothing copied
        tstb    UST
        beq.s   fnnew
        moveb   PARTB,%d0
        cmpb    UPART,%d0
        beq.s   fnundo
        clrb    UST                    | the undo is another Part's
fnnew:  lea     UNDO,%a5               | the values the paste replaces
        clrb    XDIR
        bsr.w   xfer
        moveb   PARTB,%d0
        moveb   %d0,UPART
        moveq   #1,%d0
        moveb   %d0,UST
        lea     CLIP,%a5
        moveb   %d0,XDIR
        bsr.w   xfer
        bra.s   fnend
fnundo: lea     UNDO,%a5
        moveq   #1,%d0
        moveb   %d0,XDIR
        bsr.w   xfer
        clrb    UST
fnend:  movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
fnnop:  bra.w   tb_draw
fnrel:  movel   %sp@(4),%d0
        cmpb    FNK,%d0
        bne.w   pbelow
        clrb    FNK
        rts

| xfer: a5 = a 26-byte buffer (12 bytes a box by slot, then a valid byte a
| box). XDIR 0 reads the live values into it, 1 writes it back. MODE (slot 6)
| goes first: MODE DEFAULTS' re-default rewrites the knobs around it.
| setval's page-2 path clobbers a2/d3, so the loop keeps d7 (box), d6 (slot),
| a5 (buffer), a6 (the box's named slots).
xfer:   moveq   #0,%d7
xbox:   tstb    XDIR
        bne.s   1f
        lea     %a5@(24),%a0
        clrb    %a0@(0,%d7:l)          | read: valid once the engine is found
1:      movel   %d7,%d0
        jsr     engine                 | d4 = track or -1, d5 = part, a4
        tstl    %d4
        bmi.s   xnext
        lea     NAMED,%a0
        moveq   #0,%d0
        movew   %a0@(0,%d7:l:2),%d0
        moveal  %d0,%a6
        lea     %a5@(24),%a0
        tstb    XDIR
        bne.s   2f
        moveq   #1,%d0
        moveb   %d0,%a0@(0,%d7:l)
        bra.s   3f
2:      tstb    %a0@(0,%d7:l)
        beq.s   xnext                  | nothing was copied for this box
3:      moveq   #6,%d6
        bsr.s   xslot
        moveq   #2,%d6
xl:     cmpil   #6,%d6
        beq.s   xs
        bsr.s   xslot
xs:     addql   #1,%d6
        cmpil   #12,%d6
        blt.s   xl
xnext:  addql   #1,%d7
        cmpil   #2,%d7
        blt.s   xbox
        rts

| xslot: d6 = slot, d7 = box, a5 = buffer, a6 = the box's named slots;
| d4, d5, a4 from engine.
xslot:  movel   %a6,%d0
        btst    %d6,%d0
        beq.s   xsx
        movel   %d7,%d0
        mulu.w  #12,%d0
        addl    %d6,%d0
        movel   %d0,%sp@-
        tstb    XDIR
        bne.s   xsw
        jsr     getval                 | d2
        movel   %sp@+,%d0
        moveb   %d2,%a5@(0,%d0:l)
        rts
xsw:    movel   %sp@+,%d0
        moveq   #0,%d2
        moveb   %a5@(0,%d0:l),%d2
        jsr     setval
xsx:    rts

| ---- LEFT / RIGHT: the focused box; each box keeps its own cursor ----
tb_lr:  moveq   #0,%d0
        moveq   #0x21,%d1              | RIGHT
        cmpl    %sp@(4),%d1
        bne.s   1f
        moveq   #1,%d0
1:      moveb   %d0,FOCUS
        bra.w   tb_draw

| ---- UP / DOWN: the cursor, one row, held at the box's ends -----------
tb_ud:  movel   %d2,%sp@-
        moveq   #1,%d0
        moveq   #KUP,%d1
        cmpl    %sp@(8),%d1
        bne.s   1f
        moveq   #-1,%d0
1:      moveq   #0,%d1
        moveb   FOCUS,%d1
        lea     SEL,%a1
        addal   %d1,%a1                | a1 = &SEL[box]
        moveq   #0,%d2
        moveb   %a1@,%d2
        addl    %d0,%d2                | the row asked for
        bmi.s   2f                     | above the first: stay
        lea     NV,%a0
        moveq   #0,%d0
        moveb   %a0@(0,%d1:l),%d0
        cmpl    %d0,%d2
        bge.s   2f                     | past the last: stay
        moveb   %d2,%a1@
2:      movel   %sp@+,%d2
        bra.w   tb_draw

| ---- LEVEL: whole BPM (stock); 0.1 BPM while FUNC is held -------------
tb_lvl: moveq   #0,%d0
        moveb   KROWS+(KFUNC>>3),%d0
        btst    #(KFUNC&7),%d0
        bne.s   1f
        jmp     TLEVEL
1:      movel   %sp@(8),%sp@-          | tenths = delta
        clrl    %sp@-                  | whole = 0
        jsr     TSTEP
        addql   #8,%sp
        rts

| ---- slotof: d1 = box, d0 = row -> d6 = the row's slot, -1 past the end.
| The rows are the ones the last draw listed (VIS, NV).
slotof: moveq   #-1,%d6
        lea     NV,%a0
        cmpb    %a0@(0,%d1:l),%d0
        bcc.s   1f
        movel   %d1,%d6
        mulu.w  #12,%d6
        addl    %d0,%d6
        lea     VIS,%a0
        moveb   %a0@(0,%d6:l),%d6
        extb.l  %d6
1:      rts

| ---- text: d0 = x, d1 = y, a0 = str, on a5 (clobbers d0/d1/a0/a1) ------
text:   movel   %a0,%sp@-
        pea     -1
        movel   %d1,%sp@-
        movel   %d0,%sp@-
        movel   %a5,%sp@-
        pea     FONT
        jsr     TEXT
        lea     %sp@(24),%sp
        rts

| ---- tb_draw: the whole window ------------------------------------------
| Locals at a6 (40 B): 0..15 buf, 16 whole, 20 tenths, 24 selected row,
| 28 box, 32/36 rtext's parked x/y.
tb_draw:
        lea     %sp@(-84),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        lea     %sp@(44),%a6
        movel   WINH,%d0
        beq.w   dexit
        moveal  %d0,%a5
        lea     %a5@(36),%a5           | a5 = the window's surface {w, h, ...}
        movel   %a5,%sp@-
        jsr     CLEAR
        addql   #4,%sp
        movel   %a5@(4),%d7
        subil   #14,%d7                | d7 = h - 14: the header text 6 px under the top
| header: "TEMPO 121.2" at the left, the key at the right, the rule
        pea     %a6@(20)
        pea     %a6@(16)
        jsr     TEMPOGET
        addql   #8,%sp
        lea     T_PROJ,%a0             | PTN while the pattern tempo is on, as
        tstb    0x80000024             | the stock TEMPO draw decides it
        beq.s   1f                     | (0x4004b54c)
        tstl    0x460d1aec
        bne.s   1f
        lea     T_PTN,%a0
1:      movel   %a6@(20),%sp@-         | (buf, fmt, word, whole, tenths)
        movel   %a6@(16),%sp@-
        movel   %a0,%sp@-
        pea     HDRFMT
        pea     %a6@
        jsr     SPRINTF
        lea     %sp@(20),%sp
        moveq   #4,%d0
        movel   %d7,%d1
        addql   #2,%d1
        lea     %a6@,%a0
        bsr.w   text
| the key, right-aligned: the arrows for the cursor, then "A"
| and the font's knob (0x02), the value knob, at the right edge. An icon's y is its bottom row,
| as the text's.
        moveq   #KEYX,%d0
        movel   %d7,%d1
        addql   #2,%d1
        lea     T_KEY,%a0
        bsr.w   text
        moveq   #KEYX+6,%d0
        moveq   #2,%d1
        lea     ARRUP,%a0
        bsr.s   icon
        moveq   #KEYX+13,%d0
        moveq   #2,%d1
        lea     ARRDN,%a0
        bsr.s   icon
        pea     1
        movel   %a5@,%d0
        subql   #6,%d0
        movel   %d0,%sp@-
        movel   %d7,%d0
        subql   #1,%d0
        movel   %d0,%sp@-
        pea     4
        movel   %a5,%sp@-
        jsr     RULE
        lea     %sp@(20),%sp
        moveq   #0,%d0
        bsr.s   dbox
        moveq   #1,%d0
        bsr.s   dbox
        moveq   #1,%d0
        movel   %d0,SCRDIRTY
dexit:  movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(84),%sp
        rts

| icon: a0 at x d0, header line + d1 (clobbers d0/d1/a0/a1)
icon:   addl    %d7,%d1
        movel   %d1,%sp@-
        movel   %d0,%sp@-
        movel   %a5,%sp@-
        movel   %a0,%sp@-
        jsr     ICON
        lea     %sp@(16),%sp
        rts

| rtext: a6@ (the buffer) right-aligned at d0, row d1 (clobbers d0/d1/a0/a1)
rtext:  movel   %d0,%a6@(32)
        movel   %d1,%a6@(36)
        pea     %a6@
        pea     -1
        pea     FONT
        jsr     TWIDTH
        lea     %sp@(12),%sp
        movel   %a6@(32),%d1
        subl    %d0,%d1
        movel   %d1,%d0
        movel   %a6@(36),%d1
        lea     %a6@,%a0
        bra.w   text

| ---- dbox: d0 = box; a5 = surface, a6 = locals. d7 = the box's x.
dbox:   movel   %d7,%sp@-
        movel   %d0,%a6@(28)
        moveq   #57,%d7
        mulu.l  %d0,%d7
        addql   #4,%d7                 | d7 = box x
        clrl    %sp@-                  | the title plain: the row bar marks focus
        clrl    %sp@-
        lea     TITLES,%a0
        movel   %a0@(0,%d0:l:4),%sp@-
        pea     BOXH
        pea     BOXW
        pea     4
        movel   %d7,%sp@-
        movel   %a5,%sp@-
        jsr     BOX
        lea     %sp@(32),%sp
        movel   %a6@(28),%d0
        jsr     engine
        tstl    %d4
        bmi.w   bxdone
| the MODE formatter first: it renames the knobs around it (mode cave)
        moveal  %a3@(FMTS+24),%a2
        cmpal   #0,%a2
        beq.s   1f
        moveq   #6,%d6
        jsr     getval
        movel   %d2,%sp@-
        pea     %a6@
        jsr     %a2@
        addql   #8,%sp
| the rows: each named slot whose current name is not the mode's "---"
1:      movel   %a6@(28),%d1
        lea     NTABS,%a2
        moveal  %a2@(0,%d1:l:4),%a2    | the box's names table
        jsr     rows                   | d3 = rows
| keep the selection inside the rows and the view around it
        lea     SEL,%a0
        moveq   #0,%d0
        moveb   %a0@(0,%d1:l),%d0
        cmpl    %d3,%d0
        blt.s   2f
        movel   %d3,%d0
        subql   #1,%d0
        bpl.s   2f
        moveq   #0,%d0
2:      moveb   %d0,%a0@(0,%d1:l)
        movel   %d0,%a6@(24)           | the selected row
        lea     SCR,%a1
        moveq   #0,%d2
        moveb   %a1@(0,%d1:l),%d2
        movel   %d3,%d0
        subql   #ROWS,%d0              | the last full view's first row
        bpl.s   5f
        moveq   #0,%d0
5:      cmpl    %d0,%d2
        ble.s   6f
        movel   %d0,%d2                | a view past the list's end (a MODE
6:      movel   %a6@(24),%d0           | turn on the host page) comes back
        cmpl    %d2,%d0
        bge.s   3f
        movel   %d0,%d2                | cursor above the view
3:      movel   %d2,%d3
        addql   #ROWS-1,%d3
        cmpl    %d3,%d0
        ble.s   4f
        movel   %d0,%d2
        subql   #ROWS-1,%d2            | cursor below the view
4:      moveb   %d2,%a1@(0,%d1:l)
        movel   %d2,%d5                | d5 = the row being drawn
        moveq   #BOXH-7,%d3            | d3 = its y
| each row: name, value right-aligned, the bar on the focused selection
rloop:  movel   %a6@(28),%d1
        movel   %d5,%d0
        bsr.w   slotof
        tstl    %d6
        bmi.w   bxdone
        movel   %d6,%d0
        mulu.w  #6,%d0
        lea     NTABS,%a0              | d1 = the box
        moveal  %a0@(0,%d1:l:4),%a0
        addal   %d0,%a0
        cmpil   #6,%d6                 | the MODE slot names itself after the
        bne.s   8f                     | mode (mode cave); the list says MODE
        lea     T_MODE,%a0
8:
        moveq   #4,%d0
        addl    %d7,%d0
        movel   %d3,%d1
        addql   #1,%d1
        bsr.w   text
        jsr     getval
        movel   %d6,%d0
        lsll    #2,%d0
        lea     %a3@(FMTS),%a0
        movel   %a0@(0,%d0:l),%d0
        beq.s   5f
        movel   %d2,%sp@-
        pea     %a6@
        moveal  %d0,%a0
        jsr     %a0@
        addql   #8,%sp
        bra.s   6f
5:      movel   %d2,%sp@-
        pea     DECFMT
        pea     %a6@
        jsr     SPRINTF
        lea     %sp@(12),%sp
6:      moveq   #BOXW-3,%d0
        addl    %d7,%d0
        movel   %d3,%d1
        addql   #1,%d1
        bsr.w   rtext
        moveq   #0,%d0
        moveb   FOCUS,%d0
        cmpl    %a6@(28),%d0
        bne.s   7f
        cmpl    %a6@(24),%d5
        bne.s   7f
        pea     -1
        movel   %d3,%d0
        addql   #6,%d0
        movel   %d0,%sp@-
        moveq   #BOXW-3,%d0
        addl    %d7,%d0
        movel   %d0,%sp@-
        movel   %d3,%sp@-
        movel   %d7,%d0
        addql   #3,%d0
        movel   %d0,%sp@-
        movel   %a5,%sp@-
        jsr     INVERT
        lea     %sp@(24),%sp
7:      addql   #1,%d5
        subql   #7,%d3
        moveq   #BOXH-7-7*ROWS,%d0     | past the last row
        cmpl    %d0,%d3
        bgt.w   rloop
bxdone: movel   %sp@+,%d7
        rts

| ---- data -------------------------------------------------------------
HDRFMT: .asciz  "%s %d.%d"
T_PROJ: .asciz  "TEMPO"
T_PTN:  .asciz  "PTN"
T_MODE: .asciz  "MODE"
DECFMT: .asciz  "%d"
T_DLY:  .asciz  "DELAY"
T_VRB:  .asciz  "REVERB"
| the key: the font's left and right triangles (0x13, 0x14) with room
| between them for the up and down icons; A (the knob) turns the value
T_KEY:  .asciz  "\x13     \x14 A \x02"
        .even
TITLES: .long   T_DLY, T_VRB
FOCUS:  .byte   0
SEL:    .byte   0, 0
SCR:    .byte   0, 0
PUSHK:  .byte   0                      | the encoder push held with a scene, 0 = none
TURNED: .byte   0                      | a knob turned since that push
FNK:    .byte   0                      | the REC / STOP press tb_fn took, 0 = none
XDIR:   .byte   0                      | xfer: 0 read the live values, 1 write them
UST:    .byte   0                      | 1 = a paste is on UNDO and can be undone
UPART:  .byte   0                      | the Part that paste was in
        .even
CLIP:   .space  26                     | the copy: 12 bytes a box by slot, a valid byte a box
UNDO:   .space  26                     | the values the last paste replaced
        .include "remix.inc"           | ENGIDS, NAMED (rows reads NAMED)
        NAMETAB_1                      | the reverb's: NAMES_<its id>
| The screen's labels, per box: its own tables, never the shared
| descriptor's (a host_slots remix leaves DEL and REV alone on the host page).
        .even
NTABS:  NTABS_LONGS
        .even
| An input layer as the stock ones: {0, keys, encoders, 0, 0, -1, -1}.
TB_LAYER:
        .long   0, TB_KEYS, TB_ENCS, 0, 0, -1, -1
| Key records, 26 B: {code, 0, press, release, repeat, aux, 0, delay, rate}.
TB_KEYS:
        .byte   0x34, 0
        .long   tb_lr, 0, 0, 0, 0
        .word   0, 0
        .byte   0x21, 0
        .long   tb_lr, 0, 0, 0, 0
        .word   0, 0
        .byte   0x33, 0
        .long   tb_ud, 0, tb_ud, 0, 0
        .word   15, 5
        .byte   0x20, 0
        .long   tb_ud, 0, tb_ud, 0, 0
        .word   15, 5
| the scene keys: the press and release run stock's (repeat inherited, -1;
| no sub-map of our own: the dispatcher chains the stock record's)
        .irp    k, 0x19, 0x1a
        .byte   \k, 0
        .long   tb_scn, tb_scn, -1, 0, 0
        .word   0, 0
        .endr
| FUNC: stock's press and release stay (-1), and the record's sub-map is this
| module's layer TB_FLAYER. The dispatcher chains every layer's sub-map for
| the key, this one's last, so while FUNC is held TB_FLAYER is above stock's
| FUNC maps (a FUNC press cannot be caught by a record in TB_LAYER: the FUNC
| map's own FUNC record is found first).
        .byte   0x2d, 0
        .long   -1, -1, -1, TB_FLAYER, 0
        .word   0, 0
| the encoder pushes A-F and LEVEL
        .irp    k, 0x38, 0x39, 0x3a, 0x3b, 0x3c, 0x3d, 0x3e
        .byte   \k, 0
        .long   tb_push, tb_push, -1, 0, 0
        .word   0, 0
        .endr
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
| The layer FUNC's record chains: FUNC+STOP and FUNC+REC, paste and copy.
TB_FLAYER:
        .long   0, TB_FKEYS, 0, 0, 0, -1, -1
TB_FKEYS:
        .irp    k, 0x27, 0x29
        .byte   \k, 0
        .long   tb_fn, tb_fn, -1, 0, 0
        .word   0, 0
        .endr
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
| Encoder records, 22 B: {index, 0, handler, 16 B}.
TB_ENCS:
        .irp    k, 0, 1, 2, 3, 4, 5
        .byte   \k, 0
        .long   tb_enc, 0, 0, 0, 0
        .endr
        .byte   6, 0
        .long   tb_lvl, 0, 0, 0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
