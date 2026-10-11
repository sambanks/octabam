| MODE DEFAULTS -- landing on a MODE re-defaults the knobs around it.
|
| Both page-2 editors (FX2 0x4003a9dc, FX1 0x4003abe4) call 0x40027e00
| after their Part/shadow stores and before the live-lane store; the two
| jsr sites are detoured here. At the site: a2 = slot2 (0..5), d2 = the
| clamped value just stored, d4 = track, d5 = part. The stub replays the
| displaced call, then, if slot2 + 6 is a module's MODE slot and the value
| names one of its views, writes that view's defaults: page-1 slots through
| the stock page-1 writer 0x40054cd8(track, flat, value) (FX1 flat 0x12+k,
| FX2 0x18+k), page-2 slots with the editor's own stores (Part, shadow,
| live lane, the per-slot redraw flag; the dirty flags are already set by
| the editor for this part). The table is generated per remix
| (manifest.py table_inc) from the manifests' ModeViews.
        .set    DIRTY,   0x40027e00    | the displaced call (project-dirty)
        .set    P1WRITE, 0x40054cd8    | page-1 writer (track, flat, value)
        .set    DBPTR,   0x46c82456    | long: the Part DB base
        .set    ID1OFF,  0x8ed80       | Part: per-track FX1 id byte
        .set    ID2OFF,  0x8ed88       | Part: per-track FX2 id byte
        .set    P1P2OFF, 0x8f07e       | FX1 page-2 Part store: +track*30+slot2
        .set    P2P2OFF, 0x8f084       | FX2 page-2 Part store
        .set    SHADOW1, 0x100a51cc    | FX1 page-2 shadow: +part*6322+track*30+slot2
        .set    SHADOW2, 0x100a51d2    | FX2 page-2 shadow
        .set    LIVEB,   0x80000810    | live block base, 72 B per track
        .set    LANE1,   0x32          | FX1 page-2 lane offset
        .set    LANE2,   0x38          | FX2 page-2 lane offset
        .set    REDRAW,  0x46c7d244    | [(slot2*5+1)*4] = 20 -> redraw that slot

        .text
        .globl  fx2_hook, fx1_hook, CC_MODEDEF2, CC_MODEDEF1, MODEDEF_TABLE
fx2_hook:
        jsr     DIRTY
CC_MODEDEF2:                           | CC MAP's entry (its cave sets the
        lea     %sp@(-44),%sp          | flags itself): a2 = slot2, d2 = value,
        movem.l %d2-%d7/%a2-%a6,%sp@   | d4 = track, d5 = part
        moveq   #1,%d6                 | d6 = FX2
        bra.s   body
fx1_hook:
        jsr     DIRTY
CC_MODEDEF1:
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        moveq   #0,%d6                 | d6 = FX1

| d0 = the slot's effect id, d1 = slot2 + 6, d2 = the new value,
| d4 = track, d5 = part, d6 = kind, a3 = Part base, a4 = table cursor,
| a5 = entry match (id and mode slot), d7 = counts, d3 = flags.
body:   movel   DBPTR,%d0
        movel   #6322,%d1
        mulu.l  %d5,%d1
        addl    %d1,%d0
        moveal  %d0,%a3                | a3 = DB + part*6322
        moveal  %a3,%a0
        addal   %d4,%a0
        tstl    %d6
        beq.s   id1
        addal   #ID2OFF,%a0
        bra.s   idok
id1:    addal   #ID1OFF,%a0
idok:   moveq   #0,%d0
        moveb   %a0@,%d0               | d0 = id
        movel   %a2,%d1
        addql   #6,%d1                 | d1 = the page-2 slot index 6..11
        lea     MODEDEF_TABLE,%a4
tloop:  mvz.b   %a4@+,%d3              | entry id; 0xff ends the table
        cmpil   #0xff,%d3
        beq.s   done
        cmpl    %d0,%d3
        seq     %d3                    | d3 = id matches
        mvz.b   %a4@+,%d7              | the entry's mode slot
        cmpl    %d1,%d7
        seq     %d7
        andl    %d7,%d3
        moveal  %d3,%a5                | a5 = entry match
        mvz.b   %a4@+,%d7              | nviews
vloop:  subql   #1,%d7
        bmi.s   tloop
        movel   %d7,%sp@-              | park nviews
        moveq   #0,%d3
        moveb   %a4@+,%d3              | the view's mode value
        cmpl    %d2,%d3
        seq     %d3
        movel   %a5,%d7
        andl    %d7,%d3                | d3 != 0: this view applies
        moveq   #0,%d7
        moveb   %a4@+,%d7              | npairs
ploop:  subql   #1,%d7
        bmi.s   vnext
        tstb    %d3
        beq.s   pskip
        bsr.w   apply
pskip:  addql   #2,%a4
        bra.s   ploop
vnext:  movel   %sp@+,%d7
        bra.s   vloop
done:   movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| apply: slot = %a4@(0), value = %a4@(1); everything preserved but a0/a1.
apply:  lea     %sp@(-20),%sp
        movem.l %d0-%d3/%d7,%sp@
        moveq   #0,%d0
        moveb   %a4@,%d0               | slot 0..11
        moveq   #0,%d1
        moveb   %a4@(1),%d1            | value
        moveq   #6,%d3
        cmpl    %d0,%d3                | 6 - slot
        ble.s   page2
        tstl    %d6                    | page 1: flat = 0x12 + slot (FX1), 0x18 + slot (FX2)
        beq.s   f1
        addql   #6,%d0
f1:     addil   #0x12,%d0
        movel   %d1,%sp@-
        movel   %d0,%sp@-
        movel   %d4,%sp@-
        jsr     P1WRITE
        lea     %sp@(12),%sp
        bra.s   adone
page2:  subql   #6,%d0                 | d0 = slot2
        movel   %d4,%d3
        moveq   #30,%d7
        mulu.l  %d7,%d3
        addl    %d0,%d3                | d3 = track*30 + slot2
        moveal  %a3,%a0
        addal   %d3,%a0                | Part base + track*30 + slot2
        movel   %a3,%d7
        subl    DBPTR,%d7
        addl    %d3,%d7                | d7 = part*6322 + track*30 + slot2
        tstl    %d6
        beq.s   s1
        addal   #P2P2OFF,%a0
        addil   #SHADOW2,%d7
        bra.s   s2
s1:     addal   #P1P2OFF,%a0
        addil   #SHADOW1,%d7
s2:     moveb   %d1,%a0@               | Part
        moveal  %d7,%a1
        moveb   %d1,%a1@               | shadow
        movel   %d4,%d3
        moveq   #72,%d7
        mulu.l  %d7,%d3
        addl    %d0,%d3
        lea     LIVEB,%a0
        addal   %d3,%a0
        tstl    %d6
        beq.s   l1
        addal   #LANE2,%a0
        bra.s   l2
l1:     addal   #LANE1,%a0
l2:     moveb   %d1,%a0@               | live lane
        movel   %d0,%d3
        lsll    #2,%d3
        addl    %d0,%d3
        addql   #1,%d3                 | slot2*5 + 1
        lea     REDRAW,%a0
        moveq   #20,%d7
        movel   %d7,%a0@(0,%d3:l:4)    | redraw this slot
adone:  movem.l %sp@,%d0-%d3/%d7
        lea     %sp@(20),%sp
        rts

        .include "remix.inc"           | MODEDEF_TABLE, generated per remix
