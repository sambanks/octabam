| CX OSC -- Buchla-flavoured complex oscillator as a DRAM unit (mono).
| GNU as, -mcpu=5475. Linked into the platform runtime; the kind table's
| FLEX/STATIC entries point at sy_render (modules/cxosc/manifest.py).
| Signature "CX", 1 in the Part's NEIGHBOR PLAYBACK column. Forked from
| Tim Hastie's FM SYNTH poly.s (timhastie/octatrick-modules v2.9 =
| 525f4b1, MIT); see modules/cxosc/NOTICE.
|
| WHAT: a FLEX track with CX OSC chosen generates a two-operator FM voice
| every frame (16 samples, rate 1.0): carrier = sin(phi_c + I *
| sin(phi_m + fb * m_prev)), then a sine fold with symmetry.
| PLAYBACK: PTCH RATO INDX FOLD SYMM FDBK. RATO is free 0.25..4 (FUNC snaps
| the classic table). FDBK scales to ~1 cycle at 127. Mono only -- T_POLY
| is cleared; stock LFO page (no VOIC/CHRD). GLIDE still slews pitch.
|
| (The upstream file also described paraphonic VOIC/CHRD paths retained in
| the source for provenance; CX OSC never arms them. Opening of that block:)
|   * a voice START (the packer's event bit 4: a sequencer trig or a live
|     CHROMATIC key) allocates one voice per note of the CHORD SHAPE --
|     the track's LFO page slot 5 byte (DEP3's storage, the "current value"
|     byte 0x80000810 + t*72 + 11, so a step lock on that slot picks the
|     shape per step), raw = shape << 2 | inversion (26 Sep 2026): 32 shapes
|     of four semitone offsets each (a VOICING in priority order, 29 Sep
|     2026; "----" is the one note), rotated into the inversion by
|     po_voicing (the bass = PTCH) -- at the record's PTCH word plus the offset,
|     each note snapped onto the quantizer's SCALE when one is set (po_snap:
|     the mask through the pinned accessor SCALE_AT, nearest degree, ties
|     down -- a MAJ shape in a minor scale comes out MIN). VOIC (current
|     value 0x80000810 + t*72 + 8, locks honoured) is the track's VOICE
|     CAP (27 Sep 2026): at most VOIC voices sound on the track, keys and
|     chords alike. With a shape a start plays the shape's first VOIC notes
|     (2, 3 or 4 of every shape) and is CHORD MEMORY (29 Sep 2026): every
|     voice of the track's previous chord is cut first, so exactly VOIC
|     voices sound and two keys never mix chords. With "----" a key is one
|     voice and VOIC is the polyphony: when the active voices (sounding or
|     releasing) plus 1 would exceed VOIC, the oldest of them is cut first
|     (releasing before sounding, po_steal), so VOIC 2 is a duophonic
|     keyboard (a third key takes the oldest). Each note then takes a free
|     voice, else the oldest releasing one, else the oldest sounding one (a
|     global allocation stamp, V_AGE);
|   * a live key (the quantizer's key hooks leave the key's index+1 in
|     qz_pkey[t] at KEYS_AT and keep the mask of held keys in qz_pmask[t])
|     tags its voices with the key; releasing the key (its bit leaves the
|     mask) puts them into RELEASE. A sequencer trig (qz_pkey[t] == 0)
|     first releases every sounding voice of the track: notes sustain
|     until the next trig;
|   * THE AMP ENVELOPE IS THE ENGINE'S (plan B, BUILD 31/32): the DSP sees ATK 0
|     / HOLD INF / REL INF on a synth track (sy_ison) and each voice, mono or
|     paraphonic, runs the live lane's ATK / HOLD / REL with the DSP's measured
|     laws (po_mono_env, po_frame): ATK a linear ramp to full in 3.85 ms x
|     2^(v/8.53) (16 frames the floor, po_atk); HOLD a timer from the START,
|     po_hold128 x frames a step (127 = INF), the note ends by itself; REL
|     exponential, tau = 0.295 ms x 2^(v/8.53) floored at 1 ms (po_relk), 127
|     = INF: the voice sustains until stolen -- except after STOP (po_stop:
|     S_ON bit 2), when INF takes the 1 ms floor so every voice reaches
|     silence and the next START is cold. A start while the voice still
|     sounds continues it phase-continuously from its level (the START rule);
|   * PITCH per voice: target = V_ROOT + (PTCH word - the word at the last
|     start), so a lock or slide or LFO on PTCH moves every voice by the
|     same interval (and each voice slews it with GLIDE, sy_slew on its own
|     V_CUR) while a new key's word does not move the voices already
|     sounding (V_ROOT absorbs the delta at each start). The word is folded
|     into the stock curve's 24-semitone range by octaves before the rate
|     arithmetic and the increment shifted back, so a chord note up to three
|     octaves above PTCH +12 keeps the stock's tuning;
|   * LEVEL (29 Sep 2026, equal power): each voice is c * gain with gain
|     Q15 as the mono voice's, its full value T_GMAX = 32768 / sqrt(VOIC)
|     latched at the start (po_gmax: 23170, 18919, 16384 at VOIC 2, 3, 4),
|     the sum doubled into the mono format exactly as the mono path does
|     (c * g << 1: the high word is the sample) with a saturating clamp only
|     (plan B: the peak limiter is gone). A single note is 3.0 / 4.8 / 6.0 dB
|     below the mono voice at VOIC 2 / 3 / 4; a VOIC 4 chord's coincident
|     peaks reach 2.0 FS and clamp. A stolen or chord-memory voice fades over
|     8 frames (state 3, T_GMAX / 8 a frame); a voice above the cap (a tail
|     from a lower VOIC, the mono voice carried in) converges on it at that
|     rate; a voice is freed below gain 64 (-54 dB re the mono voice's full
|     scale) once po_fill has ramped it there;
|   * VOIC ACROSS A NOTE (BUILD 32): a START never cuts what sounds. VOIC 1 ->
|     2..4 while the mono voice sounds: po_carry moves it into a voice record
|     (state 3, phase-continuous, its own pitch) and the chord's voices join
|     it; VOIC 2..4 -> 1: sy_warm's po_fade fades the voices over 8 frames
|     under the mono voice (po_fade_frame steps them, po_fill_add sums them
|     onto its samples) and the mono voice starts cold;
| The stock voice lifecycle is untouched: a new key restarts the DSP voice
| (the AMP and filter envelopes run over the whole mix as for a sample), a
| released last key posts the AMP release as stock. Musically: AMP ATK 0,
| HOLD INF, REL to taste -- the per-voice envelopes shape the notes.
|
| THE TUNING SYSTEM (27 Sep 2026): on a synth track PTCH is SEMITONES -- raw
| 64 = 0, one unit a semitone, -64..+63 (the page clone gives the slot that
| range and prints a signed whole number) -- and RATE is FINE, -64..+63
| cents (raw 64 = 0; the page names it FINE). sy_word turns the record's two
| halfwords into the engine's pitch word on the stock curve's scale (SEMI =
| 5 << 8 a semitone; w = 0x4000 + (ptch - 0x4000) * 5 + (fine - 0x4000) *
| 12.8), where everything below -- the mono voice, GLIDE's slew, the chords'
| intervals, po_snap -- works as before; po_rate_fold folds any word into the
| curve's +-12 semitones by octaves (the mono path shares the paraphonic
| path's folding now) and RATE never scales a synth voice (po_rate sees
| 1.0). An LFO on PTCH sweeps ONE SEMITONE per unit of depth on a synth
| track, five times the sample tracks' 0.2. Sample tracks: untouched.
|
| ALSO HERE: po_lfo3 / po_lfo3b (detours at the depth read of the LFO engine's
| two copies, 0x40003ca4 and 0x4000d03e: LFO 3's depth is read as 0 on a track
| whose playing voice is a synth, whatever VOIC -- its slots are VOIC and CHRD
| there, and LFO 3's default PMTR is PTCH, so a chord byte read as its depth
| was a pitch LFO: the same key gave a different pitch each press) and
| po_lfopage (a detour at the page resolver's LFO-descriptor load 0x40031e62:
| every synth track gets a clone of the LFO descriptor built here on first
| use, slot 2 named VOIC printing 1..4 with that range and default 1, slot 5
| named CHRD printing the shape's name, or "----" while VOIC is 1), and
| po_pgdesc (26 Sep 2026: the FM SYNTH PLAYBACK descriptor page.s returns is
| built here too, on first use, from the stock FLEX record in the image plus
| page.s's overrides -- the pinned page cave carries no stock bytes; page.s
| reaches the builder through the pointer word published before sy_render).
|
| Layout: the page clone's accessor word, code, then the tables (rato snap,
| shapes, names, po_relk, the sine table) and the RAM state (per-track
| records, 32 voice records, the LFO and PLAYBACK descriptor clones). The
| main OS runs from DRAM and so does this.

        .text
        .global sy_render, po_lfo3, po_lfo3b, po_lfopage
        .global po_mon, po_moff, po_mgate, po_mogate, po_mrec, po_mtrig
        .global po_ampstage, po_ampdraw1, po_ampdraw2, po_ampdraw3, po_ampedit, po_amplane
        .global po_assign, po_machwin, po_machlist, po_loadsel, po_stop, po_kill
        .global po_retrig
        .global po_fmstart, po_fmsource, po_is_synth, po_sig, po_signed, po_slot_marker
        .set    VOICE_BASE, 0x800049d8
        .set    VOICE_STRIDE, 0xa8
        .set    CURSOR, 0x80001c80
        .set    NIBBLE, 0x46104d0c
        .include "remix.inc"             | HK_MACHINE_ROWS: beside other machines (modules/hooks)
        .set    STOCK_RENDER, 0x40004008
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_RENDER
        .set    STOCK_RENDER, MC_NEXT_RENDER | the next renderer in the FLEX kind entry's chain
        .endif
        .endif
        .set    FMSRC_RET, 0x4000d51e    | after po_fmsource's displaced 8 B
        .set    FLEX_START, 0x4000f450   | stock FLEX START callback
        .set    MACH_OFF, 0x8eda2
        .set    SIG_OFF, 0x8edbc         | NEIGHBOR PLAYBACK: "CX", 1
        .set    FP_PTR, 0x800062a8       | the packer's per-track DSP parameter record
        .set    RS_PTR, 0x800062a4       | the packer's per-track render state
        .set    SETTINGS_BASE, 0x100b14f0 | the sample settings records, 0x448 each, slots 0..135
        .set    SETTINGS_SPAN, 0x24640    | 136 * 0x448
        .set    SETTINGS_STRIDE, 0x448
        .set    PITCH_TAB, 0x400aa294    | the stock 2^(x/12) curve, longs Q26 (index = PTCH word >> 5)
        .set    C4_INC, 25480119         | C4: 261.6256 / 44100 * 2^32
        .set    ENV_ONE, 0x01000000      | the index envelope's 1.0 (Q24)
        .set    ENV_FLOOR, 0x00100000    | it decays toward 1/16
        .set    K_NUM, 3068384           | k = K_NUM / raw^2, Q20 per frame: tau = 2 s at 127
        .set    K_MAX, 0xfffff
        .set    INDEX_SCALE, 2628        | 8 rad / 127 in cycles * 2^18 (offset = m_Q14 * I)
        .set    FB_SCALE, 2064           | 1.0 cycle / 127 * 2^16 (was 0.25; harsher mod feedback)
        .set    INC_MAX, 0x73000000      | a carrier above ~19.8 kHz (increment > 0.45 cycle a sample) is no note
                                         | of this synth: the safety net resets such a voice (24 Sep 2026; raised
                                         | from 8 kHz on 27 Sep 2026 for PTCH +63 and the octave shapes)
        .set    GLIDE_AT, 0x100b14ed     | the GLIDE byte in battery RAM (modules/quantizer/manifest.py GLIDE_AT; 0 = off)
        .set    KEYS_AT, 0x400d2cb0      | modules/quantizer/keys.s: qz_pkey[8] bytes, qz_pmask[8] longs at +8,
        .set    CLOCK_AT, KEYS_AT+40     | qz_clock at +40: where this unit publishes po_clock's address
        .set    SEQ_STEP, 0x800065b2     | the sequencer's step (word) and tick (byte, counting down) ...
        .set    SEQ_TICK, 0x800065b6     | ... the clock below counts their changes
        .set    CV_HOLD, 13              | flat slot 13 = AMP page slot 1 (HOLD): a sequencer note's gate
        .set    CK_TICKS, 0              | po_clock: ticks seen (monotonic, no pattern wrap)
        .set    CK_TPS, 4                | ticks a step (the largest tick value seen + 1; 0 = not yet)
        .set    CK_FPS, 8                | frames a step (measured between step changes; 345 until then)
        .set    CK_FRAMES, 12            | frames seen
        .set    CK_LAST, 16              | the last (step << 8 | tick)
        .set    CK_PING, 20              | (unused)
        .set    CK_STEP, 24              | the last step
        .set    CK_FSTEP, 28             | frames at the last step change
        .set    FPS_DEFAULT, 345         | 120 BPM, 1x: 60 / 120 / 4 s * 44100 / 16
        .set    SCALE_AT, 0x400d2ca8     | modules/quantizer/scale.s: `jmp qz_scale_mask` -- d0 := the scale's pitch-class mask, 0 = OFF
        .set    CURVALS, 0x80000810      | the frame builder's per-track current values, 72 B a track, locks applied
        .set    CV_STRIDE, 72
        .set    CV_CHRD, 11              | flat slot 11 = LFO page slot 5 (DEP3): the chord shape
        .set    CV_VOIC, 8               | flat slot 8 = LFO page slot 2 (SPD3): the voice count, 1..4
        .set    CV_REL, 14               | flat slot 14 = AMP page slot 2 (REL)
        .set    LFO_STATE, 0x80004858    | the LFO engine's per-track state, 8 B a track (a4 in its loop)
        .set    LFO_P, 0x400d37f6        | the stock LFO page descriptor (P form), 0x192 bytes
        .set    LFO_DESC_LEN, 0x192
        .set    FLEX_P, 0x400d31ae       | the stock FLEX PLAYBACK descriptor (P form), 0x192 bytes:
        .set    FLEX_DESC_LEN, 0x192     | the source of the page clone po_pgdesc builds for page.s
        .set    RESOLVER_RET, 0x40031ed6
        .set    SLOT_OFF, 0x8f04b        | Part: 0x8f04a + track*5 + machine (1 = FLEX)
        .set    SLOT_COL, 0x8f04a        | Part: the five slot bytes of a track, one a machine (the column the assigners index by machine)
        .set    PART_SHADOW, 0x1001614e  | the bank's mirror in battery RAM: + part * 6322 + the Part offset = the shadow of a Part byte (0x100a5198 = the slot bytes', 0x100a4ef0 = the machine's, 0x100a51c6 = the AMP page-2's)
        .set    CV_RATE, 3               | flat slot 3 = PLAYBACK slot D (RATE; FINE on a synth track)
        .set    LISTWIN_MACH, 0x460d5c30 | the sample-list window's chosen machine (its apply path 0x4005a826)
        .set    ASSIGN_RET, 0x400795c2   | the slot assigner 0x40079424: after its slot-byte write (po_assign)
        .set    MACHWIN_RET, 0x4007981e  | the machine window's apply path 0x400797cc: its machine-byte write (po_machwin)
        .set    LISTWIN_RET, 0x4005a850  | the sample-list window's apply path: its machine read (po_machlist)
        .set    LOADSEL_SPRINTF, 0x40013a08 | stock's sprintf: the browser's select 0x40022610 writes the chosen path into the slot's settings record with it (po_loadsel)
        .set    SPRINTF, 0x40013a08
        .set    SEMI, 0x500              | one semitone of the PTCH word (5 raw units << 8)
        .set    SHAPE_END, -128          | ends a shape's offsets ("----" only: every other shape has four notes)
        .set    PING_AT, 0x800000e0      | the frame builder's ping (the copier 0x4000caf4 reads it: the record set being built this frame)
        .set    DSP_REC, 0x80000110      | the DSP voice records: + (ping << 9) + 64 * track, halfwords 0/1/2 = AMP ATK / HOLD / REL (value << 8)
        .set    CV_ATK, 12               | flat slot 12 = AMP page slot 0 (ATK)
        .set    CUT_SHIFT, 3             | a stolen voice fades over 8 frames (2.9 ms): T_GMAX / 8 a frame (plan B)
        .set    GLOBAL_WORD, 0x46c80350  | the sequencer's STOP / restart word the frame builder turns into the DSP all-off (po_stop)
        .set    KILL_RET, 0x40006862     | the stock VOICE KILL 0x40006820: after its CF voice-byte clear (po_kill)
| ---- the per-track record, 128 bytes: the mono voice (0..43, synth.s's layout) and the poly frame
        .set    ST_STRIDE, 128
        .set    S_PHC, 0                 | carrier phase, Q32 cycles
        .set    S_PHM, 4                 | modulator phase
        .set    S_ENV, 8                 | index envelope, Q24
        .set    S_INC, 12                | carrier increment per sample (the true pitch)
        .set    S_INCM, 16               | modulator increment
        .set    S_IEFF, 20               | index * envelope, the per-sample multiplier -- the RUNNING value: sy_loop steps it by S_ISTEP a sample (BUILD 38)
        .set    S_GAIN, 24               | start ramp, Q15
        .set    S_FB, 28                 | feedback multiplier
        .set    S_LASTM, 32              | the modulator's last sample, Q14
        .set    S_ON, 36                 | bit 0: the playing voice is a synth; bit 1: a release (the AMP release, mailbox 0x40)
                                         | reached the frame builder since that START (po_rel; BUILD 27) -- tst.b still
                                         | means "a synth plays": bits 1 / 2 are set only while bit 0 is;
                                         | bit 2: STOPPED (po_stop, BUILD 32): a release under REL INF takes the 1 ms floor
        .set    S_GPREV, 38              | word: the gain the last rendered call ended at (sy_loop ramps S_GPREV -> S_GAIN across the call; every start clears it with the phases -- BUILD 26)
        .set    S_CUR, 40                | the slewed PTCH word, Q12 (GLIDE)
        .set    T_REF, 44                | paraphonic: the PTCH word at the last voice start
        .set    T_LAST, 48               | paraphonic: the PTCH word seen last frame
        .set    T_MASK, 52               | paraphonic: the held-key mask seen last frame
        .set    T_DK, 56                 | paraphonic: the index decay k this frame (0 = hold)
        .set    T_RK, 60                 | paraphonic: the release k this frame (Q16)
        .set    T_RATIO, 64              | paraphonic: the ratio this frame (Q8)
        .set    T_I, 68                  | paraphonic: the index I this frame
        .set    T_W, 72                  | paraphonic: this frame's PTCH word
        .set    T_SCALE, 76              | paraphonic: the scale mask at the last start (0 = OFF)
        .set    T_POLY, 80               | byte: the note that started last is paraphonic (VOIC 2..4 then)
        .set    S_ERAMP, 81              | byte: frames left of the mono voice's index-envelope ramp after a warm START (BUILD 38: sy_env_ramp; 0 = none)
        .set    RT_CALLS, 0              | po_rtlog (po_clock + 32, peekable): passes of the frame builder's DSP command-byte copy (po_retrig)
        .set    RT_FIXED, 4              | ... START bytes rewritten to the clean form 0x30
        .set    RT_HEAD, 8               | ... the ring's head
        .set    RT_RING, 16              | ... 32 entries x 8 B: {CK_FRAMES, track | byte posted << 8 | byte now << 16 | S_ON << 24}
        .set    RT_SIZE, 16 + 32 * 8
        .set    T_AK, 82                 | word: paraphonic: the attack step a frame this frame, Q15, at most 2048 (plan B; it was .set 104 inside T_POS 92..111 until BUILD 32 -- benign only because po_frame runs after the marker save and before its restore)
        .set    T_GMAX, 84               | paraphonic: a voice's full gain, Q15 = 32768 / sqrt(VOIC) at the last start
        .set    S_HTIM, 88               | the mono voice's HOLD timer: frames left before it releases by itself (0 = none; plan B)
                                         | (+88 was T_LIM, the peak limiter's gain, until plan B removed the limiter)
        .set    T_RAWP, 112              | the record's PTCH raw (halfword >> 8) at this frame's second call, before the neutralising (MIDI IN, 30 Sep 2026: po_start's per-note pitch)
        .set    T_SMASK, 116             | paraphonic: the held keys that got their voice (or were dropped by the cap) since their press (the same-scan sweep, 26 Sep 2026)
        .set    T_LASTK, 120             | paraphonic: the frame of the last live panel-key start (a key within KR_WIN of it is a chord press)
                                         | FOLD/SYMM live in sy_cxparm[t] -- NOT here: +124/+126 are T_LEGKEY/T_LEGN and S_ISTEP
        .set    T_POS, 92                | the marker's sample positions (voice +64..+83) before the stock call, restored after it: a synth voice never reaches the marker's end
        .set    V_POS, 64                | the voice struct's sample position fields: +64 window base, +68 position, +72/+76 the stream's, +80 frames left in the fetched chunk
        .set    PART_PTR, 0x46c82456     | the bank blob; the Part = blob + part index * 6322
        .set    PART_IDX, 0x100b14cf
        .set    UI_TRACK, 0x100b14cc
        .set    LFO_PAGE_OFF, 0x8ee9a    | the Part's LFO page bytes, 24 a track: +2 = VOIC, +5 = CHRD
| ---- a voice record, 64 bytes (the first 36 match the mono voice's fields)
        .set    V_STRIDE, 64
        .set    V_PHC, 0
        .set    V_PHM, 4
        .set    V_ENV, 8
        .set    V_INC, 12
        .set    V_INCM, 16
        .set    V_IEFF, 20               | the running I * E (po_fi_loop steps it by V_ISTEP a sample; BUILD 38)
        .set    V_GAIN, 24               | Q15 (the mono voice's S_GAIN format), at most T_GMAX
        .set    V_FB, 28
        .set    V_LASTM, 32
        .set    V_STATE, 36              | 0 free, 1 sounding, 2 releasing, 3 fading (stolen / chord-memory cut: T_GMAX / 8 a frame, plan B)
        .set    V_KEY, 37                | the live key's index + 1, 0 = a sequencer note
        .set    V_ISTEP, 38              | word: the per-sample step of V_IEFF this frame, (I * E - V_IEFF) / 16 (po_frame writes, po_fill consumes; BUILD 38)
        .set    V_CUR, 40                | the slewed word, Q12 (sy_slew's S_CUR)
        .set    V_ROOT, 44               | the note's word, Q8, relative to T_REF
        .set    V_AGE, 48                | the allocation stamp
        .set    V_HOLD, 52               | a sequencer note: frames left before it releases (0 = no gate)
        .set    V_FRAME, 56              | the frame (po_clock CK_FRAMES) the voice was allocated at (26 Sep 2026)
        .set    V_GPREV, 60              | word: the gain the last rendered frame ended at (po_fill ramps V_GPREV -> V_GAIN across a frame; 0 = the voice has been silent: a start resets the phases; a long until BUILD 38)
        .set    V_ERAMP, 62              | word: frames left of the voice's index-envelope ramp to ENV_ONE after a warm START (po_frame; BUILD 38; 0 = none)
| ---- the chord record (po_keyrec, 26 Sep 2026; 32 bytes a track since the rolling window) --
        .set    CR_STRIDE, 32
        .set    CR_STEP, 0               | the step the chord's first key was recorded on
        .set    CR_N, 1                  | keys in the record, 0 = none
        .set    CR_WROTE, 2              | CHRD/VOIC locks written on CR_STEP by this record
        .set    CR_PKEY, 3               | the key whose join is still provisional (its identity; 0 = none): the hand-over rule
        .set    CR_FRAME, 4              | the frame of the LAST key that joined (the window rolls from it)
        .set    CR_KEYS, 8               | the keys' identities (index + 1, or 0x80 | note), the first key first
        .set    CR_RAWS, 12              | their raw pitches (64 = 0 semitones, snapped)
        .set    CR_PFRAME, 16            | the provisional key's press frame
        .set    CR_PCTX, 20              | ... the recorder's context word at its press (REC_TRIG places its trig at that time)
        .set    CR_PTICKS, 24            | ... the sequencer ticks at its press (its HOLD slot, should it get its own trig)
        .set    CR_PRAW, 28              | ... its raw
        .set    CR_VOIC, 29              | the Part's VOIC read at the last call (the VOIC lock is min(keys, VOIC))
        .set    KR_WIN, 413              | the join window: 150 ms of frames (44.1 kHz / 16), rolling from the last joined key
        .set    KR_CONF, 138             | the hand-over check: a join stands once both keys were down 50 ms after it
        .set    LIVEREC_AT, 0x460d172a   | nonzero while the recorder's block runs (LIVE RECORDING, or a trig held); 0 = the records are stale
        .set    QZ_OCT_AT, KEYS_AT+44    | modules/quantizer/keys.s qz_oct: a synth track's CHROMATIC octave, -4..+4 (0 without the quantizer)
        .set    REC_TRIG, 0x40042d1c     | (track, ctx): the live recorder places a sample trig at the context's time -> the step, -1 = none
        .set    PAT_RAM, 0x400e21e0       | the patterns in RAM: + (track * 1165 + bank * 317856 + pattern * 18284) * 2 = the track's record (2330 B)
        .set    PAT_MIR, 0x1001614e       | the current bank's mirror in battery RAM: + (track * 1165 + pattern * 18284) * 2
        .set    PAT_NUDGE, 1101          | ... + (step + 1101) * 2: the step's word, whose bits 7..12 nudge the trig in 1/48 step (REC_TRIG's fp@(-1))
        .set    PAT_CUR, 0x80000004      | the current pattern (the byte REC_TRIG compares the context's pattern with) ...
        .set    BANK_CUR, 0x80000002     | ... and bank
        .set    LOCK_WRITE, 0x40042158   | (track, flat slot, value, step, ctx): the stock p-lock writer, as the quantizer's qz_holdrel calls it
        .set    REC_CTX, 0x46c7e956      | the recorder's context word the chromatic key handler passes it
        .set    CV_PTCH, 0               | flat slot 0 = PLAYBACK slot A (PTCH)
| ---- LEG (2 Oct 2026): the AMP SETUP page's sixth box on a synth track -----------
        .set    AMP_P, 0x400d3988        | the stock AMP descriptor (P form), 0x192 bytes: the source of the clone po_amp_desc builds
        .set    AMP_DESC_LEN, 0x192
        .set    AMP_P2_OFF, 0x8f078      | Part: the AMP page-2 bytes, 30 a track (AMP SYNC ATCK FX1 FX2 TRIG); +5 = LEG (slot 11, TRIG's byte)
        .set    LEG_SLOT2, 5
        .set    LEG_WIDGET, 0x40046d9c   | the three-position select of the PLAYBACK page (the AMP box uses its four-position sibling): OFF / MONO / POLY, the value always printed
        .set    MASTER_ON, 0x80000034    | nonzero: track 8 is the MASTER track (the page resolver's tst.b; its AMP page is another record)
        .set    REC_TRIGLESS, 0x4004271c | (track, ctx): the live recorder places a TRIGLESS trig (FUNC + key's) -> the step, -1 = none
        .set    T_LEGKEY, 124            | paraphonic legato: the identity handed over (po_legkey), 0 = none (a byte)
                                         | (+126..127, the record's last word: BUILD 24/25's S_LASTF frame stamp, the warm test; free since BUILD 26 -- every start is cold)
        .set    T_LEGN, 125              | ... frames waited for its PTCH lock to land (a byte)
        .set    S_ISTEP, 126             | word: the mono voice's per-sample step of S_IEFF this call, (I * E - S_IEFF) / 16 (BUILD 38: sy_loop
                                         | ramps the index across the frame; +126 / +127 were S_HOLD / S_KEYED, BUILD 27/28's record, dead since plan B)
        .set    T_MLEG, 37               | MIDI IN: the last note-on took the legato path (po_mrec records it trigless; a byte -- the byte after S_ON, free: S_ON is a byte, S_GPREV the word at +38; it was +126 until BUILD 25, aliasing the then S_LASTF word)
| ---- the FM SYNTH page's knob handler (po_knob, 30 Sep 2026) -------------------
        .set    FUNC_HELD, 0x46c7dd26     | nonzero while [FUNCTION] is down (the stock handlers' tst.l)
        .set    FUNC_ENC_OFF, 0x800000a0  | PERSONALIZE: DISABLE FUNCTION + ENCODER (the stock handlers' gate)
        .set    KEY_HELD, 0x46c7d8de+0x10 | + code * 0x18: nonzero while that key is held (PANEL.md)
        .set    PUSH_CODE, 0x38           | the encoder push switches: key codes 0x38..0x3d = A..F
        .set    KN_SLOTS, 0x12a           | the descriptor's six knob handler pointers
        .set    KN_RATIO, 1               | slot B = RATO
        .set    KN_RATO_SPAN, 960         | Q8 span 0.25..4: 1024 - 64
        .set    KN_RATO_MAX, 127          | raw 0..127
        .set    KN_RATO_SNAPS, 16         | classic table entries with ratio <= 4.01
        .set    KN_RATO_HALF, 480         | SPAN/2, for rounding snap -> raw

| ---- the page clone's accessor, published one long BEFORE sy_render -----------
| The kind table's FLEX entry 0x400d6438 holds sy_render's address (the
| manifest's SymbolRef), the one address of this unit the ROM knows. page.s,
| pinned in ROM and ignorant of where the runtime lands, reaches po_pgdesc as
| `movea.l 0x400d6438,%a0; movea.l -4(%a0),%a0; jsr (%a0)` (26 Sep 2026).
        .align  4
        .long   po_octave                | -32: FUNC + UP / DOWN with a trig held: the held steps' PTCH lock moves an octave (the hook at 0x40051fce; published for the record, 4 Oct 2026)
        .long   po_legkey                | -28: a legato press on a paraphonic synth track: the sounding chord follows this key (the quantizer's qz_leg2, 2 Oct 2026)
        .long   po_legmode               | -24: the LEG gate for track d2 (the quantizer's qz_leg1 / qz_leg2): 0 stock, 1 mono legato, 2 paraphonic, 3 paraphonic legato
        .long   po_keyrel                | -20: a CHROMATIC key released while recording (the quantizer's qz_holdrel, 26 Sep 2026: the hand-over rule)
        .long   po_knob                  | -16: the FM SYNTH page's knob handler (po_pgdesc plants it in the clone's six slots; published for the record)
        .long   po_keyrec                | -12: a CHROMATIC key recorded (the quantizer's qz_leg5, 26 Sep 2026)
        .long   po_hold128               | -8: the AMP HOLD table (the quantizer's qz_holdrel reads it here since 26 Sep 2026)
        .long   po_pgdesc                | -4: the PLAYBACK descriptor clone (page.s)
| ---- sy_render(track, ping, start, end) ------------------------------------
sy_render:
        lea     -48(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)    | 44(sp) the stock return; args 52 track, 56 ping, 60 start, 64 end
        move.l  CURSOR,%a2               | the header this call writes
        move.l  52(%sp),%d2              | track
        move.l  %d2,%d3
        lsl.l   #7,%d3
        lea     sy_state(%pc),%a3
        add.l   %d3,%a3                  | a3 = this track's record
        move.l  FP_PTR,%a4               | a4 = its DSP parameter record
        moveq   #0,%d4                   | 1 = the fp words are neutralised for the stock call
        moveq   #16,%d1
        cmp.l   64(%sp),%d1              | the frame's second call?
        bne     sy_call
        lea     NIBBLE,%a0
        lea     (%a0,%d2.l),%a0
        btst    #4,(%a0)                 | a voice starts this frame
        beq     sy_ison
        bsr     sy_machine               | d0 := the track's machine (clobbers d0, d1, a0)
        subq.l  #1,%d0
        bne     sy_no                    | not FLEX: sample
        bsr     po_signed                | CX OSC chosen in the machine list?
        beq     sy_no                    | not chosen: sample (marker path off)
sy_cold:                                 | a synth starts -- THE START RULE (plan B, 28 Sep 2026): the engine owns
        move.l  #CV_STRIDE,%d1           | the AMP envelope (the DSP sees ATK 0 / HOLD INF / REL INF: sy_ison), so
        muls.l  %d2,%d1                  | the only question is whether THIS voice still sounds. S_GPREV != 0 (the
        lea     CURVALS,%a0              | gain the last call ended at): WARM -- the SAME oscillator continues
        mvz.b   CV_HOLD(%a0,%d1.l),%d1   | phase-continuously at its current level, the pitch changes, the attack
                                         | re-runs from that level (an analog mono synth's retrigger), and the index
                                         | envelope RAMPS from its level to ENV_ONE over 16 frames (BUILD 38). S_GPREV
                                         | == 0: COLD -- both operators at phase 0, the gain ramps from 0 (the ATK law,
                                         | the 16-frame ramp its floor), the index envelope restarts at once (from
                                         | silence: inaudible). BUILD 27/28's four-condition rule (S_HOLD, S_KEYED,
                                         | the released flag) is gone: the DSP no longer restarts or
        cmpi.l  #127,%d1                 | releases anything. The HOLD the live lane holds now (the lock, else the
        beq     sy_cold_nohold           | Part's) arms the mono HOLD timer: 127 = INF (none), else po_hold128 steps
        lea     po_hold128(%pc),%a0      | in 1/128 x frames a step (the DSP's own timer runs from the START at that
        mvz.w   (%a0,%d1.l*2),%d1        | length, stage 1: HOLD 32 = 282 ms at 120 BPM, a key held or not), and its
        lea     po_clock(%pc),%a0        | end starts the release (po_mono_env). (S_HOLD / S_KEYED went with BUILD 38: S_ISTEP has +126.)
        move.l  CK_FPS(%a0),%d0
        mulu.l  %d0,%d1
        lsr.l   #7,%d1
        addq.l  #1,%d1
        bra     sy_cold_hold
sy_cold_nohold:
        moveq   #0,%d1
sy_cold_hold:
        move.l  %d1,S_HTIM(%a3)
        tst.w   S_GPREV(%a3)
        bne     sy_warm_env              | sounding: continuous
sy_cold1:
        clr.l   S_PHC(%a3)               | silent: phase 0, the gain from 0
        clr.l   S_PHM(%a3)
        clr.l   S_LASTM(%a3)
        clr.l   S_GAIN(%a3)
        clr.w   S_GPREV(%a3)
        clr.l   S_IEFF(%a3)              | the index climbs to I * E within the first frame, under the gain from 0
        clr.b   S_ERAMP(%a3)
        move.l  #ENV_ONE,%d1             | the index envelope restarts at once (BUILD 38: only cold)
        move.l  %d1,S_ENV(%a3)
        bra     sy_warm
sy_warm_env:
        move.b  #16,S_ERAMP(%a3)         | warm: the index envelope ramps from its level to ENV_ONE over 16 frames
sy_warm:                                 | (sy_env_ramp, 5.8 ms), the carrier and the level continuous (BUILD 38)
        move.l  RS_PTR,%a0
        clr.l   4(%a0)                   | the retrig count the packer just latched: no stock retrigs
        clr.b   T_POLY(%a3)              | CX OSC: mono only -- LFO 3 stays SPD3/DEP3 (no VOIC/CHRD)
        bsr     po_fade
        bsr     po_mring_reset
        lea     KEYS_AT,%a0
        clr.b   (%a0,%d2.l)
sy_synth:
        bsr     sy_word                  | a fresh note starts at its own pitch: no slide (GLIDE)
        move.l  %d6,%d1
        lsl.l   #8,%d1
        lsl.l   #4,%d1
        move.l  %d1,S_CUR(%a3)
        moveq   #1,%d3
        bra     sy_set
sy_no:
        bsr     po_free                  | not a synth: nothing of ours may sound on this track
        clr.w   S_GPREV(%a3)             | (the mono voice is silent too)
        lea     KEYS_AT,%a0              | the identity the quantizer posted for this START (a CHROMATIC key on
        clr.b   (%a0,%d2.l)              | any track since BUILD 28) is consumed: nothing stale for a later synth START
        mvz.w   (%a4),%d1                | a sample START (2.8): its pitch is its own -- S_CUR snaps to the
        lsl.l   #8,%d1                   | record's PTCH word (a lock on the trig lands here; no slide from
        lsl.l   #4,%d1                   | the previous note); the changes that follow slide from it (sy_sample)
        move.l  %d1,S_CUR(%a3)
        moveq   #0,%d3
sy_set:
        move.b  %d3,S_ON(%a3)
sy_ison:
        tst.b   S_ON(%a3)
        beq     sy_sample
        lea     CURVALS,%a0              | LEG (2 Oct 2026): the track's live lane 0x80000810 + t * 72 holds the
        move.l  #CV_STRIDE,%d1           | Part's AMP page-2 bytes at +0x2c; byte 5 (+0x31, LEG) is what the copier
        muls.l  %d2,%d1                  | 0x4000cb6a carries into the DSP record's AMP word 23, low byte, every
        clr.b   0x31(%a0,%d1.l)          | frame. Zeroed here while a synth voice plays (not restored: that copy is
                                         | the lane byte's only reader), the DSP sees 0 there, as a stock Part's TRIG
                                         | byte is; the page-2 editor never writes it into a synth track's lane
                                         | (po_amplane), the frame builder's part refresh does, until the next frame.
        move.l  PING_AT,%d1              | THE DSP-FACING OVERRIDE (plan B): the DSP voice record of this track
        andi.l  #1,%d1                   | and the frame builder's ping (0x800000e0, the copier's: sy_render's own
        lsl.l   #8,%d1                   | 56(sp) is 0x800000e4, another word), 0x80000110 + (ping << 9) + 64 *
        lsl.l   #1,%d1                   | track, halfwords 0/1/2 (AMP ATK / HOLD / REL, value << 8) := 0 / 0x7f00 / 0x7f00 -- ATK 0, HOLD INF,
        move.l  %d2,%d0                  | REL INF: the DSP's envelope opens on the START frame's first sample and
        lsl.l   #6,%d0                   | never moves again (stage 1: no fade 2 s after a note-off, +-0.3 dB across
        add.l   %d0,%d1                  | re-triggers). Every synth call, after the copier, the scene morph and the
        lea     DSP_REC,%a0              | LFO stage (all before the render loop) and before the DMA; nothing reads
        add.l   %d1,%a0                  | these halfwords after the render loop, so nothing is restored, and the
        clr.w   (%a0)                    | live lane the UI shows (0x80000810 + 72 t + 12..14) is never touched --
        move.w  #0x7f00,2(%a0)           | the same shape as the PTCH / RATE override of the CF record below. The
        move.w  #0x7f00,4(%a0)           | engine applies the lane's ATK / HOLD / REL itself (po_mono_env, po_frame).
        mvz.w   6(%a4),%d5               | the RATE (FINE) halfword, restored for the DSP after the call
        mvz.w   (%a4),%d1
        lsr.l   #8,%d1
        move.l  %d1,T_RAWP(%a3)          | the PTCH raw this frame (the halfword holds the WORD after the call)
        bsr     sy_word                  | d6 := the pitch word (PTCH + FINE, the curve's scale; clobbers d0, d1)
        tst.b   T_POLY(%a3)
        bne     sy_neutral               | paraphonic: the voices slew on their own (po_frame)
        bsr     sy_slew                  | GLIDE: d6 := the word slewed toward it
sy_neutral:
        move.w  #0x4000,(%a4)            | the stock renderer computes rate 1.0 from these
        move.w  #0x7f00,6(%a4)
        moveq   #1,%d4
        bsr     sy_voice                 | a0 = the voice's position fields: kept for after the call
        lea     T_POS(%a3),%a1           | (the stock renderer advances them at rate 1.0 and ends the
        move.l  (%a0)+,(%a1)+            | voice at the marker's end; a synth note ends through the
        move.l  (%a0)+,(%a1)+            | AMP envelope or a key release, so the marker stays put)
        move.l  (%a0)+,(%a1)+
        move.l  (%a0)+,(%a1)+
        move.l  (%a0)+,(%a1)+
        bra     sy_call

| ---- a sample track (FLEX, or STATIC since 2.8): PITCH SLIDES ---------------
| The frame's second call on a track whose playing voice is a sample. The
| record's PTCH word (raw << 8 with the LFO's fraction in the low byte; the
| curve's scale, 5 raw units a semitone) is the TARGET: sy_slew moves S_CUR
| toward it over GLIDE -- snapped at a sample start (sy_no) and whenever GLIDE
| is 0 or the track's LEG is OFF (stock's instant pitch) -- and the slewed
| word replaces the record's for the stock call. The stock rate arithmetic
| (0x40004008; docs/firmware/REPITCH.md) reads the word from the record on
| this call, so the increment it builds -- shared by the source supplier and
| the DSP voice command -- follows the slide. Nothing is restored after the
| call: the record holds what stock leaves there, as on a stock unit. A live
| legato key (LEG MONO: the trigless path), a sequenced trigless trig's PTCH
| lock, a knob turn or an LFO all arrive as the record's word changing
| between starts, so they all slide; a sample trig's lock lands at a start
| and snaps.
sy_sample:
        mvz.w   (%a4),%d6                | the target: the record's PTCH word
        bsr     sy_slew                  | d6 := the word slewed toward it (clobbers d0, d1, d3, d7, a0)
        move.w  %d6,(%a4)                | the stock rate arithmetic reads the slewed word
sy_call:
        bsr     po_signed                | CX OSC in the list: no sample -- write the source header
        beq     sy_stock                 | stock would (count, ring, rate 1.0) and silent pairs
        move.l  64(%sp),%d0
        sub.l   60(%sp),%d0
        move.l  %d0,(%a2)
        move.l  60(%sp),4(%a2)
        move.l  #0x04000000,%d1
        move.l  %d1,8(%a2)
        move.l  60(%sp),%d1
        lsl.l   #8,%d1
        lsl.l   #8,%d1
        lsl.l   #8,%d1
        lsl.l   #2,%d1
        move.l  %d1,12(%a2)
        lea     16(%a2),%a0
        add.l   %d0,%d0
        beq     sy_nat_end
sy_nat_clr:
        clr.l   (%a0)+
        subq.l  #1,%d0
        bne     sy_nat_clr
sy_nat_end:
        move.l  %a0,CURSOR
        moveq   #0,%d0
        bra     sy_called
sy_stock:
        move.l  64(%sp),-(%sp)
        move.l  64(%sp),-(%sp)
        move.l  64(%sp),-(%sp)
        move.l  64(%sp),-(%sp)
        jsr     STOCK_RENDER
        lea     16(%sp),%sp
sy_called:
        move.l  %d0,44(%sp)
        tst.l   %d4
        beq     sy_check
        move.w  %d6,(%a4)
        move.w  %d5,6(%a4)
        bsr     sy_voice
        lea     T_POS(%a3),%a1
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        bra     sy_mono_frame            | mono only

| ---- sy_voice: a0 := track d2's voice struct + V_POS (clobbers d1) ----------
sy_voice:
        move.l  #VOICE_STRIDE,%d1
        muls.l  %d2,%d1
        lea     VOICE_BASE,%a0
        add.l   %d1,%a0
        lea     V_POS(%a0),%a0
        rts

| ---- sy_machine: d0 := track d2's machine (the Part's byte: 0 STATIC, 1 FLEX, 2
| THRU, 3 NEIGHBOR, 4 PICKUP; po_is_synth's read). Clobbers d0, d1, a0. ---------
sy_machine:
        movea.l PART_PTR,%a0
        mvz.b   PART_IDX,%d0
        move.l  #6322,%d1
        muls.l  %d1,%d0
        adda.l  %d0,%a0                  | the Part
        adda.l  #MACH_OFF,%a0
        mvz.b   (%a0,%d2.l),%d0
        rts

| ---- the mono voice's frame: the rate, as the stock renderer computes it -----
sy_mono_frame:
        bsr     po_fade_frame            | paraphonic voices fading under the mono voice: their envelope (BUILD 32)
        bsr     po_rate_fold             | d0 = the increment for the word d6, any octave (clobbers d0/d1/d3/d4/d7/a0)
        cmpi.l  #INC_MAX,%d0             | safety net: an impossible pitch (a word off the curve's
        bls     sy_mono_inc              | table, a stale record) silences the voice instead of
        moveq   #0,%d0                   | playing garbage -- increment 0, gain 0 (the ramp
        clr.l   S_GAIN(%a3)              | recovers as soon as the word is sane again)
        clr.l   S_IEFF(%a3)
sy_mono_inc:
        move.l  %d0,S_INC(%a3)           | carrier increment: the true pitch

| ---- the parameters ---------------------------------------------------------
        move.l  %d0,-(%sp)               | park carrier inc (sy_rato_q8 clobbers d0)
        mvz.w   2(%a4),%d1               | STRT -> ratio (free: raw 0..127 -> Q8 0.25..16)
        lsr.l   #8,%d1
        bsr     sy_rato_q8               | d1 := Q8
        move.l  (%sp)+,%d0
        asr.l   #8,%d0
        muls.l  %d1,%d0
        move.l  %d0,S_INCM(%a3)          | modulator increment = ratio * pitch
        mvz.w   6(%a4),%d1               | RATE -> FOLD raw (sy_cxparm: not S_ISTEP / T_LEG*)
        lsr.l   #8,%d1
        move.l  %d2,%d0                  | track (still in d2 here)
        lea     sy_cxparm(%pc),%a0
        move.b  %d1,(%a0,%d0.l*2)        | FOLD
        mvz.w   8(%a4),%d1               | RTRG -> SYMM raw
        lsr.l   #8,%d1
        move.b  %d1,1(%a0,%d0.l*2)       | SYMM
        mvz.w   10(%a4),%d1              | RTIM -> feedback (FDBK)
        move.l  #FB_SCALE,%d0
        mulu.l  %d0,%d1
        lsr.l   #8,%d1
        move.l  %d1,S_FB(%a3)
        mvz.b   S_ERAMP(%a3),%d1         | a warm START's ramp (BUILD 38): the remaining distance to ENV_ONE over
        beq     sy_env_k                 | the remaining frames -- linear, ENV_ONE exactly at the last; the decay
        move.l  #ENV_ONE,%d0             | waits for it
        sub.l   S_ENV(%a3),%d0
        divs.l  %d1,%d0
        add.l   %d0,S_ENV(%a3)
        subq.l  #1,%d1
        move.b  %d1,S_ERAMP(%a3)
        bra     sy_envdone
sy_env_k:
sy_nodecay:
        | CX OSC: index env HOLD (drone with INDX; LFO/plock for motion — no DEC)
        move.l  #ENV_ONE,%d1
        move.l  %d1,S_ENV(%a3)
sy_envdone:
        mvz.w   4(%a4),%d1               | LEN -> index
        move.l  #INDEX_SCALE,%d0
        mulu.l  %d0,%d1
        lsr.l   #8,%d1                   | I (raw * 2628, fractions count)
        move.l  S_ENV(%a3),%d2
        lsr.l   #8,%d2
        lsr.l   #4,%d2                   | E, 0..4096
        mulu.l  %d2,%d1
        lsr.l   #8,%d1
        lsr.l   #4,%d1                   | I * E: this call's target
        sub.l   S_IEFF(%a3),%d1          | ... minus the running value: sy_loop ramps S_IEFF there across the
        moveq   #16,%d2                  | frame, (target - running) / 16 a sample (BUILD 38: no step at a frame
        divs.l  %d2,%d1                  | edge when the index moves -- the ramp, the decay, a knob)
        move.w  %d1,S_ISTEP(%a3)
        move.l  52(%sp),%d2              | track (d2 was RTIM above)
        bsr     po_mono_env              | the mono voice's AMP envelope (plan B): S_GAIN := the level this frame ends at
        bra     sy_check                 | (po_mono_env's body follows: not fall-through)

| ---- po_mono_env: the mono voice's AMP envelope, once a frame (plan B) -----------
| a3 = the track record, d2 = track. The level S_GAIN (Q15, full 32768; sy_loop
| ramps S_GPREV -> S_GAIN linearly across the call) follows the live lane's AMP
| bytes (CURVALS + 72 t + 12 / 13 / 14: locks, scenes and LFOs applied by the frame
| builder before the render loop) with the DSP's own laws as measured (stage 1):
|   RELEASING (S_ON bit 1: po_rel for every note-off path -- the panel key's
|     release, MIDI note-off, the sequencer's -- or the HOLD timer below, or
|     po_stop): gain -= gain * k, k = po_relk[REL] (Q16 a frame: tau = 0.295 ms x
|     2^(REL / 8.53), at least 1 ms -- Tim's ~2 ms minimum fade even at REL 0;
|     127 = INF, holds); a step below 1 still makes progress; at or under 64
|     (-54 dB) the voice is silent (0; its next START is cold).
|   SOUNDING with a finite HOLD (S_HTIM, armed by sy_cold from the lane's HOLD
|     at the START): the timer runs out -> the release starts by itself (the
|     DSP's hold ends inside the DSP with no note-off anywhere: this is that).
|   SOUNDING: gain += po_atk[ATK] (Q15 a frame: a LINEAR ramp to full in 3.85 ms x
|     2^(ATK / 8.53), the 16-frame ramp its floor, the step at least 1), capped
|     at full -- from wherever the level is (a warm START re-attacks from its
|     current level; a cold one from 0).
| Clobbers d0, d1, a0.
po_mono_env:
        move.l  S_GAIN(%a3),%d1
        move.l  #CV_STRIDE,%d0
        muls.l  %d2,%d0
        lea     CURVALS,%a0
        add.l   %d0,%a0                  | a0 = the track's live lane
        btst    #1,S_ON(%a3)
        bne     po_me_rel
        move.l  S_HTIM(%a3),%d0          | the HOLD timer
        beq     po_me_atk
        subq.l  #1,%d0
        move.l  %d0,S_HTIM(%a3)
        bne     po_me_atk
        bset    #1,S_ON(%a3)             | the hold ran out: release
        bra     po_me_rel
po_me_atk:
        mvz.b   CV_ATK(%a0),%d0
        lea     po_atk(%pc),%a0
        mvz.w   (%a0,%d0.l*2),%d0
        add.l   %d0,%d1
        cmpi.l  #32768,%d1
        ble     po_me_store
        move.l  #32768,%d1
        bra     po_me_store
po_me_rel:
        mvz.b   CV_REL(%a0),%d0
        lea     po_relk(%pc),%a0
        mvz.w   (%a0,%d0.l*2),%d0        | k, Q16 (0 = INF)
        bne     po_me_rel0
        btst    #2,S_ON(%a3)             | INF holds -- unless STOPPED (po_stop): the floor, tau 1 ms, so the
        beq     po_me_store              | voice reaches silence and the next START is cold (BUILD 32)
        mvz.w   (%a0),%d0                | po_relk[0]
po_me_rel0:
        move.l  %d1,%a0
        mulu.l  %d0,%d1
        lsr.l   #8,%d1
        lsr.l   #8,%d1                   | gain * k
        bne     po_me_rel1
        moveq   #1,%d1
po_me_rel1:
        move.l  %a0,%d0
        sub.l   %d1,%d0
        move.l  %d0,%d1
        cmpi.l  #64,%d1                  | -54 dB: silent
        bgt     po_me_store
        moveq   #0,%d1
po_me_store:
        move.l  %d1,S_GAIN(%a3)
        rts

| ---- the samples --------------------------------------------------------------
sy_check:
        tst.b   S_ON(%a3)
        beq     sy_done
        move.l  52(%sp),%d2              | track (the rate block used d2)
        move.l  #VOICE_STRIDE,%d3
        muls.l  %d2,%d3
        lea     VOICE_BASE,%a0
        tst.b   (%a0,%d3.l)              | the CF voice ended: leave stock's silence ...
        bne     sy_alive
        clr.w   S_GPREV(%a3)             | (the mono voice is silent: its next start resets the phases)
        tst.b   T_POLY(%a3)
        beq     sy_done
        bsr     po_free                  | ... and free the paraphonic voices: their owner is gone
        bra     sy_done
sy_alive:
        mvz.b   3(%a2),%d7               | source samples shipped by this call
        beq     sy_done
        lea     16(%a2),%a1              | their first L long
        tst.b   T_POLY(%a3)
        beq     sy_mono
        clr.w   S_GPREV(%a3)             | paraphonic: the mono voice is silent (a VOIC change mid-note carried it into a voice: po_carry) ...
        bra     po_fill                  | ... sum the voices (ends at sy_done)
sy_mono:
        move.l  %a2,-(%sp)               | the header: sy_gend's pass over the fading voices reads it (popped there)
        move.l  56(%sp),%d1              | track -> FOLD<<8|SYMM on the stack (sy_cxparm; not the S_ISTEP word)
        lea     sy_cxparm(%pc),%a6
        mvz.w   (%a6,%d1.l*2),%d1
        move.l  %d1,-(%sp)               | 0(sp) = cxparm, 4(sp) = header
        move.l  S_PHC(%a3),%d0
        move.l  S_PHM(%a3),%d6
        move.l  S_INC(%a3),%d5
        move.l  S_INCM(%a3),%a2
        move.l  S_LASTM(%a3),%a4
        move.l  S_GAIN(%a3),%d1          | the frame's target gain ...
        mvz.w   S_GPREV(%a3),%d2         | ... from the gain the last call ended at (a first call [0,n) has
        sub.l   %d2,%d1                  | target == previous: constant; the second call ramps toward the target)
        moveq   #15,%d3
        lsl.l   %d3,%d1                  | (target - previous) << 15 ...
        asr.l   #4,%d1                   | ... / 16 = the step a sample at the FRAME's slope (BUILD 26: it was / the
        move.l  %d1,%a6                  | call's samples -- a sequencer trig splits every frame at its sub-frame
                                         | offset, so the second call had the frame's whole 2048 step over its few
                                         | samples: a stair, measured 103 steps/s on 16th trigs; now a short call
                                         | ramps part of the way and the next call carries on from where it
                                         | ended, S_GPREV = the gain reached, stored after the loop)
                                         | (a5, a6 are restored by sy_done)
        lsl.l   %d3,%d2
        move.l  %d2,%a5                  | the running gain, gain << 15: its high word is gain / 2 (full scale
                                         | 16384: the 16 x 16 multiply below takes it; 32768 would not fit)
        lea     sy_tab(%pc),%a0
        moveq   #24,%d3
sy_loop:
        move.l  %a4,%d1
        muls.l  S_FB(%a3),%d1            | feedback: m_prev * fb
        add.l   %d6,%d1                  | modulator phase
        move.l  %d1,%d2
        lsr.l   %d3,%d2
        add.l   %d2,%d2
        mvs.w   (%a0,%d2.l),%d4          | a = tab[i]
        mvs.w   2(%a0,%d2.l),%d2         | b = tab[i+1]
        sub.l   %d4,%d2
        lsr.l   #8,%d1
        mvz.w   %d1,%d1                  | fraction, Q16
        muls.l  %d1,%d2
        asr.l   #8,%d2
        asr.l   #8,%d2
        add.l   %d2,%d4                  | m, Q14
        move.l  %d4,%a4                  | m_prev
        mvs.w   S_ISTEP(%a3),%d1         | the index one step on (a linear ramp across the frame; BUILD 38)
        add.l   S_IEFF(%a3),%d1
        move.l  %d1,S_IEFF(%a3)
        muls.l  %d1,%d4                  | m * I: the phase offset, Q32 cycles (wraps: it is a phase)
        add.l   %d0,%d4                  | carrier phase, modulated
        move.l  %d4,%d2
        lsr.l   %d3,%d2
        add.l   %d2,%d2
        mvs.w   (%a0,%d2.l),%d1          | a
        mvs.w   2(%a0,%d2.l),%d2         | b
        sub.l   %d1,%d2
        lsr.l   #8,%d4
        mvz.w   %d4,%d4
        muls.l  %d4,%d2
        asr.l   #8,%d2
        asr.l   #8,%d2
        add.l   %d2,%d1                  | c, Q14 (+-0x4000 = -6 dBFS)
        | ---- FOLD (RATE) + SYMM (RTRG): sine fold with Buchla-style symmetry ----
        | folded = sin(drive * (c + offset)); offset_q14 = SYMM*64 (0..8128).
        | drive_q8 = 256 + FOLD*24 (1.0 .. ~12.9). Dry stays unbiased; SYMM only
        | skews the fold. out = c + (folded - c) * FOLD/128.
        move.l  (%sp),%d2                | FOLD<<8|SYMM
        lsr.l   #8,%d2
        beq     sy_nofold
        move.l  %d1,-(%sp)               | park c (unbiased dry)
        move.l  %d2,-(%sp)               | park FOLD amount
        move.l  %d2,%d4                  | fold*24 = fold*16 + fold*8
        lsl.l   #4,%d4
        lsl.l   #3,%d2
        add.l   %d2,%d4
        addi.l  #256,%d4                 | drive_q8
        move.l  4(%sp),%d1               | c
        move.l  8(%sp),%d2               | FOLD<<8|SYMM (under the two parks)
        mvz.b   %d2,%d2                  | SYMM
        lsl.l   #6,%d2                   | *64 -> Q14 offset
        add.l   %d2,%d1                  | c + symmetry (fold input only)
        muls.l  %d4,%d1                  | (c+off) * drive_q8
        asl.l   #8,%d1                   | phase: drive 1.0 + peak c -> index 64 (sin pi/2)
        move.l  %d1,%d2
        lsr.l   %d3,%d2                  | >>24 -> table index
        add.l   %d2,%d2
        mvs.w   (%a0,%d2.l),%d4          | a
        mvs.w   2(%a0,%d2.l),%d2         | b
        sub.l   %d4,%d2
        lsr.l   #8,%d1
        mvz.w   %d1,%d1
        muls.l  %d1,%d2
        asr.l   #8,%d2
        asr.l   #8,%d2
        add.l   %d2,%d4                  | folded, Q14
        move.l  (%sp)+,%d2               | FOLD
        move.l  (%sp)+,%d1               | c (dry, unbiased)
        sub.l   %d1,%d4                  | folded - c
        muls.l  %d2,%d4
        asr.l   #7,%d4                   | * FOLD / 128
        add.l   %d4,%d1                  | dry/wet
sy_nofold:
        adda.l  %a6,%a5                  | the gain one step on (a linear ramp across the call: no step at a frame edge)
        move.l  %a5,%d2
        swap    %d2                      | gain / 2, Q14
        muls.w  %d2,%d1                  | c * gain / 2 (16 x 16)
        lsl.l   #2,%d1                   | = (c * g) << 1: the high word is (c * g) >> 15 -- at full gain c itself, as before
        clr.w   %d1                      | sample << 16: the DSP's 24-bit word is the top 24 bits
        move.l  %d1,(%a1)+               | L
        move.l  %d1,(%a1)+               | R
        add.l   %a2,%d6                  | mod phase advances (wraps unsigned)
        add.l   %d5,%d0
        subq.l  #1,%d7
        bne     sy_loop
        move.l  %d0,S_PHC(%a3)
        move.l  %d6,S_PHM(%a3)
        move.l  %a4,S_LASTM(%a3)
        move.l  %a5,%d1                  | the gain the ramp reached (gain << 15) -> S_GPREV: the next call ramps on
        moveq   #15,%d3                  | from here (a fade to target 0 may land a few units below 0 by the floor
        asr.l   %d3,%d1                  | of the step: clamped, the voice is silent)
        bpl     sy_gend
        moveq   #0,%d1
sy_gend:
        move.w  %d1,S_GPREV(%a3)
        move.l  (%sp)+,%d1               | drop cxparm
        move.l  (%sp)+,%a2               | the header
        move.l  52(%sp),%d2              | track
        bsr     po_any                   | paraphonic voices still fading under the mono voice (VOIC 2..4 -> 1 across
        beq     sy_done                  | a note, sy_warm's po_fade): summed onto the mono voice's samples (BUILD 32)
        mvz.b   3(%a2),%d7
        lea     16(%a2),%a1
        bra     po_fill_add
sy_done:
        move.l  44(%sp),%d0
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     48(%sp),%sp
        rts

| ---- po_tick: the sequencer clock, once an audio frame -------------------------
| Called from po_lfo3b for track 0's LFO 3 -- the frame builder's LFO pass runs
| every frame for every track from boot, voice or no voice (sy_render runs
| only once a FLEX voice has started, which left the first note of a session
| untimed). Counts frames and the changes of the sequencer's (step, tick) pair
| -- a monotonic tick count the live-record note-length hooks read through
| qz_clock (the pattern's step word wraps, this does not); ticks a step = the
| largest tick value seen + 1; frames a step measured at each step change
| (the HOLD gate's unit). Clobbers d1, d3, a0; d0 untouched.
po_tick:
        lea     po_clock(%pc),%a0
        move.l  %a0,CLOCK_AT             | published for the quantizer
        addq.l  #1,CK_FRAMES(%a0)
        mvz.w   SEQ_STEP,%d1
        lsl.l   #8,%d1
        mvz.b   SEQ_TICK,%d3
        or.l    %d3,%d1
        cmp.l   CK_LAST(%a0),%d1
        beq     po_tk_done
        move.l  %d1,CK_LAST(%a0)
        addq.l  #1,CK_TICKS(%a0)
        addq.l  #1,%d3
        cmp.l   CK_TPS(%a0),%d3
        ble     po_tk_step
        move.l  %d3,CK_TPS(%a0)
po_tk_step:
        lsr.l   #8,%d1
        cmp.l   CK_STEP(%a0),%d1
        beq     po_tk_done
        move.l  %d1,CK_STEP(%a0)
        move.l  CK_FRAMES(%a0),%d1
        move.l  %d1,%d3
        sub.l   CK_FSTEP(%a0),%d3
        move.l  %d1,CK_FSTEP(%a0)
        cmpi.l  #16,%d3                  | a plausible step (not the first after a stop)
        blt     po_tk_done
        move.l  %d3,CK_FPS(%a0)
po_tk_done:
        rts

| ---- po_rate: d0 := C4_INC * rate, the rate as the stock renderer computes it ----
| (0x4000409e..0x40004104): d6 = the PTCH word (raw << 8, 0x0400..0x7c00), d5 =
| the RATE word, a4 = the parameter record (its RATE-mode byte at +27).
| Clobbers d0, d1, d3, d4, a0 and acc0; d2, d5, d6, d7 survive.
po_rate:
        move.l  %d6,%d0
        mov3q.l #1,%d3                   | PTCH <= 0 semitones: the curve's lower half, halved
        cmpi.w  #0x4000,%d0
        ble     po_rate1
        subi.l  #0x3c00,%d0
        moveq   #0,%d3
po_rate1:
        move.l  %d0,%d1
        asr.l   #5,%d0
        lea     PITCH_TAB,%a0
        lea     (%a0,%d0.l*4),%a0
        moveq   #27,%d4
        lsl.l   %d4,%d1
        move.l  (%a0)+,%d4
        lsr.l   #1,%d1                   | the 5-bit fraction, Q31
        move.l  %d4,%acc0
        msac.l  %d1,%d4,(%a0)+,%d4,%acc0 | t0 - frac*t0, then t1
        mac.l   %d1,%d4,%acc0            | + frac*t1
        mvz.b   27(%a4),%d4              | the RATE-mode byte: 0 = RATE scales the pitch
        bne     po_rate2
        move.l  %d5,%d4
        cmpi.w  #0x7f00,%d4
        bge     po_rate2
        movclr.l %acc0,%d0
        swap    %d4
        lsl.l   #2,%d4
        bcc     po_rate3
        lsr.l   #1,%d4
        neg.l   %d4
        bra     po_rate4
po_rate3:
        lsr.l   #1,%d4
        addi.l  #0x80000000,%d4
po_rate4:
        msac.l  %d0,%d4,%acc0
po_rate2:
        movclr.l %acc0,%d0
        asr.l   %d3,%d0                  | rate, Q26 (0x04000000 = 1.0)
        move.l  #C4_INC,%d1
        mac.l   %d1,%d0,%acc0            | C4_INC * rate / 32 (fractional mode: >> 31)
        movclr.l %acc0,%d0
        lsl.l   #5,%d0
        rts

| ---- sy_word: d6 := the synth's pitch word from the parameter record a4 --------
| The record's PTCH halfword is the raw byte << 8 with the frame builder's
| locks, LFO and scenes applied (fractions in the low byte). On a synth track
| one raw unit is ONE SEMITONE (the page's PTCH prints -64..+63), so the word
| is stretched onto the stock curve's scale, where a semitone is SEMI = 5 <<
| 8: w = 0x4000 + (ptch - 0x4000) * 5. FINE, the RATE byte on a synth track,
| adds (rate - 0x4000) / 256 cents: SEMI / 100 = 12.8 a cent, i.e. the
| halfword difference / 20 (3277 / 65536; 0.006 % off: 0.004 cent at +-64). The word runs from 0x4000 - 64 * SEMI to 0x4000
| + 63.6 * SEMI, far outside the curve's +-12; the callers fold it by octaves
| (po_rate_fold), and the slew (sy_slew) and the chord arithmetic take it as
| a signed long. Clobbers d0, d1.
sy_word:
        mvz.w   (%a4),%d6
        subi.l  #0x4000,%d6
        move.l  %d6,%d0
        lsl.l   #2,%d6
        add.l   %d0,%d6                  | (ptch - 0x4000) * 5
        | CX OSC: RATE is FOLD, not FINE -- pitch is PTCH alone (no cents)
        addi.l  #0x4000,%d6
        rts

| ---- po_rate_fold: d0 := the carrier increment for the pitch word d6, any range --
| The word is folded into the stock curve's 24-semitone window (0x0400..
| 0x7c00) by octaves and the increment shifted back -- the paraphonic path
| did this inline since phase 5; the mono path shares it now that PTCH spans
| +-64 semitones. RATE never scales a synth voice (its byte is FINE, already
| in the word): po_rate is given 1.0. More than six octaves up (PTCH +63 with
| an octave shape: past 40 kHz) is no note: d0 := -1, which the callers'
| INC_MAX net silences. Clobbers d0, d1, d3, d4, d7, a0; d5, d6 preserved.
po_rate_fold:
        move.l  %d5,-(%sp)
        move.l  %d6,-(%sp)
        move.l  #0x7f00,%d5
        moveq   #0,%d7                   | octaves folded out of the word
po_rf_fold1:
        cmpi.l  #0x7c00,%d6              | above +12 semitones: an octave down, shift the increment up
        ble     po_rf_fold2
        subi.l  #0x3c00,%d6
        addq.l  #1,%d7
        bra     po_rf_fold1
po_rf_fold2:
        cmpi.l  #0x0400,%d6              | below -12: an octave up
        bge     po_rf_fold3
        addi.l  #0x3c00,%d6
        subq.l  #1,%d7
        bra     po_rf_fold2
po_rf_fold3:
        cmpi.l  #6,%d7
        ble     po_rf_rate
        moveq   #-1,%d0                  | no note of this synth
        bra     po_rf_out
po_rf_rate:
        bsr     po_rate                  | d0 = the increment at the folded word (clobbers d0/d1/d3/d4/a0)
        tst.l   %d7
        beq     po_rf_out
        bmi     po_rf_down
        lsl.l   %d7,%d0
        bra     po_rf_out
po_rf_down:
        neg.l   %d7
        asr.l   %d7,%d0
po_rf_out:
        move.l  (%sp)+,%d6
        move.l  (%sp)+,%d5
        rts

| ---- sy_glide: d0 := the track's GLIDE value, 0 = off, 1..127 -----------------
sy_glide:
        mvz.b   GLIDE_AT,%d0
        rts

| ---- po_legbyte: d2 = track -> d0 = the Part's LEG byte (0 OFF, 1 MONO, 2.. POLY) --
| The AMP page-2 byte 5 of the track (po_legmode's byte). Clobbers d0, d3, a0.
po_legbyte:
        movea.l PART_PTR,%a0
        mvz.b   PART_IDX,%d0
        move.l  #6322,%d3
        muls.l  %d3,%d0
        adda.l  %d0,%a0                  | the Part
        move.l  %d2,%d3
        lsl.l   #5,%d3
        sub.l   %d2,%d3
        sub.l   %d2,%d3                  | track * 30
        adda.l  #AMP_P2_OFF,%a0
        mvz.b   LEG_SLOT2(%a0,%d3.l),%d0
        rts

| ---- sy_slew: d6 := the PTCH word slewed toward d6 (GLIDE) ---------------------
| a3 = the record whose +40 (S_CUR / V_CUR) is the current word, Q12. GLIDE
| off, or the track's LEG OFF (po_legbyte: no glide at all on such a track --
| live keys and sequenced trigless trigs alike, whatever GLIDE says; the
| mono voice and every paraphonic voice come through here, so both are
| covered): S_CUR := the target. GLIDE g: cur += (target - cur) * k, k = T / tau,
| tau = 10 ms * 100^((g - 1) / 126) (10 ms at 1, 100 ms at 64, 1 s at 127); k
| in Q16 from the stock 2^x curve PITCH_TAB (entry i = 2 * 2^((i - 512) /
| 480), Q26, so 2^f = entry 32 + 480 f): e = 127 - g, x = e * log2(100) / 126
| = n + f, k = 23.78 * 2^n * 2^f. The step is (|diff| >> 8) * k >> 8.
| Clobbers d0, d1, d3, d7, a0.
sy_slew:
        bsr     sy_glide
        move.l  %d0,%d1                  | g
        move.l  %d6,%d0
        lsl.l   #8,%d0
        lsl.l   #4,%d0                   | the target, Q12
        tst.l   %d1
        beq     sy_sl_snap
        move.l  %d0,%d7                  | (the target, kept across the byte read)
        bsr     po_legbyte               | the track's LEG (clobbers d0, d3, a0)
        move.l  %d0,%d3
        move.l  %d7,%d0
        tst.l   %d3
        beq     sy_sl_snap               | LEG OFF: no glide on this track
        moveq   #127,%d3
        sub.l   %d1,%d3                  | e = 127 - g
        move.l  #3456,%d7                | log2(100) / 126 * 2^16
        mulu.l  %d7,%d3                  | x, Q16
        move.l  %d3,%d1
        swap    %d1
        mvz.w   %d1,%d1                  | n = 0..6
        mvz.w   %d3,%d3                  | f, Q16
        move.l  #480,%d7
        mulu.l  %d7,%d3
        swap    %d3
        mvz.w   %d3,%d3                  | 480 f = the table index above entry 32
        lea     PITCH_TAB+128,%a0        | entry 32 = 2^0
        move.l  (%a0,%d3.l*4),%d3        | 2^f, Q26
        lsr.l   #8,%d3
        lsr.l   #2,%d3                   | Q16
        move.l  #6087,%d7                | 23.78 * 256
        mulu.l  %d7,%d3
        moveq   #24,%d7
        sub.l   %d1,%d7
        lsr.l   %d7,%d3                  | k = 23.78 * 2^n * 2^f, Q16
        move.l  S_CUR(%a3),%d1           | the current word, Q12
        sub.l   %d1,%d0                  | diff = target - current
        bpl     sy_sl_up
        neg.l   %d0
        lsr.l   #8,%d0
        mulu.l  %d3,%d0
        lsr.l   #8,%d0
        sub.l   %d0,%d1
        bra     sy_sl_store
sy_sl_up:
        lsr.l   #8,%d0
        mulu.l  %d3,%d0
        lsr.l   #8,%d0
        add.l   %d0,%d1
        bra     sy_sl_store
sy_sl_snap:
        move.l  %d0,%d1                  | off: no lag
sy_sl_store:
        move.l  %d1,S_CUR(%a3)
        asr.l   #8,%d1                   | (signed: a synth word below -12 semitones is negative)
        asr.l   #4,%d1
        move.l  %d1,%d6                  | the slewed PTCH word
        rts

| ==== PARAPHONIC: the voices' frame (the second call, after the stock call) ======
| In: d2 = track, a3 = the track record, a4 = fp, d6 = the PTCH word, d5 = the
| RATE word. Preserves a2, a3, d2 (sy_check needs them). Uses a5 = the track
| record, a6 = the voice being updated, a2 = the end of the track's voices.
po_frame:
        lea     -8(%sp),%sp
        movem.l %a2/%a3,(%sp)
        move.l  %a3,%a5
        move.l  %d6,T_W(%a5)
| ---- keys released since last frame -> their voices release ----------------
        lea     KEYS_AT+8,%a0
        move.l  (%a0,%d2.l*4),%d0        | the held-key mask now
        move.l  T_MASK(%a5),%d1
        move.l  %d0,T_MASK(%a5)
        and.l   %d0,T_SMASK(%a5)         | a released key's start mark goes with it (the same-scan sweep)
        tst.l   LIVEREC_AT               | the recorder off (STOP, REC off): the chord record is stale
        bne     po_fr_rec
        lea     po_chord(%pc),%a0
        move.l  %d2,%d3
        lsl.l   #5,%d3
        clr.b   CR_N(%a0,%d3.l)
        clr.b   CR_PKEY(%a0,%d3.l)
po_fr_rec:
        not.l   %d0
        and.l   %d0,%d1                  | gone = held then & ~held now
        beq     po_fr_start
        bsr     po_voices_of             | a6 = the track's voices, a2 = their end
po_fr_gone:
        mvz.b   V_STATE(%a6),%d0
        cmpi.l  #1,%d0
        bne     po_fr_gone1
        mvz.b   V_KEY(%a6),%d0
        beq     po_fr_gone1
        subq.l  #1,%d0
        btst    %d0,%d1
        beq     po_fr_gone1
        move.b  #2,V_STATE(%a6)          | that key's note releases
po_fr_gone1:
        lea     V_STRIDE(%a6),%a6
        cmp.l   %a2,%a6
        bne     po_fr_gone
po_fr_start:
| ---- MIDI notes released since (MIDI IN, 30 Sep 2026): a voice tagged with a
| MIDI identity (V_KEY 0x80 | note, po_mon) whose note is no longer in the
| track's held-note list (po_mheld; the note-off detour po_moff removes it)
        bsr     po_voices_of
po_fr_mgone:
        mvz.b   V_STATE(%a6),%d0
        cmpi.l  #1,%d0
        bne     po_fr_mgone1
        mvz.b   V_KEY(%a6),%d0
        cmpi.l  #0x80,%d0
        bcs     po_fr_mgone1             | a panel key or a sequencer note: the mask above decides
        bsr     po_held                  | still held? (Z = no)
        bne     po_fr_mgone1
        move.b  #2,V_STATE(%a6)          | that note releases
po_fr_mgone1:
        lea     V_STRIDE(%a6),%a6
        cmp.l   %a2,%a6
        bne     po_fr_mgone
| ---- a legato hand-over (po_legkey, 2 Oct 2026): the sounding chord follows the key
| once its PTCH lock has landed (T_W moved: the flag is set before the trigless
| trig is posted, so the lock's frame is the hand-over's), or after 8 frames
| (a key at the same pitch) --------------------------------------------------
        mvz.b   T_LEGKEY(%a5),%d7
        beq     po_fr_nolh
        move.l  T_W(%a5),%d0
        cmp.l   T_LAST(%a5),%d0
        bne     po_fr_lh
        mvz.b   T_LEGN(%a5),%d0
        addq.l  #1,%d0
        move.b  %d0,T_LEGN(%a5)
        cmpi.l  #8,%d0
        bcs     po_fr_nolh
po_fr_lh:
        clr.b   T_LEGKEY(%a5)
        bsr     po_handover              | d7 = the identity (clobbers d0, d1, d3, d4, d6, d7, a0, a1, a2, a6)
        move.l  FP_PTR,%a4
po_fr_nolh:
| ---- a voice start this frame: the chord ------------------------------------
        lea     NIBBLE,%a0
        lea     (%a0,%d2.l),%a0
        btst    #4,(%a0)
        beq     po_fr_params
        bsr     po_start
po_fr_params:
| ---- the track's parameters this frame ----------------------------------------
        mvz.w   2(%a4),%d1               | STRT -> ratio (free: raw 0..127 -> Q8 0.25..16)
        lsr.l   #8,%d1
        bsr     sy_rato_q8               | d1 := Q8
        move.l  %d1,T_RATIO(%a5)
        mvz.w   10(%a4),%d1              | RTIM -> feedback (FDBK)
        move.l  #FB_SCALE,%d0
        mulu.l  %d0,%d1
        lsr.l   #8,%d1
        move.l  %d1,S_FB(%a5)
        moveq   #0,%d0                   | index env HOLD (T_DK 0 = no decay)
po_fr_dk:
        move.l  %d0,T_DK(%a5)
        mvz.w   4(%a4),%d1               | LEN -> index I
        move.l  #INDEX_SCALE,%d0
        mulu.l  %d0,%d1
        lsr.l   #8,%d1
        move.l  %d1,T_I(%a5)
        move.l  #CV_STRIDE,%d0           | AMP REL -> the release k (po_relk: the DSP's law, plan B)
        muls.l  %d2,%d0
        lea     CURVALS,%a0
        add.l   %d0,%a0
        mvz.b   CV_REL(%a0),%d0
        lea     po_relk(%pc),%a1
        mvz.w   (%a1,%d0.l*2),%d0
        bne     po_fr_rk
        btst    #2,S_ON(%a5)             | REL INF, STOPPED (po_stop): the floor, tau 1 ms -- every releasing
        beq     po_fr_rk                 | voice reaches silence under the DSP's all-off (BUILD 32)
        mvz.w   (%a1),%d0
po_fr_rk:
        move.l  %d0,T_RK(%a5)
        mvz.b   CV_ATK(%a0),%d0          | AMP ATK -> the attack step a frame, po_atk[ATK] * T_GMAX / 32768 (at least 1)
        lea     po_atk(%pc),%a1
        mvz.w   (%a1,%d0.l*2),%d0
        mulu.l  T_GMAX(%a5),%d0
        lsr.l   #8,%d0
        lsr.l   #7,%d0
        bne     po_fr_ak
        moveq   #1,%d0
po_fr_ak:
        move.w  %d0,T_AK(%a5)
| ---- every sounding voice: pitch, increments, envelopes ----------------------
        bsr     po_voices_of             | a6 = the voices, a2 = their end
po_fr_v:
        tst.b   V_STATE(%a6)
        beq     po_fr_next
        move.l  %a6,%a3                  | sy_slew works on +40 of a3
        move.l  T_W(%a5),%d6
        sub.l   T_REF(%a5),%d6
        add.l   V_ROOT(%a6),%d6          | the target word: the note plus what PTCH moved since its start
        bsr     sy_slew                  | d6 := slewed (clobbers d0, d1, d3, d7, a0)
        bsr     po_rate_fold             | d0 = the increment, the word folded by octaves (clobbers d0/d1/d3/d4/d7/a0)
        cmpi.l  #INC_MAX,%d0             | safety net: an impossible pitch frees the voice
        bls     po_fr_inc1
        clr.b   V_STATE(%a6)
        clr.l   V_GAIN(%a6)
        bra     po_fr_next
po_fr_inc1:
        move.l  %d0,V_INC(%a6)
        asr.l   #8,%d0
        muls.l  T_RATIO(%a5),%d0
        move.l  %d0,V_INCM(%a6)          | modulator increment = ratio * pitch
        mvz.w   V_ERAMP(%a6),%d1         | a warm START's ramp (BUILD 38): the remaining distance to ENV_ONE over
        beq     po_fr_envk               | the remaining frames -- linear; the decay waits for it
        move.l  #ENV_ONE,%d0
        sub.l   V_ENV(%a6),%d0
        divs.l  %d1,%d0
        add.l   %d0,V_ENV(%a6)
        subq.l  #1,%d1
        move.w  %d1,V_ERAMP(%a6)
        bra     po_fr_env
po_fr_envk:
        move.l  T_DK(%a5),%d0            | the index envelope
        beq     po_fr_envhold
        move.l  V_ENV(%a6),%d1
        subi.l  #ENV_FLOOR,%d1
        ble     po_fr_env
        lsr.l   #8,%d1
        lsr.l   #4,%d1
        mulu.l  %d0,%d1
        lsr.l   #8,%d1
        sub.l   %d1,V_ENV(%a6)
        bra     po_fr_env
po_fr_envhold:
        move.l  #ENV_ONE,%d1
        move.l  %d1,V_ENV(%a6)
po_fr_env:
        move.l  T_I(%a5),%d1
        move.l  V_ENV(%a6),%d0
        lsr.l   #8,%d0
        lsr.l   #4,%d0
        mulu.l  %d0,%d1
        lsr.l   #8,%d1
        lsr.l   #4,%d1                   | I * E: this frame's target ...
        sub.l   V_IEFF(%a6),%d1          | ... minus the running value: po_fill ramps V_IEFF across the frame,
        moveq   #16,%d0                  | (target - running) / 16 a sample (BUILD 38)
        divs.l  %d0,%d1
        move.w  %d1,V_ISTEP(%a6)
        move.l  S_FB(%a5),%d0
        move.l  %d0,V_FB(%a6)
        move.l  V_HOLD(%a6),%d0          | a gated sequencer note: its HOLD runs out -> release
        beq     po_fr_amp
        subq.l  #1,%d0
        move.l  %d0,V_HOLD(%a6)
        bne     po_fr_amp
        move.b  #2,V_STATE(%a6)
po_fr_amp:
        move.l  V_GAIN(%a6),%d1          | the amplitude envelope (plan B: the laws of po_mono_env, per voice)
        mvz.b   V_STATE(%a6),%d0
        cmpi.l  #2,%d0
        beq     po_fr_rel
        cmpi.l  #3,%d0
        beq     po_fr_cut
        move.l  T_GMAX(%a5),%d0          | sounding: the attack, po_atk[ATK] scaled to T_GMAX a frame, then full
        cmp.l   %d0,%d1
        bge     po_fr_cap                | at full (or above it: a voice po_carry brought in, taken warm): no attack
        mvz.w   T_AK(%a5),%d3
        add.l   %d3,%d1
        cmp.l   %d0,%d1
        ble     po_fr_gain
        move.l  %d0,%d1
        bra     po_fr_gain
po_fr_cut:
        move.l  T_GMAX(%a5),%d3          | stolen / chord-memory cut: T_GMAX / 8 a frame (8 frames = 2.9 ms), then freed
        lsr.l   #CUT_SHIFT,%d3
        bra     po_fr_rel1
po_fr_rel:
        move.l  T_RK(%a5),%d0            | releasing: gain -= gain * k
        move.l  %d1,%d3
        mulu.l  %d0,%d3
        lsr.l   #8,%d3
        lsr.l   #8,%d3
        bne     po_fr_rel1
        tst.l   %d0
        beq     po_fr_rel1               | INF: holds
        moveq   #1,%d3                   | a step too small to show: still make progress
po_fr_rel1:
        sub.l   %d3,%d1
        bpl     po_fr_rel1a
        moveq   #0,%d1
po_fr_rel1a:
po_fr_cap:
        cmp.l   T_GMAX(%a5),%d1          | above the cap (a tail from a start at a lower VOIC, the mono voice
        ble     po_fr_rel2               | po_carry brought in): it CONVERGES on the cap at the fade rate,
        move.l  T_GMAX(%a5),%d0          | T_GMAX / 8 a frame (BUILD 32 -- a one-frame clamp was a step)
        move.l  %d0,%d3
        lsr.l   #CUT_SHIFT,%d3
        sub.l   %d3,%d1
        cmp.l   %d0,%d1
        bge     po_fr_rel2
        move.l  %d0,%d1
po_fr_rel2:
        cmpi.l  #64,%d1                  | -54 dB re the mono voice's full scale: gone ...
        bgt     po_fr_gain
        moveq   #0,%d1                   | ... target 0 ...
        mvz.w   V_GPREV(%a6),%d0
        cmpi.l  #64,%d0                  | ... and free once po_fill has ramped it down there (a cut
        bgt     po_fr_gain               | voice -- po_fade / po_st_cut -- fades over its last frame first)
        clr.b   V_STATE(%a6)
po_fr_gain:
        move.l  %d1,V_GAIN(%a6)
po_fr_next:
        lea     V_STRIDE(%a6),%a6
        cmp.l   %a2,%a6
        bne     po_fr_v
        move.l  T_W(%a5),%d0
        move.l  %d0,T_LAST(%a5)
        movem.l (%sp),%a2/%a3
        lea     8(%sp),%sp
        rts

| ---- po_free: track d2's four voices freed (state 0, gain 0) and its limiter gain
| reset: the safety net when their owner -- the stock voice, or a paraphonic note --
| is gone, and the chord-memory cut at a start with a shape. Clobbers d0, a0.
po_free:
        lea     po_voices(%pc),%a0
        move.l  %d2,%d0
        lsl.l   #8,%d0
        add.l   %d0,%a0
        moveq   #4,%d0
po_free1:
        clr.b   V_STATE(%a0)
        clr.l   V_GAIN(%a0)
        clr.w   V_GPREV(%a0)             | silent: the next start resets its phases
        lea     V_STRIDE(%a0),%a0
        subq.l  #1,%d0
        bne     po_free1
        rts

| ---- po_fade: track d2's active voices go over ONE frame (28 Sep 2026) ---------
| The chord-memory cut: state 2 with target gain 0, so po_fill ramps each from
| the gain it had (V_GPREV) to 0 across the next frame instead of cutting it
| (a step of up to T_GMAX = a click at every chord retrigger before). A voice
| the new chord takes in this same start restarts phase-continuous from that
| gain (po_st_note). T_LIM is kept: the limiter's ramp runs on. Clobbers d0, a0.
po_fade:
        lea     po_voices(%pc),%a0
        move.l  %d2,%d0
        lsl.l   #8,%d0
        add.l   %d0,%a0
        moveq   #4,%d0
po_fade1:
        tst.b   V_STATE(%a0)
        beq     po_fade2
        move.b  #3,V_STATE(%a0)          | fading (po_fr_cut: 8 frames), unless the new chord takes it warm first
po_fade2:
        lea     V_STRIDE(%a0),%a0
        subq.l  #1,%d0
        bne     po_fade1
        rts

| ---- po_carry: the mono voice becomes a paraphonic voice (BUILD 32) -----------
| A paraphonic START (VOIC 2..4) while the mono voice sounds (S_GPREV != 0: VOIC
| went 1 -> 2..4 across a note, live or by a lock). The mono voice's fields +0..+35
| (phases, index envelope, increments, I * E, gain, feedback, the modulator's last
| sample -- the voice record's first 36 bytes are the same layout) move into a
| free voice (else the quietest active one), state 3: it FADES over 8 frames
| (po_fr_cut, T_GMAX / 8 a frame -- from 32767 at VOIC 4 that is 16 frames, 5.8
| ms) at its own pitch (V_ROOT such that po_start's fold of T_LAST - T_REF and the
| new T_REF leave its target word at S_CUR's), phase-continuous from S_GPREV --
| unless the chord's allocation takes it warm first (po_alloc: rank 0 like a free
| voice, but stamped newest, so free voices go first). The gains are capped at
| 32767 (po_fill's 16 x 16 multiply; the mono voice's 32768 would read as -1).
| The mono record is silent after it (S_GAIN / S_GPREV 0). a3 = the track record,
| d2 = track. Clobbers d0, d1, a0, a1.
po_carry:
        move.l  %d3,-(%sp)
        lea     po_voices(%pc),%a0
        move.l  %d2,%d0
        lsl.l   #8,%d0
        add.l   %d0,%a0                  | the track's voices
        move.l  %a0,%a1                  | the pick so far (the first, until better)
        move.l  #0x7fffffff,%d3
        moveq   #4,%d0
po_ca_pick:
        tst.b   V_STATE(%a0)
        beq     po_ca_free
        move.l  V_GAIN(%a0),%d1
        cmp.l   %d3,%d1
        bcc     po_ca_next
        move.l  %d1,%d3
        move.l  %a0,%a1
po_ca_next:
        lea     V_STRIDE(%a0),%a0
        subq.l  #1,%d0
        bne     po_ca_pick
        bra     po_ca_take
po_ca_free:
        move.l  %a0,%a1
po_ca_take:
        move.l  %a3,%a0
        moveq   #9,%d0
po_ca_copy:
        move.l  (%a0)+,(%a1)+            | +0..+35
        subq.l  #1,%d0
        bne     po_ca_copy
        lea     -36(%a1),%a1
        move.b  #3,V_STATE(%a1)
        clr.b   V_KEY(%a1)
        move.l  S_CUR(%a3),%d0
        move.l  %d0,V_CUR(%a1)           | the slewed word, Q12, as it is
        asr.l   #8,%d0
        asr.l   #4,%d0                   | the word
        sub.l   T_LAST(%a3),%d0
        add.l   T_REF(%a3),%d0           | po_start folds T_LAST - T_REF into every active root, then T_REF := T_W:
        move.l  %d0,V_ROOT(%a1)          | the target T_W - T_REF + V_ROOT comes out at the word
        clr.l   V_HOLD(%a1)
        lea     po_seq(%pc),%a0
        addq.l  #1,(%a0)
        move.l  (%a0),V_AGE(%a1)         | stamped newest
        lea     po_clock(%pc),%a0
        move.l  CK_FRAMES(%a0),%d0
        move.l  %d0,V_FRAME(%a1)
        mvz.w   S_GPREV(%a3),%d0
        cmpi.l  #32767,%d0
        bls     po_ca_gp
        move.l  #32767,%d0
po_ca_gp:
        move.w  %d0,V_GPREV(%a1)
        move.l  S_GAIN(%a3),%d0
        cmpi.l  #32767,%d0
        bls     po_ca_g
        move.l  #32767,%d0
po_ca_g:
        move.l  %d0,V_GAIN(%a1)
        clr.l   S_GAIN(%a3)
        clr.w   S_GPREV(%a3)
        move.l  (%sp)+,%d3
        rts

| ---- po_fade_frame: the fading voices' frame under the MONO voice (BUILD 32) ----
| The mono path's frame (sy_mono_frame, the frame's second call): every active
| voice of track d2 (state 3 after sy_warm's po_fade; any state is treated so)
| steps down by T_GMAX / 8 a frame (at least 2048: the T_GMAX of the last
| paraphonic start, 0 before any) and is freed once po_fill has ramped it to
| silence, as po_frame's po_fr_rel2 does. a3 = the track record. Clobbers nothing.
po_fade_frame:
        lea     -20(%sp),%sp
        movem.l %d0/%d1/%d3/%d4/%a0,(%sp)
        lea     po_voices(%pc),%a0
        move.l  %d2,%d0
        lsl.l   #8,%d0
        add.l   %d0,%a0
        move.l  T_GMAX(%a3),%d3
        lsr.l   #CUT_SHIFT,%d3
        cmpi.l  #2048,%d3
        bcc     po_ff_step
        move.l  #2048,%d3
po_ff_step:
        moveq   #4,%d0
po_ff_loop:
        tst.b   V_STATE(%a0)
        beq     po_ff_next
        move.l  V_GAIN(%a0),%d1
        sub.l   %d3,%d1
        bpl     po_ff_1
        moveq   #0,%d1
po_ff_1:
        cmpi.l  #64,%d1                  | -54 dB: target 0 ...
        bgt     po_ff_store
        moveq   #0,%d1
        mvz.w   V_GPREV(%a0),%d4
        cmpi.l  #64,%d4                  | ... and free once po_fill has ramped it down there
        bgt     po_ff_store
        clr.b   V_STATE(%a0)
po_ff_store:
        move.l  %d1,V_GAIN(%a0)
po_ff_next:
        lea     V_STRIDE(%a0),%a0
        subq.l  #1,%d0
        bne     po_ff_loop
        movem.l (%sp),%d0/%d1/%d3/%d4/%a0
        lea     20(%sp),%sp
        rts

| ---- po_any: Z clear when any voice of track d2 is active. Clobbers d0, d1, a0. -
po_any:
        lea     po_voices(%pc),%a0
        move.l  %d2,%d0
        lsl.l   #8,%d0
        add.l   %d0,%a0
        mvz.b   V_STATE(%a0),%d0
        mvz.b   V_STRIDE+V_STATE(%a0),%d1
        or.l    %d1,%d0
        mvz.b   2*V_STRIDE+V_STATE(%a0),%d1
        or.l    %d1,%d0
        mvz.b   3*V_STRIDE+V_STATE(%a0),%d1
        or.l    %d1,%d0
        rts

| ---- po_voices_of: a6 = track d2's four voice records, a2 = their end ---------
po_voices_of:
        lea     po_voices(%pc),%a6
        move.l  %d2,%d0
        lsl.l   #8,%d0                   | track * 4 * 64
        add.l   %d0,%a6
        lea     4*V_STRIDE(%a6),%a2
        rts

| ---- po_start: a voice starts -- allocate the chord's voices --------------------
| a5 = the track record, d2 = track, T_W = this frame's PTCH word (the new
| note's pitch), T_MASK = the held keys now. Clobbers d0, d1, d3, d4, d6, d7,
| a0, a1, a6, a2.
po_start:
        bsr     po_voices_of             | (clobbers d0)
        move.l  T_LAST(%a5),%d1
        sub.l   T_REF(%a5),%d1           | what PTCH moved since the last start:
po_st_fold:                              | fold it into the sounding voices' roots
        tst.b   V_STATE(%a6)
        beq     po_st_fold1
        add.l   %d1,V_ROOT(%a6)
po_st_fold1:
        lea     V_STRIDE(%a6),%a6
        cmp.l   %a2,%a6
        bne     po_st_fold
        move.l  T_W(%a5),%d1
        move.l  %d1,T_REF(%a5)
        lea     KEYS_AT,%a0
        mvz.b   (%a0,%d2.l),%d7          | the live key (index + 1) this trig came from, 0 = the sequencer
        clr.b   (%a0,%d2.l)              | (clr sets Z: test d7 after it)
        cmpi.l  #0x80,%d7
        bcs     po_st_panel              | a panel key, or a sequencer trig
| ---- a MIDI note-on (MIDI IN, 30 Sep 2026): the identity is 0x80 | note, and the
| track's ring (po_mring, filled by po_mon at each note-on) holds every note-on
| since the last START -- two or more when they arrived within one frame, where
| the stock mailbox posts ONE start. Each is started as a key of its own, at its
| own pitch: the frame's PTCH word (T_W, from the record's PTCH, the LAST
| note-on's lock) plus SEMI per semitone of the difference between the entry's
| raw and the record's raw (T_RAWP: read before the halfword was neutralised
| for the stock call -- after it the halfword holds the word). T_W is restored
| after; T_REF keeps the frame's word.
        move.l  T_W(%a5),-(%sp)
        move.l  T_RAWP(%a5),-(%sp)       | the record's PTCH raw
po_st_m1:
        bsr     po_mring_pop             | d7 := the identity, d0 := its raw; Z = the ring is empty
        beq     po_st_mdone
        sub.l   (%sp),%d0                | semitones from the record's raw
        move.l  #SEMI,%d1
        muls.l  %d1,%d0
        add.l   4(%sp),%d0
        move.l  %d0,T_W(%a5)             | this note's word
        bsr     po_start1                | (preserves d2, a5)
        bra     po_st_m1
po_st_mdone:
        addq.l  #4,%sp
        move.l  (%sp)+,T_W(%a5)
        rts
po_st_panel:
        move.l  %d7,-(%sp)
        bsr     po_start1                | the key itself, or the sequencer trig
        move.l  (%sp)+,%d7
        tst.l   %d7
        beq     po_st_out                | a sequencer trig: done
| ---- THE SAME-SCAN SWEEP (26 Sep 2026): the key handler posts ONE start a
| panel scan -- qz_pkey[t] names the last key pressed and the staged PTCH
| lock is its pitch -- so two keys pressed inside one scan reached the engine
| as one start and the earlier key never sounded. Every held key that has
| not had its start yet (T_SMASK: a key is marked at its start, or when the
| cap dropped it, and unmarked when it goes) is started here as a key of its
| own, at its own pitch: raw = 64 + (key - 12) + 12 * qz_oct (the
| quantizer's rule for a synth track's key, qz_oct read at its pinned
| byte), snapped onto the SCALE by po_snap, with FINE -- and whatever else
| moved this frame's word -- carried over from the last key's word (its
| snapped raw, T_RAWP, cancels out). T_W is restored after.
        move.l  T_W(%a5),-(%sp)
po_st_sw1:
        move.l  T_MASK(%a5),%d0
        move.l  T_SMASK(%a5),%d1
        not.l   %d1
        and.l   %d1,%d0                  | the held keys still without a start
        beq     po_st_swdone
        moveq   #0,%d7                   | the lowest of them
po_st_sw2:
        btst    %d7,%d0
        bne     po_st_sw3
        addq.l  #1,%d7
        bra     po_st_sw2
po_st_sw3:
        move.l  %d7,%d1
        subi.l  #12,%d1                  | key - 12 ...
        mvs.b   QZ_OCT_AT,%d0
        moveq   #12,%d3
        muls.l  %d3,%d0
        add.l   %d0,%d1                  | ... + 12 * octave = semitones from raw 64
        addi.l  #64,%d1                  | the key's raw, unsnapped
        sub.l   T_RAWP(%a5),%d1          | minus the record's raw this frame (the last key's)
        move.l  #SEMI,%d0
        muls.l  %d1,%d0
        add.l   (%sp),%d0                | the key's word = the last key's word + the difference
        bsr     po_snap                  | ... on the scale (T_SCALE: set by the start above)
        move.l  %d0,T_W(%a5)
        addq.l  #1,%d7                   | the identity
        bsr     po_start1                | (marks the key in T_SMASK first thing: the sweep ends)
        bra     po_st_sw1
po_st_swdone:
        move.l  (%sp)+,T_W(%a5)
po_st_out:
        rts

| ---- po_start1: ONE start -- d7 = the identity (0 = the sequencer, 1..25 a panel
| key's index + 1, 0x80 | note a MIDI note), T_W = its pitch word. Clobbers d0,
| d1, d3, d4, d6, d7, a0, a1, a6, a2, a4 (reloaded); preserves d2, a5.
po_start1:
        tst.l   %d7
        beq     po_st_1a
        cmpi.l  #0x80,%d7
        bcc     po_st_1a
        move.l  %d7,%d0                  | a panel key: marked as started (the same-scan sweep above
        subq.l  #1,%d0                   | never asks twice, whatever happens to the key below)
        move.l  T_SMASK(%a5),%d1
        bset    %d0,%d1
        move.l  %d1,T_SMASK(%a5)
po_st_1a:
| ---- ONE KEY = ONE VOICE (26 Sep 2026, Tim's report: a single key at VOIC 2..4
| sometimes sounded twice, doubled with a slight delay). With "----" a START
| that would give a held key a second voice is absorbed: (1) a live key K
| whose voice is SOUNDING already (the firmware's key handler saw a press
| without a release -- a key bounce, a re-press inside one key scan -- and
| posted a second trig; measured in ot_emu: two sounding voices of key 13);
| (2) a sequencer trig at the pitch of a held key's voice that started less
| than half a step ago -- the live recorder's own copy of the key (it
| quantizes to the nearest step, never further) replaying under the finger;
| (3) the other order: a live key at the pitch of a sequencer note started
| less than half a step ago adopts that voice (V_KEY := K, no HOLD gate), so
| the note sustains while the key is held and releases with it. A shape
| (chord memory), VOIC 1 (the mono path) and every other START: as before.
        move.l  #CV_STRIDE,%d0
        muls.l  %d2,%d0
        lea     CURVALS,%a0
        mvz.b   CV_CHRD(%a0,%d0.l),%d0
        lsr.l   #2,%d0
        bne     po_st_go                 | a shape: chord memory decides
        bsr     po_voices_of             | a6 = the voices, a2 = their end (clobbers d0)
        lea     po_clock(%pc),%a0
        move.l  CK_FRAMES(%a0),%d3       | now
        move.l  CK_FPS(%a0),%d4
        lsr.l   #1,%d4                   | half a step
        tst.l   %d7
        beq     po_st_dseq
po_st_dkey:                              | a live key K
        mvz.b   V_STATE(%a6),%d0
        cmpi.l  #1,%d0
        bne     po_st_dk1
        mvz.b   V_KEY(%a6),%d0
        cmp.l   %d7,%d0
        beq     po_st_dup                | (1) K's voice sounds already: a second START for a held key
        tst.l   %d0
        bne     po_st_dk1
        move.l  T_W(%a5),%d0
        cmp.l   V_ROOT(%a6),%d0          | (3) a sequencer note at K's pitch ...
        bne     po_st_dk1
        move.l  %d3,%d0
        sub.l   V_FRAME(%a6),%d0
        cmp.l   %d4,%d0
        bcc     po_st_dk1                | ... started less than half a step ago: K adopts it
        move.b  %d7,V_KEY(%a6)
        clr.l   V_HOLD(%a6)
        bra     po_st_dup
po_st_dk1:
        lea     V_STRIDE(%a6),%a6
        cmp.l   %a2,%a6
        bne     po_st_dkey
        bra     po_st_go
po_st_dseq:                              | a sequencer trig ...
        lea     KEYS_AT+8,%a0
        tst.l   (%a0,%d2.l*4)
        bne     po_st_ds1                | ... while keys are held:
        bsr     po_mheld_of              | ... or MIDI notes (a1 = the list; Z = empty)
        beq     po_st_go
po_st_ds1:
        mvz.b   V_STATE(%a6),%d0
        cmpi.l  #1,%d0
        bne     po_st_ds2
        tst.b   V_KEY(%a6)
        beq     po_st_ds2
        move.l  T_W(%a5),%d0
        cmp.l   V_ROOT(%a6),%d0          | (2) a held key's voice at the trig's pitch ...
        bne     po_st_ds2
        move.l  %d3,%d0
        sub.l   V_FRAME(%a6),%d0
        cmp.l   %d4,%d0
        bcs     po_st_dup                | ... started less than half a step ago: the recorder's copy of the key
po_st_ds2:
        lea     V_STRIDE(%a6),%a6
        cmp.l   %a2,%a6
        bne     po_st_ds1
po_st_go:
        tst.l   %d7
        bne     po_st_chord
        bsr     po_voices_of             | a sequencer trig: the sounding notes release
po_st_rel:
        mvz.b   V_STATE(%a6),%d0
        cmpi.l  #1,%d0
        bne     po_st_rel1
        move.b  #2,V_STATE(%a6)
po_st_rel1:
        lea     V_STRIDE(%a6),%a6
        cmp.l   %a2,%a6
        bne     po_st_rel
po_st_chord:
        moveq   #0,%d0
        mvz.w   SCALE_AT,%d1             | the quantizer's SCALE accessor is there (`jmp`; a remix
        cmpi.l  #0x4ef9,%d1              | without the quantizer has zeros: no scale) ...
        bne     po_st_ns
        jsr     SCALE_AT                 | ... its pitch-class mask, 0 = OFF (clobbers d0, a0)
po_st_ns:
        move.l  %d0,T_SCALE(%a5)
        move.l  #CV_STRIDE,%d0
        muls.l  %d2,%d0
        lea     CURVALS,%a0
        mvz.b   CV_VOIC(%a0,%d0.l),%d6   | VOIC: the track's voice cap, locks applied (2..4 here:
        subq.l  #1,%d6                   | the note started paraphonic on this byte; a byte outside
        cmpi.l  #3,%d6                   | 1..4 reads 1)
        bls     po_st_v1
        moveq   #0,%d6
po_st_v1:
        addq.l  #1,%d6
        mvz.b   CV_CHRD(%a0,%d0.l),%d0   | the chord byte, locks applied: shape << 2 | inversion (26 Sep 2026)
        move.l  %d0,%d3
        lsr.l   #2,%d3                   | the shape, 0..31 (0 = "----")
        beq     po_st_row0
        move.l  %d0,%d1
        andi.l  #3,%d1                   | the inversion
        move.l  %d3,%d0
        move.l  %d6,%d3                  | n = VOIC notes of it
        lea     po_vbuf(%pc),%a1         | the voicing: the shape's VOIC highest-priority notes, the
        bsr     po_voicing               | inversion's bass = PTCH (po_voicing; clobbers d0, d1, a0)
        moveq   #1,%d3                   | (a shape)
        bra     po_st_shape
po_st_row0:
        lea     po_shapes(%pc),%a1       | "----": the one note (SHAPE_END after it)
po_st_shape:
        lea     po_gmax(%pc),%a0         | the level (29 Sep 2026): a voice's full gain is the mono voice's
        move.l  (%a0,%d6.l*4),%d0        | 32768 / sqrt(VOIC) -- equal power: 23170, 18919, 16384 at 2, 3, 4 --
        move.l  %d0,T_GMAX(%a5)          | and po_fill's limiter holds the sum at FS (in phase it reaches 2.0 FS at 4)
| ---- the cap (27 Sep 2026): VOIC n = at most n voices sounding on the track,
| keys and chords alike. A shape other than "----" is a VOICING and takes k =
| n voices (29 Sep 2026: its n highest-priority notes; 26 Sep 2026: rotated
| into the inversion the CHRD byte's low two bits name); CHORD MEMORY: every
| voice of the track's previous chord is cut first (po_free), whatever its
| state, so the new chord is exactly the n voices that sound and two keys
| never mix chords. "----" is the single note (k = 1) and VOIC is the
| keyboard polyphony: when the active voices (sounding or releasing) plus 1
| exceed n, the oldest active + 1 - n of them are cut first (releasing before
| sounding, V_AGE order, po_steal) -- unless this is a CHORD PRESS at the cap
| (26 Sep 2026, po_st_cpress: the key follows another key within KR_WIN,
| other keys are held and every one of the n voices is a held key's sounding
| note): then the NEWEST key is the one dropped, so the bass of a chord
| survives on a track with fewer voices than fingers. The allocations below
| find free voices and the track ends the start with at most n voices. VOIC
| 1 never comes here (the mono path).
        tst.l   %d3
        beq     po_st_single
        bsr     po_fade                  | chord memory: the previous chord fades over the next frame (clobbers d0, a0);
        bra     po_st_note               | its voices are the oldest releasing ones po_alloc hands the new notes
po_st_single:
        bsr     po_st_cpress             | a chord press at the cap? (d0 = 1: this key gets no voice)
        bne     po_st_dup
        moveq   #1,%d3                   | k = 1
po_st_k:
        sub.l   %d6,%d3                  | k - n ...
        bsr     po_voices_of             | a6 = the track's voices (clobbers d0)
        move.l  %a6,%a0
        moveq   #4,%d0
po_st_count:
        tst.b   V_STATE(%a0)
        beq     po_st_count1
        addq.l  #1,%d3                   | ... + the active voices
po_st_count1:
        lea     V_STRIDE(%a0),%a0
        subq.l  #1,%d0
        bne     po_st_count
po_st_cut:
        tst.l   %d3                      | the excess: that many of the oldest active voices go
        ble     po_st_note
        bsr     po_steal                 | a0 = the oldest active voice (clobbers d0, d1, d4, a6)
        move.b  #3,V_STATE(%a0)          | it fades over 8 frames (po_fr_cut: T_GMAX / 8 a frame), not a cut
        lea     po_seq(%pc),%a6
        addq.l  #1,(%a6)
        move.l  (%a6),V_AGE(%a0)         | stamped newest: po_steal does not pick it again
        subq.l  #1,%d3
        bra     po_st_cut
po_st_note:                              | the voicing's notes (a shape: its n notes ascending; "----": the one)
        mvs.b   (%a1)+,%d3               | semitones above the note; SHAPE_END ends "----" after its one note
        cmpi.l  #SHAPE_END,%d3
        beq     po_st_done
        bsr     po_alloc                 | a0 = the voice to use
        tst.w   V_GPREV(%a0)             | it sounded last frame (a retrigger, a tail, a chord-memory fade):
        bne     po_st_warm               | phase-continuous, its gain ramps on from where po_fill left it
        clr.l   V_PHC(%a0)               | a silent voice: both operators at phase 0 ...
        clr.l   V_PHM(%a0)
        clr.l   V_LASTM(%a0)
        clr.l   V_GAIN(%a0)              | ... and the ramp from 0 (28 Sep 2026; before: the carrier ran on, the gain cut to 0)
        clr.l   V_IEFF(%a0)              | the index climbs to I * E within the first frame, under the gain from 0
        clr.w   V_ERAMP(%a0)
        move.l  #ENV_ONE,%d0             | the index envelope restarts at once (BUILD 38: only cold)
        move.l  %d0,V_ENV(%a0)
        bra     po_st_env
po_st_warm:
        move.w  #16,V_ERAMP(%a0)         | warm: the index envelope ramps from its level to ENV_ONE over 16 frames (po_frame; BUILD 38)
po_st_env:
        move.l  #SEMI,%d0
        muls.l  %d3,%d0
        add.l   T_W(%a5),%d0             | the note's word
        bsr     po_snap                  | ... on the scale, when one is set
        move.l  %d0,V_ROOT(%a0)
        lsl.l   #8,%d0
        lsl.l   #4,%d0
        move.l  %d0,V_CUR(%a0)           | a fresh note starts at its own pitch
        move.b  %d7,V_KEY(%a0)
        clr.l   V_HOLD(%a0)
        lea     po_clock(%pc),%a6
        move.l  CK_FRAMES(%a6),%d0
        move.l  %d0,V_FRAME(%a0)         | when (the dedupe above)
        move.l  #CV_STRIDE,%d1           | EVERY note is gated for the lane's HOLD (the lock, else the Part's
        muls.l  %d2,%d1                  | byte): frames = hold * frames a step -- a sequencer note and a live
        lea     CURVALS,%a4              | key alike (plan B: the DSP's own timer ran from the START whoever
        mvz.b   CV_HOLD(%a4,%d1.l),%d1   | started it, stage 1; 127 = INF: until the note-off / the next trig)
        cmpi.l  #127,%d1
        beq     po_st_hinf
        lea     po_hold128(%pc),%a4
        mvz.w   (%a4,%d1.l*2),%d1        | 1/128 steps
        lea     po_clock(%pc),%a4
        move.l  CK_FPS(%a4),%d4
        mulu.l  %d4,%d1
        lsr.l   #7,%d1
        addq.l  #1,%d1
        move.l  %d1,V_HOLD(%a0)
po_st_hinf:
        move.l  FP_PTR,%a4               | (a4 = the parameter record again)
        moveq   #1,%d0
        tst.l   %d7
        beq     po_st_state
po_st_live:
        cmpi.l  #0x80,%d7
        bcs     po_st_lkey
        move.l  %d0,-(%sp)
        move.l  %d7,%d0
        bsr     po_held                  | a MIDI note: still in the held list? (Z = no)
        move.l  (%sp)+,%d0
        bne     po_st_state
        moveq   #2,%d0                   | its note-off came before the start: release at once
        bra     po_st_state
po_st_lkey:
        move.l  %d7,%d1
        subq.l  #1,%d1
        move.l  T_MASK(%a5),%d4
        btst    %d1,%d4                  | the key already went before its voice started:
        bne     po_st_state
        moveq   #2,%d0                   | release at once
po_st_state:
        move.b  %d0,V_STATE(%a0)
        lea     po_seq(%pc),%a6
        addq.l  #1,(%a6)
        move.l  (%a6),V_AGE(%a0)
        subq.l  #1,%d6
        bne     po_st_note
po_st_done:
po_st_dup:
        rts

| ---- po_st_cpress: a live key K (d7, "----") -- is this a CHORD PRESS at the cap?
| d0 := 1 (NE) when K's start follows the track's previous live-key start
| within KR_WIN frames (150 ms), other keys are held, and every one of the
| track's VOIC (d6) voices is a held key's sounding note: K gets no voice
| then (the bass of the chord survives). Else 0 (EQ): the oldest active
| note is stolen as for a melody's run (a releasing voice goes first there).
| T_LASTK is stamped for every live key. Clobbers d0, d1, a0, a6, a2.
po_st_cpress:
        moveq   #0,%d0
        tst.l   %d7
        beq     po_cp_out                | a sequencer trig
        lea     po_clock(%pc),%a0
        move.l  CK_FRAMES(%a0),%d1
        move.l  %d1,%d0
        sub.l   T_LASTK(%a5),%d0
        move.l  %d1,T_LASTK(%a5)
        cmpi.l  #KR_WIN,%d0
        bhi     po_cp_no                 | the last key start was longer ago: a melody
        cmpi.l  #0x80,%d7
        bcc     po_cp_midi
        move.l  %d7,%d0
        subq.l  #1,%d0
        move.l  T_MASK(%a5),%d1
        bclr    %d0,%d1
        tst.l   %d1                      | the other keys held
        beq     po_cp_no
        bra     po_cp_count
po_cp_midi:
        lea     po_mheld(%pc),%a0
        move.l  %d2,%d0
        lsl.l   #3,%d0
        tst.b   1(%a0,%d0.l)             | a second note in the track's held list
        beq     po_cp_no
po_cp_count:
        bsr     po_voices_of             | a6 = the voices, a2 = their end (clobbers d0)
        moveq   #0,%d1                   | held keys' sounding notes
po_cp_1:
        mvz.b   V_STATE(%a6),%d0
        beq     po_cp_2                  | free: does not count
        cmpi.l  #1,%d0
        bne     po_cp_no                 | a releasing voice: the one to steal
        tst.b   V_KEY(%a6)
        beq     po_cp_no                 | a sequencer note: stolen as before
        addq.l  #1,%d1
po_cp_2:
        lea     V_STRIDE(%a6),%a6
        cmp.l   %a2,%a6
        bne     po_cp_1
        cmp.l   %d6,%d1
        bcs     po_cp_no                 | fewer than the cap: room
        moveq   #1,%d0                   | at the cap, all of them held: the newest key is dropped
        rts
po_cp_no:
        moveq   #0,%d0
po_cp_out:
        rts

| ==== LEG POLY: the legato hand-over on a paraphonic track (2 Oct 2026) ===========
| po_legkey (UI task, through the pointer block's -28: the quantizer's qz_leg2 for
| a CHROMATIC key, po_mon for a MIDI note): d2 = track, d0 = the identity of the
| key pressed while others are held, with LEG = POLY and VOIC 2..4. The press
| takes the stock TRIGLESS path (no START: the AMP envelope is not retriggered,
| the staged PTCH lock lands at the next frame); this only notes the key in the
| track record, and the frame (po_frame) does the rest once the lock has
| landed, po_handover:
|   * the PTCH delta since the last start is folded into every voice's root
|     and T_REF := T_W, so the targets below are absolute;
|   * WITH A SHAPE (chord memory): the voicing of (shape, inversion) for VOIC
|     notes at the new root (po_voicing, each note snapped onto the SCALE) is
|     assigned to the sounding voices in pitch order -- voice i slides (sy_slew,
|     from where it is, over GLIDE) to note i and belongs to the new key; with
|     more sounding voices than notes the extra ones release, with fewer the
|     missing notes start fresh voices;
|   * WITH "----": the NEWEST sounding voice (the highest V_AGE) slides to the
|     key's pitch and becomes the key's; the others hold (last-note legato).
|     No sounding voice: a fresh one (po_start1). (A key inside 150 ms of the
|     last key START is a chord press and never comes here: po_legmode.)
|   * a panel key is marked in T_SMASK (the same-scan sweep never starts it).
| Releasing: the old key's bit leaves the mask with nothing tagged to it; the
| voices go with the new key's release (po_frame's scan), and the last key's
| release posts the stock AMP release (the quantizer's qz_leg0, po_moff).
| GLIDE OFF: sy_slew snaps, so the chord changes at once without a retrigger.
po_legkey:
        move.l  %a0,-(%sp)
        move.l  %d1,-(%sp)
        lea     sy_state(%pc),%a0
        move.l  %d2,%d1
        lsl.l   #7,%d1
        adda.l  %d1,%a0
        move.b  %d0,T_LEGKEY(%a0)
        clr.b   T_LEGN(%a0)
        move.l  (%sp)+,%d1
        movea.l (%sp)+,%a0
        rts

| ---- po_handover: a5 = the track record, d2 = track, d7 = the identity, T_W = the
| new word. Clobbers d0, d1, d3, d4, d6, d7, a0, a1, a2, a6.
po_handover:
        cmpi.l  #0x80,%d7
        bcc     po_ho_fold0
        move.l  %d7,%d0                  | a panel key: started, as far as the sweep is concerned
        subq.l  #1,%d0
        move.l  T_SMASK(%a5),%d1
        bset    %d0,%d1
        move.l  %d1,T_SMASK(%a5)
po_ho_fold0:
        bsr     po_voices_of             | a6 = the voices, a2 = their end (clobbers d0)
        move.l  T_LAST(%a5),%d1          | what PTCH moved since the last start, up to LAST frame (the
        sub.l   T_REF(%a5),%d1           | key's lock landed this frame and is the new root's alone) ...
po_ho_fold:
        tst.b   V_STATE(%a6)
        beq     po_ho_fold1
        add.l   %d1,V_ROOT(%a6)          | ... folded into every active voice's root
po_ho_fold1:
        lea     V_STRIDE(%a6),%a6
        cmp.l   %a2,%a6
        bne     po_ho_fold
        move.l  T_W(%a5),%d1
        move.l  %d1,T_REF(%a5)           | the targets are the roots from here
        move.l  #CV_STRIDE,%d0
        muls.l  %d2,%d0
        lea     CURVALS,%a0
        mvz.b   CV_CHRD(%a0,%d0.l),%d3   | the chord byte, locks applied: shape << 2 | inversion
        mvz.b   CV_VOIC(%a0,%d0.l),%d6   | VOIC 1..4 (as po_st_v1)
        subq.l  #1,%d6
        cmpi.l  #3,%d6
        bls     po_ho_v1
        moveq   #0,%d6
po_ho_v1:
        addq.l  #1,%d6                   | n
        move.l  %d3,%d0
        lsr.l   #2,%d0                   | the shape
        beq     po_ho_single
        move.l  %d3,%d1
        andi.l  #3,%d1                   | the inversion
        move.l  %d6,%d3                  | n notes
        lea     po_vbuf(%pc),%a1
        bsr     po_voicing               | the voicing's n offsets, ascending, into po_vbuf (clobbers d0, d1, a0)
        lea     -20(%sp),%sp             | SORTED[4] at 0: the sounding voices by root, ascending; k at 16
        clr.l   16(%sp)
        bsr     po_voices_of
po_ho_col:
        mvz.b   V_STATE(%a6),%d0
        cmpi.l  #1,%d0
        bne     po_ho_col2
        move.l  16(%sp),%d1              | i = k: insert a6 by V_ROOT
po_ho_ins:
        tst.l   %d1
        beq     po_ho_put
        movea.l -4(%sp,%d1.l*4),%a0      | SORTED[i - 1]
        move.l  V_ROOT(%a0),%d0
        cmp.l   V_ROOT(%a6),%d0
        ble     po_ho_put                | not above the new one: it goes at i
        move.l  %a0,(%sp,%d1.l*4)        | else that one moves up
        subq.l  #1,%d1
        bra     po_ho_ins
po_ho_put:
        move.l  %a6,(%sp,%d1.l*4)
        addq.l  #1,16(%sp)
po_ho_col2:
        lea     V_STRIDE(%a6),%a6
        cmp.l   %a2,%a6
        bne     po_ho_col
        moveq   #0,%d3                   | i
        lea     po_vbuf(%pc),%a1
po_ho_as:
        cmp.l   %d6,%d3
        bcc     po_ho_extra              | i >= n: the rest release
        mvs.b   (%a1)+,%d0               | offset i
        move.l  #SEMI,%d1
        muls.l  %d1,%d0
        add.l   T_W(%a5),%d0
        bsr     po_snap                  | note i, on the scale (clobbers d1, d4)
        move.l  16(%sp),%d4
        cmp.l   %d4,%d3
        bcc     po_ho_fresh              | i >= k: a fresh voice for it
        movea.l (%sp,%d3.l*4),%a0        | SORTED[i] slides to note i ...
        move.l  %d0,V_ROOT(%a0)
        move.b  %d7,V_KEY(%a0)           | ... and is the key's
        clr.l   V_HOLD(%a0)
        bra     po_ho_next
po_ho_fresh:
        move.l  %d0,-(%sp)
        bsr     po_alloc                 | a0 = a free voice (k < n: one exists; clobbers d0, d1, d4, a6)
        move.l  (%sp)+,%d0
        clr.l   V_PHM(%a0)               | as po_st_note starts one
        clr.l   V_LASTM(%a0)
        clr.l   V_GAIN(%a0)
        clr.l   V_IEFF(%a0)
        clr.w   V_ERAMP(%a0)
        move.l  #ENV_ONE,%d1
        move.l  %d1,V_ENV(%a0)
        move.l  %d0,V_ROOT(%a0)
        lsl.l   #8,%d0
        lsl.l   #4,%d0
        move.l  %d0,V_CUR(%a0)           | at its own pitch
        move.b  %d7,V_KEY(%a0)
        clr.l   V_HOLD(%a0)
        lea     po_clock(%pc),%a6
        move.l  CK_FRAMES(%a6),%d0
        move.l  %d0,V_FRAME(%a0)
        move.b  #1,V_STATE(%a0)
        lea     po_seq(%pc),%a6
        addq.l  #1,(%a6)
        move.l  (%a6),V_AGE(%a0)
po_ho_next:
        addq.l  #1,%d3
        cmpi.l  #4,%d3
        bcs     po_ho_as
        bra     po_ho_done
po_ho_extra:                             | SORTED[i .. k) release
        move.l  16(%sp),%d4
        cmp.l   %d4,%d3
        bcc     po_ho_done
        movea.l (%sp,%d3.l*4),%a0
        move.b  #2,V_STATE(%a0)
        addq.l  #1,%d3
        bra     po_ho_extra
po_ho_done:
        lea     20(%sp),%sp
        rts
po_ho_single:                            | "----": the NEWEST sounding voice takes the key and its pitch
        bsr     po_voices_of
        suba.l  %a1,%a1
        moveq   #0,%d4                   | the highest V_AGE so far
po_ho_new:
        mvz.b   V_STATE(%a6),%d0
        cmpi.l  #1,%d0
        bne     po_ho_new1
        move.l  V_AGE(%a6),%d0
        cmp.l   %d4,%d0
        bls     po_ho_new1
        move.l  %d0,%d4
        movea.l %a6,%a1
po_ho_new1:
        lea     V_STRIDE(%a6),%a6
        cmp.l   %a2,%a6
        bne     po_ho_new
        move.l  %a1,%d0
        beq     po_start1                | nothing sounds: a fresh voice for the key (d7, T_W)
        move.l  T_W(%a5),%d0
        bsr     po_snap                  | the key's word, on the scale
        move.l  %d0,V_ROOT(%a1)          | it slides there from where it is
        move.b  %d7,V_KEY(%a1)
        clr.l   V_HOLD(%a1)
        rts

| ---- po_legmode: d2 = track -> d0 = what a CHROMATIC key (or a MIDI note) pressed
| while another is held does on the track -- THE LEG GATE (2 Oct 2026; the
| quantizer reaches it through the pointer block's -24, po_mon directly):
|   0  stock: the held note ends, the new one starts (a sample track with
|      GLIDE OFF; a synth track at VOIC 1 with LEG OFF)
|   1  mono legato: the trigless path, the mono voice slews (VOIC 1, LEG MONO or
|      POLY); a SAMPLE track with LEG MONO (the 2.6 trigless path: the key
|      changes the pitch at once, no retrigger; GLIDE is not read there)
|   2  paraphonic: the key gets a voice of its own, no legato (VOIC 2..4 with
|      LEG OFF or MONO; and with LEG POLY and CHRD "----" a CHORD PRESS: a key
|      inside KR_WIN frames -- 150 ms, the recorder's chord window -- of the
|      track's last live key START (T_LASTK), so a chord fingered on the keys
|      still gets its voices)
|   3  paraphonic legato: the trigless path and po_legkey, the chord follows the
|      key (VOIC 2..4, LEG POLY: with a shape always; with "----" a key later
|      than the chord window)
| LEG is the Part's AMP page-2 byte 5 (AMP_P2_OFF + track * 30 + 5: the AMP
| SETUP page's sixth box, TRIG's byte, po_amp_desc): 0 OFF, 1 MONO, 2 POLY (3
| and 4, a stock knob's reach on the empty box, read as POLY; on a sample
| track any nonzero byte is MONO). A stock Part reads OFF. tst.l d0 done;
| preserves every other register.
po_legmode:
        bsr     po_is_synth
        beq     po_lm_sample             | not a synth track: its LEG byte, 0 -> 0 (stock), else 1 (mono legato)
        lea     -16(%sp),%sp
        movem.l %d1/%d3/%d4/%a0,(%sp)
        movea.l PART_PTR,%a0
        mvz.b   PART_IDX,%d0
        move.l  #6322,%d1
        muls.l  %d1,%d0
        adda.l  %d0,%a0                  | the Part
        move.l  %d2,%d1
        lsl.l   #3,%d1
        move.l  %d1,%d0
        add.l   %d1,%d1
        add.l   %d0,%d1                  | track * 24
        adda.l  #LFO_PAGE_OFF,%a0
        mvz.b   2(%a0,%d1.l),%d3         | VOIC
        mvz.b   5(%a0,%d1.l),%d4         | CHRD (shape << 2 | inversion)
        suba.l  #LFO_PAGE_OFF,%a0
        move.l  %d2,%d1
        lsl.l   #5,%d1
        sub.l   %d2,%d1
        sub.l   %d2,%d1                  | track * 30
        adda.l  #AMP_P2_OFF,%a0
        mvz.b   LEG_SLOT2(%a0,%d1.l),%d0 | LEG: 0 OFF, 1 MONO, 2.. POLY
        subq.l  #2,%d3
        cmpi.l  #2,%d3                   | VOIC 2..4?
        bls     po_lm_para
        tst.l   %d0                      | VOIC 1: OFF -> 0 (stock), else 1 (mono legato)
        beq     po_lm_out
        moveq   #1,%d0
        bra     po_lm_out
po_lm_para:
        cmpi.l  #2,%d0                   | VOIC 2..4: POLY -> 3 (or a chord press, 2), else 2
        bcc     po_lm_leg
po_lm_two:
        moveq   #2,%d0
        bra     po_lm_out
po_lm_leg:
        lsr.l   #2,%d4                   | a shape: legato
        bne     po_lm_three
        lea     sy_state(%pc),%a0        | "----": inside the chord window of the track's last live
        move.l  %d2,%d1                  | key START (po_st_cpress stamps T_LASTK) the key is a chord
        lsl.l   #7,%d1                   | press -- a voice of its own
        move.l  po_clock+CK_FRAMES(%pc),%d0
        sub.l   T_LASTK(%a0,%d1.l),%d0
        cmpi.l  #KR_WIN,%d0
        bls     po_lm_two
po_lm_three:
        moveq   #3,%d0
po_lm_out:
        movem.l (%sp),%d1/%d3/%d4/%a0
        lea     16(%sp),%sp
        tst.l   %d0
        rts
po_lm_sample:
        lea     -8(%sp),%sp              | a sample track (3 Oct 2026): LEG OFF -> 0 (stock), LEG MONO (any
        movem.l %d3/%a0,(%sp)            | nonzero byte) -> 1 (the trigless path: instant pitch, no retrigger).
        bsr     po_legbyte               | GLIDE is not consulted (it was the switch until 3 Oct 2026).
        movem.l (%sp),%d3/%a0
        lea     8(%sp),%sp
        tst.l   %d0
        beq     po_lm_ret
        moveq   #1,%d0
po_lm_ret:
        rts

| ---- po_snap: d0 := the note word d0 snapped onto the scale (T_SCALE, 0 = as is) --
| The quantizer's rule (quantizer.s qz_chrom): the note's pitch class -- its
| semitone number from PTCH raw 64, the scale's root -- is moved to the nearest
| degree of the mask, the lower candidate first at each distance (ties go
| down). The word keeps its fraction: only whole semitones are added. Uses
| d1, d4 (d2, d6 saved); a5 = the track record.
po_snap:
        move.l  T_SCALE(%a5),%d4
        beq     po_sn_ret                | SCALE OFF
        lea     -8(%sp),%sp
        move.l  %d2,(%sp)                | (po_start's track and note count)
        move.l  %d6,4(%sp)
        move.l  %d0,%d6
        subi.l  #0x4000,%d6
        addi.l  #0x280+120*SEMI,%d6      | word - root + half a semitone, biased by 120 semitones
        move.l  #SEMI,%d2
        divu.l  %d2,%d6                  | n + 120: the nearest semitone number from the root
        addi.l  #1080,%d6                | n + 1200
        move.l  %d6,%d1
        moveq   #12,%d2
        divu.l  %d2,%d1                  | / 12 ...
        move.l  %d1,%d2
        add.l   %d2,%d2
        add.l   %d1,%d2                  | 3 q ...
        lsl.l   #2,%d2                   | ... * 4 = 12 q
        sub.l   %d2,%d6
        move.l  %d6,%d2                  | pc = 0..11
        moveq   #0,%d1                   | the distance
po_sn_dist:
        move.l  %d2,%d6
        sub.l   %d1,%d6                  | the lower candidate first
        bpl     po_sn_lo
        addi.l  #12,%d6
po_sn_lo:
        btst    %d6,%d4
        bne     po_sn_down
        move.l  %d2,%d6
        add.l   %d1,%d6                  | then the upper
        cmpi.l  #12,%d6
        blt     po_sn_hi
        subi.l  #12,%d6
po_sn_hi:
        btst    %d6,%d4
        bne     po_sn_up
        addq.l  #1,%d1
        cmpi.l  #6,%d1
        ble     po_sn_dist
        moveq   #0,%d1                   | no degree at all (cannot happen: every mask has the root)
        bra     po_sn_out
po_sn_down:
        neg.l   %d1
po_sn_up:
        move.l  #SEMI,%d6
        muls.l  %d1,%d6
        add.l   %d6,%d0                  | the word moved by whole semitones, its fraction kept
po_sn_out:
        move.l  (%sp),%d2
        move.l  4(%sp),%d6
        lea     8(%sp),%sp
po_sn_ret:
        rts

| ---- po_alloc: a0 := the voice of track d2 to take for a new note ---------------
| A free voice (state 0) first, else the oldest releasing one, else the oldest
| sounding one: the least (rank << 28 | age) with rank 0 / 1 / 2. Clobbers d0,
| d1, d4, a6; saves d3, d6 and a1 for po_start.
| po_steal (the VOIC cap): the same search with a free voice ranked last (3),
| so a0 := the oldest releasing voice, else the oldest sounding one -- the
| one to cut when the track is over its cap (po_start calls it only while an
| active voice exists).
po_steal:
        lea     -12(%sp),%sp
        movem.l %d3/%d6/%a1,(%sp)
        lea     po_rank_act(%pc),%a1
        bra     po_al_go
po_alloc:
        lea     -12(%sp),%sp
        movem.l %d3/%d6/%a1,(%sp)
        lea     po_rank(%pc),%a1
po_al_go:
        lea     po_voices(%pc),%a6
        move.l  %d2,%d0
        lsl.l   #8,%d0
        add.l   %d0,%a6
        move.l  %a6,%a0
        moveq   #-1,%d4                  | the best key so far (unsigned)
        moveq   #4,%d6
po_al_loop:
        mvz.b   V_STATE(%a6),%d0
        mvz.b   (%a1,%d0.l),%d0
        lsl.l   #8,%d0
        lsl.l   #8,%d0
        lsl.l   #8,%d0
        lsl.l   #4,%d0                   | rank << 28
        move.l  V_AGE(%a6),%d3
        andi.l  #0x0fffffff,%d3
        or.l    %d0,%d3
        cmp.l   %d4,%d3
        bcc     po_al_next               | not better
        move.l  %d3,%d4
        move.l  %a6,%a0
po_al_next:
        lea     V_STRIDE(%a6),%a6
        subq.l  #1,%d6
        bne     po_al_loop
        movem.l (%sp),%d3/%d6/%a1
        lea     12(%sp),%sp
        rts
po_rank:
        .byte   0, 2, 1, 0
po_rank_act:                             | po_steal: free voices last
        .byte   3, 2, 1, 3
        .align  2

| ==== PARAPHONIC: the samples -- every sounding voice summed into the record =====
| From sy_check: a1 = the first L long, d7 = the source count, a3 = the track
| record, 52(sp) = track. Each voice adds c * gain (Q15, at most T_GMAX =
| 32768 / sqrt(VOIC)) into the L long: the sum is Q29 with FS = 0x20000000 =
| 32768 * 0x4000, the mono voice's full scale (c = +-0x4000), the ceiling
| the DSP chain wants (above it the track clipped, 28 Sep 2026). PLAN B (28 Sep
| 2026): the final pass is the doubling into the mono format with a SATURATING
| CLAMP on the sum only -- the peak limiter that follows in this note is HISTORY
| (removed: its gain movement was itself a level modulation under chords; the
| level law 1/sqrt(VOIC) alone bounds a single note at 0.5 FS and a VOIC 4 chord's
| coincident peaks at 2.0 FS, clamped). History (29 Sep 2026): a PEAK LIMITER, a gain and not a curve: the frame's
| peak |x| is scanned; the track's gain g (T_LIM, Q16) releases toward 1.0
| by 1/2048 of the deficit a frame (tau = 0.74 s) and is pulled down to FS /
| peak at once when this frame's peak would pass FS, so no sample ever
| exceeds FS (the attack is the frame, 0.36 ms, and the sum only grows over
| the 8-frame ramp or a beat, so the steps are small); at g = 1.0 (a single
| note at any VOIC peaks at 0.71 FS at most; chords until their peaks
| coincide) the samples pass untouched; else each is x * g (mac.l, the
| fractional EMAC as po_rate uses it). A silent frame (peak 0: every voice
| freed) and po_free (a chord-memory start) reset g to 1.0. Then the doubling
| as the mono path does (c * g << 1, the high word is the sample) and R := L.
| A soft-clip curve was simulated first and rejected: with equal-power gains
| two notes at VOIC 2 sum to 1.41 FS at every coincidence, and any waveshaper
| under 1.0 FS puts intermodulation at -17..-19 dB on ordinary chords -- the
| clipping of OCTATRIK11 again, only rounder. The gain costs 6 instructions
| a sample for the scan and 4 for the multiply (only while g < 1.0), plus a
| divu.l a frame while limiting. The saturation after the doubling is only a
| guard: |x * g| <= FS always.
po_fill_add:                             | BUILD 32: the mono voice's samples are in the record (sy_gend): the
        moveq   #1,%d4                   | fading voices are ADDED to them -- each L long, (c * g) << 1 with its low
        bra     po_fill1                 | word cleared, is halved into the sum's format (c * g) first
po_fill:
        moveq   #0,%d4                   | the record is cleared first
po_fill1:
        move.l  52(%sp),%d2              | track
        lea     -24(%sp),%sp             | (sp) L longs, 4 count, 8 voices' end, 12 track record, 16 the voice's gain step, 20 its index step
        move.l  %a1,(%sp)                | the first L long
        move.l  %d7,4(%sp)               | the count
        move.l  %a3,12(%sp)              | the track record
        move.l  %a1,%a0
        move.l  %d7,%d0
        tst.l   %d4
        bne     po_fi_half
po_fi_clear:
        clr.l   (%a0)
        addq.l  #8,%a0
        subq.l  #1,%d0
        bne     po_fi_clear
        bra     po_fi_voices
po_fi_half:
        move.l  (%a0),%d1
        asr.l   #1,%d1
        move.l  %d1,(%a0)
        addq.l  #8,%a0
        subq.l  #1,%d0
        bne     po_fi_half
po_fi_voices:
        bsr     po_voices_of             | a6 = the voices, a2 = their end
        move.l  %a2,8(%sp)
po_fi_voice:
        tst.b   V_STATE(%a6)
        beq     po_fi_next
        move.l  %a6,%a3
        move.l  (%sp),%a1
        move.l  4(%sp),%d7
        move.l  V_PHC(%a3),%d0
        move.l  V_PHM(%a3),%d6
        move.l  V_INC(%a3),%d5
        move.l  V_INCM(%a3),%a2
        move.l  V_LASTM(%a3),%a4
        mvs.w   V_ISTEP(%a3),%d1         | the index step a sample (po_frame's; consumed: a voice po_frame does not
        move.l  %d1,20(%sp)              | visit -- one fading under the mono voice -- holds its index)
        clr.w   V_ISTEP(%a3)
        move.l  V_GAIN(%a3),%d1          | the gain this frame ends at (po_frame's target) ...
        mvz.w   V_GPREV(%a3),%d2         | ... from the one the last frame ended at
        move.w  %d1,V_GPREV(%a3)
        sub.l   %d2,%d1
        swap    %d1
        clr.w   %d1                      | (target - previous) << 16 ...
        divs.l  %d7,%d1                  | ... / the frame's samples = the step, Q15.16
        move.l  %d1,16(%sp)
        swap    %d2
        clr.w   %d2
        move.l  %d2,%a5                  | the running gain, Q15.16 (a5 is restored by sy_done)
        lea     sy_tab(%pc),%a0
        moveq   #24,%d3
po_fi_loop:
        move.l  %a4,%d1
        muls.l  V_FB(%a3),%d1            | feedback: m_prev * fb
        add.l   %d6,%d1                  | modulator phase
        move.l  %d1,%d2
        lsr.l   %d3,%d2
        add.l   %d2,%d2
        mvs.w   (%a0,%d2.l),%d4          | a = tab[i]
        mvs.w   2(%a0,%d2.l),%d2         | b = tab[i+1]
        sub.l   %d4,%d2
        lsr.l   #8,%d1
        mvz.w   %d1,%d1                  | fraction, Q16
        muls.l  %d1,%d2
        asr.l   #8,%d2
        asr.l   #8,%d2
        add.l   %d2,%d4                  | m, Q14
        move.l  %d4,%a4                  | m_prev
        move.l  V_IEFF(%a3),%d1          | the index one step on (a linear ramp across the frame; BUILD 38)
        add.l   20(%sp),%d1
        move.l  %d1,V_IEFF(%a3)
        muls.l  %d1,%d4                  | m * I: the phase offset (wraps: it is a phase)
        add.l   %d0,%d4                  | carrier phase, modulated
        move.l  %d4,%d2
        lsr.l   %d3,%d2
        add.l   %d2,%d2
        mvs.w   (%a0,%d2.l),%d1          | a
        mvs.w   2(%a0,%d2.l),%d2         | b
        sub.l   %d1,%d2
        lsr.l   #8,%d4
        mvz.w   %d4,%d4
        muls.l  %d4,%d2
        asr.l   #8,%d2
        asr.l   #8,%d2
        add.l   %d2,%d1                  | c, Q14
        adda.l  16(%sp),%a5              | the gain one step on (a linear ramp across the frame: no step at its edge)
        move.l  %a5,%d2
        swap    %d2                      | its integer part, Q15
        muls.w  %d2,%d1                  | c * gain (16 x 16: c is +-0x4000, the gain at most 23170)
        add.l   %d1,(%a1)                | into the sum
        addq.l  #8,%a1
        add.l   %d5,%d0
        add.l   %a2,%d6
        subq.l  #1,%d7
        bne     po_fi_loop
        move.l  %d0,V_PHC(%a3)
        move.l  %d6,V_PHM(%a3)
        move.l  %a4,V_LASTM(%a3)
po_fi_next:
        lea     V_STRIDE(%a6),%a6
        cmp.l   8(%sp),%a6
        bne     po_fi_voice
| ---- the final pass (plan B: the peak limiter is gone -- the sum is what the
| voices add up to, saturated only if it wraps) ---------------------------------
po_fi_unity:
        move.l  (%sp),%a1                | the final pass: sum * 2 (the mono format), saturated (the clamp), L and R
        move.l  4(%sp),%d7
po_fi_out:
        move.l  (%a1),%d1
        add.l   %d1,%d1
        bvs     po_fi_sat
po_fi_put:
        clr.w   %d1
        move.l  %d1,(%a1)+               | L
        move.l  %d1,(%a1)+               | R
        subq.l  #1,%d7
        bne     po_fi_out
        lea     24(%sp),%sp
        bra     sy_done
po_fi_sat:
        bmi     po_fi_satp               | the doubled sum wrapped: its sign says which way
        move.l  #0x80000000,%d1
        bra     po_fi_put
po_fi_satp:
        move.l  #0x7fff0000,%d1
        bra     po_fi_put

| ==== po_lfo3: the LFO engine's depth read (jmp, 8 bytes), twice ==================
| The engine exists twice in the OS, the same code: a routine at 0x40003b90
| and a copy inlined in the frame builder at 0x4000cf40 (the one that runs
| for the audio tracks' frames). At the depth read of both -- `mvsw
| %a2@(0x12,%d2:l:2),%d0; lea %a0@(0,%d4:l:2),%a1` at 0x40003ca4 and at
| 0x4000d03e -- d2 = the LFO (2 = LFO 3), a4 = the track's LFO state
| (LFO_STATE + 8 * track), a2 = its fp record, a0 = its staging record. On a
| track playing a synth voice LFO 3's depth reads as 0, whatever VOIC: the
| chord byte modulates nothing. d1/d3/d4/d7 are dead here (reloaded by the
| code that follows); a0 is done with. The stubs share po_lfo3_depth.
po_lfo3:
        bsr     po_lfo3_depth
        jmp     0x40003cac
po_lfo3b:
        move.l  %a4,%d1
        subi.l  #LFO_STATE,%d1
        bne     po_l3b_depth
        cmpi.l  #2,%d2
        bne     po_l3b_depth
        bsr     po_tick                  | track 0, LFO 3: the clock, once a frame
po_l3b_depth:
        bsr     po_lfo3_depth
        jmp     0x4000d046
po_lfo3_depth:
        mvs.w   0x12(%a2,%d2.l*2),%d0    | displaced: the depth
        lea     (%a0,%d4.l*2),%a1        | displaced
        cmpi.l  #2,%d2
        bne     po_l3_back
        move.l  %a4,%d1                  | (whatever VOIC: slot 5 is the chord byte on a synth track,
        subi.l  #LFO_STATE,%d1
        lsr.l   #3,%d1                   | the track
        lsl.l   #7,%d1
        lea     sy_state(%pc),%a0        | and stock's depth on it would be a pitch LFO, 24 Sep 2026)
        tst.b   S_ON(%a0,%d1.l)          | its playing voice is a synth?
        beq     po_l3_back
        moveq   #0,%d0                   | muted
po_l3_back:
        rts

| ==== po_lfopage: the page resolver's LFO-descriptor load, 0x40031e62 (jmp, 8 B) ==
| `movel #0x400d37f6,%d0; bras 0x40031ed6`. d3 = track, d1 = part index, a1 =
| the bank blob, d5 = the machine byte (0x40031e2a); d2-d5 are restored by the
| epilogue at RESOLVER_RET, d0/d1/a0/a1 are C scratch. For a FLEX track whose
| assigned FLEX slot's sample is named SYNTH* (page.s's test) the clone --
| built from the stock descriptor on first use -- is returned.
po_lfopage:
        move.l  #LFO_P,%d0               | displaced: the stock descriptor
        cmpi.l  #1,%d5                   | FLEX?
        bne     po_lp_done
        move.l  #6322,%d2
        muls.l  %d1,%d2                  | part * 6322
        add.l   %a1,%d2                  | + the bank blob
        move.l  %d3,%d4
        lsl.l   #2,%d4
        add.l   %d3,%d4                  | track * 5
        add.l   %d4,%d2
        move.l  %d2,%a0
        add.l   #SLOT_OFF,%a0
        mvz.b   (%a0),%d2                | the track's FLEX slot, 0-based
        cmpi.l  #127,%d2
        bhi     po_lp_done               | 0xff = none; 128.. = the recorder buffers
        move.l  #SETTINGS_STRIDE,%d4
        muls.l  %d2,%d4
        addi.l  #SETTINGS_BASE,%d4
        move.l  %d4,%a0                  | the slot's settings record; its path at +0
        move.l  %a0,%a1
        move.l  #255,%d4
po_lp_scan:
        mvz.b   (%a0)+,%d5
        beq     po_lp_scanned
        cmpi.l  #'/',%d5
        bne     po_lp_scan1
        move.l  %a0,%a1
po_lp_scan1:
        subq.l  #1,%d4
        bne     po_lp_scan
po_lp_scanned:
        move.w  #0x0000,%d5              | no alt prefix; marker is CXOSC* only
        cmp.w   (%a1),%d5
        bne     po_lp_fm
        addq.l  #2,%a1
po_lp_fm:
        lea     sy_name(%pc),%a0
        moveq   #5,%d4
po_lp_cmp:
        mvz.b   (%a0)+,%d5
        mvz.b   (%a1)+,%d2
        cmp.l   %d2,%d5
        bne     po_lp_done
        subq.l  #1,%d4
        bne     po_lp_cmp
        lea     po_lfodesc(%pc),%a1
        tst.b   po_lfo_built
        bne     po_lp_have
        lea     LFO_P,%a0                | the clone: the stock record ...
        move.l  #LFO_DESC_LEN,%d4
po_lp_copy:
        move.b  (%a0)+,(%a1)+
        subq.l  #1,%d4
        bne     po_lp_copy
        lea     po_lfodesc(%pc),%a1
        lea     po_chrd(%pc),%a0         | ... slot 5 named CHRD (6 bytes) ...
        move.l  (%a0)+,0x16+30(%a1)
        move.w  (%a0),0x16+34(%a1)
        lea     po_fmt_chord(%pc),%a0    | ... its formatter the shape's name ...
        move.l  %a0,0xca+20(%a1)
        lea     po_voic(%pc),%a0         | ... slot 2 (SPD3, LFO 3 being muted here) named VOIC ...
        move.l  (%a0)+,0x16+12(%a1)
        move.w  (%a0),0x16+16(%a1)
        lea     po_fmt_voic(%pc),%a0     | ... printing 1..4 ...
        move.l  %a0,0xca+8(%a1)
        moveq   #1,%d4                   | ... range 1..4, default 1 (the knob clamps to them;
        move.l  %d4,0x6a+8(%a1)          | a Part's stock byte 32 reads as 1 until turned) ...
        move.b  %d4,0x5e+2(%a1)
        moveq   #4,%d4
        move.l  %d4,0x9a+8(%a1)
        clr.l   0x12a+8(%a1)             | ... the stock enum stepper (handler 0, as PMTR/WAVE: one
                                         | step a detent; the accumulator handlers scale by the range) ...
        move.l  0x18e(%a1),%d4           | ... both always shown (nibbles 2 and 5, bit 2)
        andi.l  #0xff0ff0ff,%d4
        ori.l   #0x00500500,%d4
        move.l  %d4,0x18e(%a1)
        lea     po_lfo_built(%pc),%a0
        move.b  #1,(%a0)
po_lp_have:
        move.l  %a1,%d0
po_lp_done:
        jmp     RESOLVER_RET

| ---- po_fmt_voic: fmt(buf, value) -> "1".."4" (a byte outside 1..4 reads 1, as the engine reads it) --
po_fmt_voic:
        move.l  8(%sp),%d0
        subq.l  #1,%d0
        cmpi.l  #3,%d0
        bls     po_fv1
        moveq   #0,%d0
po_fv1:
        addq.l  #1,%d0
po_fv2:
        move.l  %d0,-(%sp)
        pea     po_f_d(%pc)
        move.l  12(%sp),-(%sp)           | buf
        jsr     SPRINTF
        lea     12(%sp),%sp
        rts

| ---- po_fmt_chord: fmt(buf, value) -> the shape's name and its inversion ("MAJ",
| "MAJ1", "MAJ2", "MAJ3": the byte is shape << 2 | inversion, 26 Sep 2026; the
| name is at most three characters so the digit fits the four-character box);
| "----" while the current track's Part VOIC is 1 (the chord has no effect then)
| or for shape 0 (no inversion printed). Written into buf directly.
po_fmt_chord:
        movea.l PART_PTR,%a0
        mvz.b   PART_IDX,%d0
        move.l  #6322,%d1
        muls.l  %d1,%d0
        adda.l  %d0,%a0                  | the Part
        adda.l  #LFO_PAGE_OFF,%a0
        mvz.b   UI_TRACK,%d0
        lsl.l   #3,%d0                   | track * 8 ...
        move.l  %d0,%d1
        add.l   %d1,%d0
        add.l   %d1,%d0                  | ... * 3 = track * 24
        mvz.b   2(%a0,%d0.l),%d0         | its VOIC
        subq.l  #2,%d0
        cmpi.l  #2,%d0                   | 2..4: the shape
        bls     po_fc_shape
        moveq   #0,%d0                   | 1: "----"
        moveq   #0,%d1
        bra     po_fc_name
po_fc_shape:
        move.l  8(%sp),%d0               | the value
        move.l  %d0,%d1
        andi.l  #3,%d1                   | the inversion
        lsr.l   #2,%d0
        andi.l  #31,%d0                  | the shape
        bne     po_fc_name
        moveq   #0,%d1                   | "----": no inversion
po_fc_name:
        lsl.l   #2,%d0                   | 4 bytes a name
        lea     po_names(%pc),%a0
        lea     (%a0,%d0.l),%a0
        movea.l 4(%sp),%a1               | buf
        moveq   #4,%d0
po_fc_cp:
        tst.b   (%a0)
        beq     po_fc_inv
        move.b  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne     po_fc_cp
po_fc_inv:
        tst.l   %d1
        beq     po_fc_end
        addi.l  #'0',%d1
        move.b  %d1,(%a1)+               | the inversion digit
po_fc_end:
        clr.b   (%a1)
        rts

| ==== po_pgdesc(a1 = page.s's patch list) -> d0 = the FM SYNTH PLAYBACK descriptor ==
| Called by page.s's pg_resolve (the resolver's PLAYBACK-page detour, a UI-task
| path: the resolver 0x40031da4 serves the page renderer, the footer and the
| knob handler, never the audio interrupt) through the pointer word before
| sy_render, for a FLEX track whose sample is named SYNTH*. The clone is
| built on first use: the stock FLEX PLAYBACK descriptor (FLEX_P, 402 B, read
| from the OS image in DRAM, never written) is copied into po_pgdesc_buf,
| this unit's own RAM, and page.s's overrides are applied over the copy --
| {offset.w, length.w, source.l} records, a negative offset ending the list:
| the title, the four synth slot names, the formatter and widget pointers
| into the pinned page cave, the enable nibbles. page.s owns the layout;
| this routine only copies. The built flag and the buffer are runtime data,
| depacked as zeros by the loader at every boot, so a power cycle rebuilds
| the clone (the LFO page's po_lfodesc works the same way). The repository
| carries none of the record's stock bytes. Clobbers d0/d1/a0/a1 only.
po_pgdesc:
        lea     -8(%sp),%sp
        movem.l %a2-%a3,(%sp)
        lea     po_pgdesc_buf(%pc),%a2   | the clone
        tst.b   po_pg_built
        bne     po_pg_have
        lea     FLEX_P,%a0               | the stock record ...
        move.l  %a2,%a3
        move.l  #FLEX_DESC_LEN,%d1
po_pg_copy:
        move.b  (%a0)+,(%a3)+
        subq.l  #1,%d1
        bne     po_pg_copy
po_pg_patch:                             | ... then page.s's fields over it
        mvs.w   (%a1)+,%d0               | the field's offset; negative ends the list
        blt     po_pg_built_now
        mvz.w   (%a1)+,%d1               | its length
        move.l  (%a1)+,%a0               | its bytes, in the page cave
        lea     (%a2,%d0.l),%a3
po_pg_byte:
        move.b  (%a0)+,(%a3)+
        subq.l  #1,%d1
        bne     po_pg_byte
        bra     po_pg_patch
po_pg_built_now:                         | ... then the six knob handlers (P+0x12a, 4 B a slot) -> po_knob
        lea     po_knob(%pc),%a0         | (30 Sep 2026: page.s's list zeroes PTCH's and FINE's, which the
        move.l  %a0,%d1                  | stock caller reads as its default stepper 0x4003240c -- one unit
        lea     KN_SLOTS(%a2),%a3        | a detent, x7 pressed, no FUNC; the unit's own address is only
        moveq   #6,%d0                   | known here, so the clone is finished here)
po_pg_knob:
        move.l  %d1,(%a3)+
        subq.l  #1,%d0
        bne     po_pg_knob
        lea     po_pg_built(%pc),%a0
        move.b  #1,(%a0)
po_pg_have:
        move.l  %a2,%d0
        movem.l (%sp),%a2-%a3
        lea     8(%sp),%sp
        rts

| ==== po_knob(slot, detents, value) -> d0 = the new raw value: the FM SYNTH page's
| knob handler (30 Sep 2026) ==================================================
| The stock knob routine 0x40055008 (PARAM_PAGES.md) reads the Part byte, calls
| the descriptor's per-slot handler (P+0x12a + 4*slot; 0 = its default stepper
| 0x4003240c) with (slot, detents, value) on the C stack, clamps d0 to the
| slot's [min, min+count-1] (P+0x6a, P+0x9a) and stores the byte -- so this
| routine never clamps: PTCH -64..+63 (raw 0..127), FINE the same, INDX FDBK
| DEC 0..127, RATO 0..127 (free Q8 0.25..4: q8 = 64 + raw * 960 / 127). The
| flags are read the way the stock handlers read them (0x40032d08, the sample
| tracks' PTCH; 0x4003240c): [FUNCTION] is the long 0x46c7dd26 (nonzero while
| held), the encoder's PUSH switch is the key record of code 0x38 + slot
| (PANEL.md: records of 0x18 B at 0x46c7d8de; +0x10 nonzero while the key is
| held), and PERSONALIZE's DISABLE FUNCTION + ENCODER is the long 0x800000a0
| (nonzero = the FUNC layer is off, as in the stock handlers). What a detent
| does (manual 5.2.1 / 5.2.2 on the synth's own units):
|   plain           one unit (a semitone, a cent, one of 128, one raw of RATO)
|   knob pressed    seven units (QUICK PARAMETER EDITING)
|   FUNC held       PTCH 12 semitones (an octave), FINE 10 cents, INDX FDBK DEC
|                   16 units; RATO the next classic table ratio <= 4.01
|                   (sy_rato_snap); off either end stays
|   (FUNC wins over the push; the caller's clamp ends every run)
| A synth track's PTCH with the SCALE on: the quantizer's store hook (qz_knob
| at 0x40055170) recomputes the value from the detent count, by scale degree,
| as it does for the stock handler -- FUNC and the push count as degrees there.
| Sample tracks never reach this routine (their PLAYBACK page is stock).
| Clobbers d0/d1/a0 (C scratch); d2-d5 saved.
po_knob:
        lea     -16(%sp),%sp
        movem.l %d2-%d5,(%sp)
        move.l  20(%sp),%d2              | the slot, 0..5
        move.l  24(%sp),%d1              | detents, signed
        move.l  28(%sp),%d0              | the raw value the knob is turned from
        tst.l   FUNC_HELD
        beq     po_kn_plain
        tst.l   FUNC_ENC_OFF
        bne     po_kn_plain
        cmpi.l  #KN_RATIO,%d2
        beq     po_kn_ratio
        lea     po_kn_jump(%pc),%a0
        mvz.b   (%a0,%d2.l),%d3          | the slot's jump: 12 . 16 10 16 16
        muls.l  %d3,%d1
        add.l   %d1,%d0
        bra     po_kn_out
po_kn_plain:
        move.l  %d2,%d3
        addi.l  #PUSH_CODE,%d3           | the push switch's key code ...
        move.l  %d3,%a0
        add.l   %d3,%d3
        add.l   %a0,%d3                  | * 3 ...
        lsl.l   #3,%d3                   | * 8 = code * 0x18: its key record
        lea     KEY_HELD,%a0
        tst.l   (%a0,%d3.l)
        beq     po_kn_one
        move.l  %d1,%d3                  | pressed: seven units a detent
        lsl.l   #3,%d1
        sub.l   %d3,%d1
po_kn_one:
        add.l   %d1,%d0
        bra     po_kn_out
| FUNC + RATO: walk classic snaps by their rounded raw. Must require a STRICTLY
| greater/less raw than the current one -- otherwise snap Q8 that round-trip
| below the target (e.g. 0.5 -> raw 8 -> Q8 0.48) leave the index stuck and
| every detent lands on the same value.
po_kn_ratio:
        move.l  %d1,%d3                  | detent count
        tst.l   %d3
        beq     po_kn_out                | d0 already the current raw
        moveq   #1,%d2                   | direction +1 / -1
        tst.l   %d3                      | (moveq left Z clear; re-test the count)
        bgt     po_kn_r_det
        neg.l   %d2
        neg.l   %d3
po_kn_r_det:
        lea     sy_rato_snap(%pc),%a0
        moveq   #0,%d1                   | snap index
        move.l  #0x100,%d4               | best candidate raw (none = 0x100)
        tst.l   %d2
        bgt     po_kn_r_up
        moveq   #-1,%d4                  | down: best = none
po_kn_r_up:
| scan snaps: map each to rounded raw; keep nearest strictly above/below d0
po_kn_r_scan:
        mvz.w   (%a0,%d1.l*2),%d5
        move.l  %d0,-(%sp)               | park current raw
        move.l  %d1,-(%sp)               | park snap index (sy_rato_raw clobbers d1)
        move.l  %d5,%d0
        bsr     sy_rato_raw              | d0 := rounded raw for this snap
        move.l  %d0,%d5
        move.l  (%sp)+,%d1
        move.l  (%sp)+,%d0
        tst.l   %d2
        bgt     po_kn_r_sup
        cmp.l   %d0,%d5                  | down: want raw < current
        bge     po_kn_r_next
        cmp.l   %d4,%d5
        ble     po_kn_r_next             | keep the greatest below
        move.l  %d5,%d4
        bra     po_kn_r_next
po_kn_r_sup:
        cmp.l   %d0,%d5                  | up: want raw > current
        ble     po_kn_r_next
        cmp.l   %d4,%d5
        bge     po_kn_r_next             | keep the least above
        move.l  %d5,%d4
po_kn_r_next:
        addq.l  #1,%d1
        cmpi.l  #KN_RATO_SNAPS,%d1
        bcs     po_kn_r_scan
        cmpi.l  #0x100,%d4               | none found (up sentinel)?
        beq     po_kn_r_none
        tst.l   %d4                      | down sentinel -1?
        bmi     po_kn_r_none
        move.l  %d4,%d0                  | take it
po_kn_r_none:
        subq.l  #1,%d3
        bne     po_kn_r_det
po_kn_out:
        movem.l (%sp),%d2-%d5
        lea     16(%sp),%sp
        rts
po_kn_jump:                              | FUNC's jump a detent, by slot: PTCH RATO INDX FOLD SYMM FDBK
        .byte   12, 0, 16, 16, 16, 16
        .align  4

| ==== FINGERED CHORDS: po_keyrec / po_keyrel (UI task; 26 Sep 2026, the second pass) ==
| po_keyrec is reached from the quantizer twice per recorded key, through the
| pointer published 12 bytes before sy_render, with d2 = track, d3 = the key's
| IDENTITY (a panel key's index + 1, 1..25; 0x80 | note for a MIDI note, from
| po_mrec), a2 = its raw pitch (64 = 0 semitones, snapped onto the SCALE by
| the quantizer): FIRST from qz_leg3 / po_mrec, at the live recorder's entry,
| with d0 = -1 -- the JOIN query: does this key join the chord being
| recorded? If so the chord's step gets its locks here and d0 := 1, and the
| quantizer skips the stock recorder for the key (no trig of its own); else
| d0 := 0 and the key is recorded as stock. THEN, for a key recorded as
| stock, from qz_leg5 / po_mrec (after the recorder wrote the key's trig and
| PTCH lock) with d0 = the step it was recorded on: a new record starts
| with that key. Runs only while the recorder is on (both detours sit
| inside its block: LIVE RECORDING, or a trig held) and only on a synth
| track whose Part VOIC is 2..4 and CHRD is "----" (the player chose no
| shape). po_keyrel, at every key release (the quantizer's qz_holdrel, a
| MIDI note-off), is the hand-over rule below.
| THE RULES (the second pass, after the 50-take investigation of 2.4):
|   * THE WINDOW: a record (po_chord, 32 B a track) starts at a key press and
|     keeps that key's step; a later press JOINS it while the record is
|     OPEN: less than KR_WIN frames (150 ms, whatever the tempo) since the
|     LAST key that joined -- a roll of five keys 100 ms apart is one chord
|     -- and at least one key of the record still held (a released first key
|     no longer closes it). The record is its keys still held, in order,
|     plus the new one, four at most; the recognition re-runs at every join
|     and the last result stands. A key pressed later starts a new record.
|   * THE HAND-OVER: a join is PROVISIONAL for KR_CONF frames (50 ms). When
|     another key of the record goes up inside that time, the new key was a
|     melody's next note taken with the finger still on the last -- legato,
|     not a chord: po_keyrel undoes the join (the earlier keys' locks again)
|     and gives the key the trig of its own it was denied, at its own time.
|     After KR_CONF frames both keys were held together: the join stands.
|   * THE MATCH (po_match): played intervals = each key's raw minus the
|     lowest, unreduced; for every inversion 0..3 in turn, every shape in
|     table order, the VOICING of (shape, inversion) for n = the keys held
|     (po_voicing: the shape's n highest-priority notes rotated so that the
|     inversion's note is the bass) -- the first whose intervals EQUAL the
|     played ones is the chord: E G B C is MA7 inv 1, E G C5 is MAJ inv 1, C
|     D is SU2, D F A C is MI7 (root positions first, so a root position
|     outranks another shape's inversion). No exact voicing: the second pass
|     takes the (shape, inversion) whose n notes are the played PITCH
|     CLASSES (mod 12) with the voicing span closest to the played span (C3
|     E4 G4 is MAS, the spread). Nothing: the root alone.
|   * THE LOCKS, written on the FIRST key's step with the stock writer
|     (LOCK_WRITE, as the quantizer writes HOLD): PTCH := the lowest key
|     (the played bass: the voicing's bass on playback); with a match CHRD
|     := shape << 2 | inversion and VOIC := min(keys, the Part's VOIC) --
|     the voices that were heard (the engine drops the newest key of a
|     chord press at the cap, po_st_cpress), so playback has the count the
|     take had; without one no CHRD/VOIC lock (a lock this record wrote
|     before is removed, 0xff). A joined key leaves no trig of its own and
|     no HOLD lock: the chord's length is the first key's.
| Live: unchanged (the engine plays the keys you hold); if the live voices
| differ from the shape's chosen notes (VOIC below the keys: the engine kept
| the oldest keys, the shape keeps its priorities) they are left as they
| are. Playback: PTCH + the voicing of (shape, inversion) with VOIC voices.
| po_keyrec clobbers d1, a0, a1 (C scratch); d0 := 1 when the key joined.

| ---- po_voicing: the voicing of (shape d0, inversion d1) for n = d3 voices ----
| The n semitone offsets above the bass, ascending, into (a1); d0 := the
| shape's distinct pitch classes m (1..4). The row's four notes (po_shapes,
| priority order) are sorted by pitch; a note whose pitch class a lower note
| already has is a DOUBLING (the octaves of 4TH, MAJ ..., three of them in
| OCT); the m distinct notes are rotated for the inversion (inv mod m: the
| bass is the inv-th distinct note, the ones below it go up by octaves until
| above it), then each doubling becomes an octave of a rotated note in
| ascending order (the k-th doubling = the (k mod m)-th note + 12 * (k div m
| + 1)), every note is taken relative to the bass, and the n notes of the
| highest PRIORITY (the row order, kept through the sorting) are the
| voicing, ascending. So MAJ (0 4 7 12) inv 1 at n = 3 is 0 3 8 (E G C5 from
| E), at n = 4 0 3 8 12 (E5 doubled); 4TH inv 1 is a 5TH; MA7 inv 2 is 0 4 5
| 9 (G B C E from G). Clobbers d0, d1, a0; everything else preserved.
po_voicing:
        lea     -48(%sp),%sp
        movem.l %d2-%d7/%a2-%a3,(%sp)
        lea     32(%sp),%a2              | scratch: NOTE[4] +0, PRIO[4] +4 (bit 7 = a doubling), DIDX[4] +8, OUT[4] +12
        lea     po_shapes(%pc),%a0
        lea     (%a0,%d0.l*4),%a0
        moveq   #0,%d2
pv_load:
        move.b  (%a0,%d2.l),%d4
        move.b  %d4,(%a2,%d2.l)
        move.b  %d2,4(%a2,%d2.l)
        addq.l  #1,%d2
        cmpi.l  #4,%d2
        bne     pv_load
        bsr     pv_sort
        moveq   #1,%d2                   | the doublings: a pitch class seen at a lower index
pv_d1:
        moveq   #0,%d5
pv_d2:
        mvs.b   (%a2,%d2.l),%d6
        bsr     pv_pc
        move.l  %d6,%d7
        mvs.b   (%a2,%d5.l),%d6
        bsr     pv_pc
        cmp.l   %d6,%d7
        bne     pv_d3
        lea     4(%a2,%d2.l),%a0
        move.b  (%a0),%d6
        bset    #7,%d6
        move.b  %d6,(%a0)
        bra     pv_d4
pv_d3:
        addq.l  #1,%d5
        cmp.l   %d2,%d5
        bne     pv_d2
pv_d4:
        addq.l  #1,%d2
        cmpi.l  #4,%d2
        bne     pv_d1
        bsr     pv_didx                  | d4 := m, DIDX := the distinct entries' indices
        move.l  %d1,%d5                  | the inversion, mod m
pv_i1:
        cmp.l   %d4,%d5
        bcs     pv_i2
        sub.l   %d4,%d5
        bra     pv_i1
pv_i2:
        mvz.b   8(%a2,%d5.l),%d6
        mvs.b   (%a2,%d6.l),%d7          | the bass note
        moveq   #0,%d2                   | the distinct notes below it go up ...
pv_r1:
        cmp.l   %d5,%d2
        bcc     pv_r3
        mvz.b   8(%a2,%d2.l),%d6
        lea     (%a2,%d6.l),%a0
        mvs.b   (%a0),%d6
pv_r2:
        addi.l  #12,%d6                  | ... by octaves until above the bass
        cmp.l   %d7,%d6
        ble     pv_r2
        move.b  %d6,(%a0)
        addq.l  #1,%d2
        bra     pv_r1
pv_r3:
        bsr     pv_sort                  | the rotated notes in order (the marks ride along; d6/d7 used)
        bsr     pv_didx
        mvz.b   8(%a2),%d6
        mvs.b   (%a2,%d6.l),%d7          | the bass again: the lowest distinct note now
        moveq   #0,%d5                   | the doublings, in order: octaves of the rotated notes
        moveq   #0,%d2
pv_b1:
        tst.b   4(%a2,%d2.l)
        bpl     pv_b3
        move.l  %d5,%d6                  | k
        moveq   #12,%d0                  | 12 * (k div m + 1)
pv_b2:
        cmp.l   %d4,%d6
        bcs     pv_b2a
        sub.l   %d4,%d6
        addi.l  #12,%d0
        bra     pv_b2
pv_b2a:
        mvz.b   8(%a2,%d6.l),%d6
        mvs.b   (%a2,%d6.l),%d6
        add.l   %d0,%d6
        move.b  %d6,(%a2,%d2.l)
        addq.l  #1,%d5
pv_b3:
        addq.l  #1,%d2
        cmpi.l  #4,%d2
        bne     pv_b1
        moveq   #0,%d0                   | the n notes of the highest priority, relative to the bass
        moveq   #0,%d5
pv_o1:
        moveq   #0,%d2
pv_o2:
        mvz.b   4(%a2,%d2.l),%d6
        andi.l  #3,%d6
        cmp.l   %d0,%d6
        beq     pv_o3
        addq.l  #1,%d2
        cmpi.l  #4,%d2
        bne     pv_o2
        bra     pv_o4
pv_o3:
        mvs.b   (%a2,%d2.l),%d6
        sub.l   %d7,%d6
        move.b  %d6,12(%a2,%d5.l)
        addq.l  #1,%d5
pv_o4:
        addq.l  #1,%d0
        cmp.l   %d3,%d5
        bcs     pv_o1
        move.l  %d3,%d1                  | sorted ascending
        subq.l  #1,%d1
        ble     pv_copy
pv_p1:
        moveq   #0,%d2
pv_p2:
        mvs.b   12(%a2,%d2.l),%d6
        mvs.b   13(%a2,%d2.l),%d0
        cmp.l   %d6,%d0
        bge     pv_p3
        move.b  %d0,12(%a2,%d2.l)
        move.b  %d6,13(%a2,%d2.l)
pv_p3:
        addq.l  #1,%d2
        cmp.l   %d1,%d2
        bne     pv_p2
        subq.l  #1,%d1
        bne     pv_p1
pv_copy:
        moveq   #0,%d2
pv_c1:
        move.b  12(%a2,%d2.l),%d6
        move.b  %d6,(%a1,%d2.l)
        addq.l  #1,%d2
        cmp.l   %d3,%d2
        bne     pv_c1
        move.l  %d4,%d0
        movem.l (%sp),%d2-%d7/%a2-%a3
        lea     48(%sp),%sp
        rts
pv_sort:                                 | NOTE[0..3] ascending, PRIO with them (three passes)
        moveq   #3,%d4
pv_s1:
        moveq   #0,%d5
pv_s2:
        mvs.b   (%a2,%d5.l),%d6
        mvs.b   1(%a2,%d5.l),%d7
        cmp.l   %d6,%d7
        bge     pv_s3
        move.b  %d7,(%a2,%d5.l)
        move.b  %d6,1(%a2,%d5.l)
        move.b  4(%a2,%d5.l),%d6
        move.b  5(%a2,%d5.l),%d7
        move.b  %d7,4(%a2,%d5.l)
        move.b  %d6,5(%a2,%d5.l)
pv_s3:
        addq.l  #1,%d5
        cmpi.l  #3,%d5
        bne     pv_s2
        subq.l  #1,%d4
        bne     pv_s1
        rts
pv_didx:                                 | d4 := the distinct count m, DIDX[0..m-1] := their indices
        moveq   #0,%d4
        moveq   #0,%d2
pv_x1:
        tst.b   4(%a2,%d2.l)
        bmi     pv_x2
        move.b  %d2,8(%a2,%d4.l)
        addq.l  #1,%d4
pv_x2:
        addq.l  #1,%d2
        cmpi.l  #4,%d2
        bne     pv_x1
        rts
pv_pc:                                   | d6 := d6 mod 12 (d6 >= 0)
        cmpi.l  #12,%d6
        bcs     pv_pc1
        subi.l  #12,%d6
        bra     pv_pc
pv_pc1:
        rts

| ---- po_match: the chord of the record a3's keys -> d0 = the shape (1..31, 0 =
| none), d1 = its inversion (the rules above). Clobbers d0, d1 only.
po_match:
        lea     -56(%sp),%sp
        movem.l %d2-%d7/%a2-%a4,(%sp)    | scratch: PLAYED[4] at 36, V[4] at 40, BEST at 44 (shape << 8 | inv), its distance at 48
        lea     36(%sp),%a2
        mvz.b   CR_N(%a3),%d3            | n
        lea     CR_RAWS(%a3),%a0
        moveq   #0,%d2
pm_l1:
        move.b  (%a0,%d2.l),%d0
        move.b  %d0,(%a2,%d2.l)
        addq.l  #1,%d2
        cmp.l   %d3,%d2
        bne     pm_l1
        move.l  %d3,%d1                  | the raws ascending
        subq.l  #1,%d1
        ble     pm_base
pm_p1:
        moveq   #0,%d2
pm_p2:
        mvz.b   (%a2,%d2.l),%d6
        mvz.b   1(%a2,%d2.l),%d0
        cmp.l   %d6,%d0
        bcc     pm_p3
        move.b  %d0,(%a2,%d2.l)
        move.b  %d6,1(%a2,%d2.l)
pm_p3:
        addq.l  #1,%d2
        cmp.l   %d1,%d2
        bne     pm_p2
        subq.l  #1,%d1
        bne     pm_p1
pm_base:
        mvz.b  (%a2),%d6                 | the lowest: the played bass
        moveq   #0,%d2
        moveq   #0,%d4                   | the played pitch-class set
pm_i1:
        mvz.b   (%a2,%d2.l),%d0
        sub.l   %d6,%d0
        move.b  %d0,(%a2,%d2.l)          | the interval above the bass
        bsr     pm_pc12
        bset    %d0,%d4
        addq.l  #1,%d2
        cmp.l   %d3,%d2
        bne     pm_i1
        mvz.b   -1(%a2,%d2.l),%d5        | the played span: the highest interval
        moveq   #9,%d0
        movea.l %d0,%a4                  | BEST's distinct count, 9 = none yet (2.8: among the equal voicings of a
                                         | pass the shape with the FEWEST distinct notes wins, table order among
                                         | equals -- C F is 4TH before SU4's root and 4th, C F# DIM before DI7's,
                                         | now that the intervals sit at the end of the table)
        moveq   #0,%d7                   | FIRST: an exact voicing -- the root position of every shape ...
        moveq   #1,%d6
pm_e1:
        bsr     pm_try                   | d0 = m when (shape d6, inversion d7) equals the played intervals, else 0
        bsr     pm_keep
        addq.l  #1,%d6
        cmpi.l  #32,%d6
        bne     pm_e1
        cmpa.l  #9,%a4
        bne     pm_found
        moveq   #1,%d6                   | ... then the inversions, shape by shape in table order (the same rule)
pm_e2:
        moveq   #1,%d7
pm_e3:
        bsr     pm_try
        bsr     pm_keep
        addq.l  #1,%d7
        cmpi.l  #4,%d7
        bne     pm_e3
        addq.l  #1,%d6
        cmpi.l  #32,%d6
        bne     pm_e2
        cmpa.l  #9,%a4
        beq     pm_second
pm_found:
        move.l  44(%sp),%d0              | the chord: BEST = shape << 8 | inversion
        move.l  %d0,%d1
        andi.l  #0xff,%d1
        lsr.l   #8,%d0
        bra     pm_out
pm_keep:                                 | d0 = m of an equal voicing (0: not equal): BEST := (d6, d7) when m is below BEST's
        tst.l   %d0
        beq     pm_k_out
        cmp.l   %a4,%d0
        bcc     pm_k_out
        movea.l %d0,%a4
        move.l  %d6,%d0
        lsl.l   #8,%d0
        or.l    %d7,%d0
        move.l  %d0,48(%sp)              | (44(sp) of po_match's frame, under this call's return address)
pm_k_out:
        rts
pm_try:                                  | d0 := m when the voicing of (d6, d7) for n keys equals PLAYED, 0 when not (a lower inversion again: never)
        move.l  %d6,%d0
        move.l  %d7,%d1
        lea     4(%a2),%a1
        bsr     po_voicing               | V := the voicing; d0 = m
        cmp.l   %d0,%d7
        bcc     pm_no                    | inv >= m: a lower inversion again
        move.l  %d0,%d1                  | m
        moveq   #0,%d2
pm_t1:
        move.b  (%a2,%d2.l),%d0
        cmp.b   4(%a2,%d2.l),%d0
        bne     pm_no
        addq.l  #1,%d2
        cmp.l   %d3,%d2
        bne     pm_t1
        move.l  %d1,%d0                  | equal: m
        rts
pm_no:
        moveq   #0,%d0                   | not equal
        rts
pm_second:
        clr.l   44(%sp)                  | SECOND: the pitch classes, the closest span (then the fewest distinct notes, then table order)
        move.l  #0x7fffffff,%d0
        move.l  %d0,48(%sp)
        moveq   #1,%d6
pm_c1:
        moveq   #0,%d7
pm_c2:
        move.l  %d6,%d0
        move.l  %d7,%d1
        lea     4(%a2),%a1
        bsr     po_voicing
        cmp.l   %d0,%d7
        bcc     pm_c4                    | inv >= m: the next shape
        movea.l %d0,%a4                  | m
        moveq   #0,%d2                   | the voicing's pitch-class set
        moveq   #0,%d1
pm_c2a:
        mvz.b   4(%a2,%d2.l),%d0
        bsr     pm_pc12
        bset    %d0,%d1
        addq.l  #1,%d2
        cmp.l   %d3,%d2
        bne     pm_c2a
        cmp.l   %d4,%d1
        bne     pm_c3
        mvz.b   3(%a2,%d3.l),%d0         | its span: V[n - 1]
        sub.l   %d5,%d0
        bpl     pm_c2b
        neg.l   %d0
pm_c2b:
        lsl.l   #3,%d0                   | the key: span distance << 3 | m
        add.l   %a4,%d0
        cmp.l   48(%sp),%d0
        bcc     pm_c3                    | not closer than the best so far (nor fewer distinct notes at the same distance)
        move.l  %d0,48(%sp)
        move.l  %d6,%d0
        lsl.l   #8,%d0
        or.l    %d7,%d0
        move.l  %d0,44(%sp)
pm_c3:
        addq.l  #1,%d7
        cmpi.l  #4,%d7
        bne     pm_c2
pm_c4:
        addq.l  #1,%d6
        cmpi.l  #32,%d6
        bne     pm_c1
        move.l  44(%sp),%d0
        move.l  %d0,%d1
        andi.l  #0xff,%d1
        lsr.l   #8,%d0                   | the shape, 0 = none
pm_out:
        movem.l (%sp),%d2-%d7/%a2-%a4
        lea     56(%sp),%sp
        rts
pm_pc12:                                 | d0 := d0 mod 12 (d0 >= 0)
        cmpi.l  #12,%d0
        bcs     pm_pc1
        subi.l  #12,%d0
        bra     pm_pc12
pm_pc1:
        rts

| ---- po_keyrec (see the rules above) ------------------------------------------
po_keyrec:
        lea     -44(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        move.l  %d0,%d5                  | the step, or -1: the join query
        move.l  %a2,%d6                  | the raw
        move.l  %d3,%d4                  | the identity (index + 1, or 0x80 | note)
        movea.l PART_PTR,%a0             | the Part's LFO page bytes: VOIC 2..4 and CHRD "----" only
        mvz.b   PART_IDX,%d0
        move.l  #6322,%d1
        muls.l  %d1,%d0
        adda.l  %d0,%a0
        adda.l  #LFO_PAGE_OFF,%a0
        move.l  %d2,%d0
        lsl.l   #3,%d0
        move.l  %d0,%d1
        add.l   %d1,%d0
        add.l   %d1,%d0                  | track * 24
        mvz.b   2(%a0,%d0.l),%d1         | VOIC
        subq.l  #2,%d1
        cmpi.l  #2,%d1
        bhi     po_kr_out                | 1 (or out of range): the mono synth, stock recording
        addq.l  #2,%d1
        mvz.b   5(%a0,%d0.l),%d0         | CHRD
        lsr.l   #2,%d0
        bne     po_kr_out                | a shape: the player's choice stands
        lea     po_chord(%pc),%a3
        move.l  %d2,%d0
        lsl.l   #5,%d0
        adda.l  %d0,%a3                  | a3 = the track's chord record
        move.b  %d1,CR_VOIC(%a3)         | the Part's VOIC: the VOIC lock's ceiling
        lea     po_clock(%pc),%a4
        move.l  CK_FRAMES(%a4),%d7       | now
        bsr     po_kr_settle             | a provisional join older than KR_CONF stands
        tst.l   %d5
        bpl     po_kr_new                | after the recorder: a new record on the step it chose
        mvz.b   CR_N(%a3),%d0
        beq     po_kr_out                | the query: no record open
        move.l  %d7,%d1
        sub.l   CR_FRAME(%a3),%d1
        cmpi.l  #KR_WIN,%d1
        bhi     po_kr_out                | later than the window after the record's last key: not this record
        lea     CR_KEYS(%a3),%a0         | one of its keys still held?
        move.l  %d0,%d1
po_kr_any:
        mvz.b   (%a0)+,%d0
        bsr     po_held
        bne     po_kr_join
        subq.l  #1,%d1
        bne     po_kr_any
        bra     po_kr_out                | every key of it is up: not this record
po_kr_join:
        mvz.b   CR_N(%a3),%d0
        move.l  %d0,-(%sp)               | the keys still held, in order, then the new one
        lea     CR_KEYS(%a3),%a0
        lea     CR_KEYS(%a3),%a1
        lea     CR_RAWS(%a3),%a5
        lea     CR_RAWS(%a3),%a6
        moveq   #0,%d1                   | kept
po_kr_cp:
        mvz.b   (%a0)+,%d0
        cmp.l   %d4,%d0
        beq     po_kr_cp1                | the new key again: appended below
        bsr     po_held
        beq     po_kr_cp1                | released since
        move.b  %d0,(%a1)+
        move.b  (%a5),(%a6)+
        addq.l  #1,%d1
po_kr_cp1:
        addq.l  #1,%a5
        subq.l  #1,(%sp)
        bne     po_kr_cp
        addq.l  #4,%sp
        clr.b   CR_PKEY(%a3)
        cmpi.l  #4,%d1
        bcc     po_kr_full               | four already: a fifth key does not count (and is not provisional)
        move.b  %d4,(%a1)
        move.b  %d6,(%a6)
        addq.l  #1,%d1
        move.b  %d4,CR_PKEY(%a3)         | its join is provisional for KR_CONF frames (po_keyrel: the hand-over rule)
        move.l  %d7,CR_PFRAME(%a3)
        move.l  REC_CTX,%d0
        move.l  %d0,CR_PCTX(%a3)
        move.l  CK_TICKS(%a4),%d0
        move.l  %d0,CR_PTICKS(%a3)
        move.b  %d6,CR_PRAW(%a3)
po_kr_full:
        move.b  %d1,CR_N(%a3)
        move.l  %d7,CR_FRAME(%a3)        | the window rolls from this key
        bsr     po_kr_write              | the recognition, and the step's locks
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     44(%sp),%sp
        moveq   #1,%d0                   | joined: the quantizer records no trig for the key
        rts
po_kr_new:                               | a new record: this key, its step, now
        move.b  %d5,CR_STEP(%a3)
        move.l  %d7,CR_FRAME(%a3)
        move.b  %d4,CR_KEYS(%a3)
        move.b  %d6,CR_RAWS(%a3)
        move.b  #1,CR_N(%a3)
        clr.b   CR_WROTE(%a3)
        clr.b   CR_PKEY(%a3)
po_kr_out:
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     44(%sp),%sp
        moveq   #0,%d0                   | not joined
        rts

| ---- po_kr_settle: a provisional join older than KR_CONF frames stands (d7 = now) --
po_kr_settle:
        tst.b   CR_PKEY(%a3)
        beq     po_ks_out
        move.l  %d7,%d0
        sub.l   CR_PFRAME(%a3),%d0
        cmpi.l  #KR_CONF,%d0
        bcs     po_ks_out
        clr.b   CR_PKEY(%a3)
po_ks_out:
        rts

| ---- po_kr_write: the record's step gets its locks from the keys in it -------
| n >= 2: the root (the lowest raw) as PTCH; a match (po_match) -> CHRD :=
| shape << 2 | inversion, VOIC := min(n, the Part's VOIC), CR_WROTE; no match
| -> the root alone, a CHRD/VOIC lock this record wrote removed (0xff). n =
| 1: that key's raw as PTCH (the record's own note again), the locks
| removed. Clobbers d0, d1, d3, d4, a0, a1.
po_kr_write:
        mvz.b   CR_N(%a3),%d3
        lea     CR_RAWS(%a3),%a0
        moveq   #127,%d4                 | the root: the lowest raw
        move.l  %d3,%d0
po_kw_root:
        mvz.b   (%a0)+,%d1
        cmp.l   %d4,%d1
        bcc     po_kw_root1
        move.l  %d1,%d4
po_kw_root1:
        subq.l  #1,%d0
        bne     po_kw_root
        move.l  %d4,%d0
        moveq   #CV_PTCH,%d1
        bsr     po_lockw
        cmpi.l  #2,%d3
        bcs     po_kw_remove
        bsr     po_match                 | d0 = the shape (0 = none), d1 = the inversion
        tst.l   %d0
        beq     po_kw_remove
        lsl.l   #2,%d0
        or.l    %d1,%d0
        moveq   #CV_CHRD,%d1
        bsr     po_lockw
        mvz.b   CR_VOIC(%a3),%d0
        cmp.l   %d3,%d0
        bls     po_kw_voic
        move.l  %d3,%d0                  | VOIC := min(keys, the Part's VOIC): the count that was heard
po_kw_voic:
        moveq   #CV_VOIC,%d1
        bsr     po_lockw
        move.b  #1,CR_WROTE(%a3)
        rts
po_kw_remove:
        tst.b   CR_WROTE(%a3)
        beq     po_kw_out
        move.l  #0xff,%d0
        moveq   #CV_CHRD,%d1
        bsr     po_lockw
        move.l  #0xff,%d0
        moveq   #CV_VOIC,%d1
        bsr     po_lockw
        clr.b   CR_WROTE(%a3)
po_kw_out:
        rts

| ---- po_keyrel: a key released (UI task) -- the hand-over rule ------------------
| Reached through the pointer published 20 bytes before sy_render from the
| quantizer's qz_holdrel (every CHROMATIC key release on a synth track: d2 =
| track, d0 = the key index, a0 = the track's four HOLD slots -- key, step,
| in use, pad, ticks) and from po_moff (a MIDI note-off: d0 = 0x80 | note,
| a0 = 0). Preserves every register. When the record's provisional key is
| younger than KR_CONF frames and ANOTHER key of the record goes up, the
| provisional key was a HAND-OVER: it leaves the record, the record's step
| gets its locks from the keys before it (po_kr_write: PTCH the earlier note
| again, a CHRD/VOIC lock removed or the smaller chord), and the key gets
| the trig of its own it was denied, at its own time (REC_TRIG with the
| recorder's context word saved at its press), its PTCH lock, and -- a panel
| key -- a HOLD slot in the quantizer's table (its press ticks), so its
| release writes its length as for any key; the next record is that key
| alone on that step. The provisional key's own release, or a release after
| KR_CONF: the join stands.
po_keyrel:
        lea     -52(%sp),%sp
        movem.l %d0-%d7/%a0-%a4,(%sp)
        move.l  %d0,%d4
        cmpi.l  #0x80,%d4
        bcc     po_rl_id
        addq.l  #1,%d4                   | a panel key's identity
po_rl_id:
        lea     po_chord(%pc),%a3
        move.l  %d2,%d0
        lsl.l   #5,%d0
        adda.l  %d0,%a3
        mvz.b   CR_PKEY(%a3),%d5
        beq     po_rl_out                | nothing provisional
        lea     po_clock(%pc),%a4
        move.l  CK_FRAMES(%a4),%d7
        bsr     po_kr_settle             | old enough: it stands
        tst.b   CR_PKEY(%a3)
        beq     po_rl_out
        cmp.l   %d4,%d5
        beq     po_rl_out                | the provisional key itself went: the join stands (a tapped note of the chord)
        mvz.b   CR_N(%a3),%d0            | another key of the record?
        subq.l  #1,%d0                   | (the last entry is the provisional key)
        beq     po_rl_out
        lea     CR_KEYS(%a3),%a0
po_rl_k:
        cmp.b   (%a0)+,%d4
        beq     po_rl_hand
        subq.l  #1,%d0
        bne     po_rl_k
        bra     po_rl_out                | not of this record
po_rl_hand:                              | a HAND-OVER: the join is undone
        mvz.b   CR_N(%a3),%d0
        subq.l  #1,%d0
        move.b  %d0,CR_N(%a3)
        clr.b   CR_PKEY(%a3)
        bsr     po_kr_write              | the step's locks from the keys before it
        lea     -8(%sp),%sp              | the key's own trig, at its own time: REC_TRIG(track, ctx)
        move.l  %d2,(%sp)
        move.l  CR_PCTX(%a3),%d0
        move.l  %d0,4(%sp)
        jsr     REC_TRIG
        lea     8(%sp),%sp
        tst.l   %d0
        bmi     po_rl_out                | no step: the key is lost (the recorder refused)
        move.l  %d0,%d6                  | the step
        bsr     po_rl_nudge              | (its timing nudge cleared: a stale context misleads the recorder's next-step arithmetic)
        move.b  %d6,CR_STEP(%a3)         | the next record: this key alone, on it
        move.b  %d5,CR_KEYS(%a3)
        move.b  CR_PRAW(%a3),%d0
        move.b  %d0,CR_RAWS(%a3)
        move.b  #1,CR_N(%a3)
        clr.b   CR_WROTE(%a3)
        move.l  CR_PFRAME(%a3),%d0
        move.l  %d0,CR_FRAME(%a3)
        mvz.b   CR_PRAW(%a3),%d0         | its PTCH lock
        moveq   #CV_PTCH,%d1
        bsr     po_lockw
        cmpi.l  #0x80,%d5
        bcc     po_rl_out                | a MIDI note: no HOLD (as any MIDI note)
        move.l  32(%sp),%a0              | the quantizer's four HOLD slots of the track (0: none)
        move.l  %a0,%d0
        beq     po_rl_out
        moveq   #3,%d1                   | a free slot, else slot 0
po_rl_s1:
        tst.b   2(%a0)
        beq     po_rl_s2
        addq.l  #8,%a0
        subq.l  #1,%d1
        bpl     po_rl_s1
        move.l  32(%sp),%a0
po_rl_s2:
        move.l  %d5,%d0
        subq.l  #1,%d0
        move.b  %d0,(%a0)                | the key
        move.b  %d6,1(%a0)               | its step
        move.b  #1,2(%a0)                | in use
        move.l  CR_PTICKS(%a3),%d0
        move.l  %d0,4(%a0)               | the ticks at its press
po_rl_out:
        movem.l (%sp),%d0-%d7/%a0-%a4
        lea     52(%sp),%sp
        rts
| ---- po_rl_nudge: the timing field of track d2's step d6 in the current pattern := 0 --
| REC_TRIG called KR_CONF frames after the press computes, from the stale
| context, a trig on the right step but with a NUDGE (bits 7..12 of the
| step's word, 1/48 steps: 20 measured for a 50 ms old press) that the
| sequencer honours -- the note then fired a step early at playback. The
| immediate call of the stock recorder leaves the field 0; so does this, in
| the RAM record and the current bank's battery-RAM mirror, the two places
| REC_TRIG writes. Clobbers d0, d1, d3, a0.
po_rl_nudge:
        move.l  %d2,%d0
        move.l  #1165,%d1
        muls.l  %d1,%d0                  | track * 1165 ...
        mvz.b   PAT_CUR,%d1
        move.l  #18284,%d3
        muls.l  %d3,%d1
        add.l   %d1,%d0                  | ... + pattern * 18284 ...
        add.l   %d6,%d0
        addi.l  #PAT_NUDGE,%d0           | ... + the step + 1101: the word's index
        move.l  %d0,%d3
        add.l   %d3,%d3                  | * 2
        lea     PAT_MIR,%a0
        adda.l  %d3,%a0
        move.w  (%a0),%d1
        andi.l  #0xffffe07f,%d1
        move.w  %d1,(%a0)                | the mirror
        mvz.b   BANK_CUR,%d1
        move.l  #317856,%d3
        muls.l  %d3,%d1
        add.l   %d1,%d0                  | + bank * 317856
        add.l   %d0,%d0
        lea     PAT_RAM,%a0
        adda.l  %d0,%a0
        move.w  (%a0),%d1
        andi.l  #0xffffe07f,%d1
        move.w  %d1,(%a0)                | the record
        rts

| ---- po_lockw: the stock writer -- track d2, flat slot d1, value d0, on the record a3's
| step, with the recorder's context, exactly as the quantizer writes HOLD (it refuses
| once the recorder is off). Clobbers d0, d1, a0, a1.
po_lockw:
        lea     -20(%sp),%sp
        move.l  %d2,(%sp)
        move.l  %d1,4(%sp)
        move.l  %d0,8(%sp)
        mvz.b   CR_STEP(%a3),%d0
        move.l  %d0,12(%sp)
        move.l  REC_CTX,%d0
        move.l  %d0,16(%sp)
        jsr     LOCK_WRITE
        lea     20(%sp),%sp
        rts

| ==== MIDI IN (30 Sep 2026): MIDI notes into a synth track behave like the panel keys ==
| The STANDARD note map's chromatic block (0x4000e6e2, reached for notes 72..96
| by the octave switch at 0x4000e452 of the audio-track note-on 0x4000e018)
| posts, for every track listening on the message's channel, the voice
| command 0x1d into the mailbox 0x46c80354[t] and the PTCH lock byte the
| frame builder applies at the START -- no identity, one held note a track
| (0x400d64c2[t]), and the note-off 0x4000db98 releases only when that byte
| is the note. Five detours (modules/synth/manifest.py), all landing here:
|   * po_mon at the block's voice command 0x4000e746: a synth track's raw
|     is SEMITONES, raw = note - 20 (84 = C6 = 0; 20..127 = -64..+43; 0..19
|     clamp to -64; a sample track keeps the stock 64 + 5 * (note - 84)),
|     stored as the PTCH lock byte FIRST (stock posts the START and stores
|     the byte after it: a frame between the two starts the voice on the
|     previous note's lock -- seen once in the emulator, with the START
|     before the engine knew the note), the note joins the track's
|     HELD-NOTE LIST (po_mheld, 8 notes in press order), its (identity,
|     raw) is queued in the track's RING (po_mring), its identity 0x80 |
|     note is posted as the track's live key (qz_pkey[t], KEYS_AT), and the
|     START goes last: the engine's START allocates one voice per queued note-on
|     (po_start: two note-ons inside one frame share one stock START), each
|     at its own pitch, with V_KEY = the identity, so po_start1's rules apply
|     as for a key -- "----": one voice a note, VOIC the polyphony (the
|     oldest is stolen), a repeated note-on for a sounding note absorbed; a
|     shape: chord memory (the new note's chord replaces the old one);
|   * po_moff at the note-off's compare 0x4000dfd4 (reached for a note
|     outside 72..96 through po_mogate at the note-off's own octave switch
|     0x4000de10, po_mgate's twin): the note leaves the
|     list; on a paraphonic synth track (Part VOIC 2..4, the keys' rule) only
|     the LAST note's release takes the stock block (mailbox |= 0x40: the
|     AMP release, as the last key's release does), an earlier one's does
|     nothing there -- the engine releases that note's voice (po_frame's
|     scan, and po_st_live for a note-off that beat its START); VOIC 1 (the
|     mono voice, the stock lifecycle) and every sample track: stock;
|   * po_mgate at the octave switch 0x4000e452: a note outside 72..96 whose
|     channel addresses a synth track goes to the chromatic block for the
|     channel's SYNTH tracks alone (the auto channel: the active track when
|     it is a synth); the STANDARD functions of notes 24..71 do not run for
|     such a message (a synth track's channel is a keyboard); a channel
|     without a synth track, and 72..96 on any channel: stock;
|   * po_mrec at the 0x41 event's live recorder 0x400625e0 (stock: the
|     active track only, while LIVE RECORDING): on a synth track the note
|     is handed to po_keyrec as a key of its own (identity 0x80 | note, raw
|     = note - 20) -- a JOINING note records no trig (the chord's step gets
|     PTCH / CHRD / VOIC), else the stock recorder places the trig and the
|     PTCH lock is the raw (stock wrote 5 * note - 356 there, a sample
|     track's units) and a new chord record starts; po_mtrig at the
|     trig-held branch 0x4006262a: the held trig's PTCH lock is the raw too.
| Velocity is ignored (stock keeps none for audio tracks). MIDI note OUT and
| the panel keys are untouched; a MIDI note gets no HOLD (note length) lock.
| FOLLOW TM with the CHROMATIC trig mode is a different path (0x400500e8 ->
| the key handler 0x4004fb94 with key = note - 72: the quantizer's 25-key
| paraphony, 72..96) and is not changed.
| ---- po_is_synth: d2 = track -> d0 = 1 when CX OSC is chosen in the machine list.
po_is_synth:
        bsr     po_signed
        rts

| ---- po_sig: a0 = Part, d0 = track -> d0 = 1 when FLEX with "CX",1.
po_sig:
        lea     -8(%sp),%sp
        movem.l %d1/%a1,(%sp)
        movea.l %a0,%a1
        adda.l  #MACH_OFF,%a1
        mvz.b   (%a1,%d0.l),%d1
        subq.l  #1,%d1
        bne     po_sig_no
        mulu.w  #30,%d0
        movea.l %a0,%a1
        adda.l  %d0,%a1
        adda.l  #SIG_OFF,%a1
        mvz.w   (%a1),%d1
        cmpi.l  #0x4358,%d1              | "CX"
        bne     po_sig_no
        mvz.b   2(%a1),%d1
        subq.l  #1,%d1
        bne     po_sig_no
        moveq   #1,%d0
        bra     po_sig_out
po_sig_no:
        moveq   #0,%d0
po_sig_out:
        movem.l (%sp),%d1/%a1
        lea     8(%sp),%sp
        tst.l   %d0
        rts

| ---- po_signed: d2 = track -> d0 = 1 when CX OSC chosen.
po_signed:
        lea     -8(%sp),%sp
        movem.l %d1/%a0,(%sp)
        movea.l PART_PTR,%a0
        mvz.b   PART_IDX,%d0
        move.l  #6322,%d1
        muls.l  %d1,%d0
        adda.l  %d0,%a0
        move.l  %d2,%d0
        bsr     po_sig
        movem.l (%sp),%d1/%a0
        lea     8(%sp),%sp
        tst.l   %d0
        rts

| ---- po_fmsource: frame builder supplier -- signed tracks get sy_render.
po_fmsource:
        movea.l (%a4)+,%a0
        lea     -8(%sp),%sp
        movem.l %d0/%d2,(%sp)
        move.l  %d3,%d2
        bsr     po_signed
        beq     po_fs_keep
        lea     sy_render,%a0
po_fs_keep:
        movem.l (%sp),%d0/%d2
        lea     8(%sp),%sp
        move.l  %a0,(%a3)+
        pea     16.w
        jmp     FMSRC_RET

| ---- po_fmstart: FLEX START without a sample when signed.
po_fmstart:
        lea     -8(%sp),%sp
        movem.l %d2/%a0,(%sp)
        move.l  12(%sp),%d2
        bsr     po_signed
        beq     po_fst_stock
        move.l  #VOICE_STRIDE,%d0
        muls.l  %d2,%d0
        lea     VOICE_BASE,%a0
        add.l   %d0,%a0
        move.l  #0x100,%d0
        tst.b   (%a0)
        beq     po_fst_cold
        moveq   #0,%d0
po_fst_cold:
        move.b  #0xff,(%a0)
        move.b  #1,20(%a0)
        movem.l (%sp),%d2/%a0
        lea     8(%sp),%sp
        rts
po_fst_stock:
        movem.l (%sp),%d2/%a0
        lea     8(%sp),%sp
        jmp     FLEX_START

| ---- po_slot_marker: always 0 (marker path off, as FM 2.15).
po_slot_marker:
        moveq   #0,%d0
        rts

| ---- po_polytrack: always 0 -- CX OSC is mono (LFO 3 is a normal LFO).
po_polytrack:
        moveq   #0,%d0
        rts

| ---- the held-note list: 8 bytes a track, identities 0x80 | note in press order,
| packed at the front, 0 = empty.
| po_mheld_of: a1 := track d2's list; Z = it is empty. Clobbers d0, a1.
po_mheld_of:
        lea     po_mheld(%pc),%a1
        move.l  %d2,%d0
        lsl.l   #3,%d0
        adda.l  %d0,%a1
        tst.b   (%a1)
        rts

| po_held: d0 = an identity (1..25 a panel key's index + 1: its bit in qz_pmask[t];
| 0x80 | note a MIDI note: the list), d2 = track -> Z clear when it is held.
| Preserves every register (the flags are the result).
po_held:
        lea     -12(%sp),%sp
        movem.l %d0/%d1/%a1,(%sp)
        cmpi.l  #0x80,%d0
        bcc     po_hd_midi
        subq.l  #1,%d0
        lea     KEYS_AT+8,%a1
        move.l  (%a1,%d2.l*4),%d1
        btst    %d0,%d1                  | the key's bit (0..24)
        bra     po_hd_out
po_hd_midi:
        bsr     po_mheld_of
        move.l  (%sp),%d0
        moveq   #8,%d1
po_hd_scan:
        cmp.b   (%a1)+,%d0
        beq     po_hd_yes
        subq.l  #1,%d1
        bne     po_hd_scan
        moveq   #0,%d1                   | not held: Z
        bra     po_hd_out
po_hd_yes:
        moveq   #1,%d1                   | held: NZ
po_hd_out:
        movem.l (%sp),%d0/%d1/%a1        | (movem and lea leave the flags)
        lea     12(%sp),%sp
        rts

| po_mheld_add: d1 = the identity -> appended to track d2's list unless it is there;
| a full list drops its oldest note (the engine releases that note's voice at
| the next frame, as a stolen key). Preserves every register.
po_mheld_add:
        lea     -16(%sp),%sp
        movem.l %d0/%d3/%a0/%a1,(%sp)
        bsr     po_mheld_of
        movea.l %a1,%a0
        moveq   #8,%d3
po_ma_scan:
        mvz.b   (%a0),%d0
        cmp.l   %d1,%d0
        beq     po_ma_out                | held already
        tst.l   %d0
        beq     po_ma_put                | the end of the list
        addq.l  #1,%a0
        subq.l  #1,%d3
        bne     po_ma_scan
        movea.l %a1,%a0                  | full: the oldest goes, the rest move down
        moveq   #7,%d3
po_ma_shift:
        move.b  1(%a0),(%a0)+
        subq.l  #1,%d3
        bne     po_ma_shift              | a0 = the last slot
po_ma_put:
        move.b  %d1,(%a0)
po_ma_out:
        movem.l (%sp),%d0/%d3/%a0/%a1
        lea     16(%sp),%sp
        rts

| po_mheld_del: d1 = the identity -> removed from track d2's list; d0 := the notes
| left in it, or -1 when it was not there. Preserves every other register.
po_mheld_del:
        lea     -12(%sp),%sp
        movem.l %d3/%a0/%a1,(%sp)
        bsr     po_mheld_of
        movea.l %a1,%a0
        moveq   #8,%d3
po_md_scan:
        mvz.b   (%a0),%d0
        cmp.l   %d1,%d0
        beq     po_md_found
        tst.l   %d0
        beq     po_md_none
        addq.l  #1,%a0
        subq.l  #1,%d3
        bne     po_md_scan
po_md_none:
        moveq   #-1,%d0
        bra     po_md_out
po_md_found:                             | the ones after it move down (d3 = slots from here to the end)
        subq.l  #1,%d3
        beq     po_md_last
po_md_shift:
        move.b  1(%a0),(%a0)+
        subq.l  #1,%d3
        bne     po_md_shift
po_md_last:
        clr.b   (%a0)
        moveq   #0,%d0                   | the notes left
        moveq   #8,%d3
po_md_count:
        tst.b   (%a1)+
        beq     po_md_out
        addq.l  #1,%d0
        subq.l  #1,%d3
        bne     po_md_count
po_md_out:
        movem.l (%sp),%d3/%a0/%a1
        lea     12(%sp),%sp
        rts

| ---- the ring of pending note-ons: 8 entries of (identity, raw) a track, head
| (the engine's, po_start) and tail (the note-on's, po_mon) bytes mod 8.
| po_mring_push: d1 = the identity, d0 = its raw -> queued for track d2 (a full
| ring drops the note). Preserves every register.
po_mring_push:
        lea     -16(%sp),%sp
        movem.l %d0/%d3/%a0/%a1,(%sp)
        lea     po_mtail(%pc),%a0
        mvz.b   (%a0,%d2.l),%d3          | the tail
        move.l  %d3,%d0
        addq.l  #1,%d0
        andi.l  #7,%d0                   | the next tail
        lea     po_mhead(%pc),%a1
        cmp.b   (%a1,%d2.l),%d0
        beq     po_mp_out                | full: this note is dropped
        lea     po_mring(%pc),%a1
        add.l   %d3,%d3
        adda.l  %d3,%a1
        move.l  %d2,%d3
        lsl.l   #4,%d3
        adda.l  %d3,%a1                  | the entry
        move.b  %d1,(%a1)
        move.l  (%sp),%d3                | the raw
        move.b  %d3,1(%a1)
        move.b  %d0,(%a0,%d2.l)          | the entry is written before the tail moves
po_mp_out:
        movem.l (%sp),%d0/%d3/%a0/%a1
        lea     16(%sp),%sp
        rts

| po_mring_pop: d7 := the oldest pending identity, d0 := its raw; Z = the ring is
| empty (d7 = 0 then). Clobbers d1, a0, a1.
po_mring_pop:
        lea     po_mhead(%pc),%a0
        mvz.b   (%a0,%d2.l),%d1          | the head
        lea     po_mtail(%pc),%a1
        moveq   #0,%d7
        cmp.b   (%a1,%d2.l),%d1
        beq     po_mq_out                | empty
        lea     po_mring(%pc),%a1
        move.l  %d2,%d0
        lsl.l   #4,%d0
        adda.l  %d0,%a1
        adda.l  %d1,%a1
        adda.l  %d1,%a1                  | the entry
        mvz.b   (%a1),%d7
        mvz.b   1(%a1),%d0
        addq.l  #1,%d1
        andi.l  #7,%d1
        move.b  %d1,(%a0,%d2.l)          | head := next
        tst.l   %d7
po_mq_out:
        rts

| po_mring_reset: track d2's ring emptied (head := tail). Clobbers d0, a0, a1.
po_mring_reset:
        lea     po_mtail(%pc),%a1
        mvz.b   (%a1,%d2.l),%d0
        lea     po_mhead(%pc),%a0
        move.b  %d0,(%a0,%d2.l)
        rts

| ---- po_mon: 0x4000e746, the chromatic block's voice command `moveq #29,%d1;
| movel %d1,%a5@(0,%d2:l:4)` (6 bytes): the START into the mailbox, which
| stock posts BEFORE it stores the PTCH lock byte (0x4000e74c..0x4000e758: a0
| = 5 * note - 100 -> the byte at d4, the track's lock block). d2 = the track,
| a3 -> the note, a5 = the mailbox base, d4 = the lock block; d0, d1, a0, a1
| are scratch here (a1 is loaded from d4 right after the mapping). A synth
| track: the lock byte, the list, the ring and the identity first, the START
| last; stock goes on at 0x4000e754 with a0 = the raw (its own store of the
| byte repeats it). A sample track: the displaced START, then the stock mapping.
po_mon:
        bsr     po_is_synth
        beq     po_mon_stock
        mvz.b   (%a3),%d0                | the note
        subi.l  #20,%d0                  | raw = 64 + (note - 84): semitones, 84 = 0
        bpl     po_mon_raw
        moveq   #0,%d0                   | 0..19: -64
po_mon_raw:
        movea.l %d4,%a1
        move.b  %d0,(%a1)                | the PTCH lock byte, before any START can take it
        movea.l %d0,%a0
        mvz.b   (%a3),%d1
        ori.l   #0x80,%d1                | the identity
        lea     sy_state(%pc),%a1        | (the track record: T_MLEG)
        move.l  %d2,%d0
        lsl.l   #7,%d0
        adda.l  %d0,%a1
        clr.b   T_MLEG(%a1)
        bsr     po_mheld_of              | a note held on the track already? (clobbers d0, a1)
        beq     po_mon_start
        bsr     po_legmode               | the LEG gate (2 Oct 2026): 1 / 3 = legato -- the note takes the
        btst    #0,%d0                   | trigless path as a legato key does: the lock byte set, no START
        beq     po_mon_start
        bsr     po_mheld_add             | it joins the held list (its note-off releases as any note's)
        cmpi.l  #3,%d0
        bne     po_mon_trigless
        move.l  %d1,%d0
        bsr     po_legkey                | paraphonic legato: the chord follows the note (the flag before the trig)
po_mon_trigless:
        lea     sy_state(%pc),%a1
        move.l  %d2,%d0
        lsl.l   #7,%d0
        adda.l  %d0,%a1
        move.b  #1,T_MLEG(%a1)           | po_mrec records it as a trigless trig
        move.l  (%a5,%d2.l*4),%d0
        ori.l   #0x119,%d0               | the trigless trig (the key handler's 0x4004fca6)
        move.l  %d0,(%a5,%d2.l*4)
        jmp     0x4000e754
po_mon_start:
        bsr     po_mheld_add
        move.l  %a0,%d0                  | the raw again (po_mheld_of used d0)
        bsr     po_mring_push            | (identity, raw) for the engine's START
        lea     KEYS_AT,%a1
        move.b  %d1,(%a1,%d2.l)          | qz_pkey[t]: the START is this note's
        moveq   #29,%d1
        move.l  %d1,(%a5,%d2.l*4)        | the START, last
        jmp     0x4000e754
po_mon_stock:
        moveq   #29,%d1                  | displaced: the START ...
        move.l  %d1,(%a5,%d2.l*4)
        jmp     0x4000e74c               | ... then the stock mapping, 64 + 5 * (note - 84)

| ---- po_moff: 0x4000dfd4, the note-off's per-track compare `mvsb %a0@,%d1; mvsb
| %a3@,%d0; cmpl %d1,%d0; bnes 0x4000dff8` (8 bytes). d2 = the track, a0 -> its
| held-note byte, a3 -> the note; d0, d1 scratch (d5 = 1, d3 = the track's bit,
| d4 = the channel's mask, a1 = the end, a2 = the mailbox: kept). The stock
| block at 0x4000dfdc: mailbox := 0x40, held := -1, the gate bit cleared.
po_moff:
        bsr     po_is_synth
        beq     po_moff_stock
        mvz.b   (%a3),%d1
        ori.l   #0x80,%d1
        bsr     po_mheld_del             | d0 := the notes left, -1 = it was not held here
        bmi     po_moff_stock
        move.l  %d0,-(%sp)
        move.l  %a0,-(%sp)
        move.l  %d1,%d0                  | the identity: the recorder's hand-over rule (po_keyrel; no HOLD slot)
        suba.l  %a0,%a0
        bsr     po_keyrel
        movea.l (%sp)+,%a0
        move.l  (%sp)+,%d0
        move.l  %d0,%d1
        bsr     po_polytrack
        beq     po_moff_stock            | VOIC 1: the mono voice ends with the last note pressed, as stock
        tst.l   %d1
        bne     po_moff_more             | notes remain: the engine releases this one's voice, nothing else
        jmp     0x4000dfdc               | the last note: the stock block (the AMP release)
po_moff_more:
        jmp     0x4000dff8
po_moff_stock:
        mvs.b   (%a0),%d1                | displaced
        mvs.b   (%a3),%d0
        cmp.l   %d1,%d0
        bne     po_moff_more
        jmp     0x4000dfdc

| ---- po_rel: 0x4000b51a, the frame builder's AMP-release consumer `moveal
| %sp@(114),%a3; movel %a1@(0,%a3:l:4),%d0` (8 bytes): the builder found bit 6
| in the track's mailbox 0x46c80354[t] (0x4000b4e4; a1 = the mailbox base,
| sp@(114) = the track), took the release bytes 0x80001828/9 into its frame,
| wrote 4 into the LFO state 0x80004858[t], and here re-reads the word to clear
| bit 6 (andl #-65 at 0x4000b522). Every path that posts 0x40 -- the panel key
| release 0x4004fbfe.. (the last held key), the MIDI note-off's stock block
| 0x4000dfdc (po_moff's last note), whatever the sequencer posts -- passes this
| one site. A synth voice (S_ON bit 0) takes the released flag (S_ON bit 1):
| plan B -- the mono voice's release starts (po_mono_env: the REL law), since the
| DSP no longer fades anything -- unless the same word carries the START (bit 2):
| the START retriggers the voice warm (sy_cold), nothing releases. d2 is reloaded from a3 at 0x4000b52c, a0
| at 0x4000b540: both scratch here; d0 = the word, a3 = the track: kept.
po_rel:
        movea.l 114(%sp),%a3             | displaced: the track
        move.l  (%a1,%a3.l*4),%d0        | displaced: its mailbox word (bit 6 set)
        btst    #2,%d0                   | a START in the same word (a panel key pressed while one is held,
        bne     po_rel_out               | LEG OFF: 0x4004fbfe posts the note-off and the START together): the
        move.l  %a3,%d2                  | DSP restarts at full this frame, the release never fades -- no flag
        lsl.l   #7,%d2                   | * ST_STRIDE
        lea     sy_state(%pc),%a0
        adda.l  %d2,%a0
        btst    #0,S_ON(%a0)             | a synth plays: it has been released
        beq     po_rel_out
        bset    #1,S_ON(%a0)
po_rel_out:
        jmp     0x4000b522

| ---- po_retrig: 0x4000c634 (8 bytes displaced: `moveal 114(sp),a1; moveb (a0,a1.l),d0`,
| a0 = 0x46104d15) -- the frame builder's per-track copy of the DSP command byte
| 0x46104d15[t] into the packer's nibble byte 0x46104d0c[t] (0x4000c642), the one
| funnel every START form passes on its way to the DSP and the packer. THE CAUSE
| (BUILD 37, 29 Sep 2026; po_rtlog's ring, root29w/run_f37a.log): a sequencer trig
| on a track whose voice still sounds is posted by the builder's own sequencer
| path (0x4000b906: the trig record's byte +62, then the OR-0x10 of 0x4000b9aa /
| 0x4000bd74 / 0x4000bdc0) as 0x10 | n -- the CF START bit 4 with the trig's
| sub-frame position n (measured cycling 4, 0xc, 5, 0xd, ... at 120 BPM: a step
| is 344.5 frames) and no bit 5; the packer splits the frame's render calls at n
| and the DSP crossfades its old voice under the new one for ~26 samples. Both
| are the engine's one continuous stream (sy_warm: the same oscillator carries
| on), so old + new = a +5.6 dB bump at every trig. The panel key's START (the
| raw mailbox word 0x1d of 0x40005030's raw-store exit) reaches the DSP as 0x30
| -- bits 4 and 5, nibble 0 -- and is clean (x1.00, the DIAG round's kwh take).
| THE FIX: on a synth track whose engine voice is on (S_ON != 0) every START byte
| (bit 4 or 5 set) becomes exactly the key's clean form 0x30 -- the CF START at
| the frame's first sample (the trig lands a frame boundary early, at most 15
| samples = 0.34 ms), the packer's calls [0,0) + [0,16), sy_render's START rule
| as before (HOLD re-armed, the index envelope restarted, the pitch snapped,
| warm: phase-continuous from the level reached). A silent synth track (S_ON 0)
| and every sample track keep stock's byte. po_rtlog counts the passes and the
| rewrites and rings the START bytes (the rig peeks it at po_clock + 32).
po_retrig:
        movea.l 114(%sp),%a1             | displaced: a1 = the track
        lea     -24(%sp),%sp
        movem.l %d1-%d4/%a2-%a3,(%sp)
        move.l  %a1,%d4                  | the track
        cmpi.l  #8,%d4
        bcc     po_retrig_out
        mvz.b   (%a0,%a1.l),%d1          | the DSP command byte posted this frame
        lea     po_rtlog(%pc),%a2
        addq.l  #1,RT_CALLS(%a2)
        move.l  %d1,%d2
        andi.l  #0x30,%d2
        beq     po_retrig_out            | no START of any form (a release, nothing): stock's byte stands
        move.l  %d4,%d2
        lsl.l   #7,%d2
        lea     sy_state(%pc),%a3
        add.l   %d2,%a3                  | the track's engine record
        move.l  %d1,%d3                  | the byte as posted
        tst.b   S_ON(%a3)
        beq     po_retrig_log            | not a synth track with a voice on: stock's byte stands
        moveq   #0x30,%d1
        move.b  %d1,(%a0,%a1.l)          | the clean form: a CF START at the frame's first sample
        addq.l  #1,RT_FIXED(%a2)
po_retrig_log:
        move.l  RT_HEAD(%a2),%d2
        addq.l  #1,RT_HEAD(%a2)
        andi.l  #31,%d2
        lsl.l   #3,%d2
        lea     RT_RING(%a2,%d2.l),%a2
        move.l  po_clock+CK_FRAMES(%pc),%d2
        move.l  %d2,(%a2)
        mvz.b   S_ON(%a3),%d2
        lsl.l   #8,%d2
        or.l    %d1,%d2                  | the byte now
        lsl.l   #8,%d2
        or.l    %d3,%d2                  | the byte as posted
        lsl.l   #8,%d2
        or.l    %d4,%d2                  | the track
        move.l  %d2,4(%a2)
po_retrig_out:
        movem.l (%sp),%d1-%d4/%a2-%a3
        lea     24(%sp),%sp
        move.b  (%a0,%a1.l),%d0          | displaced: the byte (rewritten or not) for the packer's nibble byte
        jmp     0x4000c63c

| ---- po_stop: 0x4000b2c8, the frame builder's `clrl 0x46c80350` (6 bytes) -- the
| sequencer's STOP / restart word (3, or 1) consumed: the builder has just turned
| it into the DSP-wide all-off command byte (0x10 / 0x30 into 0x46104d14), with no
| per-track mailbox and no CF voice kill (stage 1). The DSP's envelope no longer
| ends anything (plan B), so the engine ends everything here: every synth track's
| mono voice takes the released flag (S_ON bit 1 -> po_mono_env's release) and
| every sounding paraphonic voice releases (state 2 -> po_frame's release). The
| tail fades under the DSP's all-off (inaudible) and the levels reach 0, so the
| next START is cold. d0 is dead here (reloaded at 0x4000b2ce); a0 / d1 saved.
po_stop:
        clr.l   GLOBAL_WORD              | displaced
        lea     -16(%sp),%sp
        movem.l %d1/%d2/%a0/%a1,(%sp)
        lea     sy_state(%pc),%a0
        lea     po_voices(%pc),%a1
        moveq   #8,%d1
po_stop_t:
        btst    #0,S_ON(%a0)
        beq     po_stop_p
        bset    #1,S_ON(%a0)
        bset    #2,S_ON(%a0)             | STOPPED: REL INF releases at the 1 ms floor (po_mono_env, po_frame's T_RK)
po_stop_p:
        moveq   #4,%d2
po_stop_v:
        mvz.b   V_STATE(%a1),%d0
        cmpi.l  #1,%d0
        bne     po_stop_v1
        move.b  #2,V_STATE(%a1)
po_stop_v1:
        lea     V_STRIDE(%a1),%a1
        subq.l  #1,%d2
        bne     po_stop_v
        lea     ST_STRIDE(%a0),%a0
        subq.l  #1,%d1
        bne     po_stop_t
        movem.l (%sp),%d1/%d2/%a0/%a1
        lea     16(%sp),%sp
        jmp     0x4000b2ce

| ---- po_kill: 0x4000685c, the stock VOICE KILL 0x40006820(t)'s CF voice-byte
| clear `clrb %d0; moveb %d0,%a1@(0,%a0:l)` (6 bytes; BUILD 33). The kill's
| prologue takes the track from 4(sp): t >= 8 recurses through the entry for
| 0..7, so this site sees one track at a time, d1 = t, a0 = 0x800049d8, a1 =
| 168 t, interrupts masked (0x40006846: no render call is mid-flight). Every
| path that ends a stock voice HARD comes here: the sequencer's STOP / pattern
| change 0x40043c50 (per track), the sample preview stop 0x40093ec0 /
| 0x40096ad4, the loaders 0x4007eb3e / 0x4008044e / 0x4000f518 (slot / project
| change), the frame builder's own 0x4000d45a (its end mask), 0x40008110 /
| 0x40006b30 / 0x4008055c. The DSP voice is dead at this instant -- an
| immediate zero is inaudible -- so the engine's voices of the track END here:
| S_GAIN / S_GPREV / S_HTIM := 0 and S_ON := 0 (the mono voice: silent, no
| synth playing), the four paraphonic voices freed (po_free: state 0, V_GAIN /
| V_GPREV 0) with V_KEY / V_HOLD := 0. The next START is cold (sy_cold:
| S_GPREV == 0 -> phase 0 from 0). A sample track's record is zeroed the same
| way (S_ON was 0 already). po_stop (0x4000b2c8) stays as belt-and-braces for a
| STOP that posts the global word without a kill: on a killed track it finds
| S_ON 0 and does nothing. d0 / a0 are dead here (reloaded at 0x40006862 /
| 0x40006866), a2 is set at 0x40006868; d1 / d2 / a1 preserved.
po_kill:
        clr.b   %d0                      | displaced
        move.b  %d0,(%a1,%a0.l)          | displaced: the CF voice byte := 0
        lea     -8(%sp),%sp
        movem.l %d2/%a1,(%sp)
        move.l  %d1,%d2                  | d2 = the track (po_free's argument)
        move.l  %d1,%d0
        lsl.l   #7,%d0                   | * ST_STRIDE
        lea     sy_state(%pc),%a0
        add.l   %d0,%a0
        clr.b   S_ON(%a0)                | nothing of ours plays on this track
        clr.l   S_GAIN(%a0)
        clr.w   S_GPREV(%a0)             | silent: the next START is cold
        clr.l   S_HTIM(%a0)
        bsr     po_free                  | the four voices: state 0, V_GAIN / V_GPREV 0 (clobbers d0, a0)
        lea     po_voices(%pc),%a0
        move.l  %d2,%d0
        lsl.l   #8,%d0                   | * 4 voices * V_STRIDE
        add.l   %d0,%a0
        moveq   #4,%d0
po_kill_v:
        clr.b   V_KEY(%a0)               | no key owns it, no sequencer gate runs
        clr.l   V_HOLD(%a0)
        lea     V_STRIDE(%a0),%a0
        subq.l  #1,%d0
        bne     po_kill_v
        movem.l (%sp),%d2/%a1
        lea     8(%sp),%sp
        jmp     KILL_RET

| ---- po_mgate: 0x4000e452, the octave switch `movel %d6,%d0; subql #2,%d0; moveq
| #5,%d2; cmpl %d0,%d2` (8 bytes; the bcs at 0x4000e45a follows). d6 = the octave
| (7 for note 96), d3 = the channel's track mask (bit 8 = the auto channel), a3
| -> the note. A note outside 72..96 addressed to a synth track takes the
| chromatic block for the channel's synth tracks alone.
po_mgate:
        mvz.b   (%a3),%d0
        cmpi.l  #72,%d0
        bcs     po_mg_wide
        cmpi.l  #96,%d0
        bls     po_mg_stock              | 72..96: the stock map (po_mon maps the synth tracks in it)
po_mg_wide:
        btst    #8,%d3
        beq     po_mg_mask
        mvz.b   0x80000000,%d2           | the auto channel: the active track alone
        bsr     po_is_synth
        beq     po_mg_stock
        jmp     0x4000e6e2
po_mg_mask:
        move.l  %d1,-(%sp)
        moveq   #0,%d1                   | the synth tracks among the channel's
        moveq   #7,%d2
po_mg_scan:
        btst    %d2,%d3
        beq     po_mg_next
        bsr     po_is_synth
        beq     po_mg_next
        bset    %d2,%d1
po_mg_next:
        subq.l  #1,%d2
        bpl     po_mg_scan
        tst.l   %d1
        beq     po_mg_none
        move.l  %d1,%d3                  | a keyboard channel: its synth tracks take the note
        move.l  (%sp)+,%d1
        jmp     0x4000e6e2
po_mg_none:
        move.l  (%sp)+,%d1
po_mg_stock:
        move.l  %d6,%d0                  | displaced
        subq.l  #2,%d0
        moveq   #5,%d2
        cmp.l   %d0,%d2
        jmp     0x4000e45a

| ---- po_mogate: 0x4000de10, the note-off's octave switch `subql #2,%d0; moveq
| #5,%d3; cmpl %d0,%d3` (6 bytes; the bcs at 0x4000de16 follows). d0 = the
| octave, d2 = the note, d4 = the channel's track mask (bit 8 = the auto
| channel). A note outside 72..96 addressed to a synth track takes the
| chromatic block 0x4000df9e for the channel's synth tracks alone, as its
| note-on did (po_mgate), so po_moff sees its release.
po_mogate:
        cmpi.l  #72,%d2
        bcs     po_mog_wide
        cmpi.l  #96,%d2
        bls     po_mog_stock
po_mog_wide:
        lea     -12(%sp),%sp
        movem.l %d0/%d1/%d2,(%sp)
        btst    #8,%d4
        beq     po_mog_mask
        mvz.b   0x80000000,%d2           | the auto channel: the active track alone
        bsr     po_is_synth
        beq     po_mog_none
        movem.l (%sp),%d0/%d1/%d2
        lea     12(%sp),%sp
        jmp     0x4000df9e
po_mog_mask:
        moveq   #0,%d1                   | the synth tracks among the channel's
        moveq   #7,%d2
po_mog_scan:
        btst    %d2,%d4
        beq     po_mog_next
        bsr     po_is_synth
        beq     po_mog_next
        bset    %d2,%d1
po_mog_next:
        subq.l  #1,%d2
        bpl     po_mog_scan
        tst.l   %d1
        beq     po_mog_none
        move.l  %d1,%d4                  | the keyboard channel's synth tracks
        movem.l (%sp),%d0/%d1/%d2
        lea     12(%sp),%sp
        jmp     0x4000df9e
po_mog_none:
        movem.l (%sp),%d0/%d1/%d2
        lea     12(%sp),%sp
po_mog_stock:
        subq.l  #2,%d0                   | displaced
        moveq   #5,%d3
        cmp.l   %d0,%d3
        jmp     0x4000de16

| ---- po_mrec: 0x400625e0, the 0x41 event handler's live-recorder entry `movel
| %a2@(4),%d0; movel %d0,0x46c7e956` (10 bytes), reached for the ACTIVE track
| while LIVE RECORDING (stock's checks, kept). d1 = the track, a2 -> the event
| record (+2 the note, +4 the context). Stock goes on at 0x400625ea (the
| recorder, then the PTCH lock 5 * note - 356 through 0x40062550); the handler
| ends at 0x40062d1c with the stack as here.
po_mrec:
        move.l  4(%a2),%d0               | displaced: the recorder's context ...
        move.l  %d0,REC_CTX              | ... published for the writers
        lea     -24(%sp),%sp
        movem.l %d2-%d4/%a2-%a4,(%sp)
        move.l  %d1,%d2                  | the track
        bsr     po_is_synth
        beq     po_mr_stock
        mvz.b   2(%a2),%d3               | the note
        move.l  %d3,%d4
        subi.l  #20,%d4                  | its raw (po_mon's rule)
        bpl     po_mr_raw
        moveq   #0,%d4
po_mr_raw:
        ori.l   #0x80,%d3                | the identity (po_keyrec's d3)
        movea.l %d4,%a2                  | the raw (po_keyrec's a2)
        lea     sy_state(%pc),%a3
        move.l  %d2,%d0
        lsl.l   #7,%d0
        adda.l  %d0,%a3
        tst.b   T_MLEG(%a3)              | a legato note (po_mon, 2 Oct 2026): a TRIGLESS trig, as a legato
        bne     po_mr_leg                | key records (the quantizer's qz_leg3), no join query
        moveq   #-1,%d0
        bsr     po_keyrec                | does the note JOIN the chord being recorded?
        tst.l   %d0
        bne     po_mr_done               | joined: the chord's step has the locks, no trig of its own
        lea     -20(%sp),%sp             | (the frames are stored, not pushed: po_lockw's form)
        move.l  %d2,(%sp)
        move.l  REC_CTX,%d0
        move.l  %d0,4(%sp)
        jsr     REC_TRIG                 | the stock recorder (track, ctx) -> the step, -1 = none
        bra     po_mr_placed
po_mr_leg:
        clr.b   T_MLEG(%a3)
        lea     -20(%sp),%sp
        move.l  %d2,(%sp)
        move.l  REC_CTX,%d0
        move.l  %d0,4(%sp)
        jsr     REC_TRIGLESS             | the stock trigless recorder (track, ctx) -> the step, -1 = none
po_mr_placed:
        tst.l   %d0
        bmi     po_mr_pop
        move.l  %d0,%d4                  | the step
        move.l  %d0,12(%sp)
        move.l  %a2,8(%sp)               | the raw
        clr.l   4(%sp)                   | flat slot 0: PTCH
        move.l  REC_CTX,%d0
        move.l  %d0,16(%sp)
        jsr     LOCK_WRITE               | the step's PTCH lock, as stock writes it (semitones here)
        lea     20(%sp),%sp
        move.l  %d4,%d0
        bsr     po_keyrec                | a new chord record starts with this note on its step
        bra     po_mr_done
po_mr_pop:
        lea     20(%sp),%sp
po_mr_done:
        movem.l (%sp),%d2-%d4/%a2-%a4
        lea     24(%sp),%sp
        jmp     0x40062d1c               | the handler's end
po_mr_stock:
        movem.l (%sp),%d2-%d4/%a2-%a4
        lea     24(%sp),%sp
        move.l  4(%a2),%d0               | as displaced
        jmp     0x400625ea

| ---- po_mtrig: 0x4006262a, the same handler's trig-held branch `mvsb %a2@(2),%d2;
| moveal %d2,%a0; lea %a0@(0,%d2:l:4),%a0` (8 bytes): a0 - 356 is the PTCH lock
| the held trig gets (0x4004f5f8 through 0x40062afc). d1 = the track. A synth
| track's lock is the raw, note - 20.
po_mtrig:
        mvs.b   2(%a2),%d2               | displaced: a0 = 5 * note
        movea.l %d2,%a0
        lea     (0,%a0,%d2.l*4),%a0
        move.l  %d2,-(%sp)
        move.l  %d1,%d2
        bsr     po_is_synth
        move.l  (%sp)+,%d2
        tst.l   %d0
        beq     po_mt_out
        move.l  %d2,%d0
        subi.l  #20,%d0
        bpl     po_mt_raw
        moveq   #0,%d0
po_mt_raw:
        addi.l  #356,%d0                 | raw + 356: the branch subtracts 356
        movea.l %d0,%a0
po_mt_out:
        jmp     0x40062634

| ==== TRANSPOSING A HELD STEP: po_octave (4 Oct 2026) ==========================
| FUNC + UP / DOWN is the trig-mode selector (manual 12.7): both keys' records
| in the FUNC layer's table (0x400bf628, MKI 0x400bf2b4) name the handler
| 0x40051fc4(code, edge). The selector is a WINDOW: its handle is the long
| 0x400bebae (0 = closed). Closed, a press (edge 1) opens it through the
| pointer 0x400bebca (0x400586cc: 0x4005829c builds it, the handle is
| stored, its key layer registered with 0x40031494, the list drawn with the
| mode 0x460d16f0) and any other edge returns; open, a press or a repeat
| (edge 2) steps the mode (0x40051f54 UP for code 0x33, 0x40051ee4 DOWN for
| any other) and the handler chains to 0x400bebd2 (the window's redraw
| 0x400359ac). The hook sits at the handle test (0x40051fce: `tstl
| 0x400bebae; beqs 0x40051ff6`, d1 = the code, d0 = the edge, d2 pushed) and
| takes a press with the window CLOSED when a [TRIG] key is held for locking
| on a synth track in GRID RECORDING, in any trig mode -- the lock editor's
| own state: the held-trig mask 0x460d174a (a word, bit n = [TRIG n + 1],
| as the PTCH knob's editor 0x400508e4 walks it), the trig page's first
| step 0x460d174c, GRID RECORDING 0x460d1736. The trig mode 0x460d16f0 is
| NOT a gate (6 Oct 2026, Tim on hardware: CHROMATIC + a held trig + FUNC +
| DOWN opened the selector): in GRID RECORDING the [TRIG] keys edit steps
| whatever the mode, and the mask's writers (the press 0x40050f88.., the
| release 0x4005fbb2..) test the edit state 0x460d5db4 and the machine, not
| the mode. Every held step's PTCH lock (flat slot 0, the
| record's 0x59 + step * 32) moves 12 raw units = an octave in the synth's
| semitone PTCH, UP or DOWN, clamped 0..127 (-64..+63); a step without a
| lock (0xff) starts from the Part's PTCH and gets one. The store is the
| editor's (0x40050e60..): the byte in the bank's RAM record and in its
| battery-RAM mirror, the bank's changed flag (+635698) and 0x100f8598,
| 0x40027e00 after each step, then its tail -- 0x4009da20(track), 0x460d173a
| := 1, the six words 0x460d1a9e.. and 0x460d10dc cleared, 0x460d1750 := 1,
| 0x400418e0, the redraw 0x4004d948(-1), 0x40027de4 -- so the PLAYBACK page
| (the locks are shown while the trig is held) prints the new value at
| once; the handler then returns as it does for a release (0x40052006), the
| selector never opened. A repeat or a release with a trig held returns the
| same way (stock returns there too with the window closed): one press, one
| octave. The window open, no trig held, a sample track, or GRID RECORDING
| off: the displaced test and its branch, byte for byte the selector.
        .set    SEL_WIN, 0x400bebae      | the selector window's handle, 0 = closed
        .set    OCT_HOOK_OPEN, 0x40051fd6 | the displaced beq's fall-through: the window is open (its presses step the mode)
        .set    OCT_HOOK_CLOSED, 0x40051ff6 | ... its target: the window is closed (a press opens it)
        .set    OCT_HOOK_RTS, 0x40052006 | the handler's return (`movel %sp@+,%d2; rts`)
        .set    GRID_REC, 0x460d1736     | nonzero: GRID RECORDING (PANEL.md)
        .set    HELD_MASK, 0x460d174a    | word: the [TRIG] keys held for locking
        .set    HELD_PAGE, 0x460d174c    | long: the trig page's first step (0 16 32 48)
        .set    TRIG_MODE, 0x460d16f0    | 0 TRACKS 1 CHROMATIC 2 SLOTS 3 SLICES 4 QUICK MUTE 5 DELAY CTRL (not a gate since 6 Oct 2026)
        .set    TRACK_CUR, 0x100b14cc    | the current audio track
        .set    PAT_IDX, 0x100b14d0      | the current pattern in the bank
        .set    TRK_STRIDE, 2330
        .set    PAT_STRIDE, 36568
        .set    LOCK_OFF, 0x59           | the record's step locks: + step * 32 + flat slot
        .set    BANK_DIRTY, 635698       | bank RAM + this: the "changed" long the editor sets
        .set    DIRTY2, 0x100f8598
        .set    ED_TIDY, 0x40027e00      | the editor calls it after each store ...
        .set    ED_END, 0x40027de4       | ... and at its exit
        .set    ED_SENT, 0x4009da20      | (track): the editor's post-store call
        .set    ED_FLAG1, 0x460d173a
        .set    ED_WORDS, 0x460d1a9e     | five words the editor zeroes ...
        .set    ED_WORD6, 0x460d10dc     | ... and a sixth
        .set    ED_FLAG2, 0x460d1750
        .set    ED_CALL, 0x400418e0
        .set    REDRAW, 0x4004d948       | (-1): the display refresh
        .set    PLAY_SLOTS, 0x8edaa      | Part: + machine * 6 + track * 30 = the PLAYBACK slots' bytes
        .set    OCT_JUMP, 12
        .set    KEY_UP, 0x33
po_octave:
        tst.l   SEL_WIN                  | the selector open: its own presses
        bne     po_oc_open
        tst.l   GRID_REC
        beq     po_oc_closed
        tst.w   HELD_MASK
        beq     po_oc_closed
        lea     -48(%sp),%sp
        movem.l %d0-%d7/%a2-%a5,(%sp)
        mvz.b   TRACK_CUR,%d2
        bsr     po_is_synth
        tst.l   %d0
        beq     po_oc_pop_closed
        move.l  (%sp),%d0                | the edge: 1 = the press ...
        subq.l  #1,%d0
        bne     po_oc_swallow            | ... a repeat or the release: nothing (stock returns too)
        moveq   #OCT_JUMP,%d3
        cmpi.l  #KEY_UP,%d1
        beq     po_oc_dir
        neg.l   %d3
po_oc_dir:
        mvz.w   HELD_MASK,%d7
        moveq   #0,%d6                   | the trig key, 0..15
po_oc_bit:
        btst    %d6,%d7
        beq     po_oc_next
        move.l  %d6,%d0
        add.l   HELD_PAGE,%d0            | the step
        lsl.l   #5,%d0
        move.l  %d2,%d1
        move.l  #TRK_STRIDE,%d4
        muls.l  %d4,%d1
        add.l   %d1,%d0
        mvz.b   PAT_IDX,%d1
        move.l  #PAT_STRIDE,%d4
        muls.l  %d4,%d1
        add.l   %d1,%d0                  | the step's record in the bank, + LOCK_OFF = its locks
        movea.l PART_PTR,%a2
        adda.l  %d0,%a2
        lea     LOCK_OFF(%a2),%a2        | the PTCH lock byte (flat slot 0) in RAM ...
        lea     PAT_MIR+LOCK_OFF,%a3
        adda.l  %d0,%a3                  | ... and in the battery-RAM mirror
        mvz.b   (%a2),%d1
        cmpi.l  #0xff,%d1
        bne     po_oc_have
        bsr     po_part_ptch             | no lock yet: from the Part's PTCH
po_oc_have:
        add.l   %d3,%d1
        bpl     po_oc_lo
        moveq   #0,%d1
po_oc_lo:
        cmpi.l  #127,%d1
        ble     po_oc_hi
        moveq   #127,%d1
po_oc_hi:
        move.b  %d1,(%a2)
        move.b  %d1,(%a3)
        movea.l PART_PTR,%a0
        move.l  #BANK_DIRTY,%d0
        moveq   #1,%d1
        move.l  %d1,(%a0,%d0.l)          | the bank has changed
        move.l  %d1,DIRTY2
        jsr     ED_TIDY
po_oc_next:
        addq.l  #1,%d6
        cmpi.l  #16,%d6
        blt     po_oc_bit
        move.l  %d2,-(%sp)               | the editor's tail
        jsr     ED_SENT
        addq.l  #4,%sp
        moveq   #1,%d0
        move.l  %d0,ED_FLAG1
        lea     ED_WORDS,%a0
        clr.w   (%a0)
        clr.w   2(%a0)
        clr.w   4(%a0)
        clr.w   6(%a0)
        clr.w   8(%a0)
        clr.w   ED_WORD6
        move.l  %d0,ED_FLAG2
        jsr     ED_CALL
        pea     -1
        jsr     REDRAW                   | the page shows the held step's new lock
        addq.l  #4,%sp
        jsr     ED_END
po_oc_swallow:
        movem.l (%sp),%d0-%d7/%a2-%a5
        lea     48(%sp),%sp
        jmp     OCT_HOOK_RTS             | the handler returns; the selector stays closed
po_oc_pop_closed:
        movem.l (%sp),%d0-%d7/%a2-%a5
        lea     48(%sp),%sp
po_oc_closed:                            | displaced: `tstl 0x400bebae; beqs 0x40051ff6`
        jmp     OCT_HOOK_CLOSED
po_oc_open:
        jmp     OCT_HOOK_OPEN

| ---- po_part_ptch: d2 = track -> d1 = the Part's PTCH byte (raw), as the lock
| editor reads it for a step without a lock (0x40050cf2..: the Part, its
| machine byte, PLAY_SLOTS + machine * 6 + track * 30, slot 0). Clobbers d0, a0, a1.
po_part_ptch:
        movea.l PART_PTR,%a0
        mvz.b   PART_IDX,%d0
        move.l  #6322,%d1
        muls.l  %d1,%d0
        adda.l  %d0,%a0                  | the Part
        move.l  %a0,%d1
        add.l   %d2,%d1
        addi.l  #MACH_OFF,%d1
        movea.l %d1,%a1
        mvz.b   (%a1),%d0                | the track's machine (1 = FLEX)
        add.l   %d0,%d0
        move.l  %d0,%d1
        add.l   %d0,%d0
        add.l   %d0,%d1                  | machine * 6
        adda.l  %d1,%a0
        move.l  %d2,%d1
        lsl.l   #5,%d1
        sub.l   %d2,%d1
        sub.l   %d2,%d1                  | track * 30
        adda.l  %d1,%a0
        adda.l  #PLAY_SLOTS,%a0
        mvz.b   (%a0),%d1                | PTCH, slot A
        rts

| ==== THE AMP SETUP PAGE'S SIXTH BOX: LEG (2 Oct 2026) =============================
| FUNC + AMP opens the AMP SETUP window (0x40059c8c): it stages the stock AMP
| descriptor's page 2 into its knob array (0x40059d56: `pea 0x400d3988; jsr
| 0x400326d4`, the enable nibbles decide which boxes take a knob), and its
| drawer 0x40036794 walks the six boxes with the names at 0x400d39c2 (P +
| 0x3a), the formatters at 0x400d3a6a (P + 0xca + 24, the widgets 48 bytes
| on) and the enable pair 0x400d3b12/16 (P + 0x18a/0x18e), all hard-coded --
| the resolver is not consulted, so the LFO page's trick (po_lfopage) does
| not reach it. The sixth box is p11 TRIG: named, five values, nibble 0 (not
| drawn, no knob), a Part byte behind it all the same (AMP_P2_OFF + track *
| 30 + 5, the page-2 editor 0x4003adec writes it, the shadow 0x100a51c6 +
| part * 6322 + track * 30 + 5 in battery RAM with it, and the live lane
| 0x8000083c + track * 72 + 5 -> the DSP record's AMP word 23, low byte,
| which sy_render zeroes for the DSP). Five detours (modules/synth/manifest.py),
| every one asking po_amp_desc for the descriptor: the CLONE for an audio
| current track (0x80000000: the window's and the editor's track) -- count 3
| (OFF / MONO / POLY) on a synth track, count 2 (OFF / MONO) on any other
| audio track since 3 Oct 2026 (po_amp_kind) -- and the stock record for the
| master track (track 7 with 0x80000034 set: its AMP page is another
| record's); the MIDI-mode pages never run this window:
|   * po_ampstage at 0x40059d56: the clone is staged (its nibble gives box 6
|     the F knob);
|   * po_ampdraw1 at 0x4003685a (the two leas), po_ampdraw2 at 0x400368ac
|     and po_ampdraw3 at 0x40036946 (the enable pair): the drawer reads the
|     clone's names, formatter, widget and nibbles;
|   * po_ampedit at 0x4003ae40, the page-2 editor's handler read (it reads
|     the STOCK record's handler, min and count -- count 5): slot 11 of an
|     audio track gets po_legknob, one value a detent, clamped 0..2 (synth)
|     or 0..1 (sample) by the handler itself (the editor's own clamp is 0..4).
| The clone (po_ampdesc_buf, built on first use from the stock record in the
| image, as po_lfodesc): slot 11 named LEG, formatter po_fmt_leg (OFF / MONO
| / POLY), widget LEG_WIDGET, default 0, nibble 1; its count is written on
| every hand-out (3 or 2, the current track's). The knob writes the Part
| byte through the stock editor, so SAVE, RELOAD, a warm boot and Part copy
| carry it as they carry every AMP page-2 byte.
|
| po_amp_kind: d2 = track -> d0 = 0 (the master track: the stock record), 2
| (an audio track: LEG OFF / MONO) or 3 (a synth track: OFF / MONO / POLY) --
| the clone's count for slot 11. Clobbers d0, d1, a0, a1; tst.l d0 done.
po_amp_kind:
        moveq   #0,%d0
        cmpi.l  #7,%d2
        bne     po_ak_audio
        tst.b   MASTER_ON                | track 8 as the MASTER track: not ours
        bne     po_ak_out
po_ak_audio:
        bsr     po_is_synth
        addq.l  #2,%d0                   | 2 sample, 3 synth
po_ak_out:
        tst.l   %d0
        rts
po_amp_desc:                             | d0 := the descriptor for the current track; clobbers d0, d1, a0, a1
        move.l  %d2,-(%sp)
        mvz.b   0x80000000,%d2           | the current track
        bsr     po_amp_kind
        move.l  (%sp)+,%d2
        tst.l   %d0
        beq     po_ad_stock
        move.l  %d0,-(%sp)               | (the count, across the build)
        lea     po_ampdesc_buf(%pc),%a1
        tst.b   po_amp_built
        bne     po_ad_have
        lea     AMP_P,%a0                | the clone: the stock record ...
        move.l  #AMP_DESC_LEN,%d1
po_ad_copy:
        move.b  (%a0)+,(%a1)+
        subq.l  #1,%d1
        bne     po_ad_copy
        lea     po_ampdesc_buf(%pc),%a1
        lea     po_leg(%pc),%a0          | ... slot 11 named LEG (6 bytes) ...
        move.l  (%a0)+,0x16+66(%a1)
        move.w  (%a0),0x16+70(%a1)
        lea     po_fmt_leg(%pc),%a0      | ... printing OFF / MONO / POLY ...
        move.l  %a0,0xca+44(%a1)
        move.l  #LEG_WIDGET,%d1          | ... on the three-position select ...
        move.l  %d1,0xfa+44(%a1)
        clr.b   0x5e+11(%a1)             | ... default 0 (min 0 as stock; the count below) ...
        move.l  0x18a(%a1),%d1           | ... drawn and turned: p11's nibble (bits 12..15 of the
        andi.l  #0xffff0fff,%d1          | params 8..11 word) := 1
        ori.l   #0x00001000,%d1
        move.l  %d1,0x18a(%a1)
        lea     po_amp_built(%pc),%a0
        move.b  #1,(%a0)
po_ad_have:
        move.l  (%sp)+,%d0
        move.l  %d0,0x9a+44(%a1)         | slot 11's count: 3 (OFF / MONO / POLY) or 2 (OFF / MONO), the track's
        move.l  %a1,%d0
        rts
po_ad_stock:
        move.l  #AMP_P,%d0
        rts

| ---- po_legmax: d0 := the current track's top LEG value, 2 (synth) or 1 (sample);
| preserves every other register (the formatter's and the knob handler's helper).
po_legmax:
        lea     -16(%sp),%sp
        movem.l %d1/%d2/%a0/%a1,(%sp)
        mvz.b   0x80000000,%d2
        bsr     po_amp_kind
        subq.l  #1,%d0                   | 3 -> 2, 2 -> 1 (0, the master track, never draws the box)
        bpl     po_lx_out
        moveq   #0,%d0
po_lx_out:
        movem.l (%sp),%d1/%d2/%a0/%a1
        lea     16(%sp),%sp
        rts

| ---- po_fmt_leg: fmt(buf, value) -> "OFF" / "MONO" / "POLY" (the value clamped to
| the track's top: 2.. = POLY on a synth track, 1.. = MONO on a sample track) ---
po_fmt_leg:
        bsr     po_legmax
        move.l  %d0,%d1
        move.l  8(%sp),%d0
        cmp.l   %d1,%d0
        bls     po_fl1
        move.l  %d1,%d0
po_fl1:
        lsl.l   #3,%d0                   | 8 bytes a name
        lea     po_legnames(%pc),%a0
        adda.l  %d0,%a0
        movea.l 4(%sp),%a1
po_fl_cp:
        move.b  (%a0)+,(%a1)+
        bne     po_fl_cp
        rts

| ---- po_legknob(slot, detents, value) -> d0 = the value stepped one a detent, 0..2
| on a synth track, 0..1 on a sample track (po_legmax) ------------------------------
po_legknob:
        bsr     po_legmax
        move.l  %d0,%d1
        move.l  12(%sp),%d0
        add.l   8(%sp),%d0
        bpl     po_lk1
        moveq   #0,%d0
po_lk1:
        cmp.l   %d1,%d0
        ble     po_lk2
        move.l  %d1,%d0
po_lk2:
        rts

| ---- 0x40059d56, the AMP SETUP window's staging `pea 0x400d3988` (6 bytes): the
| descriptor for the current track (d0/d1/a0/a1 are scratch around the call).
po_ampstage:
        bsr     po_amp_desc
        move.l  %d0,-(%sp)
        jmp     0x40059d5c

| ---- 0x4003685a, the drawer's `lea 0x400d39c2,%a4; lea 0x400d3a6a,%a3` (12 bytes):
| a4 = the page-2 names, a3 = their formatters (the widgets at +48).
po_ampdraw1:
        bsr     po_amp_desc
        movea.l %d0,%a0
        lea     0x3a(%a0),%a4
        lea     0xca+24(%a0),%a3
        jmp     0x40036866

| ---- 0x400368ac and 0x40036946, the drawer's `movel 0x400d3b16,-(sp); movel
| 0x400d3b12,-(sp)` (12 bytes each): the enable pair for the accessor 0x400a6994.
po_ampdraw2:
        bsr     po_amp_desc
        movea.l %d0,%a0
        move.l  0x18e(%a0),-(%sp)
        move.l  0x18a(%a0),-(%sp)
        jmp     0x400368b8
po_ampdraw3:
        bsr     po_amp_desc
        movea.l %d0,%a0
        move.l  0x18e(%a0),-(%sp)
        move.l  0x18a(%a0),-(%sp)
        jmp     0x40036952

| ---- 0x4003ae40, the page-2 editor's `addil #0x400d3988,%d0; moveal %d0,%a1;
| moveal %a1@(298),%a0` (12 bytes): d0 = (slot + 6) * 4, d2 = slot + 6, d4 = the
| track; a0 := the slot's handler (0 = the default stepper). Slot 11 of an
| audio track (po_amp_kind, not the master track): po_legknob.
po_ampedit:
        addi.l  #AMP_P,%d0               | displaced
        movea.l %d0,%a1
        movea.l 0x12a(%a1),%a0
        cmpi.l  #11,%d2
        bne     po_ae_out
        move.l  %d2,-(%sp)
        move.l  %d4,%d2
        bsr     po_amp_kind
        move.l  (%sp)+,%d2
        tst.l   %d0
        beq     po_ae_out
        lea     po_legknob(%pc),%a0
po_ae_out:
        jmp     0x4003ae4c

| ---- 0x4003af0a, the page-2 editor's live-lane write `lea 0x8000083c,%a0; moveb
| %d2,%a0@(0,%d0:l)` (10 bytes): d0 = track * 72 + slot, d2 = the value, d4 =
| track * 8, a2 = the slot. Slot 5 (LEG) of a synth track: the lane gets 0 (the
| DSP's byte), the Part and its shadow keep the value (stored above); a sample
| track's lane gets the value as stock writes it (the DSP sees it: measured
| harmless, README). The lane index d0 is kept across po_is_synth (3 Oct 2026:
| until then the flag replaced it, so the synth's clear and a sample track's
| store landed on track 1's lane bytes 1 / 0).
po_amplane:
        lea     0x8000083c,%a0           | displaced
        cmpa.l  #5,%a2
        bne     po_al_store
        move.l  %d2,-(%sp)
        move.l  %d0,-(%sp)               | (the lane index)
        move.l  %d4,%d2
        lsr.l   #3,%d2                   | the track
        bsr     po_is_synth              | (tst.l d0 done)
        beq     po_al_sample
        move.l  (%sp)+,%d0
        move.l  (%sp)+,%d2
        clr.b   (%a0,%d0.l)              | a synth track: the DSP's byte stays 0
        jmp     0x4003af14
po_al_sample:
        move.l  (%sp)+,%d0
        move.l  (%sp)+,%d2
po_al_store:
        move.b  %d2,(%a0,%d0.l)          | displaced
        jmp     0x4003af14

| ==== FINE DEFAULTS TO 0c WHEN A TRACK BECOMES A SYNTH TRACK (28 Sep 2026) =========
| Tim's report: a freshly assigned synth track came up with FINE +63c -- FINE is
| the stock RATE byte (PLAYBACK slot D; cents = raw - 64) and stock's RATE
| default is 127, so every Part, and every track that was a sample track, carries
| 127 there. The three stock sites that turn a track into a FLEX track of a given
| slot are detoured; at each, when the track IS a synth track after the write
| (machine FLEX, the FLEX column's slot a marker: po_slot_marker) and WAS NOT one
| before it (the machine was not FLEX, or the FLEX slot was not a marker), RATE
| := 64 is written into the Part's FLEX PLAYBACK bytes, their battery-RAM shadow
| and the live lane (po_fine_reset), so the page reads FINE 0c at once and SAVE
| keeps it. Nothing else is touched: a synth track's tuned FINE survives a
| re-assignment of the same or another marker slot, a project load, a Part
| reload, a pattern change and a warm boot (none of them run these sites); a
| sample track is never written (a non-marker slot is no synth track); RATE
| p-locks live in the pattern and are not read here.
|   * po_assign at 0x400795ba, in the slot assigner 0x40079424 (both windows'
|     apply paths call it when the slot differs): `addal #0x8f04a,%a0; moveb
|     %d1,%a0@` -- a0 = the Part's slot byte of the new machine (a3), d1 = the
|     new slot; the machine byte was written at 0x40079522 and the OLD machine
|     is the outermost of the three arguments still on the stack (0x4007956c:
|     old machine, track, part for 0x400972fc), 8(sp). The old slot of the new
|     machine's column is read before the displaced store.
|   * po_machwin at 0x40079816, the machine window's machine-only write
|     0x400797cc (the slot equal, the machine changed -- the assigner exits at
|     0x40079672 without writing): `addal #0x8eda2,%a0; mvsb %a0@,%d3` -- d3 :=
|     the old machine, d4 = the new one, d1 = the track; the FLEX column's slot
|     is the Part's (po_flex_slot).
|   * po_machlist at 0x4005a848, the sample-list window's machine-only write
|     0x4005a826, the same shape: `addal #0x8eda2,%a0; mvsb %a0@,%d4` -- d4 :=
|     the old machine, the new one at 0x460d5c30, d2 = the track.
| Not detoured: the paste of a copied track record (0x40027e4c kind 0, machine
| and slot with every page byte from the source, so FINE comes along) and the
| project / Part loaders (a saved Part keeps its bytes).

| ---- 0x400795ba: the slot assigner's slot-byte write (8 bytes displaced) --------
po_assign:
        adda.l  #SLOT_COL,%a0            | displaced: a0 = the Part's slot byte of the new machine
        mvz.b   (%a0),%d0                | the old slot in that column
        move.b  %d1,(%a0)                | displaced: the new slot
        lea     -16(%sp),%sp
        movem.l %d1-%d4,(%sp)           | 16 bytes: the assigner's arguments for 0x400972fc are at 16 + (0 part, 4 track, 8 old machine)
        move.l  %d0,%d3                  | old slot (of the new machine's column)
        move.l  %d1,%d4                  | new slot
        move.l  24(%sp),%d0              | the old machine
        move.l  20(%sp),%d2              | the track
        move.l  %a3,%d1                  | the new machine
        bsr     po_became
        movem.l (%sp),%d1-%d4
        lea     16(%sp),%sp
        jmp     ASSIGN_RET

| ---- 0x40079816: the machine window's machine-byte write (8 bytes displaced) ----
po_machwin:
        adda.l  #MACH_OFF,%a0            | displaced: a0 = the Part's machine byte
        mvs.b   (%a0),%d3                | displaced: the old machine
        lea     -24(%sp),%sp
        movem.l %d0-%d2/%d4/%a0-%a1,(%sp)
        move.l  %d3,%d0                  | old machine
        move.l  %d1,%d2                  | the track
        move.l  %d4,%d1                  | new machine
        moveq   #-1,%d3                  | the FLEX column's slot: the Part's (unchanged here)
        bsr     po_became
        movem.l (%sp),%d0-%d2/%d4/%a0-%a1
        lea     24(%sp),%sp
        mvs.b   (%a0),%d3                | (not written yet)
        .if     HK_MACHINE_ROWS
        move.b  %d4,(%a0)                | entered from the chain (fm_main_commit_hk): the head's
        add.l   %d1,%d0                  | detour spans 0x4007981c..0x40079822, so its two
        jmp     MACHWIN_RET+4            | instructions are replayed here
        .else
        jmp     MACHWIN_RET
        .endif

| ---- 0x4005a848: the sample-list window's machine-byte write (8 bytes displaced) -
po_machlist:
        adda.l  #MACH_OFF,%a0            | displaced: a0 = the Part's machine byte
        mvs.b   (%a0),%d4                | displaced: the old machine
        lea     -24(%sp),%sp
        movem.l %d0-%d3/%a0-%a1,(%sp)
        move.l  %d4,%d0                  | old machine
        move.l  LISTWIN_MACH,%d1         | new machine (the window's; d2 = the track already)
        moveq   #-1,%d3                  | the FLEX column's slot: the Part's
        bsr     po_became
        movem.l (%sp),%d0-%d3/%a0-%a1
        lea     24(%sp),%sp
        jmp     LISTWIN_RET

| ---- po_became: d0 = the old machine, d1 = the new one, d2 = the track, d3 = the
| FLEX column's old slot (-1: unchanged, read it from the Part), d4 = its new slot
| (with d3 >= 0). Resets FINE when the track is a synth track now and was not one
| before. Preserves every register.
po_became:
        lea     -40(%sp),%sp
        movem.l %d0-%d7/%a0-%a1,(%sp)
        subq.l  #1,%d1
        bne     po_bc_out                | not FLEX now: no synth track
        tst.l   %d3
        bpl     po_bc_slots
        bsr     po_flex_slot             | d3 := d4 := the Part's FLEX slot of track d2
po_bc_slots:
        move.l  %d0,%d7                  | old machine
        move.l  %d4,%d0
        bsr     po_slot_marker           | a synth track now?
        beq     po_bc_out
        subq.l  #1,%d7
        bne     po_bc_reset              | the machine changed to FLEX: it became one
        move.l  %d3,%d0
        bsr     po_slot_marker           | was one already (FLEX with a marker slot)?
        bne     po_bc_out                | its FINE is the user's
po_bc_reset:
        bsr     po_fine_reset
po_bc_out:
        movem.l (%sp),%d0-%d7/%a0-%a1
        lea     40(%sp),%sp
        rts

| ---- po_flex_slot: d3 := d4 := the Part's FLEX-column slot byte of track d2
| (clobbers a0, d3, d4).
po_flex_slot:
        movea.l PART_PTR,%a0
        mvz.b   PART_IDX,%d3
        move.l  #6322,%d4
        muls.l  %d4,%d3
        adda.l  %d3,%a0                  | the Part
        move.l  %d2,%d3
        lsl.l   #2,%d3
        add.l   %d2,%d3                  | track * 5
        adda.l  %d3,%a0
        adda.l  #SLOT_OFF,%a0
        mvz.b   (%a0),%d3
        move.l  %d3,%d4
        rts

| ---- po_fine_reset: RATE := 1 (FOLD ~off; never 0 -- stock RATE 0 can stall) for track d2.
| Part FLEX PLAYBACK byte, shadow, live lane. Preserves every register.
po_fine_reset:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        movea.l PART_PTR,%a0
        mvz.b   PART_IDX,%d0
        move.l  #6322,%d1
        muls.l  %d1,%d0                  | part * 6322
        move.l  %d2,%d1
        lsl.l   #5,%d1
        sub.l   %d2,%d1
        sub.l   %d2,%d1                  | track * 30
        add.l   %d0,%d1
        addi.l  #PLAY_SLOTS+6+CV_RATE,%d1 | + FLEX (machine 1) * 6 + slot D
        moveq   #1,%d0
        move.b  %d0,(%a0,%d1.l)          | the Part (FOLD ~off; not 0)
        lea     PART_SHADOW,%a1
        move.b  %d0,(%a1,%d1.l)          | its shadow
        move.l  #CV_STRIDE,%d1
        muls.l  %d2,%d1
        lea     CURVALS,%a0
        move.b  %d0,CV_RATE(%a0,%d1.l)   | the live lane
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        rts

| ---- 0x40022686: the file browser's select (0x40022610: d4 = the machine, 1 =
| FLEX, d3 = the slot, d5 = the chosen file's path, d2 = the slot's settings
| record; the three sprintf arguments record / format / path are on the stack)
| writes the path into the record with `jsr 0x40013a08`, replaced by `jsr
| po_loadsel`. THE NEW-PROJECT CASE (Tim, MKI, 2.9 + the FINE fix: the FIRST
| FM machine of a project read +63c): in a fresh project every track already
| owns its slot in both columns (T1 = slot 1 .. T8 = slot 8, every slot empty;
| the port boots them STATIC), so the first marker goes INTO the track's own slot -- the machine window's YES on that
| slot takes the assigner's same-slot exit (0x40079672 -> 0x40021d94 -> the
| browser, and again after the load), the sample-list window's LOAD FILE never
| touches the Part: the machine and the slot byte do not change, none of the
| three assigner sites runs, and the track has become a synth track by its
| slot's FILE changing. So the change of a FLEX slot's file is the fourth site:
| the slot's marker state is read before the path write and after it, and when
| it went non-marker (or empty) -> marker, every FLEX track whose FLEX slot is
| this slot became a synth track: RATE := 64 for each (po_fine_reset). A marker
| replaced by a marker changes nothing (its synth tracks keep their FINE), a
| marker replaced by a sample, a STATIC slot, a recorder buffer: nothing.
po_loadsel:
        lea     -12(%sp),%sp
        movem.l %d2/%d6-%d7,(%sp)        | 12 B: the return address at 12(sp), the arguments at 16 / 20 / 24
        moveq   #0,%d7
        moveq   #1,%d0
        cmp.l   %d4,%d0
        bne     po_ls_call               | not the FLEX list
        move.l  %d3,%d0
        bsr     po_slot_marker
        move.l  %d0,%d7                  | d7 := the slot's file WAS a marker
po_ls_call:
        move.l  24(%sp),-(%sp)           | the path
        move.l  24(%sp),-(%sp)           | the format
        move.l  24(%sp),-(%sp)           | the record
        jsr     LOADSEL_SPRINTF          | stock: the path into the record
        lea     12(%sp),%sp
        moveq   #1,%d0
        cmp.l   %d4,%d0
        bne     po_ls_out
        tst.l   %d7
        bne     po_ls_out                | a marker already: its synth tracks keep their FINE
        move.l  %d3,%d0
        bsr     po_slot_marker
        beq     po_ls_out                | not a marker now: no synth track
        move.l  %d3,%d6                  | the slot
        moveq   #0,%d2                   | the track
po_ls_track:
        movea.l PART_PTR,%a0
        mvz.b   PART_IDX,%d0
        move.l  #6322,%d1
        muls.l  %d1,%d0
        adda.l  %d0,%a0                  | the Part
        move.l  %d2,%d0
        addi.l  #MACH_OFF,%d0
        mvz.b   (%a0,%d0.l),%d0
        subq.l  #1,%d0
        bne     po_ls_next               | not FLEX
        move.l  %d2,%d0
        lsl.l   #2,%d0
        add.l   %d2,%d0
        addi.l  #SLOT_OFF,%d0
        mvz.b   (%a0,%d0.l),%d0          | its FLEX slot
        cmp.l   %d6,%d0
        bne     po_ls_next
        bsr     po_fine_reset            | d2 = the track: FINE 0c (preserves every register)
po_ls_next:
        addq.l  #1,%d2
        moveq   #8,%d0
        cmp.l   %d2,%d0
        bne     po_ls_track
po_ls_out:
        movem.l (%sp),%d2/%d6-%d7
        lea     12(%sp),%sp
        rts

| ---- data ----------------------------------------------------------------------
sy_name:
        .ascii  "CXOSC"
po_chrd:
        .ascii  "CHRD\0\0"
po_voic:
        .ascii  "VOIC\0\0"
po_leg:
        .ascii  "LEG\0\0\0"
po_legnames:                             | 8 bytes each, NUL-ended
        .ascii  "OFF\0\0\0\0\0" "MONO\0\0\0\0" "POLY\0\0\0\0"
po_f_s:
        .asciz  "%s"
po_f_d:
        .asciz  "%d"
        .align  2

| ---- free RATO: raw 0..127 <-> Q8 0.25..4 (q8 = 64 + raw * 960 / 127) ----
| At a FUNC snap's rounded raw, return the EXACT classic Q8 (else free map
| prints 0.98 for 1, 2.99 for 3). sy_rato_snap_raw mirrors sy_rato_snap.
| sy_rato_q8: d1 := Q8 from raw d1 (0..127). Clobbers d0, a0.
sy_rato_q8:
        lea     sy_rato_snap_raw(%pc),%a0
        moveq   #0,%d0
sy_rq_hit:
        cmp.b   (%a0,%d0.l),%d1
        beq     sy_rq_exact
        addq.l  #1,%d0
        cmpi.l  #KN_RATO_SNAPS,%d0
        bcs     sy_rq_hit
        move.l  %d1,%d0                  | free map
        move.l  #KN_RATO_SPAN,%d1
        mulu.l  %d1,%d0
        move.l  #KN_RATO_MAX,%d1
        divu.l  %d1,%d0
        addi.l  #64,%d0
        move.l  %d0,%d1
        rts
sy_rq_exact:
        lea     sy_rato_snap(%pc),%a0
        mvz.w   (%a0,%d0.l*2),%d1        | classic Q8
        rts

| sy_rato_raw: d0 := nearest raw 0..127 for target Q8 d0 (rounded). Clobbers d1.
sy_rato_raw:
        subi.l  #64,%d0
        bpl     sy_rr_ok
        moveq   #0,%d0
        rts
sy_rr_ok:
        move.l  #KN_RATO_MAX,%d1
        mulu.l  %d1,%d0                  | (q8 - 64) * 127
        addi.l  #KN_RATO_HALF,%d0        | + SPAN/2: round to nearest
        move.l  #KN_RATO_SPAN,%d1
        divu.l  %d1,%d0
        cmpi.l  #KN_RATO_MAX,%d0
        bls     sy_rr_out
        move.l  #KN_RATO_MAX,%d0
sy_rr_out:
        rts

| FUNC+RATO snap targets: classic FM ratios <= 4.01 (Q8) + their rounded raws.
sy_rato_snap:
        .short  64, 128, 192, 256, 259, 320, 362, 384      | 0.25 0.5 0.75 1 1.01 1.25 1.41 1.5
        .short  448, 512, 515, 640, 768, 896, 1024, 1027   | 1.75 2 2.01 2.5 3 3.5 4 4.01
sy_rato_snap_raw:
        .byte   0, 8, 17, 25, 26, 34, 39, 42
        .byte   51, 59, 60, 76, 93, 110, 127, 127
        .align  2

| ---- the chord shapes: CHRD raw >> 2 -> four semitone offsets, a VOICING ----
| 32 shapes in FOUR PASSES (OCTATRICK2.8, Tim's order after Elektron's
| Syntakt convention: the common chords first, the intervals last): row 0
| the single note; pass one the triads MIN MAJ SU2 SU4; pass two the
| sevenths and adds MI7 DO7 MA7 7S4 DI7 AD2 MD2 AD9 MI6 MA6; pass three the
| rest M75 DIM AUG MI9 DO9 MA9 M69 QUA; pass four the two-note intervals
| 4TH 5TH OCT 3MI 3MA 7MI 7MA (digit-first names) and the spreads MAS MIS.
| The notes of every row are the 2.7 table's; only the positions moved, so a
| CHRD byte saved by 2.7 or earlier (a knob setting, a lock) names another
| shape in 2.8 -- the row numbers below are 2.8's. The CHRD byte's low two
| bits are the INVERSION (26 Sep 2026: raw = shape << 2 | inversion, one a
| detent, so the knob walks MIN MIN1 MIN2 MIN3 MAJ ...; a knob-set byte of an
| older pattern has 0 there = the root position). Every shape but "----"
| has FOUR notes in PRIORITY ORDER: the shape's own notes first -- the root,
| then the note that names the shape (the 7th of a MA7, the 6th of a MA6,
| the b5 of a DIM, the 9th of an AD9, the 2nd of an AD2), then the 3rd,
| then the 5th; the ninths keep their 7th before the 3rd (a 9th chord at
| VOIC 3 is root, 9th, 7th) -- then octave doublings until four. The engine
| plays the VOICING of (shape, inversion) for VOIC notes (po_voicing: the
| notes by pitch, rotated so the inversion's note is the bass = PTCH, the
| notes below it an octave up, the doublings octaves of the rotated notes,
| then the VOIC notes of the highest priority), so VOIC 2 plays two notes of
| every shape, VOIC 3 three, VOIC 4 four; the recogniser tries every (shape,
| inversion) voicing against the played keys (po_match: among equal
| voicings the shape with the FEWEST distinct notes wins, then table order
| -- C F is 4TH, not SU4's first two notes). "----" is the one note
| (SHAPE_END after it) and VOIC is the keyboard polyphony there. Nothing
| else reads a shape in order: po_snap snaps each note alone, the CHRD
| formatter prints the name and the inversion.
po_shapes:
        .byte   0, -128, -128, -128     |  0 ----  a single note
        .byte   0, 3, 7, 12             |  1 MIN   root, b3, 5th, + the root's octave      (pass one: the triads)
        .byte   0, 4, 7, 12             |  2 MAJ   root, 3rd, 5th, + octave
        .byte   0, 2, 7, 12             |  3 SU2   root, 2nd, 5th, + octave
        .byte   0, 5, 7, 12             |  4 SU4   root, 4th, 5th, + octave
        .byte   0, 10, 3, 7             |  5 MI7   root, b7, b3, 5th                        (pass two: sevenths, adds, sixths)
        .byte   0, 10, 4, 7             |  6 DO7   root, b7, 3rd, 5th
        .byte   0, 11, 4, 7             |  7 MA7   root, 7th, 3rd, 5th
        .byte   0, 5, 10, 7             |  8 7S4   7sus4: root, 4th, b7, 5th
        .byte   0, 6, 3, 9              |  9 DI7   root, b5, b3, bb7
        .byte   0, 2, 4, 7              | 10 AD2   add2: root, 2nd, 3rd, 5th
        .byte   0, 2, 3, 7              | 11 MD2   minor add2: root, 2nd, b3, 5th
        .byte   0, 14, 4, 7             | 12 AD9   root, 9th, 3rd, 5th
        .byte   0, 9, 3, 7              | 13 MI6   root, 6th, b3, 5th
        .byte   0, 9, 4, 7              | 14 MA6   root, 6th, 3rd, 5th
        .byte   0, 10, 6, 3             | 15 M75   m7b5: root, b7, b5, b3                   (pass three: the rest)
        .byte   0, 6, 3, 12             | 16 DIM   root, b5, b3, + octave
        .byte   0, 8, 4, 12             | 17 AUG   root, #5, 3rd, + octave
        .byte   0, 10, 14, 3            | 18 MI9   minor 9th: root, b7, 9th, b3
        .byte   0, 10, 14, 4            | 19 DO9   dominant 9th: root, b7, 9th, 3rd
        .byte   0, 11, 14, 4            | 20 MA9   major 9th: root, 7th, 9th, 3rd
        .byte   0, 9, 14, 4             | 21 M69   6/9: root, 6th, 9th, 3rd
        .byte   0, 5, 10, 15            | 22 QUA   quartal: stacked fourths
        .byte   0, 5, 12, 17            | 23 4TH   root, 4th, + the octave of each         (pass four: intervals and spreads)
        .byte   0, 7, 12, 19            | 24 5TH   root, 5th, + the octave of each
        .byte   0, 12, 24, 36           | 25 OCT   octaves
        .byte   0, 3, 12, 15            | 26 3MI   minor third, doubled
        .byte   0, 4, 12, 16            | 27 3MA   major third, doubled
        .byte   0, 10, 12, 22           | 28 7MI   minor seventh (the interval), doubled
        .byte   0, 11, 12, 23           | 29 7MA   major seventh (the interval), doubled
        .byte   0, 7, 16, 12            | 30 MAS   major spread: root, fifth, tenth, + octave
        .byte   0, 7, 15, 12            | 31 MIS   minor spread, + octave
po_names:                                | 4 bytes each: the name, at most three characters, NUL-padded (the inversion digit follows it)
        .ascii  "----" "MIN\0" "MAJ\0" "SU2\0" "SU4\0" "MI7\0" "DO7\0" "MA7\0"
        .ascii  "7S4\0" "DI7\0" "AD2\0" "MD2\0" "AD9\0" "MI6\0" "MA6\0" "M75\0"
        .ascii  "DIM\0" "AUG\0" "MI9\0" "DO9\0" "MA9\0" "M69\0" "QUA\0" "4TH\0"
        .ascii  "5TH\0" "OCT\0" "3MI\0" "3MA\0" "7MI\0" "7MA\0" "MAS\0" "MIS\0"
        .align  2

| ---- po_gmax: VOIC -> a voice's full gain, Q15 = 32768 / sqrt(VOIC) (29 Sep 2026) ----
| Equal power: a chord of n uncorrelated notes has the mono voice's power, a
| single note is -3.0 / -4.8 / -6.0 dB at VOIC 2 / 3 / 4 (1/VOIC was -6 / -9.5
| / -12); po_fill's limiter holds the sum at the mono voice's full scale. Index 0 unused.
po_gmax:
        .long   32768, 32768, 23170, 18919, 16384

| ---- po_atk: AMP ATK raw -> the attack step a frame, Q15 (full = 32768) ----------
| The DSP's attack as measured (stage 1, root29o/ana_env.txt): a LINEAR ramp to
| full in t = 3.85 ms x 2^(ATK / 8.53) (8: 7.5 ms, 16: 15, 32: 50, 64: 700, 96:
| 9.45 s); step = 32768 / max(16, t / 0.3628 ms) a frame -- the 16-frame ramp
| (5.8 ms, ATK 0..8) is the floor, and the Q15 step's floor of 1 makes ATK >= 91
| an 11.9 s ramp (the DSP's 96 is 9.5 s, its 127 anomalous). root29p/gen_env_tables.py.
po_atk:
        .short  2048, 2048, 2048, 2048, 2048, 2048, 1896, 1748
        .short  1612, 1486, 1370, 1263, 1165, 1074, 990, 913
        .short  841, 776, 715, 659, 608, 560, 517, 476
        .short  439, 405, 373, 344, 317, 293, 270, 249
        .short  229, 211, 195, 180, 166, 153, 141, 130
        .short  120, 110, 102, 94, 86, 80, 74, 68
        .short  62, 58, 53, 49, 45, 42, 38, 35
        .short  33, 30, 28, 26, 24, 22, 20, 18
        .short  17, 16, 14, 13, 12, 11, 10, 10
        .short  9, 8, 8, 7, 6, 6, 5, 5
        .short  5, 4, 4, 4, 3, 3, 3, 3
        .short  2, 2, 2, 2, 2, 2, 1, 1
        .short  1, 1, 1, 1, 1, 1, 1, 1
        .short  1, 1, 1, 1, 1, 1, 1, 1
        .short  1, 1, 1, 1, 1, 1, 1, 1
        .short  1, 1, 1, 1, 1, 1, 1, 1

| ---- po_relk: AMP REL raw -> the release k, Q16 per frame ---------------------
| gain -= gain * k: the DSP's release as measured (stage 1): EXPONENTIAL with
| tau = 0.295 ms x 2^(REL / 8.53) (40: 7.6 ms, 60: 38.5, 80: 196, 100: 994,
| 126: 9 s), 127 = INF (k = 0); tau is floored at 1 ms (REL 0..15) -- the DSP's
| REL 0 is a one-sample dead cut (Tim's click), the engine's is -20 dB in 2.3 ms,
| -40 dB in 4.6 ms. (Until plan B: tau = 5 ms x 1000^(rel / 126), 134 ms at REL
| 60 where the DSP takes 38.) root29p/gen_env_tables.py.
po_relk:
        .short  19941, 19941, 19941, 19941, 19941, 19941, 19941, 19941
        .short  19941, 19941, 19941, 19941, 19941, 19941, 19941, 19941
        .short  18661, 17419, 16245, 15137, 14093, 13112, 12190, 11327
        .short  10518, 9762, 9055, 8396, 7781, 7209, 6676, 6180
        .short  5719, 5292, 4894, 4526, 4184, 3868, 3574, 3302
        .short  3051, 2818, 2602, 2403, 2219, 2048, 1891, 1745
        .short  1611, 1486, 1372, 1266, 1168, 1077, 994, 917
        .short  846, 780, 720, 664, 612, 565, 521, 480
        .short  443, 408, 377, 347, 320, 295, 272, 251
        .short  232, 214, 197, 182, 167, 154, 142, 131
        .short  121, 112, 103, 95, 87, 81, 74, 69
        .short  63, 58, 54, 50, 46, 42, 39, 36
        .short  33, 30, 28, 26, 24, 22, 20, 19
        .short  17, 16, 15, 13, 12, 11, 11, 10
        .short  9, 8, 8, 7, 6, 6, 6, 5
        .short  5, 4, 4, 4, 3, 3, 3, 0

| ---- po_hold128: the AMP HOLD byte -> steps in 1/128 (the firmware's own table of
| strings at 0x400d18d0: 0.0078 .. 128.0, 127 = INF), the sequencer note's gate ----
po_hold128:
        .short  1, 1, 2, 3, 4, 6, 8, 11
        .short  16, 23, 32, 45, 64, 91, 128, 136
        .short  144, 152, 160, 168, 176, 184, 192, 200
        .short  208, 216, 224, 232, 240, 248, 256, 272
        .short  288, 304, 320, 336, 352, 368, 384, 400
        .short  416, 432, 448, 464, 480, 496, 512, 544
        .short  576, 608, 640, 672, 704, 736, 768, 800
        .short  832, 864, 896, 928, 960, 992, 1024, 1088
        .short  1152, 1216, 1280, 1344, 1408, 1472, 1536, 1600
        .short  1664, 1728, 1792, 1856, 1920, 1984, 2048, 2176
        .short  2304, 2432, 2560, 2688, 2816, 2944, 3072, 3200
        .short  3328, 3456, 3584, 3712, 3840, 3968, 4096, 4352
        .short  4608, 4864, 5120, 5376, 5632, 5888, 6144, 6400
        .short  6656, 6912, 7168, 7424, 7680, 7936, 8192, 8704
        .short  9216, 9728, 10240, 10752, 11264, 11776, 12288, 12800
        .short  13312, 13824, 14336, 14848, 15360, 15872, 16384, 65535

| ---- the sine table: 256 + 1 entries, s16, amplitude 0x4000 ---------------
        .balign 4
sy_tab:
        .short  0, 402, 804, 1205, 1606, 2006, 2404, 2801
        .short  3196, 3590, 3981, 4370, 4756, 5139, 5520, 5897
        .short  6270, 6639, 7005, 7366, 7723, 8076, 8423, 8765
        .short  9102, 9434, 9760, 10080, 10394, 10702, 11003, 11297
        .short  11585, 11866, 12140, 12406, 12665, 12916, 13160, 13395
        .short  13623, 13842, 14053, 14256, 14449, 14635, 14811, 14978
        .short  15137, 15286, 15426, 15557, 15679, 15791, 15893, 15986
        .short  16069, 16143, 16207, 16261, 16305, 16340, 16364, 16379
        .short  16384, 16379, 16364, 16340, 16305, 16261, 16207, 16143
        .short  16069, 15986, 15893, 15791, 15679, 15557, 15426, 15286
        .short  15137, 14978, 14811, 14635, 14449, 14256, 14053, 13842
        .short  13623, 13395, 13160, 12916, 12665, 12406, 12140, 11866
        .short  11585, 11297, 11003, 10702, 10394, 10080, 9760, 9434
        .short  9102, 8765, 8423, 8076, 7723, 7366, 7005, 6639
        .short  6270, 5897, 5520, 5139, 4756, 4370, 3981, 3590
        .short  3196, 2801, 2404, 2006, 1606, 1205, 804, 402
        .short  0, -402, -804, -1205, -1606, -2006, -2404, -2801
        .short  -3196, -3590, -3981, -4370, -4756, -5139, -5520, -5897
        .short  -6270, -6639, -7005, -7366, -7723, -8076, -8423, -8765
        .short  -9102, -9434, -9760, -10080, -10394, -10702, -11003, -11297
        .short  -11585, -11866, -12140, -12406, -12665, -12916, -13160, -13395
        .short  -13623, -13842, -14053, -14256, -14449, -14635, -14811, -14978
        .short  -15137, -15286, -15426, -15557, -15679, -15791, -15893, -15986
        .short  -16069, -16143, -16207, -16261, -16305, -16340, -16364, -16379
        .short  -16384, -16379, -16364, -16340, -16305, -16261, -16207, -16143
        .short  -16069, -15986, -15893, -15791, -15679, -15557, -15426, -15286
        .short  -15137, -14978, -14811, -14635, -14449, -14256, -14053, -13842
        .short  -13623, -13395, -13160, -12916, -12665, -12406, -12140, -11866
        .short  -11585, -11297, -11003, -10702, -10394, -10080, -9760, -9434
        .short  -9102, -8765, -8423, -8076, -7723, -7366, -7005, -6639
        .short  -6270, -5897, -5520, -5139, -4756, -4370, -3981, -3590
        .short  -3196, -2801, -2404, -2006, -1606, -1205, -804, -402
        .short  0

| ---- state (RAM) ---------------------------------------------------------------
        .align  4
sy_state:                                | 8 tracks x 128 bytes
        .fill   8 * ST_STRIDE, 1, 0
sy_cxparm:                               | 8 tracks x (FOLD, SYMM) -- off the 128 B record (S_ISTEP owns +126)
        .fill   16, 1, 0
po_voices:                               | 8 tracks x 4 voices x 64 bytes
        .fill   8 * 4 * V_STRIDE, 1, 0
po_seq:                                  | the allocation stamp
        .long   0
po_chord:                                | 8 tracks x 32 bytes: the fingered chord being recorded (po_keyrec / po_keyrel)
        .fill   8 * CR_STRIDE, 1, 0
po_vbuf:                                 | the voicing of a start (po_start1 -> po_voicing, the audio frame's)
        .fill   4, 1, 0
po_mheld:                                | 8 tracks x 8 bytes: the MIDI notes held (0x80 | note, press order, 0 = empty; po_mon / po_moff)
        .fill   64, 1, 0
po_mring:                                | 8 tracks x 8 entries of (identity, raw): note-ons pending a START (po_mon -> po_start)
        .fill   128, 1, 0
po_mhead:                                | the ring's head (the engine's) ...
        .fill   8, 1, 0
po_mtail:                                | ... and tail (the note-on's), per track
        .fill   8, 1, 0
po_clock:                                | the sequencer clock (po_tick), read by the quantizer through qz_clock
        .long   0, 0, FPS_DEFAULT, 0, -1, -1, -1, 0
po_rtlog:                                | po_retrig's counters and ring (po_clock + 32; the rig peeks it)
        .fill   RT_SIZE, 1, 0
po_lfo_built:
        .byte   0
        .align  4
po_lfodesc:                              | the LFO descriptor clone (built on first use)
        .fill   LFO_DESC_LEN, 1, 0
po_pg_built:
        .byte   0
        .align  4
po_pgdesc_buf:                           | the FM SYNTH PLAYBACK descriptor clone for page.s (built on first use)
        .fill   FLEX_DESC_LEN, 1, 0
po_amp_built:
        .byte   0
        .align  4
po_ampdesc_buf:                          | the AMP descriptor clone with LEG in slot 11 (built on first use, po_amp_desc)
        .fill   AMP_DESC_LEN, 1, 0
        .align  4
po_end:
