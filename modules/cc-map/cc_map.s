| CC MAP -- the MIDI CC dispatch entry (0x400d64a0) is repointed here.
| Each CC block maps CC numbers stock ignores onto one page's slots:
|   62-67  FX2 page-2 slot (cc-62), the FX2 page-2 editor 0x4003aab2's
|          stores, on BusDelay/BusVerb tracks, clamped by VCOUNT/DCOUNT
|   68-73  FX1 page-2 slot (cc-68), the FX1 page-2 editor 0x4003abe4's
|          stores (Part +0x8f07e, shadow 0x100a51cc, lane +0x32, the four
|          dirty flags), clamped by the FX1 descriptor's min/count
| Every other CC tail-calls CC_NEXT with the argument intact. A new block
| needs a range test at CAVE and its own write path.
|
| CC_NEXT is where anything but 62-73 goes: the stock CC handler
| (0x4000e79c). The build defines it (CavePatch.defsyms); it is not set
| here.
        .set    P1WRITE,  0x40054cd8   | stock page-1 writer (canary, CC 67 only)
        .set    MAPBUILD, 0x40001854   | fills the channel->track map
        .set    MAPGLOB,  0x46104cf4   | long stock loads to d3 before MAPBUILD
        .set    CHANMASK, 0x46c7febe   | [16] u32, one mask per channel
        .set    CCIN,     0x80000049   | AUDIO CC IN (bit 0)
        .set    IDLIVE,   0x80000ecc   | per-track live FX2 id (chooser-filled; unused now)
        .set    IDOFF,    0x8ed88      | Part: per-track FX2 id byte (+track)
        .set    DBPTR,    0x46c82456   | long: the Part DB base
        .set    PARTB,    0x80000003   | byte: part index -- the one the PAGE-2
                                       | editor P2EDIT uses (0x4003a4a8). The
                                       | page-1 writer uses 0x100b14cf instead;
                                       | builds 96-98 followed that and wrote the
                                       | wrong part's page-2 store when they differ.
        .set    P2OFF,    0x8f084      | FX2 page-2 Part store: DB+part*6322+track*30+slot2
        .set    DISPOFF,  0x8f084      | the same byte (kept: the FX2 dial READS it)
        .set    LIVEB,    0x80000810    | live block base
        .set    MIRRB,    0x100a50c0   | (old, part-0 view of SHADOW+24; unused)
        .set    SHADOW,   0x100a51d2   | FX2 page-2 shadow: +part*6322+track*30+slot2 (FX2 editor 0x4003aab2; 0x100a50a8 was the PLAYBACK editor's)
        .set    CHGBITS,  0x95048      | DB+: part-changed bitmask |= 1<<part (0x4003a5ca)
        .set    MODBITS,  0x100b145e   | byte: |= 1<<part (0x4003a5e2)
        .set    CHGFLAG,  0x9b332      | DB+: long "changed" = 1 (0x4003a5f0) -> refresh
        .set    GCHG,     0x100f8598   | long: global "changed" = 1 (0x4003a5f4)
        .set    FX2P2,    0            | no page term: the FX2 page-2 arrays are per track (30 B), slot2 direct
        .set    VERBID,   7            | BusVerb FX2 id
        .set    DLYID,    6            | BusDelay FX2 id
        .set    ID1OFF,   0x8ed80      | Part: per-track FX1 id byte (+track) (FX1 editor 0x4003ac1e)
        .set    DESC1,    0x400d5f58   | FX1 descriptor table [id] (0x4003ac26)
        .set    P1P2OFF,  0x8f07e      | FX1 page-2 Part store: DB+part*6322+track*30+slot (0x4003acac)
        .set    SHADOW1,  0x100a51cc   | FX1 page-2 shadow: +part*6322+track*30+slot (0x4003acb4)
        .set    LANE1,    0x32         | FX1 page-2 live lane offset in the 72-byte block (0x80000842)
| CC_MODEDEF2 / CC_MODEDEF1: after a page-2 write, the MODE DEFAULTS unit
| (when it is in the image: the build resolves the symbol to its cc_fx2 /
| cc_fx1; otherwise to a stock `rts`, 0x40027e1a) applies the landed
| mode's view -- a2 = slot2, d2 = the clamped value, d4 = track, d5 = part,
| everything preserved but d0/d1/a0/a1.

        .text
        .global ccm_entry
| ---- CAVE(msg): dispatch entry (jsr'd), msg* at %sp@(4) ------------------
ccm_entry:
CAVE:   movel   %sp@(4),%a0            | a0 = msg {status, cc, value}
        moveq   #0,%d0
        moveb   %a0@(1),%d0            | d0 = CC number
        subil   #62,%d0                | d0 = cc - 62
        moveq   #11,%d1
        cmpl    %d0,%d1                | 11 - (cc-62); carry if 11 < (cc-62)
        bcs.s   tostk                  | not 62..73 (also catches cc < 62)
        bra.s   mine
tostk:  jmp     (CC_NEXT).l            | tail-call the next handler, argument intact

mine:   lea     %sp@(-28),%sp
        movem.l %d2-%d7/%a2,%sp@
        movel   %d0,%d4                | d4 = cc-62: 0..5 = FX2 slot2, 6..11 = FX1 slot2+6 -- MAPBUILD preserves d2-d4/a2 only
        moveal  %a0,%a2                | a2 = msg (preserved across MAPBUILD)
        movel   MAPGLOB,%d3            | mimic stock register environment
        jsr     MAPBUILD               | rebuild CHANMASK[16]. ⚠️ CLOBBERS d5-d7: it
        moveq   #0,%d5
        moveb   %a2@(2),%d5            | d5 = value, loaded AFTER the call
        andil   #0x7f,%d5
        tstb    CCIN                   | any non-zero = on, exactly as stock
        beq.s   done                   | (0x4000e962 tstb/bne); a mask on bit 0
                                       | would silently skip if the flag byte
                                       | holds another value
        moveq   #0,%d0
        moveb   %a2@,%d0
        andil   #15,%d0                | channel = status & 15
        lea     CHANMASK,%a0
        movel   %a0@(0,%d0:l:4),%d7    | d7 = this channel's track mask
        moveq   #0,%d6                 | d6 = track
tloop:  moveq   #1,%d0
        lsll    %d6,%d0
        andl    %d7,%d0
        beq.s   tnext                  | track d6 not on this channel
        bsr.s   wtrack
tnext:  addql   #1,%d6
        moveq   #8,%d0
        cmpl    %d6,%d0
        bgt.s   tloop
done:   movem.l %sp@,%d2-%d7/%a2
        lea     %sp@(28),%sp
        rts

| ---- wtrack: write page-2 slot d4 = value d5 for track d6 ----------------
| reads d4/d5/d6, preserves d4/d5/d6/d7/a2; scratches d0-d3/a0/a1.
| d4 >= 6 is an FX1 CC (68-73): the block at the end of this file.
wtrack: moveq   #6,%d1
        cmpl    %d4,%d1                | 6 - d4: le when d4 >= 6
        ble.w   wtrk1
        movel   DBPTR,%d0
        moveq   #0,%d1
        moveb   PARTB,%d1
        movel   #6322,%d3
        mulu.l  %d3,%d1
        addl    %d1,%d0                | d0 = DB + part*6322
        moveal  %d0,%a0
        addal   #IDOFF,%a0
        addal   %d6,%a0
        moveq   #0,%d0
        moveb   %a0@,%d0               | the PART's FX2 id for track d6 (what the
                                       | busscreen's edit path reads, IDOFF). The
                                       | live mirror 0x80000ecc is filled by the
                                       | chooser; a hidden engine is never chosen
                                       | there, so it can read 0 and skip the track.
        moveq   #DLYID,%d1
        cmpl    %d0,%d1
        beq.s   wdly
        moveq   #VERBID,%d1
        cmpl    %d0,%d1
        beq.s   wverb
        rts                            | not a bus host -> skip this track
wverb:  lea     VCOUNT:l,%a1           | :l = absolute long, as the hand-patched
        bra.s   wclamp                 | placeholder form was; a same-section
wdly:   lea     DCOUNT:l,%a1           | label would otherwise assemble pc-relative
                                       | (2 bytes shorter) and break identity
wclamp: moveq   #0,%d1
        moveb   %a1@(0,%d4:l),%d1      | count (1..128)
        subql   #1,%d1                 | max = count - 1
        movel   %d5,%d2                | value
        cmpl    %d1,%d2                | max - value; lt if value > max
        ble.s   wpos
        movel   %d1,%d2                | clamp to max
wpos:   | d2 = clamped value (>=0 by construction)
        | Part = DB + part*6322 + P2OFF + track*30 + slot2
        movel   DBPTR,%d0
        moveq   #0,%d1
        moveb   PARTB,%d1
        movel   #6322,%d3
        mulu.l  %d3,%d1
        addl    %d1,%d0                | d0 = DB + part*6322
        moveq   #FX2P2,%d1
        addl    %d1,%d0                | d0 = DB + part*6322 + 0
        moveal  %d0,%a0
        addal   #P2OFF,%a0
        movel   %d6,%d1
        moveq   #30,%d3
        mulu.l  %d3,%d1                | track*30
        addal   %d1,%a0
        addal   %d4,%a0
        moveb   %d2,%a0@               | Part <- value
        | display = base + DISPOFF + track*30 + slot2 -- the byte the stock
        | FX2 dial READS (0x8f084, confirmed by an emu read-hook). d0 still
        | holds base, d1 still holds track*30 from the Part write above.
        moveal  %d0,%a0
        addal   #DISPOFF,%a0
        addal   %d1,%a0
        addal   %d4,%a0
        moveb   %d2,%a0@               | displayed value <- value
        | live = LIVEB + track*72 + 0x38 + slot2 -- the FX2 page-2 lane the per-frame
        | copier 0x4000cae8 delivers to the DSP record (measured under the port 13 Sep
        | 2026: +0x2c AMP, +0x32 FX1, +0x38 FX2; +0x20 is PLAYBACK's and never reaches
        | the DSP -- the FX2 editor writes 0x80000848+track*72+slot2 at 0x4003ab00)
        movel   %d6,%d1
        moveq   #72,%d3
        mulu.l  %d3,%d1
        lea     LIVEB,%a0
        addal   %d1,%a0
        addal   #0x38,%a0
        addal   %d4,%a0
        moveb   %d2,%a0@
        | shadow = SHADOW + part*6322 + track*30 + slot2   (d0 still = DB+part*6322)
        movel   %d6,%d3
        moveq   #30,%d1
        mulu.l  %d1,%d3                | d3 = track*30
        movel   %d0,%d1
        subl    DBPTR,%d1              | d1 = part*6322
        addl    %d3,%d1
        addil   #SHADOW,%d1
        moveal  %d1,%a0
        addal   %d4,%a0
        moveb   %d2,%a0@               | shadow <- value
        | mark the part changed, exactly as P2EDIT does after its stores
        | (0x4003a5c6..0x4003a5f0). P2EDIT posts nothing to the DSP: page-2 is
        | picked up by a refresh that this flag triggers, rebuilding the frame
        | (and the page cache) from the Part store. Without it the store is inert.
        moveq   #0,%d1
        moveb   PARTB,%d1
        moveq   #1,%d3
        lsll    %d1,%d3                | d3 = 1 << part
        moveal  DBPTR,%a0              | a0 = DB
        moveal  %a0,%a1
        addal   #CHGBITS,%a1
        moveb   %a1@,%d1
        orl     %d3,%d1
        moveb   %d1,%a1@               | DB+0x95048 |= 1<<part
        moveb   MODBITS,%d1
        orl     %d3,%d1
        moveb   %d1,MODBITS            | 0x100b145e |= 1<<part
        addal   #CHGFLAG,%a0
        moveq   #1,%d1
        movel   %d1,%a0@               | DB+0x9b332 = 1
        movel   %d1,GCHG               | 0x100f8598 = 1 -- the GLOBAL changed flag
        bsr.w   modedef2               | a landed MODE re-defaults its neighbours
        rts

| ---- wtrk1: FX1 page-2 slot (d4-6) = value d5 for track d6 --
| The FX1 PAGE-2 EDITOR 0x4003abe4, store for store, minus the refresher
| call and the redraw marker (see the header). Reads d4/d5/d6, preserves
| d4/d5/d6/d7/a2; scratches d0-d3/a0/a1.
wtrk1:  movel   DBPTR,%d0
        moveq   #0,%d1
        moveb   PARTB,%d1
        movel   #6322,%d3
        mulu.l  %d3,%d1
        addl    %d1,%d0                | d0 = DB + part*6322
        moveal  %d0,%a0
        addal   #ID1OFF,%a0
        addal   %d6,%a0
        moveq   #0,%d1
        moveb   %a0@,%d1               | the Part's FX1 id for track d6 (0x4003ac24)
        beq.w   w1skip                 | NONE (id 0): no page of ours -- write nothing.
                                       | (The editor never runs for NONE: that page
                                       | draws no knob. Its descriptor's counts are
                                       | not 0, so an id test is the honest guard.)
        lea     DESC1,%a1
        moveal  %a1@(0,%d1:l:4),%a1    | a1 = its descriptor (0x4003ac2c)
        movel   %d4,%d3                | d3 = (cc-62) = slot2 + 6: the page-2 slot index 6..11
        lea     %a1@(0,%d3:l:4),%a0    | a0 = desc + 4*(slot2+6)
        movel   %a0@(154),%d1          | count  (desc+0x9a+4*(slot2+6), 0x4003ac80)
        movel   %a0@(106),%d3          | min    (desc+0x6a+4*(slot2+6), 0x4003ac68)
        addl    %d3,%d1
        subql   #1,%d1                 | d1 = max = min + count - 1
        movel   %d5,%d2                | value
        cmpl    %d3,%d2                | value - min
        bge.s   w1lo
        movel   %d3,%d2                | below min -> min  (0x4003ac70..74)
w1lo:   cmpl    %d1,%d2                | max - value
        ble.s   w1ok
        movel   %d1,%d2                | above max -> max  (0x4003ac88..8c)
w1ok:   | d2 = clamped value; d0 = DB + part*6322
        movel   %d6,%d1
        moveq   #30,%d3
        mulu.l  %d3,%d1                | d1 = track*30
        movel   %d4,%d3
        subql   #6,%d3                 | d3 = slot2 (0..5)
        moveal  %d0,%a0
        addal   %d1,%a0
        addal   %d3,%a0
        addal   #P1P2OFF,%a0
        moveb   %d2,%a0@               | Part <- value (0x4003acb2)
        movel   %d0,%a1
        subl    DBPTR,%a1              | a1 = part*6322
        addal   %d1,%a1                | + track*30
        addal   %d3,%a1                | + slot2
        addal   #SHADOW1,%a1
        moveb   %d2,%a1@               | shadow <- value (0x4003acba)
        | the four dirty flags, exactly as the editor (0x4003acbe..0x4003acec)
        moveq   #0,%d1
        moveb   PARTB,%d1
        moveq   #1,%d3
        lsll    %d1,%d3                | d3 = 1 << part
        moveal  DBPTR,%a0              | a0 = DB
        moveal  %a0,%a1
        addal   #CHGBITS,%a1
        moveb   %a1@,%d1
        orl     %d3,%d1
        moveb   %d1,%a1@               | DB+0x95048 |= 1<<part
        moveb   MODBITS,%d1
        orl     %d3,%d1
        moveb   %d1,MODBITS            | 0x100b145e |= 1<<part
        addal   #CHGFLAG,%a0
        moveq   #1,%d1
        movel   %d1,%a0@               | DB+0x9b332 = 1
        movel   %d1,GCHG               | 0x100f8598 = 1
        | live = LIVEB + track*72 + 0x32 + slot2 (0x4003ad02..0x4003ad08)
        movel   %d6,%d1
        moveq   #72,%d3
        mulu.l  %d3,%d1                | d1 = track*72
        movel   %d4,%d3
        subql   #6,%d3                 | d3 = slot2
        lea     LIVEB,%a0
        addal   %d1,%a0
        addal   #LANE1,%a0
        addal   %d3,%a0
        moveb   %d2,%a0@
        bsr.w   modedef1
w1skip: rts

| ---- the MODE DEFAULTS adapters: this cave's (d4 = slot, d2 = value,
| d6 = track) into the unit's (a2 = slot2, d2, d4 = track, d5 = part).
modedef2:
        lea     %sp@(-16),%sp
        movem.l %d4-%d6/%a2,%sp@
        moveal  %d4,%a2                | slot2 (0..5)
        movel   %d6,%d4                | track
        moveq   #0,%d5
        moveb   PARTB,%d5              | part
        jsr     (CC_MODEDEF2).l
        movem.l %sp@,%d4-%d6/%a2
        lea     %sp@(16),%sp
        rts
modedef1:
        lea     %sp@(-16),%sp
        movem.l %d4-%d6/%a2,%sp@
        movel   %d4,%d5
        subql   #6,%d5
        moveal  %d5,%a2                | slot2 = (cc-62) - 6
        movel   %d6,%d4                | track
        moveq   #0,%d5
        moveb   PARTB,%d5              | part
        jsr     (CC_MODEDEF1).l
        movem.l %sp@,%d4-%d6/%a2
        lea     %sp@(16),%sp
        rts

| ---- per-engine page-2 value counts, slot2 order (slots 6..11) -----------
| Must match the engines' manifests (busverb / busdelay page-2 counts);
| tools/verify/verify_ccmap.py checks them against VERB_COUNTS / DLY_COUNTS.
VCOUNT: .byte   3, 128, 128, 128, 128, 128  | MODE TONE DIFF GATE DLY TIME
DCOUNT: .byte   3, 128, 128, 4, 128, 128  | MODE SCTR DENS SIZE PTCH TIME
