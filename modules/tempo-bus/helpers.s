| TEMPO BUS helpers -- the host lookup and the value read/write, linked
| before tempobus.s (which calls them), pinned at 0x400d24d0.
        .set    WINH,     0x460d16a0   | long: TEMPO window handle, 0 = closed
        .set    SCRDIRTY, 0x46c7c72c   | long: screen refresh request
        .set    CLEAR,    0x40035624   | (surface): the stock TEMPO draw's first call
        .set    FONT,     0x400ba876   | the small UI font
        .set    TEXT,     0x40012bd8   | (font, surf, x, y, limit, str)
        .set    TWIDTH,   0x40012f30   | (font, limit, str) -> pixels
        .set    ICON,     0x400128a8   | (icon, surf, x, y)
        .set    RULE,     0x40011910   | (surf, x, y, x2, 1)
        .set    BOX,      0x4007efd0   | (surf, x, y, w, h, title, 0, focused)
        .set    INVERT,   0x40012254   | (surf, x1, y1, x2, y2, -1)
        .set    SPRINTF,  0x40013a08   | (buf, fmt, ...)
        .set    TEMPOGET, 0x4009c5f4   | (&whole, &tenths)
        .set    TICON,    0x400cbc5c   | CONTROL's category icon, as CONTROL INPUT
        .set    LPUSH,    0x40031494   | (layer): register an input layer
        .set    LPOP,     0x4003146c   | (layer): unregister it
        .set    PUSHED,   0x4003171c   | (key): nonzero while that key is held
        .set    P1WRITE,  0x40054cd8   | (track, flat, value): page-1 writer
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
        .set    ROWS,     4            | rows visible per box
        .set    BOXW,     53
        .set    BOXH,     34

        .weak   CC_MODEDEF2            | MODE DEFAULTS' re-default, when present
        .weak   p2s_op                 | SCENES P2's page-2 lock access, when present
| A held scene (stock's scene-lock write, 0x40053498 for A, 0x40052e98 for B)
        .set    SCENE_HELD, 0x460d169c | long: 1 = A held, 2 = B
        .set    MIDIMODE, 0x80000012   | long: nonzero = the MIDI tracks
        .set    SEL_OFF,  0x8ed90      | Part: scene A's number, B's at +1
        .set    LOCKS,    0x8f3e2      | Part: the scene locks, scene*256 + track*32 + flat
        .set    SRLOCKS,  0x100a5530   | their SRAM twin: + part*6322 + scene*256 + track*32 + flat
        .set    BANKB,    0x80000002   | byte: the current bank
        .set    TRK_BANK, 0x8000182a   | bytes: the bank and part each track plays
        .set    TRK_PART, 0x80001832
        .set    XWORK,    0x80000ed4   | the morph's copy: (track*32 + flat)*2, +0 A, +1 B
        .set    LOCKVIEW, 0x460d1694   | long: the lock view (1 A, 2 B)
        .set    LOCKTURN, 0x460d1698   | long: a lock was turned
        .set    DIRTY,    0x40027e00

        .text
        .globl  engine, getval, setval, lockclr, scnheld, rows, NV, VIS
| ---- engine: d0 = box -> d4 = host track or -1, a3 = the engine's
| descriptor P, a4 = DB + part*6322, d5 = part. Clobbers d0/a0.
engine: lea     ENGIDS,%a0
        moveq   #0,%d4
        moveb   %a0@(0,%d0:l),%d4      | the engine's FX2 id
        lea     DESC2,%a0
        moveal  %a0@(0,%d4:l:4),%a3
        moveq   #0,%d5
        moveb   PARTB,%d5
        movel   #6322,%d0
        mulu.l  %d5,%d0
        addl    DBPTR,%d0
        moveal  %d0,%a4
        moveal  %a4,%a0
        addal   #IDOFF,%a0
        movel   %d4,%d0                | d0 = id
        moveq   #0,%d4
1:      cmpb    %a0@(0,%d4:l),%d0
        beq.s   2f
        addql   #1,%d4
        cmpil   #8,%d4
        blt.s   1b
        moveq   #-1,%d4
2:      rts

| ---- getval: d4 = track, d6 = slot, a4 = DB+part -> d2 = the stored value
| With a scene held (scnheld), the held scene's lock when the slot has one.
getval: bsr.w   lockget
        tstl    %d0
        bmi.s   gpart
        movel   %d0,%d2
        rts
gpart:  moveal  %a4,%a0
        moveq   #6,%d0
        cmpl    %d0,%d6
        bge.s   1f
        moveq   #24,%d0
        mulu.l  %d4,%d0
        addal   #P1OFF+18,%a0
        bra.s   2f
1:      moveq   #30,%d0
        mulu.l  %d4,%d0
        addal   #P2OFF-6,%a0
2:      addal   %d0,%a0
        moveq   #0,%d2
        moveb   %a0@(0,%d6:l),%d2
        rts

| ---- setval: d4 = track, d5 = part, d6 = slot, d2 = value, a4 = DB+part
| With a scene held the value goes to the held scene's lock (lockset).
setval: bsr.w   lockset
        tstl    %d0
        bne.s   spart
        rts
spart:  moveq   #6,%d0
        cmpl    %d0,%d6
        bge.s   p2
        movel   %d2,%sp@-              | page 1: the stock writer
        moveq   #24,%d0
        addl    %d6,%d0
        movel   %d0,%sp@-
        movel   %d4,%sp@-
        jsr     P1WRITE
        lea     %sp@(12),%sp
        rts
p2:     movel   %d6,%d3
        subql   #6,%d3                 | d3 = slot2
        moveq   #30,%d0
        mulu.l  %d4,%d0
        addl    %d3,%d0                | d0 = track*30 + slot2
        moveal  %a4,%a0
        addal   %d0,%a0
        addal   #P2OFF,%a0
        moveb   %d2,%a0@               | Part
        movel   %a4,%d1
        subl    DBPTR,%d1              | part*6322
        addl    %d0,%d1
        addil   #SHADOW,%d1
        moveal  %d1,%a0
        moveb   %d2,%a0@               | shadow
        moveq   #72,%d0
        mulu.l  %d4,%d0
        addl    %d3,%d0
        lea     LIVEB+0x38,%a0
        moveb   %d2,%a0@(0,%d0:l)      | live lane
        moveq   #1,%d0
        lsll    %d5,%d0                | 1 << part
        moveal  DBPTR,%a0
        moveal  %a0,%a1
        addal   #CHGBITS,%a1
        moveb   %a1@,%d1
        orl     %d0,%d1
        moveb   %d1,%a1@               | DB+0x95048 |= 1<<part
        moveb   MODBITS,%d1
        orl     %d0,%d1
        moveb   %d1,MODBITS            | 0x100b145e |= 1<<part
        addal   #CHGFLAG,%a0
        moveq   #1,%d1
        movel   %d1,%a0@               | DB+0x9b332 = 1
        movel   %d1,GCHG               | 0x100f8598 = 1
        lea     CC_MODEDEF2,%a0        | a2 = slot2, d2 = value, d4 = track,
        cmpal   #0,%a0                 | d5 = part (its register contract)
        beq.s   1f
        moveal  %d3,%a2
        jsr     %a0@
1:      rts

| ---- scene locks: a turn with scene A or B held edits that scene's lock, as
| stock's scene-lock knob handlers do on the parameter pages (0x40053498 for A,
| 0x40052e98 for B). Page 1 (slots 0-5, flats 24-29) is stock's lock byte;
| page 2 (slots 6-11) is SCENES P2's cell, through p2s_op. Without SCENES P2
| a page-2 row edits the Part, as a page-2 knob does on stock's pages.
|
| scnheld: -> d0 = the held scene's number (Part +0x8ed90 for A, +1 for B),
| or -1 with no scene held or the MIDI tracks on screen (MIDI SCENES' locks).
| a4 = DB + part*6322. Clobbers d1, a0.
scnheld:
        moveq   #-1,%d0
        tstl    MIDIMODE
        bne.s   1f
        movel   SCENE_HELD,%d1
        subql   #1,%d1                 | 0 = A, 1 = B
        moveq   #1,%d0
        cmpl    %d0,%d1
        bhi.s   2f                     | none held (or not 1/2)
        moveal  %a4,%a0
        addal   #SEL_OFF,%a0
        moveq   #0,%d0
        moveb   %a0@(0,%d1:l),%d0
1:      rts
2:      moveq   #-1,%d0
        rts

| lockget: d4 = track, d6 = slot, a4 -> d0 = the held scene's lock on that
| slot, or -1 (no scene held, or no lock). Clobbers a0.
lockget:
        lea     %sp@(-12),%sp
        movem.l %d1-%d2/%d5,%sp@
        bsr.s   scnheld
        tstl    %d0
        bmi.s   lgx
        moveq   #6,%d1
        cmpl    %d1,%d6
        bge.s   lg2
        bsr.w   p1off                  | d1 = the lock's offset in the Part
        moveal  %a4,%a0
        moveq   #0,%d0
        moveb   %a0@(0,%d1:l),%d0
        cmpil   #0xff,%d0
        bne.s   lgx
        moveq   #-1,%d0
        bra.s   lgx
lg2:    lea     p2s_op,%a0
        cmpal   #0,%a0
        beq.s   lgnone
        moveq   #0,%d5
        moveb   PARTB,%d5
        movel   %d6,%d2
        subql   #6,%d2                 | slot2
        moveq   #0,%d1                 | read
        jsr     %a0@
        bra.s   lgx
lgnone: moveq   #-1,%d0
lgx:    movem.l %sp@,%d1-%d2/%d5
        lea     %sp@(12),%sp
        rts

| p1off: d0 = scene, d4 = track, d6 = slot -> d1 = LOCKS + scene*256 +
| track*32 + 24 + slot (FX2 page 1 is flats 24-29).
p1off:  movel   %d0,%d1
        lsll    #3,%d1
        addl    %d4,%d1
        lsll    #5,%d1
        addl    %d6,%d1
        addil   #LOCKS+24,%d1
        rts

| lockset: d2 = value, d4 = track, d5 = part, d6 = slot, a4 -> d0 = 0 when
| a held scene took the turn (a full page-2 scene drops it, as SCENES P2's
| editor does), else nonzero and nothing written. Keeps d2-d7, a2-a6.
lockset:
        lea     %sp@(-8),%sp
        movem.l %d2-%d3,%sp@
        bsr.w   scnheld
        tstl    %d0
        bmi.s   lsno
        moveq   #6,%d1
        cmpl    %d1,%d6
        bge.s   ls2
        movel   %d0,%d3                | d3 = scene
        bsr.s   p1store
        moveq   #0,%d0
        bra.s   lsx
ls2:    lea     p2s_op,%a0
        cmpal   #0,%a0
        beq.s   lsno
        movel   %d2,%d0                | the value
        movel   %d6,%d2
        subql   #6,%d2                 | slot2
        moveq   #1,%d1                 | set
        jsr     %a0@
        moveq   #0,%d0                 | taken, or dropped when full
        bra.s   lsx
lsno:   moveq   #1,%d0
lsx:    movem.l %sp@,%d2-%d3
        lea     %sp@(8),%sp
        rts

| lockclr: d4 = track, d5 = part, d6 = slot, a4: the held scene's lock on
| that slot removed (an encoder press with a scene held, as stock's
| 0x4005435c / 0x40053a68 on release). Clobbers d0, d1, a0, a1.
lockclr:
        lea     %sp@(-8),%sp
        movem.l %d2-%d3,%sp@
        bsr.w   scnheld
        tstl    %d0
        bmi.s   lcx
        moveq   #6,%d1
        cmpl    %d1,%d6
        bge.s   lc2
        movel   %d0,%d3
        bsr.s   p1off
        moveal  %a4,%a0
        moveq   #0,%d0
        moveb   %a0@(0,%d1:l),%d0
        cmpil   #0xff,%d0
        beq.s   lcx                    | no lock there
        moveq   #-1,%d2
        bsr.s   p1store
        bra.s   lcx
lc2:    lea     p2s_op,%a0
        cmpal   #0,%a0
        beq.s   lcx
        movel   %d6,%d2
        subql   #6,%d2
        moveq   #2,%d1                 | clear
        jsr     %a0@
lcx:    movem.l %sp@,%d2-%d3
        lea     %sp@(8),%sp
        rts

| p1store: d2 = the byte (0xff = no lock), d3 = scene, d4 = track, d5 =
| part, d6 = slot, a4: stock's lock write. The lock byte and its SRAM twin;
| the Part's four changed marks and the refresh (0x40027e00); and, when the
| track plays this bank and part, the morph's copy for each side showing
| this scene; the lock view and the turned flag. Clobbers d0, d1, a0, a1.
p1store:
        movel   %d3,%d0
        bsr.w   p1off                  | d1 = LOCKS + the lock's offset
        moveal  %a4,%a0
        moveb   %d2,%a0@(0,%d1:l)      | the lock
        movel   #6322,%d0
        mulu.l  %d5,%d0
        addl    %d1,%d0
        addil   #SRLOCKS-LOCKS,%d0
        moveal  %d0,%a0
        moveb   %d2,%a0@               | its SRAM twin
        lea     TRK_PART,%a0
        moveq   #0,%d0
        moveb   %a0@(0,%d4:l),%d0
        moveq   #0,%d1
        moveb   PARTB,%d1
        cmpl    %d1,%d0
        bne.s   3f
        lea     TRK_BANK,%a0
        moveq   #0,%d0
        moveb   %a0@(0,%d4:l),%d0
        moveq   #0,%d1
        moveb   BANKB,%d1
        cmpl    %d1,%d0
        bne.s   3f
        movel   %d4,%d0                | the track plays it: the morph's copy
        lsll    #5,%d0
        addl    %d6,%d0
        addil   #24,%d0
        addl    %d0,%d0
        lea     XWORK,%a0
        addal   %d0,%a0                | a0 = (track*32 + flat)*2: +0 A, +1 B
        moveal  %a4,%a1
        addal   #SEL_OFF,%a1
        moveq   #0,%d0
        moveb   %a1@,%d0
        cmpl    %d3,%d0
        bne.s   1f
        moveb   %d2,%a0@               | scene A shows this scene
1:      moveq   #0,%d0
        moveb   %a1@(1),%d0
        cmpl    %d3,%d0
        bne.s   3f
        moveb   %d2,%a0@(1)            | scene B does
3:      bsr.w   mark
        jsr     DIRTY
        movel   SCENE_HELD,%d0
        movel   %d0,LOCKVIEW
        moveq   #1,%d0
        movel   %d0,LOCKTURN
        rts

| mark: d5 = part: the Part's four changed marks, as a stock editor's store
| sets them. Clobbers d0, d1, a0, a1.
mark:   moveq   #1,%d0
        lsll    %d5,%d0                | 1 << part
        moveal  DBPTR,%a0
        moveal  %a0,%a1
        addal   #CHGBITS,%a1
        moveb   %a1@,%d1
        orl     %d0,%d1
        moveb   %d1,%a1@               | DB+0x95048 |= 1<<part
        moveb   MODBITS,%d1
        orl     %d0,%d1
        moveb   %d1,MODBITS            | 0x100b145e |= 1<<part
        addal   #CHGFLAG,%a0
        moveq   #1,%d1
        movel   %d1,%a0@               | DB+0x9b332 = 1
        movel   %d1,GCHG               | 0x100f8598 = 1
        rts

| ---- rows: d1 = box, a2 = its names table (NTABS[box], as the mode cave
| left it) -> VIS[box] = the named slots whose name is not "---", MODE first,
| NV[box] = their count, d3 = the count. Clobbers d0/d2/d5/a0/a1.
rows:   movel   %d4,%sp@-
        movel   %d1,%d0
        mulu.w  #12,%d0
        lea     VIS,%a1
        addal   %d0,%a1                | a1 = VIS[box]
        lea     NAMED,%a0
        movew   %a0@(0,%d1:l:2),%d2    | the named slots, bit per slot
        lea     ORDER,%a0
        addal   %d0,%a0                | a0 = ORDER[box], its 12 slots in row order
        moveq   #12,%d3                | slots left to look at
        moveq   #0,%d5                 | the rows listed
1:      moveq   #0,%d0
        moveb   %a0@+,%d0              | the slot
        btst    %d0,%d2
        beq.s   2f
        movel   %d0,%d4
        mulu.w  #6,%d4
        moveb   %a2@(0,%d4:l),%d4      | the screen's name for the slot
        cmpib   #0x2d,%d4              | '-'
        beq.s   2f
        moveb   %d0,%a1@+
        addql   #1,%d5
2:      subql   #1,%d3
        bne.s   1b
        lea     NV,%a0
        moveb   %d5,%a0@(0,%d1:l)
        movel   %d5,%d3
        movel   %sp@+,%d4
        rts

        .include "remix.inc"           | ENGIDS, NAMED, the name tables
        ORDERTAB                       | ORDER: per box, the slots in row order (the manifest's ROW_ORDER); NAMED leaves out 0, 1
        NAMETAB_0                      | the delay's: NAMES_<its id>
NV:     .byte   0, 0                   | the rows listed per box, by the last draw
VIS:    .space  24                     | their slots, 12 per box
