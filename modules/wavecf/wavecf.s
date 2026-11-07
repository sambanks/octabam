| ============================================================================
| WAVE (ColdFire) -- a 4-voice wavetable machine on a FLEX track (GNU as; DRAM unit: -mcpu=54455)
|
| A row of the track's machine list ("WAVE", signature 'W','V',1 in the Part like OCTA-303's 'T','B',1).
| The voice is engine.c (modules/wavecf): 4 voices, 8 generated frames, no filter; the note layer wcf.c
| (CHRD, VOIC, TUNE).  PLAYBACK: TUNE FRAM CHRD VOIC ATK REL.  SETUP is FLEX's own.
|
| The scaffold (the machine list, SRC SETUP, the Part validator, the page clone, the render call) is
| modules/octa303's, copied: see octa303.s for the sites and their contracts.  What is WAVE's: the
| signature, the page, wc_render (the engine instead of the 303), and no gate: the voices run from the
| START and the track's AMP envelope in the DSP shapes them (OCTA-303 with GATE OFF).
|
| One limit for every machine: MC_LIMIT of them in a Part (modules/hooks, mc_sig_table).
| ============================================================================

        .text

| ---- platform (OS 1.40C) -- each value as poly.s 2.9 has it (check_platform.py compares them)
        .set    VOICE_BASE,     0x800049d8      | the CF voice structs: byte 0 = alive, +8 = the settings record
        .set    VOICE_STRIDE,   0xa8
        .set    V_POS,          64              | +64..+83: the voice's sample positions (pinned for a 303 track)
        .set    CURSOR,         0x80001c80      | the header this call writes: byte 3 = samples, L/R longs from +16
        .set    NIBBLE,         0x46104d0c      | the packer's per-track event byte, bit 4 = a voice START
        .set    STOCK_RENDER,   0x40004008      | the FLEX renderer this unit replaces in the kind table
        .set    FP_PTR,         0x800062a8      | the packer's per-track DSP parameter record (halfwords, raw<<8)
        .set    RS_PTR,         0x800062a4      | the packer's per-track render state (+4 = the latched retrig count)
        .set    SETTINGS_BASE,  0x100b14f0      | the sample settings records, 0x448 each, the path at +0
        .set    SETTINGS_SPAN,  0x24640         | 136 * 0x448
        .set    SETTINGS_STRIDE,0x448
        .set    SLOT_OFF,       0x8f04b         | Part + 0x8f04a + track*5 + 1: the track's FLEX slot
        .set    PART_SIZE,      6322
        .set    FLEX_P,         0x400d31ae      | the stock FLEX PLAYBACK descriptor (P form)
        .set    FLEX_DESC_LEN,  0x192
        .set    WC_DLEN,        0x194           | v7.0: wc_desc's records, a long apart
        .set    PART_OFF,       0x8ed80         | v7.0: the bank blob's Part 0 (Part' = BANK + this + part * 6322)
        .set    LANE_SETUP,     0x20            | v7.0: the live lane's SETUP bytes (+0x20..+0x25)
        .set    RESOLVER_RET,   0x40031ed6      | the page resolver after its table load (wc_page)
        .set    RETRIG_RET,     0x4000c63c      | the frame builder after its command-byte copy (wc_retrig)
        .set    FMT_PLAIN,      0x4003c178      | stock fmt(buf, value) -> "%d"
        .set    SPRINTF,        0x40013a08      | v6.4: the firmware's sprintf (modules/synth page.s)
        .set    FMT_D,          0x400b465d      | its "%d"
        .set    BANK_PTR,       0x46c82456      | the bank blob pointer (quantizer.s qz_is_synth)
        .set    PART_IDX,       0x100b14cf      | the current part
        .set    MACH_OFF,       0x8eda2         | Part + 0x8eda2 + track: the machine (1 = FLEX)
        .set    STEPW,          0x800065b2      | v6.5: the sequencer's step word (u16; Euclacid's LIVE, poly.s po_clock)
        .set    TICKB,          0x800065b6      | its tick byte (0..5 a step at 1x)
        .set    PAT_IDX,        0x100b14d0      | the current pattern in the bank (poly.s, hardware-proven)
        .set    PAT_STRIDE,     0x8ed8          | bank blob + pattern * 0x8ed8 (STEP_LOCKS.md 1)
        .set    TRK_STRIDE,     0x91a           | + track * 0x91a: the track record (masks at +0, +8, +16; length +0x50)
        .set    LANE_HOLD,      13              | the live lane's AMP HOLD (lock slot 13, PARAM_PAGES.md 5a')
        .include "remix.inc"            | DEVIL_ID: dEVILish's FX id, or 0x100 (never a byte) without it
        .if     HK_MACHINE_ROWS         | beside other machines (modules/hooks, machine_rows): the
        .if     MC_HAS_RENDER           | next renderer in the FLEX kind entry's chain
        .set    STOCK_RENDER,   MC_NEXT_RENDER
        .endif
        .endif
        .set    CURVALS,        0x80000810      | the frame builder's live lane, 72 B a track, locks applied
        .set    CV_STRIDE,      72
        .set    LANE_FX1P1,     18              | FX1 page 1 knobs: lane bytes 18-23 (PARAM_PAGES.md 5a')
        .set    LANE_FX2P1,     24              | FX2 page 1: 24-29
        .set    LANE_FX1P2,     0x32            | FX1 page 2: +0x32..+0x37
        .set    LANE_FX2P2,     0x38            | FX2 page 2: +0x38..+0x3d
        .set    FXID1,          0x80000ec4      | the live FX1 id of each track, a byte a track (5d)
        .set    FXID2,          0x80000ecc      | FX2
        .set    VREC,           0x80000110      | v7.1: the DSP voice records, 64 B a track + ping * 0x200:
                                                |   halfwords 6-11 FX1 page 1, 12-17 FX2 page 1, raw << 8, with
                                                |   the locks, the scene morph and the LFOs (LFO.md 5, MIDI.md C)
        .set    PINGW,          0x800000e0      | the frame's ping (0 or 1), as the builder's copy loop reads it
        .set    NEUTRAL_PTCH,   0x4000          | 0 semitones
        .set    NEUTRAL_RATE,   0x7f00          | rate 1.0
        .set    NTRACKS,        8

| ---- per-track state (longs): S_ENG is the engine (engine.h Engine, 132 bytes)
        .set    S_LATCHED,0
        .set    S_MACH,4
        .set    S_WPTCH,8
        .set    S_WRATE,12
        .set    S_POS,16                        | +16..+35: the voice's positions
        .set    S_INIT,36                       | the engine has been initialised
        .set    S_ENG,48
        .set    ST_SHIFT,9
        .set    ST_SIZE,512

| a new WAVE track's AMP page: the stock one holds a note forever (HOLD INF, REL INF) and the voices run from the
| START, so the track gets a finite HOLD and REL (Part' + 0x11a + 24 * track + 6: ATK HOLD REL; the live lane's
| flat slots 12, 13, 14)
        .set    SCALE_AT,        0x400d2ca8      | modules/quantizer/scale.s: `jmp qz_scale_mask`, d0 := the scale's pitch-class mask
        .set    AMP_PAGE,        0x120
        .set    AMP_ATK_MIN,     10              | the DSP's AMP ATK is never below this on a WAVE track (see wc_amp)
        .set    AMP_ATK,         10              | not 0: an instant attack steps the tone each time the envelope reopens (measured under the port)
        .set    AMP_HOLD,        40
        .set    AMP_REL,         56
        .set    P_CENTER,        16384
        .set    P_LO,            7168
        .set    P_HI,            25600
        .set    TUNE_LO,         -24
        .set    TUNE_HI,         24
        .set    NOTIFY,          0x4005a2b8      | NOTIFY(text, duration): the stock toast

        .macro  RAWW off, dst
        moveq   #0,%d0
        move.w  \off(%a4),%d0
        lsr.l   #8,%d0
        cmp.l   #127,%d0
        bls     .Lrw\@
        moveq   #127,%d0
.Lrw\@:
        move.l  %d0,\dst
        .endm

| the engine's C runs with MACSR fractional and ACC0 clear (engine.h); the frame interrupt's EMAC state is
| saved here and put back (as modules/waveload/wrap.s).  Clobbers d0; 12 bytes of stack.
        .macro  EMAC_ON
        lea     -12(%sp),%sp
        move.l  %macsr,%d0
        move.l  %d0,(%sp)
        move.l  #0,%macsr
        move.l  %accext01,%d0
        move.l  %d0,4(%sp)
        movclr.l %acc0,%d0
        move.l  %d0,8(%sp)
        move.l  #0x20,%macsr
        .endm
        .macro  EMAC_OFF
        move.l  #0,%macsr
        move.l  8(%sp),%d0
        move.l  %d0,%acc0
        move.l  4(%sp),%d0
        move.l  %d0,%accext01
        move.l  (%sp),%d0
        move.l  %d0,%macsr
        lea     12(%sp),%sp
        .endm


        .global wc_pgdesc, wc_page, wc_retrig, wc_chrom, wc_render
        .global eng_init, eng_adsr, eng_pos, eng_on, eng_off, eng_setup, eng_render, wcf_note, wcf_init, wcf_knobs, wcf_scale, wcf_setup
        .global wcf_table

        .align  4

| ============================================================================
| wc_render(track, ping, start, end) -- in the FLEX kind entry's chain (octa303.s sy_render: the same call,
| frame 44(sp) the stock return, 48 our return, args 52 / 56 / 60 / 64).  On the frame's last call of a
| signed track within the limit: at a START the note and the knobs, then the stock call with PTCH / RATE
| neutral and the positions pinned, and the engine's samples over what it shipped.
| ============================================================================
wc_render:
        lea     -48(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        move.l  CURSOR,%a2              | the header this call writes
        move.l  52(%sp),%d2             | track
        moveq   #NTRACKS-1,%d0
        cmp.l   %d0,%d2
        bhi     .Lstock
        move.l  %d2,%d0
        lsl.l   #8,%d0                 | track * ST_SIZE (512: 8 + 1)
        add.l   %d0,%d0
        lea     wc_state,%a3
        add.l   %d0,%a3
        move.l  FP_PTR,%a4
        moveq   #0,%d4                  | 1 = PTCH/RATE and the positions are neutralised for the call
        moveq   #16,%d1
        cmp.l   64(%sp),%d1             | the frame's last call?
        bne     .Lstock
        lea     NIBBLE,%a0
        add.l   %d2,%a0
        btst    #4,(%a0)                | a voice starts this frame: ours?
        beq     .Lison
        move.l  %d2,%d0
        bsr     wc_sigcur_lim
        move.l  %d0,S_MACH(%a3)
        beq     .Lnot
        bsr     wc_start                | the engine, the knobs and the note
        moveq   #1,%d0
        move.l  %d0,S_LATCHED(%a3)
        move.l  RS_PTR,%a0
        clr.l   4(%a0)                  | the retrig count the packer latched: no stock retrigs
        bra     .Lison
.Lnot:
        clr.l   S_LATCHED(%a3)          | not ours: stock from here on
.Lison:
        tst.l   S_LATCHED(%a3)
        beq     .Lstock
        bsr     wc_knobs                | this call's knobs, before the record is neutralised
        bsr     wc_amp                  | and the DSP's AMP attack, never instant
        move.w  (%a4),%d0
        move.w  %d0,S_WPTCH+2(%a3)
        move.w  6(%a4),%d0
        move.w  %d0,S_WRATE+2(%a3)
        move.l  #NEUTRAL_PTCH,%d0       | the stock renderer computes rate 1.0 from these
        move.w  %d0,(%a4)
        move.l  #NEUTRAL_RATE,%d0
        move.w  %d0,6(%a4)
        bsr     wc_voice                | a0 = the voice's position fields
        lea     S_POS(%a3),%a1
        move.l  (%a0)+,(%a1)+
        move.l  (%a0)+,(%a1)+
        move.l  (%a0)+,(%a1)+
        move.l  (%a0)+,(%a1)+
        move.l  (%a0)+,(%a1)+
        moveq   #1,%d4
.Lstock:
        move.l  64(%sp),-(%sp)          | end
        move.l  64(%sp),-(%sp)          | start
        move.l  64(%sp),-(%sp)          | ping
        move.l  64(%sp),-(%sp)          | track
        jsr     STOCK_RENDER
        lea     16(%sp),%sp
        move.l  %d0,44(%sp)             | the stock return value, handed back
        move.l  52(%sp),%d2
        moveq   #NTRACKS-1,%d0
        cmp.l   %d0,%d2
        bhi     .Ldone
        tst.l   %d4
        beq     .Lnorest
        move.w  S_WPTCH+2(%a3),%d0      | restore PTCH and RATE for the DSP
        move.w  %d0,(%a4)
        move.w  S_WRATE+2(%a3),%d0
        move.w  %d0,6(%a4)
        bsr     wc_voice                | pin the carrier: the positions as they were before the call
        lea     S_POS(%a3),%a1
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        bra     .Lrender
.Lnorest:
        tst.l   S_LATCHED(%a3)
        beq     .Ldone                  | not a WAVE track: the stock samples stand
        bsr     wc_knobs                | a first call [0,n): the record is untouched
        bsr     wc_amp
.Lrender:
        moveq   #0,%d7
        move.b  3(%a2),%d7              | samples shipped by this call
        beq     .Ldone
        lea     16(%a2),%a5             | where they go
        lea     S_ENG(%a3),%a6
        lea     -64(%sp),%sp            | the engine's Q27 samples
        EMAC_ON
        move.l  %d7,-(%sp)
        pea     16(%sp)                 | the samples, below the EMAC save and the pushed count
        move.l  %a6,-(%sp)
        jsr     eng_render
        lea     12(%sp),%sp
        EMAC_OFF
        move.l  %sp,%a0
.Lout:
        move.l  (%a0)+,%d0              | Q27 -> Q15, clamped
        asr.l   #8,%d0
        asr.l   #4,%d0
        move.l  #32767,%d1
        cmp.l   %d1,%d0
        ble     .Lo1
        move.l  %d1,%d0
.Lo1:
        neg.l   %d1
        cmp.l   %d1,%d0
        bge     .Lo2
        move.l  %d1,%d0
.Lo2:
        lsl.l   #8,%d0
        lsl.l   #8,%d0
        move.l  %d0,(%a5)+
        move.l  %d0,(%a5)+
        subq.l  #1,%d7
        bne     .Lout
        lea     64(%sp),%sp
.Ldone:
        move.l  44(%sp),%d0
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     48(%sp),%sp
        rts

| ---- wc_start: a START of a signed track.  d2 = track, a3 = state, a4 = the record.  The engine once, the
|      knobs, then the note from TUNE, CHRD and VOIC.  Clobbers d0, d1, d3, d5, d6, a0, a1.
wc_start:
        tst.l   S_INIT(%a3)
        bne     .Lst_have
        pea     wcf_table               | wcf_init(e, table)
        pea     S_ENG(%a3)
        jsr     wcf_init
        lea     8(%sp),%sp
        moveq   #1,%d0
        move.l  %d0,S_INIT(%a3)
.Lst_have:
        bsr     wc_knobs
        moveq   #0,%d0
        move.w  (%a4),%d0
        bsr     wc_pword
        move.l  %d0,%d3                 | p
        moveq   #0,%d0
        move.w  6(%a4),%d0              | VOIC raw 0..3 -> 1..4
        lsr.l   #8,%d0
        moveq   #3,%d1
        cmp.l   %d1,%d0
        bls     .Lst_v
        move.l  %d1,%d0
.Lst_v:
        addq.l  #1,%d0
        move.l  %d0,%d5
        moveq   #0,%d0
        move.w  4(%a4),%d0              | CHRD raw 0..31
        lsr.l   #8,%d0
        moveq   #31,%d1
        cmp.l   %d1,%d0
        bls     .Lst_c
        move.l  %d1,%d0
.Lst_c:
        move.l  %d0,%d6
        moveq   #0,%d0                  | the quantizer's scale mask: bit k = pitch class k in the scale, 0 = OFF
        mvz.w   SCALE_AT,%d1            | its accessor is there (a `jmp`; a remix without the quantizer has zeros here)
        cmpi.l  #0x4ef9,%d1
        bne     .Lst_ns
        jsr     SCALE_AT                | clobbers d0, a0
.Lst_ns:
        move.l  %d0,-(%sp)
        pea     S_ENG(%a3)
        jsr     wcf_scale
        lea     8(%sp),%sp
        EMAC_ON
        move.l  %d5,-(%sp)              | wcf_note(e, p, chrd, voic)
        move.l  %d6,-(%sp)
        move.l  %d3,-(%sp)
        pea     S_ENG(%a3)
        jsr     wcf_note
        lea     16(%sp),%sp
        EMAC_OFF
        rts

| ---- wc_knobs: FRAM, SPRD, GLID from the record (raw << 8) and the SETUP bytes into the engine.  d2 = track, a3, a4.  Clobbers d0, d1, a0, a1.
wc_knobs:
        tst.l   S_INIT(%a3)
        beq     .Lkb_x
        moveq   #CV_STRIDE,%d0          | SETUP (the live lane's +0x20..+0x25): VIBR VRAT OCT FINE COMP MODE
        muls.l  %d2,%d0
        lea     CURVALS,%a0
        add.l   %d0,%a0
        moveq   #0,%d0
        move.b  LANE_SETUP+5(%a0),%d0
        move.l  %d0,-(%sp)              | mode
        move.b  LANE_SETUP+4(%a0),%d0
        move.l  %d0,-(%sp)              | comp
        move.b  LANE_SETUP+3(%a0),%d0
        move.l  %d0,-(%sp)              | fine
        move.b  LANE_SETUP+2(%a0),%d0
        move.l  %d0,-(%sp)              | oct
        move.b  LANE_SETUP+1(%a0),%d0
        move.l  %d0,-(%sp)              | vrat
        move.b  LANE_SETUP(%a0),%d0
        move.l  %d0,-(%sp)              | vibr
        pea     S_ENG(%a3)
        jsr     wcf_setup
        lea     28(%sp),%sp
        moveq   #0,%d0
        move.w  10(%a4),%d0
        lsr.l   #8,%d0
        move.l  %d0,-(%sp)              | glid
        moveq   #0,%d0
        move.w  8(%a4),%d0
        lsr.l   #8,%d0
        move.l  %d0,-(%sp)              | sprd
        moveq   #0,%d0
        move.w  2(%a4),%d0
        lsr.l   #8,%d0
        move.l  %d0,-(%sp)              | fram
        pea     S_ENG(%a3)
        jsr     wcf_knobs
        lea     16(%sp),%sp
.Lkb_x:
        rts

| ---- wc_voice: a0 := track d2's voice struct + V_POS.  Clobbers d0.
wc_voice:
        move.l  #VOICE_STRIDE,%d0
        muls.l  %d2,%d0
        lea     VOICE_BASE,%a0
        add.l   %d0,%a0
        lea     V_POS(%a0),%a0
        rts

| ============================================================================
| wc_retrig -- Detour 0x4000c634 (8 bytes: `moveal 114(sp),a1; moveb (a0,a1.l),d0`,
| a0 = 0x46104d15): the frame builder's copy of a track's DSP command byte into the
| packer's nibble byte.  On an OCTA303 track any START form becomes the panel key's clean
| 0x30 (Tim's po_retrig, BUILD 37: a sequencer trig on a sounding voice is posted 0x10|n and
| the DSP crossfades its old voice under the new one -- one continuous stream twice, +5.6 dB).
| d0 = the byte, a0 / a1 as stock leaves them; d1 and a2 saved.
| ============================================================================
wc_retrig:
        movea.l 114(%sp),%a1            | displaced: the track
        lea     -8(%sp),%sp
        movem.l %d1/%a2,(%sp)
        move.l  %a1,%d1
        cmp.l   #NTRACKS,%d1
        bcc     .Lrt_out
        lsl.l   #8,%d1                 | track * ST_SIZE (512: 8 + 1)
        add.l   %d1,%d1
        lea     wc_state,%a2
        tst.l   S_LATCHED(%a2,%d1.l)
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_RETRIG
        beq     .Lrt_not                | not an OCTA303 track: the next machine's
        .else
        beq     .Lrt_out                | not an OCTA303 track: stock's byte stands
        .endif
        .else
        beq     .Lrt_out                | not an OCTA303 track: stock's byte stands
        .endif
        moveq   #0,%d1
        move.b  (%a0,%a1.l),%d1
        and.l   #0x30,%d1
        beq     .Lrt_out                | no START of any form
        moveq   #0x30,%d1
        move.b  %d1,(%a0,%a1.l)         | the clean form: a CF START at the frame's first sample
.Lrt_out:
        movem.l (%sp),%d1/%a2
        lea     8(%sp),%sp
        move.b  (%a0,%a1.l),%d0         | displaced: the byte for the packer's nibble byte
        jmp     RETRIG_RET
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_RETRIG
.Lrt_not:                               | entered as its own detour: it replays the load of a1
        movem.l (%sp),%d1/%a2
        lea     8(%sp),%sp
        jmp     MC_NEXT_RETRIG
        .endif
        .endif

| ============================================================================
| wc_page -- Detour 0x40031ece (6 bytes: `move.l 0(a0,d0.l*4),d0; bra.s 0x40031ed6`),
| the page resolver's PLAYBACK table load.  d0 = machine, a0 = table, d3 = track,
| d1 = part index, a1 = bank blob; d2-d5 restored by the resolver's epilogue, d0/d1/a0/a1
| scratch (poly.s po_lfopage's contract).  A FLEX track whose assigned FLEX slot holds a
| TB303* sample gets the TB-303 clone (wc_pgdesc); everything else the stock descriptor.
| ============================================================================
wc_page:
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_PAGE             | the entry state, for the next machine's resolver
        lea     -12(%sp),%sp
        movem.l %d0-%d1/%a0,(%sp)
        .endif
        .endif
        move.l  0(%a0,%d0.l*4),%d0      | displaced: the machine's descriptor
        cmp.l   #FLEX_P,%d0
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_PAGE
        bne     .Lpg_not                | not FLEX: not ours
        .else
        bne     .Lpg_done
        .endif
        .else
        bne     .Lpg_done
        .endif
        move.l  #PART_SIZE,%d2
        muls.l  %d1,%d2
        add.l   %a1,%d2                 | the Part
        move.l  %d0,%d5                 | v7.0: the TB-303 machine's track gets the machine's record
        move.l  %d2,%a0
        adda.l  #PART_OFF,%a0
        move.l  %d3,%d0
        bsr     wc_sig
        tst.l   %d0
        beq     .Lpg_smp
        bsr     wc_mdesc
        bra     .Lpg_done
.Lpg_smp:
.Lpg_stock:
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_PAGE
.Lpg_not:                               | not ours: the next machine's resolver, as its own detour
        movem.l (%sp),%d0-%d1/%a0
        lea     12(%sp),%sp
        jmp     MC_NEXT_PAGE
        .endif
        .endif
        move.l  %d5,%d0
.Lpg_done:
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_PAGE
        lea     12(%sp),%sp
        .endif
        .endif
        jmp     RESOLVER_RET

| ---- wc_fmt_tune: fmt(buf, value), C convention (modules/synth page.s pg_fmt_ptch).  v7.0: TUNE as a
|      note name, raw 64 = C3 (BASE_HZ), a semitone a step: raw 40..88 = C1..C5 ("C1", "C#3", "A4").  The knob,
|      the p-lock display (a trig held) and the page all print through it.  Writes the name itself (no
|      sprintf), returns its length in d0.  Scratch: d0, d1, a0, a1.
wc_fmt_tune:
        move.l  8(%sp),%d0              | raw
        sub.l   #64-36,%d0              | semitones above C0 (C3 = 36)
        bpl     .Lft_lo
        moveq   #0,%d0
.Lft_lo:
        moveq   #95,%d1                 | C0..B7: one octave digit
        cmp.l   %d1,%d0
        ble     .Lft_hi
        move.l  %d1,%d0
.Lft_hi:
        suba.l  %a1,%a1                 | the octave
.Lft_oct:
        moveq   #12,%d1
        cmp.l   %d1,%d0
        blt     .Lft_name
        sub.l   %d1,%d0
        addq.l  #1,%a1
        bra     .Lft_oct
.Lft_name:
        move.l  %a1,%d1
        lea     wc_notes,%a1
        add.l   %d0,%a1
        add.l   %d0,%a1                 | two bytes a name
        move.l  4(%sp),%a0              | buf
        move.b  (%a1)+,(%a0)+
        moveq   #0,%d0
        move.b  (%a1),%d0
        cmp.l   #0x20,%d0               | "C " or "C#"
        beq     .Lft_dig
        move.b  %d0,(%a0)+
.Lft_dig:
        add.l   #0x30,%d1
        move.b  %d1,(%a0)+
        clr.b   (%a0)
        move.l  %a0,%d0
        sub.l   4(%sp),%d0              | the length
        rts

| ============================================================================
| wc_chrom -- Detour 0x4004fc58 (jsr + 2 nops over 10 bytes: `lea (4,a2,a2.l*4),a2;
| mvz.b 0x100b14cf,d0`), the CHROMATIC key handler 0x4004fb94 (track d2, key index a2 =
| 0..24, 12 = TRIG 13) about to make the raw pitch 5 * idx + 4 that the voice is trigged with,
| a held or live-recorded trig's PTCH lock receives and the screen shows.  On a 303 track
| (FLEX, its slot's sample TB303*) the byte is semitones (v6.4): raw = 52 + idx = -12..+12, so
| keys and recorded locks play what they say (the knob and the locks reach +24).  Every other
| track: the stock lea.  The quantizer module's qz_chrom owns the same site: beside it, HOOKS
| overrides qz_chrom's detour and this one, built with HK_CHROM_PITCH, hands every other track
| to qz_chrom (modules/hooks, chrom_pitch).  Scratch: d0, d1, a0, a1 (as qz_chrom).
| ============================================================================
wc_chrom:
        movea.l BANK_PTR,%a0
        mvz.b   PART_IDX,%d0
        move.l  #PART_SIZE,%d1
        muls.l  %d1,%d0
        adda.l  %d0,%a0                 | the Part
        move.l  %a0,%a1
        adda.l  #MACH_OFF,%a1
        mvz.b   (%a1,%d2.l),%d0         | the track's machine
        cmp.l   #1,%d0                  | FLEX
        bne     .Lch_stock
        move.l  %a0,-(%sp)              | v7.0: the TB-303 machine
        adda.l  #PART_OFF,%a0
        move.l  %d2,%d0
        bsr     wc_sig
        move.l  (%sp)+,%a0
        tst.l   %d0
        beq     .Lch_stock
.Lch_303:
        lea     64-12(%a2),%a2          | a 303: raw = 64 + (idx - 12) = 52 + idx (semitones)
        bra     .Lch_out
.Lch_stock:
        .if     HK_CHROM_PITCH          | beside SCALE QUANTIZER / WAVE CF (modules/hooks, chrom_pitch):
        hk_chrom_next                   | every other track is the next one's (SCALE QUANTIZER's has the stock lea in it)
        .else
        move.l  %a2,%d0                 | displaced (as plain arithmetic): raw = 5 * idx + 4
        lsl.l   #2,%d0
        add.l   %a2,%d0
        addq.l  #4,%d0
        move.l  %d0,%a2
        .endif
.Lch_out:
        mvz.b   PART_IDX,%d0            | displaced: the part
        rts


| ---- wc_amp: the DSP's AMP ATK for this track is at least AMP_ATK_MIN.  The voices run from the first START and the AMP
|      envelope gates them: an attack of 0 steps the tone each time the envelope reopens (measured under the port: the second
|      difference 900x a clean sine's; ATK 10: none).  The DSP voice record is VREC + ping * 0x200 + 64 * track, halfword 0 =
|      ATK << 8 (the frame builder wrote it before this call; modules/cxosc po_amp_snap overrides it the same way).
|      d2 = track.  Clobbers d0, d1, a0.
wc_amp:
        move.l  PINGW,%d0
        lsl.l   #8,%d0
        add.l   %d0,%d0                 | ping * 0x200
        move.l  %d2,%d1
        lsl.l   #6,%d1                  | 64 * track
        add.l   %d1,%d0
        lea     VREC,%a0
        add.l   %d0,%a0
        mvz.w   (%a0),%d0
        cmp.l   #AMP_ATK_MIN<<8,%d0
        bcc     .Lam_x
        move.w  #AMP_ATK_MIN<<8,(%a0)
.Lam_x:
        rts

| ---- wc_pword: d0 = PTCH frame word -> d0 = p (Q8 semitones above C3).  Raw 64 = 0; one raw unit a semitone;
|      clamped to P_LO..P_HI (-36..+36).  Clobbers d1.
wc_pword:
        sub.l   #0x4000,%d0
        move.l  #P_LO-P_CENTER,%d1
        cmp.l   %d1,%d0
        bge     .Lpw1
        move.l  %d1,%d0
.Lpw1:
        move.l  #P_HI-P_CENTER,%d1
        cmp.l   %d1,%d0
        ble     .Lpw2
        move.l  %d1,%d0
.Lpw2:
        rts

        .if     HK_MACHINE_ROWS
        .set    WC_ROW,         MC_ROW          | beside other machines: our place in the chain (modules/hooks)
        .global wc_type, wc_title, wc_publish
        .else
        .set    WC_ROW,         5               | the machine's row and UI type
        .endif
        .set    SIG_OFF,        0x3c            | Part' + 0x3c + 30*track: 'T', 'B', 1
        .set    SRAM_PART,      0x100a4ece      | the shadow of Part 0's Part' (PB_SHADOW + PART_OFF)
        .set    SRC_CURSOR,     0x460d5c30      | SRC SETUP's selected row
        .set    PB_TABLE,       0x400d5f38      | the PLAYBACK records by UI type (5: stock NEIGHBOR's)
        .set    STOCK_DEFS,     0x400d320c      | FLEX_P + 0x5e: FLEX's twelve defaults
        .set    PAGE2_GAP,      0x1b0           | SETUP bytes - PLAYBACK bytes (0x1da - 0x2a)

        .global wc_machine_name, wc_src_names, wc_name_a, wc_name_b, wc_setup_row, wc_chooser_row
        .global wc_setup_open, wc_chooser_open, wc_tick, wc_main_commit, wc_src_commit, wc_src_commit2
        .global wc_setup_edit6, wc_setup_draw6, wc_validate

| ---- wc_sig: a0 = Part', d0 = track -> d0 = 1 when the track is the TB-303 machine (FLEX, signed),
|      else 0 (flags set).  Clobbers d1.
wc_sig:
        move.l  %a1,-(%sp)
        moveq   #7,%d1
        cmp.l   %d1,%d0
        bhi     .Lsg_no
        moveq   #0,%d1
        move.b  0x22(%a0,%d0.l),%d1
        subq.l  #1,%d1                  | FLEX
        bne     .Lsg_no
        moveq   #30,%d1
        muls.l  %d0,%d1
        move.l  %a0,%a1
        add.l   %d1,%a1
        moveq   #0,%d1
        move.b  SIG_OFF(%a1),%d1
        cmp.l   #0x57,%d1               | 'W'
        bne     .Lsg_no
        move.b  SIG_OFF+1(%a1),%d1
        cmp.l   #0x56,%d1               | 'V'
        bne     .Lsg_no
        move.b  SIG_OFF+2(%a1),%d1
        cmp.l   #1,%d1
        bne     .Lsg_no
        moveq   #1,%d0
        bra     .Lsg_x
.Lsg_no:
        moveq   #0,%d0
.Lsg_x:
        move.l  (%sp)+,%a1
        tst.l   %d0
        rts

| ---- wc_curpart: a0 = the current part's Part', d1 = 1 (0 when the bank pointer is not set: a0 junk).
wc_curpart:
        move.l  BANK_PTR,%d1
        cmp.l   #0x40000000,%d1
        bcs     .Lcp_no
        move.l  %d1,%a0
        adda.l  #PART_OFF,%a0
        mvz.b   PART_IDX,%d1
        and.l   #3,%d1
        move.l  %d0,-(%sp)
        move.l  #PART_SIZE,%d0
        muls.l  %d0,%d1
        add.l   %d1,%a0
        move.l  (%sp)+,%d0
        moveq   #1,%d1
        rts
.Lcp_no:
        moveq   #0,%d1
        rts

| ---- wc_sigcur: d0 = track -> d0 = 1 when it is the TB-303 machine in the current part.  Clobbers d1, a0.
wc_sigcur:
        bsr     wc_curpart
        tst.l   %d1
        bne     wc_sig
        moveq   #0,%d0
        rts

| ---- the limit: WC_MAX signed tracks in a Part.  Each voice costs about 9 points of the ColdFire's frame interrupt
|      and the first about 21 more (one MKII, 2 Nov 2026: 2 machines 65 %, 4 machines 83 %, ~102 % extrapolated for 6),
|      and the panel starves near 98 %.
        .if     HK_MACHINE_ROWS
        .set    WC_MAX,         MC_LIMIT        | beside other machines: one limit for all of them (modules/hooks)
        .else
        .set    WC_MAX,         2
        .endif

| ---- wc_anysig: a0 = Part', d0 = track -> d0 = 1 when the track is FLEX and signed by ANY machine on
|      the list (the three signature bytes against mc_sig_table), else 0 (flags set).  Clobbers d1; a0, a1 kept.
|      The limit counts these, so a Part holds WC_MAX machines of every kind together.
        .if     HK_MACHINE_ROWS
wc_anysig:
        lea     -8(%sp),%sp
        movem.l %a0-%a1,(%sp)
        moveq   #7,%d1
        cmp.l   %d1,%d0
        bhi     .Lmca_no
        moveq   #0,%d1
        move.b  0x22(%a0,%d0.l),%d1
        subq.l  #1,%d1                  | FLEX
        bne     .Lmca_no
        moveq   #30,%d1
        muls.l  %d0,%d1
        move.l  %a0,%a1
        add.l   %d1,%a1
        mvz.b   SIG_OFF(%a1),%d0
        lsl.l   #8,%d0
        mvz.b   SIG_OFF+1(%a1),%d1
        or.l    %d1,%d0
        lsl.l   #8,%d0
        mvz.b   SIG_OFF+2(%a1),%d1
        or.l    %d1,%d0                 | d0 = the 24-bit signature
        lea     wc_sigtab,%a0
.Lmca_l:
        move.l  (%a0)+,%d1
        beq     .Lmca_no
        cmp.l   %d1,%d0
        bne     .Lmca_l
        moveq   #1,%d0
        bra     .Lmca_x
.Lmca_no:
        moveq   #0,%d0
.Lmca_x:
        movem.l (%sp),%a0-%a1
        lea     8(%sp),%sp
        tst.l   %d0
        rts
wc_sigtab:
        mc_sig_table
        .macro  WC_ANYSIG
        bsr     wc_anysig
        .endm
        .else
        .macro  WC_ANYSIG
        bsr     wc_sig
        .endm
        .endif

| ---- wc_nsigned: a0 = Part', d0 = a track -> d0 = the signed tracks of the Part other than that one.  Saves all else.
wc_nsigned:
        lea     -16(%sp),%sp
        movem.l %d1-%d4,(%sp)
        move.l  %d0,%d3
        moveq   #0,%d2
        moveq   #7,%d4
.Lnsg_l:
        cmp.l   %d3,%d4
        beq     .Lnsg_n
        move.l  %d4,%d0
        WC_ANYSIG
        add.l   %d0,%d2
.Lnsg_n:
        subq.l  #1,%d4
        bpl     .Lnsg_l
        move.l  %d2,%d0
        movem.l (%sp),%d1-%d4
        lea     16(%sp),%sp
        rts

| ---- wc_sigcur_lim: d0 = track -> d0 = 1 when it is a signed track among the first WC_MAX of the current Part
|      (a project loaded with more has the rest play as plain FLEX).  Clobbers d1, a0.
wc_sigcur_lim:
        move.l  %d0,-(%sp)
        bsr     wc_sigcur
        beq     .Llim_x
        bsr     wc_curpart                      | a0 = Part'
        move.l  (%sp),%d0
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        move.l  %d0,%d3
        moveq   #0,%d2                          | the signed tracks below this one
        subq.l  #1,%d3
        bmi     .Llim_cnt
.Llim_l:
        move.l  %d3,%d0
        WC_ANYSIG
        add.l   %d0,%d2
        subq.l  #1,%d3
        bpl     .Llim_l
.Llim_cnt:
        moveq   #0,%d0
        cmp.l   #WC_MAX,%d2
        bcc     .Llim_no
        moveq   #1,%d0
.Llim_no:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
.Llim_x:
        addq.l  #4,%sp
        tst.l   %d0
        rts

| ---- wc_type (ANALOG BD's ab_type): d0 = a machine byte, a0 = where it was read -> d0 = WC_ROW when
|      the byte is the current part's track machine byte (Part' + 0x22 + track) of a signed track,
|      else d0 unchanged.  Everything else kept.
wc_type:
        lea     -12(%sp),%sp
        movem.l %d1/%a0-%a1,(%sp)
        moveq   #1,%d1
        cmp.l   %d1,%d0
        bne     .Lty_x
        move.l  %a0,%a1
        bsr     wc_curpart
        tst.l   %d1
        beq     .Lty_1
        move.l  %a1,%d1
        sub.l   %a0,%d1
        sub.l   #0x22,%d1               | the track, if a1 is a machine byte
        cmp.l   #7,%d1
        bhi     .Lty_1
        move.l  %d1,%d0
        bsr     wc_sig
        beq     .Lty_1
        moveq   #WC_ROW,%d0
        bra     .Lty_x
.Lty_1:
        moveq   #1,%d0
.Lty_x:
        movem.l (%sp),%d1/%a0-%a1
        lea     12(%sp),%sp
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_TYPE
        cmp.l   #WC_ROW,%d0
        beq     .Lty_rts
        jmp     MC_NEXT_TYPE            | not ours: the next machine's (it keeps all but d0)
.Lty_rts:
        .endif
        .endif
        rts

| ---- wc_sigwrite (ab_sig_write): a0 = Part' (in the bank blob), d0 = track, d1 = 1 sign / 0 unsign,
|      in the Part and its shadow.  Signing an unsigned copy first writes the machine's twelve defaults
|      (wc_mdefs) into its FLEX PLAYBACK and SETUP bytes; unsigning clears our signature only.  A
|      signed track of the current part gets its twelve bytes into the live lane too.  Everything kept.
wc_sigwrite:
        lea     -20(%sp),%sp
        movem.l %d0-%d2/%a0-%a1,(%sp)
        tst.l   %d1
        beq     .Lsw_ok                 | unsigning is never refused
        bsr     wc_nsigned              | signing: a third machine in the Part is refused (the callers store FLEX)
        cmp.l   #WC_MAX,%d0
        bcs     .Lsw_ok
        pea     0x30
        pea     wc_maxmsg
        jsr     NOTIFY
        addq.l  #8,%sp
        movem.l (%sp),%d0-%d2/%a0-%a1
        lea     20(%sp),%sp
        rts
.Lsw_ok:
        move.l  (%sp),%d0
        moveq   #30,%d2
        muls.l  %d2,%d0
        move.l  %a0,%a1
        add.l   %d0,%a1
        lea     SIG_OFF(%a1),%a1
        bsr     .Lsw_one
        move.l  %a1,%d2                 | the shadow: Part' - BANK - PART_OFF + SRAM_PART
        sub.l   BANK_PTR,%d2
        sub.l   #PART_OFF,%d2
        add.l   #SRAM_PART,%d2
        move.l  %d2,%a1
        bsr     .Lsw_one
        tst.l   %d1                     | signed, in the current part: the live lane now, as the Part
        beq     .Lsw_done               | (the frame builder refreshes it only at the next trig or edit)
        move.l  12(%sp),%a1             | Part'
        bsr     wc_curpart
        tst.l   %d1
        beq     .Lsw_done
        cmp.l   %a0,%a1
        bne     .Lsw_done
        move.l  (%sp),%d0               | the track
        moveq   #CV_STRIDE,%d2
        muls.l  %d0,%d2
        lea     CURVALS,%a0
        add.l   %d2,%a0
        moveq   #30,%d2
        muls.l  %d0,%d2
        add.l   %d2,%a1
        lea     0x30(%a1),%a1           | the FLEX PLAYBACK bytes
        moveq   #6,%d0
.Lsw_l:
        move.b  PAGE2_GAP(%a1),%d2
        move.b  %d2,LANE_SETUP(%a0)
        move.b  (%a1)+,%d2
        move.b  %d2,(%a0)+
        subq.l  #1,%d0
        bne     .Lsw_l
        move.l  12(%sp),%a1             | Part': the AMP bytes (seeded above, or the author's) into the lane's slots 12..14
        move.l  (%sp),%d0
        moveq   #24,%d2
        muls.l  %d0,%d2
        lea     AMP_PAGE(%a1),%a1
        adda.l  %d2,%a1
        move.b  (%a1),%d2
        move.b  %d2,6(%a0)
        move.b  1(%a1),%d2
        move.b  %d2,7(%a0)
        move.b  2(%a1),%d2
        move.b  %d2,8(%a0)
.Lsw_done:
        movem.l (%sp),%d0-%d2/%a0-%a1
        lea     20(%sp),%sp
        rts
.Lsw_one:                               | a1 = a copy's signature; clobbers d0, d2, a0
        moveq   #0,%d0                  | d0 = 1: this copy is signed
        moveq   #0,%d2
        move.b  (%a1),%d2
        cmp.l   #0x57,%d2
        bne     .Lsw_s
        move.b  1(%a1),%d2
        cmp.l   #0x56,%d2
        bne     .Lsw_s
        move.b  2(%a1),%d2
        cmp.l   #1,%d2
        bne     .Lsw_s
        moveq   #1,%d0
.Lsw_s:
        tst.l   %d1
        beq     .Lsw_clr
        tst.l   %d0
        bne     .Lsw_x                  | signed already: the author's knobs stand
        lea     wc_mdefs,%a0
        lea     -12(%a1),%a1            | the FLEX PLAYBACK bytes (Part' + 0x30 + 30*track)
        moveq   #6,%d0
.Lsw_d:
        move.b  6(%a0),%d2
        move.b  %d2,PAGE2_GAP(%a1)      | SETUP
        move.b  (%a0)+,%d2
        move.b  %d2,(%a1)+              | PLAYBACK
        subq.l  #1,%d0
        bne     .Lsw_d
        lea     6(%a1),%a1
        move.l  4(%sp),%d2              | the track (the caller's saved d0, below the return address)
        move.l  %d2,%d0
        add.l   %d0,%d0
        add.l   %d2,%d0
        add.l   %d0,%d0                 | 6 * track
        lea     AMP_PAGE-SIG_OFF(%a1),%a0
        suba.l  %d0,%a0                 | Part' + AMP_PAGE + 24 * track: a1 = Part' + SIG_OFF + 30 * track
        moveq   #AMP_ATK,%d2
        move.b  %d2,(%a0)
        moveq   #AMP_HOLD,%d2
        move.b  %d2,1(%a0)
        moveq   #AMP_REL,%d2
        move.b  %d2,2(%a0)
        moveq   #0x57,%d2
        move.b  %d2,(%a1)
        moveq   #0x56,%d2
        move.b  %d2,1(%a1)
        moveq   #1,%d2
        move.b  %d2,2(%a1)
        rts
.Lsw_clr:
        tst.l   %d0
        beq     .Lsw_x
        clr.b   (%a1)
        clr.b   1(%a1)
        clr.b   2(%a1)
.Lsw_x:
        rts

| ---- wc_mdesc: d0 = the machine's record (built once).  Clobbers d0, d1, a0, a1.
wc_mdesc:
        lea     FLEX_P,%a0
        lea     wc_mover,%a1
        moveq   #1,%d1
        bra     wc_clone

| ---- the hooks (ANALOG BD's, the same sites and contracts) ---------------------------------------
| wc_machine_name -- Detour 0x400334d8 (`move.l d2,-(sp); move.l 8(sp),d1`): name(row) -> d0.
wc_machine_name:
        move.l  4(%sp),%d0
        cmp.l   #WC_ROW,%d0
        beq     .Lmn_303
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_NAME
        jmp     MC_NEXT_NAME            | not our row: the next machine's
        .endif
        .endif
        move.l  %d2,-(%sp)
        move.l  8(%sp),%d1
        jmp     0x400334de
.Lmn_303:
        lea     wc_title,%a0
        move.l  %a0,%d0
        rts

| wc_src_names -- the lea at 0x4003c928: SRC SETUP's names, six rows.
        .align  4
wc_src_names:
        .long   0x400b3eac, 0x400b3e98, 0x400b7c67, 0x400b5413, 0x400b7a63, wc_title
        .if     HK_MACHINE_ROWS
        mc_names_tail                   | the other machines' names, in row order
        .endif

| wc_name_a / wc_name_b -- Detours 0x4003d718 / 0x4004c36a (`lea 0x400a78c8,a0`; then d1 = name[d0]).
wc_name_a:
        bsr     wc_name_pick
        jmp     0x4003d722
wc_name_b:
        bsr     wc_name_pick
        jmp     0x4004c374
wc_name_pick:
        bsr     wc_type
        lea     wc_src_names,%a0
        move.l  (%a0,%d0.l*4),%d1
        rts


| wc_setup_row -- Detour 0x4003c980 (`mvs.b (a0),d0; lea 24(sp),sp`): the row SRC SETUP highlights.
wc_setup_row:
        mvs.b   (%a0),%d0
        lea     24(%sp),%sp
        bsr     wc_type
        jmp     0x4003c986

| wc_chooser_row -- Detour 0x400786c8 (`mvs.b (a0),d0; cmp.l d0,d2; bne 0x400786fc`).
wc_chooser_row:
        mvs.b   (%a0),%d0
        bsr     wc_type
        cmp.l   %d0,%d2
        bne     .Lcr_no
        jmp     0x400786ce
.Lcr_no:
        jmp     0x400786fc

| wc_setup_open -- Detour 0x400585dc (`move.b (a0),d3; mvs.b d3,d4; pea 0x400bb704`).
wc_setup_open:
        move.b  (%a0),%d3
        move.l  %d0,-(%sp)
        mvs.b   %d3,%d0
        bsr     wc_type
        move.l  %d0,%d3
        move.l  (%sp)+,%d0
        mvs.b   %d3,%d4
        pea     0x400bb704
        jmp     0x400585e6

| wc_chooser_open -- Detour 0x40078886 (`mvs.b (a0),d0; move.l d0,-(sp); pea 0x460e7386`).
wc_chooser_open:
        mvs.b   (%a0),%d0
        bsr     wc_type
        move.l  %d0,-(%sp)
        pea     0x460e7386
        jmp     0x40078890

| wc_tick -- Detour 0x4005221e (`jsr 0x4005213c; jsr 0x4007e940`): publish the machine's record as UI
| type 5's (the SETUP editor and drawer index PB_TABLE by the type wc_type returns).
wc_tick:
        jsr     0x4005213c
        jsr     0x4007e940
        bsr     wc_mdesc
        move.l  %d0,PB_TABLE+4*WC_ROW
        .if     HK_MACHINE_ROWS
        mc_publish                      | each other machine's record as its row's type
        .endif
        jmp     0x40052228
        .if     HK_MACHINE_ROWS
| wc_publish -- the same record from ANALOG BD's tick hook (ab_tick_hook), which owns the site.
wc_publish:
        bsr     wc_mdesc
        move.l  %d0,PB_TABLE+4*WC_ROW
        rts
        .endif

| wc_main_commit -- Detour 0x4007981c (`mvs.b (a0),d3; move.b d4,(a0); add.l d1,d0`): the machine list's
| commit, a1 = bank, d0 = part * PART_SIZE, d1 = track, d4 = the row.  Row 5 signs the track and stores FLEX.
wc_main_commit:
        lea     -12(%sp),%sp
        movem.l %d0-%d1/%a0,(%sp)
        movea.l %a1,%a0
        adda.l  %d0,%a0
        adda.l  #PART_OFF,%a0
        move.l  %d1,%d0
        moveq   #0,%d1
        cmp.l   #WC_ROW,%d4
        bne     .Lmc_w
        moveq   #1,%d1
        moveq   #1,%d4                  | FLEX
.Lmc_w:
        bsr     wc_sigwrite
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_MAIN_COMMIT
        tst.l   %d1                     | 0: not our row (wc_sigwrite keeps d1)
        bne     .Lmc_ours
        movem.l (%sp),%d0-%d1/%a0
        lea     12(%sp),%sp
        jmp     MC_NEXT_MAIN_COMMIT     | the next machine signs its row; the last stores stock's
.Lmc_ours:
        .endif
        .endif
        movem.l (%sp),%d0-%d1/%a0
        lea     12(%sp),%sp
        mvs.b   (%a0),%d3
        move.b  %d4,(%a0)
        add.l   %d1,%d0
        jmp     0x40079822

| wc_src_commit / 2 -- Detours 0x4005a616 / 0x4005a850 (`move.l SRC_CURSOR,d1`, then `move.b d1,(a0)`):
| SRC SETUP's two commits, a1 = bank, d0 = part * PART_SIZE, d2 = track.
wc_src_commit:
        pea     0x4005a61c
        bra     .Lsrc
wc_src_commit2:
        pea     0x4005a856
.Lsrc:
        move.l  SRC_CURSOR,%d1
        lea     -12(%sp),%sp
        movem.l %d0/%d2/%a0,(%sp)
        movea.l %a1,%a0
        adda.l  %d0,%a0
        adda.l  #PART_OFF,%a0
        move.l  %d2,%d0
        cmp.l   #WC_ROW,%d1
        bne     .Lsrc_o
        moveq   #1,%d1
        bsr     wc_sigwrite
        moveq   #1,%d1                  | FLEX
        bra     .Lsrc_go
.Lsrc_o:
        move.l  %d1,-(%sp)
        moveq   #0,%d1
        bsr     wc_sigwrite
        move.l  (%sp)+,%d1
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_SRC_COMMIT
        movem.l (%sp),%d0/%d2/%a0
        lea     12(%sp),%sp
        move.l  (%sp)+,%d1              | our continuation: the next machine's commit pushes its own
        cmp.l   #0x4005a61c,%d1
        bne     .Lsrc_n2
        jmp     MC_NEXT_SRC_COMMIT
.Lsrc_n2:
        jmp     MC_NEXT_SRC_COMMIT2
        .endif
        .endif
.Lsrc_go:
        movem.l (%sp),%d0/%d2/%a0
        lea     12(%sp),%sp
        rts

| wc_setup_edit6 / wc_setup_draw6 -- Detours 0x4003a52e / 0x4003cd98 (6 * machine): SETUP's editor and
| drawer address the machine's bytes as FLEX's (Part' + 0x1da + 6 * 1 + 30 * track).
wc_setup_edit6:
        .if     HK_MACHINE_ROWS
        cmp.l   #5,%d2                  | any machine's row (ours and the others'): FLEX's bytes
        bcs     .Le6
        cmp.l   #MC_ROWS_END,%d2
        bcc     .Le6
        moveq   #1,%d2
        .else
        cmp.l   #WC_ROW,%d2
        bne     .Le6
        moveq   #1,%d2
        .endif
.Le6:
        move.l  %d2,%d0
        lsl.l   #3,%d0
        add.l   %d2,%d2
        sub.l   %d2,%d0
        jmp     0x4003a536
wc_setup_draw6:
        .if     HK_MACHINE_ROWS
        cmp.l   #5,%d6
        bcs     .Ld6
        cmp.l   #MC_ROWS_END,%d6
        bcc     .Ld6
        moveq   #1,%d6
        .else
        cmp.l   #WC_ROW,%d6
        bne     .Ld6
        moveq   #1,%d6
        .endif
.Ld6:
        move.l  %d6,%d7
        lsl.l   #3,%d7
        add.l   %d6,%d6
        sub.l   %d6,%d7
        jmp     0x4003cda0

| wc_validate -- Detour 0x40002318 (the Part validator's entry, `lea -96(sp),sp; movem.l ...`),
| validate(Part'): the stock validator sees FLEX's defaults in each signed track's twelve PLAYBACK and
| SETUP bytes (FINE SLID DRIV are 0..127 where FLEX's LEN RATE TSTR clamp to 0..3); ours are restored.
wc_validate:
        lea     -112(%sp),%sp           | 96: the saved bytes (12 a track), 16: d2, d3, a2, a3
        movem.l %d2-%d3/%a2-%a3,96(%sp)
        move.l  116(%sp),%a2            | Part'
        moveq   #0,%d3                  | the signed tracks' mask
        moveq   #0,%d2
.Lv_t:
        move.l  %d2,%d0
        move.l  %a2,%a0
        bsr     wc_sig
        beq     .Lv_n
        .if     HK_MACHINE_ROWS
        bsr     wc_vcount               | the limit: every machine's tracks below this one (d0 = their count)
        .else
        move.l  %d3,%d1                 | the limit: d3 holds the signed tracks kept so far, all below this one
        moveq   #0,%d0
.Lv_pc:
        lsr.l   #1,%d1
        bcc     .Lv_nc
        addq.l  #1,%d0
.Lv_nc:
        tst.l   %d1
        bne     .Lv_pc
        .endif
        cmp.l   #WC_MAX,%d0
        bcs     .Lv_keep
        moveq   #30,%d0                 | a third signed track (a loaded project): unsign it, the stock
        muls.l  %d2,%d0                 | validator then clamps its bytes as FLEX's
        lea     SIG_OFF(%a2),%a1
        adda.l  %d0,%a1
        clr.b   (%a1)+
        clr.b   (%a1)+
        clr.b   (%a1)
        bra     .Lv_n
.Lv_keep:
        moveq   #1,%d0
        lsl.l   %d2,%d0
        or.l    %d0,%d3
        bsr     wc_vptr                 | a0 = the PLAYBACK bytes, a1 = the save slot
        lea     STOCK_DEFS,%a3
        moveq   #6,%d1
.Lv_s:
        move.b  (%a0),%d0
        move.b  %d0,(%a1)
        move.b  PAGE2_GAP(%a0),%d0
        move.b  %d0,6(%a1)
        move.b  (%a3),%d0
        move.b  %d0,(%a0)
        move.b  6(%a3),%d0
        move.b  %d0,PAGE2_GAP(%a0)
        addq.l  #1,%a0
        addq.l  #1,%a1
        addq.l  #1,%a3
        subq.l  #1,%d1
        bne     .Lv_s
.Lv_n:
        addq.l  #1,%d2
        moveq   #8,%d0
        cmp.l   %d0,%d2
        blt     .Lv_t
        move.l  %a2,-(%sp)
        jsr     wc_stock_validate
        addq.l  #4,%sp
        move.l  %d0,%a3                 | the validator's result
        moveq   #0,%d2
.Lv_r:
        btst    %d2,%d3
        beq     .Lv_rn
        bsr     wc_vptr
        moveq   #6,%d1
.Lv_rr:
        move.b  (%a1),%d0
        move.b  %d0,(%a0)
        move.b  6(%a1),%d0
        move.b  %d0,PAGE2_GAP(%a0)
        addq.l  #1,%a0
        addq.l  #1,%a1
        subq.l  #1,%d1
        bne     .Lv_rr
.Lv_rn:
        addq.l  #1,%d2
        moveq   #8,%d1
        cmp.l   %d1,%d2
        blt     .Lv_r
        move.l  %a3,%d0
        movem.l 96(%sp),%d2-%d3/%a2-%a3
        lea     112(%sp),%sp
        rts
wc_vptr:                                | d2 = track, a2 = Part' -> a0 = Part' + 0x30 + 30*track, a1 = 4 + sp + 12*track
        moveq   #30,%d0
        muls.l  %d2,%d0
        lea     0x30(%a2),%a0
        add.l   %d0,%a0
        moveq   #12,%d0
        muls.l  %d2,%d0
        lea     4(%sp),%a1
        add.l   %d0,%a1
        rts
        .if     HK_MACHINE_ROWS
| ---- wc_vcount: d2 = track, a2 = Part' -> d0 = the tracks below d2 signed by any machine.  Saves all else.
|      (wc_validate's limit: one count for every kind of machine; an own track past it was unsigned in place.)
wc_vcount:
        lea     -12(%sp),%sp
        movem.l %d2-%d3/%a0,(%sp)
        moveq   #0,%d3
        subq.l  #1,%d2
        bmi     .Lvcn_x
.Lvcn_l:
        move.l  %d2,%d0
        move.l  %a2,%a0
        bsr     wc_anysig
        add.l   %d0,%d3
        subq.l  #1,%d2
        bpl     .Lvcn_l
.Lvcn_x:
        move.l  %d3,%d0
        movem.l (%sp),%d2-%d3/%a0
        lea     12(%sp),%sp
        rts
        .endif
wc_stock_validate:
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_VALIDATE
        jmp     MC_NEXT_VALIDATE        | the next machine's tracks, then stock
        .endif
        .endif
        lea     -96(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        jmp     0x40002320
| wc_pgdesc / wc_lfodesc (a1 = override list) -> d0 = the TB-303 PLAYBACK / LFO descriptor:
| a RAM clone of the stock record (built once, from the user's own ROM) with the listed
| fields replaced.  Called inside the page resolver: may clobber d0/d1/a0/a1 only.
| ============================================================================
wc_pgdesc:
        lea     FLEX_P,%a0
        moveq   #0,%d1
wc_clone:                               | a0 = stock record, a1 = list, d1 = 0 PLAYBACK / 1 LFO
        lea     -12(%sp),%sp
        movem.l %d2/%a2-%a3,(%sp)
        move.l  %d1,%d2
        move.l  #WC_DLEN,%d0            | v7.0: record d2 of wc_desc (0 the PLAYBACK clone, 1 the machine)
        muls.l  %d2,%d0
        lea     wc_desc,%a2
        add.l   %d0,%a2
        lea     wc_built,%a3
        tst.b   (%a3,%d2.l)
        bne     .Lclhave
        move.l  %a2,%a3
        move.l  #FLEX_DESC_LEN,%d1      | (both records are 0x192 bytes)
.Lclcp:
        move.b  (%a0)+,(%a3)+
        subq.l  #1,%d1
        bne     .Lclcp
.Lclpatch:
        mvs.w   (%a1)+,%d0
        bmi     .Lclbuilt
        mvz.w   (%a1)+,%d1
        move.l  (%a1)+,%a0
        tst.l   %d1
        beq     .Lclpatch
        move.l  %a2,%a3
        add.l   %d0,%a3
.Lclb:
        move.b  (%a0)+,(%a3)+
        subq.l  #1,%d1
        bne     .Lclb
        bra     .Lclpatch
.Lclbuilt:
        lea     wc_built,%a3
        moveq   #1,%d0
        move.b  %d0,(%a3,%d2.l)
.Lclhave:
        move.l  %a2,%d0
        movem.l (%sp),%d2/%a2-%a3
        lea     12(%sp),%sp
        rts


| ---- the page clone's fields (octa303.s wc_over): TUNE FRAM CHRD VOIC ATK REL, P+0x16 + 6 * slot names,
|      defaults P+0x5f (slots 1..5), minimums P+0x6a and counts P+0x9a (longs), formatters P+0xca, knob
|      handlers P+0x12a (0: one raw a detent).  TUNE is semitones: raw 40..88 = -24..+24, 64 = C3.
        .align  4
wc_mover:
        .short  0x009, 9
        .long   wc_title
        .short  0x016, 36
        .long   wc_names
        .short  0x05f, 5
        .long   wc_defaults
        .short  0x06a, 24
        .long   wc_mins
        .short  0x09a, 24
        .long   wc_cnts
        .short  0x0ca, 24
        .long   wc_fmts
        .short  0x12a, 24
        .long   wc_zero6
        .short  0x03a, 36                       | SETUP's names
        .long   wc_snames
        .short  0x064, 6                        | defaults
        .long   wc_mdefs+6
        .short  0x082, 24                       | minimums
        .long   wc_zero6
        .short  0x0b2, 24                       | counts
        .long   wc_scnt
        .short  0x0e2, 24                       | formatters
        .long   wc_sfmts
        .short  0x112, 24                       | no list handlers
        .long   wc_zero6
        .short  0x142, 24
        .long   wc_zero6
        .short  0x18a, 8                        | slot flags: SETUP's six plain, PLAYBACK's as FLEX's
        .long   wc_mflags
        .short  -1, 0
        .long   0
wc_scnt:                                | VIBR VRAT OCT FINE COMP MODE
        .long   128, 128, 3, 128, 128, 2
wc_sfmts:
        .long   FMT_PLAIN, FMT_PLAIN, wc_fmt_oct, wc_fmt_fine, FMT_PLAIN, wc_fmt_mode
wc_mflags:
        .long   0x00001111, 0x11311311
wc_snames:
        .ascii  "VIBR"
        .byte   0, 0
        .ascii  "VRAT"
        .byte   0, 0
        .ascii  "OCT"
        .byte   0, 0, 0
        .ascii  "FINE"
        .byte   0, 0
        .ascii  "COMP"
        .byte   0, 0
        .ascii  "MODE"
        .byte   0, 0
wc_loct:
        .asciz  "-1"
        .byte   0, 0, 0
        .asciz  "0"
        .byte   0, 0, 0, 0
        .asciz  "+1"
        .byte   0, 0, 0
wc_lmode:
        .asciz  "CHORD"
        .asciz  "POLY"
        .byte   0, 0
wc_mins:
        .long   64 + TUNE_LO, 0, 0, 0, 0, 0
wc_cnts:
        .long   TUNE_HI - TUNE_LO + 1, 128, 32, 4, 128, 128
wc_zero6:
        .long   0, 0, 0, 0, 0, 0
wc_fmts:
        .long   wc_fmt_tune, FMT_PLAIN, wc_fmt_chrd, wc_fmt_voic, FMT_PLAIN, FMT_PLAIN
wc_title:
        .ascii  "WAVE"
        .byte   0, 0, 0, 0, 0
wc_names:
        .ascii  "TUNE"
        .byte   0, 0
        .ascii  "FRAM"
        .byte   0, 0
        .ascii  "CHRD"
        .byte   0, 0
        .ascii  "VOIC"
        .byte   0, 0
        .ascii  "SPRD"
        .byte   0, 0
        .ascii  "GLID"
        .byte   0, 0
wc_defaults:                            | FRAM CHRD VOIC SPRD GLID: a chord, MAJ on three voices (VOIC raw 2)
        .byte   0, 3, 2, 0, 0
wc_mdefs:                               | a new WAVE track: PLAYBACK (TUNE 0 = C3), SETUP
        .byte   64, 0, 3, 2, 0, 0
        .byte   0, 40, 1, 64, 0, 0

        .align  4
| ---- wc_fmt_chrd / wc_fmt_voic: fmt(buf, value) -> length, C convention (octa303.s wc_fmt_tune)
wc_fmt_chrd:
        move.l  8(%sp),%d0
        moveq   #31,%d1
        cmp.l   %d1,%d0
        bls     .Lfc_o
        move.l  %d1,%d0
.Lfc_o:
        lsl.l   #3,%d0                  | eight bytes a name
        lea     wc_chords,%a1
        add.l   %d0,%a1
        move.l  4(%sp),%a0              | buf
        moveq   #0,%d1
.Lfc_c:
        move.b  (%a1)+,%d0
        beq     .Lfc_d
        move.b  %d0,(%a0)+
        addq.l  #1,%d1
        bra     .Lfc_c
.Lfc_d:
        clr.b   (%a0)
        move.l  %d1,%d0
        rts
wc_fmt_voic:
        move.l  8(%sp),%d0
        moveq   #3,%d1
        cmp.l   %d1,%d0
        bls     .Lfv_o
        move.l  %d1,%d0
.Lfv_o:
        move.l  4(%sp),%a0
        addq.l  #1,%d0
        add.l   #0x30,%d0
        move.b  %d0,(%a0)+
        clr.b   (%a0)
        moveq   #1,%d0
        rts

wc_fmt_oct:
        lea     wc_loct,%a1
        moveq   #2,%d1
        bra     wc_fmt_lbl
wc_fmt_mode:
        lea     wc_lmode,%a1
        moveq   #1,%d1
wc_fmt_lbl:                             | a1 = labels, 6 bytes each, d1 = the last
        move.l  8(%sp),%d0
        bpl     .Lfl_1
        moveq   #0,%d0
.Lfl_1:
        cmp.l   %d1,%d0
        ble     .Lfl_2
        move.l  %d1,%d0
.Lfl_2:
        moveq   #6,%d1
        muls.l  %d1,%d0
        add.l   %d0,%a1
        move.l  4(%sp),%a0
        moveq   #0,%d0
.Lfl_3:
        move.b  (%a1)+,%d1
        move.b  %d1,(%a0)+
        beq     .Lfl_4
        addq.l  #1,%d0
        bra     .Lfl_3
.Lfl_4:
        rts
wc_fmt_fine:                            | raw - 64: "-64" .. "0" .. "+63"
        move.l  8(%sp),%d0
        sub.l   #64,%d0
        lea     FMT_D,%a0
        tst.l   %d0
        ble     .Lff_1
        lea     wc_f_plus,%a0
.Lff_1:
        move.l  %d0,-(%sp)
        move.l  %a0,-(%sp)
        move.l  12(%sp),-(%sp)
        jsr     SPRINTF
        lea     12(%sp),%sp
        rts
wc_f_plus:
        .asciz  "+%d"
        .align  4
wc_notes:                               | wc_fmt_tune's names, two bytes each
        .ascii  "C C#D D#E F F#G G#A A#B "
        .align  4
wc_maxmsg:
        .asciz  "MAX 2 MACHINES"
        .align  4
wc_chords:                              | tables.py CHORD_NAMES, eight bytes each
        .ascii  "UNI"
        .fill   5, 1, 0
        .ascii  "OCT"
        .fill   5, 1, 0
        .ascii  "PWR"
        .fill   5, 1, 0
        .ascii  "MAJ"
        .fill   5, 1, 0
        .ascii  "MIN"
        .fill   5, 1, 0
        .ascii  "SUS2"
        .fill   4, 1, 0
        .ascii  "SUS4"
        .fill   4, 1, 0
        .ascii  "DIM"
        .fill   5, 1, 0
        .ascii  "AUG"
        .fill   5, 1, 0
        .ascii  "MAJ7"
        .fill   4, 1, 0
        .ascii  "MIN7"
        .fill   4, 1, 0
        .ascii  "DOM7"
        .fill   4, 1, 0
        .ascii  "DIM7"
        .fill   4, 1, 0
        .ascii  "M7B5"
        .fill   4, 1, 0
        .ascii  "MAJ6"
        .fill   4, 1, 0
        .ascii  "MIN6"
        .fill   4, 1, 0
        .ascii  "ADD9"
        .fill   4, 1, 0
        .ascii  "MADD9"
        .fill   3, 1, 0
        .ascii  "ADD11"
        .fill   3, 1, 0
        .ascii  "QRT"
        .fill   5, 1, 0
        .ascii  "5TH"
        .fill   5, 1, 0
        .ascii  "OPEN"
        .fill   4, 1, 0
        .ascii  "SPRD"
        .fill   4, 1, 0
        .ascii  "LYD"
        .fill   5, 1, 0
        .ascii  "DOR"
        .fill   5, 1, 0
        .ascii  "MIX"
        .fill   5, 1, 0
        .ascii  "PNT"
        .fill   5, 1, 0
        .ascii  "PNTM"
        .fill   4, 1, 0
        .ascii  "6/9"
        .fill   5, 1, 0
        .ascii  "M9"
        .fill   6, 1, 0
        .ascii  "M6/9"
        .fill   4, 1, 0
        .ascii  "STCK"
        .fill   4, 1, 0

| ---- runtime state: zeros, depacked by the loader at every boot
        .align  4
wc_state:
        .fill   ST_SIZE*NTRACKS, 1, 0
wc_desc:
        .fill   2*WC_DLEN, 1, 0                 | the PLAYBACK clone, the machine's record
        .align  4
wc_built:
        .fill   4, 1, 0                 | byte 0: the PLAYBACK clone is built

| >>> GENERATED ENGINE (modules/wavecf/generate.py) -- do not edit by hand
#NO_APP
	.file	"<stdin>"
	.text
	.align	2
	.type	snap.part.0, @function
snap.part.0:
	lea (-24,%sp),%sp
	moveq #12,%d1
	move.l 28(%sp),%d0
	add.l #30848,%d0
	asr.l #8,%d0
	movem.l #252,(%sp)
	move.l 32(%sp),%d5
	add.l #1080,%d0
	rems.l %d1,%d6:%d0
	move.l %d6,%d7
	move.l %d6,%a0
	subq.l #7,%d7
	move.l %d6,%d1
.L8:
	move.l %d1,%d3
	moveq #1,%d4
	add.l #12,%d3
	lsl.l %d3,%d4
	moveq #1,%d0
	move.l %d6,%a1
	move.l %a0,%d3
	lsl.l %d1,%d0
	sub.l %d1,%a1
	tst.l %d1
	jlt .L12
	and.l %d5,%d0
	tst.l %d0
	jne .L6
	moveq #11,%d0
	cmp.l %a0,%d0
	jge .L5
	add.l #-12,%d3
.L5:
	moveq #1,%d0
	subq.l #1,%d1
	lsl.l %d3,%d0
	addq.l #1,%a0
	and.l %d5,%d0
	tst.l %d0
	jne .L13
	cmp.l %d1,%d7
	jne .L8
	movem.l (%sp),#252
	move.l 28(%sp),%d0
	lea (24,%sp),%sp
	rts
.L12:
	and.l %d5,%d4
	tst.l %d4
	jeq .L5
.L6:
	mvs.w %a1,%d0
	movem.l (%sp),#252
	lsl.l #8,%d0
	sub.l %d0,28(%sp)
	move.l 28(%sp),%d0
	lea (24,%sp),%sp
	rts
.L13:
	mvs.w %a1,%d0
	movem.l (%sp),#252
	lsl.l #8,%d0
	add.l %d0,28(%sp)
	move.l 28(%sp),%d0
	lea (24,%sp),%sp
	rts
	.size	snap.part.0, .-snap.part.0
	.align	2
	.globl	eng_init
	.type	eng_init, @function
eng_init:
	move.l 4(%sp),%a1
	move.l %a1,%d0
	move.l %a1,%a0
	add.l #208,%d0
.L15:
	clr.l (%a0)+
	cmp.l %a0,%d0
	jne .L15
	move.l #268435456,%d0
	move.l 8(%sp),144(%a1)
	move.l 12(%sp),156(%a1)
	move.l 16(%sp),160(%a1)
	move.l %d0,192(%a1)
	rts
	.size	eng_init, .-eng_init
	.align	2
	.globl	eng_adsr
	.type	eng_adsr, @function
eng_adsr:
	move.l 4(%sp),%a0
	move.l 8(%sp),156(%a0)
	move.l 12(%sp),160(%a0)
	rts
	.size	eng_adsr, .-eng_adsr
	.align	2
	.globl	eng_setup
	.type	eng_setup, @function
eng_setup:
	move.l 4(%sp),%a0
	move.l 8(%sp),172(%a0)
	move.l 12(%sp),168(%a0)
	move.l 16(%sp),176(%a0)
	move.l 20(%sp),180(%a0)
	move.l 24(%sp),196(%a0)
	move.l 28(%sp),204(%a0)
	rts
	.size	eng_setup, .-eng_setup
	.align	2
	.globl	eng_pos
	.type	eng_pos, @function
eng_pos:
	move.l 8(%sp),%d0
	cmp.l #458752,%d0
	jle .L24
	moveq #7,%d0
	swap %d0
.L25:
	move.l 4(%sp),%a0
	move.l %d0,152(%a0)
	rts
.L24:
	tst.l %d0
	jge .L25
	move.l 4(%sp),%a0
	clr.l %d0
	move.l %d0,152(%a0)
	rts
	.size	eng_pos, .-eng_pos
	.align	2
	.globl	eng_on
	.type	eng_on, @function
eng_on:
	move.l 8(%sp),%d0
	moveq #36,%d1
	move.l 4(%sp),%a0
	muls.l %d1,%d0
	move.l 12(%sp),%d1
	move.l %d1,8(%a0,%d0.l)
	tst.l 24(%a0,%d0.l)
	jne .L29
	move.l %d1,4(%a0,%d0.l)
.L29:
	move.l 4(%sp),%a0
	add.l %d0,%a0
	moveq #1,%d0
	move.l %d0,28(%a0)
	move.l 16(%sp),16(%a0)
	clr.l 32(%a0)
	rts
	.size	eng_on, .-eng_on
	.align	2
	.globl	eng_off
	.type	eng_off, @function
eng_off:
	move.l 8(%sp),%d0
	moveq #36,%d1
	move.l 4(%sp),%a0
	muls.l %d1,%d0
	clr.l 28(%a0,%d0.l)
	rts
	.size	eng_off, .-eng_off
	.align	2
	.globl	eng_render
	.type	eng_render, @function
eng_render:
	lea (-52,%sp),%sp
	movem.l #31996,(%sp)
	move.l 56(%sp),%a2
	move.l 172(%a2),%d1
	tst.l %d1
	jne .L73
	move.l 192(%a2),%d3
	move.l %a2,%d2
	move.l #1073741824,%d1
	add.l #148,%d2
	lea (4,%a2),%a0
.L37:
	move.l (%a0),%a1
	move.l 4(%a0),%d0
	sub.l %a1,%d0
#APP
| 10 "fx.h" 1
	mac.l %d0,%d3,%acc0
	movclr.l %acc0,%d0
| 0 "" 2
#NO_APP
	add.l %a1,%d0
	move.l %d0,(%a0)
	cmp.l #1073741824,%d1
	jeq .L36
#APP
| 10 "fx.h" 1
	mac.l %d0,%d1,%acc0
	movclr.l %acc0,%d0
| 0 "" 2
#NO_APP
	add.l %d0,%d0
.L36:
	lea (36,%a0),%a0
	move.l %d0,-28(%a0)
	cmp.l %a0,%d2
	jne .L37
	tst.l 64(%sp)
	jle .L34
	move.l 144(%a2),%d0
	lea (144,%a2),%a0
	move.l %a0,44(%sp)
	move.l %d0,48(%sp)
.L55:
	move.l 148(%a2),%d0
	moveq #15,%d2
	move.l 152(%a2),%d1
	sub.l %d0,%d1
	asr.l #8,%d1
	moveq #11,%d3
	clr.l %d4
	move.l 48(%sp),%a3
	move.l %a2,%a0
	add.l %d1,%d0
	move.l %d0,%d1
	move.l %d0,%d7
	swap %d1
	ext.l %d1
	lsl.l %d2,%d7
	move.l %d0,148(%a2)
	lsl.l %d3,%d1
	and.l #2147450880,%d7
	add.l %d1,%a3
	lea (2048,%a3),%a4
	move.l %d7,%a6
.L51:
	move.l 28(%a0),%d0
	move.l 32(%a0),%d1
	tst.l %d0
	jeq .L39
	tst.l %d1
	jne .L69
	move.l 20(%a0),%a1
	moveq #1,%d7
	move.l %d7,24(%a0)
	move.l %d0,32(%a0)
.L42:
	move.l #135559905,%d1
	move.l 156(%a2),%d0
	sub.l %a1,%d1
#APP
| 10 "fx.h" 1
	mac.l %d0,%d1,%acc0
	movclr.l %acc0,%d0
| 0 "" 2
#NO_APP
	add.l %d0,%a1
	cmp.l #134217728,%a1
	jle .L46
	moveq #2,%d3
	move.l #134217728,%a1
	move.l %d3,24(%a0)
	move.l %a1,20(%a0)
.L47:
	moveq #22,%d0
	move.l (%a0),%d2
	move.l %d2,%d1
	lsr.l %d0,%d1
	move.l %d2,%d3
	lsr.l #8,%d3
	move.l %d1,%d0
	addq.l #1,%d1
	add.l %d0,%d0
	and.l #1023,%d1
	and.l #16383,%d3
	mvs.w (%a3,%d0.l),%d6
	mvs.w (%a4,%d0.l),%d5
	moveq #12,%d0
	move.l %d6,%d7
	lsl.l %d0,%d7
	add.l %d1,%d1
	move.l %d7,%a5
	move.l %d5,%d7
	lsl.l %d0,%d7
	mvs.w (%a3,%d1.l),%d0
	mvs.w (%a4,%d1.l),%d1
	sub.l %d6,%d0
	muls.l %d3,%d0
	sub.l %d5,%d1
	muls.l %d3,%d1
	asr.l #2,%d0
	asr.l #2,%d1
	add.l %a5,%d0
	add.l %d7,%d1
	sub.l %d0,%d1
#APP
| 10 "fx.h" 1
	mac.l %d1,%a6,%acc0
	movclr.l %acc0,%d1
| 0 "" 2
#NO_APP
	add.l 12(%a0),%d2
	add.l %d1,%d0
	move.l 16(%a0),%d1
	move.l %d2,(%a0)
#APP
| 10 "fx.h" 1
	mac.l %d0,%d1,%acc0
	movclr.l %acc0,%d0
| 0 "" 2
| 10 "fx.h" 1
	mac.l %d0,%a1,%acc0
	movclr.l %acc0,%d0
| 0 "" 2
#NO_APP
	lsl.l #4,%d0
	add.l %d0,%d4
.L49:
	lea (36,%a0),%a0
	cmp.l 44(%sp),%a0
	jne .L51
.L74:
	move.l 176(%a2),%d0
	tst.l %d0
	jeq .L52
#APP
| 10 "fx.h" 1
	mac.l %d4,%d0,%acc0
	movclr.l %acc0,%d0
| 0 "" 2
#NO_APP
	cmp.l #-4194305,%d0
	jgt .L53
	move.l #-4194304,%d0
.L54:
	lsl.l #8,%d0
#APP
| 10 "fx.h" 1
	mac.l %d0,%d0,%acc0
	movclr.l %acc0,%d1
| 0 "" 2
| 10 "fx.h" 1
	mac.l %d1,%d0,%acc0
	movclr.l %acc0,%d1
| 0 "" 2
#NO_APP
	move.l #715827883,%d2
#APP
| 10 "fx.h" 1
	mac.l %d1,%d2,%acc0
	movclr.l %acc0,%d1
| 0 "" 2
#NO_APP
	lsl.l #2,%d1
	move.l 180(%a2),%d4
	sub.l %d1,%d0
#APP
| 10 "fx.h" 1
	mac.l %d0,%d4,%acc0
	movclr.l %acc0,%d4
| 0 "" 2
#NO_APP
.L52:
	move.l 60(%sp),%a0
	addq.l #4,60(%sp)
	subq.l #1,64(%sp)
	move.l %d4,(%a0)+
	tst.l 64(%sp)
	jne .L55
.L34:
	movem.l (%sp),#31996
	lea (52,%sp),%sp
	rts
.L69:
	move.l 24(%a0),%d1
	moveq #1,%d2
	move.l 20(%a0),%a1
	move.l %d0,32(%a0)
	cmp.l %d1,%d2
	jeq .L42
	moveq #3,%d7
	cmp.l %d1,%d7
	jeq .L44
	tst.l %d1
	jne .L47
	lea (36,%a0),%a0
	cmp.l 44(%sp),%a0
	jne .L51
	jra .L74
.L39:
	tst.l %d1
	jeq .L69
	move.l 20(%a0),%a1
	moveq #3,%d0
	move.l %d0,24(%a0)
	clr.l 32(%a0)
.L44:
	move.l #-1342177,%d1
	move.l 160(%a2),%d0
	sub.l %a1,%d1
#APP
| 10 "fx.h" 1
	mac.l %d0,%d1,%acc0
	movclr.l %acc0,%d0
| 0 "" 2
#NO_APP
	add.l %d0,%a1
	tst.l %a1
	jlt .L75
.L46:
	moveq #22,%d0
	move.l (%a0),%d2
	move.l %d2,%d1
	lsr.l %d0,%d1
	move.l %d2,%d3
	lsr.l #8,%d3
	move.l %a1,20(%a0)
	move.l %d1,%d0
	addq.l #1,%d1
	add.l %d0,%d0
	and.l #1023,%d1
	and.l #16383,%d3
	mvs.w (%a3,%d0.l),%d6
	mvs.w (%a4,%d0.l),%d5
	moveq #12,%d0
	move.l %d6,%d7
	lsl.l %d0,%d7
	add.l %d1,%d1
	move.l %d7,%a5
	move.l %d5,%d7
	lsl.l %d0,%d7
	mvs.w (%a3,%d1.l),%d0
	mvs.w (%a4,%d1.l),%d1
	sub.l %d6,%d0
	muls.l %d3,%d0
	sub.l %d5,%d1
	muls.l %d3,%d1
	asr.l #2,%d0
	asr.l #2,%d1
	add.l %a5,%d0
	add.l %d7,%d1
	sub.l %d0,%d1
#APP
| 10 "fx.h" 1
	mac.l %d1,%a6,%acc0
	movclr.l %acc0,%d1
| 0 "" 2
#NO_APP
	add.l 12(%a0),%d2
	add.l %d1,%d0
	move.l 16(%a0),%d1
	move.l %d2,(%a0)
#APP
| 10 "fx.h" 1
	mac.l %d0,%d1,%acc0
	movclr.l %acc0,%d0
| 0 "" 2
| 10 "fx.h" 1
	mac.l %d0,%a1,%acc0
	movclr.l %acc0,%d0
| 0 "" 2
#NO_APP
	lsl.l #4,%d0
	add.l %d0,%d4
	jra .L49
.L75:
	clr.l 24(%a0)
	clr.l 20(%a0)
	lea (36,%a0),%a0
	cmp.l 44(%sp),%a0
	jne .L51
	jra .L74
.L53:
	cmp.l #4194304,%d0
	jle .L54
	moveq #64,%d0
	swap %d0
	lsl.l #8,%d0
#APP
| 10 "fx.h" 1
	mac.l %d0,%d0,%acc0
	movclr.l %acc0,%d1
| 0 "" 2
| 10 "fx.h" 1
	mac.l %d1,%d0,%acc0
	movclr.l %acc0,%d1
| 0 "" 2
#NO_APP
	move.l #715827883,%d2
#APP
| 10 "fx.h" 1
	mac.l %d1,%d2,%acc0
	movclr.l %acc0,%d1
| 0 "" 2
#NO_APP
	lsl.l #2,%d1
	move.l 180(%a2),%d4
	sub.l %d1,%d0
#APP
| 10 "fx.h" 1
	mac.l %d0,%d4,%acc0
	movclr.l %acc0,%d4
| 0 "" 2
#NO_APP
	jra .L52
.L73:
	move.l 164(%a2),%d2
	move.l %d2,%d3
	add.l #-2147483648,%d3
	move.l %d3,%d0
	add.l %d0,%d0
	subx.l %d0,%d0
	eor.l %d3,%d0
	add.l #-1073741824,%d0
#APP
| 10 "fx.h" 1
	mac.l %d0,%d1,%acc0
	movclr.l %acc0,%d0
| 0 "" 2
#NO_APP
	move.l #357913941,%d1
#APP
| 10 "fx.h" 1
	mac.l %d0,%d1,%acc0
	movclr.l %acc0,%d0
| 0 "" 2
#NO_APP
	move.l #1488522236,%d1
#APP
| 10 "fx.h" 1
	mac.l %d0,%d1,%acc0
	movclr.l %acc0,%d0
| 0 "" 2
| 10 "fx.h" 1
	mac.l %d0,%d0,%acc0
	movclr.l %acc0,%a1
| 0 "" 2
| 10 "fx.h" 1
	mac.l %a1,%d0,%acc0
	movclr.l %acc0,%a0
| 0 "" 2
#NO_APP
	move.l #1431655765,%d1
#APP
| 10 "fx.h" 1
	mac.l %a0,%d1,%acc0
	movclr.l %acc0,%a0
| 0 "" 2
#NO_APP
	move.l %d0,%d1
	add.l #1073741824,%d1
	move.l 64(%sp),%d0
	add.l %a1,%d1
	lea (168,%a2),%a3
	add.l %a0,%d1
	move.l 192(%a2),%d3
	muls.l (%a3),%d0
	lea (4,%a2),%a0
	add.l %d2,%d0
	move.l %a2,%d2
	add.l #148,%d2
	move.l %d0,164(%a2)
	jra .L37
	.size	eng_render, .-eng_render
	.align	2
	.globl	wcf_scale
	.type	wcf_scale, @function
wcf_scale:
	move.l 8(%sp),%d0
	move.l 4(%sp),%a0
	and.l #4095,%d0
	move.l %d0,184(%a0)
	rts
	.size	wcf_scale, .-wcf_scale
	.align	2
	.globl	wcf_inc
	.type	wcf_inc, @function
wcf_inc:
	move.l %d3,-(%sp)
	move.l %d2,-(%sp)
	move.l 12(%sp),%d0
	cmp.l #12288,%d0
	jle .L79
	move.l #12288,%d0
.L80:
	move.l %d0,%d1
	asr.l #3,%d1
	moveq #7,%d2
	and.l %d2,%d0
	move.l #384,%d3
	add.l #3072,%d1
	rems.l %d3,%d2:%d1
	divs.l %d3,%d1
	lea wcf_exp2,%a0
	move.l (%a0,%d2.l*4),%a1
	move.l 4(%a0,%d2.l*4),%d2
	sub.l %a1,%d2
	muls.l %d2,%d0
	move.l %d1,%d2
	subq.l #8,%d2
	asr.l #3,%d0
	add.l %d0,%a1
	move.l #815363776,%d0
#APP
| 10 "fx.h" 1
	mac.l %d0,%a1,%acc0
	movclr.l %acc0,%d0
| 0 "" 2
#NO_APP
	asr.l #4,%d0
	tst.l %d2
	jlt .L81
.L85:
	lsl.l %d2,%d0
	move.l (%sp)+,%d2
	move.l (%sp)+,%d3
	rts
.L79:
	cmp.l #-12288,%d0
	jge .L80
	move.l #-12288,%d0
	moveq #7,%d2
	move.l %d0,%d1
	asr.l #3,%d1
	and.l %d2,%d0
	move.l #384,%d3
	lea wcf_exp2,%a0
	add.l #3072,%d1
	rems.l %d3,%d2:%d1
	divs.l %d3,%d1
	move.l (%a0,%d2.l*4),%a1
	move.l 4(%a0,%d2.l*4),%d2
	sub.l %a1,%d2
	muls.l %d2,%d0
	move.l %d1,%d2
	subq.l #8,%d2
	asr.l #3,%d0
	add.l %d0,%a1
	move.l #815363776,%d0
#APP
| 10 "fx.h" 1
	mac.l %d0,%a1,%acc0
	movclr.l %acc0,%d0
| 0 "" 2
#NO_APP
	asr.l #4,%d0
	tst.l %d2
	jge .L85
.L81:
	moveq #8,%d2
	sub.l %d1,%d2
	lsr.l %d2,%d0
	move.l (%sp)+,%d2
	move.l (%sp)+,%d3
	rts
	.size	wcf_inc, .-wcf_inc
	.align	2
	.globl	wcf_note
	.type	wcf_note, @function
wcf_note:
	lea (-32,%sp),%sp
	moveq #4,%d0
	movem.l #15388,(%sp)
	move.l 48(%sp),%d4
	move.l %d4,%d3
	move.l 36(%sp),%a3
	cmp.l %d4,%d0
	jge .L87
	moveq #4,%d3
.L88:
	move.l 196(%a3),%d2
	tst.l %d2
	jne .L114
.L89:
	moveq #31,%d0
	and.l 44(%sp),%d0
	lea gain_n,%a0
	move.l (%a0,%d3.l*4),%a0
	move.l 188(%a3),%d4
	asr.l #5,%d4
	lea (4,%a3),%a2
	move.l %a0,28(%sp)
	lea wcf_inc,%a5
	lsl.l #2,%d0
	move.l %d0,%a4
	add.l #wcf_chord,%a4
	mvs.b (%a4),%d1
.L95:
	lsl.l #8,%d1
	move.l 40(%sp),%d0
	move.l 184(%a3),%a0
	add.l 204(%a3),%d0
	add.l %d1,%d0
	tst.l %a0
	jeq .L97
	move.l %a0,-(%sp)
	move.l %d0,-(%sp)
	jsr (snap.part.0)
	addq.l #8,%sp
.L97:
	move.l %d0,-(%sp)
	jsr (%a5)
	addq.l #4,%sp
	move.l %d0,4(%a2)
	tst.l 20(%a2)
	jne .L98
	move.l %d0,(%a2)
.L98:
	moveq #1,%d0
	addq.l #1,%d2
	move.l %d0,24(%a2)
	moveq #4,%d1
	move.l 28(%sp),12(%a2)
	clr.l 28(%a2)
	lea (36,%a2),%a2
	cmp.l %d2,%d1
	jeq .L100
.L115:
	mvs.b (%a4,%d2.l),%d1
	cmp.l %d4,%d2
	jgt .L102
	add.l #12,%d1
.L102:
	cmp.l %d2,%d3
	jgt .L95
	clr.l 24(%a2)
	moveq #4,%d1
	addq.l #1,%d2
	lea (36,%a2),%a2
	cmp.l %d2,%d1
	jne .L115
.L100:
	clr.l 200(%a3)
.L86:
	movem.l (%sp),#15388
	lea (32,%sp),%sp
	rts
.L87:
	tst.l %d4
	jgt .L88
	move.l 196(%a3),%d2
	moveq #1,%d3
	tst.l %d2
	jeq .L89
.L114:
	move.l 200(%a3),%d2
	cmp.l %d2,%d3
	jgt .L116
	move.w #1,%a4
	clr.l %d2
.L90:
	move.l 40(%sp),%d0
	lea gain_n,%a0
	move.l 184(%a3),%d1
	move.l (%a0,%d3.l*4),%a2
	add.l 204(%a3),%d0
	tst.l %d1
	jeq .L91
	move.l %d1,-(%sp)
	move.l %d0,-(%sp)
	jsr (snap.part.0)
	addq.l #8,%sp
.L91:
	move.l %d0,-(%sp)
	jsr wcf_inc
	addq.l #4,%sp
	moveq #36,%d1
	muls.l %d1,%d2
	move.l %d0,8(%a3,%d2.l)
	tst.l 24(%a3,%d2.l)
	jne .L92
	move.l %d0,4(%a3,%d2.l)
.L92:
	moveq #1,%d0
	moveq #3,%d1
	move.l %a2,16(%a3,%d2.l)
	move.l %d0,28(%a3,%d2.l)
	clr.l 32(%a3,%d2.l)
	move.l %a4,200(%a3)
	cmp.l %d4,%d1
	jlt .L86
	mulu.w #36,%d3
	move.l %a3,%d0
	add.l #172,%d0
	lea 28(%a3,%d3.l),%a0
.L94:
	clr.l (%a0)
	lea (36,%a0),%a0
	cmp.l %a0,%d0
	jeq .L86
	clr.l (%a0)
	lea (36,%a0),%a0
	cmp.l %a0,%d0
	jne .L94
	jra .L86
.L116:
	move.l %d2,%a4
	addq.l #1,%a4
	jra .L90
	.size	wcf_note, .-wcf_note
	.align	2
	.globl	wcf_init
	.type	wcf_init, @function
wcf_init:
	move.l 4(%sp),%a1
	move.l %a1,%d0
	move.l %a1,%a0
	add.l #208,%d0
.L118:
	clr.l (%a0)+
	cmp.l %a0,%d0
	jne .L118
	move.l #32721410,%d0
	move.l %d0,156(%a1)
	move.l #3776253,%d0
	move.l %d0,160(%a1)
	move.l #268435456,%d0
	move.l 8(%sp),144(%a1)
	move.l %d0,192(%a1)
	rts
	.size	wcf_init, .-wcf_init
	.align	2
	.globl	wcf_knobs
	.type	wcf_knobs, @function
wcf_knobs:
	move.l %d2,-(%sp)
	moveq #127,%d1
	move.l 12(%sp),%d0
	move.l 8(%sp),%a0
	cmp.l %d0,%d1
	jge .L123
	moveq #127,%d0
.L123:
	moveq #7,%d2
	swap %d2
	muls.l %d2,%d0
	moveq #127,%d2
	divs.l %d2,%d0
	tst.l %d0
	jlt .L129
.L124:
	move.l %d0,152(%a0)
	moveq #127,%d1
	move.l 16(%sp),%d0
	cmp.l %d0,%d1
	jge .L125
	moveq #127,%d0
.L125:
	move.l %d0,188(%a0)
	moveq #127,%d2
	move.l 20(%sp),%d0
	cmp.l %d0,%d2
	jge .L126
	moveq #127,%d0
.L126:
	lea wcf_glide,%a1
	lea (%a1,%d0.l*4),%a1
	move.l (%sp)+,%d2
	move.l (%a1),192(%a0)
	rts
.L129:
	clr.l %d0
	jra .L124
	.size	wcf_knobs, .-wcf_knobs
	.align	2
	.globl	wcf_setup
	.type	wcf_setup, @function
wcf_setup:
	subq.l #8,%sp
	move.l %a2,-(%sp)
	moveq #127,%d1
	move.l %d2,-(%sp)
	move.l 40(%sp),%d0
	move.l 20(%sp),%a0
	cmp.l %d0,%d1
	jge .L131
	moveq #127,%d0
.L131:
	lea wcf_comp_makeup,%a1
	lea wcf_comp_drive,%a2
	move.l (%a2,%d0.l*4),%d1
	move.l (%a1,%d0.l*4),%a1
	move.l 28(%sp),%d0
	move.l %d1,8(%sp)
	moveq #127,%d1
	cmp.l %d0,%d1
	jge .L132
	moveq #127,%d0
.L132:
	lea wcf_lfo,%a2
	moveq #127,%d1
	move.l (%a2,%d0.l*4),%d0
	move.l %d0,12(%sp)
	move.l 24(%sp),%d0
	cmp.l %d0,%d1
	jge .L133
	moveq #127,%d0
.L133:
	tst.l 44(%sp)
	sne %d1
	move.l #16909320,%d2
	muls.l %d0,%d2
	move.l 32(%sp),%d0
	move.l 12(%sp),168(%a0)
	move.l 8(%sp),176(%a0)
	move.l %a1,180(%a0)
	move.l %d2,172(%a0)
	mvs.b %d1,%d1
	neg.l %d1
	move.l %d1,196(%a0)
	moveq #2,%d1
	cmp.l %d0,%d1
	jge .L134
	moveq #2,%d0
.L134:
	move.l 36(%sp),%a1
	subq.l #1,%d0
	move.l #1536,%d2
	moveq #127,%d1
	muls.l %d2,%d0
	cmp.l %a1,%d1
	jge .L135
	move.w #127,%a1
.L135:
	lea -64(%a1,%d0.l),%a1
	move.l (%sp)+,%d2
	move.l (%sp)+,%a2
	move.l %a1,%d0
	add.l %d0,%d0
	move.l %d0,204(%a0)
	addq.l #8,%sp
	rts
	.size	wcf_setup, .-wcf_setup
	.globl	wcf_glide
	.section	.rodata
	.align	2
	.type	wcf_glide, @object
	.size	wcf_glide, 512
wcf_glide:
	.long	268435456
	.long	259331289
	.long	250535895
	.long	242038803
	.long	233829896
	.long	225899399
	.long	218237871
	.long	210836188
	.long	203685538
	.long	196777407
	.long	190103570
	.long	183656081
	.long	177427263
	.long	171409699
	.long	165596225
	.long	159979918
	.long	154554093
	.long	149312288
	.long	144248262
	.long	139355986
	.long	134629635
	.long	130063581
	.long	125652388
	.long	121390804
	.long	117273754
	.long	113296336
	.long	109453815
	.long	105741616
	.long	102155319
	.long	98690653
	.long	95343494
	.long	92109856
	.long	88985889
	.long	85967873
	.long	83052215
	.long	80235444
	.long	77514205
	.long	74885259
	.long	72345476
	.long	69891831
	.long	67521403
	.long	65231370
	.long	63019004
	.long	60881673
	.long	58816830
	.long	56822018
	.long	54894862
	.long	53033066
	.long	51234414
	.long	49496765
	.long	47818049
	.long	46196268
	.long	44629491
	.long	43115852
	.long	41653549
	.long	40240841
	.long	38876046
	.long	37557539
	.long	36283750
	.long	35053163
	.long	33864311
	.long	32715781
	.long	31606203
	.long	30534258
	.long	29498668
	.long	28498201
	.long	27531665
	.long	26597911
	.long	25695825
	.long	24824334
	.long	23982400
	.long	23169021
	.long	22383228
	.long	21624086
	.long	20890691
	.long	20182169
	.long	19497677
	.long	18836401
	.long	18197552
	.long	17580369
	.long	16984119
	.long	16408092
	.long	15851600
	.long	15313983
	.long	14794599
	.long	14292830
	.long	13808079
	.long	13339769
	.long	12887342
	.long	12450259
	.long	12028000
	.long	11620063
	.long	11225961
	.long	10845225
	.long	10477402
	.long	10122054
	.long	9778757
	.long	9447104
	.long	9126699
	.long	8817161
	.long	8518121
	.long	8229224
	.long	7950124
	.long	7680490
	.long	7420001
	.long	7168347
	.long	6925228
	.long	6690354
	.long	6463446
	.long	6244234
	.long	6032457
	.long	5827862
	.long	5630206
	.long	5439254
	.long	5254778
	.long	5076559
	.long	4904384
	.long	4738048
	.long	4577354
	.long	4422110
	.long	4272132
	.long	4127239
	.long	3987261
	.long	3852031
	.long	3721386
	.long	3595173
	.long	3473240
	.long	3355443
	.globl	wcf_comp_makeup
	.align	2
	.type	wcf_comp_makeup, @object
	.size	wcf_comp_makeup, 512
wcf_comp_makeup:
	.long	0
	.long	280555452
	.long	274567461
	.long	268737484
	.long	263062452
	.long	257539404
	.long	252165487
	.long	246937956
	.long	241854174
	.long	236911615
	.long	232107863
	.long	227440615
	.long	222907683
	.long	218506997
	.long	214236608
	.long	210094691
	.long	206079551
	.long	202189626
	.long	198423495
	.long	194779886
	.long	191257679
	.long	187855921
	.long	184573836
	.long	181410832
	.long	178366525
	.long	175440746
	.long	172633568
	.long	169945324
	.long	167376636
	.long	164928444
	.long	162602041
	.long	160399118
	.long	158321810
	.long	156372758
	.long	154555172
	.long	152872919
	.long	151330620
	.long	149933763
	.long	148688853
	.long	147603579
	.long	146687029
	.long	145949949
	.long	145405067
	.long	145067499
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.long	144955146
	.globl	wcf_comp_drive
	.align	2
	.type	wcf_comp_drive, @object
	.size	wcf_comp_drive, 512
wcf_comp_drive:
	.long	0
	.long	67108864
	.long	68723540
	.long	70377066
	.long	72070377
	.long	73804429
	.long	75580204
	.long	77398705
	.long	79260961
	.long	81168023
	.long	83120970
	.long	85120906
	.long	87168961
	.long	89266294
	.long	91414090
	.long	93613563
	.long	95865957
	.long	98172544
	.long	100534629
	.long	102953547
	.long	105430666
	.long	107967386
	.long	110565140
	.long	113225398
	.long	115949663
	.long	118739475
	.long	121596412
	.long	124522088
	.long	127518158
	.long	130586314
	.long	133728292
	.long	136945868
	.long	140240861
	.long	143615133
	.long	147070591
	.long	150609190
	.long	154232930
	.long	157943858
	.long	161744074
	.long	165635725
	.long	169621011
	.long	173702185
	.long	177881555
	.long	182161483
	.long	186544388
	.long	191032748
	.long	195629100
	.long	200336043
	.long	205156238
	.long	210092409
	.long	215147348
	.long	220323911
	.long	225625025
	.long	231053686
	.long	236612964
	.long	242306002
	.long	248136017
	.long	254106305
	.long	260220242
	.long	266481283
	.long	272892968
	.long	279458923
	.long	286182857
	.long	293068573
	.long	300119964
	.long	307341014
	.long	314735807
	.long	322308523
	.long	330063442
	.long	338004949
	.long	346137533
	.long	354465792
	.long	362994433
	.long	371728277
	.long	380672263
	.long	389831446
	.long	399211004
	.long	408816239
	.long	418652581
	.long	428725592
	.long	439040964
	.long	449604530
	.long	460422261
	.long	471500272
	.long	482844827
	.long	494462338
	.long	506359372
	.long	518542656
	.long	531019076
	.long	543795685
	.long	556879707
	.long	570278537
	.long	583999751
	.long	598051105
	.long	612440541
	.long	627176196
	.long	642266398
	.long	657719679
	.long	673544775
	.long	689750630
	.long	706346408
	.long	723341489
	.long	740745481
	.long	758568223
	.long	776819789
	.long	795510498
	.long	814650916
	.long	834251863
	.long	854324419
	.long	874879932
	.long	895930022
	.long	917486589
	.long	939561818
	.long	962168190
	.long	985318483
	.long	1009025785
	.long	1033303497
	.long	1058165345
	.long	1083625382
	.long	1109698001
	.long	1136397942
	.long	1163740299
	.long	1191740527
	.long	1220414456
	.long	1249778296
	.long	1279848645
	.long	1310642504
	.long	1342177280
	.globl	wcf_lfo
	.align	2
	.type	wcf_lfo, @object
	.size	wcf_lfo, 512
wcf_lfo:
	.long	13635
	.long	14311
	.long	15021
	.long	15766
	.long	16547
	.long	17368
	.long	18229
	.long	19133
	.long	20082
	.long	21078
	.long	22123
	.long	23220
	.long	24372
	.long	25580
	.long	26849
	.long	28180
	.long	29578
	.long	31045
	.long	32584
	.long	34200
	.long	35896
	.long	37676
	.long	39544
	.long	41505
	.long	43564
	.long	45724
	.long	47992
	.long	50371
	.long	52869
	.long	55491
	.long	58243
	.long	61131
	.long	64163
	.long	67345
	.long	70684
	.long	74190
	.long	77869
	.long	81730
	.long	85783
	.long	90037
	.long	94502
	.long	99189
	.long	104107
	.long	109270
	.long	114689
	.long	120376
	.long	126346
	.long	132611
	.long	139188
	.long	146090
	.long	153335
	.long	160938
	.long	168919
	.long	177296
	.long	186088
	.long	195317
	.long	205002
	.long	215168
	.long	225839
	.long	237038
	.long	248793
	.long	261131
	.long	274080
	.long	287672
	.long	301938
	.long	316911
	.long	332627
	.long	349122
	.long	366435
	.long	384606
	.long	403679
	.long	423698
	.long	444709
	.long	466762
	.long	489909
	.long	514204
	.long	539703
	.long	566467
	.long	594559
	.long	624043
	.long	654989
	.long	687471
	.long	721562
	.long	757345
	.long	794902
	.long	834321
	.long	875696
	.long	919122
	.long	964701
	.long	1012541
	.long	1062753
	.long	1115455
	.long	1170771
	.long	1228830
	.long	1289768
	.long	1353728
	.long	1420860
	.long	1491321
	.long	1565276
	.long	1642898
	.long	1724370
	.long	1809882
	.long	1899635
	.long	1993838
	.long	2092713
	.long	2196492
	.long	2305416
	.long	2419743
	.long	2539738
	.long	2665685
	.long	2797877
	.long	2936625
	.long	3082253
	.long	3235103
	.long	3395532
	.long	3563918
	.long	3740654
	.long	3926154
	.long	4120853
	.long	4325207
	.long	4539696
	.long	4764821
	.long	5001109
	.long	5249116
	.long	5509421
	.long	5782635
	.long	6069398
	.long	6370381
	.globl	wcf_chord
	.type	wcf_chord, @object
	.size	wcf_chord, 128
wcf_chord:
	.base64	"AAAAAA=="
	.base64	"AAwADA=="
	.base64	"AAcMEw=="
	.base64	"AAQHDA=="
	.base64	"AAMHDA=="
	.base64	"AAIHDA=="
	.base64	"AAUHDA=="
	.base64	"AAMGDA=="
	.base64	"AAQIDA=="
	.base64	"AAQHCw=="
	.base64	"AAMHCg=="
	.base64	"AAQHCg=="
	.base64	"AAMGCQ=="
	.base64	"AAMGCg=="
	.base64	"AAQHCQ=="
	.base64	"AAMHCQ=="
	.base64	"AAQHDg=="
	.base64	"AAMHDg=="
	.base64	"AAQHEQ=="
	.base64	"AAUKDw=="
	.base64	"AAcOFQ=="
	.base64	"AAcMEA=="
	.base64	"AAUMEQ=="
	.base64	"AAQLDg=="
	.base64	"AAMKDg=="
	.base64	"AAQKDg=="
	.base64	"AAIEBw=="
	.base64	"AAMFBw=="
	.base64	"AAIHCQ=="
	.base64	"AAcKDg=="
	.base64	"AAQJDg=="
	.base64	"AAwTGA=="
	.globl	wcf_tc
	.align	2
	.type	wcf_tc, @object
	.size	wcf_tc, 512
wcf_tc:
	.long	95216134
	.long	90304181
	.long	85640305
	.long	81212519
	.long	77009361
	.long	73019874
	.long	69233592
	.long	65640518
	.long	62231113
	.long	58996275
	.long	55927324
	.long	53015984
	.long	50254369
	.long	47634965
	.long	45150619
	.long	42794516
	.long	40560174
	.long	38441420
	.long	36432384
	.long	34527484
	.long	32721410
	.long	31009114
	.long	29385797
	.long	27846901
	.long	26388091
	.long	25005253
	.long	23694475
	.long	22452044
	.long	21274434
	.long	20158296
	.long	19100452
	.long	18097883
	.long	17147727
	.long	16247264
	.long	15393915
	.long	14585233
	.long	13818895
	.long	13092699
	.long	12404553
	.long	11752477
	.long	11134589
	.long	10549107
	.long	9994338
	.long	9468680
	.long	8970610
	.long	8498688
	.long	8051546
	.long	7627888
	.long	7226484
	.long	6846169
	.long	6485839
	.long	6144447
	.long	5821001
	.long	5514558
	.long	5224229
	.long	4949167
	.long	4688571
	.long	4441683
	.long	4207782
	.long	3986188
	.long	3776253
	.long	3577365
	.long	3388943
	.long	3210439
	.long	3041330
	.long	2881123
	.long	2729350
	.long	2585567
	.long	2449354
	.long	2320314
	.long	2198068
	.long	2082260
	.long	1972550
	.long	1868618
	.long	1770160
	.long	1676888
	.long	1588528
	.long	1504823
	.long	1425527
	.long	1350409
	.long	1279247
	.long	1211834
	.long	1147973
	.long	1087477
	.long	1030167
	.long	975877
	.long	924448
	.long	875728
	.long	829576
	.long	785855
	.long	744439
	.long	705204
	.long	668037
	.long	632829
	.long	599476
	.long	567880
	.long	537950
	.long	509597
	.long	482738
	.long	457295
	.long	433192
	.long	410360
	.long	388731
	.long	368242
	.long	348833
	.long	330447
	.long	313029
	.long	296530
	.long	280900
	.long	266094
	.long	252069
	.long	238783
	.long	226197
	.long	214274
	.long	202980
	.long	192281
	.long	182146
	.long	172545
	.long	163450
	.long	154834
	.long	146673
	.long	138942
	.long	131618
	.long	124681
	.long	118109
	.long	111883
	.long	105986
	.long	100399
	.globl	wcf_exp2
	.align	2
	.type	wcf_exp2, @object
	.size	wcf_exp2, 1540
wcf_exp2:
	.long	536870912
	.long	537840877
	.long	538812595
	.long	539786068
	.long	540761300
	.long	541738294
	.long	542717053
	.long	543697580
	.long	544679879
	.long	545663953
	.long	546649804
	.long	547637437
	.long	548626854
	.long	549618059
	.long	550611054
	.long	551605844
	.long	552602431
	.long	553600818
	.long	554601009
	.long	555603007
	.long	556606816
	.long	557612438
	.long	558619876
	.long	559629135
	.long	560640218
	.long	561653127
	.long	562667866
	.long	563684439
	.long	564702848
	.long	565723097
	.long	566745190
	.long	567769129
	.long	568794918
	.long	569822560
	.long	570852059
	.long	571883418
	.long	572916640
	.long	573951729
	.long	574988688
	.long	576027521
	.long	577068230
	.long	578110820
	.long	579155293
	.long	580201654
	.long	581249905
	.long	582300049
	.long	583352091
	.long	584406034
	.long	585461881
	.long	586519635
	.long	587579301
	.long	588640881
	.long	589704379
	.long	590769799
	.long	591837143
	.long	592906416
	.long	593977620
	.long	595050760
	.long	596125839
	.long	597202860
	.long	598281827
	.long	599362743
	.long	600445612
	.long	601530438
	.long	602617224
	.long	603705973
	.long	604796689
	.long	605889375
	.long	606984036
	.long	608080675
	.long	609179295
	.long	610279900
	.long	611382493
	.long	612487078
	.long	613593659
	.long	614702239
	.long	615812822
	.long	616925412
	.long	618040012
	.long	619156625
	.long	620275256
	.long	621395908
	.long	622518584
	.long	623643289
	.long	624770026
	.long	625898799
	.long	627029611
	.long	628162466
	.long	629297367
	.long	630434320
	.long	631573326
	.long	632714390
	.long	633857516
	.long	635002706
	.long	636149966
	.long	637299299
	.long	638450708
	.long	639604198
	.long	640759771
	.long	641917433
	.long	643077185
	.long	644239034
	.long	645402981
	.long	646569031
	.long	647737188
	.long	648907455
	.long	650079837
	.long	651254337
	.long	652430958
	.long	653609706
	.long	654790583
	.long	655973594
	.long	657158742
	.long	658346031
	.long	659535466
	.long	660727049
	.long	661920785
	.long	663116678
	.long	664314732
	.long	665514950
	.long	666717336
	.long	667921895
	.long	669128630
	.long	670337545
	.long	671548645
	.long	672761932
	.long	673977412
	.long	675195088
	.long	676414963
	.long	677637043
	.long	678861330
	.long	680087829
	.long	681316545
	.long	682547480
	.long	683780639
	.long	685016026
	.long	686253645
	.long	687493500
	.long	688735596
	.long	689979935
	.long	691226522
	.long	692475362
	.long	693726458
	.long	694979814
	.long	696235434
	.long	697493324
	.long	698753485
	.long	700015924
	.long	701280643
	.long	702547648
	.long	703816941
	.long	705088528
	.long	706362412
	.long	707638598
	.long	708917089
	.long	710197890
	.long	711481005
	.long	712766439
	.long	714054194
	.long	715344277
	.long	716636690
	.long	717931438
	.long	719228525
	.long	720527956
	.long	721829735
	.long	723133865
	.long	724440352
	.long	725749199
	.long	727060411
	.long	728373991
	.long	729689945
	.long	731008277
	.long	732328990
	.long	733652089
	.long	734977579
	.long	736305464
	.long	737635748
	.long	738968435
	.long	740303530
	.long	741641037
	.long	742980960
	.long	744323305
	.long	745668074
	.long	747015274
	.long	748364907
	.long	749716978
	.long	751071493
	.long	752428454
	.long	753787867
	.long	755149737
	.long	756514066
	.long	757880861
	.long	759250125
	.long	760621863
	.long	761996079
	.long	763372778
	.long	764751964
	.long	766133642
	.long	767517817
	.long	768904492
	.long	770293672
	.long	771685363
	.long	773079567
	.long	774476291
	.long	775875538
	.long	777277313
	.long	778681621
	.long	780088465
	.long	781497852
	.long	782909785
	.long	784324269
	.long	785741308
	.long	787160907
	.long	788583072
	.long	790007805
	.long	791435113
	.long	792865000
	.long	794297470
	.long	795732528
	.long	797170178
	.long	798610426
	.long	800053277
	.long	801498734
	.long	802946802
	.long	804397487
	.long	805850792
	.long	807306724
	.long	808765286
	.long	810226483
	.long	811690320
	.long	813156801
	.long	814625932
	.long	816097718
	.long	817572162
	.long	819049271
	.long	820529048
	.long	822011498
	.long	823496627
	.long	824984439
	.long	826474939
	.long	827968132
	.long	829464023
	.long	830962617
	.long	832463917
	.long	833967931
	.long	835474661
	.long	836984114
	.long	838496294
	.long	840011206
	.long	841528855
	.long	843049246
	.long	844572384
	.long	846098274
	.long	847626920
	.long	849158328
	.long	850692504
	.long	852229450
	.long	853769174
	.long	855311680
	.long	856856972
	.long	858405056
	.long	859955938
	.long	861509621
	.long	863066111
	.long	864625413
	.long	866187533
	.long	867752475
	.long	869320244
	.long	870890845
	.long	872464285
	.long	874040567
	.long	875619697
	.long	877201680
	.long	878786521
	.long	880374225
	.long	881964798
	.long	883558244
	.long	885154570
	.long	886753780
	.long	888355878
	.long	889960872
	.long	891568765
	.long	893179563
	.long	894793271
	.long	896409895
	.long	898029440
	.long	899651910
	.long	901277312
	.long	902905651
	.long	904536931
	.long	906171159
	.long	907808339
	.long	909448477
	.long	911091579
	.long	912737649
	.long	914386693
	.long	916038716
	.long	917693724
	.long	919351722
	.long	921012715
	.long	922676710
	.long	924343711
	.long	926013723
	.long	927686753
	.long	929362806
	.long	931041886
	.long	932724001
	.long	934409154
	.long	936097352
	.long	937788600
	.long	939482903
	.long	941180268
	.long	942880699
	.long	944584202
	.long	946290784
	.long	948000448
	.long	949713201
	.long	951429049
	.long	953147997
	.long	954870050
	.long	956595215
	.long	958323496
	.long	960054900
	.long	961789432
	.long	963527098
	.long	965267903
	.long	967011854
	.long	968758955
	.long	970509212
	.long	972262632
	.long	974019220
	.long	975778981
	.long	977541922
	.long	979308048
	.long	981077365
	.long	982849878
	.long	984625594
	.long	986404518
	.long	988186656
	.long	989972014
	.long	991760597
	.long	993552412
	.long	995347464
	.long	997145759
	.long	998947303
	.long	1000752102
	.long	1002560162
	.long	1004371488
	.long	1006186087
	.long	1008003964
	.long	1009825126
	.long	1011649578
	.long	1013477326
	.long	1015308377
	.long	1017142735
	.long	1018980408
	.long	1020821401
	.long	1022665720
	.long	1024513371
	.long	1026364360
	.long	1028218693
	.long	1030076377
	.long	1031937417
	.long	1033801819
	.long	1035669590
	.long	1037540735
	.long	1039415261
	.long	1041293173
	.long	1043174479
	.long	1045059183
	.long	1046947292
	.long	1048838813
	.long	1050733751
	.long	1052632112
	.long	1054533904
	.long	1056439131
	.long	1058347801
	.long	1060259919
	.long	1062175491
	.long	1064094525
	.long	1066017025
	.long	1067942999
	.long	1069872453
	.long	1071805392
	.long	1073741824
	.globl	wcf_base_inc
	.align	2
	.type	wcf_base_inc, @object
	.size	wcf_base_inc, 4
wcf_base_inc:
	.long	12740059
	.align	2
	.type	gain_n, @object
	.size	gain_n, 20
gain_n:
	.long	0
	.long	1717986918
	.long	858993459
	.long	572662306
	.long	429496730

| Generated by modules/wavecf/tables.py: eight 1,024-sample frames of int16 (big-endian words),
| then frame 7 again.  Do not edit.
        .text
        .even
        .global wcf_table
wcf_table:
        .word   0,90,181,271,362,452,543,633,724,814,904,995,1085,1175,1265,1355
        .word   1445,1535,1625,1715,1805,1895,1984,2074,2164,2253,2342,2432,2521,2610,2699,2788
        .word   2877,2965,3054,3142,3231,3319,3407,3495,3583,3671,3758,3846,3933,4020,4107,4194
        .word   4280,4367,4453,4539,4625,4711,4797,4882,4968,5053,5138,5222,5307,5391,5475,5559
        .word   5643,5726,5810,5893,5976,6058,6141,6223,6305,6386,6468,6549,6630,6710,6791,6871
        .word   6951,7031,7110,7189,7268,7347,7425,7503,7581,7658,7735,7812,7889,7965,8041,8117
        .word   8192,8267,8342,8417,8491,8564,8638,8711,8784,8856,8929,9000,9072,9143,9214,9284
        .word   9355,9424,9494,9563,9631,9700,9768,9835,9903,9969,10036,10102,10168,10233,10298,10363
        .word   10427,10490,10554,10617,10679,10742,10803,10865,10926,10986,11046,11106,11165,11224,11283,11341
        .word   11399,11456,11512,11569,11625,11680,11735,11790,11844,11897,11951,12003,12056,12108,12159,12210
        .word   12261,12311,12360,12409,12458,12506,12554,12601,12648,12694,12740,12785,12830,12874,12918,12962
        .word   13004,13047,13089,13130,13171,13212,13251,13291,13330,13368,13406,13444,13481,13517,13553,13588
        .word   13623,13658,13691,13725,13758,13790,13822,13853,13884,13914,13944,13973,14001,14029,14057,14084
        .word   14111,14137,14162,14187,14211,14235,14259,14281,14304,14325,14347,14367,14387,14407,14426,14444
        .word   14462,14480,14496,14513,14529,14544,14558,14572,14586,14599,14611,14623,14635,14646,14656,14665
        .word   14675,14683,14691,14699,14706,14712,14718,14723,14728,14732,14736,14739,14741,14743,14744,14745
        .word   14746,14745,14744,14743,14741,14739,14736,14732,14728,14723,14718,14712,14706,14699,14691,14683
        .word   14675,14665,14656,14646,14635,14623,14611,14599,14586,14572,14558,14544,14529,14513,14496,14480
        .word   14462,14444,14426,14407,14387,14367,14347,14325,14304,14281,14259,14235,14211,14187,14162,14137
        .word   14111,14084,14057,14029,14001,13973,13944,13914,13884,13853,13822,13790,13758,13725,13691,13658
        .word   13623,13588,13553,13517,13481,13444,13406,13368,13330,13291,13251,13212,13171,13130,13089,13047
        .word   13004,12962,12918,12874,12830,12785,12740,12694,12648,12601,12554,12506,12458,12409,12360,12311
        .word   12261,12210,12159,12108,12056,12003,11951,11897,11844,11790,11735,11680,11625,11569,11512,11456
        .word   11399,11341,11283,11224,11165,11106,11046,10986,10926,10865,10803,10742,10679,10617,10554,10490
        .word   10427,10363,10298,10233,10168,10102,10036,9969,9903,9835,9768,9700,9631,9563,9494,9424
        .word   9355,9284,9214,9143,9072,9000,8929,8856,8784,8711,8638,8564,8491,8417,8342,8267
        .word   8192,8117,8041,7965,7889,7812,7735,7658,7581,7503,7425,7347,7268,7189,7110,7031
        .word   6951,6871,6791,6710,6630,6549,6468,6386,6305,6223,6141,6058,5976,5893,5810,5726
        .word   5643,5559,5475,5391,5307,5222,5138,5053,4968,4882,4797,4711,4625,4539,4453,4367
        .word   4280,4194,4107,4020,3933,3846,3758,3671,3583,3495,3407,3319,3231,3142,3054,2965
        .word   2877,2788,2699,2610,2521,2432,2342,2253,2164,2074,1984,1895,1805,1715,1625,1535
        .word   1445,1355,1265,1175,1085,995,904,814,724,633,543,452,362,271,181,90
        .word   0,65446,65355,65265,65174,65084,64993,64903,64812,64722,64632,64541,64451,64361,64271,64181
        .word   64091,64001,63911,63821,63731,63641,63552,63462,63372,63283,63194,63104,63015,62926,62837,62748
        .word   62659,62571,62482,62394,62305,62217,62129,62041,61953,61865,61778,61690,61603,61516,61429,61342
        .word   61256,61169,61083,60997,60911,60825,60739,60654,60568,60483,60398,60314,60229,60145,60061,59977
        .word   59893,59810,59726,59643,59560,59478,59395,59313,59231,59150,59068,58987,58906,58826,58745,58665
        .word   58585,58505,58426,58347,58268,58189,58111,58033,57955,57878,57801,57724,57647,57571,57495,57419
        .word   57344,57269,57194,57119,57045,56972,56898,56825,56752,56680,56607,56536,56464,56393,56322,56252
        .word   56181,56112,56042,55973,55905,55836,55768,55701,55633,55567,55500,55434,55368,55303,55238,55173
        .word   55109,55046,54982,54919,54857,54794,54733,54671,54610,54550,54490,54430,54371,54312,54253,54195
        .word   54137,54080,54024,53967,53911,53856,53801,53746,53692,53639,53585,53533,53480,53428,53377,53326
        .word   53275,53225,53176,53127,53078,53030,52982,52935,52888,52842,52796,52751,52706,52662,52618,52574
        .word   52532,52489,52447,52406,52365,52324,52285,52245,52206,52168,52130,52092,52055,52019,51983,51948
        .word   51913,51878,51845,51811,51778,51746,51714,51683,51652,51622,51592,51563,51535,51507,51479,51452
        .word   51425,51399,51374,51349,51325,51301,51277,51255,51232,51211,51189,51169,51149,51129,51110,51092
        .word   51074,51056,51040,51023,51007,50992,50978,50964,50950,50937,50925,50913,50901,50890,50880,50871
        .word   50861,50853,50845,50837,50830,50824,50818,50813,50808,50804,50800,50797,50795,50793,50792,50791
        .word   50790,50791,50792,50793,50795,50797,50800,50804,50808,50813,50818,50824,50830,50837,50845,50853
        .word   50861,50871,50880,50890,50901,50913,50925,50937,50950,50964,50978,50992,51007,51023,51040,51056
        .word   51074,51092,51110,51129,51149,51169,51189,51211,51232,51255,51277,51301,51325,51349,51374,51399
        .word   51425,51452,51479,51507,51535,51563,51592,51622,51652,51683,51714,51746,51778,51811,51845,51878
        .word   51913,51948,51983,52019,52055,52092,52130,52168,52206,52245,52285,52324,52365,52406,52447,52489
        .word   52532,52574,52618,52662,52706,52751,52796,52842,52888,52935,52982,53030,53078,53127,53176,53225
        .word   53275,53326,53377,53428,53480,53533,53585,53639,53692,53746,53801,53856,53911,53967,54024,54080
        .word   54137,54195,54253,54312,54371,54430,54490,54550,54610,54671,54733,54794,54857,54919,54982,55046
        .word   55109,55173,55238,55303,55368,55434,55500,55567,55633,55701,55768,55836,55905,55973,56042,56112
        .word   56181,56252,56322,56393,56464,56536,56607,56680,56752,56825,56898,56972,57045,57119,57194,57269
        .word   57344,57419,57495,57571,57647,57724,57801,57878,57955,58033,58111,58189,58268,58347,58426,58505
        .word   58585,58665,58745,58826,58906,58987,59068,59150,59231,59313,59395,59478,59560,59643,59726,59810
        .word   59893,59977,60061,60145,60229,60314,60398,60483,60568,60654,60739,60825,60911,60997,61083,61169
        .word   61256,61342,61429,61516,61603,61690,61778,61865,61953,62041,62129,62217,62305,62394,62482,62571
        .word   62659,62748,62837,62926,63015,63104,63194,63283,63372,63462,63552,63641,63731,63821,63911,64001
        .word   64091,64181,64271,64361,64451,64541,64632,64722,64812,64903,64993,65084,65174,65265,65355,65446
        .word   0,58,115,173,230,288,346,403,461,518,576,634,691,749,806,864
        .word   922,979,1037,1094,1152,1210,1267,1325,1382,1440,1498,1555,1613,1670,1728,1786
        .word   1843,1901,1958,2016,2074,2131,2189,2246,2304,2362,2419,2477,2534,2592,2650,2707
        .word   2765,2822,2880,2938,2995,3053,3110,3168,3226,3283,3341,3398,3456,3514,3571,3629
        .word   3686,3744,3802,3859,3917,3974,4032,4090,4147,4205,4262,4320,4378,4435,4493,4550
        .word   4608,4666,4723,4781,4838,4896,4954,5011,5069,5126,5184,5242,5299,5357,5414,5472
        .word   5530,5587,5645,5702,5760,5818,5875,5933,5990,6048,6106,6163,6221,6278,6336,6394
        .word   6451,6509,6566,6624,6682,6739,6797,6854,6912,6970,7027,7085,7142,7200,7258,7315
        .word   7373,7430,7488,7546,7603,7661,7718,7776,7834,7891,7949,8006,8064,8122,8179,8237
        .word   8294,8352,8410,8467,8525,8582,8640,8698,8755,8813,8870,8928,8986,9043,9101,9158
        .word   9216,9274,9331,9389,9446,9504,9562,9619,9677,9734,9792,9850,9907,9965,10022,10080
        .word   10138,10195,10253,10310,10368,10426,10483,10541,10598,10656,10714,10771,10829,10886,10944,11002
        .word   11059,11117,11174,11232,11290,11347,11405,11462,11520,11578,11635,11693,11750,11808,11866,11923
        .word   11981,12038,12096,12154,12211,12269,12326,12384,12442,12499,12557,12614,12672,12730,12787,12845
        .word   12902,12960,13018,13075,13133,13190,13248,13306,13363,13421,13478,13536,13594,13651,13709,13766
        .word   13824,13882,13939,13997,14054,14112,14170,14227,14285,14342,14400,14458,14515,14573,14630,14688
        .word   14746,14688,14630,14573,14515,14458,14400,14342,14285,14227,14170,14112,14054,13997,13939,13882
        .word   13824,13766,13709,13651,13594,13536,13478,13421,13363,13306,13248,13190,13133,13075,13018,12960
        .word   12902,12845,12787,12730,12672,12614,12557,12499,12442,12384,12326,12269,12211,12154,12096,12038
        .word   11981,11923,11866,11808,11750,11693,11635,11578,11520,11462,11405,11347,11290,11232,11174,11117
        .word   11059,11002,10944,10886,10829,10771,10714,10656,10598,10541,10483,10426,10368,10310,10253,10195
        .word   10138,10080,10022,9965,9907,9850,9792,9734,9677,9619,9562,9504,9446,9389,9331,9274
        .word   9216,9158,9101,9043,8986,8928,8870,8813,8755,8698,8640,8582,8525,8467,8410,8352
        .word   8294,8237,8179,8122,8064,8006,7949,7891,7834,7776,7718,7661,7603,7546,7488,7430
        .word   7373,7315,7258,7200,7142,7085,7027,6970,6912,6854,6797,6739,6682,6624,6566,6509
        .word   6451,6394,6336,6278,6221,6163,6106,6048,5990,5933,5875,5818,5760,5702,5645,5587
        .word   5530,5472,5414,5357,5299,5242,5184,5126,5069,5011,4954,4896,4838,4781,4723,4666
        .word   4608,4550,4493,4435,4378,4320,4262,4205,4147,4090,4032,3974,3917,3859,3802,3744
        .word   3686,3629,3571,3514,3456,3398,3341,3283,3226,3168,3110,3053,2995,2938,2880,2822
        .word   2765,2707,2650,2592,2534,2477,2419,2362,2304,2246,2189,2131,2074,2016,1958,1901
        .word   1843,1786,1728,1670,1613,1555,1498,1440,1382,1325,1267,1210,1152,1094,1037,979
        .word   922,864,806,749,691,634,576,518,461,403,346,288,230,173,115,58
        .word   0,65478,65421,65363,65306,65248,65190,65133,65075,65018,64960,64902,64845,64787,64730,64672
        .word   64614,64557,64499,64442,64384,64326,64269,64211,64154,64096,64038,63981,63923,63866,63808,63750
        .word   63693,63635,63578,63520,63462,63405,63347,63290,63232,63174,63117,63059,63002,62944,62886,62829
        .word   62771,62714,62656,62598,62541,62483,62426,62368,62310,62253,62195,62138,62080,62022,61965,61907
        .word   61850,61792,61734,61677,61619,61562,61504,61446,61389,61331,61274,61216,61158,61101,61043,60986
        .word   60928,60870,60813,60755,60698,60640,60582,60525,60467,60410,60352,60294,60237,60179,60122,60064
        .word   60006,59949,59891,59834,59776,59718,59661,59603,59546,59488,59430,59373,59315,59258,59200,59142
        .word   59085,59027,58970,58912,58854,58797,58739,58682,58624,58566,58509,58451,58394,58336,58278,58221
        .word   58163,58106,58048,57990,57933,57875,57818,57760,57702,57645,57587,57530,57472,57414,57357,57299
        .word   57242,57184,57126,57069,57011,56954,56896,56838,56781,56723,56666,56608,56550,56493,56435,56378
        .word   56320,56262,56205,56147,56090,56032,55974,55917,55859,55802,55744,55686,55629,55571,55514,55456
        .word   55398,55341,55283,55226,55168,55110,55053,54995,54938,54880,54822,54765,54707,54650,54592,54534
        .word   54477,54419,54362,54304,54246,54189,54131,54074,54016,53958,53901,53843,53786,53728,53670,53613
        .word   53555,53498,53440,53382,53325,53267,53210,53152,53094,53037,52979,52922,52864,52806,52749,52691
        .word   52634,52576,52518,52461,52403,52346,52288,52230,52173,52115,52058,52000,51942,51885,51827,51770
        .word   51712,51654,51597,51539,51482,51424,51366,51309,51251,51194,51136,51078,51021,50963,50906,50848
        .word   50790,50848,50906,50963,51021,51078,51136,51194,51251,51309,51366,51424,51482,51539,51597,51654
        .word   51712,51770,51827,51885,51942,52000,52058,52115,52173,52230,52288,52346,52403,52461,52518,52576
        .word   52634,52691,52749,52806,52864,52922,52979,53037,53094,53152,53210,53267,53325,53382,53440,53498
        .word   53555,53613,53670,53728,53786,53843,53901,53958,54016,54074,54131,54189,54246,54304,54362,54419
        .word   54477,54534,54592,54650,54707,54765,54822,54880,54938,54995,55053,55110,55168,55226,55283,55341
        .word   55398,55456,55514,55571,55629,55686,55744,55802,55859,55917,55974,56032,56090,56147,56205,56262
        .word   56320,56378,56435,56493,56550,56608,56666,56723,56781,56838,56896,56954,57011,57069,57126,57184
        .word   57242,57299,57357,57414,57472,57530,57587,57645,57702,57760,57818,57875,57933,57990,58048,58106
        .word   58163,58221,58278,58336,58394,58451,58509,58566,58624,58682,58739,58797,58854,58912,58970,59027
        .word   59085,59142,59200,59258,59315,59373,59430,59488,59546,59603,59661,59718,59776,59834,59891,59949
        .word   60006,60064,60122,60179,60237,60294,60352,60410,60467,60525,60582,60640,60698,60755,60813,60870
        .word   60928,60986,61043,61101,61158,61216,61274,61331,61389,61446,61504,61562,61619,61677,61734,61792
        .word   61850,61907,61965,62022,62080,62138,62195,62253,62310,62368,62426,62483,62541,62598,62656,62714
        .word   62771,62829,62886,62944,63002,63059,63117,63174,63232,63290,63347,63405,63462,63520,63578,63635
        .word   63693,63750,63808,63866,63923,63981,64038,64096,64154,64211,64269,64326,64384,64442,64499,64557
        .word   64614,64672,64730,64787,64845,64902,64960,65018,65075,65133,65190,65248,65306,65363,65421,65478
        .word   0,29,58,86,115,144,173,202,230,259,288,317,346,374,403,432
        .word   461,490,518,547,576,605,634,662,691,720,749,778,806,835,864,893
        .word   922,950,979,1008,1037,1066,1094,1123,1152,1181,1210,1238,1267,1296,1325,1354
        .word   1382,1411,1440,1469,1498,1526,1555,1584,1613,1642,1670,1699,1728,1757,1786,1814
        .word   1843,1872,1901,1930,1958,1987,2016,2045,2074,2102,2131,2160,2189,2218,2246,2275
        .word   2304,2333,2362,2390,2419,2448,2477,2506,2534,2563,2592,2621,2650,2678,2707,2736
        .word   2765,2794,2822,2851,2880,2909,2938,2966,2995,3024,3053,3082,3110,3139,3168,3197
        .word   3226,3254,3283,3312,3341,3370,3398,3427,3456,3485,3514,3542,3571,3600,3629,3658
        .word   3686,3715,3744,3773,3802,3830,3859,3888,3917,3946,3974,4003,4032,4061,4090,4118
        .word   4147,4176,4205,4234,4262,4291,4320,4349,4378,4406,4435,4464,4493,4522,4550,4579
        .word   4608,4637,4666,4694,4723,4752,4781,4810,4838,4867,4896,4925,4954,4982,5011,5040
        .word   5069,5098,5126,5155,5184,5213,5242,5270,5299,5328,5357,5386,5414,5443,5472,5501
        .word   5530,5558,5587,5616,5645,5674,5702,5731,5760,5789,5818,5846,5875,5904,5933,5962
        .word   5990,6019,6048,6077,6106,6134,6163,6192,6221,6250,6278,6307,6336,6365,6394,6422
        .word   6451,6480,6509,6538,6566,6595,6624,6653,6682,6710,6739,6768,6797,6826,6854,6883
        .word   6912,6941,6970,6998,7027,7056,7085,7114,7142,7171,7200,7229,7258,7286,7315,7344
        .word   7373,7402,7430,7459,7488,7517,7546,7574,7603,7632,7661,7690,7718,7747,7776,7805
        .word   7834,7862,7891,7920,7949,7978,8006,8035,8064,8093,8122,8150,8179,8208,8237,8266
        .word   8294,8323,8352,8381,8410,8438,8467,8496,8525,8554,8582,8611,8640,8669,8698,8726
        .word   8755,8784,8813,8842,8870,8899,8928,8957,8986,9014,9043,9072,9101,9130,9158,9187
        .word   9216,9245,9274,9302,9331,9360,9389,9418,9446,9475,9504,9533,9562,9590,9619,9648
        .word   9677,9706,9734,9763,9792,9821,9850,9878,9907,9936,9965,9994,10022,10051,10080,10109
        .word   10138,10166,10195,10224,10253,10282,10310,10339,10368,10397,10426,10454,10483,10512,10541,10570
        .word   10598,10627,10656,10685,10714,10742,10771,10800,10829,10858,10886,10915,10944,10973,11002,11030
        .word   11059,11088,11117,11146,11174,11203,11232,11261,11290,11318,11347,11376,11405,11434,11462,11491
        .word   11520,11549,11578,11606,11635,11664,11693,11722,11750,11779,11808,11837,11866,11894,11923,11952
        .word   11981,12010,12038,12067,12096,12125,12154,12182,12211,12240,12269,12298,12326,12355,12384,12413
        .word   12442,12470,12499,12528,12557,12586,12614,12643,12672,12701,12730,12758,12787,12816,12845,12874
        .word   12902,12931,12960,12989,13018,13046,13075,13104,13133,13162,13190,13219,13248,13277,13306,13334
        .word   13363,13392,13421,13450,13478,13507,13536,13565,13594,13622,13651,13680,13709,13738,13766,13795
        .word   13824,13853,13882,13910,13939,13968,13997,14026,14054,14083,14112,14141,14170,14198,14227,14256
        .word   14285,14314,14342,14371,14400,14429,14458,14486,14515,14544,14573,14602,14630,14659,14688,14717
        .word   50790,50819,50848,50877,50906,50934,50963,50992,51021,51050,51078,51107,51136,51165,51194,51222
        .word   51251,51280,51309,51338,51366,51395,51424,51453,51482,51510,51539,51568,51597,51626,51654,51683
        .word   51712,51741,51770,51798,51827,51856,51885,51914,51942,51971,52000,52029,52058,52086,52115,52144
        .word   52173,52202,52230,52259,52288,52317,52346,52374,52403,52432,52461,52490,52518,52547,52576,52605
        .word   52634,52662,52691,52720,52749,52778,52806,52835,52864,52893,52922,52950,52979,53008,53037,53066
        .word   53094,53123,53152,53181,53210,53238,53267,53296,53325,53354,53382,53411,53440,53469,53498,53526
        .word   53555,53584,53613,53642,53670,53699,53728,53757,53786,53814,53843,53872,53901,53930,53958,53987
        .word   54016,54045,54074,54102,54131,54160,54189,54218,54246,54275,54304,54333,54362,54390,54419,54448
        .word   54477,54506,54534,54563,54592,54621,54650,54678,54707,54736,54765,54794,54822,54851,54880,54909
        .word   54938,54966,54995,55024,55053,55082,55110,55139,55168,55197,55226,55254,55283,55312,55341,55370
        .word   55398,55427,55456,55485,55514,55542,55571,55600,55629,55658,55686,55715,55744,55773,55802,55830
        .word   55859,55888,55917,55946,55974,56003,56032,56061,56090,56118,56147,56176,56205,56234,56262,56291
        .word   56320,56349,56378,56406,56435,56464,56493,56522,56550,56579,56608,56637,56666,56694,56723,56752
        .word   56781,56810,56838,56867,56896,56925,56954,56982,57011,57040,57069,57098,57126,57155,57184,57213
        .word   57242,57270,57299,57328,57357,57386,57414,57443,57472,57501,57530,57558,57587,57616,57645,57674
        .word   57702,57731,57760,57789,57818,57846,57875,57904,57933,57962,57990,58019,58048,58077,58106,58134
        .word   58163,58192,58221,58250,58278,58307,58336,58365,58394,58422,58451,58480,58509,58538,58566,58595
        .word   58624,58653,58682,58710,58739,58768,58797,58826,58854,58883,58912,58941,58970,58998,59027,59056
        .word   59085,59114,59142,59171,59200,59229,59258,59286,59315,59344,59373,59402,59430,59459,59488,59517
        .word   59546,59574,59603,59632,59661,59690,59718,59747,59776,59805,59834,59862,59891,59920,59949,59978
        .word   60006,60035,60064,60093,60122,60150,60179,60208,60237,60266,60294,60323,60352,60381,60410,60438
        .word   60467,60496,60525,60554,60582,60611,60640,60669,60698,60726,60755,60784,60813,60842,60870,60899
        .word   60928,60957,60986,61014,61043,61072,61101,61130,61158,61187,61216,61245,61274,61302,61331,61360
        .word   61389,61418,61446,61475,61504,61533,61562,61590,61619,61648,61677,61706,61734,61763,61792,61821
        .word   61850,61878,61907,61936,61965,61994,62022,62051,62080,62109,62138,62166,62195,62224,62253,62282
        .word   62310,62339,62368,62397,62426,62454,62483,62512,62541,62570,62598,62627,62656,62685,62714,62742
        .word   62771,62800,62829,62858,62886,62915,62944,62973,63002,63030,63059,63088,63117,63146,63174,63203
        .word   63232,63261,63290,63318,63347,63376,63405,63434,63462,63491,63520,63549,63578,63606,63635,63664
        .word   63693,63722,63750,63779,63808,63837,63866,63894,63923,63952,63981,64010,64038,64067,64096,64125
        .word   64154,64182,64211,64240,64269,64298,64326,64355,64384,64413,64442,64470,64499,64528,64557,64586
        .word   64614,64643,64672,64701,64730,64758,64787,64816,64845,64874,64902,64931,64960,64989,65018,65046
        .word   65075,65104,65133,65162,65190,65219,65248,65277,65306,65334,65363,65392,65421,65450,65478,65507
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790,50790
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621,60621
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429,63429
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553,64553
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746,14746
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
        .word   65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060,65060
| <<< GENERATED ENGINE
