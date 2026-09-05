| CC -> FX2 PAGE-2 cave (OS 1.40C, ColdFire).
|
| Stock CC only reaches FX2 page 1 (CC 40-45; the handler admits cc-16 < 30).
| This cave adds CC 62-67 -> the host's bus-engine page-2 slots 6-11, so the
| voicing round can drive every control over MIDI, not just page 1.
|
| HOOK: the MIDI dispatch table 0x400d6474[0xB] (CC) is repointed from the
| stock handler 0x4000e79c to CAVE. CAVE reads the CC number; anything but
| 62-67 tail-calls stock (jmp 0x4000e79c) with the argument intact, so no
| stock CC is disturbed. Only 62-67 are handled here.
|
| WRITE: mirrors the busscreen's measured page-2 write, generalised over
| track -- Part, live byte and mirror, count-clamped. It does NOT call the
| page-2 editor 0x4003a474 and does NOT touch the TRACKB global: that editor
| writes the same live byte + mirror directly and nothing in 0x40171xxx
| (traced 5 Sep 2026, docs/midi_re_cc.md), so a direct write reproduces its
| stores without the cross-task TRACKB race. Off-page there is no knob to
| redraw, so the redraw marker is skipped too.
|
| Track resolution mirrors the stock CC 16-45 handler (0x4000e91c): rebuild
| the channel->track map, gate on AUDIO CC IN, and write every audio track
| (0-7) whose trig channel is this message's channel. Auto-channel / MIDI_MODE
| retargeting is not handled (it maps to MIDI tracks, which host no FX2).
|
| Clamp uses per-engine page-2 count tables (VCOUNT/DCOUNT, 6 bytes each,
| slot2 order) patched by the build; a select's over-count value would be the
| stored index that stalls the sequencer, so the clamp is mandatory.

        .set    STOCK,    0x4000e79c   | stock CC handler (tail-called)
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
        .set    P2OFF,    0x8ef5a      | page-2 Part offset (storage)
        .set    DISPOFF,  0x8f084      | displayed-value array the FX2 dial READS
        .set    LIVEB,    0x80000810    | live block base
        .set    MIRRB,    0x100a50c0   | (old, part-0 view of SHADOW+24; unused)
        .set    SHADOW,   0x100a50a8   | shadow: +part*6322+track*30+page*6+slot2 (P2EDIT 0x4003a5bc)
        .set    CHGBITS,  0x95048      | DB+: part-changed bitmask |= 1<<part (0x4003a5ca)
        .set    MODBITS,  0x100b145e   | byte: |= 1<<part (0x4003a5e2)
        .set    CHGFLAG,  0x9b332      | DB+: long "changed" = 1 (0x4003a5f0) -> refresh
        .set    GCHG,     0x100f8598   | long: global "changed" = 1 (0x4003a5f4)
        .set    PAGEIDX,  0x460d5c30   | long: staged page index (P2EDIT 0x4003a4b4)
        .set    FX2P2,    0            | FX2 page-2 store displacement = staged index 0 * 6 (measured)
        .set    VERBID,   7            | BusVerb FX2 id
        .set    DLYID,    6            | BusDelay FX2 id
        .set    VCOUNT,   0x40bad000   | patched: verb page-2 counts (6 bytes)
        .set    DCOUNT,   0x40bad004   | patched: delay page-2 counts (6 bytes)

        .text
| ---- CAVE(msg): dispatch entry (jsr'd), msg* at %sp@(4) ------------------
CAVE:   movel   %sp@(4),%a0            | a0 = msg {status, cc, value}
        moveq   #0,%d0
        moveb   %a0@(1),%d0            | d0 = CC number
        subil   #62,%d0                | d0 = cc - 62
        moveq   #5,%d1
        cmpl    %d0,%d1                | 5 - (cc-62); carry if 5 < (cc-62)
        bcs.s   tostk                  | not 62..67 (also catches cc < 62)
        bra.s   mine
tostk:  jmp     STOCK                  | tail-call stock, argument intact

mine:   lea     %sp@(-28),%sp
        movem.l %d2-%d7/%a2,%sp@
        movel   %d0,%d4                | d4 = slot2 (0..5) -- MAPBUILD preserves d2-d4/a2 only
        moveal  %a0,%a2                | a2 = msg (preserved across MAPBUILD)
        movel   MAPGLOB,%d3            | mimic stock register environment
        jsr     MAPBUILD               | rebuild CHANMASK[16]. ⚠️ CLOBBERS d5-d7: it
                                       | saves only d2-d4/a2 (0x40001858). The value
                                       | used to be loaded into d5 BEFORE this call;
                                       | the emu's channel loop never ran so it
                                       | survived, hardware trashed it (build 94/95).
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
wtrack: movel   DBPTR,%d0
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
wverb:  lea     VCOUNT,%a1
        bra.s   wclamp
wdly:   lea     DCOUNT,%a1
wclamp: moveq   #0,%d1
        moveb   %a1@(0,%d4:l),%d1      | count (1..128)
        subql   #1,%d1                 | max = count - 1
        movel   %d5,%d2                | value
        cmpl    %d1,%d2                | max - value; lt if value > max
        ble.s   wpos
        movel   %d1,%d2                | clamp to max
wpos:   | d2 = clamped value (>=0 by construction)
        | Part = DB + part*6322 + P2OFF + track*30 + 18 + slot2
        movel   DBPTR,%d0
        moveq   #0,%d1
        moveb   PARTB,%d1
        movel   #6322,%d3
        mulu.l  %d3,%d1
        addl    %d1,%d0                | d0 = DB + part*6322
        | + page*6: P2EDIT forms DB+part*6322+0x8ef5a+track*30+page*6+slot2 with
        | page = the staged index 0x460d5c30. The FX2 page stages index 3
        | (button 4 -> 3 remap at 0x4005a5cc), so the FX2 page-2 store is +18 --
        | the busscreen's original value, hardware-confirmed 5 Sep 2026: build
        | 100 read the index live with the page up and page 2 moved over CC;
        | builds 97-99 hardcoded 4 (+24) and never took. Pinned so it works
        | with the FX2 page NOT on screen (the voicing case).
        | + page*6 where page = the staged index 0x460d5c30 (P2EDIT 0x4003a4b4).
        | MEASURED 5 Sep 2026: with the FX2 page up the staged index is 0 --
        | tag 12 wrote index*16 into GATE and the dial sat at zero, while MODE
        | and SHMR moved over CC. So the FX2 page-2 store is +0 + slot2. The
        | busscreen's +18 and my +24 (page kind 3/4 * 6) were both wrong; tags
        | 11 (+18) and 97-99 (+24) never took, tags 10/12 (live index) did.
        | Pinned so it works with the FX2 page NOT on screen (the voicing case).
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
        | display = base + DISPOFF + track*30 + 6 + slot2 -- the byte the stock
        | FX2 dial READS (0x8f084, confirmed by an emu read-hook). d0 still
        | holds base, d1 still holds track*30 from the Part write above.
        moveal  %d0,%a0
        addal   #DISPOFF,%a0
        addal   %d1,%a0                | (page*6 already in the base)
        addal   %d4,%a0
        moveb   %d2,%a0@               | displayed value <- value
        | live = LIVEB + track*72 + 0x20 + slot2
        movel   %d6,%d1
        moveq   #72,%d3
        mulu.l  %d3,%d1
        lea     LIVEB,%a0
        addal   %d1,%a0
        addal   #0x20,%a0
        addal   %d4,%a0
        moveb   %d2,%a0@
        | shadow = SHADOW + part*6322 + track*30 + 24 + slot2   (d0 still = DB+part*6322)
        movel   %d6,%d3
        moveq   #30,%d1
        mulu.l  %d1,%d3                | d3 = track*30
        movel   %d0,%d1
        subl    DBPTR,%d1              | d1 = part*6322 + page*6
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
                                       | (P2EDIT 0x4003a5f4). Emu write-diff of
                                       | P2EDIT vs this cave (5 Sep): this was the
                                       | only functional store still missing.
        rts
