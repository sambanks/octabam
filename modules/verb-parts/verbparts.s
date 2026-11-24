| VERB PARTS: a Part saved with a stock reverb opens on VERBERATION, in the matching mode at its defaults.
|
| Both stock routines that apply a Part to the engine pass through here before they read it: 0x40009094(bank, p) (a Part
| apply: project and bank loads, Part paste, save, reload, the current pattern's Part) and 0x40009e00(bank, p)
| (the pattern-change apply, which KITS' staging also goes through). The working Part (bank, p) is converted in
| place: for each track whose FX2 id is 0x14, 0x15 or 0x16 (PLATE, SPRING or DARK REV's), the id becomes
| VERBERATION's (VB_ID) and the six page-1 and six page-2 bytes are set to that mode's defaults (vp_tab: PLATE,
| ROOM, HALL, from the hidden rows' manifests). No chooser offers those ids in this remix, so a Part that holds
| one was saved with a stock reverb (or with an earlier image's VERB row).
|
| The Part (docs/firmware/PARTS.md 1, PARAM_PAGES.md 5a): working Part = 0x400e21e0 + bank*0x9b340 + 0x8ed80
| + p*0x18b2; FX2 id +0x08+t; FX2 page 1 +0x12c+t*24; FX2 page 2 +0x304+t*30.

        .include "remix.inc"                    | VB_ID and vp_tab
        .text
        .globl  vp_apply
        .globl  vp_patapply

| Both sites are a few instructions in, after the stock routine has its arguments in registers and before it
| reads the Part: the routines' entries are VARISPEED's (rp_apply1, rp_apply2), whose stubs replay the prologue
| and come back here.
| 0x400090aa in 0x40009094: a5 = bank, a6 = p; displaced `move.b %d0,0x80001828` (d0 = bank)
vp_apply:
        lea     -28(%sp),%sp
        movem.l %d0-%d3/%a0-%a2,(%sp)
        move.l  %a5,%d0
        move.l  %a6,%d1
        bsr     vp_convert
        movem.l (%sp),%d0-%d3/%a0-%a2
        lea     28(%sp),%sp
        move.b  %d0,0x80001828                  | displaced
        jmp     0x400090b0

| 0x40009e10 in 0x40009e00: d6 = bank, d5 = p; displaced `move.b %d6,0x80001828`
vp_patapply:
        lea     -28(%sp),%sp
        movem.l %d0-%d3/%a0-%a2,(%sp)
        move.l  %d6,%d0
        move.l  %d5,%d1
        bsr     vp_convert
        movem.l (%sp),%d0-%d3/%a0-%a2
        lea     28(%sp),%sp
        move.b  %d6,0x80001828                  | displaced
        jmp     0x40009e16

| d0 = bank, d1 = part; clobbers d0-d3, a0-a2 (the callers save them)
vp_convert:
        cmp.l   #15,%d0
        bhi     vp_done
        cmp.l   #3,%d1
        bhi     vp_done
        move.l  #0x9b340,%d2
        muls.l  %d0,%d2
        move.l  #0x18b2,%d3
        muls.l  %d1,%d3
        add.l   %d3,%d2
        add.l   #0x40170f60,%d2                 | 0x400e21e0 + 0x8ed80
        movea.l %d2,%a0                         | the working Part
        moveq   #0,%d3                          | track
vp_track:
        mvz.b   8(%a0,%d3.l),%d0                | its FX2 id
        sub.l   #0x14,%d0
        cmp.l   #2,%d0
        bhi     vp_next                         | not one of the three
        moveq   #VB_ID,%d1
        move.b  %d1,8(%a0,%d3.l)                | the id: VERBERATION's
        move.l  %d3,%d1
        moveq   #30,%d2
        muls.l  %d2,%d1
        lea     0x304(%a0),%a1
        adda.l  %d1,%a1                         | its FX2 page 2
        lea     vp_tab,%a2
        moveq   #12,%d2
        muls.l  %d0,%d2
        adda.l  %d2,%a2                         | the row's twelve bytes
        moveq   #5,%d2
vp_p2:  move.b  6(%a2,%d2.l),%d1                | page 2 (ColdFire: one indexed operand a move)
        move.b  %d1,0(%a1,%d2.l)
        subq.l  #1,%d2
        bpl     vp_p2
        move.l  %d3,%d1
        moveq   #24,%d2
        muls.l  %d2,%d1
        lea     0x12c(%a0),%a1
        adda.l  %d1,%a1                         | its FX2 page 1
        moveq   #5,%d2
vp_p1:  move.b  0(%a2,%d2.l),%d1                | page 1
        move.b  %d1,0(%a1,%d2.l)
        subq.l  #1,%d2
        bpl     vp_p1
vp_next:
        addq.l  #1,%d3
        cmp.l   #8,%d3
        blt     vp_track
vp_done:
        rts
