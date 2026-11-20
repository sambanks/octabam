| seq.s -- SEQ: TRACK + PAGE opens a standalone Euclid page.
|
| With any track key held, PAGE toggles this window instead of stock's
| pattern-page / SCALE path. FUNC + PAGE (SCALE SETUP) stays stock: it
| rides the FUNC layer, not this opener.
|
| Window: "SEQ" top-left, 1/2 or 2/2 top-right. LEN BR (pattern length).
| LEFT/RIGHT switch knob pages; the rhythm grid is identical on both.
| Stock
| SETUP-style 3x2 dotted grid right-aligned: A=PULSE B=ROT C=LANE /
| D=DEST E=DEPTH; F empty. LANE = TRIG|PLOCK (grid + A/B follow).
| DEST cell = PAGE + PARAM (no PMTR caption). Per-DEST plock PULSE/ROT
| in ef_plk_mem (like DEPTH). YES: TRIG->mask0; PLOCK->DEST locks;
| plock-only -> trigless-lock mask +0x10; PLCK miss clears this DEST
| (no PTCH carry onto bare note trigs - regenerating from PLCK overwrites
| TRIG-baked locks for that DEST).
| Pattern: 4×16 hollow/filled squares at the bottom (all ≤64
| steps; last row = n mod 16). Do NOT bind PAGE / arrows / PROJ /
| PART / AED / ARR in EF_KEYS (a 0 swallows; a -1 still writes
| aux/sub-map 0 and can break DOWN / step-bank PAGE). Bare PAGE never
| closes Euclid (stock step banks while open); only TRACK+PAGE toggles
| and NO closes. ARE YOU SURE? soft-hides the SEQ window (WDESTROY)
| but KEEPS EF_LAYER so ef_ask still locks knobs; answer restores.
| ef_cl_poll must not recreate SEQ while ef_ask (dialog behind).
| User/orphan close LPOPs. LEVEL encoder dead; no cursor invert.
| CUE: press = stock hold; release without a TRACK chord = free
| random k-subset. TRACK keys forward to stock (double-tap QUICK
| ASSIGN, FUNC+TRACK mute, TRACK+PLAY/STOP/BANK) then SEQ retarget;
| CUE+TRACK = stock cue-a-track.
|
| DEST = LFO SETUP PMTR targets that Euclid can drive:
|   0..29 page-1 lock flats (skip AMP XVOL=17). Labels PAGE+PARAM.
|   30..34 on CX OSC: SRC CAR/MOD/SYMM/FDBK/PWM (same as LFO). These are
|   PLAYBACK SETUP knobs - not stock p-lock flats. YES stores per-step
|   values in ef_cx_bank / ef_cx_bits (DRAM); CX OSC applies them to SETUP
|   each frame. Slots stack: a later FOLD/CAR fill does not erase PWM.
|   DEC is not a dest (LFO skips it too).
| DEPTH (0..127): lock uniform in [Part-DEPTH .. Part+DEPTH] (clamped).
| DEST=AMP VOL is unipolar below Part VOL (never louder than AMP). DEST=PTCH
| in-scale. Editing PULSE leaves free mode. Write-only: open/track switch
| load bank Euclid params only - never seed from live sample trigs. PLOCK
| PULSE 0 YES clears this DEST (same helper as DEPTH 0) and drops orphan
| TL (stack-safe). FUNC+BANK while open: LISTPOP CLEAR DEST / CLEAR ALL
| DEST / CLEAR ALL+TRIGS (keymap SymbolRef; runs on list YES immediately,
| resets knobs / recipes; SEQ stays under the list). After fill / clear,
| LOCK_COLL rebuilds the step-has-plock LED bitmap so emptied note
| trigs stop blinking yellow and emptied trigless leave the row.
|
| Params: TRIG PULSE/ROT/DEST/DEPTH/free mask per track (ef_bank). DEPTH
| and PLOCK PULSE/ROT/free/mask per track × DEST (ef_dep_mem / ef_plk_mem);
| LANE per track (ef_lane_mem). All persist in euclid.work. D/E always
| live; C switches which rhythm A/B + grid edit. Selecting a track while
| open retargets YES and loads its slot. Multi-target YES writes each
| target's own stored params.
|
| YES: TRIG mask 0; LANE=TRIG -> DEST/DEPTH locks on those trigs and
| sync plock recipe; LANE=PLOCK -> independent trigless stack.
| Battery mirror covers
| masks 0..2 + DEST lock bytes; dirty + 0x40027e00.
| MIDI mode uses the same TRIG/PLOCK lane switch. TRIG writes the MIDI note
| mask plus selected locks on hits; PLOCK writes the independent selected
| lock rhythm without note trigs. MIDI flats 0..29 use native page-1 order.

        .set    HELD,      0x460fab40   | held track keys, bit t
        .set    MIDI_MODE, 0x80000012   | nonzero selects MIDI sequencer records
        .set    CUR_TRACK, 0x80000000   | UI-selected track 0..7
        .set    UI_TRACK,  0x100b14cc   | setup mirror of CUR_TRACK
        .set    SEL_TRACK, 0x40083bf8   | (track 0..7) CUR/UI + sequencer view
        .set    TRK_STOCK, 0x40040250   | base TRACK press/release (QA/mute/…)
        .set    CUE_TRK,   0x40083dc4   | CUE overlay TRACK → cue-a-track
        .set    CUE_HELD,  0x460d168c   | stock CUE modifier byte (press=1)
        .set    MUTE_CUE,  0x80000008   | mute bit8+t / cue bit16+t
        .set    UI_WINDOW, 0x460d175c   | current top window handle
        .set    SLOT_B,    28           | per-track: 5 longs + 8-byte mask
        .set    UI_PTN,    0x100b14d0
        .set    DBPTR,     0x46c82456
        .set    MIRROR,    0x1001614e
        .set    DIRTY_G,   0x100f8598
        .set    DIRTY_OFF, 0x9b332
        .set    NOTIFY,    0x40027e00
        .set    LOCK_COLL, 0x400339d8   | rebuild step-has-plock LED bitmaps
        | CLEAR TRACK TRIGS undo: bit t in CLR_UNDO (set by 0x40029560).
        | Clipboard kind CLIP_KIND == 0xa is the matching undo tag
        | (0x40029f30 restore path). Either left armed -> next clear only
        | toasts UNDO TRACK TRIGS and leaves trigs.
        .set    CLR_UNDO,  0x1001614c
        .set    CLIP_KIND, 0x460c80f0
        .set    CLIP_KEY,  0x460c80f4
        .set    KIND_CTRG, 10           | CLEAR TRACK TRIGS
        .set    TOAST,     0x4005a2b8
        .set    DIALOG,    0x4006d57c   | (title, nlines, lines*, 3, cb); 0=YES
        .set    M_OPEN,    0x4006d94c   | (count, sel, &sel, labels, cbs)
        .set    M_CLOSE,   0x4006d754
        .set    M_OBJ,     0x460e5e30   | open LISTPOP object
        .set    M_CBS,     0x460e5e28   | callbacks pointer M_OPEN stored
        | FUNC+BANK / TRACK TRIG EDIT (PARTS.md MKI; MKII entry bra.b here).
        .set    FUNC_BANK_STOCK_MKI,  0x40058a64
        .set    MKII_TRIG_EDIT_CONT,  0x4007c0c0
        .set    PTN_STR,   0x8ed8
        .set    TRK_STR,   0x91a
        .set    PAT_LEN,   0x8e53       | pattern length (NORMAL scale)
        .set    PAT_PER,   0x8e55       | nonzero = PER TRACK
        .set    TRK_LEN,   0x50         | track length inside TRAC

        .set    WCREATE,   0x4005829c
        .set    WFRAME,    0x40056f4c
        .set    WDESTROY,  0x40055db4
        .set    CLEAR,     0x40035624
        .set    FONT,      0x400ba876   | small UI font, 6 px (tuner.s)
        .set    TEXT,      0x40012bd8   | (font, surf, x, y, limit, str)
        .set    TWIDTH,    0x40012f30   | (font, limit, str) -> pixels
        .set    RULE,      0x40011910   | (surf, x, y, w, h)
        .set    VLINE,     0x40011b94   | (surf, x, y0, y1, 1) solid
        .set    HLINE,     0x40012004   | (surf, x0, y0, x1, y1, mode) dotted
        .set    BOX,       0x40012254   | (surf, x1, y1, x2, y2, mode)
        .set    BLIT,      0x400128a8   | (glyph, surf, x, y)
        .set    SPRINTF,   0x40013a08
        .set    LPUSH,     0x40031494
        .set    LPOP,      0x4003146c
        .set    SCRDIRTY,  0x46c7c72c
        .set    TEMPO24,   0x80001814   | entropy seed (same as RND NAME)
        .set    CLOCKEST,  0x80001818

        .set    PAGE_GO,   0x4004ffcc   | after the displaced 8-byte prologue
        | HW tip CX EUCL52 (Ilia, 2026-11-10) - keep this geometry:
        | WINW=109 @ WINX=0 (19px for T5-8), no WFRAME, 1px top+bottom RULE,
        | DEST = PAGE+PARAM (no PMTR caption), 3x2 with C=LANE F empty.
        | Title top-left. Left gutter icon + right-aligned 3x2. Pattern at
        | bottom: top-left origin, centered, wider gap every 4 steps.
        .set    WINW,      109
        .set    WINH,      64
        .set    WINX,      0           | left 0; right 128-109 = 19 (T5-8)
        .set    CELL_W,    0x14
        .set    ROW_PITCH, 0x1b
        .set    X_GRID,    WINW-1-(3*CELL_W) | right-aligned (margin 1; +3 vs EUCL52)
        .set    X_DIV0,    X_GRID+CELL_W
        .set    X_DIV1,    X_GRID+2*CELL_W
        .set    X_C0,      X_GRID+CELL_W/2
        .set    X_C1,      X_GRID+CELL_W+CELL_W/2
        .set    X_C2,      X_GRID+2*CELL_W+CELL_W/2
        .set    X_PAGE_R,  X_GRID-1     | page affordance at the logo panel's top-right
        .set    ICON_W,    29          | left-gutter SEQ mark (3-ring LED)
        .set    ICON_H,    29
        .set    PAT_COLS,  16          | steps per row
        .set    PAT_ROWS,  4           | 4×16 = 64 max
        .set    PAT_SQ,    4           | square side (inclusive px)
        .set    PAT_GAP,   1           | gap between squares
        .set    PAT_SEP,   3           | extra gap after col 4/8/12 (no ticks)
        .set    PAT_STRIDE, PAT_SQ+PAT_GAP
        | Width = 16*SQ + 15*GAP + 3*SEP. Left-biased so LEN fits after
        | the squares in the window's bottom-right corner.
        .set    PAT_W,     PAT_COLS*PAT_SQ+(PAT_COLS-1)*PAT_GAP+3*PAT_SEP
        .set    X_PAT,     1
        .set    Y_PATT,    22          | +1px bottom clearance for row 3 squares
        .set    X_LEN_R,   WINW-2      | LEN stack right-aligned here
        .set    Y_LAB0,    0x38        | 56 - top cell labels (PULS/ROT)
        .set    Y_VAL0,    0x2f        | 47
        .set    Y_LEN_VAL, 5           | length digits - BR pocket (+2 vs floor)
        .set    Y_LEN_LAB, 14          | "LEN" tight above digits (same gap as PULS)
        .set    Y_GMID,    0x2b        | 43 - mid raised 1px (top −1 / bottom +1)
        | Bottom row: DEST = PAGE + PARAM (no PMTR - 3 lines crush into PULS).
        .set    Y_LAB1,    0x24        | 36 - PAGE / DPTH
        .set    Y_VAL1,    0x1e        | 30 - kept for grid math / docs
        .set    Y_DEST_P,  Y_LAB1      | PAGE (AMP/SRC)
        .set    Y_DEST_V,  Y_LAB1-(Y_LAB0-Y_VAL0) | PARAM - same gap as PULS/ROT
        | DEPTH value: same label→value gap as PULS/ROT.
        .set    Y_DEPTH_V, Y_LAB1-(Y_LAB0-Y_VAL0)
        .set    Y_GRID1,   WINH-2      | 62 - leave top rim free
        .set    Y_GRID0,   23          | floor above pattern (+1 with Y_PATT)
        | Icon centred in the left gutter (after Y_GRID* exist).
        | BLIT y = glyph BOTTOM (Y-up); bit31 = bottom row.
        .set    ICON_X,    (X_GRID-ICON_W)/2
        .set    ICON_Y,    (Y_GRID0+Y_GRID1-ICON_H)/2+1 | 2px up from EUCL97 (Y-up)

        .set    X_TITLE,   2           | "SEQ" top-left, next to the icon
        .set    Y_TITLE,   WINH-7      | 1px down with the icon
        .set    LOCK0,     0x59        | step records (STEP_LOCKS.md)
        .set    LOCK_STEP, 32
        .set    LOCK_VOL,  15          | AMP VOL flat (DEST default)
        .set    LOCK_PTCH, 0           | PLAYBACK PTCH flat (in-scale special)
        .set    UI_BANK,   0x100b14cf  | bank index
        .set    PART_STR,  6322        | Part stride in the bank blob
        .set    SIG_OFF,   0x8edbc     | NEIGHBOR col: "FM",1 when FM SYNTH chosen
        .set    MACH_OFF,  0x8eda2     | Part: machine byte per track
        .set    FX1_OFF,   0x8ed80     | Part: FX1 id per track
        .set    FX2_OFF,   0x8ed88     | Part: FX2 id per track
        .set    PLAY_SLOTS,0x8edaa     | Part: PLAYBACK p1 + mach·6 + t·30
        .set    PAGE1_OFF, 0x8ee9a     | Part: LFO/AMP/FX1/FX2 p1 + t·24
        .set    MIDI_P1_OFF,0x3e2      | Part-relative MIDI page-1 params + t·32
        .set    AMP_P1,    0x8eea0     | Part: AMP p1 + t·24 (ATK HOLD REL VOL…)
        .set    AMP_VOL,   3           | VOL slot inside AMP p1
        .set    PB_TABLE,  0x400d5f38  | machine -> PLAYBACK descriptor (P)
        .set    LFO_DESC,  0x400d37f6  | audio LFO page descriptor (P)
        .set    AMP_DESC,  0x400d3988  | AMP page descriptor (P)
        .set    FX1_TBL,   0x400d5f58  | FX1 id -> descriptor (P)
        .set    FX2_TBL,   0x400d5fdc  | FX2 id -> descriptor (P)
        .set    NAME_OFF,  0x16        | P+0x16: page-1 param names, 6 B each
        .set    TITLE_OFF, 4           | P+4: page short name (SRC/AMP/FILTR…)
        | Same PLAYBACK name path as LFO SETUP PMTR (cxosc po_lfdname):
        | resolver(track, kind0) -> machine PLAYBACK descriptor (CX: PTCH
        | RATO INDX FINE FOLD MIX; Flex/Static: stock names).
        .set    LFD_RESOLVER, 0x40031da4
        .set    LFD_MASTER, 0x400d2e8a
        .set    FLEX_P,    0x400d31ae  | stock FLEX PLAYBACK descriptor
        .set    DEST_LAST, 29          | last page-1 flat
        .set    DEST_CXLAST, 34        | CX SETUP CAR..PWM (LFO PMTR)
        .set    DEST_XVOL, 17          | AMP XVOL - skipped in DEST list
        .set    PLAY_SETUP, 0x8ef60    | Part + t·30: CAR MOD DEC SYMM FDBK PWM
        .set    CX_STEPS,  64          | per-track CX SETUP fill bank (OT max)
        .set    CX_NSLOT,  5           | CAR MOD SYMM FDBK PWM

        | DEST=PTCH: rad = max_rad*DEPTH/127 (min 1 if DEPTH>0).
        | PIT_RAD 24 = ±2 oct FM/SY; PIT_SAMP 12 = sample PLAYBACK max |st|.
        .set    PIT_RAD,   24
        .set    PIT_SAMP,  12
        .set    EF_MAGIC,  0x4546494c   | 'EFIL'
        .set    EF_VER,    11           | v11: RAND is PHRS default and value 0
        .set    EF_BANK_B, 224          | 8 tracks * 28
        .set    DEST_NSLOT, 36          | 0..34 + pad; track*36 = <<5+<<2
        .set    EF_DEP_B,  8*DEST_NSLOT | per-track × DEST depth bytes
        .set    EF_PLK_SLOT, 12         | pulse,rot,free,pad + 8-byte mask
        .set    EF_PLK_B,  8*DEST_NSLOT*EF_PLK_SLOT
        .set    EF_LANE_B, 8            | per-track LANE (0=TRIG 1=PLOCK)
        .set    EF_MIDI_B, EF_BANK_B    | eight MIDI recipes, appended for v4 compatibility
        .set    EF_FILE_V4, EF_BANK_B+EF_DEP_B+EF_PLK_B+EF_LANE_B
        .set    EF_FILE_V5, EF_FILE_V4+EF_MIDI_B
        .set    EF_MIDI_DEP_B, 8*DEST_NSLOT
        .set    EF_FILE_V6, EF_FILE_V5+EF_MIDI_DEP_B
        .set    EF_MIDI_PLK_NSLOT, 30
        .set    EF_MIDI_PLK_B, 8*EF_MIDI_PLK_NSLOT*EF_PLK_SLOT
        .set    EF_MIDI_LANE_B, 8
        .set    EF_FILE_V7, EF_FILE_V6+EF_MIDI_PLK_B+EF_MIDI_LANE_B
        .set    EF_TONE_REC, 8           | scale, root, mode, jump, phrase, harmony, style, pad
        .set    EF_TONE_B, 16*EF_TONE_REC | audio + MIDI tracks
        .set    EF_FILE_V8,EF_FILE_V7+EF_TONE_B
        .set    EF_FILE_V9,EF_FILE_V8
        .set    EF_FILE_V10,EF_FILE_V9
        .set    EF_FILE_B, EF_FILE_V10
        .set    TON_SCALE, 0
        .set    TON_ROOT,  1
        .set    TON_MODE,  2
        .set    TON_JUMP,  3           | pitch spacing; reuses old RANG byte
        .set    TON_PHRASE,4
        .set    TON_HARM,  5           | MIDI VOIC count, audio interval
        .set    TON_STYLE, 6
        .set    MASK_TL,   16           | trigless-lock mask offset (+0x10)
        .set    F_COPY,    0x40016388
        .include "remix.inc"            | EF_CLIENT from STORE CLIENT_IDS

        .text
        .globl  ef_page, ef_open, ef_close, ef_draw, ef_fill
        .globl  ef_yes, ef_no, ef_level, ef_enc
        .globl  ef_cue, ef_fb_mki, ef_fb_mkii
        .globl  ef_cl_dest, ef_cl_all, ef_cl_all_trigs
        .globl  ef_st_loadall_post, ef_st_loadmask_post, ef_st_newproj
        .globl  ef_st_bankw_post, ef_st_pstore_pre, ef_st_pstore_post
        .globl  ef_st_preload_post, ef_st_answer

| ---- 0x4004ffc4: PAGE press/release. Track held -> toggle Euclid. --------
| Displaced prologue: lea -16(sp),sp ; movem.l d2-d4/a2,(sp).
| On entry the stack is still stock's (keycode @4, event @8).
| Bare PAGE (no track held) always stock - never closes Euclid.
ef_page:
        tstl    HELD
        beq.s   9f                      | no track held: stock PAGE
        moveq   #1,%d0
        cmpl    8(%sp),%d0
        bne.s   8f                      | press only
        tstl    ef_win
        bne.w   ef_close                | TRACK+PAGE while open: close
        bra.w   ef_open
8:      rts
9:      lea     -16(%sp),%sp            | displaced prologue
        movem.l %d2-%d4/%a2,(%sp)
        jmp     PAGE_GO

| ---- open / close -------------------------------------------------------
| Open: YES targets = HELD bitmask (else UI_TRACK). Focus/bank = first
| held track - T4+PAGE must open T4's slot even if UI_TRACK is still T1
| (EUCL13 loaded UI_TRACK and ignored the chord).
ef_open:
        clrl    ef_page_no
        clrl    ef_tone_midi
        tstl    MIDI_MODE
        beq.s   op_tone_kind_ready
        moveq   #1,%d0
        movel   %d0,ef_tone_midi
op_tone_kind_ready:
        movel   HELD,%d0
        bne.s   1f
        moveq   #0,%d0
        moveb   UI_TRACK,%d0
        andil   #7,%d0
        moveq   #1,%d1
        lsll    %d0,%d1
        movel   %d1,%d0
1:      movel   %d0,ef_targets
        bsr.w   ef_first_target         | d0 = held track (not stale UI_TRACK)
        movel   %d0,ef_seen_trk
        moveq   #-1,%d1
        movel   %d1,ef_pending
        movel   %d0,-(%sp)
        bsr.w   ef_load_slot            | working := bank[held]
op_lane_ready:
        movel   (%sp),%d0
        | Stock select-track: CUR/UI + sequencer grid follow the chord.
        lea     -44(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        movel   44(%sp),-(%sp)          | track arg (above the save frame)
        jsr     SEL_TRACK
        addql   #4,%sp
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     44(%sp),%sp
        addql   #4,%sp                  | drop saved track
        | SEL_TRACK should have moved UI_TRACK; keep seen in sync so the
        | first draw's follow_ui does not load_slot over the open.
        moveq   #0,%d0
        moveb   UI_TRACK,%d0
        andil   #7,%d0
        movel   %d0,ef_seen_trk
        cmpl    ef_focus,%d0
        beq.s   op_go
        movel   ef_focus,%d0            | chord track wins if UI lagged
        movel   %d0,ef_seen_trk
op_go:
        bsr.w   ef_sync_len
        bsr.w   ef_drop_clr_undo        | prior CLEAR TRACK TRIGS undo is stale
        clrl    ef_ask
        clrl    ef_pending_edit
        clrl    ef_unlocked
        clrl    ef_dlg_guard
        clrl    ef_need_restore
        bsr.w   ef_cl_nolayer_off       | drop stuck CLEAR cancel layer
        clrl    ef_from_cue
        clrl    ef_cue_chord
        clrl    ef_cue_snap
        clrl    ef_cursor
        clrl    ef_pat_off              | scroll unused (4×16 shows all)
        bsr.w   ef_mkwin
        tstl    %d0
        beq.s   9f
        bra.w   ef_draw
9:      rts

| ef_mkwin: create the Euclid window + layer. d0 := handle, or 0 on fail.
| Used by open and by post-dialog restore (class-1 DIALOG evicts class 5).
ef_mkwin:
        pea     ef_close
        pea     5                       | TEMPO class: mutual eviction
        clrl    %sp@-                   | y = 0
        clrl    %sp@-                   | x = 0 (T5-8 keep the right 19px)
        pea     WINH
        pea     WINW
        jsr     WCREATE
        lea     %sp@(24),%sp
        movel   %d0,ef_win
        beq.s   mkw_rts
        | No WFRAME - top/bottom 1px drawn in ef_grid (RULE).
        tstl    ef_layer_on             | soft dialog kept the layer
        bne.s   mkw_on
        pea     EF_LAYER
        jsr     LPUSH
        addql   #4,%sp
mkw_on: moveq   #1,%d0
        movel   %d0,ef_layer_on
        movel   ef_win,%d0
mkw_rts: rts

| d0 := lowest set bit in ef_targets, else UI_TRACK & 7.
ef_first_target:
        moveq   #0,%d0
        movel   ef_targets,%d1
        beq.s   ft_ui
ft_bit: btst    %d0,%d1
        bne.s   ft_ok
        addql   #1,%d0
        moveq   #8,%d2
        cmpl    %d2,%d0
        bcs.s   ft_bit
ft_ui:  moveq   #0,%d0
        moveb   UI_TRACK,%d0
        andil   #7,%d0
ft_ok:  rts

| Tonal state is separate for audio and MIDI tracks, one 8-byte record each.
| Scale masks are built into SEQ, independent of SCALE QUANTIZER.
ef_tone_addr:
        moveq   #0,%d0
        movel   ef_focus,%d0
        andil   #7,%d0
        tstl    ef_tone_midi
        beq.s   1f
        addil   #8,%d0
1:      lsll    #3,%d0
        lea     ef_tone_mem,%a0
        addal   %d0,%a0
        rts
ef_tone_save:
        bsr.s   ef_tone_addr
        movel   ef_tone_scale,%d1
        moveb   %d1,%a0@(TON_SCALE)
        movel   ef_tone_root,%d1
        moveb   %d1,%a0@(TON_ROOT)
        movel   ef_tone_mode,%d1
        moveb   %d1,%a0@(TON_MODE)
        movel   ef_tone_jump,%d1
        moveb   %d1,%a0@(TON_JUMP)
        movel   ef_tone_phrase,%d1
        moveb   %d1,%a0@(TON_PHRASE)
        movel   ef_tone_harm,%d1
        moveb   %d1,%a0@(TON_HARM)
        movel   ef_tone_style,%d1
        moveb   %d1,%a0@(TON_STYLE)
        rts
ef_tone_load:
        bsr.s   ef_tone_addr
        moveq   #0,%d1
        moveb   %a0@(TON_SCALE),%d1
        movel   %d1,ef_tone_scale
        moveq   #0,%d1
        moveb   %a0@(TON_ROOT),%d1
        movel   %d1,ef_tone_root
        moveq   #0,%d1
        moveb   %a0@(TON_MODE),%d1
        movel   %d1,ef_tone_mode
        moveq   #0,%d1
        moveb   %a0@(TON_JUMP),%d1
        movel   %d1,ef_tone_jump
        moveq   #0,%d1
        moveb   %a0@(TON_PHRASE),%d1
        movel   %d1,ef_tone_phrase
        moveq   #0,%d1
        moveb   %a0@(TON_HARM),%d1
        movel   %d1,ef_tone_harm
        moveq   #0,%d1
        moveb   %a0@(TON_STYLE),%d1
        movel   %d1,ef_tone_style
        movel   ef_tone_scale,%d0
        andil   #7,%d0
        movel   %d0,ef_tone_scale
        movel   ef_tone_root,%d0
        cmpi.l  #11,%d0
        bls.s   6f
        moveq   #11,%d0
6:
        movel   %d0,ef_tone_root
        movel   ef_tone_mode,%d0
        tstl    ef_tone_midi
        bne.s   7f
        cmpi.l  #1,%d0
        bls.s   8f
        moveq   #1,%d0
        bra.s   8f
7:      cmpi.l  #2,%d0
        bls.s   8f
        clrl    %d0
8:      movel   %d0,ef_tone_mode
        movel   ef_tone_phrase,%d0
        cmpi.l  #4,%d0
        bls.s   3f
        clrl    ef_tone_phrase
3:      movel   ef_tone_jump,%d0
        cmpi.l  #127,%d0
        bls.s   10f
        moveq   #127,%d0
10:     movel   %d0,ef_tone_jump
        movel   ef_tone_harm,%d0
        tstl    ef_tone_midi
        bne.s   4f
        cmpi.l  #6,%d0
        bls.s   5f
        moveq   #6,%d0
        bra.s   5f
4:      cmpi.l  #1,%d0
        bcc.s   6f
        moveq   #1,%d0
6:      cmpi.l  #4,%d0
        bls.s   5f
        moveq   #4,%d0
5:      movel   %d0,ef_tone_harm
        rts
ef_tone_defaults:
        lea     ef_tone_mem,%a0
        moveq   #15,%d0
1:      clrb    %a0@(TON_SCALE)
        clrb    %a0@(TON_ROOT)
        clrb    %a0@(TON_MODE)
        clrb    %a0@(TON_JUMP)
        clrb    %a0@(TON_PHRASE)
        clrb    %a0@(TON_HARM)
        clrb    %a0@(TON_STYLE)
        clrb    %a0@(7)
        addal   #EF_TONE_REC,%a0
        subql   #1,%d0
        bpl.s   1b
        clrl    ef_tone_scale
        clrl    ef_tone_root
        clrl    ef_tone_mode
        clrl    ef_tone_jump
        clrl    ef_tone_phrase
        clrl    ef_tone_harm
        clrl    ef_tone_style
        rts

| Stored v10 PHRS values were UP/DOWN/ALT/TRI/RAND = 0..4.
| v11 puts RAND first; rotate all 16 audio/MIDI track values by one.
ef_tone_phrase_v10_to_v11:
        lea     ef_tone_mem,%a0
        moveq   #15,%d0
etp_migrate:
        moveq   #0,%d1
        moveb   %a0@(TON_PHRASE),%d1
        addql   #1,%d1
        cmpi.l  #5,%d1
        bcs.s   etp_store
        clrl    %d1
etp_store:
        moveb   %d1,%a0@(TON_PHRASE)
        addal   #EF_TONE_REC,%a0
        subql   #1,%d0
        bpl.s   etp_migrate
        rts

| Store working params into bank[ef_focus]. Clobbers d0/d1/a0/a1.
| ColdFire has no memory-to-memory move.l - stage each long through d1
| (open called load_slot first; mem-to-mem illegal-insn hung TRACK+PAGE).
ef_store_slot:
        tstl    MIDI_MODE
        beq.s   st_slot_recipe
        tstl    ef_lane
        beq.s   st_slot_recipe
        bsr.w   ef_plk_save             | MIDI PLOCK rhythm is separate
st_slot_recipe:
        moveq   #0,%d0
        movel   ef_focus,%d0
        andil   #7,%d0
        lea     ef_bank,%a0
        tstl    MIDI_MODE
        beq.s   st_bank_ready
        lea     ef_midi_bank,%a0
st_bank_ready:
        | slot = track * 28 = track*32 - track*4 (no mulu.l)
        movel   %d0,%d1
        lsll    #5,%d0
        lsll    #2,%d1
        subl    %d1,%d0
        addal   %d0,%a0
        movel   ef_pulses,%d1
        movel   %d1,%a0@+
        movel   ef_rot,%d1
        movel   %d1,%a0@+
        movel   ef_dest,%d1
        movel   %d1,%a0@+
        movel   ef_depth,%d1
        movel   %d1,%a0@+
        movel   ef_free,%d1
        movel   %d1,%a0@+
        lea     ef_mask,%a1
        moveq   #7,%d0
st_m:   moveb   %a1@(0,%d0:l),%d1
        moveb   %d1,%a0@(0,%d0:l)
        subql   #1,%d0
        bpl.s   st_m
        bsr.w   ef_tone_save
        moveq   #1,%d0
        movel   %d0,ef_dirty            | euclid.work on next project/bank save
        rts

| Load bank[d0] into working; set ef_focus = d0 & 7. Clobbers d0/d1/a0/a1.
ef_load_slot:
        andil   #7,%d0
        movel   %d0,ef_focus
        lea     ef_bank,%a0
        tstl    MIDI_MODE
        beq.s   ld_bank_ready
        lea     ef_midi_bank,%a0
ld_bank_ready:
        movel   %d0,%d1
        lsll    #5,%d0
        lsll    #2,%d1
        subl    %d1,%d0
        addal   %d0,%a0
        movel   %a0@+,%d1
        movel   %d1,ef_pulses
        movel   %a0@+,%d1
        movel   %d1,ef_rot
        movel   %a0@+,%d1
        movel   %d1,ef_dest
        movel   %a0@+,%d1
        movel   %d1,ef_depth
        movel   %a0@+,%d1
        movel   %d1,ef_free
        lea     ef_mask,%a1
        moveq   #7,%d0
ld_m:   moveb   %a0@(0,%d0:l),%d1
        moveb   %d1,%a1@(0,%d0:l)
        subql   #1,%d0
        bpl.s   ld_m
        bsr.w   ef_tone_load
        tstl    ef_tone_midi
        beq.s   ld_dest_checked
        movel   ef_dest,%d0
        cmpi.l  #3,%d0
        bcs.s   ld_dest_checked
        cmpi.l  #6,%d0
        bcc.s   ld_dest_checked
        clrl    ef_dest               | old NOTE2..4 selection -> NOTE
ld_dest_checked:
        | Clamp DEST/DEPTH; MIDI has its own 0..29 map; audio skips XVOL.
        movel   ef_focus,%d0
        movel   %d0,ef_trk
        movel   ef_dest,%d0
        tstl    %d0
        bpl.s   ld_d0
        clrl    %d0
ld_d0:  movel   %d0,-(%sp)
        bsr.w   ef_dest_max
        movel   %d0,%d1
        movel   (%sp)+,%d0
        cmpl    %d1,%d0
        ble.s   ld_d1
        movel   %d1,%d0
ld_d1:  moveq   #DEST_XVOL,%d1
        tstl    MIDI_MODE
        bne.s   ld_d2
        cmpl    %d1,%d0
        bne.s   ld_d2
        moveq   #16,%d0                 | BAL
ld_d2:  movel   %d0,ef_dest
        movel   ef_depth,%d0
        tstl    %d0
        bpl.s   ld_e0
        clrl    %d0
ld_e0:  moveq   #127,%d1
        cmpl    %d1,%d0
        ble.s   ld_e1
        movel   %d1,%d0
ld_e1:  movel   %d0,ef_depth
        bsr.w   ef_dep_load             | depth := mem[focus][dest] (0 if none)
        tstl    MIDI_MODE
        bne.s   ld_midi_slot
        bsr.w   ef_plk_load             | plock rhythm for DEST
        bsr.w   ef_lane_load            | LANE for this track
        rts
ld_midi_slot:
        bsr.w   ef_plk_load
        bsr.w   ef_lane_load
ld_slot_done:
        rts

| ---- per-track × DEST depth memory (persisted in euclid.work v2) --------
| Byte table: 0 = never set. DEST scroll loads; DEPTH edit / YES fill saves.
ef_dep_ptr:
        moveq   #0,%d0
        movel   ef_focus,%d0
        andil   #7,%d0
        movel   %d0,%d1
        lsll    #5,%d0                  | t*32
        lsll    #2,%d1                  | t*4
        addl    %d1,%d0                 | t*36
        moveq   #0,%d1
        movel   ef_dest,%d1
        tstl    %d1
        bpl.s   dp1
        clrl    %d1
dp1:    cmpi.l  #DEST_CXLAST,%d1
        ble.s   dp2
        moveq   #DEST_CXLAST,%d1
dp2:    addl    %d1,%d0
        lea     ef_dep_mem,%a0
        tstl    MIDI_MODE
        beq.s   dp3
        lea     ef_midi_dep_mem,%a0
dp3:
        addal   %d0,%a0
        rts

| ef_dep_load: ef_depth := mem[focus][dest]. Clobbers d0/d1/a0.
ef_dep_load:
        bsr.w   ef_dep_ptr
        moveq   #0,%d0
        moveb   %a0@,%d0
        movel   %d0,ef_depth
        rts

| ef_dep_save: mem[focus][dest] := ef_depth (0..127); mark dirty.
| Clobbers d0/d1/a0.
ef_dep_save:
        bsr.w   ef_dep_ptr
        movel   ef_depth,%d0
        tstl    %d0
        bpl.s   dps0
        clrl    %d0
dps0:   moveq   #127,%d1
        cmpl    %d1,%d0
        ble.s   dps1
        movel   %d1,%d0
dps1:   moveb   %d0,%a0@
        moveq   #1,%d0
        movel   %d0,ef_dirty
        rts

| ---- per-track × DEST plock rhythm (euclid.work v4) ---------------------
| 12 B/slot: [0]PULSE [1]ROT [2]free [3]pad [4..11]mask. + ef_lane_mem[8].
ef_plk_ptr:
        moveq   #0,%d0
        movel   ef_focus,%d0
        andil   #7,%d0
        movel   %d0,%d1
        tstl    MIDI_MODE
        beq.s   pp_audio_stride
        lsll    #5,%d0                  | t*32 - t*2 = t*30
        lsll    #1,%d1
        subl    %d1,%d0
        bra.s   pp_stride_done
pp_audio_stride:
        lsll    #5,%d0                  | t*32
        lsll    #2,%d1                  | t*4
        addl    %d1,%d0                 | t*36
pp_stride_done:
        moveq   #0,%d1
        movel   ef_dest,%d1
        tstl    %d1
        bpl.s   pp1
        clrl    %d1
pp1:    tstl    MIDI_MODE
        bne.s   pp_midi_max
        cmpi.l  #DEST_CXLAST,%d1
        ble.s   pp2
        moveq   #DEST_CXLAST,%d1
        bra.s   pp2
pp_midi_max:
        cmpi.l  #29,%d1
        ble.s   pp2
        moveq   #29,%d1
pp2:    addl    %d1,%d0                 | slot index
        movel   %d0,%d1
        lsll    #3,%d0                  | *8
        lsll    #2,%d1                  | *4
        addl    %d1,%d0                 | *12
        lea     ef_plk_mem,%a0
        tstl    MIDI_MODE
        beq.s   pp_base_ready
        lea     ef_midi_plk_mem,%a0
pp_base_ready:
        addal   %d0,%a0
        rts

| ef_plk_load: working plock rhythm := mem[focus][dest].
ef_plk_load:
        bsr.w   ef_plk_ptr
        moveq   #0,%d0
        moveb   %a0@,%d0
        movel   %d0,ef_ppulses
        moveq   #0,%d0
        moveb   1(%a0),%d0
        movel   %d0,ef_prot
        moveq   #0,%d0
        moveb   2(%a0),%d0
        movel   %d0,ef_pfree
        lea     4(%a0),%a0
        lea     ef_pmask,%a1
        moveq   #7,%d0
pl_m:   moveb   %a0@(0,%d0:l),%d1
        moveb   %d1,%a1@(0,%d0:l)
        subql   #1,%d0
        bpl.s   pl_m
        rts

| ef_plk_save: mem[focus][dest] := working plock rhythm; dirty.
ef_plk_save:
        bsr.w   ef_plk_ptr
        movel   ef_ppulses,%d0
        tstl    %d0
        bpl.s   ps0
        clrl    %d0
ps0:    moveq   #64,%d1
        cmpl    %d1,%d0
        ble.s   ps1
        movel   %d1,%d0
ps1:    moveb   %d0,%a0@
        movel   ef_prot,%d0
        tstl    %d0
        bpl.s   ps2
        clrl    %d0
ps2:    moveq   #63,%d1
        cmpl    %d1,%d0
        ble.s   ps3
        movel   %d1,%d0
ps3:    moveb   %d0,1(%a0)
        movel   ef_pfree,%d0
        tstl    %d0
        beq.s   ps4
        moveq   #1,%d0
ps4:    moveb   %d0,2(%a0)
        clrb    3(%a0)
        lea     4(%a0),%a0
        lea     ef_pmask,%a1
        moveq   #7,%d0
ps_m:   moveb   %a1@(0,%d0:l),%d1
        moveb   %d1,%a0@(0,%d0:l)
        subql   #1,%d0
        bpl.s   ps_m
        moveq   #1,%d0
        movel   %d0,ef_dirty
        rts

| Per-track LANE (0/1) in ef_lane_mem. Clobbers d0/a0.
ef_lane_load:
        moveq   #0,%d0
        movel   ef_focus,%d0
        andil   #7,%d0
        lea     ef_lane_mem,%a0
        tstl    MIDI_MODE
        beq.s   ll_base_ready
        lea     ef_midi_lane_mem,%a0
ll_base_ready:
        moveq   #0,%d1
        moveb   %a0@(0,%d0:l),%d1
        moveq   #1,%d0
        cmpl    %d0,%d1
        ble.s   ll1
        moveq   #0,%d1
ll1:    movel   %d1,ef_lane
        rts

ef_lane_save:
        moveq   #0,%d0
        movel   ef_focus,%d0
        andil   #7,%d0
        lea     ef_lane_mem,%a0
        tstl    MIDI_MODE
        beq.s   ls_base_ready
        lea     ef_midi_lane_mem,%a0
ls_base_ready:
        movel   ef_lane,%d1
        tstl    %d1
        beq.s   ls1
        moveq   #1,%d1
ls1:    moveb   %d1,%a0@(0,%d0:l)
        moveq   #1,%d0
        movel   %d0,ef_dirty
        rts

| While open: apply ef_pending (from T1..T8) or fall back to UI_TRACK.
| No CUR_TRACK read/write here - that path bricked hardware.
ef_follow_ui:
        tstl    ef_win
        beq.s   fu_rts
        movel   ef_pending,%d0
        moveq   #-1,%d1
        cmpl    %d1,%d0
        beq.s   fu_ui
        movel   %d1,ef_pending          | consume
        bra.s   fu_do
fu_ui:  moveq   #0,%d0
        moveb   UI_TRACK,%d0
        andil   #7,%d0
fu_do:  cmpl    ef_seen_trk,%d0
        beq.s   fu_rts
        movel   %d0,ef_seen_trk
        movel   %d0,-(%sp)
        bsr.w   ef_store_slot
        movel   (%sp),%d0
        moveq   #1,%d1
        lsll    %d0,%d1
        movel   %d1,ef_targets
        movel   (%sp)+,%d0
        bsr.w   ef_load_slot
        bsr.w   ef_sync_len
fu_rts: rts

| STEPS from the UI pattern's length (NORMAL: +0x8e53; PER TRACK: first
| target track's TRAC+0x50). Same sources as RLEN PLEN / DIRECT JUMP.
| Offsets past ±32K use an address register + add (ColdFire d16 limit).
ef_sync_len:
        moveal  DBPTR,%a0
        moveq   #0,%d0
        moveb   UI_PTN,%d0
        movel   #PTN_STR,%d1
        mulu.l  %d1,%d0
        addal   %d0,%a0                 | a0 = pattern base
        tstl    MIDI_MODE
        bne.w   sl_midi                 | MIDI tracks always use their own LEN
        movel   %a0,%d1
        addil   #PAT_PER,%d1
        moveal  %d1,%a1
        tst.b   %a1@
        beq.s   sl_pat
        moveq   #0,%d2                  | first set bit in ef_targets
        movel   ef_targets,%d3
sl_bit: btst    %d2,%d3
        bne.s   sl_trk
        addql   #1,%d2
        moveq   #8,%d0
        cmpl    %d0,%d2
        bcs.s   sl_bit
        moveq   #0,%d2
        moveb   UI_TRACK,%d2
        andil   #7,%d2
sl_trk: movel   %d2,%d0
        movel   #TRK_STR,%d1
        mulu.l  %d1,%d0
        addil   #TRK_LEN,%d0
        moveb   %a0@(0,%d0:l),%d0
        extb.l  %d0
        bra.s   sl_clamp
sl_pat: movel   %a0,%d1
        addil   #PAT_LEN,%d1
        moveal  %d1,%a1
        moveb   %a1@,%d0
        extb.l  %d0
sl_clamp:
        moveq   #1,%d1
        cmpl    %d1,%d0
        bge.s   sl1
        moveq   #1,%d0
sl1:    moveq   #64,%d1
        cmpl    %d1,%d0
        ble.s   sl2
        moveq   #64,%d0
sl2:    movel   %d0,ef_steps
        movel   ef_pulses,%d1
        cmpl    %d0,%d1
        ble.s   sl3
        movel   %d0,ef_pulses
sl3:    movel   ef_rot,%d1
        subql   #1,%d0
        cmpl    %d0,%d1
        ble.s   sl4
        movel   %d0,ef_rot
sl4:    clrl    ef_pat_off              | all steps fit; scroll unused
        rts
sl_midi:
        | MIDI track t has LEN at +0x48f8+t*0x8b0.
        moveq   #0,%d2
        moveb   UI_TRACK,%d2
        andil   #7,%d2
        movel   #0x8b0,%d1
        mulu.l  %d1,%d2
        addil   #0x48f8,%d2
        moveq   #0,%d0
        moveb   %a0@(0,%d2:l),%d0
        extb.l  %d0
        bra.w   sl_clamp

| Close callback / NO / ef_page. Soft dialog (dlg_guard): destroy the
| window only and KEEP EF_LAYER - encoders stay on ef_enc/ef_ask so
| knobs stay locked while ARE YOU SURE? is up. Answer restores via
| ef_mkwin (layer already on). User close / orphan: LPOP via layer_on.
ef_close:
        tstl    ef_dlg_guard
        beq.s   close_nosoft
        moveq   #1,%d0
        movel   %d0,ef_need_restore     | even if win already 0 (LISTPOP race)
        tstl    ef_win
        beq.s   soft_rts                | re-enter after zero: keep layer
        pea     ef_win
        jsr     WDESTROY
        addql   #4,%sp
soft_rts:
        rts
close_nosoft:
        tstl    ef_win
        beq.s   close_orphan            | class-1 may zero handle first
        clrl    ef_ask
        clrl    ef_pending_edit
        clrl    ef_unlocked
        clrl    ef_need_restore
        bsr.w   ef_store_slot
        bsr.w   ef_cl_close             | drop clear LISTPOP if still up
        bsr.w   ef_cl_nolayer_off
        pea     ef_win
        jsr     WDESTROY
        addql   #4,%sp
        | WDESTROY may re-enter → close_orphan LPOPs once (layer_on).
close_orphan:
        tstl    ef_layer_on
        beq.s   9f
        clrl    ef_layer_on
        pea     EF_LAYER
        jsr     LPOP
        addql   #4,%sp
9:      rts


ef_no:
        moveq   #1,%d0
        cmpl    8(%sp),%d0
        bne.s   9f
        bsr.w   ef_cl_ours              | our CLEAR list still up?
        tstl    %d0
        beq.s   en_soft
        jsr     M_CLOSE
        clrl    ef_dlg_guard
        bra.w   ef_cl_rest
en_soft:
        | LISTPOP may have already eaten NO and closed; still restore.
        tstl    ef_dlg_guard
        beq.s   en_close
        clrl    ef_dlg_guard
        bra.w   ef_cl_rest
en_close:
        bra.w   ef_close
9:      rts

ef_yes:
        moveq   #1,%d0
        cmpl    8(%sp),%d0
        bne.s   9f
        clrl    ef_unlocked             | re-lock rhythm knobs after a bake
        bsr.w   ef_fill
        pea     0x30
        pea     T_FILLED
        jsr     TOAST
        addql   #8,%sp
        bra.w   ef_draw
9:      rts

| ---- CUE: stock hold + SEQ random on bare release ----------------------
| Press: stock CUE (hold / cue LED). Release with no TRACK while held:
| free random k-subset on the focused lane (TRIG: ARE YOU SURE? when
| baked; PLOCK: no prompt). CUE+TRACK sets ef_cue_chord so release
| skips random and only runs stock CUE release.
ef_cue:
        moveq   #1,%d0
        cmpl    8(%sp),%d0
        beq.s   cue_down
        | release: drop modifier; skip random if cue bits moved
        | (CUE+TRACK). Stock's CUE sub-map often owns TRACK while CUE
        | is held, so ef_trkkey may never see the chord - compare the
        | cue mask snapshot from press instead.
        clrl    CUE_HELD
        movel   MUTE_CUE,%d0
        swap    %d0                     | cue bits in low 16
        andil   #0xff,%d0
        cmpl    ef_cue_snap,%d0
        bne.s   cue_rel_done            | CUE+TRACK changed a cue bit
        tstl    ef_cue_chord
        bne.s   cue_rel_done            | layer saw the chord
        bsr.w   ef_cue_random
cue_rel_done:
        clrl    ef_cue_chord
        rts
cue_down:
        clrl    ef_cue_chord
        moveq   #1,%d0
        moveb   %d0,CUE_HELD            | same byte stock CUE press writes
        movel   MUTE_CUE,%d0
        swap    %d0
        andil   #0xff,%d0
        movel   %d0,ef_cue_snap         | cue mask before possible TRACK
        rts

| SEQ random k-subset (former bare-CUE press body). Clobbers many regs.
ef_cue_random:
        bsr.w   ef_sync_len
        tstl    ef_lane
        bne.s   cue_go                  | PLOCK cue: no trig-clear prompt
        bsr.w   ef_rhythm_gate
        tstl    %d0
        beq.s   cue_go
        tstl    MIDI_MODE
        beq.w   ef_cue_rts
        moveq   #2,%d0
        movel   %d0,ef_pending_edit
        bra.w   ef_cue_rts
cue_go: move.l  ef_steps,%d5            | n
        moveq   #1,%d0
        cmpl    %d0,%d5
        bge.s   1f
        moveq   #1,%d5
1:      moveq   #64,%d0
        cmpl    %d0,%d5
        ble.s   2f
        moveq   #64,%d5
2:      tstl    ef_lane
        bne.s   cue_pk
        move.l  ef_pulses,%d4           | TRIG k
        bra.s   cue_k
cue_pk: move.l  ef_ppulses,%d4          | PLOCK k
cue_k:  tstl    %d4
        bpl.s   21f
        clrl    %d4
21:     cmpl    %d5,%d4
        ble.s   22f
        move.l  %d5,%d4
        tstl    ef_lane
        bne.s   cue_ks
        move.l  %d4,ef_pulses
        bra.s   22f
cue_ks: move.l  %d4,ef_ppulses
22:     tstl    ef_lane
        bne.s   cue_m
        lea     ef_mask,%a0
        bra.s   cue_mz
cue_m:  lea     ef_pmask,%a0
cue_mz: moveq   #7,%d0
0:      clrb    %a0@(0,%d0:l)
        subql   #1,%d0
        bpl.s   0b
        moveq   #0,%d2                  | placed so far
cplace: cmpl    %d4,%d2
        bcc.w   cdone
        | pick among the (n - placed) free slots.
        | ef_rng clobbers d0/d1 - park the divisor; a live d1 here was
        | 1664525 and remul made an unreachable rank → cwalk spun forever.
        move.l  %d5,%d1
        sub.l   %d2,%d1                 | free count > 0
        movel   %d1,-(%sp)
        bsr.w   ef_rng
        move.l  %d0,%d3                 | dividend
        movel   (%sp)+,%d1              | divisor
        | ColdFire: remul Dr,Du_rem,Dc_div - NOT divu.w (illegal on 5407)
        remul   %d1,%d0,%d3             | d0 = d3 % d1
        move.l  %d0,%d3                 | target rank 0..free-1
        moveq   #0,%d6                  | step
        moveq   #0,%d7                  | free seen
cwalk:  cmpl    %d5,%d6
        bcc.w   cdone                   | defense: never walk past n
        | is bit d6 set?
        move.l  %d6,%d1
        lsr.l   #3,%d1
        tstl    ef_lane
        bne.s   cw_m
        lea     ef_mask,%a0
        bra.s   cw_t
cw_m:   lea     ef_pmask,%a0
cw_t:   move.b  %a0@(0,%d1:l),%d0
        andil   #0xff,%d0               | ColdFire: MOVE.B leaves upper bits
        move.l  %d6,%d1
        andil   #7,%d1
        btst    %d1,%d0
        bne.s   cskip                   | already on: not free
        cmpl    %d3,%d7
        beq.s   cset
        addql   #1,%d7
cskip:  addql   #1,%d6
        bra.s   cwalk
cset:   | set bit d6
        move.l  %d6,%d1
        lsr.l   #3,%d1
        tstl    ef_lane
        bne.s   cs_m
        lea     ef_mask,%a0
        bra.s   cs_a
cs_m:   lea     ef_pmask,%a0
cs_a:   addal   %d1,%a0
        move.l  %d6,%d1
        andil   #7,%d1
        moveq   #1,%d0
        lsll    %d1,%d0
        move.b  %a0@,%d1
        or.l    %d0,%d1
        move.b  %d1,%a0@
        addql   #1,%d2
        bra.w   cplace
cdone:  moveq   #1,%d0
        movel   %d0,ef_from_cue         | bake YES may use free/pmask
        tstl    ef_lane
        bne.s   cd_p
        move.l  %d0,ef_free
        bsr.w   ef_store_slot           | TRIG free mask per-track
        bra.s   cd_d
cd_p:   move.l  %d0,ef_pfree
        bsr.w   ef_plk_save
cd_d:   clrl    ef_cursor
        bra.w   ef_draw
ef_cue_rts:
        rts

| Numerical Recipes LCG (same constants as RND NAME). Seed from tempo/clock.
ef_rng:
        move.l  ef_rng_state,%d0
        bne.s   1f
        move.l  TEMPO24,%d0
        move.l  CLOCKEST,%d1
        eor.l   %d1,%d0
        eor.l   #0xA5A5A5A5,%d0
        bne.s   1f
        moveq   #1,%d0
1:      move.l  #1664525,%d1
        mulu.l  %d1,%d0
        add.l   #1013904223,%d0
        move.l  %d0,ef_rng_state
        rts

| d2=step i, d4=k (euclid), d5=n, d6=rot -> d7=1 if that cell is on.
| Free mode: bit (i+n-rot)%n of ef_mask. Euclid: (idx·k)%n < k.
ef_hit:
        move.l  %d2,%d3
        addl    %d5,%d3
        subl    %d6,%d3
1:      cmpl    %d5,%d3
        bcs.s   2f
        subl    %d5,%d3
        bra.s   1b
2:      moveq   #0,%d7
        tstl    ef_free
        beq.s   4f
        | free: test bit d3 in ef_mask
        move.l  %d3,%d1
        lsr.l   #3,%d1
        lea     ef_mask,%a0
        move.b  %a0@(0,%d1:l),%d0
        andil   #0xff,%d0
        move.l  %d3,%d1
        andil   #7,%d1
        btst    %d1,%d0
        beq.s   3f
        moveq   #1,%d7
3:      rts
4:      tstl    %d4
        beq.s   3b
        move.l  %d3,%d0
        mulu.w  %d4,%d0                 | idx * k
        remul   %d5,%d1,%d0             | d1 = (idx*k) % n
        cmpl    %d4,%d1
        bcc.s   3b
        moveq   #1,%d7
        rts


| d2=step, d5=n; k/rot from ef_ppulses/ef_prot; free=ef_pfree/ef_pmask.
| Same law as ef_hit. -> d7.
ef_phit:
        movel   ef_ppulses,%d4
        tstl    %d4
        bpl.s   ph0
        clrl    %d4
ph0:    movel   ef_prot,%d6
        tstl    %d6
        bpl.s   ph1
        clrl    %d6
ph1:    move.l  %d2,%d3
        addl    %d5,%d3
        subl    %d6,%d3
ph2:    cmpl    %d5,%d3
        bcs.s   ph3
        subl    %d5,%d3
        bra.s   ph2
ph3:    moveq   #0,%d7
        tstl    ef_pfree
        beq.s   ph5
        move.l  %d3,%d1
        lsr.l   #3,%d1
        lea     ef_pmask,%a0
        move.b  %a0@(0,%d1:l),%d0
        andil   #0xff,%d0
        move.l  %d3,%d1
        andil   #7,%d1
        btst    %d1,%d0
        beq.s   ph4
        moveq   #1,%d7
ph4:    rts
ph5:    tstl    %d4
        beq.s   ph4
        move.l  %d3,%d0
        mulu.w  %d4,%d0
        remul   %d5,%d1,%d0
        cmpl    %d4,%d1
        bcc.s   ph4
        moveq   #1,%d7
        rts

| Encoders: page 1 = rhythm controls; page 2 = tonal controls.
| Cursor: 0=PULSE 1=ROT 2=LANE 3=DEST 4=DEPTH. F rejected.
ef_page_left:
        tstl    ef_ask
        bne.s   9f
        clrl    ef_page_no
        bra.w   ef_draw
ef_page_right:
        tstl    ef_ask
        bne.s   9f
        bsr.w   ef_pitch_selected
        tstl    %d0
        beq.s   9f
        moveq   #1,%d0
        movel   %d0,ef_page_no
        bra.w   ef_draw
9:      rts

ef_enc:
        bsr.w   ef_cl_poll              | LISTPOP may have closed on NO already
        tstl    ef_ask                  | CLEAR PATTERN? dialog: all knobs dead
        bne.s   9f
        bsr.w   ef_cl_ours              | clear LISTPOP: knobs locked
        tstl    %d0
        bne.s   9f
        movel   4(%sp),%d1              | encoder index 0..5
        tstl    ef_page_no
        bne.s   ef_enc_tonal
        moveq   #5,%d0
        cmpl    %d0,%d1
        beq.s   9f                      | F empty
        bhi.s   9f
        movel   %d1,ef_cursor           | A..E = 0..4
        movel   8(%sp),%d0
        beq.s   9f
        bra.w   ef_nudge
ef_enc_tonal:
        moveq   #6,%d0
        cmpl    %d0,%d1
        bcc.s   9f
        movel   %d1,ef_cursor
        movel   8(%sp),%d0
        beq.s   9f
        bra.w   ef_tonal_nudge
9:      rts

| LEVEL encoder: bound but dead (A/B/D/E own the four cells).
ef_level:
        rts
| Encoder path: d0 = ±delta already. Edits the last A/B/D/E param.
| ef_sync_len clobbers d0-d3/a0/a1 - park the signed delta on the stack
| first. Without that, every encoder turn nudges upward only.
| While CLEAR PATTERN? is up: every knob locked. Else PULSE/ROT (and CUE)
| need unlock when baked; DEST/DEPTH free once the dialog is gone.
ef_nudge:
        tstl    ef_ask                  | dialog up: knobs dead
        bne.w   ef_nudge_rts
        movel   %d0,-(%sp)              | park signed delta (cl_ours clobbers)
        bsr.w   ef_cl_ours
        tstl    %d0
        beq.s   ef_nudge_go
        addql   #4,%sp
        bra.w   ef_nudge_rts
ef_nudge_go:
        bsr.w   ef_sync_len             | STEPS stays = pattern length
        movel   (%sp)+,%d2              | restore delta
        movel   ef_cursor,%d1
nud_mode_ready:
        | PULSE/ROT (0/1): rhythm gate only on TRIG lane
        moveq   #1,%d0
        cmpl    %d0,%d1
        bhi.s   nudge_go
        tstl    ef_lane
        bne.s   nudge_go                | PLOCK edits: no trig-clear prompt
        movel   %d2,-(%sp)
        movel   %d1,-(%sp)
        bsr.w   ef_rhythm_gate
        movel   (%sp)+,%d1
        movel   (%sp)+,%d2
        tstl    %d0
        beq.s   nudge_go
        tstl    MIDI_MODE
        beq.w   ef_nudge_rts
        moveq   #1,%d0
        movel   %d0,ef_pending_edit
        movel   %d2,ef_pending_delta
        movel   %d1,ef_pending_cursor
        bra.w   ef_nudge_rts
nudge_go:
        | LANE (cursor 2): 0=TRIG 1=PLOCK
        moveq   #2,%d0
        cmpl    %d0,%d1
        bne.s   nd_ab
        movel   ef_lane,%d0
        addl    %d2,%d0
        tstl    %d0
        bpl.s   ln0
        clrl    %d0
ln0:    moveq   #1,%d3
        cmpl    %d3,%d0
        ble.s   ln1
        movel   %d3,%d0
ln1:    movel   %d0,ef_lane
        bsr.w   ef_lane_save
        bra.w   ef_draw
nd_ab:
        | A/B -> focused rhythm (TRIG: ef_pulses/rot; PLOCK: ppulses/prot)
        tstl    %d1
        beq.s   nd_pulse
        moveq   #1,%d0
        cmpl    %d0,%d1
        beq.s   nd_rot
        bra.w   nd_dest
nd_pulse:
        clrl    ef_from_cue             | knob edit: bake from PULSE, not mask
        tstl    ef_lane
        bne.s   nd_pp
        lea     ef_pulses,%a0
        clrl    ef_free                 | back to Euclid
        bra.s   nd_pr_clamp
nd_pp:  lea     ef_ppulses,%a0
        clrl    ef_pfree
        bra.s   nd_pr_clamp
nd_rot:
        clrl    ef_from_cue
        tstl    ef_lane
        bne.s   nd_pr
        lea     ef_rot,%a0
        bra.s   nd_rt_clamp
nd_pr:  lea     ef_prot,%a0
        bra.s   nd_rt_clamp
nd_pr_clamp:
        movel   %a0@,%d0
        addl    %d2,%d0
        tstl    %d0
        bpl.s   pc0
        clrl    %d0
pc0:    movel   ef_steps,%d3
        cmpl    %d3,%d0
        ble.s   pc1
        movel   %d3,%d0
pc1:    movel   %d0,%a0@
        tstl    ef_lane
        beq.w   nd_store
        bsr.w   ef_plk_save
        bra.w   nd_store
nd_rt_clamp:
        movel   %a0@,%d0
        addl    %d2,%d0
        tstl    %d0
        bpl.s   rc0
        clrl    %d0
rc0:    movel   ef_steps,%d3
        subql   #1,%d3
        cmpl    %d3,%d0
        ble.s   rc1
        movel   %d3,%d0
rc1:    movel   %d0,%a0@
        tstl    ef_lane
        beq.w   nd_store
        bsr.w   ef_plk_save
        bra.w   nd_store
nd_dest:
        moveq   #3,%d0
        cmpl    %d0,%d1
        bne.w   nd_depth
        | DEST: save plock for old DEST, then change, load depth+plock
        tstl    MIDI_MODE
        bne.s   nds_midi_old
        bsr.w   ef_plk_save
        bra.s   nds_midi
nds_midi_old:
        tstl    ef_lane
        beq.s   nds_midi
        bsr.w   ef_plk_save
nds_midi:
        lea     ef_dest,%a0
        movel   %a0@,%d0
        tstl    ef_tone_midi
        beq.s   nds_midi_audio
        cmpi.l  #3,%d0
        bcs.s   nds_midi_indexed
        cmpi.l  #6,%d0
        bcc.s   nds_midi_skip
        clrl    %d0                    | legacy NOT2..4 selection -> NOTE
        bra.s   nds_midi_indexed
nds_midi_skip:
        subil   #3,%d0
nds_midi_indexed:
        addl    %d2,%d0
        tstl    %d0
        bpl.s   4f
        clrl    %d0
4:      cmpi.l  #26,%d0
        ble.s   5f
        moveq   #26,%d0
5:      cmpi.l  #3,%d0
        bcs.s   nds_midi_store
        addil   #3,%d0
nds_midi_store:
        movel   %d0,%a0@
        bra.w   nds_midi_load
nds_midi_audio:
        addl    %d2,%d0
        tstl    %d0
        bpl.s   nds0
        clrl    %d0
nds0:    movel   %a0,-(%sp)
        movel   %d0,-(%sp)
        movel   ef_focus,%d0
        movel   %d0,ef_trk
        bsr.w   ef_dest_max
        movel   %d0,%d3
        movel   (%sp)+,%d0
        movel   (%sp)+,%a0
        cmpl    %d3,%d0
        ble.s   nds1
        movel   %d3,%d0
nds1:
        moveq   #DEST_XVOL,%d3
        cmpl    %d3,%d0
        bne.s   nds2
        tstl    %d2
        bmi.s   nds_m
        moveq   #18,%d0
        bra.s   nds2
nds_m:   moveq   #16,%d0
nds2:    movel   %d0,%a0@
nds_midi_load:
        bsr.w   ef_dep_load
        tstl    ef_tone_midi
        bne.s   nds_midi_new
        bsr.w   ef_plk_load
        bra.s   nds_done
nds_midi_new:
        tstl    ef_lane
        beq.s   nds_done
        bsr.w   ef_plk_load
nds_done:
        bra.w   nd_store
nd_depth:
        | cursor 4 = DEPTH
        lea     ef_depth,%a0
        movel   %a0@,%d0
        addl    %d2,%d0
        tstl    %d0
        bpl.s   ndp0
        clrl    %d0
ndp0:    moveq   #127,%d3
        cmpl    %d3,%d0
        ble.s   ndp1
        movel   %d3,%d0
ndp1:    movel   %d0,%a0@
        bsr.w   ef_dep_save
nd_store:
        bsr.w   ef_store_slot
        bra.w   ef_draw
ef_nudge_rts:
        rts

| ---- draw helpers (y up from bottom; TEXT limit = -1) -------------------
| ef_text: d0=x, d1=y, a0=str; a5=surf. Clobbers d0/d1/a0/a1.
ef_text:
        movel   %a0,%sp@-
        pea     -1
        movel   %d1,%sp@-
        movel   %d0,%sp@-
        movel   %a5,%sp@-
        pea     FONT
        jsr     TEXT
        lea     %sp@(24),%sp
        rts

| ef_rtext: right-align a0 at x=d0, row d1. MUST reload a0 after TWIDTH
| (tuner parks the string in a6; we park the pointer in ef_rstr).
ef_rtext:
        movel   %a0,ef_rstr
        movel   %d0,ef_rx
        movel   %d1,ef_ry
        movel   %a0,%sp@-
        pea     -1
        pea     FONT
        jsr     TWIDTH
        lea     %sp@(12),%sp
        movel   ef_rx,%d1
        subl    %d0,%d1
        tstl    %d1
        bpl.s   1f
        moveq   #0,%d1                  | clamp if wider than the box
1:      movel   %d1,%d0
        movel   ef_ry,%d1
        movel   ef_rstr,%a0
        bra.w   ef_text

| ef_ctext: center a0 at cell-centre x=d0, row d1 (midi-follow idiom).
ef_ctext:
        movel   %a0,ef_rstr
        movel   %d0,ef_rx               | centre
        movel   %d1,ef_ry
        movel   %a0,%sp@-
        pea     -1
        pea     FONT
        jsr     TWIDTH
        lea     %sp@(12),%sp
        asrl    #1,%d0                  | tw/2
        movel   ef_rx,%d1
        subl    %d0,%d1                 | centre - tw/2
        tstl    %d1
        bpl.s   1f
        moveq   #0,%d1
1:      movel   %d1,%d0
        movel   ef_ry,%d1
        movel   ef_rstr,%a0
        bra.w   ef_text

| ---- draw ---------------------------------------------------------------
|  (icon) PULS   ROT    ·          <- icon mid-gutter; 3x2 right
|         5      0      ·             (solid VLINE left of table)
|         AMP    DPTH  ·
|         VOL    0
|  ------------ floor ---------------
|  [pattern left-biased]      LEN   <- bottom-right after squares
|                              n
ef_draw:
        tstl    ef_win
        beq.w   d9
        bsr.w   ef_follow_ui
        bsr.w   ef_sync_len
        lea     %sp@(-48),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        movel   ef_win,%a2
        lea     %a2@(36),%a5
        movel   %a5,%sp@-
        jsr     CLEAR
        addql   #4,%sp

        bsr.w   ef_draw_pat
        bsr.w   ef_grid
        bsr.w   ef_draw_icon            | mid left gutter
        moveq   #X_TITLE,%d0            | title always SEQ (LANE is C)
        moveq   #Y_TITLE,%d1
        lea     T_TITLE,%a0
        bsr.w   ef_text

        | Page affordance sits in the logo panel's top-right corner.
        tstl    ef_page_no
        beq.s   d_page1
        lea     T_PAGE2,%a0
        bra.s   d_page
d_page1:
        bsr.w   ef_pitch_selected
        tstl    %d0
        beq.s   d_page_done
        lea     T_PAGE1,%a0
d_page: moveq   #X_PAGE_R,%d0
        moveq   #Y_TITLE,%d1
        bsr.w   ef_rtext
d_page_done:

        | Window bottom-right, past the pattern squares: LEN / n.
        moveq   #X_LEN_R,%d0
        moveq   #Y_LEN_LAB,%d1
        lea     L_LEN,%a0
        bsr.w   ef_rtext
        movel   ef_steps,-(%sp)
        pea     VFMT
        pea     ef_buf
        jsr     SPRINTF
        lea     %sp@(12),%sp
        moveq   #X_LEN_R,%d0
        moveq   #Y_LEN_VAL,%d1
        lea     ef_buf,%a0
        bsr.w   ef_rtext

        tstl    ef_page_no
        bne.w   ef_draw_tonal

        | A=PULSE (focused lane)
        moveq   #X_C0,%d0
        moveq   #Y_LAB0,%d1
        lea     L_PULSES,%a0
        bsr.w   ef_ctext
        tstl    ef_lane
        bne.s   da_p
        movel   ef_pulses,-(%sp)
        bra.s   da_pv
da_p:   movel   ef_ppulses,-(%sp)
da_pv:  pea     VFMT
        pea     ef_buf
        jsr     SPRINTF
        lea     %sp@(12),%sp
        moveq   #X_C0,%d0
        moveq   #Y_VAL0,%d1
        lea     ef_buf,%a0
        bsr.w   ef_ctext

        | B=ROT (focused lane)
        moveq   #X_C1,%d0
        moveq   #Y_LAB0,%d1
        lea     L_ROT,%a0
        bsr.w   ef_ctext
        tstl    ef_lane
        bne.s   db_p
        movel   ef_rot,-(%sp)
        bra.s   db_pv
db_p:   movel   ef_prot,-(%sp)
db_pv:  pea     VFMT
        pea     ef_buf
        jsr     SPRINTF
        lea     %sp@(12),%sp
        moveq   #X_C1,%d0
        moveq   #Y_VAL0,%d1
        lea     ef_buf,%a0
        bsr.w   ef_ctext

        | C=LANE (TRIG / PLCK)
        moveq   #X_C2,%d0
        moveq   #Y_LAB0,%d1
        lea     L_LANE,%a0
        bsr.w   ef_ctext
        lea     L_TRIG,%a0
        tstl    ef_lane
        beq.s   dc_v
        lea     L_PLOCK,%a0
dc_v:   moveq   #X_C2,%d0
        moveq   #Y_VAL0,%d1
        bsr.w   ef_ctext

        | D=DEST: PAGE + PARAM (same rows as DPTH / value).
        moveq   #0,%d2
        moveq   #Y_DEST_V,%d3
        bsr.w   ef_dest_label
        moveq   #X_C0,%d0
        moveq   #Y_DEST_P,%d1
        lea     ef_buf,%a0
        bsr.w   ef_ctext                | PAGE
        lea     ef_buf,%a0
df_skip: tstb   %a0@+
        bne.s   df_skip                 | a0 -> PARAM
        moveq   #X_C0,%d0
        moveq   #Y_DEST_V,%d1
        bsr.w   ef_ctext                | PARAM

        | E=DEPTH (F empty)
        moveq   #X_C1,%d0
        moveq   #Y_LAB1,%d1
        lea     L_DEPTH,%a0
        bsr.w   ef_ctext
        movel   ef_depth,-(%sp)
        pea     VFMT
        pea     ef_buf
        jsr     SPRINTF
        lea     %sp@(12),%sp
        moveq   #X_C1,%d0
        moveq   #Y_DEPTH_V,%d1
        lea     ef_buf,%a0
        bsr.w   ef_ctext                | centered like PULS/ROT

da_midi_done:
        moveq   #1,%d0
        movel   %d0,SCRDIRTY
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(48),%sp
d9:     rts

| Page 2 keeps the rhythm grid and LEN visible, changing only the knob map.
ef_draw_tonal:
        lea     L_SCALE,%a0
        moveq   #0,%d0
        moveq   #0,%d2
        movel   ef_tone_scale,%d2
        lea     ef_scale_names,%a1
        moveal  (%a1,%d2.l*4),%a0
        bsr.w   ef_tonal_cell
        lea     L_ROOT,%a0
        moveq   #1,%d0
        movel   ef_tone_root,%d2
        lea     ef_root_names,%a1
        moveal  (%a1,%d2.l*4),%a0
        bsr.w   ef_tonal_cell
        tstl    MIDI_MODE
        beq.s   edt_phrase
        lea     L_MODE,%a0
        moveq   #2,%d0
        movel   ef_tone_mode,%d2
        tstl    MIDI_MODE
        beq.s   1f
        lea     L_VOIC,%a0
        movel   ef_tone_harm,%d2
        subql   #1,%d2
        lea     ef_harmony_names,%a1
        moveal  (%a1,%d2.l*4),%a0
        bra.s   2f
1:      lea     ef_mode_names,%a1
        moveal  (%a1,%d2.l*4),%a0
2:
        bsr.w   ef_tonal_cell
edt_phrase:
        lea     L_PHRASE,%a0
        moveq   #3,%d0
        movel   ef_tone_phrase,%d2
        lea     ef_phrase_names,%a1
        moveal  (%a1,%d2.l*4),%a0
        bsr.w   ef_tonal_cell
        tstl    MIDI_MODE
        beq.s   edt_jump
        lea     L_CHORD,%a0
        movel   ef_tone_style,%d2
        lsrl    #2,%d2
        lea     ef_chord_names,%a1
        moveal  (%a1,%d2.l*4),%a0
        movel   %a0,ef_tonal_value
        movel   ef_tone_style,%d2
        andil   #3,%d2
        movel   %d2,-(%sp)
        movel   ef_tonal_value,-(%sp)
        pea     VFMT_CHORD
        pea     ef_buf
        jsr     SPRINTF
        lea     %sp@(16),%sp
        lea     ef_buf,%a0
        moveq   #5,%d0
        bsr.w   ef_tonal_cell
edt_jump:
        movel   ef_tone_jump,-(%sp)
        pea     VFMT
        pea     ef_buf
        jsr     SPRINTF
        lea     %sp@(12),%sp
        lea     ef_buf,%a0
        moveq   #4,%d0
        bsr.w   ef_tonal_cell
        bra.w   da_midi_done

| d0=index 0..5, d2=value, a0=value string; label comes from index.
ef_tonal_cell:
        movel   %d0,ef_tonal_index
        movel   %a0,ef_tonal_value
        bra.w   ef_tonal_draw_cell
ef_tonal_draw_cell:
        movel   %d0,%d3
        movel   %d2,%d4
        lea     ef_tonal_labels,%a1
        moveal  (%a1,%d3.l*4),%a0
        cmpi.l  #2,%d3
        bne.s   5f
        tstl    MIDI_MODE
        beq.s   5f
        lea     L_VOIC,%a0
5:
        cmpi.l  #5,%d3
        bne.s   3f
        lea     L_CHORD,%a0
3:
        cmpi.l  #4,%d3
        bne.s   4f
        lea     L_JUMP,%a0
4:
        movel   %a0,ef_tonal_label
        moveq   #Y_LAB0,%d1
        cmpi.l  #3,%d3
        bcs.s   1f
        subi.l  #3,%d3
        moveq   #Y_LAB1,%d1
1:      lea     ef_xcells,%a1
        movel   (%a1,%d3.l*4),%d0
        moveal  ef_tonal_label,%a0
        bsr.w   ef_ctext
        lea     ef_xcells,%a1
        movel   (%a1,%d3.l*4),%d0
        moveq   #Y_VAL0,%d1
        | Recover row from the original index saved for this cell.
        moveq   #Y_VAL0,%d1
        movel   ef_tonal_index,%d3
        cmpi.l  #3,%d3
        bcs.s   2f
        moveq   #Y_DEPTH_V,%d1
2:      moveal  ef_tonal_value,%a0
        bsr.w   ef_ctext
        rts

ef_tonal_nudge:
        tstl    MIDI_MODE
        bne.s   9f
        movel   ef_cursor,%d1
        cmpi.l  #2,%d1
        beq.w   etn_done
        cmpi.l  #5,%d1
        beq.w   etn_done
9:
        movel   %d0,%d2
        movel   ef_cursor,%d1
        lea     ef_tonal_index,%a0
        movel   %d1,%a0@
        moveq   #0,%d0
        cmpl    %d0,%d1
        bne.s   etn_root
        lea     ef_tone_scale,%a0
        moveq   #7,%d3
        bra.s   etn_clamp
etn_root:
        cmpi.l  #1,%d1
        bne.s   etn_mode
        lea     ef_tone_root,%a0
        moveq   #11,%d3
        bra.s   etn_clamp
etn_mode:
        cmpi.l  #2,%d1
        bne.s   etn_phrase
        lea     ef_tone_mode,%a0
        moveq   #1,%d3
        tstl    MIDI_MODE
        beq.s   etn_clamp
        lea     ef_tone_harm,%a0
        moveq   #4,%d3
        bra.s   etn_clamp
etn_phrase:
        cmpi.l  #3,%d1
        bne.s   etn_jump
        lea     ef_tone_phrase,%a0
        moveq   #4,%d3
        bra.s   etn_clamp
etn_jump:
        cmpi.l  #4,%d1
        bne.s   etn_harm
        lea     ef_tone_jump,%a0
        moveq   #127,%d3
        bra.s   etn_clamp
etn_harm:
        cmpi.l  #5,%d1
        bne.s   etn_done
        lea     ef_tone_style,%a0
        moveq   #123,%d3
etn_clamp:
        movel   %a0@,%d0
        addl    %d2,%d0
        tstl    %d0
        bpl.s   1f
        clrl    %d0
1:      cmpl    %d3,%d0
        ble.s   2f
        movel   %d3,%d0
2:      tstl    ef_tone_midi
        beq.s   3f
        cmpi.l  #2,%d1
        bne.s   3f
        tstl    %d0
        bne.s   3f
        moveq   #1,%d0
3:      movel   %d0,%a0@
        bsr.w   ef_tone_save
        moveq   #1,%d0
        movel   %d0,ef_dirty
etn_done:
        bra.w   ef_draw

| ef_grid: 1px top+bottom rim, table edge (VLINE), dotted internal divs +
| mid (HLINE), solid floor above the pattern (RULE).
| No left VLINE - WCREATE/stock already puts the window's left edge; drawing
| another at surface x=0 made a double line with a 1px gap (CX EUCL95 LCD).
| RULE is (surf, x, y, w, h) - w=WINW for true edge-to-edge.
ef_grid:
        lea     -8(%sp),%sp
        movem.l %d2/%a2,(%sp)

        | 1px top rim (Y-up: WINH-1).
        pea     1
        pea     WINW
        pea     WINH-1
        pea     0
        movel   %a5,-(%sp)
        jsr     RULE
        lea     %sp@(20),%sp
        | 1px bottom rim.
        pea     1
        pea     WINW
        pea     0
        pea     0
        movel   %a5,-(%sp)
        jsr     RULE
        lea     %sp@(20),%sp

        | Solid vertical left of PULS (stock EFFECT SETUP left edge).
        pea     1
        pea     Y_GRID1
        pea     Y_GRID0
        pea     X_GRID
        movel   %a5,-(%sp)
        jsr     VLINE
        lea     %sp@(20),%sp

        moveq   #3,%d2                  | two divs + mid
        lea     EF_GRID,%a2
1:      pea     1
        movel   %a2@(12),-(%sp)
        movel   %a2@(8),-(%sp)
        movel   %a2@(4),-(%sp)
        movel   %a2@,-(%sp)
        movel   %a5,-(%sp)
        jsr     HLINE
        lea     %sp@(24),%sp
        lea     16(%a2),%a2
        subql   #1,%d2
        bne.s   1b

        | Floor above pattern squares - edge to edge (w=WINW).
        pea     1
        pea     WINW
        pea     Y_GRID0
        pea     0
        movel   %a5,-(%sp)
        jsr     RULE
        lea     %sp@(20),%sp

        movem.l (%sp),%d2/%a2
        lea     8(%sp),%sp
        rts

| ef_fmt_track: "Tn" (focus 1-based) into ef_buf.
ef_fmt_track:
        moveq   #0,%d0
        movel   ef_focus,%d0
        andil   #7,%d0
        addql   #1,%d0
        movel   %d0,-(%sp)
        pea     T_TRK
        pea     ef_buf
        jsr     SPRINTF
        lea     %sp@(12),%sp
        rts

| ef_fmt_len: pattern length into ef_buf.
ef_fmt_len:
        movel   ef_steps,-(%sp)
        pea     VFMT
        pea     ef_buf
        jsr     SPRINTF
        lea     %sp@(12),%sp
        rts

| Track key T1..T8 while open: forward every edge to stock (press and
| release share 0x40040250), so double-tap QUICK ASSIGN, FUNC+TRACK
| mute, TRACK+PLAY/STOP/BANK keep working. CUE held -> CUE overlay
| TRACK handler (cue-a-track) and mark ef_cue_chord. On press also
| retarget SEQ (ef_pending + SEL_TRACK + draw); poking CUR/UI alone
| left the sequencer grid on the pre-open track (EUCL13).
ef_trkkey:
        lea     -44(%sp),%sp            | ColdFire: no predec movem
        movem.l %d2-%d7/%a2-%a6,(%sp)
        movel   44+4(%sp),%d2           | keycode
        movel   44+8(%sp),%d3           | event
        | CUE_HELD byte: our ef_cue press sets it (stock CUE modifier).
        tstb    CUE_HELD
        beq.s   tk_base
        moveq   #1,%d0
        movel   %d0,ef_cue_chord        | bare CUE release: skip random
        clrl    ef_from_cue             | never randomize after a cue chord
        movel   %d3,-(%sp)
        movel   %d2,-(%sp)
        jsr     CUE_TRK
        addql   #8,%sp
        bra.s   tk_after
tk_base:
        movel   %d3,-(%sp)
        movel   %d2,-(%sp)
        jsr     TRK_STOCK
        addql   #8,%sp
tk_after:
        moveq   #1,%d0
        cmpl    %d3,%d0
        bne.s   tk_done                 | release: stock only
        | Stock stole the UI (QUICK ASSIGN, audio editor, …): do not
        | SEL_TRACK / redraw SEQ over it.
        movel   UI_WINDOW,%d0
        cmpl    ef_win,%d0
        bne.s   tk_done
        movel   %d2,%d0
        andil   #0xff,%d0
        subi.l  #0x10,%d0               | T1..T8 -> 0..7
        bmi.s   tk_done
        moveq   #7,%d1
        cmpl    %d1,%d0
        bhi.s   tk_done
        movel   %d0,ef_pending
        movel   %d0,-(%sp)
        jsr     SEL_TRACK
        addql   #4,%sp
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     44(%sp),%sp
        bra.w   ef_draw
tk_done:
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     44(%sp),%sp
        rts


| Slot zero is NOTE on MIDI, but INAB on THRU. Use the audio descriptor's
| actual parameter name for both the page hint and the RIGHT handler.
| Keeps d2/d3, clobbers d0/d1/a0/a1 like ef_dest_label.
ef_pitch_selected:
        tstl    ef_dest
        bne.s   eps_no
        tstl    MIDI_MODE
        bne.s   eps_yes
        bsr.w   ef_dest_label
        lea     ef_buf,%a0
eps_page:
        tstb    %a0@+
        bne.s   eps_page
        movel   %a0@,%d0
        cmpil   #0x50544348,%d0         | PTCH
        bne.s   eps_no
eps_yes:
        moveq   #1,%d0
        rts
eps_no:
        moveq   #0,%d0
        rts

| ef_dest_label: LFO SETUP PMTR style PAGE\0PARAM\0 into ef_buf
| (two lines: AMP/VOL, SRC/PTCH, SRC/CAR…). Via ef_dest_name; static
| tables only on miss. Keeps d2/d3 (draw row / y) - EUCL9/10.
ef_dest_label:
        movel   %d2,-(%sp)
        movel   %d3,-(%sp)
        movel   ef_focus,%d0            | open window's track (not HELD)
        andil   #7,%d0
        movel   %d0,ef_trk
        bsr.w   ef_dest_name
        lea     ef_buf,%a0
        moveq   #0,%d0
        moveb   (%a0),%d0
        cmpi.b  #0x2d,%d0               | '-' = miss -> static PAGE PARAM
        bne.s   dl_ok
        bsr.w   ef_dest_static
dl_ok:  movel   (%sp)+,%d3
        movel   (%sp)+,%d2
        rts

| Static fallback: PAGE + PARAM (Flex/AMP/LFO tokens) when resolver misses.
| CX 30..34 use ef_cxpriv_tab (same tokens as LFO PMTR).
ef_dest_static:
        movel   ef_dest,%d0
        tstl    %d0
        bpl.s   ds0
        clrl    %d0
ds0:    moveq   #DEST_LAST,%d1
        cmpl    %d1,%d0
        ble.s   ds1
        moveq   #DEST_CXLAST,%d1
        cmpl    %d1,%d0
        ble.s   ds_cx
        moveq   #DEST_LAST,%d0
        bra.s   ds1
ds_cx:  subi.l  #30,%d0
        lea     ef_buf,%a1
        moveq   #0x53,%d1               | 'S'
        moveb   %d1,(%a1)+
        moveq   #0x52,%d1               | 'R'
        moveb   %d1,(%a1)+
        moveq   #0x43,%d1               | 'C'
        moveb   %d1,(%a1)+
        clrb    (%a1)+                  | SRC\0 then PARAM
        lea     ef_cxpriv_tab,%a0
        movel   %d0,%d1
        addl    %d1,%d1
        addl    %d0,%d1
        addl    %d1,%d1                 | *6
        addal   %d1,%a0
        moveq   #5,%d0
ds_cxc: moveb   (%a0)+,%d1
        moveb   %d1,(%a1)+
        beq.s   ds_rts
        subql   #1,%d0
        bpl.s   ds_cxc
        clrb    (%a1)
ds_rts: rts
ds1:    moveq   #0,%d2                  | page = flat / 6
        movel   %d0,%d3                 | slot = flat % 6
        moveq   #6,%d1
ds_div: cmpl    %d1,%d3
        bcs.s   ds_pg
        subl    %d1,%d3
        addql   #1,%d2
        bra.s   ds_div
ds_pg:  lea     ef_buf,%a1
        lea     ef_dpage_tab,%a0        | 4-byte page title
        movel   %d2,%d0
        lsll    #2,%d0
        addal   %d0,%a0
        moveq   #3,%d0
ds_p:   moveb   %a0@+,%d1
        beq.s   ds_sp
        moveb   %d1,%a1@+
        subql   #1,%d0
        bpl.s   ds_p
ds_sp:  clrb    %a1@+                   | PAGE\0 then PARAM
        lea     ef_dparam_tab,%a0       | 6-byte param; page*36 + slot*6
        movel   %d2,%d0
        lsll    #5,%d0
        movel   %d2,%d1
        lsll    #2,%d1
        addl    %d1,%d0
        movel   %d3,%d1
        addl    %d1,%d1
        addl    %d3,%d1
        addl    %d1,%d1
        addl    %d1,%d0
        addal   %d0,%a0
        moveq   #5,%d0
ds_c:   moveb   %a0@+,%d1
        moveb   %d1,%a1@+
        beq.s   ds_done
        subql   #1,%d0
        bpl.s   ds_c
        clrb    %a1@
ds_done: rts

| ef_draw_icon: 29×29 Euclid mark (ring + E(3,16) on-dot triangle), centred
| in the left gutter. a5 = surf. Uses stock BLIT.
ef_draw_icon:
        pea     ICON_Y
        pea     ICON_X
        movel   %a5,%sp@-
        pea     ef_icon_bmp
        jsr     BLIT
        lea     %sp@(16),%sp
        rts

| ef_box1: solid rect mode 1. a1=x0 a2=y0 a3=x1 d3=y1 a5=surf.
| BOX clobbers a0/a1/a3 (and d0/d1); a2 and d2-d7 preserved.
ef_box1:
        pea     1
        movel   %d3,%sp@-
        movel   %a3,%sp@-
        movel   %a2,%sp@-
        movel   %a1,%sp@-
        movel   %a5,%sp@-
        jsr     BOX
        lea     %sp@(24),%sp
        rts

| ef_draw_pat: 4×16 hollow/filled squares for steps 0..n-1 (n≤64).
| Origin top-left (row 0 under the floor). Centered. Extra PAT_SEP
| after every 4 cols. Last row = n mod 16 (16 when n is a multiple of
| 16). Hit = filled; miss = four edges.
| Coords in ef_rx/ry/px1/py1 (BOX clobbers a0/a1/a3).
| a5 = surf. d4=k d5=n d6=rot across the loop.
ef_draw_pat:
        movel   ef_steps,%d5
        moveq   #1,%d0
        cmpl    %d0,%d5
        bge.s   p1
        moveq   #1,%d5
p1:     moveq   #64,%d0
        cmpl    %d0,%d5
        ble.s   p2
        moveq   #64,%d5
p2:     movel   ef_pulses,%d4
        tstl    %d4
        bpl.s   p3
        clrl    %d4
p3:     cmpl    %d5,%d4
        ble.s   p4
        movel   %d5,%d4
p4:     movel   ef_rot,%d6
        tstl    %d6
        bpl.s   p5
        clrl    %d6
p5:     cmpl    %d5,%d6
        bcs.s   p5x
        clrl    %d6
p5x:    | Focused lane: TRIG keeps ef_pulses/rot; PLOCK swaps to ppulses/prot.
        tstl    ef_lane
        beq.s   p6
        movel   ef_ppulses,%d4
        tstl    %d4
        bpl.s   p6a
        clrl    %d4
p6a:    cmpl    %d5,%d4
        ble.s   p6b
        movel   %d5,%d4
p6b:    movel   ef_prot,%d6
        tstl    %d6
        bpl.s   p6c
        clrl    %d6
p6c:    cmpl    %d5,%d6
        bcs.s   p6
        clrl    %d6
p6:     moveq   #0,%d2                  | step i
ploop:
        movel   %d2,-(%sp)              | park i
        tstl    ef_lane
        bne.s   pl_ph
        bsr.w   ef_hit                  | d7 = trig hit
        bra.s   pl_got
pl_ph:  bsr.w   ef_phit                 | d7 = plock hit
pl_got:
        movel   (%sp),%d2
        | col = i & 15, row = i >> 4
        movel   %d2,%d1
        andil   #PAT_COLS-1,%d1         | col
        movel   %d2,%d0
        lsr.l   #4,%d0                  | row
        | x0 = X_PAT + col*STRIDE + (col/4)*SEP
        movel   %d1,%d3
        lsr.l   #2,%d3                  | col/4
        mulu.w  #PAT_SEP,%d3
        mulu.w  #PAT_STRIDE,%d1
        addl    %d3,%d1
        addil   #X_PAT,%d1              | x0
        | y0 = Y_PATT - PAT_SQ - row*STRIDE  (row 0 at top)
        mulu.w  #PAT_STRIDE,%d0
        addql   #PAT_SQ,%d0
        movel   #Y_PATT,%d3
        subl    %d0,%d3                 | y0
        movel   %d1,ef_rx
        movel   %d3,ef_ry
        moveq   #PAT_SQ-1,%d0
        addl    %d1,%d0
        movel   %d0,ef_px1
        moveq   #PAT_SQ-1,%d0
        addl    %d3,%d0
        movel   %d0,ef_py1
        tstl    %d7
        beq.s   phollow
        movel   ef_rx,%a1
        movel   ef_ry,%a2
        movel   ef_px1,%a3
        movel   ef_py1,%d3
        bsr.w   ef_box1
        bra.s   pnext
phollow:
        movel   ef_rx,%a1
        movel   ef_ry,%a2
        movel   ef_px1,%a3
        movel   ef_ry,%d3
        bsr.w   ef_box1
        movel   ef_rx,%a1
        movel   ef_py1,%a2
        movel   ef_px1,%a3
        movel   ef_py1,%d3
        bsr.w   ef_box1
        movel   ef_rx,%a1
        movel   ef_ry,%a2
        movel   ef_rx,%a3
        movel   ef_py1,%d3
        bsr.w   ef_box1
        movel   ef_px1,%a1
        movel   ef_ry,%a2
        movel   ef_px1,%a3
        movel   ef_py1,%d3
        bsr.w   ef_box1
pnext:  movel   (%sp)+,%d2
        addql   #1,%d2
        cmpl    %d5,%d2
        bcs.w   ploop
        rts

| ---- fill: Euclidean trigs + optional DEST locks on ef_targets ----------
| Each target uses its own bank slot (PULSE/ROT/DEST/DEPTH/free mask).
ef_fill:
        bsr.w   ef_store_slot           | commit focused edits first
        movel   ef_focus,%d0            | restore UI after per-track loads
        movel   %d0,ef_fill_focus
        movel   ef_targets,%d0
        movel   %d0,ef_fill_tgts
        lea     %sp@(-36),%sp
        movem.l %d2-%d7/%a2-%a4,%sp@
        movel   ef_targets,%d7
        beq.w   fout
        moveal  DBPTR,%a2
        moveq   #0,%d2
        moveb   UI_PTN,%d2
        movel   #PTN_STR,%d0
        mulu.l  %d0,%d2
        addal   %d2,%a2                 | a2 = pattern base in blob

        moveq   #0,%d2                  | track
tloop:  btst    %d2,%d7
        jbeq    tnext                   | ColdFire: no Bcc.W; jcc picks size
        movel   %d7,-(%sp)              | park; load/sync clobber d0/d1/a0/a1
        movel   %d2,-(%sp)
        movel   %a2,-(%sp)
        movel   %d2,%d0
        bsr.w   ef_load_slot            | working := bank[track]
        moveq   #1,%d1                  | STEPS from this track when PER TRACK
        lsll    %d2,%d1
        movel   %d1,ef_targets
        bsr.w   ef_sync_len
        movel   (%sp)+,%a2
        movel   (%sp)+,%d2
        movel   (%sp)+,%d7
        movel   ef_steps,%d5
        moveq   #1,%d0
        cmpl    %d0,%d5
        bge.s   1f
        moveq   #1,%d5
1:      moveq   #64,%d0
        cmpl    %d0,%d5
        ble.s   2f
        moveq   #64,%d5
2:      movel   ef_pulses,%d4
        tstl    %d4
        bpl.s   3f
        clrl    %d4
3:      cmpl    %d5,%d4
        ble.s   4f
        movel   %d5,%d4
4:      movel   ef_rot,%d6
        tstl    %d6
        bpl.s   5f
        clrl    %d6
5:      cmpl    %d5,%d6
        bcs.s   6f
        clrl    %d6
6:      movel   %d2,%d0
        movel   #TRK_STR,%d1
        mulu.l  %d1,%d0
        lea     %a2@(0,%d0:l),%a3       | a3 = TRAC
        movel   %d2,ef_trk              | track for PTCH encoding (synth vs sample)
        movel   %d5,-(%sp)
        movel   %d4,-(%sp)
        movel   %d6,-(%sp)
        movel   %a3,-(%sp)
        tstl    ef_tone_midi
        bne.w   ef_midi_fill
        bsr.w   ef_write_mask
        lea     %sp@(16),%sp
        bsr.w   ef_dep_save             | applied depth for this track×DEST
        bsr.w   ef_plk_save             | applied plock rhythm for DEST
        | battery mirror: masks 0..2 + DEST lock bytes on rewritten steps
        moveq   #0,%d0
        moveb   UI_PTN,%d0
        movel   #PTN_STR,%d1
        mulu.l  %d1,%d0
        movel   %d2,%d1
        movel   #TRK_STR,%d3
        mulu.l  %d3,%d1
        addl    %d1,%d0
        addil   #MIRROR,%d0
        moveal  %d0,%a4
        moveq   #23,%d0                 | masks 0..2 (trig + trigless)
mcopy:  moveb   %a3@(0,%d0:l),%d1
        moveb   %d1,%a4@(0,%d0:l)
        subql   #1,%d0
        bpl.s   mcopy
        | mirror page-1 DEST lock bytes (CX SETUP uses DRAM bank, not locks)
        movel   ef_dest,%d0
        moveq   #DEST_LAST,%d1
        cmpl    %d1,%d0
        bhi.w   tnext
        moveq   #0,%d0
mvloop: cmpl    %d5,%d0
        jbcc    tnext
        movel   %d0,%d1
        lsll    #5,%d1
        addil   #LOCK0,%d1
        addl    ef_dest,%d1
        moveb   %a3@(0,%d1:l),%d3
        moveb   %d3,%a4@(0,%d1:l)
        addql   #1,%d0
        bra.s   mvloop
ef_midi_fill:
        | MIDI TRIG and PLOCK use the track's note mask / 32-byte lock table.
        lea     %sp@(16),%sp
        tstl    ef_lane
        bne.s   ef_midi_plk_fill
        bsr.w   ef_write_midi_mask
        bsr.w   ef_write_midi_locks
        bsr.w   ef_dep_save
        bra.w   tnext
ef_midi_plk_fill:
        bsr.w   ef_write_midi_plocks
        bra.w   tnext
tnext:  addql   #1,%d2
        moveq   #8,%d0
        cmpl    %d0,%d2
        jbcs    tloop

        moveal  DBPTR,%a0
        addal   #DIRTY_OFF,%a0
        moveq   #1,%d0
        movel   %d0,%a0@
        moveal  #DIRTY_G,%a0
        movel   %d0,%a0@
        jsr     NOTIFY
        | Rebuild 0x46c7d48c / 0x46c7d2e4 from #1 lock bytes. Without this,
        | clearing the last plock leaves the step yellow (bitmap stale) and
        | a emptied trigless can stay lit on the row. Stock erase path does
        | the same refresh after writing 0xff.
        jsr     LOCK_COLL
        | After NOTIFY: drop CLEAR TRACK TRIGS undo. Filling rewrote trigs,
        | so a prior clear's undo arm must not steal the next stock
        | FUNC+PLAY (toast UNDO TRACK TRIGS, trigs stay). EUCL24 only
        | cleared CLR_UNDO bits - also kill clipboard kind 0xa / CLIP_KEY.
        bsr.w   ef_drop_clr_undo
fout:   movem.l %sp@,%d2-%d7/%a2-%a4
        lea     %sp@(36),%sp
        movel   ef_fill_tgts,%d0
        movel   %d0,ef_targets
        movel   ef_fill_focus,%d0
        bsr.w   ef_load_slot            | restore focused params for the UI
        rts

| Rewrite the selected MIDI track's note-trig mask for steps 0..n-1.
| d2=track 0..7, ef_steps / ef_pulses / ef_rot are the active recipe.
| Keep steps outside the pattern length and every MIDI lock byte intact.
| The stock MIDI sequencer reads the bit for step 0 at pattern+0x48d7.
ef_write_midi_mask:
        lea     -32(%sp),%sp
        movem.l %d2-%d7/%a0-%a1,(%sp)
        movel   %d2,ef_trk
        moveal  DBPTR,%a0
        moveq   #0,%d0
        moveb   UI_PTN,%d0
        movel   #PTN_STR,%d1
        mulu.l  %d1,%d0
        adda.l  %d0,%a0
        move.l  %d2,%d0
        movel   #0x8b0,%d1
        mulu.l  %d1,%d0
        adda.l  %d0,%a0
        lea     %a0@(0x48d0),%a0       | MIDI track record
        moveq   #0,%d2
        movel   ef_steps,%d5
        movel   ef_pulses,%d4
        movel   ef_rot,%d6
wmid_loop:
        cmpl    %d5,%d2
        bcc.s   wmid_done
        movel   %a0,-(%sp)              | free-mask reader uses a0
        bsr.w   ef_hit
        moveal  (%sp)+,%a0              | restore MIDI record before writes
        movel   %d2,%d1
        lsr.l   #3,%d1
        eori.l  #7,%d1
        moveq   #1,%d0
        movel   %d2,%d3
        andil   #7,%d3
        lsl.l   %d3,%d0
        | The first step is the low bit of byte +7; subsequent groups
        | walk backward through the 8-byte mask.
        moveq   #0,%d3
        moveb   %a0@(0,%d1:l),%d3
        tstl    %d7
        beq.s   wmid_clear
        or.l    %d0,%d3
        bra.w   wmid_store
wmid_clear:
        not.l   %d0
        and.l   %d0,%d3
wmid_store:
        moveb   %d3,%a0@(0,%d1:l)
        addql   #1,%d2
        bra.s   wmid_loop
wmid_done:
        | Battery mirror: copy the eight-byte MIDI note-trig mask.
        moveq   #0,%d0
        moveb   UI_PTN,%d0
        movel   #PTN_STR,%d1
        mulu.l  %d1,%d0
        addil   #MIRROR+0x48d0,%d0
        | ef_trk still holds the MIDI track index; add its record stride.
        movel   ef_trk,%d1
        movel   #0x8b0,%d3
        mulu.l  %d3,%d1
        addl    %d1,%d0
        moveal  %d0,%a1
        moveq   #7,%d0
wmid_mirror:
        moveb   %a0@(0,%d0:l),%d1
        moveb   %d1,%a1@(0,%d0:l)
        subql   #1,%d0
        bpl.s   wmid_mirror
        movem.l (%sp),%d2-%d7/%a0-%a1
        lea     32(%sp),%sp
        rts

| MIDI TRIG lane: selected page-1 flat follows the same Euclidean hits as
| the note mask. Misses clear only this flat; all other MIDI locks survive.
ef_write_midi_locks:
        lea     -28(%sp),%sp
        movem.l %d2-%d7,(%sp)
        clrl    ef_jump_index
        clrl    ef_rand_valid
        moveq   #0,%d2
        movel   ef_steps,%d5
        movel   ef_pulses,%d4
        movel   ef_rot,%d6
wmil_loop:
        cmpl    %d5,%d2
        bcc.s   wmil_done
        bsr.w   ef_hit
        tstl    %d7
        beq.s   wmil_clear
        bsr.w   ef_write_dest
        bra.s   wmil_next
wmil_clear:
        moveq   #-1,%d0
        bsr.w   ef_midi_lock_store
        tstl    ef_dest
        bne.s   wmil_next
        bsr.w   ef_midi_clear_chord_locks
wmil_next:
        addql   #1,%d2
        bra.s   wmil_loop
wmil_done:
        movem.l (%sp),%d2-%d7
        lea     28(%sp),%sp
        rts

| MIDI PLOCK lane: selected MIDI locks on its own rhythm; note trigs untouched.
ef_write_midi_plocks:
        lea     -28(%sp),%sp
        movem.l %d2-%d7,(%sp)
        clrl    ef_jump_index
        clrl    ef_rand_valid
        moveq   #0,%d2
        movel   ef_steps,%d5
wmpl_loop:
        cmpl    %d5,%d2
        bcc.s   wmpl_done
        bsr.w   ef_phit
        tstl    %d7
        beq.s   wmpl_clear
        bsr.w   ef_write_dest
        bra.s   wmpl_next
wmpl_clear:
        moveq   #-1,%d0
        bsr.w   ef_midi_lock_store
        tstl    ef_dest
        bne.s   wmpl_next
        bsr.w   ef_midi_clear_chord_locks
wmpl_next:
        addql   #1,%d2
        bra.s   wmpl_loop
wmpl_done:
        movem.l (%sp),%d2-%d7
        lea     28(%sp),%sp
        rts

| d0=value, d2=step, ef_trk=track, ef_dest=flat. Store to bank and CS1.
ef_midi_lock_store:
        movel   %d0,-(%sp)
        moveq   #0,%d1
        moveb   UI_PTN,%d1
        movel   #PTN_STR,%d0
        mulu.l  %d0,%d1
        addil   #0x4900,%d1
        movel   ef_trk,%d3
        movel   #0x8b0,%d0
        mulu.l  %d0,%d3
        addl    %d3,%d1
        movel   %d2,%d3
        lsll    #5,%d3
        addl    %d3,%d1
        addl    ef_dest,%d1
        moveal  DBPTR,%a0
        adda.l  %d1,%a0
        movel   (%sp)+,%d0
        moveb   %d0,%a0@
        moveal  #MIRROR,%a0
        adda.l  %d1,%a0
        moveb   %d0,%a0@
        rts

| ef_drop_clr_undo: disarm CLEAR TRACK TRIGS undo (bitmask + kind 0xa).
| Clobbers d0/d1. Safe any time; stock mark is 0x40029560 / kind tag 0xa.
ef_drop_clr_undo:
        clrb    CLR_UNDO
        movel   CLIP_KIND,%d0
        moveq   #KIND_CTRG,%d1
        cmpl    %d1,%d0
        bne.s   1f
        clrl    CLIP_KIND
        clrl    CLIP_KEY
1:      rts

| ef_write_mask(trac, rot, k, n) -- stack: TRIG rot/k/n. DEST/DEPTH:
|   LANE=TRIG: rewrite mask 0 from TRIG; locks on TRIG hits; clear this
|   DEST on !thit (other DEST locks kept - promote to TL if the note
|   drops); sync that DEST's plock recipe to the TRIG rhythm after loop.
|   LANE=PLOCK: leave sample trigs alone (read mask 0 as thit only);
|   independent plock rhythm; plock∩¬trig sets TL; miss clears this DEST
|   on every step (incl. note trigs / PTCH) so a PLCK YES overwrites
|   TRIG-baked locks for that DEST. Other DEST trigless stay.
|   Clear TL on note trigs. Leaves n..63 alone. Other DEST locks stack.
ef_write_mask:
        lea     -28(%sp),%sp
        movem.l %d2-%d7/%a2,(%sp)
        clrl    ef_jump_index
        clrl    ef_rand_valid
        moveal  32(%sp),%a2             | 28 + 4 return = 32
        movel   36(%sp),%d6             | TRIG rot
        movel   40(%sp),%d4             | TRIG k
        movel   44(%sp),%d5             | n
wm0:    | Free/pmask bake only after CUE (ef_from_cue); else PULSE/ROT.
        tstl    ef_from_cue
        bne.s   wm0b
        clrl    ef_free
        clrl    ef_pfree
wm0b:   | PLOCK-lane active iff LANE=PLOCK and PULSE>0.
        | PULSE 0 always clears (ignore stale pfree / empty CUE mask).
        clrl    ef_plock_on
        tstl    ef_lane
        beq.s   wm_off                  | TRIG lane: DEST follows thit
        tstl    ef_ppulses
        beq.s   wm_off                  | PULSE 0: clear path, not hits
wm_on:  moveq   #1,%d0
        movel   %d0,ef_plock_on
wm_off: moveq   #0,%d2
1:      cmpl    %d5,%d2
        bcc.w   9f
        tstl    ef_lane
        bne.w   wm_keep_trig            | PLCK: do not rewrite sample trigs
        | --- LANE=TRIG: rewrite mask 0 from TRIG rhythm ---
        bsr.w   ef_bit_addr
        moveb   %a0@,%d1
        move.l  %d0,%d3
        not.l   %d3
        and.l   %d3,%d1
        moveb   %d1,%a0@
        movel   %d4,-(%sp)              | park TRIG k/rot across hit
        movel   %d6,-(%sp)
        bsr.w   ef_hit                  | d7 = thit (uses d4/d6/ef_free)
        movel   %d7,ef_thit
        tstl    %d7
        beq.s   wm_t0
        bsr.w   ef_bit_addr
        moveb   %a0@,%d1
        or.l    %d0,%d1
        moveb   %d1,%a0@
wm_t0:  movel   (%sp)+,%d6
        movel   (%sp)+,%d4
        | --- DEST locks on the same trigs ---
        tstl    ef_thit
        beq.w   wm_dest_clr             | reshape this DEST to the trig set
        bsr.w   ef_write_dest
        bsr.w   ef_tl_clr               | note owns the step
        bra.w   8f
wm_keep_trig:
        | Existing sample trig (if any) -> thit; mask 0 untouched.
        bsr.w   ef_bit_addr
        moveb   %a0@,%d1
        and.l   %d0,%d1
        sne     %d1
        andil   #1,%d1
        movel   %d1,ef_thit
wm_plock:
        tstl    ef_plock_on
        beq.w   wm_dest_clr             | PLOCK PULSE 0: clear this DEST
        movel   %d4,-(%sp)
        movel   %d6,-(%sp)
        bsr.w   ef_phit                 | d7 = phit
        movel   (%sp)+,%d6
        movel   (%sp)+,%d4
        tstl    %d7
        beq.w   wm_dest_clr             | miss: drop TRIG-baked DEST too
        bsr.w   ef_write_dest
        tstl    ef_thit
        bne.s   wm_clr_tl
        tstl    ef_depth
        beq.w   wm_mtl                  | DEST cleared; drop orphan TL
        bsr.w   ef_tl_set               | trigless stack
        bra.s   8f
wm_clr_tl:
        bsr.w   ef_tl_clr
        bra.s   8f
| PULSE 0 / miss: clear this DEST (shared with DEPTH 0 / ed_clear).
wm_dest_clr:
        bsr.w   ef_clear_dest_step
wm_mtl:
8:      bsr.w   ef_tl_reconcile
        addql   #1,%d2
        bra.w   1b
9:      | LANE=TRIG: copy TRIG rhythm into this DEST's plock recipe.
        tstl    ef_lane
        bne.s   wm_done
        movel   ef_pulses,%d0
        movel   %d0,ef_ppulses
        movel   ef_rot,%d0
        movel   %d0,ef_prot
        movel   ef_free,%d0
        movel   %d0,ef_pfree
        lea     ef_mask,%a0
        lea     ef_pmask,%a1
        moveq   #7,%d0
wm_cp:  moveb   %a0@(0,%d0:l),%d1
        moveb   %d1,%a1@(0,%d0:l)
        subql   #1,%d0
        bpl.s   wm_cp
        bsr.w   ef_plk_save
wm_done:
        movem.l (%sp),%d2-%d7/%a2
        lea     28(%sp),%sp
        rts

| ef_clear_dest_step: d2=step, a2=trac. Clear ef_dest lock (page-1 0xff
| or CX bit). Same bytes DEPTH 0 / PULSE 0 / miss write. Clobbers d0/d1/a0;
| ef_cx_clear saves/restores d2.
ef_clear_dest_step:
        movel   ef_dest,%d0
        moveq   #DEST_LAST,%d1
        cmpl    %d1,%d0
        bhi.w   ef_cx_clear
        movel   %d2,%d1
        lsll    #5,%d1
        addil   #LOCK0,%d1
        addl    ef_dest,%d1
        moveq   #-1,%d0
        moveb   %d0,%a2@(0,%d1:l)
        rts

| Trigless-lock bit (+0x10). d2=step, a2=trac. Clobbers d0/d1/a0.
ef_tl_bit_addr:
        movel   %d2,%d1
        lsr.l   #3,%d1
        moveq   #7,%d0
        subl    %d1,%d0
        addil   #MASK_TL,%d0
        lea     %a2@(0,%d0:l),%a0
        movel   %d2,%d1
        andil   #7,%d1
        moveq   #1,%d0
        lsll    %d1,%d0
        rts
ef_tl_set:
        bsr.w   ef_tl_bit_addr
        moveb   %a0@,%d1
        or.l    %d0,%d1
        moveb   %d1,%a0@
        rts
ef_tl_clr:
        bsr.w   ef_tl_bit_addr
        moveb   %a0@,%d1
        move.l  %d0,%d3
        not.l   %d3
        and.l   %d3,%d1
        moveb   %d1,%a0@
        rts

| ef_tl_reconcile: d2=step, a2=trac. Note trig -> clear TL. Else if any
| #1 lock (32 flats) or CX bit remains -> SET TL so other DEST stacks
| survive a TRIG reshape that drops the note (else locks go orphan /
| invisible). No locks left -> clear TL. Clobbers d0/d1/a0.
ef_tl_reconcile:
        tstl    ef_thit
        bne.s   tr_clr
        movel   %d2,%d1
        lsll    #5,%d1
        addil   #LOCK0,%d1
        lea     %a2@(0,%d1:l),%a0
        moveq   #31,%d1                 | flats 0..31 (DEST_LAST is 29 only)
        moveq   #-1,%d0
tr_scan:
        cmp.b   %a0@,%d0
        bne.s   tr_keep                 | another DEST still locked -> TL
        addql   #1,%a0
        subql   #1,%d1
        bpl.s   tr_scan
        | CX SETUP bits for this step (if any) also keep TL.
        movel   %d2,%d0
        moveq   #63,%d1
        cmpl    %d1,%d0
        bhi.s   tr_clr
        movel   ef_trk,%d1
        andil   #7,%d1
        lsll    #6,%d1                  | trk * CX_STEPS
        addl    %d2,%d1
        lea     ef_cx_bits,%a0
        tst.b   %a0@(0,%d1:l)
        bne.s   tr_keep
tr_clr: bsr.w   ef_tl_clr
        rts
tr_keep:
        bsr.w   ef_tl_set
        rts

| ef_write_dest: on hit step d2 / trac a2. DEPTH=0 -> clear. DEST=PTCH ->
| in-scale. DEST=AMP VOL -> unipolar below Part VOL (never louder).
| CX SETUP 30..34 -> ef_cx_bank. Else page-1 lock uniform [Part±DEPTH].
ef_write_dest:
        movel   ef_depth,%d3
        tstl    %d3
        beq.w   ed_clear
        tstl    MIDI_MODE
        bne.w   ed_generic
        movel   ef_dest,%d0
        tstl    %d0
        beq.w   ef_write_ptch           | PTCH special
        moveq   #LOCK_VOL,%d1
        cmpl    %d1,%d0
        beq.w   ef_write_vol            | velocity: ceiling = AMP VOL
        | generic: uniform in [Part-DEPTH .. Part+DEPTH] clamped 0..127
        | (remul - not muls/divs (r-64)*D/64, which collapsed to 2 values).
ed_generic:
        tstl    MIDI_MODE
        beq.s   ed_generic_base
        tstl    ef_dest
        beq.w   ef_write_midi_pitch
ed_generic_base:
        bsr.w   ef_part_flat            | d0 = Part value for ef_dest
        movel   %d0,%d3                 | base
        movel   ef_depth,%d1
        movel   %d3,%d0
        subl    %d1,%d0                 | base - depth
        bpl.s   ed_lo
        clrl    %d0
ed_lo:  movel   %d0,-(%sp)              | lo
        movel   %d3,%d0
        addl    %d1,%d0                 | base + depth
        moveq   #127,%d1
        cmpl    %d1,%d0
        ble.s   ed_hi
        movel   %d1,%d0
ed_hi:  movel   (%sp),%d1               | lo
        subl    %d1,%d0                 | hi - lo
        addql   #1,%d0                  | span
        movel   %d0,-(%sp)
        bsr.w   ef_rng
        move.l  %d0,%d3                 | dividend
        movel   (%sp)+,%d1              | span
        remul   %d1,%d0,%d3             | d0 = rng % span
        movel   (%sp)+,%d1              | lo
        addl    %d1,%d0                 | lock
        bra.w   ed_store
ed_clear:
        tstl    MIDI_MODE
        bne.s   ed_midi_clear
        bra.w   ef_clear_dest_step      | same clear as PULSE 0 / miss
ed_midi_clear:
        moveq   #-1,%d0
        bra.w   ed_store
ed_store:
        tstl    MIDI_MODE
        bne.s   ed_midi_store
        movel   ef_dest,%d1
        moveq   #DEST_LAST,%d3
        cmpl    %d3,%d1
        bhi.w   ef_cx_store             | CX SETUP: bank, not a p-lock
        movel   %d2,%d1
        lsll    #5,%d1
        addil   #LOCK0,%d1
        addl    ef_dest,%d1
        moveb   %d0,%a2@(0,%d1:l)
        rts
ed_midi_store:
        bsr.w   ef_midi_lock_store
        rts

| ef_write_vol: DEST=AMP VOL. Ceiling is Part AMP VOL - locks never go
| louder. drop = r*DEPTH/127 (r 0..127) -> lock = max(0, Part - drop).
| DEPTH=0 already cleared above. Clobbers d0/d1/d3.
ef_write_vol:
        bsr.w   ef_part_flat            | d0 = Part AMP VOL
        movel   %d0,-(%sp)
        bsr.w   ef_rng
        andil   #0x7f,%d0               | r = 0..127
        movel   ef_depth,%d1
        mulu.l  %d1,%d0                 | r * DEPTH
        moveq   #127,%d1
        divul   %d1,%d0                 | drop = r*DEPTH/127 (0..DEPTH)
        movel   (%sp)+,%d1              | Part VOL (ceiling)
        subl    %d0,%d1
        bpl.s   ev1
        clrl    %d1
ev1:    movel   %d1,%d0
        bra.w   ed_store

| ef_write_ptch: on hit step d2 / trac a2 when DEST=PTCH.
| JUMP spaces phrase-ranked pitches on audio and MIDI. DEPTH=0 -> clear PTCH.
| No quantizer / SCALE OFF -> lock = Part PLAYBACK
| PTCH (base; every hit the same). SCALE ON: rad =
| max(1, max_rad*DEPTH/127); pick uniform among delta in [-rad..+rad]
| whose absolute PC (ROOT + base_st + delta) mod 12 is in SEQ's scale;
| lock encodes base_st+delta. Center is Part PLAYBACK PTCH (overall
| knob), not unison - same byte stock unlocks fall back to.
| FM/SY/CX: raw=64+st (max_rad=PIT_RAD). Sample: raw=64+5·st (PIT_SAMP).
| Clamp raw to 0..127 before store.
| Caller keeps n in d5 and rot in d6 - park across the pick.
| ef_tone_mask returns the selected SEQ-owned scale as a 12-bit mask.
ef_tone_mask:
        moveq   #0,%d1
        movel   ef_tone_scale,%d1
        andil   #7,%d1
        lsll    #1,%d1
        lea     ef_scale_masks,%a0
        moveq   #0,%d0
        move.w  (%a0,%d1.l),%d0
        andil   #0x0fff,%d0
        rts

| d0=1-based scale degree. Return its semitone offset above the root.
| Missing degrees (for pentatonic scales) resolve to the next octave.
ef_degree_interval:
        movel   %d0,%d4
        bsr.w   ef_tone_mask
        movel   %d0,%d7
        moveq   #0,%d3
        moveq   #0,%d1
1:      moveq   #12,%d0
        cmpl    %d0,%d1
        bcc.s   4f
        btst    %d1,%d7
        beq.s   2f
        addql   #1,%d3
        cmpl    %d4,%d3
        beq.s   3f
2:      addql   #1,%d1
        bra.s   1b
3:      movel   %d1,%d0
        rts
4:      moveq   #12,%d0
        rts

| d3=available pitch count, d2=step. Return a phrase rank 0..count-1.
| Phrase 0 random, 1 rises, 2 falls, 3 reflects, 4 repeats a short triangle.
ef_pitch_rank:
        movel   ef_tone_phrase,%d1
        tstl    %d1
        beq.w   epr_random
        cmpi.l  #1,%d1
        beq.w   epr_up
        cmpi.l  #2,%d1
        beq.w   epr_down
        cmpi.l  #3,%d1
        beq.w   epr_reflect
        cmpi.l  #4,%d1
        beq.w   epr_triangle
        movel   %d2,%d1
        movel   %d3,%d5
        remul   %d5,%d0,%d1
        rts
epr_up:
        moveq   #0,%d1
        bra.w   epr_linear
epr_down:
        moveq   #1,%d1                 | DOWN starts at the Part pitch
        bra.w   epr_linear
epr_linear:
        movel   %d4,-(%sp)
        movel   %d5,-(%sp)
        movel   %d1,%d4                | preserve UP/DOWN direction
        movel   %d2,%d1
        movel   %d3,%d5
        remul   %d5,%d0,%d1            | wrap transformed ordinal by candidate count
        movel   ef_tone_anchor,%d1
        tstl    %d4                    | UP adds, DOWN subtracts
        beq.s   epr_wrap_up
        subl    %d0,%d1
        bra.s   epr_wrap_result
epr_wrap_up:
        addl    %d0,%d1
epr_wrap_result:
        tstl    %d1
        bpl.s   epr_wrap_low
        addl    %d3,%d1
epr_wrap_low:
        cmpl    %d3,%d1
        bcs.s   epr_wrap_ready
        subl    %d3,%d1
epr_wrap_ready:
        movel   %d1,%d0
        movel   (%sp)+,%d5
        movel   (%sp)+,%d4
        rts
epr_reflect:
        movel   %d3,%d1
        lsll    #1,%d1
        subql   #2,%d1
        tstl    %d1
        bne.s   1f
        moveq   #1,%d1
1:      movel   %d2,%d5
        remul   %d1,%d0,%d5
        cmpl    %d3,%d0
        bcs.s   2f
        movel   %d1,%d5
        subl    %d0,%d5
        movel   %d5,%d0
2:      rts
epr_triangle:
        movel   %d3,%d1
        lsll    #1,%d1
        movel   %d2,%d5
        remul   %d1,%d0,%d5
        cmpl    %d3,%d0
        bcs.s   3f
        movel   %d3,%d1
        lsll    #1,%d1
        subql   #1,%d1
        subl    %d0,%d1
        movel   %d1,%d0
3:      rts
epr_random:
        cmpi.l  #1,%d3
        bls.s   epr_rand_single
        tstl    ef_rand_valid
        bne.s   epr_rand_next
        bsr.w   ef_rng
        movel   %d0,%d1
        movel   %d3,%d5
        remul   %d5,%d0,%d1
        movel   %d0,ef_rand_rank
        moveq   #1,%d1
        movel   %d1,ef_rand_valid
        rts
epr_rand_next:
        | Pick a random direction; JUMP sets the scale-degree distance.
        bsr.w   ef_rng
        movel   %d0,%d1
        movel   %d3,%d5
        subql   #1,%d5
        lsrl    #1,%d5
        movel   ef_tone_jump,%d0
        mulu.w  %d5,%d0
        moveq   #127,%d5
        divu.l  %d5,%d0
        addql   #1,%d0
        tstl    %d1
        bpl.s   epr_rand_up
        negl    %d0
epr_rand_up:
        addl    ef_rand_rank,%d0
        tstl    %d0
        bpl.s   epr_rand_low
        addl    %d3,%d0
epr_rand_low:
        cmpl    %d3,%d0
        bcs.s   epr_rand_store
        subl    %d3,%d0
epr_rand_store:
        movel   %d0,ef_rand_rank
        rts
epr_rand_single:
        clrl    %d0
        rts

| MIDI-only phrase spacing. JUMP=0 advances one phrase step per note.
| Higher values multiply the generated-note ordinal by a coprime stride,
| preserving phrase contours while selecting wider notes from the DEPTH set.
| d2=generated-note ordinal, d3=candidate count; return transformed ordinal in d2.
ef_pitch_step:
        movel   ef_tone_phrase,%d1
        tstl    %d1
        beq.s   eps_done                | RAND applies JUMP in its random walk
        tstl    ef_tone_jump
        beq.s   eps_done
        cmpi.l  #2,%d3
        bls.s   eps_done
        movel   %d4,-(%sp)
        movel   %d5,-(%sp)
        movel   %d3,%d1
        subql   #1,%d1
        lsrl    #1,%d1
        movel   ef_tone_jump,%d0
        mulu.w  %d1,%d0
        moveq   #127,%d1
        divu.l  %d1,%d0
        tstl    %d0
        beq.s   eps_restore
        addql   #1,%d0                 | candidate phrase-step multiplier
        movel   %d2,-(%sp)             | preserve note ordinal for multiplication
eps_period:
        movel   ef_tone_phrase,%d4
        cmpi.l  #3,%d4
        beq.s   eps_alt_period
        cmpi.l  #4,%d4
        beq.s   eps_tri_period
        movel   %d3,%d1                 | UP/DOWN cycle over candidate count
        bra.s   eps_gcd_start
eps_alt_period:
        movel   %d3,%d1
        subql   #1,%d1
        lsll    #1,%d1                  | ALT reflects over 2*(count-1)
        bra.s   eps_gcd_start
eps_tri_period:
        movel   %d3,%d1
        lsll    #1,%d1                  | TRI repeats over 2*count
eps_gcd_start:
        movel   %d1,%d4
        movel   %d0,%d5
eps_gcd:
        remul   %d5,%d2,%d4            | d2 = period % candidate
        tstl    %d2
        beq.s   eps_gcd_end
        movel   %d5,%d4
        movel   %d2,%d5
        bra.s   eps_gcd
eps_gcd_end:
        cmpi.l  #1,%d5
        beq.s   eps_stride
        addql   #1,%d0                 | next wider coprime multiplier
        bra.s   eps_gcd_start
eps_stride:
        movel   (%sp)+,%d2
        mulu.w  %d0,%d2
eps_restore:
        movel   (%sp)+,%d5
        movel   (%sp)+,%d4
eps_done:
        rts

| d0=absolute MIDI note. Return nearest note in SEQ scale/root, ties down.
ef_snap_note:
        movel   %d0,%d6
        bsr.w   ef_tone_mask
        movel   %d0,%d7
        moveq   #0,%d5
1:      movel   %d6,%d4
        subl    %d5,%d4
        bmi.s   2f
        movel   %d4,%d1
3:      moveq   #12,%d0
        cmpl    %d0,%d1
        bcs.s   4f
        subl    %d0,%d1
        bra.s   3b
4:      subl    ef_tone_root,%d1
5:      tstl    %d1
        bpl.s   6f
        addil   #12,%d1
        bra.s   5b
6:      cmpi.l  #12,%d1
        bcs.s   7f
        subil   #12,%d1
        bra.s   6b
7:      btst    %d1,%d7
        bne.w   9f                      | lower candidate wins ties
2:      movel   %d6,%d4
        addl    %d5,%d4
        cmpi.l  #127,%d4
        bhi.s   8f
        movel   %d4,%d1
10:     cmpi.l  #12,%d1
        bcs.s   11f
        subi.l  #12,%d1
        bra.s   10b
11:     subl    ef_tone_root,%d1
12:     tstl    %d1
        bpl.s   13f
        addil   #12,%d1
        bra.s   12b
13:     cmpi.l  #12,%d1
        bcs.s   14f
        subil   #12,%d1
        bra.s   13b
14:     btst    %d1,%d7
        bne.s   9f
8:      addql   #1,%d5
        cmpi.l  #12,%d5
        bcs.w   1b
        movel   %d6,%d4                 | defensive fallback (all scales nonempty)
9:      movel   %d4,%d0
        rts

| MIDI MELO generation: phrase-ranked in-scale notes within the DEPTH span.
| DEPTH 0 is handled by ef_write_dest before this entry.
ef_write_midi_pitch:
        movel   %d2,-(%sp)
        lea     -16(%sp),%sp
        movem.l %d4-%d7,%sp@            | preserve the fill loop state
        addql   #1,ef_jump_index
        movel   %d2,ef_tonal_index      | rank helper reuses d2/d5
        bsr.w   ef_part_flat
        movel   %d0,%d5                 | Part NOTE
        movel   %d5,ef_tonal_value      | preserve Part NOTE across rank helper
        movel   ef_tone_mode,%d1
        tstl    ef_tone_midi
        beq.s   18f
        clrl    %d1
18:
        cmpi.l  #2,%d1
        beq.w   ewmp_arp
        | Melody phrases rank the in-scale notes inside the Part-centered range.
        movel   ef_depth,%d0
        mulu.w  #48,%d0                 | DEPTH 127 spans four octaves either side
        moveq   #127,%d1
        divu.l  %d1,%d0
        movel   %d0,%d6                 | pitch radius
        movel   %d5,%d4
        subl    %d6,%d4
        movel   %d4,%d6
        bpl.s   1f
        clrl    %d6
1:      movel   %d5,%d4
        movel   ef_depth,%d0
        mulu.w  #48,%d0
        moveq   #127,%d1
        divu.l  %d1,%d0
        addl    %d0,%d4
        cmpi.l  #127,%d4
        ble.s   2f
        moveq   #127,%d4
2:      bsr.w   ef_tone_mask
        movel   %d0,%d7
        clrl    %d3
        movel   %d6,%d0
3:      movel   %d0,%d1
        subl    ef_tone_root,%d1
4:      tstl    %d1
        bpl.s   5f
        addil   #12,%d1
        bra.s   4b
5:      cmpi.l  #12,%d1
        bcs.s   6f
        subi.l  #12,%d1
        bra.s   5b
6:      btst    %d1,%d7
        beq.s   7f
        addql   #1,%d3
7:      cmp.l   %d4,%d0
        beq.s   8f
        addql   #1,%d0
        bra.s   3b
8:      tstl    %d3
        beq.w   12f
        clrl    ef_tone_anchor
        movel   %d6,%d0                 | count scale notes below the Part NOTE
        movel   ef_tonal_value,%d2
1:      cmpl    %d2,%d0
        bge.s   6f
        movel   %d0,%d1
        subl    ef_tone_root,%d1
2:      tstl    %d1
        bpl.s   3f
        addil   #12,%d1
        bra.s   2b
3:      cmpi.l  #12,%d1
        bcs.s   4f
        subi.l  #12,%d1
        bra.s   3b
4:      btst    %d1,%d7
        beq.s   5f
        addql   #1,ef_tone_anchor
5:      cmpl    %d4,%d0
        beq.s   6f
        addql   #1,%d0
        bra.s   1b
6:      movel   ef_tone_anchor,%d0
        cmpl    %d3,%d0
        bcs.s   7f
        movel   %d3,%d0
        subql   #1,%d0
        movel   %d0,ef_tone_anchor
7:
        movel   ef_jump_index,%d2
        subql   #1,%d2
        bsr.w   ef_pitch_step
        bsr.w   ef_pitch_rank
        movel   %d0,%d1                 | selected in-scale rank
        movel   %d6,%d0
9:      movel   %d0,%d2
        subl    ef_tone_root,%d2
10:     tstl    %d2
        bpl.s   11f
        addil   #12,%d2
        bra.s   10b
11:     cmpi.l  #12,%d2
        bcs.s   13f
        subi.l  #12,%d2
        bra.s   11b
13:     btst    %d2,%d7
        beq.s   14f
        tstl    %d1
        beq.s   15f
        subql   #1,%d1
14:     addql   #1,%d0
        bra.s   9b
15:     bra.s   16f
12:     movel   %d5,%d0
        bsr.w   ef_snap_note
16:     bra.w   17f
ewmp_arp:
        movel   %d5,ef_tonal_value      | ef_pitch_rank uses d5 as scratch
        clrl    ef_tone_anchor
        moveq   #0,%d0
        movel   ef_tone_scale,%d0
        lea     ef_scale_counts,%a0
        moveq   #0,%d1
        move.b  (%a0,%d0.l),%d1
        movel   %d1,%d3
        movel   ef_jump_index,%d2
        subql   #1,%d2
        bsr.w   ef_pitch_step
        bsr.w   ef_pitch_rank
        addql   #1,%d0
        bsr.w   ef_degree_interval
        movel   ef_tonal_value,%d1
        addl    %d1,%d0
        tstl    %d0
        bpl.s   3f
        clrl    %d0
3:      cmpi.l  #127,%d0
        ble.s   4f
        moveq   #127,%d0
4:      bsr.w   ef_snap_note
17:     movem.l %sp@,%d4-%d7
        lea     16(%sp),%sp
        movel   (%sp)+,%d2
        tstl    ef_tone_midi
        beq.w   ed_store
        tstl    ef_dest
        bne.w   ed_store
        tstl    %d0
        bmi.w   ed_store
        movel   %d2,%d1
        bsr.w   ef_midi_chord_locks
        bra.w   ed_store

| MIDI VOIC writes the selected FM SYNTH chord's extra notes to NOT2..NOT4.
ef_midi_chord_locks:
        movel   %d0,-(%sp)              | generated root
        movel   %d4,-(%sp)              | preserve the TRIG PULSE count
        movel   %d7,-(%sp)              | preserve the hit flag
        movel   ef_dest,-(%sp)
        movel   %d2,-(%sp)              | stable step copy for nested stores
        movel   ef_tone_style,%d0
        lsrl    #2,%d0
        addql   #1,%d0                  | FM shape indices 1..31; 0 is no chord
        lsll    #2,%d0
        lea     ef_chord_shapes,%a0
        adda.l  %d0,%a0
        lea     -36(%sp),%sp
        movem.l %d2-%d5/%a2,%sp@
        lea     %sp@(20),%a2            | four working semitone notes
        moveq   #0,%d2
1:      moveq   #0,%d3
        moveb   %a0@(0,%d2:l),%d3
        movel   %d3,%a2@(0,%d2:l*4)
        addql   #1,%d2
        cmpi.l  #4,%d2
        bcs.s   1b
        | Sort the four shape notes into pitch order.
        moveq   #3,%d2
2:      moveq   #0,%d3
3:      movel   %a2@(0,%d3:l*4),%d4
        movel   %a2@(4,%d3:l*4),%d5
        cmpl    %d5,%d4
        ble.s   4f
        movel   %d5,%a2@(0,%d3:l*4)
        movel   %d4,%a2@(4,%d3:l*4)
4:      addql   #1,%d3
        cmp.l   %d2,%d3
        bcs.s   3b
        subql   #1,%d2
        bne.s   2b
        | Choose the inversion's bass by indexing distinct pitch classes.
        moveq   #0,%d3
        moveq   #0,%d5
        movel   ef_tone_style,%d4
        andil   #3,%d4
5:      movel   %a2@(0,%d3:l*4),%d0
        andil   #0xff,%d0
        tstl    %d3
        beq.s   6f
        movel   %a2@(-4,%d3:l*4),%d1
        andil   #0xff,%d1
        cmp.l   %d1,%d0
        beq.s   7f
6:      cmpl    %d4,%d5
        beq.s   8f
        addql   #1,%d5
7:      addql   #1,%d3
        cmpi.l  #4,%d3
        bcs.s   5b
        clrl    %d3                    | inversion wraps over distinct tones
        bra.s   5b
8:      movel   %d0,%d5                | bass semitone offset
        | Rotate lower notes up octaves, then sort again.
        moveq   #0,%d3
9:      movel   %a2@(0,%d3:l*4),%d0
        andil   #0xff,%d0
        cmpl    %d5,%d0
        bge.s   11f
10:     addil   #12,%d0
        cmpl    %d5,%d0
        ble.s   10b
        movel   %d0,%a2@(0,%d3:l*4)
11:     addql   #1,%d3
        cmpi.l  #4,%d3
        bcs.s   9b
        moveq   #3,%d2
12:     moveq   #0,%d3
13:     movel   %a2@(0,%d3:l*4),%d4
        movel   %a2@(4,%d3:l*4),%d0
        cmpl    %d0,%d4
        ble.s   14f
        movel   %d0,%a2@(0,%d3:l*4)
        movel   %d4,%a2@(4,%d3:l*4)
14:     addql   #1,%d3
        cmp.l   %d2,%d3
        bcs.s   13b
        subql   #1,%d2
        bne.s   12b
        | Shift the generated NOTE lock to the inversion bass.
        movel   52(%sp),%d0
        addl    %d5,%d0
        movel   %d0,52(%sp)
        clrl    ef_dest
        movel   36(%sp),%d2
        bsr.w   ef_midi_lock_store
        | Store the first VOIC-1 ascending intervals to NOT2..NOT4.
        moveq   #3,%d4
15:     movel   %d4,ef_dest
        movel   %d4,%d0
        subql   #2,%d0                  | NOTE2 ordinal (1), NOTE3 (2), NOTE4 (3)
        moveq   #0,%d1
        movel   ef_tone_harm,%d1
        cmpl    %d1,%d0
        bcc.s   16f
        movel   %a2@(0,%d0:l*4),%d1
        andil   #0xff,%d1
        subl    %d5,%d1
        addi.l  #64,%d1
        movel   %d1,%d0
        bra.s   17f
16:     moveq   #-1,%d0              | unused voice: empty lock, not -64
17:     movel   36(%sp),%d2
        bsr.w   ef_midi_lock_store
        addql   #1,%d4
        cmpi.l  #6,%d4
        bcs.s   15b
        movem.l %sp@,%d2-%d5/%a2
        lea     36(%sp),%sp
        addql   #4,%sp
        movel   (%sp)+,ef_dest
        movel   (%sp)+,%d7
        movel   (%sp)+,%d4
        movel   (%sp)+,%d0
        rts

ef_midi_clear_chord_locks:
        movel   %d0,-(%sp)              | caller chooses 0 (hit) or -1 (miss)
        movel   %d4,-(%sp)              | preserve the TRIG PULSE count
        movel   ef_dest,-(%sp)
        moveq   #3,%d4
1:      movel   %d4,ef_dest
        movel   8(%sp),%d0
        bsr.w   ef_midi_lock_store
        addql   #1,%d4
        cmpi.l  #6,%d4
        bcs.s   1b
        movel   (%sp)+,ef_dest
        movel   (%sp)+,%d4
        movel   (%sp)+,%d0
        rts


ef_write_ptch:
        movel   ef_depth,%d3            | 0..127
        tstl    %d3
        beq.w   ep_clear
        movel   %d2,-(%sp)
        movel   %d3,-(%sp)
        movel   %d4,-(%sp)
        movel   %d5,-(%sp)
        movel   %d6,-(%sp)
        movel   %d7,-(%sp)
        bsr.w   ef_tone_mask            | SEQ scale mask; ROOT applied below
        movel   (%sp)+,%d7
        movel   (%sp)+,%d6
        movel   (%sp)+,%d5
        movel   (%sp)+,%d4
        movel   (%sp)+,%d3
        movel   (%sp)+,%d2
        movel   %d2,-(%sp)              | park step
        movel   %d5,-(%sp)              | park n
        movel   %d6,-(%sp)              | park rot
        movel   %d4,-(%sp)              | park pulses
        movel   %d0,%d7                 | mask
        bsr.w   ef_is_synth
        moveq   #PIT_RAD,%d4            | max_rad
        tstl    %d0
        bne.s   1f
        moveq   #PIT_SAMP,%d4
1:      movel   %d0,-(%sp)              | park is_synth
        bsr.w   ef_part_ptch            | d0 = Part PTCH raw
        movel   (%sp),%d1               | is_synth (still parked)
        tstl    %d1
        bne.s   ep_dsy
        subi.l  #64,%d0                 | sample: raw offset from unison
        moveq   #5,%d1
        movel   %d0,-(%sp)              | DIVS.L returns quotient only on ColdFire
        divs.l  %d1,%d0
        movel   %d0,%d2
        muls.l  %d1,%d2
        movel   (%sp)+,%d1
        subl    %d2,%d1                 | signed remainder = offset - quotient*5
        tstl    %d1
        beq.s   ep_dst
        tstl    %d1
        bpl.s   ep_sround_pos
        negl    %d1
        cmpi.l  #3,%d1
        blt.s   ep_dst
        subql   #1,%d0                 | nearest semitone below
        bra.s   ep_dst
ep_sround_pos:
        cmpi.l  #3,%d1
        blt.s   ep_dst
        addql   #1,%d0                 | nearest semitone above
        bra.s   ep_dst
ep_dsy: subi.l  #64,%d0                 | synth: st = raw-64
ep_dst:
        movel   %d0,-(%sp)              | park base_st
        | DEPTH sets the pitch radius up to the machine's full range.
        movel   %d4,%d0
        mulu.w  %d3,%d0
        moveq   #127,%d1
        divu.l  %d1,%d0
        tstl    %d0
        bne.s   2f
        moveq   #1,%d0
2:      movel   %d0,%d4                 | d4 = rad
        movel   ef_tone_root,%d0
        negl    %d0
        movel   %d0,%d6                 | d6 = -ROOT
        | count delta where (base_st+delta-ROOT)%12 is in scale mask
        moveq   #0,%d3
        move.l  %d4,%d1
        negl    %d1                     | d1 = delta = -rad
        clrl    ef_tone_anchor
ep_cnt: move.l  %d1,%d0
        addl    (%sp),%d0               | + base_st
        movel   %d0,%d2                 | absolute candidate semitone
        addl    %d6,%d0                 | - ROOT
ep_cm:  tstl    %d0
        bpl.s   ep_cp
        addil   #12,%d0
        bra.s   ep_cm
ep_cp:  moveq   #12,%d5
        cmpl    %d5,%d0
        bcs.s   ep_ck
        subl    %d5,%d0
        bra.s   ep_cp
ep_ck:  btst    %d0,%d7
        beq.s   ep_cn
        addql   #1,%d3
        cmpl    (%sp),%d2
        bge.s   ep_cn
        addql   #1,ef_tone_anchor
ep_cn:  addql   #1,%d1
        move.l  %d4,%d0
        addql   #1,%d0                  | rad+1
        cmpl    %d0,%d1
        blt.w   ep_cnt
        tstl    %d3
        beq.w   ep_clear_rad
        movel   ef_tone_anchor,%d0
        cmpl    %d3,%d0
        bcs.s   ep_anchor_ready
        movel   %d3,%d0
        subql   #1,%d0
        movel   %d0,ef_tone_anchor
ep_anchor_ready:
        movel   ef_jump_index,%d2
        bsr.w   ef_pitch_step
        addql   #1,ef_jump_index
        bsr.w   ef_pitch_rank
        move.l  %d0,%d3
        move.l  %d4,%d1
        negl    %d1                     | delta = -rad
        moveq   #0,%d5
ep_pk:  move.l  %d4,%d0
        addql   #1,%d0
        cmpl    %d0,%d1
        bge.w   ep_clear_rad
        move.l  %d1,%d0
        addl    (%sp),%d0               | base_st
        addl    %d6,%d0                 | - ROOT
ep_pm:  tstl    %d0
        bpl.s   ep_pp
        addil   #12,%d0
        bra.s   ep_pm
ep_pp:  moveq   #12,%d2
        cmpl    %d2,%d0
        bcs.s   ep_pq
        subl    %d2,%d0
        bra.s   ep_pp
ep_pq:  btst    %d0,%d7
        beq.s   ep_ps
        cmpl    %d3,%d5
        beq.s   ep_got
        addql   #1,%d5
ep_ps:  addql   #1,%d1
        bra.s   ep_pk
ep_got: | d1 = delta; abs st = base_st + delta
        move.l  %d1,%d3
        movel   (%sp)+,%d0              | base_st
        addl    %d0,%d3                 | abs st
        movel   (%sp)+,%d0              | is_synth
        tstl    %d0
        beq.s   ep_samp
        moveq   #64,%d0
        addl    %d3,%d0                 | synth: 64+st
        bra.s   ep_clamp
ep_samp: move.l  %d3,%d0
        moveq   #5,%d1
        muls.l  %d1,%d0
        addi.l  #64,%d0                 | sample: 64+5·st
ep_clamp: tstl    %d0
        bpl.s   ep_chi
        moveq   #0,%d0
ep_chi: moveq   #127,%d1
        cmpl    %d1,%d0
        ble.s   ep_ok
        moveq   #127,%d0
ep_ok:  movel   (%sp)+,%d4              | pulses
        movel   (%sp)+,%d6              | rot
        movel   (%sp)+,%d5              | n
        movel   (%sp)+,%d2              | step
        bra.s   ep_store
ep_clear_rad:
        movel   (%sp)+,%d0              | drop base_st
        movel   (%sp)+,%d0              | drop is_synth
        movel   (%sp)+,%d4
        movel   (%sp)+,%d6
        movel   (%sp)+,%d5
        movel   (%sp)+,%d2
        moveq   #-1,%d0
        bra.s   ep_store
ep_clear:
        moveq   #-1,%d0
ep_store:
        movel   %d2,%d1
        lsll    #5,%d1
        addil   #LOCK0+LOCK_PTCH,%d1
        moveb   %d0,%a2@(0,%d1:l)
        rts

| ef_part_flat: d0 := Part value for ef_dest on ef_trk.
| 0..5 PLAYBACK p1; 6..29 LFO/AMP/FX1/FX2 p1; 30..34 PLAYBACK SETUP
| (CAR MOD SYMM FDBK PWM - DEC skipped). Clobbers d0/d1/a0/a1.
ef_part_flat:
        tstl    MIDI_MODE
        bne.w   ef_midi_part_flat
        movel   ef_dest,%d0
        moveq   #DEST_LAST,%d1
        cmpl    %d1,%d0
        bhi.w   ef_part_setup           | CX CAR..PWM
        moveq   #6,%d1
        cmpl    %d1,%d0
        bcs.w   ef_part_play_slot       | PLAYBACK slot = flat
        subl    %d1,%d0                 | flat-6
        movel   %d0,-(%sp)
        moveal  DBPTR,%a0
        moveq   #0,%d0
        moveb   UI_BANK,%d0
        move.l  #PART_STR,%d1
        muls.l  %d1,%d0
        addal   %d0,%a0                 | Part
        addal   #PAGE1_OFF,%a0
        move.l  ef_trk,%d1
        move.l  %d1,%d0
        lsll    #4,%d0                  | t*16
        lsll    #3,%d1                  | t*8
        addl    %d1,%d0                 | t*24
        addal   %d0,%a0
        movel   (%sp)+,%d1              | flat-6
        moveq   #0,%d0
        moveb   %a0@(0,%d1:l),%d0
        rts

| MIDI Part page-1 value: Part + 0x8f162 + track*32 + flat.
ef_midi_part_flat:
        | MIDI playback has its own per-track Part latch. The UI Part can
        | differ while the sequencer runs, so use STORE's engine context.
        moveq   #0,%d0
        movel   ef_trk,%d0
        jsr     store_part_midi_context
        tstl    %d0
        bpl.s   mpf_context
        jsr     store_part_ui_context  | only if STORE has no MIDI context
mpf_context:
        movel   %d0,%d1                | STORE context for the engine's Part
        moveq   #0,%d0
        movel   ef_trk,%d0
        lsll    #5,%d0
        addil   #MIDI_P1_OFF,%d0
        addl    ef_dest,%d0
        jsr     store_part_read        | honors bank context and live snapshot
        rts

| ef_part_setup: Part PLAYBACK SETUP byte for DEST 30..34 (CAR..PWM).
| Maps 30,31,32,33,34 -> slots 0,1,3,4,5 (DEC skipped). Clobbers d0/d1/a0.
ef_part_setup:
        movel   ef_dest,%d0
        subi.l  #30,%d0
        lea     ef_cx_slots,%a0
        moveq   #0,%d1
        moveb   %a0@(0,%d0:l),%d1       | SETUP slot
        movel   %d1,-(%sp)
        moveal  DBPTR,%a0
        moveq   #0,%d0
        moveb   UI_BANK,%d0
        move.l  #PART_STR,%d1
        muls.l  %d1,%d0
        addal   %d0,%a0
        addal   #PLAY_SETUP,%a0
        move.l  ef_trk,%d1
        move.l  %d1,%d0
        lsll    #5,%d0
        subl    %d1,%d0
        subl    %d1,%d0                 | t*30
        addal   %d0,%a0
        movel   (%sp)+,%d1
        moveq   #0,%d0
        moveb   %a0@(0,%d1:l),%d0
        rts

| ef_part_play_slot: d0 in = PLAYBACK slot 0..5; out = Part raw for ef_trk.
ef_part_play_slot:
        movel   %d0,-(%sp)              | park slot
        bsr.w   ef_part_ptch_base       | a0 = PLAYBACK p1 base (slot 0)
        movel   (%sp)+,%d1
        moveq   #0,%d0
        moveb   %a0@(0,%d1:l),%d0
        rts

| ef_part_ptch: d0 := Part PLAYBACK PTCH raw for ef_trk (slot A).
| Same path as po_part_ptch / qz: Part + 0x8edaa + machine·6 + track·30.
| Clobbers d0/d1/a0/a1.
ef_part_ptch:
        bsr.w   ef_part_ptch_base
        moveq   #0,%d0
        moveb   (%a0),%d0               | PTCH
        rts

| ef_part_ptch_base: a0 := &Part PLAYBACK p1[0] for ef_trk. Clobbers d0/d1.
ef_part_ptch_base:
        moveal  DBPTR,%a0
        moveq   #0,%d0
        moveb   UI_BANK,%d0
        move.l  #PART_STR,%d1
        muls.l  %d1,%d0
        addal   %d0,%a0                 | Part
        movel   %a0,-(%sp)              | park Part
        addal   #MACH_OFF,%a0
        move.l  ef_trk,%d1
        moveq   #0,%d0
        moveb   %a0@(0,%d1:l),%d0       | machine
        addl    %d0,%d0
        move.l  %d0,%d1
        addl    %d0,%d0
        addl    %d0,%d1                 | machine * 6
        moveal  (%sp)+,%a0              | Part
        addal   %d1,%a0
        move.l  ef_trk,%d1
        move.l  %d1,%d0
        lsll    #5,%d0
        subl    %d1,%d0
        subl    %d1,%d0                 | track * 30
        addal   %d0,%a0
        addal   #PLAY_SLOTS,%a0
        rts

| ef_dest_name: LFO PMTR PAGE\0PARAM\0 into ef_buf. Caller sets ef_trk.
| 0..29 via descriptors (+4 title, +0x16 param); PLAYBACK via resolver.
| 30..34 on CX: SRC\0CAR/MOD/… (same tokens as cx_lf_pmtr_fmt).
| "----\0" on miss. Clobbers d0-d3/a0/a1.
ef_dest_name:
        tstl    MIDI_MODE
        bne.w   dn_midi
        movel   ef_dest,%d0
        tstl    %d0
        bpl.s   dn_dc
        clrl    %d0
dn_dc:  moveq   #DEST_CXLAST,%d1
        cmpl    %d1,%d0
        ble.s   dn_cxchk
        movel   %d1,%d0
dn_cxchk:
        moveq   #DEST_LAST,%d1
        cmpl    %d1,%d0
        ble.w   dn_page1
        | 30..34: CX private LFO dests only
        movel   %d0,%d3                 | park dest (move to Dn sets CCR)
        bsr.w   ef_is_cx
        tstl    %d0
        beq.w   dn_miss
        movel   %d3,%d0
        subi.l  #30,%d0                 | 0..4
        lea     ef_buf,%a1
        moveq   #0x53,%d1               | 'S'
        moveb   %d1,(%a1)+
        moveq   #0x52,%d1               | 'R'
        moveb   %d1,(%a1)+
        moveq   #0x43,%d1               | 'C'
        moveb   %d1,(%a1)+
        clrb    (%a1)+                  | SRC\0 then PARAM
        lea     ef_cxpriv_tab,%a0
        movel   %d0,%d1
        addl    %d1,%d1
        addl    %d0,%d1
        addl    %d1,%d1                 | *6
        addal   %d1,%a0
        moveq   #5,%d0
dn_cxc: moveb   (%a0)+,%d1
        moveb   %d1,(%a1)+
        beq.w   dn_done
        subql   #1,%d0
        bpl.s   dn_cxc
        clrb    (%a1)
        rts
dn_page1:
        moveal  DBPTR,%a0
        moveq   #0,%d1
        moveb   UI_BANK,%d1
        move.l  #PART_STR,%d2
        muls.l  %d2,%d1
        addal   %d1,%a0                 | Part
        moveq   #0,%d1
        move.l  %d0,%d3
        moveq   #6,%d2
dn_div: cmpl    %d2,%d3
        bcs.s   dn_pg
        subl    %d2,%d3
        addql   #1,%d1
        bra.s   dn_div                  | d1=page 0..4, d3=slot 0..5
dn_pg:  tstl    %d1
        beq.s   dn_pb
        moveq   #1,%d2
        cmpl    %d2,%d1
        beq.s   dn_lfo
        moveq   #2,%d2
        cmpl    %d2,%d1
        beq.s   dn_amp
        moveq   #3,%d2
        cmpl    %d2,%d1
        beq.s   dn_fx1
        addal   #FX2_OFF,%a0
        move.l  ef_trk,%d0
        moveq   #0,%d2
        moveb   %a0@(0,%d0:l),%d2
        moveq   #63,%d0
        cmpl    %d0,%d2
        bhi.w   dn_miss
        moveal  #FX2_TBL,%a1
        bra.s   dn_idx
dn_fx1: addal   #FX1_OFF,%a0
        move.l  ef_trk,%d0
        moveq   #0,%d2
        moveb   %a0@(0,%d0:l),%d2
        moveq   #63,%d0
        cmpl    %d0,%d2
        bhi.w   dn_miss
        moveal  #FX1_TBL,%a1
        bra.s   dn_idx
dn_amp: moveal  #AMP_DESC,%a0
        bra.s   dn_got
dn_lfo: moveal  #LFO_DESC,%a0
        bra.s   dn_got
dn_pb:  lea     -44(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)   | d3 = slot
        movel   ef_trk,%d0
        clrl    -(%sp)                  | page kind 0 = PLAYBACK
        movel   %d0,-(%sp)              | track
        jsr     LFD_RESOLVER
        addql   #8,%sp
        cmpil   #LFD_MASTER,%d0
        beq.s   dn_flex
        tstl    %d0
        beq.s   dn_flex
        moveal  %d0,%a0
        bra.s   dn_pb_done
dn_flex: moveal  #FLEX_P,%a0
dn_pb_done:
        movel   %a0,%d1
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     44(%sp),%sp
        moveal  %d1,%a0
        bra.s   dn_got
dn_idx: lsll    #2,%d2
        moveal  %a1@(0,%d2:l),%a0
dn_got: tstl    %a0
        beq.w   dn_miss
        | PAGE\0PARAM\0 - title at +4, param at +0x16 + slot*6
        lea     ef_buf,%a1
        movel   %a0,-(%sp)              | keep descriptor base
        addal   #TITLE_OFF,%a0
        moveq   #3,%d0
dn_tit: moveb   (%a0)+,%d1
        beq.s   dn_sp
        moveb   %d1,(%a1)+
        subql   #1,%d0
        bpl.s   dn_tit
dn_sp:  clrb    (%a1)+                  | end PAGE; PARAM follows
        moveal  (%sp)+,%a0
        addal   #NAME_OFF,%a0
        move.l  %d3,%d0
        addl    %d0,%d0
        move.l  %d0,%d1
        addl    %d0,%d0
        addl    %d0,%d1                 | slot * 6
        addal   %d1,%a0
        moveq   #5,%d0
dn_cp:  moveb   (%a0)+,%d1
        moveb   %d1,(%a1)+
        beq.w   dn_done
        subql   #1,%d0
        bpl.s   dn_cp
        clrb    (%a1)
dn_done: rts
dn_miss: lea     ef_buf,%a1
        moveq   #0x2d,%d0
        moveb   %d0,(%a1)+
        moveb   %d0,(%a1)+
        moveb   %d0,(%a1)+
        moveb   %d0,(%a1)+
        clrb    (%a1)+                  | "----\0\0" - empty PARAM line
        clrb    (%a1)
        rts

| MIDI flats map to NOTE, LFO, ARP, CTRL1 and CTRL2 descriptors.
dn_midi:
        moveq   #0,%d3
        movel   ef_dest,%d0
        tstl    %d0
        bpl.s   dnm_clamp
        clrl    %d0
dnm_clamp:
        moveq   #29,%d1
        cmpl    %d1,%d0
        ble.s   dnm_page
        movel   %d1,%d0
dnm_page:
        moveq   #0,%d1
dnm_div:
        moveq   #6,%d2
        cmpl    %d2,%d0
        bcs.s   dnm_desc
        subl    %d2,%d0
        addql   #1,%d1
        bra.s   dnm_div
dnm_desc:
        movel   %d0,%d3               | slot within page
        lsll    #2,%d1
        lea     ef_midi_desc_tab,%a1
        moveal  %a1@(0,%d1:l),%a0
        bra.w   dn_got

| ef_dest_max: d0 := DEST_LAST (29) or DEST_CXLAST (34) when ef_trk is CX.
| Clobbers d0/d1/a0/a1 - callers must park a0 (EUCL19/20).
ef_dest_max:
        tstl    MIDI_MODE
        beq.s   edm_audio
        moveq   #DEST_LAST,%d0
        rts
edm_audio:
        bsr.w   ef_is_cx
        tstl    %d0
        beq.s   edm29
        moveq   #DEST_CXLAST,%d0
        rts
edm29:  moveq   #DEST_LAST,%d0
        rts

| ef_is_cx: d0 := 1 when ef_trk's Part NEIGHBOR sig is "CX",1. Else 0.
ef_is_cx:
        moveal  DBPTR,%a0
        moveq   #0,%d0
        moveb   UI_BANK,%d0
        move.l  #PART_STR,%d1
        muls.l  %d1,%d0
        addal   %d0,%a0
        move.l  ef_trk,%d0
        mulu.w  #30,%d0
        lea     %a0@(0,%d0:l),%a1
        addal   #SIG_OFF,%a1
        moveq   #0,%d0
        moveb   2(%a1),%d0
        subql   #1,%d0
        bne.s   eic_no
        moveq   #0,%d0
        movew   (%a1),%d0
        cmpil   #0x4358,%d0             | "CX"
        bne.s   eic_no
        moveq   #1,%d0
        rts
eic_no: moveq   #0,%d0
        rts

| ef_cx_store: d0 = value, d2 = step. Write ef_cx_bank[trk][step][dest-30]
| and set bit (dest-30) in ef_cx_bits. Steps >= 64 ignored. Other CX slots
| stay set so fills stack. Clobbers d0/d1/d3/a0; restores d2.
ef_cx_store:
        movel   %d2,-(%sp)
        movel   %d0,-(%sp)              | value
        cmpi.l  #CX_STEPS,%d2
        bcc.w   ecs_drop
        movel   ef_dest,%d3
        subi.l  #30,%d3                 | slot 0..4
        movel   ef_trk,%d1
        andil   #7,%d1
        move.l  #CX_STEPS*CX_NSLOT,%d0
        mulu.l  %d0,%d1                 | trk * 320
        movel   4(%sp),%d2              | step
        movel   %d2,%d0
        addl    %d0,%d0
        addl    %d2,%d0
        addl    %d0,%d0
        addl    %d2,%d0                 | step * 5
        addl    %d0,%d1
        addl    %d3,%d1
        lea     ef_cx_bank,%a0
        movel   (%sp),%d0               | value
        moveb   %d0,%a0@(0,%d1:l)
        movel   4(%sp),%d2              | step
        movel   ef_trk,%d1
        andil   #7,%d1
        lsll    #6,%d1                  | trk * 64
        addl    %d2,%d1
        lea     ef_cx_bits,%a0
        moveq   #0,%d0
        moveb   %a0@(0,%d1:l),%d0
        moveq   #1,%d2
        lsll    %d3,%d2                 | 1 << slot
        or.l    %d2,%d0
        moveb   %d0,%a0@(0,%d1:l)
ecs_drop:
        movel   (%sp)+,%d0
        movel   (%sp)+,%d2
        rts

| ef_cx_clear: clear ef_cx_bits bit for ef_dest at step d2 (leave other
| CX slots). Clobbers d0/d1/d3/a0; restores d2.
ef_cx_clear:
        movel   %d2,-(%sp)
        cmpi.l  #CX_STEPS,%d2
        bcc.s   ecc_done
        movel   ef_dest,%d3
        subi.l  #30,%d3
        movel   ef_trk,%d1
        andil   #7,%d1
        lsll    #6,%d1
        addl    %d2,%d1
        lea     ef_cx_bits,%a0
        moveq   #0,%d0
        moveb   %a0@(0,%d1:l),%d0
        bclr    %d3,%d0
        moveb   %d0,%a0@(0,%d1:l)
ecc_done:
        movel   (%sp)+,%d2
        rts

| ef_is_synth: d0 := 1 when ef_trk's Part NEIGHBOR sig is "FM",1 / "SY",1
| / "CX",1 (same semitone encoding as qz_is_synth / qz_fmtrack). Else 0.
| Clobbers d0/d1/a0/a1 only - caller parks what it needs.
ef_is_synth:
        moveal  DBPTR,%a0
        moveq   #0,%d0
        moveb   UI_BANK,%d0
        move.l  #PART_STR,%d1
        muls.l  %d1,%d0
        addal   %d0,%a0                 | Part
        move.l  ef_trk,%d0
        mulu.w  #30,%d0
        lea     %a0@(0,%d0:l),%a1
        addal   #SIG_OFF,%a1            | NEIGHBOR column
        moveq   #0,%d0
        moveb   2(%a1),%d0
        subql   #1,%d0
        bne.s   eis_no                  | not kind 1
        moveq   #0,%d0
        movew   (%a1),%d0
        cmpil   #0x464d,%d0             | "FM"
        beq.s   eis_yes
        cmpil   #0x5359,%d0             | "SY"
        beq.s   eis_yes
        cmpil   #0x4358,%d0             | "CX"
        bne.s   eis_no
eis_yes: moveq   #1,%d0
        rts
eis_no: moveq   #0,%d0
        rts

| d2=step, a2=trac -> a0=&byte, d0=bitmask. Clobbers d0,d1,a0.
ef_bit_addr:
        movel   %d2,%d1
        lsr.l   #3,%d1
        moveq   #7,%d0
        subl    %d1,%d0
        lea     %a2@(0,%d0:l),%a0
        movel   %d2,%d1
        andil   #7,%d1
        moveq   #1,%d0
        lsll    %d1,%d0
        rts

| ef_rhythm_gate: for PULSE/ROT/CUE. d0 := 1 if blocked (baked, not
| unlocked) - stock ARE YOU SURE? dialog. YES unlocks knobs/CUE only;
| NO cancels. Trig rewrite stays on fill YES. Soft-hide SEQ before
| DIALOG (class-1 alone left SEQ on top / dialog behind on HW). Keep
| EF_LAYER; answer restores via ef_mkwin.
ef_rhythm_gate:
        tstl    ef_unlocked
        bne.s   erg_ok
        bsr.w   ef_trk_baked
        tstl    %d0
        beq.s   erg_ok
        tstl    ef_ask
        bne.s   erg_block               | dialog already pending
        tstl    ef_dlg_guard
        bne.s   erg_block
        moveq   #1,%d0
        movel   %d0,ef_ask
        movel   %d0,ef_dlg_guard        | soft-close keeps EF_LAYER
        tstl    ef_win
        beq.s   erg_dlg
        movel   %d0,ef_need_restore
        pea     ef_win
        jsr     WDESTROY                | hide SEQ under ARE YOU SURE?
        addql   #4,%sp
erg_dlg: pea     ef_dlg_answer
        pea     3
        pea     ef_clr_lines
        pea     2                       | two body lines (no YES/NO crib)
        pea     T_CLRTITLE
        jsr     DIALOG
        lea     20(%sp),%sp
erg_block:
        moveq   #1,%d0
        rts
erg_ok: moveq   #0,%d0
        rts

| Dialog YES unlocks editing. Resume the pending MIDI gesture in the
| preview; the next explicit fill YES is the only pattern write.
ef_dlg_answer:
        | Stock calls this as a C callback; preview editors use d2-d7/a2-a6.
        lea     -44(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        movel   48(%sp),%d0
        movel   %d0,-(%sp)
        bsr.w   ef_dlg_apply
        addql   #4,%sp
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     44(%sp),%sp
        rts
ef_dlg_apply:
        clrl    ef_dlg_guard
        movel   4(%sp),%d0
        bne.s   eda_no
        clrl    ef_ask
        moveq   #1,%d0
        movel   %d0,ef_unlocked
        bra.s   eda_rest
eda_no: clrl    ef_ask
        clrl    ef_pending_edit
eda_rest:
        tstl    ef_need_restore
        beq.s   eda_pending
        clrl    ef_need_restore
        bsr.w   ef_mkwin
        tstl    %d0
        beq.s   eda_rts
eda_pending:
        movel   ef_pending_edit,%d0
        clrl    ef_pending_edit
        moveq   #1,%d1
        cmpl    %d1,%d0
        beq.s   eda_nudge
        moveq   #2,%d1
        cmpl    %d1,%d0
        beq.w   ef_cue_random
        bra.w   ef_draw
eda_nudge:
        movel   ef_pending_cursor,%d0
        movel   %d0,ef_cursor
        movel   ef_pending_delta,%d0
        bra.w   ef_nudge
eda_rts: rts

| ef_trk_baked: d0 := 1 if focus track has any sample trig (mask 0) on
| steps 0..STEPS-1, else 0. Caller must ef_sync_len first. Clobbers
| d1-d3/a0-a2.
ef_trk_baked:
        tstl    MIDI_MODE
        bne.w   bkd_midi
        bsr.w   ef_trac_focus           | a2 = TRAC, d3 = n
        moveq   #0,%d2
bkdlp:  cmpl    %d3,%d2
        bcc.s   bkd0
        bsr.w   ef_bit_addr
        moveb   %a0@,%d1
        and.l   %d0,%d1
        bne.s   bkd1
        addql   #1,%d2
        bra.s   bkdlp
bkd0:   moveq   #0,%d0
        rts
bkd1:   moveq   #1,%d0
        rts
bkd_midi:
        | The MIDI note mask has its own record and bit order.
        moveal  DBPTR,%a2
        moveq   #0,%d0
        moveb   UI_PTN,%d0
        movel   #PTN_STR,%d1
        mulu.l  %d1,%d0
        adda.l  %d0,%a2
        movel   ef_focus,%d0
        movel   #0x8b0,%d1
        mulu.l  %d1,%d0
        adda.l  %d0,%a2
        lea     %a2@(0x48d0),%a2
        moveq   #0,%d2
bkd_midi_loop:
        cmpl    ef_steps,%d2
        bcc.s   bkd_midi_no
        movel   %d2,%d1
        andil   #7,%d1
        moveq   #1,%d0
        lsll    %d1,%d0
        movel   %d2,%d1
        lsr.l   #3,%d1
        eori.l  #7,%d1
        moveq   #0,%d3
        moveb   %a2@(0,%d1:l),%d3
        and.l   %d0,%d3
        bne.s   bkd_midi_yes
        addql   #1,%d2
        bra.s   bkd_midi_loop
bkd_midi_no:
        moveq   #0,%d0
        rts
bkd_midi_yes:
        moveq   #1,%d0
        rts

| ef_trac_focus: a2 := focus track's TRAC in the bank blob (DBPTR)  - 
| same base fill YES writes. d3 := STEPS clamped 1..64.
| Caller must ef_sync_len first. Clobbers d0/d1/a2.
ef_trac_focus:
        moveal  DBPTR,%a2
        moveq   #0,%d0
        moveb   UI_PTN,%d0
        movel   #PTN_STR,%d1
        mulu.l  %d1,%d0
        addal   %d0,%a2
        movel   ef_focus,%d0
        movel   #TRK_STR,%d1
        mulu.l  %d1,%d0
        lea     %a2@(0,%d0:l),%a2
        movel   ef_steps,%d3
        moveq   #1,%d0
        cmpl    %d0,%d3
        bge.s   tf1
        moveq   #1,%d3
tf1:    moveq   #64,%d0
        cmpl    %d0,%d3
        ble.s   tf2
        moveq   #64,%d3
tf2:    rts

| ---- FUNC+BANK clear menu (LISTPOP over SEQ; no WDESTROY) ----------------
| MKI: SymbolRef FUNC-held BANK press (ROM table). MKII: BRAIN clones that
| table into DRAM (brain_func_keys), so Detour TRACK TRIG EDIT 0x4007c0d0
| instead. Do NOT also list BANK in EF_KEYS - layer + Detour both fire and
| the clear list toggles open/closed (lag / "does nothing" on unit).

| MKI FUNC+BANK press. SEQ session (win or layer) -> clear LISTPOP;
| else 0x40058a64. Soft-closed clear list leaves ef_win=0 but layer_on.
ef_fb_mki:
        bsr.w   ef_cl_poll
        tstl    ef_win
        bne.s   efb_mki_go
        tstl    ef_layer_on
        beq.s   efb_mki_st
efb_mki_go:
        bra.w   ef_clear_menu
efb_mki_st:
        jmp     FUNC_BANK_STOCK_MKI

| MKII FUNC+BANK / TRACK TRIG EDIT. SEQ session -> clear; else stock.
ef_fb_mkii:
        bsr.w   ef_cl_poll              | stranded soft-close: bring SEQ back
        tstl    ef_win
        bne.s   efb_mkii_go
        tstl    ef_layer_on
        beq.s   efb_mkii_st
efb_mkii_go:
        bra.w   ef_clear_menu
efb_mkii_st:
        jmp     MKII_TRIG_EDIT_CONT     | stock bra.b target (entry was 60ee)

| Lock knobs while our LISTPOP is up (M_CBS == EF_CL_CBS).
ef_cl_ours:
        tstl    M_OBJ
        beq.s   eco_no
        movel   M_CBS,%d0
        cmpil   #EF_CL_CBS,%d0
        bne.s   eco_no
        moveq   #1,%d0
        rts
eco_no: moveq   #0,%d0
        rts

| Safety net: LISTPOP NO without our cancel layer. If dlg_guard is set
| and our CLEAR list is gone, recreate SEQ. Do NOT treat ARE YOU SURE?
| the same way: ef_enc polls every knob turn, and restoring SEQ while
| ef_ask is set stacked the window on top of the dialog (HW: dialog
| behind SEQ).
ef_cl_poll:
        tstl    ef_dlg_guard
        beq.s   ecp_rts
        tstl    ef_ask                  | stock dialog still owns the screen
        bne.s   ecp_rts
        bsr.w   ef_cl_ours
        tstl    %d0
        bne.s   ecp_rts
        clrl    ef_dlg_guard
        bra.w   ef_cl_rest
ecp_rts: rts

ef_cl_close:
        bsr.w   ef_cl_ours
        tstl    %d0
        beq.s   ecc2_rts
        jsr     M_CLOSE
        clrl    ef_dlg_guard
ecc2_rts: rts

| Drop the NO-only cancel layer pushed over CLEAR LISTPOP.
ef_cl_nolayer_off:
        tstl    ef_cl_nolayer
        beq.s   ecn_rts
        clrl    ef_cl_nolayer
        pea     EF_CL_NO_LAYER
        jsr     LPOP
        addql   #4,%sp
ecn_rts: rts

| NO while CLEAR list is up (cancel layer on top of LISTPOP). One press:
| close list + restore SEQ. Stock LISTPOP would eat NO and leave SEQ
| soft-closed on the main screen.
ef_cl_cancel:
        moveq   #1,%d0
        cmpl    8(%sp),%d0
        bne.s   ecc_rts
        bsr.w   ef_cl_ours
        tstl    %d0
        beq.s   ecc_rest
        jsr     M_CLOSE
ecc_rest:
        clrl    ef_dlg_guard
        bra.w   ef_cl_rest
ecc_rts: rts

| Open / toggle the 3-row clear LISTPOP. M_OPEN evicts class-5 SEQ
| (dlg_guard soft-close). Do NOT ef_mkwin while the list is up: WCREATE
| stacks SEQ on top of LISTPOP and the clear menu is invisible (HW:
| "FUNC+BANK does nothing"). After M_OPEN, LPUSH a NO-only layer so one
| NO closes the list and restores SEQ (LISTPOP alone eats NO).
ef_clear_menu:
        tstl    ef_win
        bne.s   ecm_have
        tstl    ef_layer_on             | soft-closed: still our session
        beq.s   ecm_rts
ecm_have:
        bsr.w   ef_cl_ours
        tstl    %d0
        beq.s   ecm_open
        jsr     M_CLOSE
        clrl    ef_dlg_guard
        bra.w   ef_cl_rest
ecm_open:
        moveq   #1,%d0
        movel   %d0,ef_dlg_guard        | soft-close if LISTPOP evicts class 5
        tstl    ef_win
        beq.s   ecm_do
        movel   %d0,ef_need_restore     | M_OPEN will soft-close; restore on list close
ecm_do: clrl    ef_cl_sel
        pea     EF_CL_CBS
        pea     EF_CL_LBL
        pea     ef_cl_sel
        clrl    -(%sp)                  | initial sel 0
        pea     3
        jsr     M_OPEN
        lea     20(%sp),%sp
        bsr.w   ef_cl_nolayer_off       | idempotent if a prior push stuck
        pea     EF_CL_NO_LAYER
        jsr     LPUSH
        addql   #4,%sp
        moveq   #1,%d0
        movel   %d0,ef_cl_nolayer
ecm_rts: rts

| Recreate SEQ after clear LISTPOP / ARE YOU SURE? soft-close.
ef_cl_rest:
        bsr.w   ef_cl_nolayer_off
        tstl    ef_need_restore
        beq.s   ecm_draw
        clrl    ef_need_restore
        bsr.w   ef_mkwin
        tstl    %d0
        beq.s   ecr_rts
ecm_draw:
        tstl    ef_win
        beq.s   ecr_rts
        bra.w   ef_draw
ecr_rts: rts

| LISTPOP YES callbacks: clear immediately + reset params (no SEQ YES).
ef_cl_dest:
        bsr.w   ef_clear_cur_dest
        pea     0x30
        pea     T_CL_DEST
        jsr     TOAST
        addql   #8,%sp
        bra.w   ef_cl_done
ef_cl_all:
        bsr.w   ef_clear_all_dest
        pea     0x30
        pea     T_CL_ALL
        jsr     TOAST
        addql   #8,%sp
        bra.w   ef_cl_done
ef_cl_all_trigs:
        bsr.w   ef_clear_all_dest
        bsr.w   ef_clear_trigs
        pea     0x30
        pea     T_CL_SEQ
        jsr     TOAST
        addql   #8,%sp
ef_cl_done:
        jsr     M_CLOSE
        clrl    ef_dlg_guard
        bra.w   ef_cl_rest
ecat_midi_rts:
        rts

| a2 := focused TRAC, d5 := n steps. Clobbers d0-d3/a0-a2.
ef_trac_n:
        bsr.w   ef_sync_len
        bsr.w   ef_trac_focus           | a2, d3 = n
        movel   ef_focus,%d0
        andil   #7,%d0
        movel   %d0,ef_trk
        movel   %d3,%d5
        rts

| Clear focused DEST over 0..n-1 + reset that DEST's depth/plock recipe.
ef_clear_cur_dest:
        tstl    MIDI_MODE
        bne.w   ef_midi_clear_dest
        lea     -28(%sp),%sp
        movem.l %d2-%d7/%a2,(%sp)
        bsr.w   ef_trac_n
        moveq   #0,%d2
ccd_lp: cmpl    %d5,%d2
        bcc.s   ccd_done
        bsr.w   ef_bit_addr
        moveb   %a0@,%d1
        and.l   %d0,%d1
        sne     %d1
        andil   #1,%d1
        movel   %d1,ef_thit
        bsr.w   ef_clear_dest_step
        bsr.w   ef_tl_reconcile
        addql   #1,%d2
        bra.s   ccd_lp
ccd_done:
        bsr.w   ef_reset_cur_plk
        bsr.w   ef_clear_finish
        movem.l (%sp),%d2-%d7/%a2
        lea     28(%sp),%sp
        rts
ccd_midi_rts:
        rts

| Reset working + mem for current DEST: DEPTH/PULSE/ROT/free/mask = 0.
ef_reset_cur_plk:
        clrl    ef_depth
        clrl    ef_ppulses
        clrl    ef_prot
        clrl    ef_pfree
        clrl    ef_from_cue
        lea     ef_pmask,%a0
        moveq   #7,%d0
rcp_z:  clrb    %a0@(0,%d0:l)
        subql   #1,%d0
        bpl.s   rcp_z
        bsr.w   ef_dep_save
        bsr.w   ef_plk_save
        bra.w   ef_store_slot

| Clear every DEST SEQ knows on the focused track; leave sample trigs.
ef_clear_all_dest:
        tstl    MIDI_MODE
        bne.w   ef_midi_clear_all
        lea     -32(%sp),%sp
        movem.l %d2-%d7/%a2-%a3,(%sp)
        bsr.w   ef_trac_n
        movel   ef_dest,-(%sp)          | restore after
        moveq   #0,%d6                  | dest
cad_d:  moveq   #DEST_CXLAST,%d0
        cmpl    %d0,%d6
        bhi.s   cad_fin
        moveq   #DEST_XVOL,%d0
        cmpl    %d0,%d6
        beq.s   cad_nx
        movel   %d6,ef_dest
        moveq   #0,%d2
cad_s:  cmpl    %d5,%d2
        bcc.s   cad_nx
        bsr.w   ef_bit_addr
        moveb   %a0@,%d1
        and.l   %d0,%d1
        sne     %d1
        andil   #1,%d1
        movel   %d1,ef_thit
        bsr.w   ef_clear_dest_step
        bsr.w   ef_tl_reconcile
        addql   #1,%d2
        bra.s   cad_s
cad_nx: addql   #1,%d6
        bra.s   cad_d
cad_fin:
        movel   (%sp)+,ef_dest
        bsr.w   ef_reset_all_plk
        bsr.w   ef_clear_finish
        movem.l (%sp),%d2-%d7/%a2-%a3
        lea     32(%sp),%sp
        rts
cad_midi_rts:
        rts

| Zero all depth + plock slots for focused track; working DEST params 0.
ef_reset_all_plk:
        tstl    MIDI_MODE
        bne.w   ef_reset_midi_plk
        moveq   #0,%d0
        movel   ef_focus,%d0
        andil   #7,%d0
        movel   %d0,%d1
        lsll    #5,%d0                  | t*32
        lsll    #2,%d1                  | t*4
        addl    %d1,%d0                 | t*36
        lea     ef_dep_mem,%a0
        addal   %d0,%a0
        moveq   #DEST_NSLOT-1,%d1
rap_d:  clrb    %a0@(0,%d1:l)
        subql   #1,%d1
        bpl.s   rap_d
        | plock: slot index = t*36 + dest; each 12 B
        moveq   #0,%d0
        movel   ef_focus,%d0
        andil   #7,%d0
        movel   %d0,%d1
        lsll    #5,%d0
        lsll    #2,%d1
        addl    %d1,%d0                 | t*36
        movel   %d0,%d1
        lsll    #3,%d0                  | *8
        lsll    #2,%d1                  | *4
        addl    %d1,%d0                 | *12 = byte off of first dest slot
        lea     ef_plk_mem,%a0
        addal   %d0,%a0
        movel   #DEST_NSLOT*EF_PLK_SLOT,%d0
        subql   #1,%d0
rap_p:  clrb    %a0@(0,%d0:l)
        subql   #1,%d0
        bpl.s   rap_p
rap_work:
        clrl    ef_depth
        clrl    ef_ppulses
        clrl    ef_prot
        clrl    ef_pfree
        clrl    ef_from_cue
        lea     ef_pmask,%a0
        moveq   #7,%d0
rap_m:  clrb    %a0@(0,%d0:l)
        subql   #1,%d0
        bpl.s   rap_m
        moveq   #1,%d0
        movel   %d0,ef_dirty
        bra.w   ef_store_slot

| MIDI clear actions only address the focused MIDI track and its recipes.
ef_midi_clear_dest:
        lea     -32(%sp),%sp
        movem.l %d2-%d7/%a2-%a3,(%sp)
        bsr.w   ef_sync_len
        movel   ef_focus,%d0
        movel   %d0,ef_trk
        movel   ef_steps,%d5
        moveq   #0,%d2
mcd_loop:
        cmpl    %d5,%d2
        bcc.s   mcd_done
        moveq   #-1,%d0
        bsr.w   ef_midi_lock_store
        addql   #1,%d2
        bra.s   mcd_loop
mcd_done:
        bsr.w   ef_reset_cur_plk
        bsr.w   ef_clear_finish
        movem.l (%sp),%d2-%d7/%a2-%a3
        lea     32(%sp),%sp
        rts

ef_midi_clear_all:
        lea     -32(%sp),%sp
        movem.l %d2-%d7/%a2-%a3,(%sp)
        bsr.w   ef_sync_len
        movel   ef_focus,%d0
        movel   %d0,ef_trk
        movel   ef_steps,%d5
        movel   ef_dest,%d7
        moveq   #0,%d6
mca_flat:
        movel   %d6,ef_dest
        moveq   #0,%d2
mca_step:
        cmpl    %d5,%d2
        bcc.s   mca_next
        moveq   #-1,%d0
        bsr.w   ef_midi_lock_store
        addql   #1,%d2
        bra.s   mca_step
mca_next:
        addql   #1,%d6
        cmpil   #30,%d6
        bcs.s   mca_flat
        movel   %d7,ef_dest
        bsr.w   ef_reset_all_plk
        bsr.w   ef_clear_finish
        movem.l (%sp),%d2-%d7/%a2-%a3
        lea     32(%sp),%sp
        rts

ef_reset_midi_plk:
        movel   ef_focus,%d0
        movel   #DEST_NSLOT,%d1
        mulu.l  %d1,%d0
        lea     ef_midi_dep_mem,%a0
        adda.l  %d0,%a0
        moveq   #DEST_NSLOT-1,%d1
rmp_dep:
        clrb    %a0@(0,%d1:l)
        subql   #1,%d1
        bpl.s   rmp_dep
        movel   ef_focus,%d0
        movel   #EF_MIDI_PLK_NSLOT*EF_PLK_SLOT,%d1
        mulu.l  %d1,%d0
        lea     ef_midi_plk_mem,%a0
        adda.l  %d0,%a0
        movel   #EF_MIDI_PLK_NSLOT*EF_PLK_SLOT-1,%d1
rmp_plk:
        clrb    %a0@(0,%d1:l)
        subql   #1,%d1
        bpl.s   rmp_plk
        bra.w   rap_work

ef_midi_clear_trigs:
        lea     -32(%sp),%sp
        movem.l %d2-%d7/%a2-%a3,(%sp)
        bsr.w   ef_sync_len
        movel   ef_focus,%d2
        movel   %d2,ef_trk
        clrl    ef_pulses
        clrl    ef_free
        bsr.w   ef_write_midi_mask
        moveq   #5,%d0
        movel   %d0,ef_pulses
        clrl    ef_rot
        clrl    ef_from_cue
        clrl    ef_unlocked
        lea     ef_mask,%a0
        moveq   #7,%d0
mct_mask:
        clrb    %a0@(0,%d0:l)
        subql   #1,%d0
        bpl.s   mct_mask
        bsr.w   ef_store_slot
        bsr.w   ef_clear_finish
        movem.l (%sp),%d2-%d7/%a2-%a3
        lea     32(%sp),%sp
        rts

| Wipe sample trigs 0..n-1 + reset TRIG recipe defaults (PULSE 5).
ef_clear_trigs:
        tstl    MIDI_MODE
        bne.w   ef_midi_clear_trigs
        lea     -28(%sp),%sp
        movem.l %d2-%d7/%a2,(%sp)
        bsr.w   ef_trac_n
        moveq   #0,%d2
ctr_lp: cmpl    %d5,%d2
        bcc.s   ctr_done
        bsr.w   ef_bit_addr
        moveb   %a0@,%d1
        move.l  %d0,%d3
        not.l   %d3
        and.l   %d3,%d1
        moveb   %d1,%a0@
        clrl    ef_thit
        bsr.w   ef_tl_reconcile
        addql   #1,%d2
        bra.s   ctr_lp
ctr_done:
        moveq   #5,%d0
        movel   %d0,ef_pulses
        clrl    ef_rot
        clrl    ef_free
        clrl    ef_from_cue
        lea     ef_mask,%a0
        moveq   #7,%d0
ctr_m:  clrb    %a0@(0,%d0:l)
        subql   #1,%d0
        bpl.s   ctr_m
        bsr.w   ef_store_slot
        bsr.w   ef_drop_clr_undo
        | mirror masks 0..2
        moveq   #0,%d0
        moveb   UI_PTN,%d0
        movel   #PTN_STR,%d1
        mulu.l  %d1,%d0
        movel   ef_focus,%d1
        andil   #7,%d1
        movel   #TRK_STR,%d3
        mulu.l  %d3,%d1
        addl    %d1,%d0
        addil   #MIRROR,%d0
        moveal  %d0,%a4
        moveq   #23,%d0
ctr_c:  moveb   %a2@(0,%d0:l),%d1
        moveb   %d1,%a4@(0,%d0:l)
        subql   #1,%d0
        bpl.s   ctr_c
        bsr.w   ef_clear_finish
        movem.l (%sp),%d2-%d7/%a2
        lea     28(%sp),%sp
        rts
ctr_midi_rts:
        rts

| Dirty + NOTIFY + LOCK_COLL after a clear. Clobbers d0/a0.
ef_clear_finish:
        moveal  DBPTR,%a0
        addal   #DIRTY_OFF,%a0
        moveq   #1,%d0
        movel   %d0,%a0@
        moveal  #DIRTY_G,%a0
        movel   %d0,%a0@
        jsr     NOTIFY
        jsr     LOCK_COLL
        rts

| ---- layer --------------------------------------------------------------
        .balign 4
EF_LAYER:
        .long   0, EF_KEYS, EF_ENCS, 0, 0, -1, -1
EF_KEYS:
        | PAGE (0x1b): omit - ef_page: TRACK+PAGE toggles; bare PAGE is
        | stock (never closes). Listing PAGE here swallows step banks.

        .byte   0x31, 0                 | YES
        .long   ef_yes, 0, 0, 0, 0
        .word   0, 0
        .byte   0x32, 0                 | NO
        .long   ef_no, 0, 0, 0, 0
        .word   0, 0
        | LEFT/RIGHT switch SEQ knob pages. UP/DOWN / PROJ/PART/AED/ARR
        | remain omitted (a -1 row can break stock navigation).
        .byte   0x34, 0                 | LEFT (stock key id used by FUNC+LEFT)
        .long   ef_page_left, 0, 0, 0, 0
        .word   0, 0
        .byte   0x21, 0                 | RIGHT
        .long   ef_page_right, 0, 0, 0, 0
        .word   0, 0
        | Listing with 0 swallows; listing with -1 still stores aux=0
        | and has been seen to break DOWN after Euclid → PROJECT.
        .byte   0x2a, 0                 | CUE: press+release (0 swallows release)
        .long   ef_cue, ef_cue, 0, 0, 0
        .word   0, 0
        | BANK (0x2f): omit - FUNC+BANK is Detour / MKI SymbolRef only.
| T1..T8: press+release both ef_trkkey (stock needs release to clear
| HELD). On press, retarget SEQ only if UI_WINDOW still ef_win.
        .byte   0x10, 0
        .long   ef_trkkey, ef_trkkey, 0, 0, 0
        .word   0, 0
        .byte   0x11, 0
        .long   ef_trkkey, ef_trkkey, 0, 0, 0
        .word   0, 0
        .byte   0x12, 0
        .long   ef_trkkey, ef_trkkey, 0, 0, 0
        .word   0, 0
        .byte   0x13, 0
        .long   ef_trkkey, ef_trkkey, 0, 0, 0
        .word   0, 0
        .byte   0x14, 0
        .long   ef_trkkey, ef_trkkey, 0, 0, 0
        .word   0, 0
        .byte   0x15, 0
        .long   ef_trkkey, ef_trkkey, 0, 0, 0
        .word   0, 0
        .byte   0x16, 0
        .long   ef_trkkey, ef_trkkey, 0, 0, 0
        .word   0, 0
        .byte   0x17, 0
        .long   ef_trkkey, ef_trkkey, 0, 0, 0
        .word   0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
EF_ENCS:
        .byte   0, 0                    | A = PULSE
        .long   ef_enc, 0, 0, 0, 0
        .byte   1, 0                    | B = ROT
        .long   ef_enc, 0, 0, 0, 0
        .byte   2, 0                    | C = LANE
        .long   ef_enc, 0, 0, 0, 0
        .byte   3, 0                    | D = DEST
        .long   ef_enc, 0, 0, 0, 0
        .byte   4, 0                    | E = DEPTH
        .long   ef_enc, 0, 0, 0, 0
        .byte   5, 0                    | F = empty
        .long   ef_enc, 0, 0, 0, 0
        .byte   6, 0                    | LEVEL = noop
        .long   ef_level, 0, 0, 0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0

| Dotted internals only - left edge is solid VLINE above.
        .balign 4
EF_GRID:
        .long   X_DIV0, Y_GRID0, X_DIV0, Y_GRID1
        .long   X_DIV1, Y_GRID0, X_DIV1, Y_GRID1
        .long   X_GRID, Y_GMID, X_GRID+3*CELL_W, Y_GMID

T_TITLE:  .asciz "SEQ"
T_PAGE1:  .asciz " 1>"
T_PAGE2:  .asciz "<2 "
T_TRK:    .asciz "T%d"
T_FILLED: .asciz "TRIGS CREATED"
T_CLRTITLE: .asciz "ARE YOU SURE?"
T_CLRMSG1:  .asciz "EXISTING TRIGS IN THE PATTERN"
T_CLRMSG2:  .asciz "WILL BE CLEARED ON NEXT FILL"
T_CL_DEST:  .asciz "DEST CLEARED"
T_CL_ALL:   .asciz "DESTS CLEARED"
T_CL_SEQ:   .asciz "SEQ CLEARED"
L_CL_DEST:  .asciz "CLEAR DEST"
L_CL_ALL:   .asciz "CLEAR ALL DEST"
L_CL_ATRG:  .asciz "CLEAR ALL+TRIGS"
        .balign 4
ef_clr_lines:
        .long   T_CLRMSG1, T_CLRMSG2
EF_CL_LBL:
        .long   L_CL_DEST, L_CL_ALL, L_CL_ATRG
EF_CL_CBS:
        .long   ef_cl_dest, ef_cl_all, ef_cl_all_trigs
| NO-only layer above CLEAR LISTPOP: one NO closes + restores SEQ.
        .balign 4
EF_CL_NO_LAYER:
        .long   0, EF_CL_NO_KEYS, 0, 0, 0, -1, -1
EF_CL_NO_KEYS:
        .byte   0x32, 0                 | NO
        .long   ef_cl_cancel, 0, 0, 0, 0
        .word   0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
| 4-char max - stock page-1 cells are 20 px (PANEL.md).
L_LEN:    .asciz "LEN"
L_PULSES: .asciz "PULS"
L_ROT:    .asciz "ROT"
L_LANE:   .asciz "LANE"
L_TRIG:   .asciz "TRIG"
L_PLOCK:  .asciz "PLCK"
L_DEPTH:  .asciz "DPTH"
L_SCALE:  .asciz "SCAL"
L_ROOT:   .asciz "ROOT"
L_MODE:   .asciz "MODE"
L_PHRASE: .asciz "PHRS"
L_JUMP:   .asciz "JUMP"
L_VOIC:   .asciz "VOIC"
L_CHORD:  .asciz "CHRD"
VFMT:     .asciz "%d"
VFMT_CHORD:.asciz "%s%d"
S_MAJ:    .asciz "MAJ"
S_MIN:    .asciz "MIN"
S_PENT:   .asciz "PENT"
S_DOR:    .asciz "DOR"
S_PHR:    .asciz "PHR"
S_MIX:    .asciz "MIX"
S_WHOLE:  .asciz "WHOL"
S_CHRO:   .asciz "CHRO"
N_C:      .asciz "C"
N_CS:     .asciz "C#"
N_D:      .asciz "D"
N_DS:     .asciz "D#"
N_E:      .asciz "E"
N_F:      .asciz "F"
N_FS:     .asciz "F#"
N_G:      .asciz "G"
N_GS:     .asciz "G#"
N_A:      .asciz "A"
N_AS:     .asciz "A#"
N_B:      .asciz "B"
M_MELODY: .asciz "MELO"
M_ARP:    .asciz "ARP"
H_V1:     .asciz "1"
H_V2:     .asciz "2"
H_V3:     .asciz "3"
H_V4:     .asciz "4"
CH_MIN:   .asciz "MIN"
CH_MAJ:   .asciz "MAJ"
CH_SU2:   .asciz "SU2"
CH_SU4:   .asciz "SU4"
CH_MI7:   .asciz "MI7"
CH_DO7:   .asciz "DO7"
CH_MA7:   .asciz "MA7"
CH_7S4:   .asciz "7S4"
CH_DI7:   .asciz "DI7"
CH_AD2:   .asciz "AD2"
CH_MD2:   .asciz "MD2"
CH_AD9:   .asciz "AD9"
CH_MI6:   .asciz "MI6"
CH_MA6:   .asciz "MA6"
CH_M75:   .asciz "M75"
CH_DIM:   .asciz "DIM"
CH_AUG:   .asciz "AUG"
CH_MI9:   .asciz "MI9"
CH_DO9:   .asciz "DO9"
CH_MA9:   .asciz "MA9"
CH_M69:   .asciz "M69"
CH_QUA:   .asciz "QUA"
CH_4TH:   .asciz "4TH"
CH_5TH:   .asciz "5TH"
CH_OCT:   .asciz "OCT"
CH_3MI:   .asciz "3MI"
CH_3MA:   .asciz "3MA"
CH_7MI:   .asciz "7MI"
CH_7MA:   .asciz "7MA"
CH_MAS:   .asciz "MAS"
CH_MIS:   .asciz "MIS"
P_UP:     .asciz "UP"
P_DOWN:   .asciz "DOWN"
P_ALT:    .asciz "ALT"
P_TRI:    .asciz "TRI"
P_RAND:   .asciz "RAND"
H_TRIAD:  .asciz "TRI"
H_SEVENTH:.asciz "7TH"
        .balign 4
ef_tonal_labels:
        .long L_SCALE,L_ROOT,L_MODE,L_PHRASE,L_JUMP,L_CHORD
ef_xcells:
        .long X_C0,X_C1,X_C2
ef_scale_names:
        .long S_MAJ,S_MIN,S_PENT,S_DOR,S_PHR,S_MIX,S_WHOLE,S_CHRO
ef_root_names:
        .long N_C,N_CS,N_D,N_DS,N_E,N_F,N_FS,N_G,N_GS,N_A,N_AS,N_B
ef_mode_names:
        .long M_MELODY,M_ARP
ef_phrase_names:
        .long P_RAND,P_UP,P_DOWN,P_ALT,P_TRI
ef_harmony_names:
        .long H_V1,H_V2,H_V3,H_V4
ef_chord_shapes:
        .byte 0,-128,-128,-128
        .byte 0,3,7,12, 0,4,7,12, 0,2,7,12, 0,5,7,12
        .byte 0,10,3,7, 0,10,4,7, 0,11,4,7, 0,5,10,7
        .byte 0,6,3,9, 0,2,4,7, 0,2,3,7, 0,14,4,7
        .byte 0,9,3,7, 0,9,4,7, 0,10,6,3, 0,6,3,12
        .byte 0,8,4,12, 0,10,14,3, 0,10,14,4, 0,11,14,4
        .byte 0,9,14,4, 0,5,10,15, 0,5,12,17, 0,7,12,19
        .byte 0,12,24,36, 0,3,12,15, 0,4,12,16, 0,10,12,22
        .byte 0,11,12,23, 0,7,16,12, 0,7,15,12
ef_chord_names:
        .long CH_MIN,CH_MAJ,CH_SU2,CH_SU4,CH_MI7,CH_DO7,CH_MA7,CH_7S4
        .long CH_DI7,CH_AD2,CH_MD2,CH_AD9,CH_MI6,CH_MA6,CH_M75,CH_DIM
        .long CH_AUG,CH_MI9,CH_DO9,CH_MA9,CH_M69,CH_QUA,CH_4TH,CH_5TH
        .long CH_OCT,CH_3MI,CH_3MA,CH_7MI,CH_7MA,CH_MAS,CH_MIS
ef_scale_masks:
        .word 0x0ab5,0x05ad,0x0295,0x06ad,0x05ab,0x06b5,0x0555,0x0fff
ef_scale_counts:
        .byte 7,7,5,7,7,7,6,12
        .balign 4
| SEQ mark 29×29: 3 rings E(4,12) LED; mid hollow squares at 45°.
| Column-major; bit 31 = bottom row.
ef_icon_bmp:
        .long   ICON_W, ICON_H, 1, ef_icon_data, ef_icon_mask
ef_icon_mask:
        .rept   ICON_W
        .long   0xfffffff8              | rows 0..28
        .endr
ef_icon_data:
        .long   0x00070000
        .long   0x001dc000
        .long   0x00e73800
        .long   0x03800e00
        .long   0x06000300
        .long   0x0c1fc180
        .long   0x187070c0
        .long   0x11c01c40
        .long   0x31401460
        .long   0x23c21e20
        .long   0x220d8220
        .long   0x461ac310
        .long   0x44306110
        .long   0xe4202138
        .long   0xa4505128
        .long   0xe4202138
        .long   0x44306110
        .long   0x461ac310
        .long   0x220d8220
        .long   0x23c21e20
        .long   0x31401460
        .long   0x11c01c40
        .long   0x187070c0
        .long   0x0c1fc180
        .long   0x06000300
        .long   0x03800e00
        .long   0x00e73800
        .long   0x001dc000
        .long   0x00070000
| Static DEST name fallback (PAGE + PARAM) when the page resolver /
| FX table miss. Live path uses descriptors (+4 / +0x16) + LFD_RESOLVER.
| AMP XVOL stays in the table (flat 17) but DEST nudge skips that index.
| CX private 30..34: ef_cxpriv_tab (SRC CAR..PWM).
        .balign 4
ef_dpage_tab:
        .ascii  "SRC\0"
        .ascii  "LFO\0"
        .ascii  "AMP\0"
        .ascii  "FX1\0"
        .ascii  "FX2\0"
        .balign 4
ef_midi_desc_tab:
        .long   0x400d3e3e             | NOTE: NOTE VEL LEN NOT2..4
        .long   0x400d4162             | LFO
        .long   0x400d3fd0             | ARP
        .long   0x400d42f4             | CTRL1: PB AT CC1..4
        .long   0x400d4486             | CTRL2: CC5..10
ef_dparam_tab:
        .ascii  "PTCH\0\0STRT\0\0LEN\0\0\0RATE\0\0RTRG\0\0RTIM\0\0"
        .ascii  "SPD1\0\0SPD2\0\0SPD3\0\0DEP1\0\0DEP2\0\0DEP3\0\0"
        .ascii  "ATK\0\0\0HOLD\0\0REL\0\0\0VOL\0\0\0BAL\0\0\0XVOL\0\0"
        .ascii  "A\0\0\0\0\0B\0\0\0\0\0C\0\0\0\0\0D\0\0\0\0\0E\0\0\0\0\0F\0\0\0\0\0"
        .ascii  "A\0\0\0\0\0B\0\0\0\0\0C\0\0\0\0\0D\0\0\0\0\0E\0\0\0\0\0F\0\0\0\0\0"
        .balign 4
ef_cxpriv_tab:                          | PMTR 30..34 - matches cx_lf_pmtr_fmt
        .ascii  "CAR\0\0\0"
        .ascii  "MOD\0\0\0"
        .ascii  "SYMM\0\0"
        .ascii  "FDBK\0\0"
        .ascii  "PWM\0\0\0"
        .balign 4
ef_cx_slots:                            | DEST 30..34 -> PLAYBACK SETUP slot (skip DEC)
        .byte   0, 1, 3, 4, 5
        .balign 4

| ---- euclid.work (STORE client): bank + depths + plock + LANE ----------
| Header 16 B: magic 'EFIL', version EF_VER, EF_FILE_B, CRC-32 of the
| contiguous payload ef_bank through ef_tone_mem.
| Written on bank/project save when dirty; .strd = copy.
FMT_EWORK: .asciz "%s/euclid.work"
FMT_ESTRD: .asciz "%s/euclid.strd"
FMT_EBAK:  .asciz "%s/euclid.bak"
EF_MODE_R: .asciz "r"
EF_MODE_W: .asciz "w"
        .balign 4

| Reset all 8 slots + DEST-depth table. Clobbers d0/d1/a0.
ef_defaults:
        bsr.w   ef_tone_defaults
        lea     ef_bank,%a0
        moveq   #7,%d0
ed_1:   moveq   #5,%d1
        movel   %d1,%a0@+
        clrl    %a0@+
        moveq   #LOCK_PTCH,%d1
        movel   %d1,%a0@+
        clrl    %a0@+
        clrl    %a0@+
        clrl    %a0@+                   | mask[0..3]
        clrl    %a0@+                   | mask[4..7]
        subql   #1,%d0
        bpl.s   ed_1
        bsr.w   ef_midi_defaults
        lea     ef_dep_mem,%a0
        movel   #EF_DEP_B+EF_PLK_B+EF_LANE_B,%d0
        addql   #3,%d0                  | round up to long
        lsr.l   #2,%d0                  | longs (dep||plk||lane)
        subql   #1,%d0
ed_z:   clrl    %a0@+
        subql   #1,%d0
        bpl.s   ed_z
        clrl    ef_lane
        clrl    ef_ppulses
        clrl    ef_prot
        clrl    ef_pfree
        clrl    ef_from_cue
        lea     ef_pmask,%a0
        moveq   #7,%d0
ed_pm:  clrb    %a0@(0,%d0:l)
        subql   #1,%d0
        bpl.s   ed_pm
        clrl    ef_dirty
        rts

| Reset the separate eight MIDI-track SEQ recipes.
ef_midi_defaults:
        lea     ef_midi_bank,%a0
        moveq   #7,%d0
emd_1:  moveq   #5,%d1
        movel   %d1,%a0@+
        clrl    %a0@+
        clrl    %a0@+                  | default target NOTE (flat 0)
        clrl    %a0@+
        clrl    %a0@+
        clrl    %a0@+
        clrl    %a0@+
        subql   #1,%d0
        bpl.s   emd_1
        lea     ef_midi_dep_mem,%a0
        moveq   #EF_MIDI_DEP_B/4-1,%d0
emd_z:  clrl    %a0@+
        subql   #1,%d0
        bpl.s   emd_z
        bsr.w   ef_midi_plk_defaults
        rts

| Reset MIDI PLOCK recipes and per-track lane selectors.
ef_midi_plk_defaults:
        lea     ef_midi_plk_mem,%a0
        movel   #EF_MIDI_PLK_B/4-1,%d0
emp_z:  clrl    %a0@+
        subql   #1,%d0
        bpl.s   emp_z
        lea     ef_midi_lane_mem,%a0
        clrl    %a0@
        clrl    4(%a0)
        rts

| Copy work path formats: a0=src fmt, a1=dst fmt -> d0 from F_COPY.
ef_copy_file:
        movel   %a1,-(%sp)
        lea     ef_psrc,%a1
        moveq   #0,%d0
        jsr     store_path
        movel   (%sp)+,%a0
        lea     ef_path,%a1
        moveq   #0,%d0
        jsr     store_path
        clrl    -(%sp)
        pea     ef_psrc
        pea     ef_path
        jsr     F_COPY
        lea     12(%sp),%sp
        rts

| Write ef_bank + ef_dep_mem to euclid.work when dirty. Clobbers everything.
ef_write_due:
        tstl    ef_dirty
        beq.w   ew_rts
        tstl    ef_nowrite
        bne.w   ew_rts
        tstl    ef_backup
        beq.s   ew_1
        clrl    ef_backup
        lea     FMT_EWORK,%a0
        lea     FMT_EBAK,%a1
        bsr.w   ef_copy_file
ew_1:   lea     ef_bank,%a0             | bank || dep contiguous
        movel   #EF_FILE_B,%d0
        moveq   #0,%d1
        jsr     store_crc32
        movel   %d0,ef_hdr+12
        movel   #EF_MAGIC,%d0
        movel   %d0,ef_hdr
        moveq   #EF_VER,%d0
        movel   %d0,ef_hdr+4
        movel   #EF_FILE_B,%d0
        movel   %d0,ef_hdr+8
        lea     FMT_EWORK,%a0
        lea     ef_path,%a1
        moveq   #0,%d0
        jsr     store_path
        lea     ef_path,%a0
        lea     EF_MODE_W,%a1
        lea     ef_ctx,%a2
        jsr     store_fopen
        tstl    %d0
        bmi.w   ew_rts
        lea     ef_hdr,%a0
        moveq   #16,%d0
        jsr     store_fwrite
        movel   %d0,%d2
        lea     ef_bank,%a0
        movel   #EF_FILE_B,%d0
        jsr     store_fwrite
        movel   %d0,%d3
        jsr     store_fclose
        subql   #1,%d2
        bne.s   ew_rts
        subql   #1,%d3
        bne.s   ew_rts
        clrl    ef_dirty
ew_rts: rts

| Load euclid.work. Missing -> defaults. Bad -> refuse + defaults.
| v1 bank; v2 bank+dep; v3 bank+dep+plk. Older payloads zero the rest.
ef_load_file:
        bsr.w   ef_tone_defaults
        clrl    ef_nowrite
        clrl    ef_backup
        lea     FMT_EWORK,%a0
        lea     ef_path,%a1
        moveq   #0,%d0
        jsr     store_path
        lea     ef_path,%a0
        lea     EF_MODE_R,%a1
        lea     ef_ctx,%a2
        jsr     store_fopen
        tstl    %d0
        bmi.w   ef_defaults
        lea     ef_hdr,%a0
        moveq   #16,%d0
        jsr     store_fread
        subql   #1,%d0
        bne.w   el_bad
        lea     ef_hdr,%a0
        movel   %a0@,%d0
        cmpl    #EF_MAGIC,%d0
        bne.w   el_bad
        movel   %a0@(4),%d2             | version
        movel   %a0@(8),%d3             | payload size
        moveq   #1,%d0
        cmpl    %d0,%d2
        beq.w   el_v1
        moveq   #2,%d0
        cmpl    %d0,%d2
        beq.w   el_v2
        moveq   #3,%d0
        cmpl    %d0,%d2
        beq.w   el_v3
        moveq   #4,%d0
        cmpl    %d0,%d2
        beq.w   el_v4
        moveq   #5,%d0
        cmpl    %d0,%d2
        beq.w   el_v5
        moveq   #6,%d0
        cmpl    %d0,%d2
        beq.w   el_v6
        moveq   #7,%d0
        cmpl    %d0,%d2
        beq.w   el_v7
        moveq   #8,%d0
        cmpl    %d0,%d2
        beq.w   el_v8
        moveq   #9,%d0
        cmpl    %d0,%d2
        beq.w   el_v9
        moveq   #10,%d0
        cmpl    %d0,%d2
        beq.w   el_v10
        moveq   #EF_VER,%d0
        cmpl    %d0,%d2
        bne.w   el_bad
        movel   #EF_FILE_B,%d0
        cmpl    %d0,%d3
        bne.w   el_bad
        lea     ef_bank,%a0
        movel   #EF_FILE_B,%d0
        jsr     store_fread
        subql   #1,%d0
        bne.w   el_bad
        jsr     store_fclose
        lea     ef_bank,%a0
        movel   #EF_FILE_B,%d0
        moveq   #0,%d1
        jsr     store_crc32
        cmpl    ef_hdr+12,%d0
        bne.w   el_crc
        clrl    ef_dirty
        rts
| v9 stored RANG in the byte now used by JUMP. Keep the tonal settings,
| reset that byte for all tracks so old ranges do not become wide jumps.
el_v9:  movel   #EF_FILE_V9,%d0
        cmpl    %d0,%d3
        bne.w   el_bad
        lea     ef_bank,%a0
        movel   %d3,%d0
        jsr     store_fread
        subql   #1,%d0
        bne.w   el_bad
        jsr     store_fclose
        lea     ef_bank,%a0
        movel   #EF_FILE_V9,%d0
        moveq   #0,%d1
        jsr     store_crc32
        cmpl    ef_hdr+12,%d0
        bne.w   el_crc
        lea     ef_tone_mem,%a0
        moveq   #15,%d0
el9_track:
        clrb    %a0@(TON_JUMP)
        addal   #EF_TONE_REC,%a0
        subql   #1,%d0
        bpl.s   el9_track
        bsr.w   ef_tone_phrase_v10_to_v11
        moveq   #1,%d0
        movel   %d0,ef_dirty
        rts
| v10 has the current record shape and old PHRS values. Rotate values so
| RAND becomes 0 without changing the selected mode on any saved track.
el_v10: movel   #EF_FILE_V10,%d0
        cmpl    %d0,%d3
        bne.w   el_bad
        lea     ef_bank,%a0
        movel   %d3,%d0
        jsr     store_fread
        subql   #1,%d0
        bne.w   el_bad
        jsr     store_fclose
        lea     ef_bank,%a0
        movel   #EF_FILE_V10,%d0
        moveq   #0,%d1
        jsr     store_crc32
        cmpl    ef_hdr+12,%d0
        bne.w   el_crc
        bsr.w   ef_tone_phrase_v10_to_v11
        moveq   #1,%d0
        movel   %d0,ef_dirty
        rts
el_v8:  movel   #EF_FILE_V8,%d0
        cmpl    %d0,%d3
        bne.w   el_bad
        lea     ef_bank,%a0
        movel   %d3,%d0
        jsr     store_fread
        subql   #1,%d0
        bne.w   el_bad
        jsr     store_fclose
        lea     ef_bank,%a0
        movel   #EF_FILE_V8,%d0
        moveq   #0,%d1
        jsr     store_crc32
        cmpl    ef_hdr+12,%d0
        bne.w   el_crc
        moveq   #0,%d2
el8_track:
        movel   %d2,%d0
        addql   #8,%d0
        lsll    #3,%d0
        lea     ef_tone_mem,%a0
        adda.l  %d0,%a0
        moveq   #0,%d1
        moveb   %a0@(TON_MODE),%d1
        cmpi.l  #1,%d1
        bne.s   el8_mono
        moveq   #3,%d1
        moveq   #0,%d0
        moveb   %a0@(TON_HARM),%d0
        cmpi.l  #1,%d0
        bne.s   el8_voice
        moveq   #4,%d1
        bra.s   el8_voice
el8_mono:
        moveq   #1,%d1
el8_voice:
        moveb   %d1,%a0@(TON_HARM)
        clrb    %a0@(TON_MODE)
        moveb   #4,%a0@(TON_STYLE)     | default MAJ chord, raw shape<<2
        addql   #1,%d2
        cmpi.l  #8,%d2
        bcs.s   el8_track
        bsr.w   ef_tone_phrase_v10_to_v11
        moveq   #1,%d0
        movel   %d0,ef_dirty
        rts
| v7 has MIDI PLOCK recipes; v8 appends tonal settings.
el_v7:  movel   #EF_FILE_V7,%d0
        cmpl    %d0,%d3
        bne.w   el_bad
        lea     ef_bank,%a0
        movel   %d3,%d0
        jsr     store_fread
        subql   #1,%d0
        bne.w   el_bad
        jsr     store_fclose
        lea     ef_bank,%a0
        movel   #EF_FILE_V7,%d0
        moveq   #0,%d1
        jsr     store_crc32
        cmpl    ef_hdr+12,%d0
        bne.w   el_crc
        bsr.w   ef_tone_defaults
        moveq   #1,%d0
        movel   %d0,ef_dirty
        rts
| v6 adds MIDI PLOCK recipes and lane state; defaults those appended tables.
el_v6:  movel   #EF_FILE_V6,%d0
        cmpl    %d0,%d3
        bne.w   el_bad
        lea     ef_bank,%a0
        movel   %d3,%d0
        jsr     store_fread
        subql   #1,%d0
        bne.w   el_bad
        jsr     store_fclose
        lea     ef_bank,%a0
        movel   #EF_FILE_V6,%d0
        moveq   #0,%d1
        jsr     store_crc32
        cmpl    ef_hdr+12,%d0
        bne.w   el_crc
        bsr.w   ef_midi_plk_defaults
        moveq   #1,%d0
        movel   %d0,ef_dirty            | rewrite as v7
        rts
| v5 keeps audio + MIDI recipes; the MIDI depth table is new.
el_v5:  movel   #EF_FILE_V5,%d0
        cmpl    %d0,%d3
        bne.w   el_bad
        lea     ef_bank,%a0
        movel   %d3,%d0
        jsr     store_fread
        subql   #1,%d0
        bne.w   el_bad
        jsr     store_fclose
        lea     ef_bank,%a0
        movel   #EF_FILE_V5,%d0
        moveq   #0,%d1
        jsr     store_crc32
        cmpl    ef_hdr+12,%d0
        bne.w   el_crc
        lea     ef_midi_dep_mem,%a0
        moveq   #EF_MIDI_DEP_B/4-1,%d0
el5_z:  clrl    %a0@+
        subql   #1,%d0
        bpl.s   el5_z
        bsr.w   ef_midi_plk_defaults
        moveq   #1,%d0
        movel   %d0,ef_dirty            | rewrite as v7
        rts
| v4 keeps the original audio layout; MIDI recipes and depths start default.
el_v4:  movel   #EF_FILE_V4,%d0
        cmpl    %d0,%d3
        bne.w   el_bad
        lea     ef_bank,%a0
        movel   %d3,%d0
        jsr     store_fread
        subql   #1,%d0
        bne.w   el_bad
        jsr     store_fclose
        lea     ef_bank,%a0
        movel   #EF_FILE_V4,%d0
        moveq   #0,%d1
        jsr     store_crc32
        cmpl    ef_hdr+12,%d0
        bne.w   el_crc
        bsr.w   ef_midi_defaults
        moveq   #1,%d0
        movel   %d0,ef_dirty            | rewrite as v7
        rts
| v3: bank+dep+2-byte plock slots -> expand into 12-byte slots; lanes 0.
el_v3:  movel   #EF_BANK_B+EF_DEP_B+8*DEST_NSLOT*2,%d0
        cmpl    %d0,%d3
        bne.w   el_bad
        lea     ef_bank,%a0
        movel   %d3,%d0
        jsr     store_fread
        subql   #1,%d0
        bne.w   el_bad
        jsr     store_fclose
        lea     ef_bank,%a0
        movel   #EF_BANK_B+EF_DEP_B+8*DEST_NSLOT*2,%d0
        moveq   #0,%d1
        jsr     store_crc32
        cmpl    ef_hdr+12,%d0
        bne.w   el_crc
        bsr.w   ef_plk_expand_v3
        bsr.w   ef_midi_defaults
        lea     ef_lane_mem,%a0
        clrl    %a0@
        clrl    4(%a0)
        moveq   #1,%d0
        movel   %d0,ef_dirty            | rewrite as v7
        rts
el_v2:  movel   #EF_BANK_B+EF_DEP_B,%d0
        cmpl    %d0,%d3
        bne.w   el_bad
        lea     ef_bank,%a0
        movel   #EF_BANK_B+EF_DEP_B,%d0
        jsr     store_fread
        subql   #1,%d0
        bne.w   el_bad
        jsr     store_fclose
        lea     ef_bank,%a0
        movel   #EF_BANK_B+EF_DEP_B,%d0
        moveq   #0,%d1
        jsr     store_crc32
        cmpl    ef_hdr+12,%d0
        bne.w   el_crc
        bsr.w   ef_midi_defaults
        lea     ef_plk_mem,%a0
        movel   #EF_PLK_B+EF_LANE_B,%d0
        addql   #3,%d0
        lsr.l   #2,%d0
        subql   #1,%d0
el_z2:  clrl    %a0@+
        subql   #1,%d0
        bpl.s   el_z2
        moveq   #1,%d0
        movel   %d0,ef_dirty            | rewrite as v6
        rts
el_v1:  movel   #EF_BANK_B,%d0
        cmpl    %d0,%d3
        bne.w   el_bad
        lea     ef_bank,%a0
        movel   #EF_BANK_B,%d0
        jsr     store_fread
        subql   #1,%d0
        bne.w   el_bad
        jsr     store_fclose
        lea     ef_bank,%a0
        movel   #EF_BANK_B,%d0
        moveq   #0,%d1
        jsr     store_crc32
        cmpl    ef_hdr+12,%d0
        bne.w   el_crc
        bsr.w   ef_midi_defaults
        lea     ef_dep_mem,%a0
        movel   #EF_DEP_B+EF_PLK_B+EF_LANE_B,%d0
        addql   #3,%d0
        lsr.l   #2,%d0
        subql   #1,%d0
el_z:   clrl    %a0@+
        subql   #1,%d0
        bpl.s   el_z
        moveq   #1,%d0
        movel   %d0,ef_dirty            | rewrite as v6
        rts

| Expand in-place v3 plock (2 B/slot) into v4 (12 B/slot). Walks high->low.
| Clobbers d0-d4/a0. Source lives at start of ef_plk_mem.
ef_plk_expand_v3:
        movel   #8*DEST_NSLOT-1,%d2     | last slot index (287)
ex_lp:  tstl    %d2
        bmi.s   ex_done
        | src = plk + idx*2
        movel   %d2,%d0
        addl    %d0,%d0
        lea     ef_plk_mem,%a0
        addal   %d0,%a0
        moveb   %a0@,%d3                | pulse
        moveb   1(%a0),%d1              | rot
        | dst = plk + idx*12
        movel   %d2,%d0
        movel   %d0,%d4
        lsll    #3,%d0                  | *8
        lsll    #2,%d4                  | *4
        addl    %d4,%d0                 | *12
        lea     ef_plk_mem,%a0
        addal   %d0,%a0
        moveb   %d3,%a0@
        moveb   %d1,1(%a0)
        clrb    2(%a0)
        clrb    3(%a0)
        clrl    4(%a0)
        clrl    8(%a0)
        subql   #1,%d2
        bra.s   ex_lp
ex_done: rts
el_bad: jsr     store_fclose
el_crc: moveq   #1,%d0
        movel   %d0,ef_nowrite
        moveq   #EF_CLIENT,%d0
        moveq   #0,%d1
        jsr     store_refuse
        bra.w   ef_defaults

| ---- STORE event handlers ------------------------------------------------
ef_st_loadall_post:
ef_st_loadmask_post:
        bra.w   ef_load_file

ef_st_newproj:
        clrl    ef_nowrite
        clrl    ef_backup
        bra.w   ef_defaults

ef_st_bankw_post:
ef_st_pstore_pre:
        bra.w   ef_write_due

ef_st_pstore_post:
        tstl    ef_nowrite
        bne.s   ep_rts
        lea     FMT_EWORK,%a0
        lea     FMT_ESTRD,%a1
        bra.w   ef_copy_file
ep_rts: rts

ef_st_preload_post:
        lea     FMT_ESTRD,%a0
        lea     FMT_EWORK,%a1
        bsr.w   ef_copy_file
        tstl    %d0
        bmi.s   ep_rts
        bra.w   ef_load_file

ef_st_answer:
        tstl    %d0
        beq.s   ea_rts
        moveq   #2,%d1
        cmpl    %d1,%d0
        bne.s   ea_1
        moveq   #1,%d1
        movel   %d1,ef_backup
ea_1:   clrl    ef_nowrite
        moveq   #1,%d0
        movel   %d0,ef_dirty
ea_rts: rts

        .data
        .balign 4
        .globl  ef_win, ef_steps, ef_pulses, ef_rot, ef_dest, ef_depth
        .globl  ef_cursor, ef_targets, ef_focus, ef_bank, ef_midi_bank, ef_dep_mem
        .globl  ef_dest, ef_depth, ef_pulses, ef_rot, ef_midi_dep_mem
        .globl  ef_midi_plk_mem, ef_midi_lane_mem
        .globl  ef_plk_mem, ef_lane_mem, ef_lane, ef_ppulses, ef_prot
        .globl  ef_ask, ef_unlocked, ef_from_cue, ef_cue_chord, ef_cue_snap, ef_free
        .globl  ef_cx_bank, ef_cx_bits  | CX OSC SETUP fills (stackable)
ef_win:     .long 0
ef_page_no: .long 0                    | 0=RHYTHM, 1=PITCH
ef_tone_scale: .long 0
ef_tone_root: .long 0
ef_tone_mode: .long 0
ef_tone_jump: .long 0
ef_tone_anchor:.long 0
ef_jump_index:.long 0
ef_rand_rank:.long 0
ef_rand_valid:.long 0
ef_tone_phrase:.long 0
ef_tone_harm: .long 0
ef_tone_style:.long 0
ef_tone_midi: .long 0                  | context after stock SEL_TRACK
ef_tonal_index:.long 0
ef_tonal_label:.long 0
ef_tonal_value:.long 0
ef_steps:   .long 16
ef_pulses:  .long 5                     | match filter EUCLID default
ef_rot:     .long 0
ef_ppulses: .long 0                     | current DEST plock PULSE (0=off)
ef_prot:    .long 0
ef_lane:    .long 0                     | 0=TRIG 1=PLOCK
ef_pfree:   .long 0
ef_thit:    .long 0                     | write: trig hit this step
ef_plock_on:.long 0                     | scratch: plock lane active this fill
ef_dest:    .long LOCK_PTCH             | default SRC PTCH
ef_depth:   .long 0                     | 0..127; 0 = clear DEST locks
ef_cursor:  .long 0
ef_pat_off: .long 0                     | unused (kept for slot layout)
ef_targets: .long 0
ef_focus:   .long 0                     | track whose slot is in working vars
ef_seen_trk: .long 0                    | UI_TRACK last seen by ef_follow_ui
ef_pending: .long -1                    | T1..T8 stash; -1 = none (EUCL10 unused)
ef_fill_focus: .long 0                  | scratch: focus across ef_fill
ef_fill_tgts:  .long 0                  | scratch: targets across ef_fill
ef_rng_state: .long 0                   | LCG; 0 -> seed from tempo/clock
ef_free:    .long 0                     | nonzero: draw/write ef_mask + ROT
ef_from_cue: .long 0                    | 1: free/pmask from CUE (bake may use)
ef_cue_chord: .long 0                   | 1: layer saw CUE+TRACK (no random)
ef_cue_snap: .long 0                    | cue-byte snapshot at CUE press
ef_mask:    .space 8                    | TRIG free pattern bits 0..63
ef_pmask:   .space 8                    | PLOCK free pattern bits 0..63
ef_trk:     .long 0                     | current fill target track (0..7)
ef_rx:      .long 0
ef_ry:      .long 0
ef_rstr:    .long 0
ef_px1:     .long 0                     | pattern square x1 (draw scratch)
ef_py1:     .long 0                     | pattern square y1
ef_buf:     .space 24
        .balign 4
| CX SETUP fills: 8 tracks × 64 steps × 5 slots (CAR MOD SYMM FDBK PWM).
ef_cx_bank: .space 8*CX_STEPS*CX_NSLOT
| Per step: bit0 CAR, bit1 MOD, bit2 SYMM, bit3 FDBK, bit4 PWM.
ef_cx_bits: .space 8*CX_STEPS
        .balign 4
| Per-track bank + depths + plock + lane (contiguous for EF_FILE_B).
ef_bank:
        .rept   8
        .long   5, 0, LOCK_PTCH, 0, 0
        .space  8
        .endr
ef_dep_mem:
        .space  EF_DEP_B                | 8 tracks × DEST_NSLOT depths
ef_plk_mem:
        .space  EF_PLK_B                | 8×DEST × 12 B plock slots
ef_lane_mem:
        .space  EF_LANE_B               | per-track LANE
ef_midi_bank:
        .rept   8
        .long   5, 0, 0, 0, 0
        .space  8
        .endr
ef_midi_dep_mem:
        .space  EF_MIDI_DEP_B          | 8 tracks × MIDI flat depths
ef_midi_plk_mem:
        .space  EF_MIDI_PLK_B          | 8 tracks × 30 flats × 12-byte PLOCK recipes
ef_midi_lane_mem:
        .space  EF_MIDI_LANE_B         | MIDI track LANE (0=TRIG, 1=PLOCK)
ef_tone_mem:
        .space  EF_TONE_B              | audio + MIDI tonal settings, appended v8
        .balign 4
ef_dirty:   .long 0
ef_ask:     .long 0                     | 1: ARE YOU SURE? dialog pending
ef_unlocked: .long 0                    | 1: PULSE/ROT/CUE free until next bake
ef_pending_edit: .long 0                | MIDI approval: 1=encoder, 2=CUE
ef_pending_delta: .long 0
ef_pending_cursor: .long 0
ef_dlg_guard: .long 0                   | 1: soft-close on class-5 eviction
ef_need_restore: .long 0                | 1: recreate window after dialog
ef_layer_on: .long 0                    | 1: EF_LAYER registered (LPOP even if ef_win=0)
ef_cl_nolayer: .long 0                  | 1: EF_CL_NO_LAYER pushed over CLEAR
ef_cl_sel:  .long 0                     | clear LISTPOP cursor
ef_nowrite: .long 0                     | refused file: do not overwrite
ef_backup:  .long 0                     | next write copies to euclid.bak first
ef_hdr:     .space 16                   | magic, ver, len, crc
ef_ctx:     .space 4120                 | STORE_CTX
ef_path:    .space 260
ef_psrc:    .space 260
