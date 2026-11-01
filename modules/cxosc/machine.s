| CX OSC -- machine list row (sixth after the stock five). GNU as, -mcpu=5475;
| DRAM unit linked beside poly.s (modules/cxosc/manifest.py, Linked
| "fmmachine"). Signature "CX", 1. From Tim Hastie's v2.15 machine.s
| (timhastie/octatrick-modules 17ba281, MIT), itself adapted from Modwerk's
| FM Synth (repeat98/modwerk @ 1c1d938, MIT, Copyright (c) 2026 Modwerk
| contributors). See modules/cxosc/NOTICE.
|
| THE ROWS. ml_rows lists rows after the stock five (remix.inc: CX OSC
| always; SY DRUM when HAVE_SYDRUM). A row descriptor (20 bytes): +0
| signature ("CX", 1), +3 engine kind, +4 name, +8 twelve seed bytes,
| +12 PLAYBACK descriptor routine, +16 flags. Detours take 5+ML_COUNT so
| several machine modules share the sites.
|
| Chooser / Part validation / sample-free transport keep Modwerk's hook
| sites and register contracts (written out in asm). This tree: machine
| window commit shares 0x40079816 with po_machwin; PLAYBACK via page.s
| pg_resolve; selection guard below (not Modwerk's); name table filled
| at run time; marker path off.
|
| THE STORAGE. Chosen track = FLEX (machine byte 1) with signature
| "C", "X", 1 in NEIGHBOR PLAYBACK: bank + part * 6322 + 0x8edbc + 30 *
| track (and the battery-RAM shadow). Seed PLAYBACK: PTCH 0, RATO 1,
| INDX 32, FOLD 1, SYMM 0, FDBK 0; SETUP 0 (LOOP, SLIC,
| LEN, RATE, TSTR, TSNS: OFF); choosing it again keeps the patch; choosing any other
| row clears the signature.
|
| THE MACHINE CHANGE (2.12). A change of the machine a track plays, where the old or the
| new machine is a row's (CX OSC, SY DRUM), sets the track to the new machine's init:
| PLAYBACK and its SETUP, AMP and AMP SETUP, the three LFOs and LFO SETUP; step and scene
| locks (SY DRUM's lock rows too) and the FX1 / FX2 slots stay (ml_reset). Through either list (fm_choose) and through
| the slot assigner (poly.s, ml_became; until 2.14 also a marker file, through it and the file browser). A
| change between two stock machines is stock's (nothing written); a project, a Part
| reload, a paste or a pattern change is no change (the bytes saved are the bytes played).
|
| THE SELECTION GUARD (2.15). CX OSC and SY DRUM render on the ColdFire, and too many
| tracks of them freeze the unit. Both lists refuse a choice that would take the ACTIVE
| Part past the limits of synth/machine_limits.inc (2.15: at most 2 SY DRUM tracks, at
| most 1 CX OSC track, and CX OSC with at most 1 SY DRUM track), counted over the
| Part's eight audio tracks by the signature each machine keeps in the Part (ml_guard).
| A refused choice writes nothing: the track keeps its machine and its patch, the
| firmware's own message popup shows why (the stock routine and duration the lists use
| for their own NOT AVAILABLE HERE!), and the window leaves through the same exit as
| that stock refusal, so the list works as before. Choosing a track's own machine again
| and choosing any stock machine are always allowed. Stock's copy / paste and undo are
| guarded the same way (the paste guards below), and the 2.10 marker file selects nothing
| since 2.15 (poly.s po_slot_marker), so a row's machine comes from a guarded write only.
| A Part saved by an older build with more loads and plays as saved.
|
| The engine's side is poly.s: po_is_synth (and the quantizer's qz_is_synth) answer
| yes for a signed track, po_fmstart starts its voice without a sample, po_fmsource
| hands its source to sy_render, sy_call writes the source header stock would have;
| po_signed answers the row's engine kind (2.11).

        .text
        .global fm_machine_name, fm_name_a, fm_src_names
        .global fm_setup_row, fm_chooser_row, fm_setup_open, fm_chooser_open
        .global fm_setup_edit6, fm_setup_draw6
        .global fm_main_commit, fm_src_commit, fm_src_commit2
        .global fm_tick, fm_validate
        .global ml_win_count, ml_src_count, ml_name_bound, ml_draw_bound, ml_hi_bound, ml_cur_bound
        .global ml_clamp1, ml_clamp2, ml_clamp3, ml_clamp4, ml_clamp5
        .global ml_rows, fm_row
        .global ml_reset, ml_kindof, ml_became | 2.12: the machine change's init (poly.s: the marker route)
        .global ml_guard, ml_limits      | 2.15: the selection guard and its limits (machine_limits.inc)
        .global fm_page_store, fm_track_undo, fm_track_paste, fm_part_undo, fm_part_paste, fm_preview | 2.15: the paste guards
        .include "remix.inc"             | 2.11: HAVE_SYDRUM and the shared equates (engine_abi.inc; manifest.py)

        .if     HK_MACHINE_ROWS          | beside other machines (modules/hooks, machine_rows): our
        .set    FM_ROW, MC_ROW           | place in the list, after theirs; their hooks are the head's,
        .global fm_main_commit_hk, fm_publish, fm_name, fm_type | which chain into ours for any row not theirs
        .else
        .set    FM_ROW, 5                | the sixth row, the first after the stock five: CX OSC
        .endif
        .set    ML_COUNT, 1 + HAVE_SYDRUM | the rows after the stock five (2.11)
        .set    ML_LAST, 4 + ML_COUNT    | the last row's index
        .set    RD_KIND, 3               | a row descriptor: +0 signature (3 B), +3 kind, +4 name,
        .set    RD_NAME, 4               | +8 seeds (12 B), +12 its PLAYBACK descriptor routine, +16 flags
        .set    RD_SEEDS, 8
        .set    RD_DESC, 12
        .set    RD_FLAGS, 16
        .set    FLEX, 1
        .set    PART_OFF, 0x8ed80        | the Part's own +0 (what the validator is handed)
        .set    FLEX_PB, 0x8edb0         | + 30 * track: the FLEX PLAYBACK bytes (PTCH STRT LEN RATE RTRG RTIM)
        .set    SETUP_GAP, 0x1b0         | ... their FLEX SETUP bytes this far on (blob + 0x8ef60 + 30 * track)
        .set    CV_SETUP, 32             | + lane: the PLAYBACK page's SETUP bytes (LOOP SLIC LEN RATE TSTR TSNS)
        .set    SRC_CURSOR, 0x460d5c30   | SRC SETUP's machine row (the sample-list window's)
        .set    NAMES, 0x400a78c8        | the stock machine-name table, five pointers (STATIC .. PICKUP)
        .set    PB_TABLE, 0x400d5f38     | the machine -> PLAYBACK descriptor table (slot 5: a spare)
        .set    FLEX_DEF, 0x400d320c     | the FLEX descriptor's defaults: 6 PLAYBACK, then 6 SETUP bytes
        .set    NAME_RET, 0x400334de     | fm_machine_name's way back
        .set    NAME_A_RET, 0x4003d722
        .set    SETUP_ROW_RET, 0x4003c986
        .set    CHOOSER_HIT, 0x400786ce  | the chooser's row-equals-machine branch ...
        .set    CHOOSER_MISS, 0x400786fc | ... and its other one
        .set    SETUP_OPEN_RET, 0x400585e6
        .set    CHOOSER_OPEN_RET, 0x40078890
        .set    EDIT6_RET, 0x4003a536
        .set    DRAW6_RET, 0x4003cda0
        .set    SRC_COMMIT_RET, 0x4005a61c
        .set    SRC_COMMIT2_RET, 0x4005a856
        .set    TICK_A, 0x4005213c       | the UI tick's two calls fm_tick replays (the first is PC-relative
        .set    TICK_B, 0x4007e940       | in stock, so it is replayed by its absolute address)
        .set    TICK_RET, 0x40052228
        .set    WIN_COUNT_RET, 0x40079250 | the machine window's list init after its `pea 5; pea 6` (ml_win_count)
        .set    SRC_COUNT_RET, 0x40058602 | SRC SETUP's list init after its `pea 5; pea 5` (ml_src_count)
        .set    NAME_BOUND_IN, 0x4003c956 | SRC SETUP's name lookup: the row has a name ...
        .set    NAME_BOUND_OUT, 0x4003c95a | ... or not (the default string)
        .set    DRAW_BOUND_IN, 0x40078684 | the machine window's drawer: the row's name drawn (after the formatter call) ...
        .set    WIN_LIST, 0x460e7386     | SELECT MACHINE TYPE's list: +0 top, +4 cursor in the window, +8 row, +12 visible, +16 count
        .set    DRAW_BOUND_OUT, 0x400786a2 | ... or not
        .set    HI_BOUND_IN, 0x400786d4  | the machine window's highlight: the row is highlighted ...
        .set    CUR_BOUND_IN, 0x400797cc | the machine window's cursor: the row is applied ...
        .set    CUR_BOUND_OUT, 0x4007990c | ... or not
        .set    VALIDATE_BODY, 0x40002320 | the Part validator after its prologue
        .set    TOAST, 0x4005a2b8        | the firmware's message popup: (text, duration); both lists' own refusal calls it
        .set    TOAST_TIME, 48           | ... with this duration (NOT AVAILABLE HERE!)
        .set    WIN_REFUSE, 0x4007989c   | the machine window's way out after its own refusal (the stack as at the commit)
        .set    SRC_REFUSE, 0x4005a8ba   | SRC SETUP's way out after its own refusal (both of its paths)
        .if     (ML_FM_MAX < 1) || (ML_FM_MAX > 8) || (ML_SY_MAX < 1) || (ML_SY_MAX > 8) || (ML_SY_WITH_FM < 0) || (ML_SY_WITH_FM > 8)
        .error  "machine_limits.inc: each limit is 1..8 (ML_SY_WITH_FM 0..8)"
        .endif

| ---- fm_choose: d1 = the chosen row, d2 = the track (the current Part) -> d1 = the
| machine byte to store. A row of ml_rows -> FLEX, with that row's signature written into
| the Part and its shadow; a stock row: unchanged, any row's signature cleared. Preserves
| every other register.
| THE MACHINE CHANGE (2.12, Tim, 10 Oct 2026: "all the parameters, including any LFO
| settings, should be set to init. They should not inherit any parameters from the last
| machine that was on that track."). The machine the track plays before the choice (ml_ident:
| 0 a stock machine, 1 FM -- chosen, or FLEX with a marker slot --, 2 SY DRUM) is compared
| with the one it plays after it (the row's engine kind; a stock row: 0, or 1 for FLEX
| whose FLEX slot holds a marker file; 2.15: no slot is a marker, po_slot_marker). When they differ and either is one of the rows'
| machines, the track gets the new machine's init (ml_reset): its PLAYBACK and PLAYBACK
| SETUP bytes, the AMP and AMP SETUP pages, the three LFOs and LFO SETUP; the step and scene
| locks (SY DRUM's lock rows too) and the FX1 / FX2 slots are kept. The same machine again keeps the patch. A
| change between stock machines writes nothing here (stock's own behaviour: each machine
| keeps its PLAYBACK column, every other page stays).
fm_choose:
        lea     -36(%sp),%sp
        movem.l %d0/%d3/%a0-%a6,(%sp)
        movea.l PART_PTR,%a0
        mvz.b   PART_IDX,%d0
        move.l  #6322,%d3
        muls.l  %d3,%d0                  | part * 6322
        adda.l  %d0,%a0                  | the Part
        lea     PART_SHADOW,%a1
        adda.l  %d0,%a1                  | its shadow
        move.l  %d2,%d0
        mulu.w  #30,%d0                  | track * 30
        adda.l  %d0,%a0
        adda.l  %d0,%a1
        movea.l %a0,%a2
        adda.l  #SIG_OFF,%a2             | a2 = the signature in the Part
        movea.l %a1,%a3
        adda.l  #SIG_OFF,%a3             | a3 = ... in the shadow
        bsr     ml_ident                 | (d2) the machine the track plays now: 0 / 1 FM / 2 SY DRUM
        move.l  %d0,%d3
        move.l  %d1,%d0
        subq.l  #FM_ROW,%d0              | the row's index in ml_rows
        cmpi.l  #ML_COUNT,%d0
        bcc     fm_ch_stock              | (unsigned) a stock row
        lea     ml_rows(%pc),%a6
        movea.l (%a6,%d0.l*4),%a6        | a6 = the row's descriptor
        mvz.b   RD_KIND(%a6),%d0         | the machine it plays
        cmp.l   %d3,%d0
        beq     fm_ch_sign               | that machine already: its patch is the user's
        bsr     ml_reset                 | its init (d0 = its kind)
fm_ch_sign:
        move.b  (%a6),(%a2)              | the row's signature: the Part ...
        move.b  1(%a6),1(%a2)
        move.b  2(%a6),2(%a2)
        move.b  (%a6),(%a3)              | ... and its shadow
        move.b  1(%a6),1(%a3)
        move.b  2(%a6),2(%a3)
        moveq   #FLEX,%d1                | stored as FLEX
        bra     fm_ch_out
fm_ch_stock:
        moveq   #0,%d0                   | a stock machine ...
        cmpi.l  #FLEX,%d1
        bne     fm_ch_new
        bsr     ml_flexmark              | ... but FLEX over a marker slot plays the FM voice
fm_ch_new:
        cmp.l   %d3,%d0
        beq     fm_ch_unsign             | the same machine (or stock to stock): nothing written
        bsr     ml_reset                 | d0 = 0 / 1, d1 = the stock machine
fm_ch_unsign:
        movea.l %a2,%a0
        bsr     fm_unsign
        movea.l %a3,%a0
        bsr     fm_unsign
fm_ch_out:
        movem.l (%sp),%d0/%d3/%a0-%a6
        lea     36(%sp),%sp
        rts
| ml_ident: d2 = track of the current Part -> d0 = the machine it plays: 1 FM (CX OSC
| chosen; until 2.14 also FLEX with an FMSYNTH* / SYNTH* slot), 2 SY DRUM (chosen), 0 a stock machine;
| tst.l done. Preserves every other register.
ml_ident:
        .if     HAVE_SYDRUM
        jmp     po_ident
        .else
        jmp     po_is_synth
        .endif
| ml_flexmark: d2 = track -> d0 = 1 when the current Part's FLEX slot of the track holds a
| marker file (po_slot_marker), else 0; tst.l done. Preserves every other register.
ml_flexmark:
        move.l  %a0,-(%sp)
        bsr     ml_part
        move.l  %d2,%d0
        mulu.w  #5,%d0
        adda.l  %d0,%a0
        adda.l  #SLOT_FLEX,%a0
        mvz.b   (%a0),%d0                | its FLEX slot, 0-based
        movea.l (%sp)+,%a0
        jmp     po_slot_marker
| ml_part: a0 := the current Part (the bank blob + part * 6322). Preserves every other register.
ml_part:
        move.l  %d0,-(%sp)
        mvz.b   PART_IDX,%d0
        mulu.w  #6322,%d0                | part * 6322 (part 0..3)
        movea.l PART_PTR,%a0
        adda.l  %d0,%a0
        move.l  (%sp)+,%d0
        rts
| ml_kindof: d0 = a machine byte, d1 = a FLEX slot, d2 = track of the current Part -> d0 =
| the machine the track plays with them: 0 a stock machine, the row's kind for FLEX with a
| row's signature (the Part's), 1 for FLEX over a marker slot; tst.l done. Preserves every
| other register (the assigners' test, before or after their write: poly.s).
ml_kindof:
        cmpi.l  #FLEX,%d0
        bne     ml_ko_stock
        move.l  %a0,-(%sp)
        bsr     ml_part
        move.l  %d2,%d0
        mulu.w  #30,%d0
        adda.l  %d0,%a0
        adda.l  #SIG_OFF,%a0             | the track's signature place
        bsr     ml_sigrow
        bmi     ml_ko_marker
        lea     ml_rows(%pc),%a0
        movea.l (%a0,%d0.l*4),%a0
        mvz.b   RD_KIND(%a0),%d0         | the row's machine
        movea.l (%sp)+,%a0
        rts
ml_ko_marker:
        movea.l (%sp)+,%a0
        move.l  %d1,%d0
        jmp     po_slot_marker
ml_ko_stock:
        moveq   #0,%d0
        rts
| ml_became: the slot assigner's test (poly.s po_assign, after its slot-byte write): d0 =
| the old machine, d1 = the new one, d2 = the track, d3 = the old slot of the new machine's
| column, d4 = its new slot. The machine the track played before the assignment and the one
| it plays after it (ml_kindof, the FLEX slot being d3 / d4 when the new machine is FLEX,
| else the Part's): different, and one of them a row's -> ml_reset to the new one. The
| marker route: a FLEX track given an FMSYNTH* / SYNTH* slot, or a marker track given a
| sample, a STATIC slot... 2.15: a track that leaves FLEX keeps no signature (cleared
| after its init), and FLEX given to a track that was not FLEX revives none (cleared
| before: the slot assigned plays) -- a row's machine comes from a guarded write only.
| Preserves every register.
ml_became:
        lea     -24(%sp),%sp
        movem.l %d0-%d5,(%sp)
        cmpi.l  #FLEX,%d1
        bne     ml_bc_kinds
        cmpi.l  #FLEX,%d0
        beq     ml_bc_kinds              | FLEX to FLEX: the track keeps its machine
        bsr     ml_unsign_t              | (2.15) FLEX given now: no signature revived
ml_bc_kinds:
        move.l  %d1,%d5                  | the new machine
        cmpi.l  #FLEX,%d1
        beq     ml_bc_slots              | the FLEX column's slots are d3 (before) and d4 (after)
        bsr     ml_flexslot              | another column: the FLEX slot is the Part's, unchanged
        move.l  %d1,%d3
        move.l  %d1,%d4
ml_bc_slots:
        move.l  %d3,%d1
        bsr     ml_kindof                | d0 (the old machine), d1 (its FLEX slot): before
        move.l  %d0,%d3
        move.l  %d5,%d0
        move.l  %d4,%d1
        bsr     ml_kindof                | after
        cmp.l   %d3,%d0
        beq     ml_bc_out
        move.l  %d5,%d1                  | the new machine (the column of a stock init)
        bsr     ml_reset
ml_bc_out:
        cmpi.l  #FLEX,%d5
        beq     ml_bc_rts
        bsr     ml_unsign_t              | (2.15) not FLEX now: the signature goes
ml_bc_rts:
        movem.l (%sp),%d0-%d5
        lea     24(%sp),%sp
        rts
| ml_flexslot: d2 = track -> d1 = the current Part's FLEX slot of the track (0-based).
| Preserves every other register.
ml_flexslot:
        move.l  %a0,-(%sp)
        bsr     ml_part
        move.l  %d2,%d1
        mulu.w  #5,%d1
        adda.l  %d1,%a0
        adda.l  #SLOT_FLEX,%a0
        mvz.b   (%a0),%d1
        movea.l (%sp)+,%a0
        rts

| ---- ml_reset (2.12): d0 = the machine the track gets (0 a stock machine, 1 CX OSC, 2 SY
| DRUM), d1 = the stock machine (d0 = 0), d2 = the track of the current Part. Writes the
| machine's INIT into the Part, its battery-RAM shadow and the track's live lane, so the
| page shows it at once, the next frame plays it and SAVE keeps it:
|   * PLAYBACK and PLAYBACK SETUP: a row's machine -- its twelve seeds in the FLEX column (FM
|     SYNTH: PTCH 0, RATO 1, INDX 32, FOLD 1, SYMM 0, FDBK 0, SETUP 0; SY DRUM: PTCH 0, MODE
|     A, WDTH 64, SWEP 0, SPED 64, DEC 64, LSPD 64, LDEP 0, WAVE OFF, S&H OFF); a stock
|     machine -- its column at the defaults of its stock PLAYBACK descriptor, and the FLEX
|     column at FLEX's (the FLEX bytes a row's machine had used: they are no sample settings);
|   * AMP (ATK HOLD REL VOL BAL XVOL), AMP SETUP (AMP SYNC ATCK FX1 FX2, and LEG / TRIG), the
|     LFO page (SPD1..3 DEP1..3) and LFO SETUP (PMTR WAVE MULT TRIG of each LFO): the stock
|     new-track values -- what the stock Part initialiser (0x40005638, run for every Part of
|     a new project and by Part CLEAR) writes, read here from the same stock descriptors at
|     run time (their defaults: page 1 at P + 0x5e, page 2 at P + 0x64; the six PMTR / WAVE
|     bytes from the LFO page's slot 6 / 7 defaults and the six MULT / TRIG bytes from its
|     slot 8 / 9 defaults, alternately, as the initialiser writes them);
|     CX OSC: VOIC 1 and CHRD off in LFO 3's SPD3 / DEP3 bytes;
| FX1 / FX2 (their effect, page and setup bytes) are kept: effect slots, not the machine's.
| Step locks, scene locks and SY DRUM's own lock rows are kept, as at a stock machine change.
| The live lane gets the bytes written (its PLAYBACK, SETUP, page-1 and page-2 bytes, the
| page-1 value words byte << 8, their slew counters cleared): the stock machine change
| reloads a track from its Part only for PICKUP (0x400972fc -> 0x40001f18), and the frame
| builder refreshes the words from the Part only at a trig from another bank or Part (8 Oct
| 2026: a stale RATE word played 67.8 Hz). Preserves every register.
        .set    LFO_P, 0x400d37f6        | the stock LFO page descriptor (P form)
        .set    AMP_P, 0x400d3988        | the stock AMP page descriptor (P form)
        .set    DEF1, 0x5e               | a descriptor's twelve defaults: page 1 (6), then page 2 (6) at + 6
        .set    PB_OFF, 0x8edaa          | + 30 * track + 6 * machine: a PLAYBACK column (SETUP_GAP on: its SETUP column)
        .set    PAGE1_OFF, 0x8ee9a       | + 24 * track: LFO (SPD1..3 DEP1..3), AMP, FX1, FX2 page 1
        .set    PAGE2_OFF, 0x8f072       | + 30 * track: PMTR1..3 WAVE1..3, AMP SETUP, FX1 SETUP, FX2 SETUP, the MULT / TRIG bytes
        .set    SLOT_FLEX, 0x8f04b       | + 5 * track: the FLEX column's slot byte
        .set    CV_LFO, 6                | the lane: page 1 at + 6 (LFO, then AMP at + 12)
        .set    CV_P2, 38                | ... page 2's PMTR / WAVE at + 38, AMP SETUP at + 44
        .set    CV_MT, 62                | ... MULT / TRIG at + 62
ml_reset:
        lea     -48(%sp),%sp
        movem.l %d0-%d5/%a0-%a5,(%sp)
        bsr     ml_part                  | a0 = the Part
        move.l  %a0,%d3
        sub.l   PART_PTR,%d3
        lea     PART_SHADOW,%a1
        adda.l  %d3,%a1                  | a1 = its shadow
        move.l  %d2,%d3
        mulu.w  #CV_STRIDE,%d3
        addi.l  #CURVALS,%d3
        movea.l %d3,%a2                  | a2 = the track's live lane
        move.l  %d2,%d3
        lsl.l   #6,%d3
        addi.l  #CV_WORDS,%d3
        movea.l %d3,%a3                  | a3 = its value words
        move.l  %d0,%d4                  | the machine
        beq     ml_rs_stock
        bsr     ml_kindrow               | a5 = the row's descriptor
        movea.l RD_SEEDS(%a5),%a5        | its seeds: 6 PLAYBACK, then 6 SETUP
        moveq   #FLEX,%d1
        moveq   #1,%d3
        bsr     ml_column                | the FLEX column, the lane's too
        bra     ml_rs_pages
ml_rs_stock:
        move.l  %d1,%d5                  | the stock machine
        moveq   #FLEX,%d1
        movea.l PB_TABLE+4*FLEX,%a5
        lea     DEF1(%a5),%a5            | FLEX's defaults
        moveq   #0,%d3
        bsr     ml_column                | the FLEX column (Part and shadow)
        move.l  %d5,%d1
        lea     PB_TABLE,%a5             | the machine -> PLAYBACK descriptor table
        movea.l (%a5,%d1.l*4),%a5
        lea     DEF1(%a5),%a5            | the machine's defaults
        moveq   #1,%d3
        bsr     ml_column                | its column, the lane's too
ml_rs_pages:
        move.l  %d2,%d3
        lsl.l   #3,%d3
        move.l  %d3,%d0
        add.l   %d3,%d3
        add.l   %d0,%d3                  | track * 24
        addi.l  #PAGE1_OFF,%d3
        lea     LFO_P+DEF1,%a4           | the LFO page: SPD1..3 DEP1..3
        moveq   #0,%d1
ml_rs_lfo:
        mvz.b   (%a4)+,%d0
        cmpi.l  #1,%d4
        bne     ml_rs_lfo1               | CX OSC: SPD3 = VOIC 1, DEP3 = CHRD off
        cmpi.l  #2,%d1
        bne     ml_rs_chrd
        moveq   #1,%d0
ml_rs_chrd:
        cmpi.l  #5,%d1
        bne     ml_rs_lfo1
        moveq   #0,%d0
ml_rs_lfo1:
        bsr     ml_p1byte
        addq.l  #1,%d1
        cmpi.l  #6,%d1
        bne     ml_rs_lfo
        lea     AMP_P+DEF1,%a4           | the AMP page: ATK HOLD REL VOL BAL XVOL
ml_rs_amp:
        mvz.b   (%a4)+,%d0
        bsr     ml_p1byte
        addq.l  #1,%d1
        cmpi.l  #12,%d1
        bne     ml_rs_amp
        move.l  %d2,%d3
        lsl.l   #5,%d3
        sub.l   %d2,%d3
        sub.l   %d2,%d3                  | track * 30
        addi.l  #PAGE2_OFF,%d3
        moveq   #0,%d1                   | page 2's bytes 0..5: PMTR / WAVE of LFO 1..3
        lea     LFO_P+DEF1+6,%a4         | (the LFO page's slot 6 / 7 defaults: PMTR, WAVE)
        bsr     ml_p2pairs
        lea     AMP_P+DEF1+6,%a4         | 6..11: AMP SETUP
ml_rs_amps:
        mvz.b   (%a4)+,%d0
        bsr     ml_p2byte
        addq.l  #1,%d1
        cmpi.l  #12,%d1
        bne     ml_rs_amps
        moveq   #24,%d1                  | 24..29: MULT / TRIG of LFO 1..3
        lea     LFO_P+DEF1+8,%a4         | (slot 8 / 9 defaults: MULT, TRIG)
        bsr     ml_p2pairs
        move.l  %d2,%d0
        lsl.l   #5,%d0
        addi.l  #CV_SLEW,%d0
        movea.l %d0,%a4                  | the slew counters of lane bytes 0..19 (a long per four)
        clr.l   (%a4)+
        clr.l   (%a4)+
        clr.l   (%a4)+
        clr.l   (%a4)+
        clr.l   (%a4)
        movem.l (%sp),%d0-%d5/%a0-%a5
        lea     48(%sp),%sp
        rts
| ml_column: d1 = a machine's column, d2 = track, a5 = 12 bytes (6 PLAYBACK, 6 SETUP), d3 = 1
| to write the live lane (a2) and the value words (a3) too, a0 / a1 = the Part / shadow ->
| the column's PLAYBACK and SETUP bytes written. Clobbers d0 only.
ml_column:
        lea     -12(%sp),%sp
        movem.l %d1/%d4-%d5,(%sp)
        move.l  %d2,%d0
        mulu.w  #30,%d0
        move.l  %d1,%d4
        mulu.w  #6,%d4
        add.l   %d4,%d0
        addi.l  #PB_OFF,%d0              | the column's PLAYBACK bytes
        move.l  %d0,%d5
        addi.l  #SETUP_GAP,%d5           | its SETUP bytes
        moveq   #0,%d1
ml_cl_byte:
        mvz.b   (%a5,%d1.l),%d4
        move.b  %d4,(%a0,%d0.l)          | PLAYBACK k: the Part,
        move.b  %d4,(%a1,%d0.l)          | its shadow
        tst.l   %d3
        beq     ml_cl_setup
        move.b  %d4,(%a2,%d1.l)          | the lane
        lsl.l   #8,%d4
        move.w  %d4,(%a3,%d1.l*2)        | its value word
ml_cl_setup:
        mvz.b   6(%a5,%d1.l),%d4
        move.b  %d4,(%a0,%d5.l)          | SETUP k: the Part,
        move.b  %d4,(%a1,%d5.l)          | its shadow
        tst.l   %d3
        beq     ml_cl_next
        move.b  %d4,CV_SETUP(%a2,%d1.l)  | the lane
ml_cl_next:
        addq.l  #1,%d0
        addq.l  #1,%d5
        addq.l  #1,%d1
        cmpi.l  #6,%d1
        bne     ml_cl_byte
        movem.l (%sp),%d1/%d4-%d5
        lea     12(%sp),%sp
        rts
| ml_p1byte: d0 = a value, d1 = page 1's slot 0..11 (LFO, AMP), d3 = the track's page 1 in
| the Part -> the Part, the shadow, the lane (+ 6 + slot) and the value word written.
ml_p1byte:
        move.l  %d3,-(%sp)
        add.l   %d1,%d3
        move.b  %d0,(%a0,%d3.l)
        move.b  %d0,(%a1,%d3.l)
        move.b  %d0,CV_LFO(%a2,%d1.l)
        lsl.l   #8,%d0
        move.w  %d0,2*CV_LFO(%a3,%d1.l*2)
        move.l  (%sp)+,%d3
        rts
| ml_p2byte: d0 = a value, d1 = page 2's byte 0..29, d3 = the track's page 2 in the Part ->
| the Part, the shadow and the lane (+ 38 + byte; MULT / TRIG at + 62) written.
ml_p2byte:
        move.l  %d3,-(%sp)
        add.l   %d1,%d3
        move.b  %d0,(%a0,%d3.l)
        move.b  %d0,(%a1,%d3.l)
        move.l  (%sp)+,%d3
        cmpi.l  #24,%d1
        bcc     ml_p2_mt
        move.b  %d0,CV_P2(%a2,%d1.l)
        rts
ml_p2_mt:
        move.b  %d0,CV_MT-24(%a2,%d1.l)
        rts
| ml_p2pairs: a4 = two defaults (a, b), d1 = page 2's first byte -> bytes d1 .. d1 + 5 =
| a b a b a b, as the stock initialiser writes them (`slot & 1` picks the default); d1 += 6.
ml_p2pairs:
        moveq   #3,%d5
ml_pp_lfo:
        mvz.b   (%a4),%d0
        bsr     ml_p2byte
        addq.l  #1,%d1
        mvz.b   1(%a4),%d0
        bsr     ml_p2byte
        addq.l  #1,%d1
        subq.l  #1,%d5
        bne     ml_pp_lfo
        rts
| ml_kindrow: d0 = a row's engine kind -> a5 = its descriptor in ml_rows (the first row
| when none matches). Preserves every other register.
ml_kindrow:
        move.l  %d1,-(%sp)
        moveq   #0,%d1
ml_kr_row:
        lea     ml_rows(%pc),%a5
        movea.l (%a5,%d1.l*4),%a5
        cmp.b   RD_KIND(%a5),%d0
        beq     ml_kr_out
        addq.l  #1,%d1
        cmpi.l  #ML_COUNT,%d1
        bne     ml_kr_row
        lea     ml_rows(%pc),%a5
        movea.l (%a5),%a5
ml_kr_out:
        move.l  (%sp)+,%d1
        rts
| ml_sigrow: a0 = a signature's place -> d0 = the index in ml_rows of the row whose
| signature it holds, else -1; tst.l done (bmi: none). Preserves every other register.
ml_sigrow:
        lea     -8(%sp),%sp
        movem.l %d1/%a1,(%sp)
        moveq   #0,%d0
ml_sr_row:
        lea     ml_rows(%pc),%a1
        movea.l (%a1,%d0.l*4),%a1        | the row's descriptor: its signature at +0
        mvz.b   (%a0),%d1
        cmp.b   (%a1),%d1
        bne     ml_sr_next
        mvz.b   1(%a0),%d1
        cmp.b   1(%a1),%d1
        bne     ml_sr_next
        mvz.b   2(%a0),%d1
        cmp.b   2(%a1),%d1
        beq     ml_sr_out
ml_sr_next:
        addq.l  #1,%d0
        cmpi.l  #ML_COUNT,%d0
        bne     ml_sr_row
        moveq   #-1,%d0
ml_sr_out:
        movem.l (%sp),%d1/%a1
        lea     8(%sp),%sp
        tst.l   %d0
        rts
| fm_unsign: a0 = a signature's place -> cleared when it holds a row's signature (d0 clobbered)
fm_unsign:
        bsr     ml_sigrow
        bmi     fm_us_out
        clr.b   (%a0)
        clr.b   1(%a0)
        clr.b   2(%a0)
fm_us_out:
        rts

| ---- 0x40079816 (jmp, 8 B): the machine window's machine-byte write (FUNC + SRC, YES).
| a1 = the bank blob, d0 = part * 6322, d1 = the track, d2 = the part index, d4 = the
| chosen row, a0 = blob + part * 6322 + track. The row becomes the machine byte to store
| (fm_choose), then po_machwin (poly.s) replays the displaced `addal #0x8eda2,%a0; mvsb
| %a0@,%d3` with its FINE rule and stock stores d4 into the Part and its shadow. Stock
| goes on with d0 (+ d1: the shadow's byte, 0x100a4ef0 + part * 6322 + track), d1, d2
| (the Part's change bit), d3 (the old machine), d4 and a0 / a1: each is what it was, d4
| the machine to store (2.15: the guard's verdict is not left in d0).
fm_main_commit:
        move.l  %d2,-(%sp)
        move.l  %d1,-(%sp)
        move.l  %d0,-(%sp)               | part * 6322: stock's shadow offset
        move.l  %d1,%d2                  | the track
        move.l  %d4,%d1                  | the row
        bsr     ml_guard                 | 2.15: over a limit? (d0 = the verdict)
        bne     fm_mc_refuse
        bsr     fm_choose
        move.l  %d1,%d4                  | the machine to store
        move.l  (%sp)+,%d0
        move.l  (%sp)+,%d1
        move.l  (%sp)+,%d2
        jmp     po_machwin
fm_mc_refuse:
        lea     12(%sp),%sp              | the exit reloads what it uses
        bsr     ml_toast
        jmp     WIN_REFUSE               | nothing written: the stock refusal's exit
        .if     HK_MACHINE_ROWS
| fm_main_commit_hk: the same from the chain's head (ANALOG BD's or OCTA303's commit at
| 0x4007981c, which does not take a CX OSC row): our 0x40079816 detour stands down, so stock's
| `addal #0x8eda2,%a0` there has run. Undone here, as fm_main_commit replays it (po_machwin,
| which rejoins after the head's span when built for the chain).
fm_main_commit_hk:
        suba.l  #MACH_OFF,%a0
        bra     fm_main_commit
        .endif

| ---- 0x4005a616 / 0x4005a850 (jmp, 6 B each): SRC SETUP's two machine-byte writes:
| displaced `movel 0x460d5c30,%d1` (the chosen row), then stock stores d1 at a0 (the
| machine byte) and into the shadow. d2 = the track. The second site follows
| po_machlist's detour (0x4005a848, poly.s), which returns to it. Stock goes on with d0
| (part * 6322; + d2: the shadow's byte), d1 (the machine to store), d2, d3 (the part
| index: the Part's change bit), d4 (the old machine), a0 and a1: each is returned as it
| came but d1 (2.15: the guard's verdict is not left in d0).
| 2.15: a row the guard refuses leaves through SRC_REFUSE with nothing written.
fm_src_commit:
        move.l  SRC_CURSOR,%d1           | displaced
        move.l  %d0,-(%sp)               | part * 6322
        bsr     ml_guard                 | (d0 = the verdict)
        bne     fm_sc_refuse
        move.l  (%sp)+,%d0
        bsr     fm_choose
        jmp     SRC_COMMIT_RET
fm_src_commit2:
        move.l  SRC_CURSOR,%d1           | displaced
        move.l  %d0,-(%sp)
        bsr     ml_guard
        bne     fm_sc_refuse
        move.l  (%sp)+,%d0
        bsr     fm_choose
        jmp     SRC_COMMIT2_RET
fm_sc_refuse:
        addq.l  #4,%sp                   | SRC_REFUSE reloads what it uses
        bsr     ml_toast
        jmp     SRC_REFUSE

| ---- the selection guard (2.15) ----
| ml_guard: d1 = the chosen row, d2 = the track (the current Part) -> d0 = 0 when the
| choice is allowed, else the message that refuses it; tst.l done. A stock row, or the row
| of the machine the track has already, is allowed; a row's machine is refused when the
| Part's other seven audio tracks hold (by their signatures, ml_sigkind):
|   CX OSC: ML_FM_MAX CX OSC tracks already ("CX OSC: 1 MAX"), or more than
|             ML_SY_WITH_FM SY DRUM tracks ("FM+SY DRUM: LIMIT");
|   SY DRUM:  ML_SY_MAX SY DRUM tracks already ("SY DRUM: 2 MAX"), or an CX OSC
|             track and ML_SY_WITH_FM SY DRUM tracks ("FM+SY DRUM: LIMIT").
| The limits are read from ml_limits. Preserves every other register. ml_guard_p: the
| same for a0 = any Part (the paste guards: the Part a stock paste writes into).
        .set    LIM_FM, 0                | ml_limits: the three bytes
        .set    LIM_SY, 1
        .set    LIM_SYFM, 2
ml_guard:
        move.l  %a0,-(%sp)
        bsr     ml_part                  | a0 = the current Part
        bsr     ml_guard_p
        movea.l (%sp)+,%a0
        tst.l   %d0
        rts
ml_guard_p:
        lea     -28(%sp),%sp
        movem.l %d1-%d5/%a0-%a1,(%sp)
        movea.l %a0,%a1                  | a1 = the Part
        move.l  %d1,%d0
        subq.l  #FM_ROW,%d0
        cmpi.l  #ML_COUNT,%d0
        bcc     ml_gd_ok                 | (unsigned) a stock row: always
        lea     ml_rows(%pc),%a0
        movea.l (%a0,%d0.l*4),%a0
        mvz.b   RD_KIND(%a0),%d5         | the machine chosen: 1 CX OSC, 2 SY DRUM
        movea.l %a1,%a0                  | a0 = the Part
        move.l  %d2,%d0
        bsr     ml_sigkind
        cmp.l   %d5,%d0
        beq     ml_gd_ok                 | the track's own machine again: always
        moveq   #0,%d3                   | CX OSC tracks among the other seven
        moveq   #0,%d4                   | SY DRUM tracks among them
        moveq   #0,%d1
ml_gd_track:
        cmp.l   %d2,%d1
        beq     ml_gd_next               | the track being changed
        move.l  %d1,%d0
        bsr     ml_sigkind
        cmpi.l  #1,%d0
        bne     ml_gd_sy1
        addq.l  #1,%d3
ml_gd_sy1:
        cmpi.l  #2,%d0
        bne     ml_gd_next
        addq.l  #1,%d4
ml_gd_next:
        addq.l  #1,%d1
        cmpi.l  #8,%d1
        bne     ml_gd_track
        lea     ml_limits(%pc),%a0
        cmpi.l  #2,%d5
        beq     ml_gd_sy
        mvz.b   LIM_FM(%a0),%d0          | CX OSC chosen
        cmp.l   %d0,%d3
        bcc     ml_gd_fm                 | (unsigned) as many CX OSC tracks as allowed already
        mvz.b   LIM_SYFM(%a0),%d0
        cmp.l   %d0,%d4
        bhi     ml_gd_both               | more SY DRUM tracks than CX OSC allows beside it
        bra     ml_gd_ok
ml_gd_sy:
        mvz.b   LIM_SY(%a0),%d0          | SY DRUM chosen
        cmp.l   %d0,%d4
        bcc     ml_gd_symax              | as many SY DRUM tracks as allowed already
        tst.l   %d3
        beq     ml_gd_ok                 | no CX OSC track
        mvz.b   LIM_SYFM(%a0),%d0
        cmp.l   %d0,%d4
        bcc     ml_gd_both               | as many as CX OSC allows beside it already
ml_gd_ok:
        moveq   #0,%d0
        bra     ml_gd_out
ml_gd_fm:
        lea     ml_msg_fm(%pc),%a0
        bra     ml_gd_msg
ml_gd_symax:
        lea     ml_msg_sy(%pc),%a0
        bra     ml_gd_msg
ml_gd_both:
        lea     ml_msg_both(%pc),%a0
ml_gd_msg:
        move.l  %a0,%d0
ml_gd_out:
        movem.l (%sp),%d1-%d5/%a0-%a1
        lea     28(%sp),%sp
        tst.l   %d0
        rts
| ml_sigkind: a0 = a Part, d0 = a track -> d0 = the machine its signature names: the row's
| engine kind (1 CX OSC, 2 SY DRUM) for FLEX with a row's signature, else 0; tst.l done.
| Preserves every other register.
ml_sigkind:
        lea     -8(%sp),%sp
        movem.l %d1/%a0,(%sp)
        move.l  %d0,%d1
        adda.l  #MACH_OFF,%a0
        mvz.b   (%a0,%d1.l),%d0          | the track's machine byte
        suba.l  #MACH_OFF,%a0
        cmpi.l  #FLEX,%d0
        bne     ml_sk_none
        mulu.w  #30,%d1
        adda.l  %d1,%a0
        adda.l  #SIG_OFF,%a0             | its signature place
        bsr     ml_sigrow
        bmi     ml_sk_none
        lea     ml_rows(%pc),%a0
        movea.l (%a0,%d0.l*4),%a0
        mvz.b   RD_KIND(%a0),%d0
        bra     ml_sk_out
ml_sk_none:
        moveq   #0,%d0
ml_sk_out:
        movem.l (%sp),%d1/%a0
        lea     8(%sp),%sp
        tst.l   %d0
        rts
| ml_toast: d0 = a message -> the firmware's popup shows it for TOAST_TIME (the stock
| routine; d0/d1/a0/a1 clobbered, as by any stock call).
ml_toast:
        pea     (TOAST_TIME).w
        move.l  %d0,-(%sp)
        jsr     TOAST
        addq.l  #8,%sp
        rts

| ---- the paste guards (2.15). Stock's copy / paste and its undo write a track's machine
| byte without either list: the SRC page (FUNC + REC / FUNC + STOP on the SRC page: the
| machine, its slot and its PLAYBACK column), the whole track (FUNC + REC / FUNC + STOP in
| SRC SETUP: the machine, the 30 PLAYBACK bytes with the signature, every page and the
| pattern track) and the Part (the PART window: all of it). Each store is guarded where
| it starts, for a paste and for an undo alike (an undo restores what a paste or a clear
| replaced). A store that would give the Part a row's machine past the limits is refused
| as a choice in the lists is: nothing is written (the pattern track and SY DRUM's lock
| rows included), the clipboard is kept, stock's own "nothing stored" exit is taken, and
| the popup shows the same message. A Part paste is refused whole when the Part pasted
| holds more than the limits (a Part saved by an older build); a Part within them pastes
| as in 2.14. A track that leaves FLEX keeps no signature, and FLEX given to a track that
| was not FLEX does not revive one (ml_became, fm_preview): only a guarded write makes a
| row's machine.
        .set    CLIP_BUF, 0x460c8122     | stock's clipboard: what COPY took (a page, a track, a Part ...)
        .set    UNDO_BUF, 0x460bf218     | stock's undo buffer: what a paste replaced (the same layouts)
        .set    PAGE_STORE_RET, 0x40027ea2 | the SRC page's store (0x40027e4c, page 0), after the three loads
        .set    PAGE_STORE_NONE, 0x40028f2e | ... its "nothing stored" exit (d0 := 0)
        .set    FULL_STORE, 0x4002b654   | the whole track's store (clip, pattern, track)
        .set    TRACK_PASTE_RET, 0x4002b9a8 | its paste, after the store
        .set    TRACK_UNDO_RET, 0x4002b96c | its undo, after the store
        .set    TRACK_UNDO_NONE, 0x4002b980 | ... the undo's "nothing restored" exit (d0 := 0)
        .set    PART_STORE, 0x40029a4c   | the Part's store (clip, part)
        .set    PART_PASTE_RET, 0x40029b94 | its paste, after the store
        .set    PART_UNDO_RET, 0x40029b5e | its undo, after the store
        .set    PART_UNDO_NONE, 0x40029b70 | ... the undo's "nothing restored" exit (d0 := 0)
        .set    TS_MACH, 2334            | the whole track's clip: the machine byte ...
        .set    TS_SIG, 2335 + 18        | ... its 30 PLAYBACK bytes at 2335: the signature's place
        .set    PATTERN_SIZE, 36568      | a pattern in the bank blob ...
        .set    PAT_PART, 36438 + 1      | ... and its Part (a signed byte)
        .set    PREVIEW_SAVE, 0x46105424 | the FLEX preview's saved machine
        .set    PREVIEW_RET, 0x40096d2e
| 0x40027e98 (jmp, 10 B): the SRC page's store (d4 = the Part, d5 = the track, a2 = the
| clipboard for a paste, 0x40028fd4, or the undo buffer for an undo, 0x40028f94): displaced `moveb %a2@(19),%d3; mvsb %d3,%d6; moveb %a2@(18),%d7` (the machine and
| its slot). FLEX pasted over a track whose signature place holds a row's signature makes
| that machine (the signature is not written by this store): guarded.
fm_page_store:
        move.b  19(%a2),%d3              | displaced: the machine pasted
        mvs.b   %d3,%d6                  | displaced
        move.b  18(%a2),%d7              | displaced: its slot
        cmpi.l  #FLEX,%d6
        bne     fm_ps_go                 | another machine: no row's
        lea     -16(%sp),%sp
        movem.l %d1-%d2/%a0-%a1,(%sp)
        move.l  %d4,%d0
        bsr     ml_partn                 | a0 = the Part pasted into
        move.l  %d5,%d2                  | the track
        bsr     ml_rowat                 | d1 = the row its signature names
        bmi     fm_ps_ok
        bsr     ml_guard_p
        bne     fm_ps_refuse
fm_ps_ok:
        movem.l (%sp),%d1-%d2/%a0-%a1
        lea     16(%sp),%sp
fm_ps_go:
        jmp     PAGE_STORE_RET
fm_ps_refuse:
        movem.l (%sp),%d1-%d2/%a0-%a1
        lea     16(%sp),%sp
        bsr     ml_toast
        jmp     PAGE_STORE_NONE
| 0x4002b962 / 0x4002b99e (jmp, 10 B each): the whole track's undo (0x4002b8xx, which saved
| d2 / d3) and its paste (0x4002b988) call the store: displaced `pea UNDO_BUF / CLIP_BUF;
| jsr %pc@(FULL_STORE)` (replayed by its address); the store's other two arguments are on
| the stack (0(sp) the pattern, 4(sp) the track). A refusal leaves through the function's
| own "nothing" answer (d0 = 0).
fm_track_undo:
        lea     UNDO_BUF,%a1
        bsr     ml_trackchk
        bne     fm_tu_refuse
        pea     (UNDO_BUF).l             | displaced
        jsr     FULL_STORE               | displaced
        jmp     TRACK_UNDO_RET
fm_tu_refuse:
        bsr     ml_toast
        addq.l  #8,%sp                   | the store's two arguments
        jmp     TRACK_UNDO_NONE
fm_track_paste:
        lea     CLIP_BUF,%a1
        bsr     ml_trackchk
        bne     fm_tp_refuse
        pea     (CLIP_BUF).l             | displaced
        jsr     FULL_STORE               | displaced
        jmp     TRACK_PASTE_RET
fm_tp_refuse:
        bsr     ml_toast
        addq.l  #8,%sp                   | the store's two arguments
        moveq   #0,%d0                   | nothing pasted (the paste's own answer when the clipboard holds no track)
        rts
| ml_trackchk: a1 = a whole track's clip, 4(sp) = the pattern, 8(sp) = the track (the
| caller's store arguments) -> d0 = 0 when storing it is allowed, else the message; tst.l
| done. Clobbers d0 only.
ml_trackchk:
        lea     -16(%sp),%sp
        movem.l %d1-%d2/%a0/%a2,(%sp)
        moveq   #0,%d0
        mvz.b   TS_MACH(%a1),%d1
        cmpi.l  #FLEX,%d1
        bne     ml_tc_out                | another machine: no row's
        lea     TS_SIG(%a1),%a0
        bsr     ml_sigrow
        bmi     ml_tc_ok                 | FLEX with no signature: a sample track
        addq.l  #FM_ROW,%d0
        movea.l %d0,%a2                  | the row pasted
        move.l  20(%sp),%d0              | the pattern
        move.l  #PATTERN_SIZE,%d1
        muls.l  %d1,%d0
        movea.l PART_PTR,%a0
        adda.l  %d0,%a0
        adda.l  #PAT_PART,%a0
        mvs.b   (%a0),%d0                | its Part: the one stock's store writes
        move.l  #6322,%d1
        muls.l  %d1,%d0
        movea.l PART_PTR,%a0
        adda.l  %d0,%a0
        move.l  %a2,%d1
        move.l  24(%sp),%d2              | the track
        bsr     ml_guard_p
        bra     ml_tc_out
ml_tc_ok:
        moveq   #0,%d0
ml_tc_out:
        movem.l (%sp),%d1-%d2/%a0/%a2
        lea     16(%sp),%sp
        tst.l   %d0
        rts
| 0x40029b54 / 0x40029b8a (jmp, 10 B each): the Part's undo and its paste call the store:
| displaced `pea UNDO_BUF / CLIP_BUF; jsr %pc@(PART_STORE)` (replayed by its address); the
| Part's index is on the stack. The buffer holds a whole Part from its +0.
fm_part_undo:
        lea     UNDO_BUF-PART_OFF,%a0
        bsr     ml_part_over
        bne     fm_pu_refuse
        pea     (UNDO_BUF).l             | displaced
        jsr     PART_STORE               | displaced
        jmp     PART_UNDO_RET
fm_pu_refuse:
        bsr     ml_toast
        addq.l  #4,%sp                   | the store's other argument
        jmp     PART_UNDO_NONE
fm_part_paste:
        lea     CLIP_BUF-PART_OFF,%a0
        bsr     ml_part_over
        bne     fm_pp_refuse
        pea     (CLIP_BUF).l             | displaced
        jsr     PART_STORE               | displaced
        jmp     PART_PASTE_RET
fm_pp_refuse:
        bsr     ml_toast
        addq.l  #4,%sp                   | the store's other argument
        moveq   #0,%d0                   | nothing pasted (the paste's own answer)
        rts
| ml_part_over: a0 = a Part -> d0 = 0 when its eight tracks are within the limits, else
| the message (as ml_guard's); tst.l done. Preserves every other register.
ml_part_over:
        lea     -20(%sp),%sp
        movem.l %d1/%d3-%d4/%a0-%a1,(%sp)
        moveq   #0,%d3                   | CX OSC tracks
        moveq   #0,%d4                   | SY DRUM tracks
        moveq   #0,%d1
ml_po_track:
        move.l  %d1,%d0
        bsr     ml_sigkind
        cmpi.l  #1,%d0
        bne     ml_po_sy
        addq.l  #1,%d3
ml_po_sy:
        cmpi.l  #2,%d0
        bne     ml_po_next
        addq.l  #1,%d4
ml_po_next:
        addq.l  #1,%d1
        cmpi.l  #8,%d1
        bne     ml_po_track
        lea     ml_limits(%pc),%a1
        lea     ml_msg_fm(%pc),%a0
        mvz.b   LIM_FM(%a1),%d0
        cmp.l   %d0,%d3
        bhi     ml_po_msg                | more CX OSC tracks than allowed
        lea     ml_msg_sy(%pc),%a0
        mvz.b   LIM_SY(%a1),%d0
        cmp.l   %d0,%d4
        bhi     ml_po_msg                | more SY DRUM tracks than allowed
        lea     ml_msg_both(%pc),%a0
        tst.l   %d3
        beq     ml_po_ok
        mvz.b   LIM_SYFM(%a1),%d0
        cmp.l   %d0,%d4
        bhi     ml_po_msg                | more SY DRUM tracks than CX OSC allows beside it
ml_po_ok:
        suba.l  %a0,%a0
ml_po_msg:
        move.l  %a0,%d0
        movem.l (%sp),%d1/%d3-%d4/%a0-%a1
        lea     20(%sp),%sp
        tst.l   %d0
        rts
| 0x40096d22 (jmp, 12 B): the sample preview of the FLEX list (0x40096c54: d4 = the track
| of the current Part, a0 = its machine byte) makes the track FLEX while it plays and puts
| the machine back after: displaced `mvsb %a0@,%d3; movel %d3,PREVIEW_SAVE; moveb #1,%a0@`.
| A track that is not FLEX loses the signature it kept, so the preview plays the sample.
fm_preview:
        mvs.b   (%a0),%d3                | displaced: the machine before the preview
        move.l  %d3,PREVIEW_SAVE         | displaced
        cmpi.l  #FLEX,%d3
        beq     fm_pv_flex               | FLEX already: the track plays what it played
        move.l  %d2,-(%sp)
        move.l  %d4,%d2
        bsr     ml_unsign_t
        move.l  (%sp)+,%d2
fm_pv_flex:
        move.b  #FLEX,(%a0)              | displaced
        jmp     PREVIEW_RET
| ml_unsign_t: d2 = a track of the current Part -> a row's signature in its signature
| place cleared, in the Part and its shadow. Preserves every register.
ml_unsign_t:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        bsr     ml_part
        move.l  %a0,%d1
        sub.l   PART_PTR,%d1             | part * 6322
        move.l  %d2,%d0
        mulu.w  #30,%d0
        addi.l  #SIG_OFF,%d0
        add.l   %d0,%d1
        adda.l  %d0,%a0                  | the Part's signature place
        bsr     fm_unsign
        lea     PART_SHADOW,%a0
        adda.l  %d1,%a0                  | ... its shadow
        bsr     fm_unsign
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        rts
| ml_partn: d0 = a Part's index -> a0 = the Part (the bank blob + index * 6322). Clobbers d0.
ml_partn:
        move.l  %d1,-(%sp)
        move.l  #6322,%d1
        muls.l  %d1,%d0
        movea.l PART_PTR,%a0
        adda.l  %d0,%a0
        move.l  (%sp)+,%d1
        rts
| ml_rowat: a0 = a Part, d2 = a track -> d1 = the row (FM_ROW + its index in ml_rows) whose
| signature the track's signature place holds, whatever its machine byte, else -1; tst.l
| done. Clobbers d0.
ml_rowat:
        move.l  %a0,-(%sp)
        move.l  %d2,%d1
        mulu.w  #30,%d1
        adda.l  %d1,%a0
        adda.l  #SIG_OFF,%a0
        bsr     ml_sigrow
        movea.l (%sp)+,%a0
        bmi     ml_ra_none
        addq.l  #FM_ROW,%d0
ml_ra_none:
        move.l  %d0,%d1
        rts

| ---- fm_type: d0 = a machine read through a0 = a pointer to it -> d0 = 5 + the row's
| index when a0 is the current Part's machine byte of a track whose row of ml_rows is
| chosen (FLEX, signed), else d0 unchanged. Preserves every other register
| (registration.c's fm_type).
fm_type:
        cmpi.l  #FLEX,%d0
        bne     fm_ty_rts
        lea     -16(%sp),%sp
        movem.l %d1-%d2/%a0-%a1,(%sp)
        movea.l PART_PTR,%a1
        mvz.b   PART_IDX,%d1
        move.l  #6322,%d2
        muls.l  %d2,%d1
        adda.l  %d1,%a1                  | the Part
        move.l  %a0,%d2
        sub.l   %a1,%d2
        subi.l  #MACH_OFF,%d2            | the track, if a0 is one of its machine bytes
        moveq   #8,%d1
        cmp.l   %d1,%d2
        bhs     fm_ty_out                | (unsigned) another byte: unchanged
        mulu.w  #30,%d2
        movea.l %a1,%a0
        adda.l  %d2,%a0
        adda.l  #SIG_OFF,%a0             | the track's signature place (FLEX: the caller's byte)
        bsr     ml_sigrow
        bmi     fm_ty_flex               | unsigned: FLEX
        addq.l  #FM_ROW,%d0              | its row
        bra     fm_ty_out
fm_ty_flex:
        moveq   #FLEX,%d0
fm_ty_out:
        movem.l (%sp),%d1-%d2/%a0-%a1
        lea     16(%sp),%sp
fm_ty_rts:
        rts

| ---- 0x400334d8 (jmp, 6 B): the machine-name formatter name(row): rows 5.. -> their
| names; any other row replays the displaced `movel %d2,%sp@-; movel %sp@(8),%d1`.
fm_machine_name:
        move.l  4(%sp),%d0
        subq.l  #FM_ROW,%d0
        cmpi.l  #ML_COUNT,%d0
        bcs     fm_mn_row                | (unsigned) one of ours
        move.l  %d2,-(%sp)               | displaced
        move.l  8(%sp),%d1               | displaced
        jmp     NAME_RET
fm_mn_row:
        lea     ml_rows(%pc),%a0
        movea.l (%a0,%d0.l*4),%a0
        move.l  RD_NAME(%a0),%d0
        rts

| ---- 0x4003d718 (jmp, 6 B): a track's machine name, d0 = its machine (0..4 checked),
| a0 = its machine byte; displaced `lea 0x400a78c8,%a0`, then d1 := the name (the
| instruction after, `movel %a0@(0,%d0:l:4),%d1`, is done here: rejoins after it).
fm_name_a:
        bsr     fm_type                  | FLEX + signed -> its row
        lea     NAMES,%a0                | displaced
        cmpi.l  #FM_ROW,%d0
        bge     fm_na_row
        move.l  (%a0,%d0.l*4),%d1
        jmp     NAME_A_RET
fm_na_row:
        lea     ml_rows-4*FM_ROW(%pc),%a0
        movea.l (%a0,%d0.l*4),%a0
        move.l  RD_NAME(%a0),%d1
        lea     NAMES,%a0
        jmp     NAME_A_RET

| ---- 0x4003c980 (jmp, 6 B): SRC SETUP's row highlight: displaced `mvsb %a0@,%d0; lea
| %sp@(24),%sp` (a0 = the track's machine byte); a signed track's row is its row.
fm_setup_row:
        mvs.b   (%a0),%d0
        lea     24(%sp),%sp
        bsr     fm_type
        jmp     SETUP_ROW_RET

| ---- 0x400786c8 (jmp, 6 B): the machine window's row highlight: displaced `mvsb
| %a0@,%d0; cmpl %d0,%d2; bnes 0x400786fc` (d2 = the visible row drawn; 2.11: the
| window scrolls, so the list row is d2 + its top, ml_draw_name).
fm_chooser_row:
        mvs.b   (%a0),%d0
        bsr     fm_type
        move.l  WIN_LIST,%d1             | the list's top row (d1 is reloaded at 0x400786fc)
        add.l   %d2,%d1
        cmp.l   %d0,%d1
        bne     fm_cr_miss
        jmp     CHOOSER_HIT
fm_cr_miss:
        jmp     CHOOSER_MISS

| ---- 0x400585dc (jmp, 10 B): SRC SETUP opens on the track's row: displaced `moveb
| %a0@,%d3; mvsb %d3,%d4; pea 0x400bb704`; d4 indexes the PLAYBACK descriptor table
| (slots 5..: the rows' pages, fm_tick), d3 is the row the window starts on.
fm_setup_open:
        move.b  (%a0),%d3
        move.l  %d0,-(%sp)
        mvs.b   %d3,%d0
        bsr     fm_type
        move.l  %d0,%d3
        move.l  (%sp)+,%d0
        mvs.b   %d3,%d4
        pea     (0x400bb704).l           | displaced
        jmp     SETUP_OPEN_RET

| ---- 0x40078886 (jmp, 10 B): the machine window opens on the track's row: displaced
| `mvsb %a0@,%d0; movel %d0,%sp@-; pea 0x460e7386`.
fm_chooser_open:
        mvs.b   (%a0),%d0
        bsr     fm_type
        move.l  %d0,-(%sp)
        pea     (0x460e7386).l           | displaced
        jmp     CHOOSER_OPEN_RET

| ---- 0x4003a52e / 0x4003cd98 (jmp, 8 B each): SRC SETUP's editor and drawer address the
| row's Part bytes at row * 6: displaced `movel %dN,%d0; lsll #3,%d0; addl %dN,%dN; subl
| %dN,%d0` (d2 / d6, the row; d0 / d7 := row * 6). Rows 5.. address FLEX's.
fm_setup_edit6:
        cmpi.l  #FM_ROW,%d2
        blt     fm_e6
        moveq   #FLEX,%d2
fm_e6:
        move.l  %d2,%d0
        lsl.l   #3,%d0
        add.l   %d2,%d2
        sub.l   %d2,%d0
        jmp     EDIT6_RET
fm_setup_draw6:
        cmpi.l  #FM_ROW,%d6
        blt     fm_d6
        moveq   #FLEX,%d6
fm_d6:
        move.l  %d6,%d7
        lsl.l   #3,%d7
        add.l   %d6,%d6
        sub.l   %d6,%d7
        jmp     DRAW6_RET

| ---- 0x4005221e (jmp, 10 B): the UI tick: displaced `jsr 0x4005213c; jsr 0x4007e940`,
| replayed; then SRC SETUP's name table is filled from the stock one and the rows' names,
| and the PLAYBACK descriptor table's spare slots 5.. get the rows' pages (CX OSC:
| page.s, built on first use; SY DRUM: its unit's), so the SRC SETUP window has a page
| for each row. (Slots 5 and 6 are spares holding NEIGHBOR's descriptor in stock; slot 7
| is the table's end: two rows at most write here.)
fm_tick:
        jsr     TICK_A                   | displaced
        jsr     TICK_B                   | displaced
        lea     NAMES,%a0
        lea     fm_src_names(%pc),%a1
        moveq   #5,%d0
fm_tk_copy:
        move.l  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne     fm_tk_copy
        move.l  %a2,-(%sp)
        move.l  %d2,-(%sp)
        moveq   #0,%d2
fm_tk_row:
        lea     ml_rows(%pc),%a2
        movea.l (%a2,%d2.l*4),%a2        | the row's descriptor
        move.l  RD_NAME(%a2),%d0         | its name
        lea     fm_src_names+4*FM_ROW(%pc),%a0
        move.l  %d0,(%a0,%d2.l*4)
        movea.l RD_DESC(%a2),%a0
        jsr     (%a0)                    | d0 = its page (d0/d1/a0/a1 clobbered)
        lea     PB_TABLE+4*FM_ROW,%a0
        move.l  %d0,(%a0,%d2.l*4)
        addq.l  #1,%d2
        cmpi.l  #ML_COUNT,%d2
        bne     fm_tk_row
        move.l  (%sp)+,%d2
        movea.l (%sp)+,%a2
        jmp     TICK_RET
        .if     HK_MACHINE_ROWS
| fm_publish: fm_tick's PLAYBACK records from the chain's head's tick hook, which owns the
| site and fills its own SRC SETUP name table (fm_name is a word of it). d0/d1/a0/a1
| clobbered, as by the stock calls around it.
fm_publish:
        move.l  %a2,-(%sp)
        move.l  %d2,-(%sp)
        moveq   #0,%d2
fm_pb_row:
        lea     ml_rows(%pc),%a2
        movea.l (%a2,%d2.l*4),%a2
        movea.l RD_DESC(%a2),%a0
        jsr     (%a0)                    | d0 = its page
        lea     PB_TABLE+4*FM_ROW,%a0
        move.l  %d0,(%a0,%d2.l*4)
        addq.l  #1,%d2
        cmpi.l  #ML_COUNT,%d2
        bne     fm_pb_row
        move.l  (%sp)+,%d2
        movea.l (%sp)+,%a2
        rts
        .endif

| ---- the six row-count and row-bound sites (2.11): the stock list code was written for
| five machines; 2.10 poked its constants to six rows. Each detour does what the stock
| instruction did with 5 + ML_COUNT rows (the last row ML_LAST), and rejoins.
| 0x40079248 (jmp, 8 B): the machine window's list init, `pea 5; pea 6` (rows, visible).
ml_win_count:
        pea     (5+ML_COUNT).w           | the rows
        pea     6.w                      | the rows visible (stock's)
        jmp     WIN_COUNT_RET
| 0x400585fa (jmp, 8 B): SRC SETUP's list init, stock `pea 5; pea 5`.
| Visible 6 so the sixth row (CX OSC) keeps STATIC..PICKUP on screen (same as
| the machine window); stock's five-row viewport scrolled STATIC away.
ml_src_count:
        pea     (5+ML_COUNT).w
        pea     6.w
        jmp     SRC_COUNT_RET
| 0x4003c950 (jmp, 6 B): SRC SETUP's name lookup, `moveq #4,%d1; cmpl %d2,%d1; bcss
| 0x4003c95a` (d2 = the row: past the last row, the default string).
ml_name_bound:
        moveq   #ML_LAST,%d1
        cmp.l   %d2,%d1
        bcs     ml_nb_out
        jmp     NAME_BOUND_IN
ml_nb_out:
        jmp     NAME_BOUND_OUT
| 0x40078678 (jmp, 12 B): the machine window's row drawer, `moveq #4,%d0; cmpl %d2,%d0;
| blts 0x400786a2; movel %d2,%sp@-; moveal %d3,%a0; jsr %a0@` (d2 = the visible row, d3 =
| the name formatter). It drew name(d2) for d2 = 0 .. 5 with no scroll offset: a seventh
| row was never drawn and the cursor box left its name (found by a study of the list code, 8 Oct 2026). 2.11:
| name(d2 + the list's top), up to the last row -- the window scrolls as SRC SETUP's does,
| six rows visible. With six rows or fewer the top stays 0: stock's drawing.
ml_draw_bound:
        move.l  WIN_LIST,%d0             | the top row
        add.l   %d2,%d0
        cmpi.l  #ML_LAST,%d0
        bgt     ml_db_out
        move.l  %d0,-(%sp)               | (replaces the pushed d2: the same stack)
        movea.l %d3,%a0
        jsr     (%a0)
        jmp     DRAW_BOUND_IN
ml_db_out:
        jmp     DRAW_BOUND_OUT
| 0x400786ce (jmp, 6 B): the machine window's highlight, `moveq #4,%d0; cmpl %d2,%d0;
| blts 0x400786fc`.
ml_hi_bound:
        moveq   #ML_LAST,%d0
        cmp.l   %d2,%d0
        blt     ml_hb_out
        jmp     HI_BOUND_IN
ml_hb_out:
        jmp     CHOOSER_MISS
| The machine window's row clamp after a list move (five sites, 8 B each: `moveq #5,%d1;
| cmpl %d0,%d1; bges +2; moveq #5,%d0` -- the absolute row 0x460e738e kept to 0..5, the
| six rows the window shows, then handed to the list's row setter 0x4007edb0): a row past
| the sixth was put back on the sixth, so it could not be selected or committed (located by the
| development line's machine-list build, 8 Oct 2026). 2.11: kept to 0 .. the last row.
        .macro  ML_CLAMP n, back
ml_clamp\n:
        moveq   #ML_LAST,%d1
        cmp.l   %d0,%d1
        bge     1f
        moveq   #ML_LAST,%d0
1:      jmp     \back
        .endm
        ML_CLAMP 1, 0x40078c2a
        ML_CLAMP 2, 0x40078cb8
        ML_CLAMP 3, 0x40078d36
        ML_CLAMP 4, 0x40078df6
        ML_CLAMP 5, 0x40078e84
| 0x40079904 (jmp, 8 B): the machine window's cursor, `moveq #4,%d3; cmpl %d4,%d3;
| bgew 0x400797cc` (d4 = the cursor's row).
ml_cur_bound:
        moveq   #ML_LAST,%d3
        cmp.l   %d4,%d3
        blt     ml_cb_out
        jmp     CUR_BOUND_IN
ml_cb_out:
        jmp     CUR_BOUND_OUT

| ---- 0x40002318 (jmp, 8 B): the Part validator (4(sp) = the Part's +0), entered before
| its prologue. The stock validator clamps every column's PLAYBACK bytes into its
| descriptor's ranges -- FLEX's PTCH into 4..124, where CX OSC's PTCH is 0..127
| (-64..+63 semitones) -- and the SETUP bytes into theirs (SY DRUM's LSPD is 0..127 in
| FLEX's LOOP byte). For each track signed with a row of ml_rows the twelve FLEX bytes
| are swapped for the stock FLEX defaults (read from the descriptor), the stock
| validator runs, and the row's bytes are put back. d0 = the stock result.
fm_validate:
        lea     -116(%sp),%sp            | 96 B: 8 tracks x 12 saved bytes; 20 B: d2-d4/a2-a3
        movem.l %d2-%d4/%a2-%a3,96(%sp)
        movea.l 120(%sp),%a2
        suba.l  #PART_OFF,%a2            | blob-relative: + MACH_OFF / SIG_OFF / FLEX_PB
        moveq   #0,%d3                   | the signed tracks
        moveq   #0,%d2
fm_vd_save:
        movea.l %a2,%a0
        adda.l  #MACH_OFF,%a0
        mvz.b   (%a0,%d2.l),%d0          | the track's machine
        subq.l  #FLEX,%d0
        bne     fm_vd_snext              | not FLEX
        move.l  %d2,%d0
        mulu.w  #30,%d0
        movea.l %a2,%a0
        adda.l  %d0,%a0
        adda.l  #SIG_OFF,%a0
        bsr     ml_sigrow                | signed with one of the rows?
        bmi     fm_vd_snext
        bset    %d2,%d3
        bsr     fm_vd_ptrs               | a0 = its FLEX bytes, a1 = its save area, a3 = the defaults
        moveq   #6,%d4
fm_vd_s1:
        move.b  (%a0),(%a1)
        move.b  SETUP_GAP(%a0),6(%a1)
        move.b  (%a3),(%a0)
        move.b  6(%a3),SETUP_GAP(%a0)
        addq.l  #1,%a0
        addq.l  #1,%a1
        addq.l  #1,%a3
        subq.l  #1,%d4
        bne     fm_vd_s1
fm_vd_snext:
        addq.l  #1,%d2
        moveq   #8,%d0
        cmp.l   %d0,%d2
        bne     fm_vd_save
        move.l  120(%sp),-(%sp)
        bsr     fm_stock_validate
        addq.l  #4,%sp
        moveq   #0,%d2
fm_vd_rest:
        btst    %d2,%d3
        beq     fm_vd_rnext
        move.l  %d0,-(%sp)
        bsr     fm_vd_ptrs4              | (the stack is 4 deeper here)
        move.l  (%sp)+,%d0
        moveq   #6,%d4
fm_vd_r1:
        move.b  (%a1),(%a0)
        move.b  6(%a1),SETUP_GAP(%a0)
        addq.l  #1,%a0
        addq.l  #1,%a1
        subq.l  #1,%d4
        bne     fm_vd_r1
fm_vd_rnext:
        addq.l  #1,%d2
        moveq   #8,%d4
        cmp.l   %d4,%d2
        bne     fm_vd_rest
        movem.l 96(%sp),%d2-%d4/%a2-%a3
        lea     116(%sp),%sp
        rts
| fm_vd_ptrs: d2 = the track -> a0 = blob-relative Part a2 + FLEX_PB + 30 * track, a1 =
| the caller's save area + 12 * track, a3 = the stock FLEX defaults (d0 clobbered).
fm_vd_ptrs:
        lea     4(%sp),%a1               | the caller's frame: its save area at its 0(sp)
        bra     fm_vd_p
fm_vd_ptrs4:
        lea     8(%sp),%a1
fm_vd_p:
        move.l  %d2,%d0
        mulu.w  #12,%d0
        adda.l  %d0,%a1
        move.l  %d2,%d0
        mulu.w  #30,%d0
        movea.l %a2,%a0
        adda.l  %d0,%a0
        adda.l  #FLEX_PB,%a0
        lea     FLEX_DEF,%a3
        rts
fm_stock_validate:
        lea     -96(%sp),%sp             | displaced
        movem.l %d2-%d7/%a2-%fp,(%sp)    | displaced
        jmp     VALIDATE_BODY

| the guard's limits (machine_limits.inc), as bytes ml_guard reads: CX OSC, SY DRUM, SY
| DRUM beside CX OSC; and its three messages, the numbers printed from the same limits.
| The popup shows a short line only: 17 characters were measured on screen, 21 were not
| drawn at all (the stock routine draws nothing for a line wider than its box).
ml_limits:
        .byte   ML_FM_MAX, ML_SY_MAX, ML_SY_WITH_FM, 0
ml_msg_fm:
        .ascii  "CX OSC: "
        .byte   '0' + ML_FM_MAX
        .asciz  " MAX"
ml_msg_sy:
        .ascii  "SY DRUM: "
        .byte   '0' + ML_SY_MAX
        .asciz  " MAX"
ml_msg_both:
        .asciz  "FM+SY DRUM: LIMIT"
        .balign 2
fm_defaults:
        .byte   64, 25, 32, 1, 0, 0    | PLAYBACK: PTCH 0, RATO ~1 (free 0.25..4 raw 25), INDX 32, FOLD 1, SYMM 0, FDBK 0
        .byte   0, 0, 0, 0, 0, 0         | SETUP: LOOP SLIC LEN RATE TSTR TSNS all 0 (OFF)
fm_name:
        .asciz  "CX OSC"
        .balign 4
| CX OSC's row descriptor (the layout above ml_rows)
fm_row:
        .byte   'C', 'X', 1, 1           | the signature "CX", 1; engine kind 1
        .long   fm_name
        .long   fm_defaults
        .long   fm_descriptor            | page.s (DRAM Linked, or cave at 0x400d24d0 when PLACE=CAVE)
        .byte   0, 0, 0, 0               | flags: its SETUP bytes are FLEX's (kept when it is left, as 2.10)
| THE ROWS after the stock five, in list order (2.11): CX OSC, then each machine module
| on this engine the remix carries -- SY DRUM's descriptor is its own unit's sd_row.
ml_rows:
        .long   fm_row
        .if     HAVE_SYDRUM
        .long   sd_row
        .endif
| SRC SETUP's name table (the lea at 0x4003c928 points here): the stock five, copied
| by fm_tick, and the rows' names.
fm_src_names:
        .fill   5+ML_COUNT, 4, 0
