| ============================================================================
| OCTA303 v6.7.2 (dEVILish) -- DRAM unit: a TB-303 voice on a FLEX track (GNU as; DRAM units: -mcpu=54455)
|
| VCO   saw (phase accumulator, polyBLEP) or square (duty by pitch, v6.6), coupling highpass (v6.7: 149 Hz)
| VCF   TB-303 diode ladder: four coupled stages, bottom capacitor halved (k_osc = 17 in the
|       analogue limit), coefficients solved numerically per 1/4 semitone so the resonance sits
|       on the cutoff; soft clip at the ladder input; highpass inside the resonance loop (v6.7: 45 Hz)
| ENV   MEG (3 ms attack, Decay pot 0.10..2.35 s at -20 dB, accent forces the minimum), ENV MOD;
|       v6.7: every pot law, KF / LG (resonance and level by cutoff) and ACC_AMT fitted to
|       Din Sync's TB-303 recordings (tools/octa303/o3tables.py, CAL),
|       VEG (long, fixed), accent VCA path (47k * 0.033 uF), Whittle's accent-sweep capacitor
| SLIDE RC slew on the pitch CV (103.3k * 0.22 uF = 22.7 ms), driven by trigless PTCH locks
| TUNE  (v6.4) semitones, -24..+24 (v6.5c): four octaves, 0 in the middle (Tim Hastie's tuning system); the
|       CHROMATIC keys follow (o3_chrom)
| dEVILish (v6.3): a 303 track whose FX1 or FX2 is the dEVILish module reads its twelve knobs
|       (Robin Whittle's Devil Fish: OVDR FM TRCK VDEC SLID ADEC / SATK SWP SPD MUFF CUTX ENVX)
|       from that slot's live lane; every other 303 track reads O3_DF_NEUTRAL, which is v6.1.1
|       sample for sample.  The LFO page is stock again.
| DIST  optional (SETUP's WAVE +D): a fixed pedal after the VCA -- gain, asymmetric
|       soft clip, 6 kHz tone -- the London acid-techno treatment.  The plain carriers are pure.
|
| WHICH TRACKS: the TB-303 machine (v7.0, a signed FLEX track; see "THE TB-303 MACHINE" below),
| decided at the voice START.  v7.9: the older way in, a FLEX track whose sample is named TB303*,
| is gone; such a track is an ordinary FLEX track.  Every other track is the stock renderer's,
| byte for byte.
|
| THE CALL (Tim Hastie's poly.s 2.9, sy_render): sy_render(track, ping, start, end) replaces
| the kind table's FLEX entry; the packer calls it once a 16-sample frame, twice when a START
| splits the frame ([0,n) then [n,16)); the stock renderer is called every time with the four
| arguments and its return value is handed back.  On the frame's last call (end == 16) of an
| OCTA303 track the record's PTCH and RATE words are set to 0x4000 / 0x7f00 (0 semitones,
| rate 1.0: the DSP's resampler is an identity) and the voice's sample positions are saved,
| both restored after the stock call (the carrier never ends); at the START the packer's
| latched retrig count is cleared (DEC sits in the RTRG slot).  Then the 303 overwrites the
| samples the stock call shipped (header byte 3 = how many, L/R longs from +16).
| o3_retrig (detour 0x4000c634, Tim's po_retrig): a START on a sounding OCTA303 track is
| posted as the clean 0x30 so the DSP does not crossfade the one continuous stream with
| itself (+5.6 dB at every trig, measured by Tim).  o3_page (detour 0x40031ece): the
| machine's pages are a runtime clone of the stock FLEX record (o3_mdesc).
|
| CPU (v6.x): per-sample multiplies are ((x >> pre) * c) >> post -- one muls.l and two shifts --
| the per-sample code is inline, constants are read through %a5, control runs every 16 samples.
|
| The integer arithmetic is mirrored line for line by tools/octa303/ref303.py and
| tools/octa303/sim/test_octa303.py requires bit-identical output.  Change both or neither.
| Integration follows Tim Hastie's SYNTH MACHINE 2.9 (timhastie/octatrick-modules, MIT).
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
        .set    PART_SIZE,      6322
        .set    FLEX_P,         0x400d31ae      | the stock FLEX PLAYBACK descriptor (P form)
        .set    FLEX_DESC_LEN,  0x192
        .set    O3_DLEN,        0x194           | v7.0: o3_desc, the machine's record (v7.9: the only one)
        .set    PART_OFF,       0x8ed80         | v7.0: the bank blob's Part 0 (Part' = BANK + this + part * 6322)
        .set    LANE_SETUP,     0x20            | v7.0: the live lane's SETUP bytes (+0x20..+0x25)
        .set    RESOLVER_RET,   0x40031ed6      | the page resolver after its table load (o3_page)
        .set    RETRIG_RET,     0x4000c63c      | the frame builder after its command-byte copy (o3_retrig)
        .set    FMT_PLAIN,      0x4003c178      | stock fmt(buf, value) -> "%d"
        .set    SPRINTF,        0x40013a08      | v6.4: the firmware's sprintf (modules/synth page.s)
        .set    FMT_D,          0x400b465d      | its "%d"
        .set    BANK_PTR,       0x46c82456      | the bank blob pointer (quantizer.s qz_is_synth)
        .set    PART_IDX,       0x100b14cf      | the current part
        .set    MACH_OFF,       0x8eda2         | Part + 0x8eda2 + track: the machine (1 = FLEX)
        .set    STEPW,          0x800065b2      | v6.5: the sequencer's step word (u16; Euclacid's LIVE, poly.s po_clock)
        .set    TICKB,          0x800065b6      | its tick byte (0..5 a step at 1x)
        .set    TRANSPORT,      0x800065b8      | v7.4: 1 = the sequencer running (STEM_REC.md; measured under the port)
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

| ---- per-track state (longs), mostly in ref303.FIELDS' order (v7.8's S_Y27 appended); 512 bytes a track
        .set    S_LATCHED,0
        .set    S_WAVE,4
        .set    S_DIST,8
        .set    S_PHASE,12
        .set    S_INC,16
        .set    S_PCUR,20
        .set    S_CS,24
        .set    S_MEG,28
        .set    S_MEGS,32
        .set    S_VEG,36
        .set    S_ACCD,40
        .set    S_ACCI,44                       | v7.8: ACCENT raw (VR7's position; the circuit's tables)
        .set    S_V34,48                        | v7.8: C36's voltage, uV (the accent's VCA path)
        .set    S_DVC,52                        | v7.8: C13's voltage above N134, uV (the accent's push)
        .set    S_AMP,56
        .set    S_AMPSTEP,60
        .set    S_HP,64
        .set    S_Y1,68
        .set    S_Y2,72
        .set    S_Y3,76
        .set    S_Y4,80
        .set    S_FB,84
        .set    S_DC,88
        .set    S_TONE,92
        .set    S_C1,96
        .set    S_B,100
        .set    S_K,104
        .set    S_GCOMP,108
        .set    S_PTGT,112
        .set    S_CUT,116
        .set    S_RES,120
        .set    S_ENV,124
        .set    S_DEC,128
        .set    S_GIN,132
        .set    S_VEGD,136
        .set    S_VSUS,140
        .set    S_TRKHZ,144
        .set    S_FMQ,148
        .set    S_SCTRL,152
        .set    S_KMUL,156
        .set    S_OVCA,160
        .set    S_OCOMP,164
        .set    S_OGAIN,168
        .set    S_SLIDE,172
        .set    S_SWP,176
        .set    S_ADEC,180
        .set    S_SATK,184
        .set    S_VATT,188
        .set    S_SPD,192
        .set    S_MUFF,196
        .set    S_MLO,200
        .set    S_CUTX,204
        .set    S_ENVX,208
        .set    S_GINQ15,212
        .set    S_NZ,216
        .set    S_WPTCH,220
        .set    S_WRATE,224
        .set    S_POS,228                       | +228..+247: the voice's positions
        .set    S_GMODE,248                     | v6.5, the 303's gate (ref303.gate_frame): on (HOLD INF)
        .set    S_GATE,252                      | the gate: 1 open
        .set    S_GLVL,256                      | its level, Q15 (3 ms edges)
        .set    S_GSTEP,260                     | the step whose half closes it
        .set    S_LSTEP,264                     | the sequencer's step / tick last frame
        .set    S_LTICK,268
        .set    S_IDLE,272                      | frames without a step/tick change
        .set    S_KMAX,276                      | the largest tick of this step
        .set    S_TPS,280                       | ticks a step (measured)
        .set    S_GNEW,284                      | a 303 START since the last gate frame
        .set    S_GEL,288                       | v6.5d: ticks since the START
        .set    S_GEND,292                      | close at 2 * S_GEL >= S_GEND (tps, + 2 tps a tie)
        .set    S_SQTP,296                      | v7.6: Q8's square: this semitone's row of O3_SQC (an address)
        .set    S_DFK,300                       | v7.1: dEVILish page 1 as the DSP gets it (6 bytes, o3_vrec)
        .set    S_UD,308                        | v6.9: the ring's decay by RES, dB/ms Q10 (O3_TB_UD), for FM's per-sample k
        .set    S_SQK,312                       | v7.6: Q8's square: the hard edge, times the saw (Q15, O3_SQK)
        .set    S_ACCVG,316                     | v7.0: the accent VCA gain (ACCV)
        .set    S_OSIN,320                      | v7.0: the output stage's input gain (DRIV)
        .set    S_OSLIM,324                     | v7.0: its clamp (v7.7: unused, kept for the layout)
        .set    S_FINE,328                      | v7.0: FINE, Q8 semitones
        .set    S_CUTB,332                      | v7.0: the cutoff base, smoothed (Q16)
        .set    S_ENVS,336                      | v7.0: the env depth, smoothed (Q16)
        .set    S_SMOK,340                      | v7.0: the two above are live
        .set    S_GSEL,344                      | v7.0: SETUP's GATE (0 OFF, 1 303)
        .set    S_FCNT,348                      | v7.0: frames since the sequencer last moved
        .set    S_FPT,352                       | v7.0: frames a tick (0: not yet measured)
        .set    S_FSEEN,356                     | v7.0: a move seen (FCNT is a whole interval)
        .set    S_GELF,360                      | v7.0: frames since the START
        .set    S_MACH,364                      | v7.0: the track is the TB-303 machine (signed FLEX)
        .set    S_CLG,368                       | v7.3: the ladder clip's gain g (Q12), 0 = the plain soft clip
        .set    S_CLI,372                       | v7.3: 1/g (Q12)
        .set    S_CLL,376                       | v7.3: the clamp before * g (+-sqrt2 / g)
        .set    S_FSKIP,380                     | v7.4: gate: tick intervals still to skip after a stop
        .set    S_STOPD,384                     | v7.4: gate: a STOP seen (transport word not 1)
        .set    S_VP1,388                       | v7.4: the VCA input pair: R121/C21's high-pass state
        .set    S_VP2,392                       | v7.4: R122/C22's
        .set    S_W2,396                        | v7.4: the RES path's weight (Q12), OVDR applied
        .set    S_FBO,400                       | v7.4: this sample's high-passed ladder output
        .set    S_SQL,404                       | v7.6: the square's edge lowpass state (as v6.9)
        .set    S_Y27,408                       | v7.8: I27 x R27, uV (D27 into pin 1)
        .set    S_FAB,412                       | v7.9: WAVE's R, the factory preset (TM3_FAB on the cutoff)
| v8.2 P11 (from v8.1 517daa36): the VCA closed -> the chain after it at its fixed point is not recomputed.
        .set    S_P11,416                       | 0 = unknown, -1 = the sample before tried, 1 = the fixed point holds
        .set    S_P11OUT,420                    | the output word the fixed point gives (both channels)
        .set    S_P11A,424                      | S_DC before the try
        .set    S_P11B,428                      | S_MLO before it
        .set    S_P11C,432                      | S_TONE before it
| v8.2 P2 (from v8.1 dda993a9): o3_ctrl / o3_params skip the work whose inputs are the last step's (pure functions
| of them: bit for bit).  v7.9's GCOMP reads O3_LG by the cutoff, so its cache (v8.1's S_P2G*) does not apply here.
        .set    S_P2PV,436                      | 1: the three keys below are a step that left PCUR where it was
        .set    S_P2PT,440                      | PTGT, PCUR and SLIDE of that step
        .set    S_P2PC,444
        .set    S_P2PS,448
        .set    S_P2EK,452                      | the env-mod depth's key: ENV | RES << 8 | ENVX << 16 | 1 << 30
        .set    S_P2EV,456                      | and its depth
        .set    S_P2CD,460                      | a CUTB difference whose glide step was 0 (0 at boot: MULQ15 of 0 is 0)
        .set    S_P2ND,464                      | an ENVS difference whose glide step was 0
        .set    S_P2T,468                       | scratch: this step's difference
        .set    S_P2DV,472                      | o3_params: 1 = the three below hold the last call's dEVILish bytes
        .set    S_P2D1,476                      | page 1 bytes 0-3, page 1 4-5 + page 2 0-1, page 2 2-5
        .set    S_P2D2,480
        .set    S_P2D3,484
        .set    S_P2DA,488                      | and page 1's source address
| v9.1: FM's source, the VCA's word through a one-pole (1/4 a sample)
        .set    S_FLP,492
| v9.0 the hybrid (O3 SEAM): the track's block in o3_hyb
        .set    H_U,0                           | u of each sample of the frame, 16 longs
        .set    H_P,64                          | three pieces, 13 longs each: n c1 b k clg cli cll w2 gcomp amp step
                                                | flags osin (v9.1; with FM, c1 b k clg = sctrl kmul ud fmq)
        .set    H_NP,220                        | pieces this frame
        .set    H_START,224                     | the frame's first rendered sample + 1 (0: none yet)
        .set    H_MODE,228                      | 1: the DSP has the voice (its states live there)
        .set    H_FMD,232                       | v9.1: an FM piece since the last control step (the next plain
                                                | piece keeps FM's last coefficients: flags bit 5)
        .set    ST_SHIFT,9
        .set    ST_SIZE,512

| ---- the per-sample constant block O3_K, addressed through %a5
        .set    K_PREHP,0
        .set    K_SQLP,4                        | v6.9: the square's edge lowpass (v6.1-v6.8: unused)
        .set    K_FBHP,8
        .set    K_DCHP,12
        .set    K_SQ,16
        .set    K_TONE,20
        .set    K_C6,24
        .set    K_C1R,28                        | v6.7: the ladder's first-stage coefficient ratio, Q12 (stock 2.0 = 8192)
        .set    K_VP1,32                        | v7.4: the VCA pair's 72 Hz high-pass
        .set    K_VP2,36                        | v7.4: its 156 Hz high-pass (RES path)

| >>> GENERATED CONSTANTS (tools/octa303/gen_tables.py) -- do not edit by hand
        .set    CS,              16
        .set    SHIFT_OUT,       6
        .set    P_CENTER,        16384
        .set    P_LO,            7168
        .set    P_HI,            25600
        .set    TUNE_LO,         -24
        .set    TUNE_HI,         24
        .set    GATE_K,          3733
        .set    GATE_HOLD_INF,   127
        .set    GATE_IDLE,       2048
        .set    GATE_TPS0,       6
        .set    GATE_FSKIP,      2
        .set    OTA_IN,          7596
        .set    OTA_OUT,         17669
        .set    OTA_LIM,         799590
        .set    SQL_DLIM,        1800000
        .set    ONE30,           1073741823
        .set    S_MAX,           28480
        .set    DIST_GAIN,       5
        .set    DIST_BIAS,       125829
        .set    TB_MEG_ATT,      12103
        .set    DF_FM_MUL,       96
        .set    DF_GIN_Q15,      25
        .set    DF_ENVX_MUL,     3
        .set    DF_MUFF_LP,      693
        .set    DF_MUFF_T,       314572
        .set    DF_HIRES,        2
        .set    OSAT_IN,         529
        .set    OSAT_OUT,        63385
        .set    OSAT_LIM,        16238056
        .set    DRV_G0,          4096
        .set    DRV_YLIM,        4194304
        .set    DRV_KN,          454725
        .set    DRV_KP,          818505
        .set    DRV_RN,          11216
        .set    DRV_RP,          6231
        .set    DRV_WN,          23933
        .set    DRV_WP,          43079
        .set    DRV_DN4,         95732
        .set    DRV_DP4,         172316
        .set    VCA_LIM,         1657856
        .set    SMOOTH_K,        9971
        .set    FINE_Q8,         2
        .set    CL_I0,           383
        .set    DF_MUFF_DLIM,    49581136
        .set    P6_K,            2241
        .set    P6_AMAX,         33554432
        .set    P6_KP,           1535
        .set    MEG_NLEV,        64
        .set    ADEC_Q50,        52
        .set    TM3_FAB,         1766
        .set    AC_R0,           93000
        .set    AC_KLN,          31915
        .set    AC_R72N,         100000
        .set    AC_VMAX,         13074431
        .set    AC_V134,         3270000
        .set    AC_V69,          576245
        .set    AC_AL,           961306801
        .set    AC_BE,           112435023
        .set    AC_Q27G,         196290749
        .set    AC_KV,           13613786
        .set    AC_KSW,          4050025
        .set    NHZ,             446
| <<< GENERATED CONSTANTS

| ---- exact split multiplies: dst = floor(dst * cof / 2^s); cof >= 0, |dst| < 2^30, tmp scratch
        .macro  MULQ15 dst, cof, tmp
        move.l  \dst,\tmp
        and.l   #0x7FFF,\tmp
        mulu.l  \cof,\tmp
        lsr.l   #8,\tmp
        lsr.l   #7,\tmp
        asr.l   #8,\dst
        asr.l   #7,\dst
        muls.l  \cof,\dst
        add.l   \tmp,\dst
        .endm
        .macro  MULQ14 dst, cof, tmp
        move.l  \dst,\tmp
        and.l   #0x3FFF,\tmp
        mulu.l  \cof,\tmp
        lsr.l   #8,\tmp
        lsr.l   #6,\tmp
        asr.l   #8,\dst
        asr.l   #6,\dst
        muls.l  \cof,\dst
        add.l   \tmp,\dst
        .endm
        .macro  MULQ12 dst, cof, tmp
        move.l  \dst,\tmp
        and.l   #0xFFF,\tmp
        mulu.l  \cof,\tmp
        lsr.l   #8,\tmp
        lsr.l   #4,\tmp
        asr.l   #8,\dst
        asr.l   #4,\dst
        muls.l  \cof,\dst
        add.l   \tmp,\dst
        .endm
        .macro  MULQ8 dst, cof, tmp
        move.l  \dst,\tmp
        and.l   #0xFF,\tmp
        mulu.l  \cof,\tmp
        lsr.l   #8,\tmp
        asr.l   #8,\dst
        muls.l  \cof,\dst
        add.l   \tmp,\dst
        .endm
        .macro  CLAMP reg, lo, hi
        cmp.l   #\hi,\reg
        ble     .Lcl\@a
        move.l  #\hi,\reg
.Lcl\@a:
        cmp.l   #\lo,\reg
        bge     .Lcl\@b
        move.l  #\lo,\reg
.Lcl\@b:
        .endm
| ---- fast multiplies (per sample): dst = ((dst >> pre) * cof) >> post
        .macro  FM78 dst, cof
        asr.l   #7,\dst
        muls.l  \cof,\dst
        asr.l   #8,\dst
        .endm
        .macro  FM411 dst, cof          | v8.4: the sample loop only, where d7 = 11 (>> 11 in one shift)
        asr.l   #4,\dst
        muls.l  \cof,\dst
        asr.l   %d7,\dst
        .endm
        .macro  FM66 dst, cof
        asr.l   #6,\dst
        muls.l  \cof,\dst
        asr.l   #6,\dst
        .endm
        .macro  FM68 dst, cof
        asr.l   #6,\dst
        muls.l  \cof,\dst
        asr.l   #8,\dst
        .endm
| ---- reg = softclip(reg): clamp to +-sqrt2, reg - reg^3/6 (S20).  Clobbers d0-d2; needs a5.
        .macro  SOFTCLIP reg
        CLAMP   \reg,-1482910,1482910
        move.l  \reg,%d0
        asr.l   #8,%d0
        move.l  %d0,%d1
        muls.l  %d0,%d1
        asr.l   #8,%d1
        asr.l   #4,%d1
        muls.l  %d0,%d1
        asr.l   #8,%d1
        asr.l   #4,%d1
        muls.l  K_C6(%a5),%d1
        asr.l   #8,%d1
        sub.l   %d1,\reg
        .endm
| ---- v7.3: the ladder clip's operating point at the ladder index in d0 (clobbered); d1, a0 scratch.
|      ACID (SWP 2) only.
        .macro  CLSET
        moveq   #2,%d1                  | ACID only (SWP 2): WHST / SELF keep the plain clip
        cmp.l   S_SWP(%a3),%d1
        bne     .Lcs0\@
        sub.l   #CL_I0,%d0
        bgt     .Lcs1\@
.Lcs0\@:
        clr.l   S_CLG(%a3)              | at or below CL_I0: the plain soft clip
        bra     .Lcs9\@
.Lcs1\@:
        lea     O3_CL_G,%a0
        move.l  (%a0,%d0.l*4),%d1
        lea     O3_CL_INV,%a0
        move.l  %d1,S_CLG(%a3)
        move.l  (%a0,%d0.l*4),%d1
        lea     O3_CL_LIM,%a0
        move.l  %d1,S_CLI(%a3)
        move.l  (%a0,%d0.l*4),%d1
        move.l  %d1,S_CLL(%a3)
.Lcs9\@:
        .endm
        .macro  KB off, areg            | d0 = the knob byte at off(areg), clamped 0..127
        mvz.b   \off(\areg),%d0         | (v10.0, Yves Rosius #1244 ff2ef4dd: one mvz.b for moveq + move.b)
        cmp.l   #127,%d0
        bls     .Lkb\@
        moveq   #127,%d0
.Lkb\@:
        .endm
        .macro  MIN2                    | d0 = min(d0, 2): a select's index, clamped
        moveq   #2,%d1
        cmp.l   %d1,%d0
        bls     .Lm2\@
        move.l  %d1,%d0
.Lm2\@:
        .endm
        .macro  DRVSAT k, r, w, d4      | v7.7 DRIV: d0 = a >= 0 -> K + (L-K) tanh((a-K)/(L-K)) above K; d1, d2, a0
        sub.l   #\k,%d0
        ble     .Ldv\@z                | a <= K: unchanged
        cmp.l   #\d4,%d0
        ble     .Ldv\@a
        move.l  #\d4,%d0               | a - K <= 4 (L - K): tanh 4 = 0.9993
.Ldv\@a:
        move.l  #\r,%d1
        muls.l  %d1,%d0
        asr.l   #6,%d0                  | t = 64 (a - K) / (L - K), Q16
        lea     O3_DRV_TH,%a0
        move.l  %d0,%d1
        swap    %d1
        and.l   #0xFFFF,%d1             | i = t >> 16
        cmp.l   #256,%d1
        blt     .Ldv\@b
        move.l  1024(%a0),%d1           | i = 256: the table's end
        bra     .Ldv\@c
.Ldv\@b:
        lea     (%a0,%d1.l*4),%a0
        and.l   #0xFFFF,%d0
        lsr.l   #1,%d0                  | the fraction, Q15
        move.l  (%a0)+,%d2              | TH[i]
        move.l  (%a0),%d1
        sub.l   %d2,%d1                 | TH[i+1] - TH[i], >= 0 and < 2^15
        muls.l  %d0,%d1
        moveq   #15,%d0
        asr.l   %d0,%d1
        add.l   %d2,%d1
.Ldv\@c:
        move.l  #\w,%d0
        muls.l  %d1,%d0                 | (L - K) tanh, Q14
        moveq   #14,%d1
        asr.l   %d1,%d0
.Ldv\@z:
        add.l   #\k,%d0
        .endm
        .macro  TAB tab, dst            | dst = tab[d0] (a long), via a1
        lea     \tab,%a1
        move.l  (%a1,%d0.l*4),%d1
        move.l  %d1,\dst(%a3)
        .endm
| v10.0 (Yves Rosius, sambanks/octabam#1244 5d7bdd44, ported): KBTAB and TABNEXT are KB then TABs with no
| address-use stall (MCF54455RM 3.3.5.1): KBTAB sets a1 before KB reads the byte; TABNEXT stores the previous
| table's long between the next table's lea and its load.  The longs stored are TAB's; the caller stores the last.
        .macro  KBTAB off, areg, tab    | d0 = the knob byte at off(areg) (KB), d1 = tab[d0]
        lea     \tab,%a1
        KB      \off,\areg
        move.l  (%a1,%d0.l*4),%d1
        .endm
        .macro  TABNEXT prev, tab       | prev(a3) = d1, then d1 = tab[d0]
        lea     \tab,%a1
        move.l  %d1,\prev(%a3)
        move.l  (%a1,%d0.l*4),%d1
        .endm
        .macro  RAWW off, dst           | dst = the word at off(a4) >> 8, clamped 0..127: its high byte
        mvz.b   \off(%a4),%d0           | (v10.0, Yves Rosius #1244 ff2ef4dd)
        cmp.l   #127,%d0
        bls     .Lrw\@
        moveq   #127,%d0
.Lrw\@:
        move.l  %d0,\dst(%a3)
        .endm

        .global o3_page, o3_retrig, o3_chrom
        .if     HK_MACHINE_ROWS         | CX OSC's poly.s exports sy_render too: ours is o3_render
        .global o3_render
        .else
        .global sy_render
        .endif

        .align  4

| ============================================================================
| sy_render(track, ping, start, end) -- in place of the stock FLEX renderer
| (frame as poly.s: 44(sp) the stock return, 48 our return, args 52 / 56 / 60 / 64)
| ============================================================================
        .if     HK_MACHINE_ROWS
o3_render:
        .else
sy_render:
        .endif
| v10.0 (Yves Rosius, sambanks/octabam#1244 298000b0, ported): a call that cannot make this track OCTA303's goes
| straight to the stock renderer, before the register frame: the track is not latched, and either this is not the
| frame's last call or no voice starts on it this frame (the full path below then only calls the stock renderer and
| returns its value: .Lstockcall, .Lnorest, .Ldone with no stopwatch row).  The stock renderer finds the same four
| arguments at the same offsets and returns to our caller; d1, a0, a1 and the flags are a call's scratch.
| (Its tests mirror the full path's entry: a change to .Lison/.Lstock's conditions must be made here too.)
        move.l  4(%sp),%d0              | track
        moveq   #NTRACKS-1,%d1
        cmp.l   %d1,%d0
        bhi     .Lfast                  | (never: the packer renders tracks 0..7; the full path only calls stock)
        move.l  %d0,%d1
        lsl.l   #8,%d1                  | track * ST_SIZE (512: 8 + 1)
        add.l   %d1,%d1
        lea     o3_state,%a0
        add.l   %d1,%a0
        moveq   #16,%d1                 | here, between the add and the load: no address-use stall
        tst.l   S_LATCHED(%a0)
        bne     .Lfull                  | latched: the full path
        cmp.l   16(%sp),%d1             | the frame's last call?
        bne     .Lfast
        lea     NIBBLE,%a0
        add.l   %d0,%a0
        btst    #4,(%a0)                | a voice starts this frame: the full path decides whose sample
        bne     .Lfull
.Lfast:
        jmp     STOCK_RENDER
.Lfull:
        lea     -48(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        move.l  O3_DTCN3,%d0            | ACIDV91 stopwatch (tools/octa303/prof): the call's entry on DMA timer 3
        move.l  %d0,o3_pt0
        move.l  CURSOR,%a2              | the header this call writes
        move.l  52(%sp),%d2             | track
        moveq   #NTRACKS-1,%d0
        cmp.l   %d0,%d2
        bhi     .Lstock                 | (never: the packer renders tracks 0..7)
        move.l  %d2,%d0
        lsl.l   #8,%d0                 | track * ST_SIZE (512: 8 + 1)
        add.l   %d0,%d0
        lea     o3_state,%a3
        add.l   %d0,%a3
        move.l  FP_PTR,%a4
        moveq   #0,%d4                  | 1 = PTCH/RATE and the positions are neutralised for the call
        moveq   #16,%d1
        cmp.l   64(%sp),%d1             | the frame's last call?
        bne     .Lstock
        lea     NIBBLE,%a0
        add.l   %d2,%a0
        btst    #4,(%a0)                | a voice starts this frame: whose sample?
        beq     .Lison
        move.l  %d2,%d0                 | v7.0: the TB-303 machine (a signed FLEX track, one of the first O3_MAX)?
        bsr     o3_sigcur_lim
        move.l  %d0,S_MACH(%a3)
        beq     .Lnot                   | v7.9: not the machine: not ours (TB303* samples are FLEX)
        bsr     o3_setupptr             | yes: SETUP's WAVE is the carrier, whatever the slot holds
        KB      0,%a0
        moveq   #7,%d1                  | v7.9: 8 values (bit 2 = R)
        cmp.l   %d1,%d0
        bls     .Lours
        move.l  %d1,%d0
        bra     .Lours
.Lours:
        move.l  %d0,%d5
        bsr     o3_params               | dEVILish first: SATK decides how the note starts
        bsr     o3_note_on
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
        bsr     o3_params               | this call's knobs, before the record is neutralised
        bsr     o3_gate                 | v7.0: SETUP's GATE (OFF: the AMP decides, as v6.5e-v6.9)
        move.w  (%a4),%d0
        move.w  %d0,S_WPTCH+2(%a3)
        move.w  6(%a4),%d0
        move.w  %d0,S_WRATE+2(%a3)
        move.l  #NEUTRAL_PTCH,%d0       | the stock renderer computes rate 1.0 from these
        move.w  %d0,(%a4)
        move.l  #NEUTRAL_RATE,%d0
        move.w  %d0,6(%a4)
        lea     S_POS(%a3),%a1          | (before the call, which keeps a1: no address-use stall; #1244 b609e4ed)
        bsr     o3_voice                | a0 = the voice's position fields
        move.l  (%a0)+,(%a1)+
        move.l  (%a0)+,(%a1)+
        move.l  (%a0)+,(%a1)+
        move.l  (%a0)+,(%a1)+
        move.l  (%a0)+,(%a1)+
        moveq   #1,%d4
.Lstock:
        moveq   #NTRACKS-1,%d0          | v8.6: one of OUR tracks (latched): no stock call.  The stock FLEX
        cmp.l   %d0,%d2                 | renderer would play the slot's sample under the 303 every frame
        bhi     .Lstockcall             | (the carrier, its positions pinned: it never ends) -- ~14 us of PRE
        tst.l   S_LATCHED(%a3)          | on a track whose slot holds a sample (13 Nov 2026, machine).  As CX
        beq     .Lstockcall             | OSC's sy_call (sam/modules/cxosc/poly.s, PR #906): write what stock
        moveq   #16,%d0                 | v8.7 (vFable's hybrid, f0898424): the LAST call of a frame with a
        cmp.l   64(%sp),%d0             | START still runs the stock renderer, neutralised as before v8.6.
        bne     .Lnatskip               | v8.6 skipped it too, and a track set back from OCTA-303 to FLEX
        lea     NIBBLE,%a0              | stayed silent on the unit (Marko, 15 Nov, T5 and T6); ACIDF04,
        add.l   %d2,%a0                 | which keeps this call, plays the FLEX (its test 8).  A START is
        btst    #4,(%a0)                | ~1 frame in 280: the skip keeps nearly all of its saving.
        bne     .Lstockcall
.Lnatskip:
        move.l  64(%sp),%d0             | would -- the count, the start, rate 1.0, the ring word -- and silent
        sub.l   60(%sp),%d0             | pairs; the 303 overwrites the pairs below.
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
        beq     .Lnatend
.Lnatclr:
        clr.l   (%a0)+
        subq.l  #1,%d0
        bne     .Lnatclr
.Lnatend:
        move.l  %a0,CURSOR
        clr.l   44(%sp)                 | the return value: 0
        bra     .Lcalled
.Lstockcall:
        move.l  64(%sp),-(%sp)          | end
        move.l  64(%sp),-(%sp)          | start
        move.l  64(%sp),-(%sp)          | ping
        move.l  64(%sp),-(%sp)          | track
        jsr     STOCK_RENDER
        move.l  %d0,60(%sp)             | the stock return value, handed back (44(%sp) after the pop): stored
        lea     16(%sp),%sp             | before the pop, a moveq between it and the next sp use (#1244 b609e4ed)
.Lcalled:
        moveq   #NTRACKS-1,%d0
        move.l  52(%sp),%d2
        cmp.l   %d0,%d2
        bhi     .Ldone
        tst.l   %d4
        beq     .Lnorest
        move.w  S_WPTCH+2(%a3),%d0      | restore PTCH and RATE for the DSP
        move.w  %d0,(%a4)
        move.w  S_WRATE+2(%a3),%d0
        move.w  %d0,6(%a4)
        lea     S_POS(%a3),%a1          | (before the call: no address-use stall)
        bsr     o3_voice                | pin the carrier: the positions as they were before the call
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        bra     .Lrender
.Lnorest:
        tst.l   S_LATCHED(%a3)
        beq     .Ldone                  | not an OCTA303 track: the stock samples stand
        bsr     o3_params               | a first call [0,n): the record is untouched
.Lrender:                               | the machine plays with or without a sample (v7.9: only the machine)
        moveq   #0,%d7
        move.b  3(%a2),%d7              | samples shipped by this call
        beq     .Ldone
        lea     16(%a2),%a1
        lea     O3_K,%a5
        clr.l   S_P11(%a3)              | v8.2 P11: the knobs may have moved since the last frame
        move.l  O3_DTCN3,%d0            | stopwatch: the sample loop starts (d0 is free: the loop writes it first)
        move.l  %d0,o3_pt1
        move.l  %d7,o3_pn               | and how many samples it renders
        moveq   #1,%d0
        move.l  %d0,o3_pflag
        move.l  %d7,%d0                 | v8.4: the loop runs to a6 (two longs a sample), so d7 is free:
        lsl.l   #3,%d0
        lea     (%a1,%d0.l),%a6
        moveq   #11,%d7                 | it holds the shift 11 (FM411, the VCO's >> 11) for the whole loop
        .if     O3_SEAM
        move.l  52(%sp),%d0             | v9.0 (O3 SEAM, the hybrid): the DSP renders the chain after u (o3h.asm
        lsl.l   #8,%d0                  | at the source seam; v9.1: every voice, v9.0: no FM, MUFF, DIST, DRIV);
        lea     o3_hyb,%a2              | a2 = the track's hybrid block (the header is not read past this point)
        add.l   %d0,%a2
        tst.l   60(%sp)                 | a frame's first call (start 0), whichever half renders it: no pieces, no
        bne     .LHnf                   | first sample yet (review 19 Nov: a frame whose last call went to the
        clr.l   H_NP(%a2)               | ColdFire left them stale for the next one)
        clr.l   H_START(%a2)
.LHnf:
        bra     .LHrender               | v9.1: every voice (FM, MUFF, DIST and DRIV too) renders on the DSP
        .endif
        tst.l   S_FMQ(%a3)              | v8.8: the neutral case runs .LFloop (same samples, fewer tests)
        bne     .Lloop
        tst.l   S_WAVE(%a3)
        bne     .Lloop
        tst.l   S_GINQ15(%a3)
        beq     .Lloop
        moveq   #2,%d0
        cmp.l   S_SWP(%a3),%d0
        bne     .Lloop
        tst.l   S_MUFF(%a3)
        bne     .Lloop
        tst.l   S_DIST(%a3)
        bne     .Lloop
        move.l  S_OSIN(%a3),%d0
        cmp.l   #DRV_G0,%d0
        beq     .LFloop

| ---------------------------------------------------------------- per sample (inline)
.Lloop:
        subq.l  #1,S_CS(%a3)
        bne     .Lnoctl
        moveq   #CS,%d0
        move.l  %d0,S_CS(%a3)
        bsr     o3_ctrl
        clr.l   S_P11(%a3)              | v8.2 P11: the control step may move the level's step
.Lnoctl:
        tst.l   S_P11(%a3)              | v8.5: closed at its fixed point since the last control step: the
        bgt     .Lp11                   | whole voice waits (VCO, filter, FM: paused; the word is the same)
        move.l  S_FMQ(%a3),%d1          | FM: the last VCA sample moves the cutoff, per sample
        beq     .Lnofm
        move.l  S_OVCA(%a3),%d0         | v9.1: through a one-pole, 1/4 a sample (~2 kHz): extreme FM stays
        sub.l   S_FLP(%a3),%d0          | wild, not TV static (Marko's choice by ear, 25 Nov 2026)
        asr.l   #2,%d0
        add.l   S_FLP(%a3),%d0
        move.l  %d0,S_FLP(%a3)
        asr.l   #8,%d0
        muls.l  %d1,%d0
        asr.l   #8,%d0
        asr.l   #4,%d0
        add.l   S_SCTRL(%a3),%d0
        CLAMP   %d0,0,S_MAX-1
        lea     O3_LADDER_B,%a0
        asr.l   #6,%d0
        move.l  (%a0,%d0.l*4),%d1
        move.l  %d1,S_B(%a3)
        muls.l  K_C1R(%a5),%d1          | v6.7: c1 = b * C1R (Q12; v6.6: b * 2)
        asr.l   #8,%d1
        asr.l   #4,%d1
        lea     O3_LADDER_K,%a0
        move.l  %d1,S_C1(%a3)
        move.l  (%a0,%d0.l*4),%d1
        muls.l  S_KMUL(%a3),%d1
        asr.l   #8,%d1
        lea     O3_KF,%a0               | the oscillation point and its shape by frequency (Q12)
        asr.l   #7,%d1
        move.l  (%a0,%d0.l*4),%d2
        muls.l  %d2,%d1
        asr.l   #8,%d1
        lea     O3_KD,%a0               | v6.9: less the ring's decay, UD (dB/ms) * KD; never < 0
        asr.l   #4,%d1
        move.l  (%a0,%d0.l*4),%d2
        muls.l  S_UD(%a3),%d2
        asr.l   #8,%d2
        asr.l   #2,%d2
        sub.l   %d2,%d1
        bpl     .Lfm_k
        moveq   #0,%d1
.Lfm_k:
        move.l  %d1,S_K(%a3)
        CLSET                 | v7.3
.Lnofm:
        move.l  S_INC(%a3),%d5          | VCO
        move.l  S_PHASE(%a3),%d4
        add.l   %d5,%d4
        move.l  %d4,S_PHASE(%a3)
        tst.l   S_WAVE(%a3)
        bne     .Lsq
        move.l  %d4,%d6                 | saw
        lsr.l   %d7,%d6
        sub.l   #0x100000,%d6
        cmp.l   %d5,%d4                 | polyBLEP only within one increment of the wrap
        bcs     .Lsb
        move.l  %d4,%d0
        neg.l   %d0
        cmp.l   %d5,%d0
        bcc     .Losc
.Lsb:
        move.l  %d4,%d0
        bsr     o3_blep
        lsl.l   #5,%d0
        sub.l   %d0,%d6
        bra     .Losc
.Lsq:
        move.l  %d4,%d6                 | v7.6: Q8's square (o3q8.py) = its cycle's smooth part (a table, 128
        lsr.l   %d7,%d6                 | points, linear) + SQK * the saw (with its polyBLEP): the one hard edge
                                        | is the saw's reset
        sub.l   #0x100000,%d6
        cmp.l   %d5,%d4
        bcs     .Lqb
        move.l  %d4,%d0
        neg.l   %d0
        cmp.l   %d5,%d0
        bcc     .Lqn
.Lqb:
        move.l  %d4,%d0
        bsr     o3_blep
        lsl.l   #5,%d0
        sub.l   %d0,%d6
.Lqn:
        FM78    %d6,S_SQK(%a3)
        move.l  S_SQTP(%a3),%a0
        move.l  %d4,%d0
        moveq   #25,%d1
        lsr.l   %d1,%d0                 | i = phase >> 25
        move.l  %d0,%d1                 | v10.0: i + 1 first, so neither indexed load follows the write of its
        addq.l  #1,%d1                  | index (cf_scan: 3 cycles each, 2 a sample on a square voice)
        and.l   #127,%d1
        move.w  (%a0,%d0.l*2),%d2
        ext.l   %d2                     | c0
        move.w  (%a0,%d1.l*2),%d3
        ext.l   %d3
        sub.l   %d2,%d3                 | c1 - c0
        move.l  %d4,%d1
        lsr.l   #8,%d1
        lsr.l   #2,%d1
        and.l   #0x7FFF,%d1             | fr = (phase >> 10) & 0x7FFF
        muls.l  %d1,%d3
        asr.l   #8,%d3
        asr.l   #7,%d3
        add.l   %d3,%d2
        lsl.l   #5,%d2
        add.l   %d2,%d6
        move.l  %d6,%d0                 | the 303's square has softer edges than Q8's alone: a one-pole
        sub.l   S_SQL(%a3),%d0          | (fitted, as v6.9); the step clamped so the multiply fits 32 bits
        CLAMP   %d0,-SQL_DLIM,SQL_DLIM
        FM411   %d0,K_SQLP(%a5)
        add.l   S_SQL(%a3),%d0
        move.l  %d0,S_SQL(%a3)
        move.l  %d0,%d6
.Losc:
        move.l  %d6,%d0                 | VCO->VCF coupling highpass, level
        sub.l   S_HP(%a3),%d0
        FM411   %d0,K_PREHP(%a5)
        add.l   S_HP(%a3),%d0
        move.l  %d0,S_HP(%a3)
        sub.l   %d0,%d6
        tst.l   S_GINQ15(%a3)           | OVDR: up to normal, v6.1's product exactly...
        beq     .Lov
        FM78    %d6,S_GIN(%a3)
        bra     .Lov2
.Lov:
        asr.l   #6,%d6                  | ...above it, to 66.6x (Q10)
        muls.l  S_GIN(%a3),%d6
        asr.l   #4,%d6
.Lov2:
        moveq   #2,%d0                  | SWP 1/0: the analogue noise floor (~-84 dB), so the filter
        cmp.l   S_SWP(%a3),%d0          | can self-oscillate with no VCO
        beq     .Lnz9
        move.l  S_NZ(%a3),%d0
        bne     .Lnz0
        move.l  #0x1D872B41,%d0
.Lnz0:
        move.l  %d0,%d1
        lsr.l   #1,%d0
        btst    #0,%d1
        beq     .Lnz1
        eor.l   #0xD0000001,%d0
.Lnz1:
        move.l  %d0,S_NZ(%a3)
        btst    #0,%d0
        beq     .Lnzm
        add.l   #64,%d6
        bra     .Lnz9
.Lnzm:
        sub.l   #64,%d6
.Lnz9:
        move.l  S_Y4(%a3),%d4           | resonance: y4 through the loop highpass, * k
        move.l  %d4,%d0
        sub.l   S_FB(%a3),%d0
        FM411   %d0,K_FBHP(%a5)
        add.l   S_FB(%a3),%d0
        move.l  %d0,S_FB(%a3)
        move.l  %d4,%d1
        sub.l   %d0,%d1
        CLAMP   %d1,-0x800000,0x800000
        move.l  %d1,S_FBO(%a3)          | v7.4: the high-passed ladder output, also the voice's output
        asr.l   #8,%d1
        muls.l  S_K(%a3),%d1
        sub.l   %d1,%d6
        tst.l   S_CLG(%a3)              | v7.3 (#1011): at the top of the table softclip(u * g) / g,
        beq     .Llcp                   | so its 3rd harmonic cannot lock the loop at fs/4
        move.l  S_CLL(%a3),%d2
        cmp.l   %d2,%d6
        ble     .Llc1
        move.l  %d2,%d6
.Llc1:
        neg.l   %d2
        cmp.l   %d2,%d6
        bge     .Llc2
        move.l  %d2,%d6
.Llc2:
        asr.l   #4,%d6
        muls.l  S_CLG(%a3),%d6
        asr.l   #8,%d6
        SOFTCLIP %d6
        asr.l   #4,%d6
        muls.l  S_CLI(%a3),%d6
        asr.l   #8,%d6
        bra     .Llc9
.Llcp:
        SOFTCLIP %d6
.Llc9:
        move.l  S_Y1(%a3),%d1           | diode ladder
        move.l  S_Y2(%a3),%d2
        move.l  S_Y3(%a3),%d3
        move.l  S_B(%a3),%d5
        move.l  %d6,%d0
        sub.l   %d1,%d0
        add.l   %d2,%d0
        FM78    %d0,S_C1(%a3)
        add.l   %d0,%d1
        move.l  %d1,%d0
        sub.l   %d2,%d0
        sub.l   %d2,%d0
        add.l   %d3,%d0
        FM78    %d0,%d5
        add.l   %d0,%d2
        move.l  %d2,%d0
        sub.l   %d3,%d0
        sub.l   %d3,%d0
        add.l   %d4,%d0
        FM78    %d0,%d5
        add.l   %d0,%d3
        move.l  %d3,%d0
        sub.l   %d4,%d0
        sub.l   %d4,%d0
        FM78    %d0,%d5
        add.l   %d0,%d4
        move.l  %d1,S_Y1(%a3)
        move.l  %d2,S_Y2(%a3)
        move.l  %d3,S_Y3(%a3)
        move.l  %d4,S_Y4(%a3)
        move.l  S_FBO(%a3),%d6          | v7.4: the output is the loop's high-pass (one, shared), then the
        move.l  %d6,%d0                 | VCA's input pair: 72 Hz plain + 156 Hz from the RES wiper
        sub.l   S_VP1(%a3),%d0
        FM411   %d0,K_VP1(%a5)
        add.l   S_VP1(%a3),%d0
        move.l  %d0,S_VP1(%a3)
        move.l  %d6,%d1
        sub.l   %d0,%d1                 | d1 = fb - vp1
        move.l  %d6,%d0
        sub.l   S_VP2(%a3),%d0
        FM411   %d0,K_VP2(%a5)
        add.l   S_VP2(%a3),%d0
        move.l  %d0,S_VP2(%a3)
        sub.l   %d0,%d6                 | fb - vp2
        asr.l   #6,%d6
        muls.l  S_W2(%a3),%d6
        asr.l   #6,%d6
        add.l   %d1,%d6
        move.l  S_AMP(%a3),%d3          | v8.2 P11: the VCA's level first (was after the OTA, same value;
        add.l   S_AMPSTEP(%a3),%d3      | d3 is free from here to the sample's end)
        bgt     .Lamp                   | open: the whole chain
        moveq   #0,%d3
        move.l  %d3,S_AMP(%a3)          | closed this sample: max(0, amp + step) = 0
        move.l  S_P11(%a3),%d0
        bgt     .Lp11                   | 1: the chain after the VCA sits at its fixed point: its word again
        beq     .Lp11t                  | 0: try
        move.l  S_DC(%a3),%d0           | -1: the sample before was the try (closed, same frame, no control
        cmp.l   S_P11A(%a3),%d0         | step since): did it leave the chain's three states where they were?
        bne     .Lp11t
        move.l  S_MLO(%a3),%d0
        cmp.l   S_P11B(%a3),%d0
        bne     .Lp11t
        move.l  S_TONE(%a3),%d0
        cmp.l   S_P11C(%a3),%d0
        bne     .Lp11t
        moveq   #1,%d0                  | yes: the fixed point, and its word is the one just written
        move.l  %d0,S_P11(%a3)
        move.l  -4(%a1),%d0
        move.l  %d0,S_P11OUT(%a3)
        bra     .Lp11
.Lp11t:
        moveq   #-1,%d0                 | try: this sample runs the chain at level 0; keep its states
        move.l  %d0,S_P11(%a3)
        move.l  S_DC(%a3),%d0
        move.l  %d0,S_P11A(%a3)
        move.l  S_MLO(%a3),%d0
        move.l  %d0,S_P11B(%a3)
        move.l  S_TONE(%a3),%d0
        move.l  %d0,S_P11C(%a3)
        bra     .Lamp0
.Lamp:
        move.l  %d3,S_AMP(%a3)
        clr.l   S_P11(%a3)
.Lamp0:
        FM66    %d6,S_GCOMP(%a3)        | level compensation, VCA (ramped per sample)
        CLAMP   %d6,-OTA_LIM,OTA_LIM    | v7.6: the VCA is an OTA (IC15 BA6110): OTA_V * softclip(o / OTA_V)
        asr.l   #4,%d6
        move.l  #OTA_IN,%d1
        muls.l  %d1,%d6
        asr.l   #8,%d6
        SOFTCLIP %d6
        asr.l   #4,%d6
        move.l  #OTA_OUT,%d1
        muls.l  %d1,%d6
        asr.l   #8,%d6
        asr.l   #3,%d6
        CLAMP   %d6,-VCA_LIM,VCA_LIM    | v6.9: the VCA multiply never wraps
        move.l  %d3,%d1                 | v8.2 P11: the level, from above
        asr.l   #1,%d1                  | v7.3: (o >> 7) * (amp >> 1) >> 6, four times the room
        asr.l   #7,%d6                  | (#1011; v6.9-v7.1: FM68 with amp)
        muls.l  %d1,%d6
        asr.l   #6,%d6
| v7.7: the BA662A's pin 6 cannot leave the supply (o3tables P6_*):
        move.l  %d6,%d0                 | o -> sign(o) * P6_F(64 |o| / L), linear between the 257 points;
        move.l  #P6_KP,%d1              | v7.8: the positive side p6r x higher (O3_P6_FP)
        lea     O3_P6_FP,%a0
        tst.l   %d0
        bpl     .Lp6a
        neg.l   %d0
        move.l  #P6_K,%d1
        lea     O3_P6_F,%a0
.Lp6a:
        cmp.l   #P6_AMAX,%d0            | beyond P6_AMAX the table is flat: the multiply stays in 32 bits
        ble     .Lp6b
        move.l  #P6_AMAX,%d0
.Lp6b:
        asr.l   #6,%d0
        muls.l  %d1,%d0
        asr.l   #2,%d0                  | t = 64 |o| / L, Q16
        move.l  %d0,%d1
        swap    %d1
        and.l   #0xFFFF,%d1             | i = t >> 16
        cmp.l   #256,%d1
        blt     .Lp6c
        move.l  1024(%a0),%d1           | i >= 256: the flat end
        bra     .Lp6d
.Lp6c:
        lea     (%a0,%d1.l*4),%a0
        and.l   #0xFFFF,%d0
        lsr.l   #1,%d0                  | the fraction, Q15
        move.l  (%a0)+,%d2              | F[i]
        move.l  (%a0),%d1
        sub.l   %d2,%d1                 | F[i+1] - F[i], >= 0 and < 2^15
        muls.l  %d0,%d1
        moveq   #15,%d0
        asr.l   %d0,%d1
        add.l   %d2,%d1
.Lp6d:
        tst.l   %d6
        bpl     .Lp6e
        neg.l   %d1
.Lp6e:
        move.l  %d1,%d6
        move.l  S_MUFF(%a3),%d0         | MUFF: the bass passes, the rest is clipped
        beq     .Lmu9
        move.l  %d6,%d1
        sub.l   S_MLO(%a3),%d1
        CLAMP   %d1,-DF_MUFF_DLIM,DF_MUFF_DLIM  | v7.3: the product fits 32 bits at the wider VCA
        move.l  #DF_MUFF_LP,%d2
        FM411   %d1,%d2
        add.l   S_MLO(%a3),%d1
        move.l  %d1,S_MLO(%a3)
        sub.l   %d1,%d6                 | h
        cmp.l   #1,%d0
        bne     .Lmu2
        CLAMP   %d6,-1048576,1048576    | v6.7: no overflow (softclip saturates far below this)
        asr.l   #2,%d6                  | 1: T * softclip(h / T)
        move.l  #3413,%d2
        muls.l  %d2,%d6
        asr.l   #8,%d6
        SOFTCLIP %d6
        asr.l   #4,%d6
        move.l  #9830,%d2
        muls.l  %d2,%d6
        asr.l   #8,%d6
        asr.l   #3,%d6
        bra     .Lmu3
.Lmu2:
        CLAMP   %d6,-DF_MUFF_T,DF_MUFF_T  | 2: hard
.Lmu3:
        add.l   S_MLO(%a3),%d6
.Lmu9:
        move.l  %d6,S_OVCA(%a3)         | FM reads the VCA after the Muffler
        tst.l   S_DIST(%a3)
        beq     .Lnod
        move.l  %d6,%d0                 | the pedal: x DIST_GAIN = 5, as 4 x + x (v8.2 P4; gen_tables asserts 5)
        lsl.l   #2,%d6
        add.l   %d0,%d6
        add.l   #DIST_BIAS,%d6
        SOFTCLIP %d6
        move.l  %d6,%d0
        sub.l   S_TONE(%a3),%d0
        FM78    %d0,K_TONE(%a5)
        add.l   S_TONE(%a3),%d0
        move.l  %d0,S_TONE(%a3)
        move.l  %d0,%d6
.Lnod:
        move.l  %d6,%d0                 | output coupling
        sub.l   S_DC(%a3),%d0
        FM411   %d0,K_DCHP(%a5)
        add.l   S_DC(%a3),%d0
        move.l  %d0,S_DC(%a3)
        sub.l   %d0,%d6
        move.l  S_OSIN(%a3),%d2        | v7.7: DRIV 0 = Din Sync's VOLUME: pin 6 is the only ceiling, bit for bit
        cmp.l   #DRV_G0,%d2
        bne     .Losd
        CLAMP   %d6,-16777216,16777216
        bra     .Losx
.Losd:
        CLAMP   %d6,-DRV_YLIM,DRV_YLIM  | v7.7: DRIV = VR8 past Din Sync's position, into Q33/Q34 (o3tables DRV_*)
        asr.l   #6,%d6
        muls.l  %d2,%d6
        asr.l   #6,%d6                  | x = G y, G = 0..+10 dB (Q12)
        move.l  %d6,%d0
        bmi     .Losn
        DRVSAT  DRV_KP,DRV_RP,DRV_WP,DRV_DP4    | + side: L+ = 1.8 L-
        move.l  %d0,%d6
        bra     .Losx
.Losn:
        neg.l   %d0
        DRVSAT  DRV_KN,DRV_RN,DRV_WN,DRV_DN4    | - side: L- = today's ceiling
        neg.l   %d0
        move.l  %d0,%d6
.Losx:
        asr.l   #SHIFT_OUT,%d6
        CLAMP   %d6,-32767,32767
        lsl.l   #8,%d6
        lsl.l   #8,%d6
        move.l  %d6,(%a1)+
        move.l  %d6,(%a1)+
        cmpa.l  %a6,%a1                 | v8.4: to the end pointer (d7 holds 11)
        bne     .Lloop
        bra     .Ldone
.Lp11:                                  | v8.2 P11: closed, fixed point: the same word, S_OVCA unchanged
        move.l  S_P11OUT(%a3),%d6
        move.l  %d6,(%a1)+
        move.l  %d6,(%a1)+
        cmpa.l  %a6,%a1                 | v8.4: to the end pointer (d7 holds 11)
        bne     .Lloop
        bra     .Ldone
| ---------------------------------------------------------------- v8.8: the neutral loop (strada A, step 1)
| The same arithmetic as .Lloop, bit for bit, with what the neutral case never runs left out: no FM, the saw,
| OVDR up to normal (GINQ15), SWP ACID (no noise), no MUFF, no +D, DRIV 0.  None of these is written by the
| control step (o3_ctrl), so a call that enters here stays here; the ladder clip (CLG) and P11 are kept.
.LFloop:
        subq.l  #1,S_CS(%a3)
        bne     .LFnoctl
        moveq   #CS,%d0
        move.l  %d0,S_CS(%a3)
        bsr     o3_ctrl
        clr.l   S_P11(%a3)              | v8.2 P11: the control step may move the level's step
.LFnoctl:
        tst.l   S_P11(%a3)              | v8.5: closed at its fixed point since the last control step: the
        bgt     .LFp11                   | whole voice waits (VCO, filter, FM: paused; the word is the same)
        move.l  S_INC(%a3),%d5          | VCO
        move.l  S_PHASE(%a3),%d4
        add.l   %d5,%d4
        move.l  %d4,S_PHASE(%a3)
        move.l  %d4,%d6                 | saw
        lsr.l   %d7,%d6
        sub.l   #0x100000,%d6
        cmp.l   %d5,%d4                 | polyBLEP only within one increment of the wrap
        bcs     .LFsb
        move.l  %d4,%d0
        neg.l   %d0
        cmp.l   %d5,%d0
        bcc     .LFosc
.LFsb:
        move.l  %d4,%d0
        bsr     o3_blep
        lsl.l   #5,%d0
        sub.l   %d0,%d6
.LFosc:
        move.l  %d6,%d0                 | VCO->VCF coupling highpass, level
        sub.l   S_HP(%a3),%d0
        FM411   %d0,K_PREHP(%a5)
        add.l   S_HP(%a3),%d0
        move.l  %d0,S_HP(%a3)
        sub.l   %d0,%d6
        FM78    %d6,S_GIN(%a3)          | OVDR up to normal (this loop is entered with GINQ15 set)
        move.l  S_Y4(%a3),%d4           | resonance: y4 through the loop highpass, * k
        move.l  %d4,%d0
        sub.l   S_FB(%a3),%d0
        FM411   %d0,K_FBHP(%a5)
        add.l   S_FB(%a3),%d0
        move.l  %d0,S_FB(%a3)
        move.l  %d4,%d1
        sub.l   %d0,%d1
        CLAMP   %d1,-0x800000,0x800000
        move.l  %d1,S_FBO(%a3)          | v7.4: the high-passed ladder output, also the voice's output
        asr.l   #8,%d1
        muls.l  S_K(%a3),%d1
        sub.l   %d1,%d6
        tst.l   S_CLG(%a3)              | v7.3 (#1011): at the top of the table softclip(u * g) / g,
        beq     .LFlcp                   | so its 3rd harmonic cannot lock the loop at fs/4
        move.l  S_CLL(%a3),%d2
        cmp.l   %d2,%d6
        ble     .LFlc1
        move.l  %d2,%d6
.LFlc1:
        neg.l   %d2
        cmp.l   %d2,%d6
        bge     .LFlc2
        move.l  %d2,%d6
.LFlc2:
        asr.l   #4,%d6
        muls.l  S_CLG(%a3),%d6
        asr.l   #8,%d6
        SOFTCLIP %d6
        asr.l   #4,%d6
        muls.l  S_CLI(%a3),%d6
        asr.l   #8,%d6
        bra     .LFlc9
.LFlcp:
        SOFTCLIP %d6
.LFlc9:
        move.l  S_Y1(%a3),%d1           | diode ladder
        move.l  S_Y2(%a3),%d2
        move.l  S_Y3(%a3),%d3
        move.l  S_B(%a3),%d5
        move.l  %d6,%d0
        sub.l   %d1,%d0
        add.l   %d2,%d0
        FM78    %d0,S_C1(%a3)
        add.l   %d0,%d1
        move.l  %d1,%d0
        sub.l   %d2,%d0
        sub.l   %d2,%d0
        add.l   %d3,%d0
        FM78    %d0,%d5
        add.l   %d0,%d2
        move.l  %d2,%d0
        sub.l   %d3,%d0
        sub.l   %d3,%d0
        add.l   %d4,%d0
        FM78    %d0,%d5
        add.l   %d0,%d3
        move.l  %d3,%d0
        sub.l   %d4,%d0
        sub.l   %d4,%d0
        FM78    %d0,%d5
        add.l   %d0,%d4
        move.l  %d1,S_Y1(%a3)
        move.l  %d2,S_Y2(%a3)
        move.l  %d3,S_Y3(%a3)
        move.l  %d4,S_Y4(%a3)
        move.l  S_FBO(%a3),%d6          | v7.4: the output is the loop's high-pass (one, shared), then the
        move.l  %d6,%d0                 | VCA's input pair: 72 Hz plain + 156 Hz from the RES wiper
        sub.l   S_VP1(%a3),%d0
        FM411   %d0,K_VP1(%a5)
        add.l   S_VP1(%a3),%d0
        move.l  %d0,S_VP1(%a3)
        move.l  %d6,%d1
        sub.l   %d0,%d1                 | d1 = fb - vp1
        move.l  %d6,%d0
        sub.l   S_VP2(%a3),%d0
        FM411   %d0,K_VP2(%a5)
        add.l   S_VP2(%a3),%d0
        move.l  %d0,S_VP2(%a3)
        sub.l   %d0,%d6                 | fb - vp2
        asr.l   #6,%d6
        muls.l  S_W2(%a3),%d6
        asr.l   #6,%d6
        add.l   %d1,%d6
        move.l  S_AMP(%a3),%d3          | v8.2 P11: the VCA's level first (was after the OTA, same value;
        add.l   S_AMPSTEP(%a3),%d3      | d3 is free from here to the sample's end)
        bgt     .LFamp                   | open: the whole chain
        moveq   #0,%d3
        move.l  %d3,S_AMP(%a3)          | closed this sample: max(0, amp + step) = 0
        move.l  S_P11(%a3),%d0
        bgt     .LFp11                   | 1: the chain after the VCA sits at its fixed point: its word again
        beq     .LFp11t                  | 0: try
        move.l  S_DC(%a3),%d0           | -1: the sample before was the try (closed, same frame, no control
        cmp.l   S_P11A(%a3),%d0         | step since): did it leave the chain's three states where they were?
        bne     .LFp11t
        move.l  S_MLO(%a3),%d0
        cmp.l   S_P11B(%a3),%d0
        bne     .LFp11t
        move.l  S_TONE(%a3),%d0
        cmp.l   S_P11C(%a3),%d0
        bne     .LFp11t
        moveq   #1,%d0                  | yes: the fixed point, and its word is the one just written
        move.l  %d0,S_P11(%a3)
        move.l  -4(%a1),%d0
        move.l  %d0,S_P11OUT(%a3)
        bra     .LFp11
.LFp11t:
        moveq   #-1,%d0                 | try: this sample runs the chain at level 0; keep its states
        move.l  %d0,S_P11(%a3)
        move.l  S_DC(%a3),%d0
        move.l  %d0,S_P11A(%a3)
        move.l  S_MLO(%a3),%d0
        move.l  %d0,S_P11B(%a3)
        move.l  S_TONE(%a3),%d0
        move.l  %d0,S_P11C(%a3)
        bra     .LFamp0
.LFamp:
        move.l  %d3,S_AMP(%a3)
        clr.l   S_P11(%a3)
.LFamp0:
        FM66    %d6,S_GCOMP(%a3)        | level compensation, VCA (ramped per sample)
        CLAMP   %d6,-OTA_LIM,OTA_LIM    | v7.6: the VCA is an OTA (IC15 BA6110): OTA_V * softclip(o / OTA_V)
        asr.l   #4,%d6
        move.l  #OTA_IN,%d1
        muls.l  %d1,%d6
        asr.l   #8,%d6
        SOFTCLIP %d6
        asr.l   #4,%d6
        move.l  #OTA_OUT,%d1
        muls.l  %d1,%d6
        asr.l   #8,%d6
        asr.l   #3,%d6
        CLAMP   %d6,-VCA_LIM,VCA_LIM    | v6.9: the VCA multiply never wraps
        move.l  %d3,%d1                 | v8.2 P11: the level, from above
        asr.l   #1,%d1                  | v7.3: (o >> 7) * (amp >> 1) >> 6, four times the room
        asr.l   #7,%d6                  | (#1011; v6.9-v7.1: FM68 with amp)
        muls.l  %d1,%d6
        asr.l   #6,%d6
| v7.7: the BA662A's pin 6 cannot leave the supply (o3tables P6_*):
        move.l  %d6,%d0                 | o -> sign(o) * P6_F(64 |o| / L), linear between the 257 points;
        move.l  #P6_KP,%d1              | v7.8: the positive side p6r x higher (O3_P6_FP)
        lea     O3_P6_FP,%a0
        tst.l   %d0
        bpl     .LFp6a
        neg.l   %d0
        move.l  #P6_K,%d1
        lea     O3_P6_F,%a0
.LFp6a:
        cmp.l   #P6_AMAX,%d0            | beyond P6_AMAX the table is flat: the multiply stays in 32 bits
        ble     .LFp6b
        move.l  #P6_AMAX,%d0
.LFp6b:
        asr.l   #6,%d0
        muls.l  %d1,%d0
        asr.l   #2,%d0                  | t = 64 |o| / L, Q16
        move.l  %d0,%d1
        swap    %d1
        and.l   #0xFFFF,%d1             | i = t >> 16
        cmp.l   #256,%d1
        blt     .LFp6c
        move.l  1024(%a0),%d1           | i >= 256: the flat end
        bra     .LFp6d
.LFp6c:
        lea     (%a0,%d1.l*4),%a0
        and.l   #0xFFFF,%d0
        lsr.l   #1,%d0                  | the fraction, Q15
        move.l  (%a0)+,%d2              | F[i]
        move.l  (%a0),%d1
        sub.l   %d2,%d1                 | F[i+1] - F[i], >= 0 and < 2^15
        muls.l  %d0,%d1
        moveq   #15,%d0
        asr.l   %d0,%d1
        add.l   %d2,%d1
.LFp6d:
        tst.l   %d6
        bpl     .LFp6e
        neg.l   %d1
.LFp6e:
        move.l  %d1,%d6
        move.l  %d6,S_OVCA(%a3)         | kept: the full loop's FM reads it if a later call runs there
        move.l  %d6,%d0                 | output coupling
        sub.l   S_DC(%a3),%d0
        FM411   %d0,K_DCHP(%a5)
        add.l   S_DC(%a3),%d0
        move.l  %d0,S_DC(%a3)
        sub.l   %d0,%d6
        CLAMP   %d6,-16777216,16777216  | DRIV 0 (this loop is entered with OSIN = DRV_G0)
        asr.l   #SHIFT_OUT,%d6
        CLAMP   %d6,-32767,32767
        lsl.l   #8,%d6
        lsl.l   #8,%d6
        move.l  %d6,(%a1)+
        move.l  %d6,(%a1)+
        cmpa.l  %a6,%a1                 | v8.4: to the end pointer (d7 holds 11)
        bne     .LFloop
        bra     .Ldone
.LFp11:                                  | v8.2 P11: closed, fixed point: the same word, S_OVCA unchanged
        move.l  S_P11OUT(%a3),%d6
        move.l  %d6,(%a1)+
        move.l  %d6,(%a1)+
        cmpa.l  %a6,%a1                 | v8.4: to the end pointer (d7 holds 11)
        bne     .LFloop
        .if     O3_SEAM
| ---------------------------------------------------------------- v9.0 the hybrid: the ColdFire half
| (coordination, 19 Nov 2026; tools/octa303/ibrido3/hyb.py is its model, the record's format in its docstring).
| Each sample up to u (VCO, the input highpass, OVDR's gain, the noise) into the track's hybrid block; the control
| words in pieces (a piece opens at the call and after each control step); at the frame's last call the record
| goes into the track's source slot for o3h.asm.  amp is kept here as max(0, amp + n * step) per piece.
.LHrender:
        move.l  60(%sp),%d0             | this call's first sample; 0 = a new frame (its first call is [0, s) or
        bne     .LHsame                 | [0, 16)): no pieces, no first sample yet (the record's write clears
        clr.l   H_NP(%a2)               | them too: a frame whose first call was not ours starts clean)
        clr.l   H_START(%a2)
.LHsame:
        tst.l   H_START(%a2)            | H_START = the frame's first rendered sample + 1 (0: none yet)
        bne     .LHst
        move.l  %d0,%d1
        addq.l  #1,%d1
        move.l  %d1,H_START(%a2)
.LHst:
        lsl.l   #2,%d0
        lea     H_U(%a2),%a1
        add.l   %d0,%a1
        move.l  o3_pn,%d0               | its samples: to a6
        lsl.l   #2,%d0
        lea     (%a1,%d0.l),%a6
        bsr     .LHopen
.LHloop:
        subq.l  #1,S_CS(%a3)
        bne     .LHnoctl
        bsr     .LHclose
        moveq   #CS,%d0
        move.l  %d0,S_CS(%a3)
        bsr     o3_ctrl
        clr.l   H_FMD(%a2)              | v9.1: the control step sets the coefficients again
        bsr     .LHopen
.LHnoctl:
        move.l  S_INC(%a3),%d5          | VCO
        move.l  S_PHASE(%a3),%d4
        add.l   %d5,%d4
        move.l  %d4,S_PHASE(%a3)
        tst.l   S_WAVE(%a3)
        bne     .LHsq
        move.l  %d4,%d6                 | saw
        lsr.l   %d7,%d6
        sub.l   #0x100000,%d6
        cmp.l   %d5,%d4                 | polyBLEP only within one increment of the wrap
        bcs     .LHsb
        move.l  %d4,%d0
        neg.l   %d0
        cmp.l   %d5,%d0
        bcc     .LHosc
.LHsb:
        move.l  %d4,%d0
        bsr     o3_blep
        lsl.l   #5,%d0
        sub.l   %d0,%d6
        bra     .LHosc
.LHsq:
        move.l  %d4,%d6                 | v7.6: Q8's square (o3q8.py) = its cycle's smooth part (a table, 128
        lsr.l   %d7,%d6                 | points, linear) + SQK * the saw (with its polyBLEP): the one hard edge
                                        | is the saw's reset
        sub.l   #0x100000,%d6
        cmp.l   %d5,%d4
        bcs     .LHqb
        move.l  %d4,%d0
        neg.l   %d0
        cmp.l   %d5,%d0
        bcc     .LHqn
.LHqb:
        move.l  %d4,%d0
        bsr     o3_blep
        lsl.l   #5,%d0
        sub.l   %d0,%d6
.LHqn:
        FM78    %d6,S_SQK(%a3)
        move.l  S_SQTP(%a3),%a0
        move.l  %d4,%d0
        moveq   #25,%d1
        lsr.l   %d1,%d0                 | i = phase >> 25
        move.l  %d0,%d1                 | v10.0: i + 1 first, so neither indexed load follows the write of its
        addq.l  #1,%d1                  | index (cf_scan: 3 cycles each, 2 a sample on a square voice)
        and.l   #127,%d1
        move.w  (%a0,%d0.l*2),%d2
        ext.l   %d2                     | c0
        move.w  (%a0,%d1.l*2),%d3
        ext.l   %d3
        sub.l   %d2,%d3                 | c1 - c0
        move.l  %d4,%d1
        lsr.l   #8,%d1
        lsr.l   #2,%d1
        and.l   #0x7FFF,%d1             | fr = (phase >> 10) & 0x7FFF
        muls.l  %d1,%d3
        asr.l   #8,%d3
        asr.l   #7,%d3
        add.l   %d3,%d2
        lsl.l   #5,%d2
        add.l   %d2,%d6
        move.l  %d6,%d0                 | the 303's square has softer edges than Q8's alone: a one-pole
        sub.l   S_SQL(%a3),%d0          | (fitted, as v6.9); the step clamped so the multiply fits 32 bits
        CLAMP   %d0,-SQL_DLIM,SQL_DLIM
        FM411   %d0,K_SQLP(%a5)
        add.l   S_SQL(%a3),%d0
        move.l  %d0,S_SQL(%a3)
        move.l  %d0,%d6
.LHosc:
        move.l  %d6,%d0                 | VCO->VCF coupling highpass, level
        sub.l   S_HP(%a3),%d0
        FM411   %d0,K_PREHP(%a5)
        add.l   S_HP(%a3),%d0
        move.l  %d0,S_HP(%a3)
        sub.l   %d0,%d6
        tst.l   S_GINQ15(%a3)           | OVDR: up to normal, v6.1's product exactly...
        beq     .LHov
        FM78    %d6,S_GIN(%a3)
        bra     .LHov2
.LHov:
        asr.l   #6,%d6                  | ...above it, to 66.6x (Q10)
        muls.l  S_GIN(%a3),%d6
        asr.l   #4,%d6
.LHov2:
        moveq   #2,%d0                  | SWP 1/0: the analogue noise floor (~-84 dB), so the filter
        cmp.l   S_SWP(%a3),%d0          | can self-oscillate with no VCO
        beq     .LHnz9
        move.l  S_NZ(%a3),%d0
        bne     .LHnz0
        move.l  #0x1D872B41,%d0
.LHnz0:
        move.l  %d0,%d1
        lsr.l   #1,%d0
        btst    #0,%d1
        beq     .LHnz1
        eor.l   #0xD0000001,%d0
.LHnz1:
        move.l  %d0,S_NZ(%a3)
        btst    #0,%d0
        beq     .LHnzm
        add.l   #64,%d6
        bra     .LHnz9
.LHnzm:
        sub.l   #64,%d6
.LHnz9:
        move.l  %d6,(%a1)+              | u
        addq.l  #1,(%a4)                | the piece's n
        cmpa.l  %a6,%a1
        bne     .LHloop
        bsr     .LHclose
        moveq   #16,%d0
        cmp.l   64(%sp),%d0             | the frame's last call: the record
        bne     .Ldone
        move.l  52(%sp),%d0             | 0x80001c90 + (ping & 1) * 0xa80 + 336 * track (ab_render's slot)
        move.l  #336,%d1
        muls.l  %d1,%d0
        add.l   #0x80001c90,%d0
        moveq   #1,%d1
        and.l   56(%sp),%d1
        beq     .LHr0
        add.l   #0xa80,%d0
.LHr0:
        move.l  %d0,%a0
        move.l  %d0,%a6
        move.l  #0xA303,%d0
        move.w  %d0,(%a0)+              | w0 the signature
        moveq   #1,%d0                  | w1 a new voice: the DSP's states from zero
        tst.l   H_MODE(%a2)
        beq     .LHr1
        moveq   #0,%d0
.LHr1:
        move.w  %d0,(%a0)+
        move.l  #0x0303,%d0
        move.w  %d0,(%a0)+              | w2 the signature
        move.l  H_NP(%a2),%d1
        move.l  %d1,%d0
        lsl.l   #8,%d0
        add.l   H_START(%a2),%d0
        subq.l  #1,%d0
        move.w  %d0,(%a0)+              | w3 start | pieces << 8
        lea     H_P(%a2),%a4
.LHr2:
        move.l  (%a4)+,%d0              | n c1 b k clg cli: halves
        move.w  %d0,(%a0)+
        move.l  (%a4)+,%d0
        move.w  %d0,(%a0)+
        move.l  (%a4)+,%d0
        move.w  %d0,(%a0)+
        move.l  (%a4)+,%d0
        move.w  %d0,(%a0)+
        move.l  (%a4)+,%d0
        move.w  %d0,(%a0)+
        move.l  (%a4)+,%d0
        move.w  %d0,(%a0)+
        move.l  (%a4)+,%d0              | cll: high half, low half
        swap    %d0
        move.w  %d0,(%a0)+
        swap    %d0
        move.w  %d0,(%a0)+
        move.l  (%a4)+,%d0              | w2 gcomp
        move.w  %d0,(%a0)+
        move.l  (%a4)+,%d0
        move.w  %d0,(%a0)+
        move.l  (%a4)+,%d0              | amp: high half, low half
        swap    %d0
        move.w  %d0,(%a0)+
        swap    %d0
        move.w  %d0,(%a0)+
        move.l  (%a4)+,%d0              | ampstep (signed, 16 bits)
        move.w  %d0,(%a0)+
        move.l  (%a4)+,%d0              | v9.1: flags, osin
        move.w  %d0,(%a0)+
        move.l  (%a4)+,%d0
        move.w  %d0,(%a0)+
        subq.l  #1,%d1
        bne     .LHr2
        lea     104(%a6),%a0            | w52: u, sixteen longs (high half first)
        lea     H_U(%a2),%a4
        moveq   #16,%d1
.LHr3:
        move.l  (%a4)+,(%a0)+
        subq.l  #1,%d1
        bne     .LHr3
        moveq   #1,%d0
        move.l  %d0,H_MODE(%a2)
        clr.l   H_NP(%a2)               | the next frame starts clean
        clr.l   H_START(%a2)
        bra     .Ldone
| .LHopen: a new piece, a4 = it: n = 0 and this sample's control words.  Clobbers d0 and d1 (both free at its
| two calls: before the loop, and after .LHclose, which clobbers them too).
.LHopen:
        move.l  H_NP(%a2),%d0
        cmp.l   #3,%d0                  | (three at most a frame: the call's, the control step's, the second
        bcs     .LHo1                   | call's; a fourth would write past the block: keep the third)
        moveq   #2,%d0
        subq.l  #1,H_NP(%a2)
.LHo1:
        addq.l  #1,H_NP(%a2)
        mulu.w  #52,%d0
        lea     H_P(%a2),%a4
        add.l   %d0,%a4
        moveq   #0,%d0
        move.l  %d0,(%a4)
        move.l  S_MUFF(%a3),%d1         | v9.1: flags: bit 0 FM, 2..1 MUFF, 3 DIST, 4 ACID, 5 KEEP
        add.l   %d1,%d1
        tst.l   S_DIST(%a3)
        beq     .LHo2
        addq.l  #8,%d1
.LHo2:
        moveq   #2,%d0
        cmp.l   S_SWP(%a3),%d0
        bne     .LHo3
        moveq   #16,%d0
        add.l   %d0,%d1
.LHo3:
        tst.l   S_FMQ(%a3)
        beq     .LHo4
        addq.l  #1,%d1                  | FM: the DSP sets c1 b k and the clip per sample from these four
        moveq   #1,%d0
        move.l  %d0,H_FMD(%a2)
        move.l  %d1,44(%a4)
        move.l  S_SCTRL(%a3),4(%a4)
        move.l  S_KMUL(%a3),8(%a4)
        move.l  S_UD(%a3),12(%a4)
        move.l  S_FMQ(%a3),16(%a4)
        bra     .LHo6
.LHo4:
        tst.l   H_FMD(%a2)              | no FM now, but FM moved the coefficients since the last control step:
        beq     .LHo5                   | the DSP keeps its own (ref303 keeps them to the next control step)
        moveq   #32,%d0
        add.l   %d0,%d1
.LHo5:
        move.l  %d1,44(%a4)
        move.l  S_C1(%a3),4(%a4)
        move.l  S_B(%a3),8(%a4)
        move.l  S_K(%a3),12(%a4)
        move.l  S_CLG(%a3),16(%a4)
.LHo6:
        move.l  S_OSIN(%a3),48(%a4)
        move.l  S_CLI(%a3),20(%a4)
        move.l  S_CLL(%a3),24(%a4)
        move.l  S_W2(%a3),28(%a4)
        move.l  S_GCOMP(%a3),32(%a4)
        move.l  S_AMP(%a3),36(%a4)
        move.l  S_AMPSTEP(%a3),40(%a4)
        rts
| .LHclose: the piece a4 ends: amp = max(0, amp + n * step); an empty piece is dropped.  Clobbers d0, d1.
.LHclose:
        move.l  (%a4),%d0
        bne     .LHc1
        subq.l  #1,H_NP(%a2)
        rts
.LHc1:
        move.l  40(%a4),%d1
        muls.l  %d0,%d1
        add.l   36(%a4),%d1
        bpl     .LHc2
        moveq   #0,%d1
.LHc2:
        move.l  %d1,S_AMP(%a3)
        rts
        .endif
.Ldone:
        tst.l   o3_pflag                | stopwatch: a call that ran the sample loop adds its times to its track's row
        beq     .Lpf_x
        clr.l   o3_pflag
        move.l  O3_DTCN3,%d1            | the call's end
        move.l  52(%sp),%d0             | track
        lsl.l   #5,%d0                  | 32 bytes a track
        lea     O3_PROF,%a0
        add.l   %d0,%a0
        addq.l  #1,(%a0)                | +0  calls
        move.l  %d1,%d0
        sub.l   o3_pt0,%d0
        add.l   %d0,4(%a0)              | +4  the whole call (counts of 132 MHz)
        cmp.l   8(%a0),%d0
        bls     .Lpf_1
        move.l  %d0,8(%a0)              | +8  its longest
.Lpf_1:
        move.l  o3_pt1,%d0
        sub.l   o3_pt0,%d0
        add.l   %d0,12(%a0)             | +12 entry to the loop: params, gate, the stock renderer's call
        sub.l   o3_pt1,%d1
        add.l   %d1,16(%a0)             | +16 the sample loop (with the control steps inside it)
        cmp.l   20(%a0),%d1
        bls     .Lpf_2
        move.l  %d1,20(%a0)             | +20 its longest
.Lpf_2:
        move.l  o3_pn,%d0
        add.l   %d0,24(%a0)             | +24 samples rendered
.Lpf_x:
        move.l  44(%sp),%d0
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     48(%sp),%sp
        rts

| ---- o3_voice: a0 := track d2's voice struct + V_POS.  Clobbers d0.
o3_voice:
        move.l  #VOICE_STRIDE,%d0
        muls.l  %d2,%d0
        lea     VOICE_BASE+V_POS,%a0    | (V_POS folded in: no lea through the a0 just written; #1244 b609e4ed)
        add.l   %d0,%a0
        rts

| ============================================================================
| o3_retrig -- Detour 0x4000c634 (8 bytes: `moveal 114(sp),a1; moveb (a0,a1.l),d0`,
| a0 = 0x46104d15): the frame builder's copy of a track's DSP command byte into the
| packer's nibble byte.  On an OCTA303 track any START form becomes the panel key's clean
| 0x30 (Tim's po_retrig, BUILD 37: a sequencer trig on a sounding voice is posted 0x10|n and
| the DSP crossfades its old voice under the new one -- one continuous stream twice, +5.6 dB).
| d0 = the byte, a0 / a1 as stock leaves them; d1 and a2 saved.
| ============================================================================
o3_retrig:
        movea.l 114(%sp),%a1            | displaced: the track
        lea     -8(%sp),%sp
        movem.l %d1/%a2,(%sp)
        move.l  %a1,%d1
        cmp.l   #NTRACKS,%d1
        bcc     .Lrt_out
        lsl.l   #8,%d1                 | track * ST_SIZE (512: 8 + 1)
        add.l   %d1,%d1
        lea     o3_state,%a2
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
| o3_page -- Detour 0x40031ece (6 bytes: `move.l 0(a0,d0.l*4),d0; bra.s 0x40031ed6`),
| the page resolver's PLAYBACK table load.  d0 = machine, a0 = table, d3 = track,
| d1 = part index, a1 = bank blob; d2-d5 restored by the resolver's epilogue, d0/d1/a0/a1
| scratch (poly.s po_lfopage's contract).  The TB-303 machine's track gets the machine's record
| (o3_mdesc); everything else the stock descriptor (v7.9: a TB303* sample too).
| ============================================================================
o3_page:
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_PAGE             | the entry state, for the next machine's resolver (a1: the bank blob, which
        lea     -16(%sp),%sp            | o3_basename below clobbers)
        movem.l %d0-%d1/%a0-%a1,(%sp)
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
        bsr     o3_sig
        tst.l   %d0
        beq     .Lpg_stock
        bsr     o3_mdesc
        bra     .Lpg_done
.Lpg_stock:
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_PAGE
.Lpg_not:                               | not ours: the next machine's resolver, as its own detour
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        jmp     MC_NEXT_PAGE
        .endif
        .endif
        move.l  %d5,%d0
.Lpg_done:
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_PAGE
        lea     16(%sp),%sp
        .endif
        .endif
        jmp     RESOLVER_RET

| ============================================================================
| o3_gate -- v6.5d, the 303's own gate (ref303.gate_frame), timed from the note's START in ticks
| (v6.5c timed it from the step word, which moves about a tick before the START arrives), once a frame on a 303 track (the
| frame's last call).  With the track's AMP HOLD at INF (the live lane, locks applied) a note
| sounds for half a step and stays on into the next step when that step holds a trigless trig
| or a trigless lock (a slide), as the 303's sequencer does; any other HOLD: S_GMODE 0, the AMP
| decides (v6.4 sample for sample).  The step and tick come from the sequencer (STEPW, TICKB),
| the ticks a step are measured, the slides read from the current pattern's track record.
| A sequencer standing still (GATE_IDLE frames) leaves the gate open.
| d2 = track, a3 = state.  Clobbers d0, d1, a0, a1; d3-d6 saved.
| ============================================================================
o3_gate:
        lea     -16(%sp),%sp
        movem.l %d3-%d6,(%sp)
        moveq   #16,%d6                 | the track's length (16 without a record)
        suba.l  %a1,%a1                 | a1 = the track record, 0 = none
        move.l  BANK_PTR,%d0
        beq     .Lg_len
        move.l  %d0,%a1
        mvz.b   PAT_IDX,%d0
        and.l   #15,%d0
        move.l  #PAT_STRIDE,%d1
        muls.l  %d1,%d0
        add.l   %d0,%a1
        move.l  %d2,%d0
        move.l  #TRK_STRIDE,%d1
        muls.l  %d1,%d0
        add.l   %d0,%a1
        mvz.b   0x50(%a1),%d6
.Lg_len:
        tst.l   %d6                     | 1..64, else 16
        beq     .Lg_l16
        moveq   #64,%d0
        cmp.l   %d0,%d6
        bls     .Lg_lok
.Lg_l16:
        moveq   #16,%d6
.Lg_lok:
        mvz.w   STEPW,%d3               | s = the step word mod L
        move.l  %d3,%d0
        divu.l  %d6,%d0
        mulu.l  %d6,%d0
        sub.l   %d0,%d3
        mvz.b   TICKB,%d4               | k
        moveq   #0,%d5                  | d5 bit 0 = the sequencer moved (a tick) since the last frame,
        move.l  S_IDLE(%a3),%d0         | bit 1 = it stood still GATE_IDLE frames (a restart),
        cmp.l   #GATE_IDLE,%d0          | bit 2 = v7.4: the transport word reads running (1)
        blt     .Lg_rs
        moveq   #2,%d5
.Lg_rs:
        moveq   #1,%d0
        cmp.l   TRANSPORT,%d0
        bne     .Lg_stp
        addq.l  #4,%d5
        bra     .Lg_rn
.Lg_stp:
        move.l  %d0,S_STOPD(%a3)        | v7.4: a STOP seen: the next move while running is a PLAY
.Lg_rn:
        cmp.l   S_LSTEP(%a3),%d3
        bne     .Lg_mv
        cmp.l   S_LTICK(%a3),%d4
        beq     .Lg_nmv
.Lg_mv:
        addq.l  #1,%d5
.Lg_nmv:
        cmp.l   S_LSTEP(%a3),%d3
        beq     .Lg_same
        move.l  S_KMAX(%a3),%d0         | a new step: the last one's ticks
        beq     .Lg_k0
        addq.l  #1,%d0
        move.l  %d0,S_TPS(%a3)
.Lg_k0:
        clr.l   S_KMAX(%a3)
        clr.l   S_IDLE(%a3)
        bra     .Lg_kmax
.Lg_same:
        cmp.l   S_LTICK(%a3),%d4
        beq     .Lg_idle
        clr.l   S_IDLE(%a3)
        bra     .Lg_kmax
.Lg_idle:
        move.l  S_IDLE(%a3),%d0
        cmp.l   #GATE_IDLE,%d0
        bge     .Lg_kmax
        addq.l  #1,%d0
        move.l  %d0,S_IDLE(%a3)
.Lg_kmax:
        cmp.l   S_KMAX(%a3),%d4
        ble     .Lg_k2
        move.l  %d4,S_KMAX(%a3)
.Lg_k2:
        move.l  %d3,S_LSTEP(%a3)
        move.l  %d4,S_LTICK(%a3)
        tst.l   S_TPS(%a3)
        bne     .Lg_tps
        moveq   #GATE_TPS0,%d0
        move.l  %d0,S_TPS(%a3)
.Lg_tps:
        btst    #0,%d5                  | v6.5d: the ticks since the START
        beq     .Lg_ne
        move.l  S_GEL(%a3),%d0
        cmp.l   #4096,%d0
        bge     .Lg_ne
        addq.l  #1,%d0
        move.l  %d0,S_GEL(%a3)
.Lg_ne:
        move.l  S_FCNT(%a3),%d0         | v7.0: the frames a tick, measured
        cmp.l   #4095,%d0
        bge     .Lg_f1
        addq.l  #1,%d0
.Lg_f1:
        btst    #0,%d5
        beq     .Lg_f3
        btst    #2,%d5                  | v7.4: a move while stopped (STOP resets the step word) is no tick
        beq     .Lg_f2
        tst.l   S_STOPD(%a3)            | PLAY after a stop (or GATE_IDLE still): the position reset and
        bne     .Lg_rst                 | the first tick come a frame apart (measured under the port):
        tst.l   S_FSEEN(%a3)            | v7.5: the first move a fresh state sees (the first PLAY after
        beq     .Lg_rst                 | boot) is a PLAY too
        btst    #1,%d5                  | skip GATE_FSKIP intervals, and restart the last note's clock
        beq     .Lg_sk                  | (no 1-frame snap before the START)
.Lg_rst:
        clr.l   S_STOPD(%a3)
        moveq   #GATE_FSKIP,%d1
        move.l  %d1,S_FSKIP(%a3)
        clr.l   S_GEL(%a3)
        clr.l   S_GELF(%a3)
.Lg_sk:
        move.l  S_FSKIP(%a3),%d1
        beq     .Lg_sk0
        subq.l  #1,%d1
        move.l  %d1,S_FSKIP(%a3)
        bra     .Lg_f2
.Lg_sk0:
        tst.l   S_FSEEN(%a3)
        beq     .Lg_f2
        move.l  %d0,S_FPT(%a3)
.Lg_f2:
        moveq   #1,%d1
        move.l  %d1,S_FSEEN(%a3)
        moveq   #0,%d0
.Lg_f3:
        move.l  %d0,S_FCNT(%a3)
        move.l  S_GELF(%a3),%d0         | v7.0: the frames since the START
        cmp.l   #65535,%d0
        bge     .Lg_f4
        addq.l  #1,%d0
        move.l  %d0,S_GELF(%a3)
.Lg_f4:
        tst.l   S_GNEW(%a3)
        beq     .Lg_nn
        clr.l   S_GNEW(%a3)             | a 303 START: open, the clock from 0, half a step to go
        moveq   #1,%d0
        move.l  %d0,S_GATE(%a3)
        clr.l   S_GEL(%a3)
        clr.l   S_GELF(%a3)
        move.l  S_TPS(%a3),%d0          | v7.0: 3.5 of the step's 6 clocks, doubled (Whittle)
        moveq   #7,%d1
        muls.l  %d1,%d0
        addq.l  #3,%d0
        moveq   #6,%d1
        divs.l  %d1,%d0
        move.l  %d0,S_GEND(%a3)
        move.l  %d3,%d1                 | v7.4: the step word holds the NEXT step (measured under the
        subq.l  #1,%d1                  | port): the note's step cur = (s - 1) mod L
        bpl     .Lg_cur
        move.l  %d6,%d1
        subq.l  #1,%d1
.Lg_cur:
        move.l  %d4,%d0                 | the note's step: past half a step, the next one's
        add.l   %d0,%d0
        cmp.l   S_TPS(%a3),%d0
        blt     .Lg_gs0
        move.l  %d1,%d0
        addq.l  #1,%d0
        cmp.l   %d6,%d0
        blt     .Lg_gs
        moveq   #0,%d0
        bra     .Lg_gs
.Lg_gs0:
        move.l  %d1,%d0
.Lg_gs:
        move.l  %d0,S_GSTEP(%a3)
.Lg_nn:
        tst.l   S_GSEL(%a3)             | v7.0: SETUP's GATE (v6.5: AMP HOLD INF)
        bne     .Lg_on
        clr.l   S_GMODE(%a3)            | OFF: the AMP decides
        move.l  #32767,%d0
        move.l  %d0,S_GLVL(%a3)
        bra     .Lg_out
.Lg_on:
        moveq   #1,%d0
        move.l  %d0,S_GMODE(%a3)
        move.l  S_IDLE(%a3),%d0
        cmp.l   #GATE_IDLE,%d0
        blt     .Lg_run
        moveq   #1,%d0                  | the sequencer stands still: open
        move.l  %d0,S_GATE(%a3)
        bra     .Lg_out
.Lg_run:
        tst.l   S_GATE(%a3)
        beq     .Lg_out
        move.l  S_FPT(%a3),%d1          | v7.0: 3.5 clocks (+ a step a tie) since the START, in frames
        beq     .Lg_tk
        move.l  S_GEND(%a3),%d0
        muls.l  %d1,%d0
        move.l  S_GELF(%a3),%d1
        add.l   %d1,%d1
        cmp.l   %d0,%d1
        blt     .Lg_out
        bra     .Lg_due
.Lg_tk:
        move.l  S_GEL(%a3),%d0          | no tick measured yet: in ticks
        add.l   %d0,%d0
        cmp.l   S_GEND(%a3),%d0
        blt     .Lg_out
.Lg_due:
        move.l  S_GSTEP(%a3),%d0        | nxt = (gstep + 1) mod L
        addq.l  #1,%d0
        cmp.l   %d6,%d0
        blt     .Lg_n1
        moveq   #0,%d0
.Lg_n1:
        move.l  %d0,%d4
        bsr     o3_slide
        beq     .Lg_close
        move.l  %d4,S_GSTEP(%a3)        | the next step slides: still on, one step more
        move.l  S_GEND(%a3),%d0
        add.l   S_TPS(%a3),%d0
        add.l   S_TPS(%a3),%d0
        move.l  %d0,S_GEND(%a3)
        bra     .Lg_out
.Lg_close:
        clr.l   S_GATE(%a3)
.Lg_out:
        movem.l (%sp),%d3-%d6
        lea     16(%sp),%sp
        rts

| ---- o3_slide: d0 = a step (0..63), a1 = the track record or 0 -> d0 = 1 (NE) when the step holds
|      a trigless trig (mask 1, +8) or a trigless lock (mask 2, +16): byte 7 - s/8, bit s%8.
|      Clobbers d1, a0.
o3_slide:
        move.l  %a1,%d1
        beq     .Lsl_no
        move.l  %a1,%a0
        move.l  %d0,%d1
        lsr.l   #3,%d1
        suba.l  %d1,%a0
        and.l   #7,%d0
        mvz.b   15(%a0),%d1
        btst    %d0,%d1
        bne     .Lsl_yes
        mvz.b   23(%a0),%d1
        btst    %d0,%d1
        bne     .Lsl_yes
.Lsl_no:
        moveq   #0,%d0
        rts
.Lsl_yes:
        moveq   #1,%d0
        rts

| ---- o3_fmt_tune: fmt(buf, value), C convention (modules/synth page.s pg_fmt_ptch).  v7.0: TUNE as a
|      note name, raw 64 = C3 (BASE_HZ), a semitone a step: raw 40..88 = C1..C5 ("C1", "C#3", "A4").  The knob,
|      the p-lock display (a trig held) and the page all print through it.  Writes the name itself (no
|      sprintf), returns its length in d0.  Scratch: d0, d1, a0, a1.
o3_fmt_tune:
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
        lea     o3_notes,%a1
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
| o3_chrom -- Detour 0x4004fc58 (jsr + 2 nops over 10 bytes: `lea (4,a2,a2.l*4),a2;
| mvz.b 0x100b14cf,d0`), the CHROMATIC key handler 0x4004fb94 (track d2, key index a2 =
| 0..24, 12 = TRIG 13) about to make the raw pitch 5 * idx + 4 that the voice is trigged with,
| a held or live-recorded trig's PTCH lock receives and the screen shows.  On the TB-303 machine
| (v7.9: no longer on a TB303* sample) the byte is semitones (v6.4): raw = 52 + idx = -12..+12, so
| keys and recorded locks play what they say (the knob and the locks reach +24).  Every other
| track: the stock lea.  The quantizer module's qz_chrom owns the same site: beside it, HOOKS
| overrides qz_chrom's detour and this one, built with HK_CHROM_PITCH, hands every other track
| to qz_chrom (modules/hooks, chrom_pitch).  Scratch: d0, d1, a0, a1 (as qz_chrom).
| ============================================================================
o3_chrom:
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
        adda.l  #PART_OFF,%a0           | v7.0: the TB-303 machine?
        move.l  %d2,%d0
        bsr     o3_sig
        tst.l   %d0
        beq     .Lch_stock
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

| ---- o3_pword: d0 = PTCH frame word -> d0 = p (Q8 semitones).  Clobbers d1.
|      v6.4, THE 3-OCTAVE TUNE (Tim Hastie's tuning system): on a 303 track the PTCH byte is
|      SEMITONES, raw 64 = 0, one raw unit a semitone (the page clone: TUNE -12..+24), so the
|      word is already Q8 semitones -- no /5.  Clamped to P_LO..P_HI (-36..+36: the knob's range
|      plus an octave of LFO either side; an old project's 5-a-semitone byte cannot scream).
o3_pword:
        sub.l   #0x4000,%d0
        add.l   #P_CENTER,%d0
        cmp.l   #P_LO,%d0
        bge     .Lpw1
        move.l  #P_LO,%d0
.Lpw1:
        cmp.l   #P_HI,%d0
        ble     .Lpw2
        move.l  #P_HI,%d0
.Lpw2:
        add.l   S_FINE(%a3),%d0         | v7.0: FINE, clamped again
        cmp.l   #P_LO,%d0
        bge     .Lpw3
        move.l  #P_LO,%d0
.Lpw3:
        cmp.l   #P_HI,%d0
        ble     .Lpw4
        move.l  #P_HI,%d0
.Lpw4:
        rts

| ---- o3_setupptr (v7.0): a0 = the track's six SETUP bytes (o3tables.SETUP_NAMES): the live lane's
|      +0x20..+0x25 (track d2), locks applied.  Only the machine's tracks get here (v7.9: the TB303*
|      sample's neutral SETUP is gone).  Clobbers a0 only.
o3_setupptr:
        move.l  %d0,-(%sp)
        moveq   #CV_STRIDE,%d0
        muls.l  %d2,%d0
        lea     CURVALS+LANE_SETUP,%a0
        add.l   %d0,%a0
        move.l  (%sp)+,%d0
        rts

| ---- o3_setup (v7.0): the SETUP page into the state: S_ACCVG (ACCV), S_FINE, S_OSIN (DRIV).
|      SLID is o3_params' last step (dEVILish's SLID wins).  Clobbers d0, d1, a0, a1.
o3_setup:
        bsr     o3_setupptr
        KB      5,%a0                   | ACCV raw (v7.8): the accent's VCA level x ACCV / 64
        move.l  %d0,S_ACCVG(%a3)
        KB      2,%a0                   | FINE: (FINE - 64) * FINE_Q8
        sub.l   #64,%d0
        moveq   #FINE_Q8,%d1
        muls.l  %d1,%d0
        move.l  %d0,S_FINE(%a3)
        KBTAB   4,%a0,O3_DRV_G           | DRIV: the gain into the output mixer (v7.7)
        move.l  %d1,S_OSIN(%a3)
        KB      1,%a0                   | GATE: 0 OFF, >= 1 303
        tst.l   %d0
        beq     .Lsu_g
        moveq   #1,%d0
.Lsu_g:
        move.l  %d0,S_GSEL(%a3)
        rts

| ============================================================================
| v7.0 -- THE TB-303 MACHINE: row 5 of the track's machine list (STATIC FLEX THRU NEIGHBOR PICKUP
| TB-303).  The seams are the ones repeat98's ANALOG BD measured (modules/analog-bassdrum machine.s,
| control.c), ported to assembly for one machine: the track is stored as FLEX and signed 'T','B',1 in
| its NEIGHBOR PLAYBACK bytes (Part' + 0x3c + 30*track, which NEIGHBOR does not use); every hook asks
| o3_type, which reads a signed FLEX track as machine 5.  Its pages are one record (o3_mdesc, a clone
| of the user's FLEX record): PLAYBACK TUNE CUT RES ENV DEC ACC (the FLEX slots, as a TB303* sample's
| track had until v7.9), SETUP WAVE GATE FINE SLID DRIV ACCV (FLEX's SETUP slots, Part' + 0x1e0 + 30*track, the live
| lane +0x20).  The stock validator sees FLEX's defaults in a signed track's twelve bytes (o3_validate).
| Part' = BANK + PART_OFF + part * PART_SIZE (the machine bytes at +0x22, ANALOG BD's form).
| ============================================================================
        .if     HK_MACHINE_ROWS
        .set    O3_ROW,         MC_ROW          | beside other machines: our place in the chain (modules/hooks)
        .global o3_type, o3_title, o3_publish
        .else
        .set    O3_ROW,         5               | the machine's row and UI type
        .endif
        .set    SIG_OFF,        0x3c            | Part' + 0x3c + 30*track: 'T', 'B', 1
        .set    PB_FLEX,        0x8edb0         | Part + 0x8edaa + 6 * FLEX: the FLEX PLAYBACK knobs (+30 a track)
        .set    PB_SHADOW,      0x1001614e      | shadow = Part offset + this (modules/mode-defaults' bases agree)
        .set    SRAM_PART,      0x100a4ece      | the shadow of Part 0's Part' (PB_SHADOW + PART_OFF)
        .set    SRC_CURSOR,     0x460d5c30      | SRC SETUP's selected row
        .set    PB_TABLE,       0x400d5f38      | the PLAYBACK records by UI type (5: stock NEIGHBOR's)
        .set    STOCK_DEFS,     0x400d320c      | FLEX_P + 0x5e: FLEX's twelve defaults
        .set    PAGE2_GAP,      0x1b0           | SETUP bytes - PLAYBACK bytes (0x1da - 0x2a)

        .global o3_machine_name, o3_src_names, o3_name_a, o3_name_b, o3_setup_row, o3_chooser_row
        .global o3_setup_open, o3_chooser_open, o3_tick, o3_main_commit, o3_src_commit, o3_src_commit2
        .global o3_setup_edit6, o3_setup_draw6, o3_validate

| ---- o3_sig: a0 = Part', d0 = track -> d0 = 1 when the track is the TB-303 machine (FLEX, signed),
|      else 0 (flags set).  Clobbers d1.
o3_sig:
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
        cmp.l   #0x54,%d1               | 'T'
        bne     .Lsg_no
        move.b  SIG_OFF+1(%a1),%d1
        cmp.l   #0x42,%d1               | 'B'
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

| ---- o3_curpart: a0 = the current part's Part', d1 = 1 (0 when the bank pointer is not set: a0 junk).
o3_curpart:
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

| ---- o3_sigcur: d0 = track -> d0 = 1 when it is the TB-303 machine in the current part.  Clobbers d1, a0.
o3_sigcur:
        bsr     o3_curpart
        tst.l   %d1
        bne     o3_sig
        moveq   #0,%d0
        rts

| ---- the limit: O3_MAX signed tracks in a Part.  Each voice costs about 9 points of the ColdFire's frame interrupt
|      and the first about 21 more (one MKII, 2 Nov 2026: 2 machines 65 %, 4 machines 83 %, ~102 % extrapolated for 6),
|      and the panel starves near 98 %.
        .if     HK_MACHINE_ROWS
        .set    O3_MAX,         MC_LIMIT        | beside other machines: one limit for all of them (modules/hooks)
        .else
        .set    O3_MAX,         2
        .endif

| ---- o3_anysig: a0 = Part', d0 = track -> d0 = 1 when the track is FLEX and signed by ANY machine on
|      the list (the three signature bytes against mc_sig_table), else 0 (flags set).  Clobbers d1; a0, a1 kept.
|      The limit counts these, so a Part holds O3_MAX machines of every kind together.
        .if     HK_MACHINE_ROWS
o3_anysig:
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
        lea     o3_sigtab,%a0
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
o3_sigtab:
        mc_sig_table
        .macro  O3_ANYSIG
        bsr     o3_anysig
        .endm
        .else
        .macro  O3_ANYSIG
        bsr     o3_sig
        .endm
        .endif

| ---- o3_nsigned: a0 = Part', d0 = a track -> d0 = the signed tracks of the Part other than that one.  Saves all else.
o3_nsigned:
        lea     -16(%sp),%sp
        movem.l %d1-%d4,(%sp)
        move.l  %d0,%d3
        moveq   #0,%d2
        moveq   #7,%d4
.Lnsg_l:
        cmp.l   %d3,%d4
        beq     .Lnsg_n
        move.l  %d4,%d0
        O3_ANYSIG
        add.l   %d0,%d2
.Lnsg_n:
        subq.l  #1,%d4
        bpl     .Lnsg_l
        move.l  %d2,%d0
        movem.l (%sp),%d1-%d4
        lea     16(%sp),%sp
        rts

| ---- o3_sigcur_lim: d0 = track -> d0 = 1 when it is a signed track among the first O3_MAX of the current Part
|      (a project loaded with more has the rest play as plain FLEX).  Clobbers d1, a0.
o3_sigcur_lim:
        move.l  %d0,-(%sp)
        bsr     o3_sigcur
        beq     .Llim_x
        bsr     o3_curpart                      | a0 = Part'
        move.l  (%sp),%d0
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        move.l  %d0,%d3
        moveq   #0,%d2                          | the signed tracks below this one
        subq.l  #1,%d3
        bmi     .Llim_cnt
.Llim_l:
        move.l  %d3,%d0
        O3_ANYSIG
        add.l   %d0,%d2
        subq.l  #1,%d3
        bpl     .Llim_l
.Llim_cnt:
        moveq   #0,%d0
        cmp.l   #O3_MAX,%d2
        bcc     .Llim_no
        moveq   #1,%d0
.Llim_no:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
.Llim_x:
        addq.l  #4,%sp
        tst.l   %d0
        rts

| ---- o3_type (ANALOG BD's ab_type): d0 = a machine byte, a0 = where it was read -> d0 = O3_ROW when
|      the byte is the current part's track machine byte (Part' + 0x22 + track) of a signed track,
|      else d0 unchanged.  Everything else kept.
o3_type:
        lea     -12(%sp),%sp
        movem.l %d1/%a0-%a1,(%sp)
        moveq   #1,%d1
        cmp.l   %d1,%d0
        bne     .Lty_x
        move.l  %a0,%a1
        bsr     o3_curpart
        tst.l   %d1
        beq     .Lty_1
        move.l  %a1,%d1
        sub.l   %a0,%d1
        sub.l   #0x22,%d1               | the track, if a1 is a machine byte
        cmp.l   #7,%d1
        bhi     .Lty_1
        move.l  %d1,%d0
        bsr     o3_sig
        beq     .Lty_1
        moveq   #O3_ROW,%d0
        bra     .Lty_x
.Lty_1:
        moveq   #1,%d0
.Lty_x:
        movem.l (%sp),%d1/%a0-%a1
        lea     12(%sp),%sp
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_TYPE
        cmp.l   #O3_ROW,%d0
        beq     .Lty_rts
        jmp     MC_NEXT_TYPE            | not ours: the next machine's (it keeps all but d0)
.Lty_rts:
        .endif
        .endif
        rts

| ---- o3_sigwrite (ab_sig_write): a0 = Part' (in the bank blob), d0 = track, d1 = 1 sign / 0 unsign,
|      in the Part and its shadow.  Signing an unsigned copy first writes the machine's twelve defaults
|      (o3_mdefs) into its FLEX PLAYBACK and SETUP bytes; unsigning clears our signature only.  A
|      signed track of the current part gets its twelve bytes into the live lane too.  Everything kept.
o3_sigwrite:
        lea     -20(%sp),%sp
        movem.l %d0-%d2/%a0-%a1,(%sp)
        tst.l   %d1
        beq     .Lsw_ok                 | unsigning is never refused
        bsr     o3_nsigned              | signing: a third machine in the Part is refused (the callers store FLEX)
        cmp.l   #O3_MAX,%d0
        bcs     .Lsw_ok
        pea     0x30
        pea     o3_maxmsg
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
        bsr     o3_curpart
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
.Lsw_done:
        movem.l (%sp),%d0-%d2/%a0-%a1
        lea     20(%sp),%sp
        rts
.Lsw_one:                               | a1 = a copy's signature; clobbers d0, d2, a0
        moveq   #0,%d0                  | d0 = 1: this copy is signed
        moveq   #0,%d2
        move.b  (%a1),%d2
        cmp.l   #0x54,%d2
        bne     .Lsw_s
        move.b  1(%a1),%d2
        cmp.l   #0x42,%d2
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
        lea     o3_mdefs,%a0
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
        moveq   #0x54,%d2
        move.b  %d2,(%a1)
        moveq   #0x42,%d2
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

| ---- o3_mdesc: d0 = the machine's record (built once).  Clobbers d0, d1, a0, a1.
o3_mdesc:
        lea     FLEX_P,%a0
        lea     o3_mover,%a1
        bra     o3_clone

| ---- the hooks (ANALOG BD's, the same sites and contracts) ---------------------------------------
| o3_machine_name -- Detour 0x400334d8 (`move.l d2,-(sp); move.l 8(sp),d1`): name(row) -> d0.
o3_machine_name:
        move.l  4(%sp),%d0
        cmp.l   #O3_ROW,%d0
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
        lea     o3_title,%a0
        move.l  %a0,%d0
        rts

| o3_src_names -- the lea at 0x4003c928: SRC SETUP's names, six rows.
        .align  4
o3_src_names:
        .long   0x400b3eac, 0x400b3e98, 0x400b7c67, 0x400b5413, 0x400b7a63, o3_title
        .if     HK_MACHINE_ROWS
        mc_names_tail                   | the other machines' names, in row order
        .endif

| o3_name_a / o3_name_b -- Detours 0x4003d718 / 0x4004c36a (`lea 0x400a78c8,a0`; then d1 = name[d0]).
o3_name_a:
        bsr     o3_name_pick
        jmp     0x4003d722
o3_name_b:
        bsr     o3_name_pick
        jmp     0x4004c374
o3_name_pick:
        bsr     o3_type
        lea     o3_src_names,%a0
        move.l  (%a0,%d0.l*4),%d1
        rts

| o3_lfo_name -- Detour 0x4003bff0 (`mvs.b (a0),d0; lea 0x400d5f38,a0`, 8 bytes) in the LFO PMTR
| formatter 0x4003bf64 (the LFO SETUP destination, read 23 Oct 2026 from the user's 1.40C): for a
| PLAYBACK destination it takes the track's machine (a0 = Part + 0x8eda2 + track, d1 = the track)
| and indexes PB_TABLE, so an OCTA-303 track (stored FLEX) drew FLEX's PTCH STRT LEN RATE RTRG
| RTIM.  On a signed track the machine's record goes to a2 (its names TUNE CUT RES ENV DEC ACC,
| as o3_page gives the SRC page) and the formatter resumes after its own lookup, 0x4003c058;
| every other track: HOOKS LFO_NAME next (CX OSC's po_lfdname) when present, else reload the
| machine into d0 (o3_sig clobbered it on an unsigned FLEX miss), the displaced lea, and
| 0x4003c054.  The formatter keeps d1 (the track), d2 (the slot) and a4 (the buffer) across
| here; scratch d0, a0, a1.
o3_lfo_name:
        move.l  %a0,-(%sp)              | entry a0 (machine byte) for the next machine
        mvs.b   (%a0),%d0               | displaced: the machine
        moveq   #1,%d3
        cmp.l   %d3,%d0                 | FLEX
        bne     .Llf_other
        move.l  %d1,-(%sp)
        suba.l  %d1,%a0
        suba.l  #0x22,%a0               | Part' (Part + 0x8ed80)
        move.l  %d1,%d0
        bsr     o3_sig                  | (clobbers d1)
        beq     .Llf_flex
        bsr     o3_mdesc                | d0 = the machine's record (keeps d2, a2, a3)
        move.l  (%sp)+,%d1
        addq.l  #4,%sp                  | drop entry a0
        movea.l %d0,%a2
        jmp     0x4003c058
.Llf_flex:
        move.l  (%sp)+,%d1
.Llf_other:
        move.l  (%sp)+,%a0              | restore entry a0
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_LFO_NAME
        jmp     MC_NEXT_LFO_NAME        | CX OSC (or next): entered as at the site
        .endif
        .endif
        mvs.b   (%a0),%d0               | machine again (o3_sig clobbered d0 on FLEX miss)
        lea     PB_TABLE,%a0            | displaced
        jmp     0x4003c054

| ---- v7.1 (23 Oct 2026): the TB-303's UP / DOWN and its slide, on the step locks ------------
| A step's TUNE lock is byte 0 of its 32 lock bytes: bank blob + pattern * 0x8ed8 + track * 0x91a
| + 0x59 + step * 32 (0xff = not locked), mirrored at 0x1001614e + the same offset (the battery-
| backed copy of the current bank's patterns); the stock knob-lock writer (0x40050e60) writes
| both, then sets bank + 0x9b332 and 0x100f8598 (edited) and calls 0x40027e00
| (docs/firmware/STEP_LOCKS.md sections 1, 2).
        .set    TRK_STRIDE,     0x91a
        .set    PAT_STRIDE,     0x8ed8
        .set    LOCK_OFF,       0x59            | the step's 32 lock bytes in the track record
        .set    LOCK_SHADOW,    0x1001614e      | the battery-backed copy of the bank's patterns
        .set    CUR_TRACK,      0x100b14cc      | the UI's track
        .set    MIDI_MODE,      0x80000012      | non-zero: the UI is on the MIDI tracks
        .set    HELD_TRIGS,     0x460d174a      | u16: the held trig keys (bit k = key k)
        .set    HELD_PAGE,      0x460d174c      | the first step of the trig keys' page
        .set    TRIG_PAGE,      0x460d1e04      | the page the trig keys place on (0..3)
        .set    BANK_EDITED,    0x9b332         | bank + this, and 0x100f8598: the edited marks
        .set    NOTIFY,         0x4005a2b8      | NOTIFY(text, duration): the stock toast
        .set    O3_TLO,         64 + TUNE_LO    | raw TUNE range 40..88 (C1..C5)
        .set    O3_THI,         64 + TUNE_HI

| ---- o3_cur303: -> d0 = the UI's track when it is an OCTA-303 audio track, else -1 (flags set).
|      Clobbers d1, a0, a1.
o3_cur303:
        tst.l   MIDI_MODE
        bne     .Lc3_no
        mvz.b   PART_IDX,%d0
        move.l  #PART_SIZE,%d1
        muls.l  %d1,%d0
        movea.l BANK_PTR,%a0
        adda.l  %d0,%a0
        adda.l  #PART_OFF,%a0           | Part'
        mvz.b   CUR_TRACK,%d0
        bsr     o3_sig                  | (clobbers d1)
        beq     .Lc3_no
        mvz.b   CUR_TRACK,%d0
        tst.l   %d0
        rts
.Lc3_no:
        moveq   #-1,%d0
        rts

| ---- o3_tunelock: d0 = track, d1 = step -> a0 = its TUNE lock byte in the bank blob, a1 = the
|      same byte in the battery-backed copy.  Clobbers d0, d1, d2.
o3_tunelock:
        move.l  #TRK_STRIDE,%d2
        muls.l  %d2,%d0
        lsl.l   #5,%d1
        add.l   %d1,%d0
        mvz.b   PAT_IDX,%d1
        and.l   #15,%d1
        move.l  #PAT_STRIDE,%d2
        muls.l  %d2,%d1
        add.l   %d1,%d0
        add.l   #LOCK_OFF,%d0
        movea.l BANK_PTR,%a0
        adda.l  %d0,%a0
        lea     LOCK_SHADOW,%a1
        adda.l  %d0,%a1
        rts

| ---- o3_basetune: d0 = track -> d0 = the Part's TUNE (raw).  Clobbers d1; keeps a0, a1.
o3_basetune:
        move.l  %a0,-(%sp)
        moveq   #30,%d1
        muls.l  %d0,%d1
        movea.l BANK_PTR,%a0
        adda.l  %d1,%a0
        mvz.b   PART_IDX,%d1
        move.l  #PART_SIZE,%d0
        muls.l  %d1,%d0
        adda.l  %d0,%a0
        adda.l  #PB_FLEX,%a0
        mvz.b   (%a0),%d0
        movea.l (%sp)+,%a0
        rts

| o3_octave -- Detour 0x400434d8 (`lea -28(sp),sp; movem.l d2-d7/a2,(sp)`, 8 bytes), the entry of
| the held-trig layer's UP / DOWN handler (table 0x400becda; read 23 Oct 2026): stock opens the
| sample-lock list on a STATIC or FLEX track.  On an OCTA-303 track there is no sample: UP raises
| and DOWN lowers each held step's TUNE lock by an octave (a step without one starts from the
| Part's TUNE), as the TB-303's UP / DOWN; a note past C1..C5 stays where it is.  The toast names
| the note ("C4 +OCT").  handler(keycode @4, event @8); d2-d7 / a2-a6 are the caller's.
o3_octave:
        bsr     o3_cur303
        bmi     .Loc_stock
        lea     -40(%sp),%sp
        movem.l %d2-%d7/%a2-%a5,(%sp)
        move.l  %d0,%d4                 | the track
        moveq   #12,%d5
        moveq   #0x33,%d0
        cmp.l   44(%sp),%d0             | UP
        beq     .Loc_up
        moveq   #-12,%d5
.Loc_up:
        mvz.w   HELD_TRIGS,%d6
        move.l  HELD_PAGE,%d7
        moveq   #0,%d3                  | the key
        movea.l #-1,%a5                 | the last note written
.Loc_key:
        btst    %d3,%d6
        beq     .Loc_next
        move.l  %d4,%d0
        move.l  %d7,%d1
        add.l   %d3,%d1                 | the step
        bsr     o3_tunelock
        mvz.b   (%a0),%d0
        cmp.l   #0xff,%d0
        bne     .Loc_have
        move.l  %d4,%d0
        bsr     o3_basetune
.Loc_have:
        add.l   %d5,%d0
        moveq   #O3_TLO,%d1
        cmp.l   %d1,%d0
        blt     .Loc_next               | past C1: unchanged
        moveq   #O3_THI,%d1
        cmp.l   %d1,%d0
        bgt     .Loc_next               | past C5: unchanged
        move.b  %d0,(%a0)
        move.b  %d0,(%a1)
        movea.l %d0,%a5
.Loc_next:
        addq.l  #1,%d3
        moveq   #16,%d0
        cmp.l   %d0,%d3
        blt     .Loc_key
        move.l  %a5,%d0
        bmi     .Loc_done               | nothing moved
        movea.l BANK_PTR,%a0
        moveq   #1,%d1
        move.l  #BANK_EDITED,%d0
        move.l  %d1,(%a0,%d0.l)
        move.l  %d1,0x100f8598
        jsr     0x40027e00
        move.l  %d4,-(%sp)
        jsr     0x4009da20              | as the knob-lock writer, after its stores
        addq.l  #4,%sp
        move.l  %a5,-(%sp)              | the toast: the note and the direction
        pea     o3_obuf
        jsr     o3_fmt_tune             | d0 = its length
        addq.l  #8,%sp
        lea     o3_obuf,%a0
        adda.l  %d0,%a0
        move.b  #0x20,(%a0)+
        moveq   #0x2b,%d0               | '+'
        tst.l   %d5
        bpl     .Loc_sign
        moveq   #0x2d,%d0               | '-'
.Loc_sign:
        move.b  %d0,(%a0)+
        move.b  #0x4f,(%a0)+            | "OCT"
        move.b  #0x43,(%a0)+
        move.b  #0x54,(%a0)+
        clr.b   (%a0)
        pea     0x30
        pea     o3_obuf
        jsr     NOTIFY
        addq.l  #8,%sp
.Loc_done:
        movem.l (%sp),%d2-%d7/%a2-%a5
        lea     40(%sp),%sp
        jmp     0x40027de4              | the stock handler's own tail
.Loc_stock:
        lea     -28(%sp),%sp            | displaced
        movem.l %d2-%d7/%a2,(%sp)
        jmp     0x400434e0

| o3_trig_in / o3_trig_out -- the trig keys (read 23 Oct 2026, and under the port with a PC watch):
| the dispatcher 0x40060b58(key, event) sends a press (event 1) to 0x40050f20, which places or
| removes the trig (FUNC + TRIG sets the trigless lock there), and a release (event 0) to the
| handler 0x4005fb44.  On an OCTA-303 track a trigless trig or a trigless lock is a slide
| (o3_slide), so the step gets the note it slides from, as the TB-303's slide ties into the next
| step: the TUNE lock is written at once.  Press (Detour 0x40060b58, `lea -12(sp),sp;
| movem.l d2-d4,(sp)`): the track's trigless masks (+8 trigless trigs, +16 trigless locks) are
| kept, once until the next release.  Release (Detour 0x40060b3e, `movem.l 4(sp),d2-d7/a2-a5;
| lea 44(sp),sp`, the handler's tail before its jmp 0x40027de4): every step whose trigless bit is
| new gets, when it has no TUNE lock, the note of the previous step that has a trig, a trigless
| trig or a trigless lock (its TUNE lock, or the Part's TUNE).  Comparing the masks, rather than
| following the branches, makes the rule the same for every key chord that makes a slide.
o3_trig_in:
        lea     -12(%sp),%sp            | displaced
        movem.l %d2-%d4,(%sp)
        moveq   #1,%d0
        cmp.l   20(%sp),%d0             | a press?
        bne     .Lti_out
        tst.l   o3_snapt
        bpl     .Lti_out                | one kept already, until a release
        bsr     o3_cur303               | (d0, d1, a0, a1)
        bmi     .Lti_out
        move.l  %d0,o3_snapt
        move.l  %d0,%d2
        bsr     o3_trackrec             | a0 = the track record
        lea     o3_snap,%a1
        move.l  8(%a0),(%a1)+           | +8 .. +23: the trigless trigs and the trigless locks
        move.l  12(%a0),(%a1)+
        move.l  16(%a0),(%a1)+
        move.l  20(%a0),(%a1)
.Lti_out:
        jmp     0x40060b60

o3_trig_out:
        move.l  o3_snapt,%d4
        bmi     .Lto_out
        bsr     o3_cur303
        cmp.l   %d4,%d0
        bne     .Lto_out                | not the same OCTA-303 track any more
        move.l  %d4,%d2
        bsr     o3_trackrec
        movea.l %a0,%a4                 | the track record
        moveq   #0,%d5                  | the step
.Lto_step:
        move.l  %d5,%d0
        lsr.l   #3,%d0
        moveq   #7,%d1
        sub.l   %d0,%d1                 | byte 7 - s / 8
        move.l  %d5,%d2
        and.l   #7,%d2                  | bit s % 8
        mvz.b   8(%a4,%d1.l),%d0        | trigless trigs now
        mvz.b   16(%a4,%d1.l),%d3       | trigless locks now
        or.l    %d3,%d0
        lea     o3_snap,%a0
        mvz.b   (%a0,%d1.l),%d3
        mvz.b   8(%a0,%d1.l),%d6
        or.l    %d6,%d3                 | before
        not.l   %d3
        and.l   %d3,%d0                 | new
        btst    %d2,%d0
        beq     .Lto_next
        move.l  %d4,%d0
        move.l  %d5,%d1
        bsr     o3_autoslide
.Lto_next:
        addq.l  #1,%d5
        moveq   #64,%d0
        cmp.l   %d0,%d5
        blt     .Lto_step
.Lto_out:
        moveq   #-1,%d0
        move.l  %d0,o3_snapt
        movem.l 4(%sp),%d2-%d7/%a2-%a5  | displaced
        lea     44(%sp),%sp
        jmp     0x40060b48

| ---- o3_trackrec: d2 = track -> a0 = its record in the current pattern.  Clobbers d0, d1.
o3_trackrec:
        mvz.b   PAT_IDX,%d0
        and.l   #15,%d0
        move.l  #PAT_STRIDE,%d1
        muls.l  %d1,%d0
        movea.l BANK_PTR,%a0
        adda.l  %d0,%a0
        move.l  #TRK_STRIDE,%d0
        muls.l  %d2,%d0
        adda.l  %d0,%a0
        rts

| ---- o3_autoslide: d0 = track, d1 = step, a4 = the track record: a step without a TUNE lock gets
|      the note it slides from (above).  Clobbers d0-d3, d6, d7, a0-a3; keeps d4, d5, a4.
o3_autoslide:
        move.l  %d1,%d6                 | the step
        move.l  %d0,-(%sp)              | the track
        bsr     o3_tunelock
        movea.l (%sp)+,%a1
        mvz.b   (%a0),%d0
        cmp.l   #0xff,%d0
        bne     .Las_x                  | locked already
        movea.l %a0,%a2                 | the step's lock byte
        movea.l %a2,%a3
        suba.l  BANK_PTR,%a3
        adda.l  #LOCK_SHADOW,%a3        | and its copy
        moveq   #1,%d3                  | k: steps back
.Las_back:
        move.l  %d6,%d1
        sub.l   %d3,%d1
        and.l   #63,%d1                 | the step k back (64 steps around)
        move.l  %d1,%d0
        lsr.l   #3,%d0
        neg.l   %d0
        addq.l  #7,%d0                  | byte 7 - s / 8
        mvz.b   (%a4,%d0.l),%d2         | trigs
        mvz.b   8(%a4,%d0.l),%d7        | trigless trigs
        or.l    %d7,%d2
        mvz.b   16(%a4,%d0.l),%d7       | trigless locks
        or.l    %d7,%d2
        move.l  %d1,%d0
        and.l   #7,%d0
        btst    %d0,%d2
        bne     .Las_found
        addq.l  #1,%d3
        moveq   #64,%d0
        cmp.l   %d0,%d3
        blt     .Las_back
        bra     .Las_base               | no note before it: the Part's TUNE
.Las_found:
        lsl.l   #5,%d1
        mvz.b   LOCK_OFF(%a4,%d1.l),%d0
        cmp.l   #0xff,%d0
        bne     .Las_write
.Las_base:
        move.l  %a1,%d0                 | the track
        bsr     o3_basetune
.Las_write:
        move.b  %d0,(%a2)
        move.b  %d0,(%a3)
        movea.l BANK_PTR,%a0            | the edited marks, as the knob-lock writer
        moveq   #1,%d1
        move.l  #BANK_EDITED,%d0
        move.l  %d1,(%a0,%d0.l)
        move.l  %d1,0x100f8598
.Las_x:
        rts

| o3_setup_row -- Detour 0x4003c980 (`mvs.b (a0),d0; lea 24(sp),sp`): the row SRC SETUP highlights.
o3_setup_row:
        mvs.b   (%a0),%d0
        lea     24(%sp),%sp
        bsr     o3_type
        jmp     0x4003c986

| o3_chooser_row -- Detour 0x400786c8 (`mvs.b (a0),d0; cmp.l d0,d2; bne 0x400786fc`).
o3_chooser_row:
        mvs.b   (%a0),%d0
        bsr     o3_type
        cmp.l   %d0,%d2
        bne     .Lcr_no
        jmp     0x400786ce
.Lcr_no:
        jmp     0x400786fc

| o3_setup_open -- Detour 0x400585dc (`move.b (a0),d3; mvs.b d3,d4; pea 0x400bb704`).
o3_setup_open:
        move.b  (%a0),%d3
        move.l  %d0,-(%sp)
        mvs.b   %d3,%d0
        bsr     o3_type
        move.l  %d0,%d3
        move.l  (%sp)+,%d0
        mvs.b   %d3,%d4
        pea     0x400bb704
        jmp     0x400585e6

| o3_chooser_open -- Detour 0x40078886 (`mvs.b (a0),d0; move.l d0,-(sp); pea 0x460e7386`).
o3_chooser_open:
        mvs.b   (%a0),%d0
        bsr     o3_type
        move.l  %d0,-(%sp)
        pea     0x460e7386
        jmp     0x40078890

| o3_tick -- Detour 0x4005221e (`jsr 0x4005213c; jsr 0x4007e940`): publish the machine's record as UI
| type 5's (the SETUP editor and drawer index PB_TABLE by the type o3_type returns).
o3_tick:
        jsr     0x4005213c
        jsr     0x4007e940
        bsr     o3_mdesc
        move.l  %d0,PB_TABLE+4*O3_ROW
        .if     HK_MACHINE_ROWS
        mc_publish                      | each other machine's record as its row's type
        .endif
        jmp     0x40052228
        .if     HK_MACHINE_ROWS
| o3_publish -- the same record from ANALOG BD's tick hook (ab_tick_hook), which owns the site.
o3_publish:
        bsr     o3_mdesc
        move.l  %d0,PB_TABLE+4*O3_ROW
        rts
        .endif

| o3_main_commit -- Detour 0x4007981c (`mvs.b (a0),d3; move.b d4,(a0); add.l d1,d0`): the machine list's
| commit, a1 = bank, d0 = part * PART_SIZE, d1 = track, d4 = the row.  Row 5 signs the track and stores FLEX.
o3_main_commit:
        lea     -12(%sp),%sp
        movem.l %d0-%d1/%a0,(%sp)
        movea.l %a1,%a0
        adda.l  %d0,%a0
        adda.l  #PART_OFF,%a0
        move.l  %d1,%d0
        moveq   #0,%d1
        cmp.l   #O3_ROW,%d4
        bne     .Lmc_w
        moveq   #1,%d1
        moveq   #1,%d4                  | FLEX
.Lmc_w:
        bsr     o3_sigwrite
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_MAIN_COMMIT
        tst.l   %d1                     | 0: not our row (o3_sigwrite keeps d1)
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

| o3_src_commit / 2 -- Detours 0x4005a616 / 0x4005a850 (`move.l SRC_CURSOR,d1`, then `move.b d1,(a0)`):
| SRC SETUP's two commits, a1 = bank, d0 = part * PART_SIZE, d2 = track.
o3_src_commit:
        pea     0x4005a61c
        bra     .Lsrc
o3_src_commit2:
        pea     0x4005a856
.Lsrc:
        move.l  SRC_CURSOR,%d1
        lea     -12(%sp),%sp
        movem.l %d0/%d2/%a0,(%sp)
        movea.l %a1,%a0
        adda.l  %d0,%a0
        adda.l  #PART_OFF,%a0
        move.l  %d2,%d0
        cmp.l   #O3_ROW,%d1
        bne     .Lsrc_o
        moveq   #1,%d1
        bsr     o3_sigwrite
        moveq   #1,%d1                  | FLEX
        bra     .Lsrc_go
.Lsrc_o:
        move.l  %d1,-(%sp)
        moveq   #0,%d1
        bsr     o3_sigwrite
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

| o3_setup_edit6 / o3_setup_draw6 -- Detours 0x4003a52e / 0x4003cd98 (6 * machine): SETUP's editor and
| drawer address the machine's bytes as FLEX's (Part' + 0x1da + 6 * 1 + 30 * track).
o3_setup_edit6:
        .if     HK_MACHINE_ROWS
        cmp.l   #5,%d2                  | any machine's row (ours and the others'): FLEX's bytes
        bcs     .Le6
        cmp.l   #MC_ROWS_END,%d2
        bcc     .Le6
        moveq   #1,%d2
        .else
        cmp.l   #O3_ROW,%d2
        bne     .Le6
        moveq   #1,%d2
        .endif
.Le6:
        move.l  %d2,%d0
        lsl.l   #3,%d0
        add.l   %d2,%d2
        sub.l   %d2,%d0
        jmp     0x4003a536
o3_setup_draw6:
        .if     HK_MACHINE_ROWS
        cmp.l   #5,%d6
        bcs     .Ld6
        cmp.l   #MC_ROWS_END,%d6
        bcc     .Ld6
        moveq   #1,%d6
        .else
        cmp.l   #O3_ROW,%d6
        bne     .Ld6
        moveq   #1,%d6
        .endif
.Ld6:
        move.l  %d6,%d7
        lsl.l   #3,%d7
        add.l   %d6,%d6
        sub.l   %d6,%d7
        jmp     0x4003cda0

| o3_validate -- Detour 0x40002318 (the Part validator's entry, `lea -96(sp),sp; movem.l ...`),
| validate(Part'): the stock validator sees FLEX's defaults in each signed track's twelve PLAYBACK and
| SETUP bytes (FINE SLID DRIV are 0..127 where FLEX's LEN RATE TSTR clamp to 0..3); ours are restored.
o3_validate:
        lea     -112(%sp),%sp           | 96: the saved bytes (12 a track), 16: d2, d3, a2, a3
        movem.l %d2-%d3/%a2-%a3,96(%sp)
        move.l  116(%sp),%a2            | Part'
        moveq   #0,%d3                  | the signed tracks' mask
        moveq   #0,%d2
.Lv_t:
        move.l  %d2,%d0
        move.l  %a2,%a0
        bsr     o3_sig
        beq     .Lv_n
        .if     HK_MACHINE_ROWS
        bsr     o3_vcount               | the limit: every machine's tracks below this one (d0 = their count)
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
        cmp.l   #O3_MAX,%d0
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
        bsr     o3_vptr                 | a0 = the PLAYBACK bytes, a1 = the save slot
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
        jsr     o3_stock_validate
        addq.l  #4,%sp
        move.l  %d0,%a3                 | the validator's result
        moveq   #0,%d2
.Lv_r:
        btst    %d2,%d3
        beq     .Lv_rn
        bsr     o3_vptr
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
o3_vptr:                                | d2 = track, a2 = Part' -> a0 = Part' + 0x30 + 30*track, a1 = 4 + sp + 12*track
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
| ---- o3_vcount: d2 = track, a2 = Part' -> d0 = the tracks below d2 signed by any machine.  Saves all else.
|      (o3_validate's limit: one count for every kind of machine; an own track past it was unsigned in place.)
o3_vcount:
        lea     -12(%sp),%sp
        movem.l %d2-%d3/%a0,(%sp)
        moveq   #0,%d3
        subq.l  #1,%d2
        bmi     .Lvcn_x
.Lvcn_l:
        move.l  %d2,%d0
        move.l  %a2,%a0
        bsr     o3_anysig
        add.l   %d0,%d3
        subq.l  #1,%d2
        bpl     .Lvcn_l
.Lvcn_x:
        move.l  %d3,%d0
        movem.l (%sp),%d2-%d3/%a0
        lea     12(%sp),%sp
        rts
        .endif
o3_stock_validate:
        .if     HK_MACHINE_ROWS
        .if     MC_HAS_VALIDATE
        jmp     MC_NEXT_VALIDATE        | the next machine's tracks, then stock
        .endif
        .endif
        lea     -96(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        jmp     0x40002320

| ---- the SETUP page's formatters (fmt(buf, value) -> length)
o3_fmt_wave:
        lea     o3_lwave,%a1
        moveq   #7,%d1                  | v7.9: 8 labels
        bra     o3_fmt_lbl
o3_fmt_gate:
        lea     o3_lgate,%a1
        moveq   #1,%d1
o3_fmt_lbl:                             | a1 = labels, 6 bytes each, d1 = the last
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
o3_fmt_fine:                            | raw - 64: "-64" .. "0" .. "+63"
        move.l  8(%sp),%d0
        sub.l   #64,%d0
        lea     FMT_D,%a0
        tst.l   %d0
        ble     .Lff_1
        lea     o3_f_plus,%a0
.Lff_1:
        move.l  %d0,-(%sp)
        move.l  %a0,-(%sp)
        move.l  12(%sp),-(%sp)
        jsr     SPRINTF
        lea     12(%sp),%sp
        rts

| ---- o3_inc: d0 = p -> d0 = phase increment.  Clobbers d1, a0.
o3_inc:
        divu.w  #3072,%d0
        move.l  %d0,%d1
        swap    %d1
        and.l   #0xFFFF,%d1
        lsr.l   #2,%d1
        lea     O3_INC_TAB,%a0
        and.l   #0xFFFF,%d0             | here, between the lea and the load: no address-use stall (#1244 5d7bdd44)
        move.l  (%a0,%d1.l*4),%d1
        lsl.l   %d0,%d1
        move.l  %d1,%d0
        rts

| ---- o3_mul30: d0, d1 in [0, 2^31) -> d0 ~ (d0*d1) >> 30.  Clobbers d1-d3.
o3_mul30:
        move.l  %d0,%d2
        and.l   #0x7FFF,%d2
        lsr.l   #8,%d0
        lsr.l   #7,%d0
        move.l  %d1,%d3
        and.l   #0x7FFF,%d3
        lsr.l   #8,%d1
        lsr.l   #7,%d1
        mulu.l  %d0,%d3
        mulu.l  %d1,%d2
        add.l   %d3,%d2
        lsr.l   #8,%d2
        lsr.l   #7,%d2
        mulu.l  %d1,%d0
        add.l   %d2,%d0
        rts

| ---- o3_megf (v7.8): d0 = the MEG in (0, ONE30], d1 = DECAY -> d0 = this frame's factor (Q30, ref303.megf):
|      O3_MEG_T by DECAY (33 rows, 4 apart, linear) and by level (64 points, 6 an octave, linear; the level's
|      position from ff1 and the mantissa, o3meg.level_of_x).  Clobbers d1-d6, a0.
|      o3_megfa (v7.9): the same on O3_ADEC_T (34 rows), d1 = the ADEC row position (accents; ADEC 50 -> 52).
o3_megfa:
        lea     O3_ADEC_T,%a0
        bra     .Lmf_go
o3_megf:
        lea     O3_MEG_T,%a0
.Lmf_go:
        move.l  %d1,%d6                 | DECAY (or the ADEC row position)
        move.l  %d0,%d2
        ff1     %d2                     | n, the leading zeros (>= 2)
        lsl.l   %d2,%d0                 | m << n: bit 31 set
        neg.l   %d0                     | t = 2^32 - (m << n), Q31 in (0, 2^31]
        lsr.l   #8,%d0
        lsr.l   #7,%d0
        move.l  %d0,%d1
        add.l   %d0,%d0
        add.l   %d1,%d0
        add.l   %d0,%d0                 | 6 (t >> 15)
        subq.l  #2,%d2
        move.l  #393216,%d1             | 6 points an octave, Q16
        muls.l  %d1,%d2
        add.l   %d2,%d0                 | x, Q16
        move.l  %d0,%d4
        lsr.l   #8,%d4
        lsr.l   #8,%d4                  | j
        move.l  %d0,%d5
        and.l   #0xFFFF,%d5
        lsr.l   #1,%d5                  | the fraction, Q15
        move.l  %d6,%d3
        lsr.l   #2,%d3
        lsl.l   #8,%d3                  | the row, 64 longs
        lea     (%a0,%d3.l),%a0
        bsr     .Lmf_lv
        and.l   #3,%d6                  | between two rows
        beq     .Lmf_x
        move.l  %d0,-(%sp)
        lea     256(%a0),%a0
        bsr     .Lmf_lv
        move.l  (%sp)+,%d1
        sub.l   %d1,%d0
        muls.l  %d6,%d0
        asr.l   #2,%d0
        add.l   %d1,%d0
.Lmf_x:
        rts
.Lmf_lv:                                | d0 = row a0 at j d4, fraction d5 (j >= 63: the last point).  d1, d2
        cmp.l   #MEG_NLEV-1,%d4
        blt     .Lmf_i
        move.l  (MEG_NLEV-1)*4(%a0),%d0
        rts
.Lmf_i:
        move.l  (%a0,%d4.l*4),%d1
        move.l  4(%a0,%d4.l*4),%d0
        sub.l   %d1,%d0
        MULQ15  %d0,%d5,%d2
        add.l   %d1,%d0
        rts

| ---- o3_acf (v7.8): d0 = V (uV), a0 = O3_AC_F or O3_AC_F27 -> d0 = y = i R of the diode in series with R
|      (0 for V <= 0; V clamped at AC_VMAX; linear between points 2^15 uV apart).  Clobbers d1, d2, a0.
o3_acf:
        tst.l   %d0
        ble     .Laf_0
        cmp.l   #AC_VMAX,%d0
        ble     .Laf_1
        move.l  #AC_VMAX,%d0
.Laf_1:
        move.l  %d0,%d1
        and.l   #0x7FFF,%d1
        lsr.l   #8,%d0
        lsr.l   #7,%d0
        lea     (%a0,%d0.l*4),%a0
        move.l  (%a0)+,%d0
        move.l  (%a0),%d2
        sub.l   %d0,%d2
        muls.l  %d1,%d2
        asr.l   #8,%d2
        asr.l   #7,%d2
        add.l   %d2,%d0
        rts
.Laf_0:
        moveq   #0,%d0
        rts

| ---- o3_acc (v7.8, V8A): the accent circuit, two backward-Euler sub-steps (ref303.accent; o3tables AC_*).
|      d0 = the MEG into VR7 (Q30, 0 on normal notes) -> d6 = the push to the filter (Q8 semitones),
|      d4 = I27 / I_Q31 (Q14).  Clobbers d0-d5, a0 (keeps a1).  Locals: 0 qre, 4 qrp, 8 q72, 12 dl, 16 k2,
|      20 y24, 24 tm, 28 the sub-steps left.
o3_acc:
        lea     -32(%sp),%sp
        move.l  %d0,24(%sp)
        move.l  S_ACCI(%a3),%d4
        lea     O3_AC_K2,%a0
        move.l  S_RES(%a3),%d5
        move.l  (%a0,%d5.l*4),%d0
        move.l  S_SPD(%a3),%d1
        moveq   #1,%d2
        cmp.l   %d2,%d1
        bne     .Lac_k1
        lsl.l   #2,%d0                  | dEVILish SPD FAST: C13 / 4 (INTERPRETED)
        bra     .Lac_k3
.Lac_k1:
        moveq   #3,%d2
        cmp.l   %d2,%d1
        bne     .Lac_k3
        lsr.l   #2,%d0                  | SLOW: C13 x 4 (INTERPRETED)
.Lac_k3:
        move.l  %d0,16(%sp)             | k2
        tst.l   24(%sp)                 | at rest (no MEG in, C36 and I27 at 0, C13's step 0): the sub-steps
        bne     .Lac_go                 | would change nothing (exact shortcut, ref303.accent)
        tst.l   S_V34(%a3)
        bne     .Lac_go
        tst.l   S_Y27(%a3)
        bne     .Lac_go
        move.l  S_DVC(%a3),%d0
        move.l  16(%sp),%d1
        bsr     o3_mul30
        tst.l   %d0
        bne     .Lac_go
        moveq   #0,%d4
        move.l  S_RES(%a3),%d5
        bra     .Lac_out
.Lac_go:
        move.l  S_ACCI(%a3),%d4
        lea     O3_AC_RE,%a0
        move.l  S_RES(%a3),%d5
        move.l  (%a0,%d4.l*4),%d6       | Re
        lea     O3_AC_RA,%a0
        move.l  (%a0,%d5.l*4),%d3
        add.l   %d6,%d3                 | R24 = Re + RA
        move.l  %d3,%d2
        sub.l   #AC_R0,%d2
        move.l  #AC_KLN,%d1
        muls.l  %d1,%d2
        asr.l   #8,%d2
        asr.l   #8,%d2
        move.l  %d2,12(%sp)             | dl ~ nVT ln(R24 / R0)
        move.l  #0x20000000,%d0
        divu.l  %d3,%d0                 | 2^29 / R24
        move.l  %d0,%d1
        muls.l  %d6,%d1
        lea     O3_AC_RP,%a0
        move.l  %d1,0(%sp)              | qre = Re / R24, Q29
        move.l  (%a0,%d5.l*4),%d1
        muls.l  %d0,%d1
        move.l  %d1,4(%sp)              | qrp
        move.l  #AC_R72N,%d1
        muls.l  %d1,%d0
        move.l  %d0,8(%sp)              | q72
        moveq   #2,%d0
        move.l  %d0,28(%sp)
.Lac_st:
        lea     O3_AC_A1,%a0
        move.l  S_ACCI(%a3),%d4         | ve: VR7's wiper loaded by R119 to C36
        move.l  (%a0,%d4.l*4),%d1
        move.l  24(%sp),%d0
        bsr     o3_mul30
        move.l  %d0,%d6
        lea     O3_AC_A2,%a0
        move.l  S_ACCI(%a3),%d4
        move.l  (%a0,%d4.l*4),%d1
        move.l  S_V34(%a3),%d0
        bsr     o3_mul30
        add.l   %d0,%d6                 | ve
        lea     O3_AC_B1,%a0
        move.l  S_RES(%a3),%d5          | v24: D24 + R46 + VR4B towards C13
        move.l  (%a0,%d5.l*4),%d1
        move.l  S_DVC(%a3),%d0
        bsr     o3_mul30
        move.l  %d6,%d4
        sub.l   #AC_V134,%d4
        sub.l   %d0,%d4
        moveq   #0,%d0
        tst.l   %d4
        ble     .Lac_y0
        move.l  %d4,%d0
        add.l   12(%sp),%d0
        lea     O3_AC_F,%a0
        bsr     o3_acf
.Lac_y0:
        move.l  %d0,20(%sp)             | y24 = i24 R24
        move.l  0(%sp),%d1
        bsr     o3_mul30
        add.l   %d0,%d0
        sub.l   %d0,%d6                 | w7 = ve - i24 Re
        bpl     .Lac_w
        moveq   #0,%d6
.Lac_w:
        move.l  20(%sp),%d0             | C13 (above N134) towards i24 R72
        move.l  8(%sp),%d1
        bsr     o3_mul30
        add.l   %d0,%d0
        sub.l   S_DVC(%a3),%d0
        bmi     .Lac_dn
        move.l  16(%sp),%d1
        bsr     o3_mul30
        bra     .Lac_dd
.Lac_dn:
        neg.l   %d0
        move.l  16(%sp),%d1
        bsr     o3_mul30
        neg.l   %d0
.Lac_dd:
        add.l   S_DVC(%a3),%d0
        move.l  %d0,S_DVC(%a3)
        move.l  S_V34(%a3),%d0          | p: C36 with R119 ...
        move.l  #AC_AL,%d1
        bsr     o3_mul30
        move.l  %d0,%d4
        move.l  %d6,%d0
        move.l  #AC_BE,%d1
        bsr     o3_mul30
        add.l   %d0,%d4                 | p
        move.l  S_Y27(%a3),%d0          | ... then R120 + D27 into pin 1 (a junction at Q31's + I27)
        move.l  %d0,%d1
        lsr.l   #8,%d0
        lsr.l   #8,%d0
        lea     O3_AC_L69,%a0
        cmp.l   #128,%d0
        blt     .Lac_l1
        move.l  512(%a0),%d0
        bra     .Lac_l2
.Lac_l1:
        and.l   #0xFFFF,%d1
        lsr.l   #1,%d1
        move.l  4(%a0,%d0.l*4),%d2
        move.l  (%a0,%d0.l*4),%d0
        sub.l   %d0,%d2
        muls.l  %d1,%d2
        asr.l   #8,%d2
        asr.l   #7,%d2
        add.l   %d2,%d0
.Lac_l2:
        neg.l   %d0
        add.l   %d4,%d0
        sub.l   #AC_V69,%d0             | v27
        lea     O3_AC_F27,%a0
        bsr     o3_acf
        move.l  %d0,S_Y27(%a3)
        move.l  #AC_Q27G,%d1
        bsr     o3_mul30
        sub.l   %d0,%d4                 | C36: p - i27 / G
        bpl     .Lac_v
        moveq   #0,%d4
.Lac_v:
        move.l  %d4,S_V34(%a3)
        move.l  28(%sp),%d0
        subq.l  #1,%d0
        move.l  %d0,28(%sp)
        bne     .Lac_st
        move.l  20(%sp),%d0             | i24 Rp
        move.l  4(%sp),%d1
        bsr     o3_mul30
        add.l   %d0,%d0
        move.l  %d0,-(%sp)
        move.l  S_Y27(%a3),%d0
        move.l  #AC_KV,%d1
        bsr     o3_mul30
        move.l  %d0,%d4                 | (I_Q31 + I27) / I_Q31 - 1, Q14
        move.l  (%sp)+,%d6
        move.l  S_RES(%a3),%d5
        bra     .Lac_w2
.Lac_out:
        moveq   #0,%d6                  | the shortcut: no i24
.Lac_w2:
        lea     O3_AC_B1,%a0            | the wiper above N134: C13 through VR4B, plus i24 Rp
        move.l  (%a0,%d5.l*4),%d1
        move.l  S_DVC(%a3),%d0
        bsr     o3_mul30
        moveq   #3,%d1
        cmp.l   S_SPD(%a3),%d1
        bne     .Lac_s
        add.l   %d0,%d0                 | SLOW: read doubled (INTERPRETED)
.Lac_s:
        add.l   %d6,%d0
        move.l  #AC_KSW,%d1
        bsr     o3_mul30
        move.l  %d0,%d6                 | through R72 into N134, Q8 semitones
        lea     32(%sp),%sp
        rts

| ---- o3_blep: d0 = phase, d5 = inc -> d0 = polyBLEP residual (Q15) of a -2 jump at the wrap.
|      Clobbers d1.
o3_blep:
        cmp.l   %d5,%d0
        bcs     .Lbl_lo
        neg.l   %d0
        cmp.l   %d5,%d0
        bcc     .Lbl_0
        bsr     .Lbl_q
        move.l  %d1,%d0
        rts
.Lbl_lo:
        bsr     .Lbl_q
        move.l  %d1,%d0
        neg.l   %d0
        rts
.Lbl_0:
        moveq   #0,%d0
        rts
.Lbl_q:
        lsl.l   #3,%d0
        move.l  %d5,%d1
        lsr.l   #8,%d1
        lsr.l   #4,%d1
        divu.l  %d1,%d0
        cmp.l   #32768,%d0
        bls     .Lbl_q1
        move.l  #32768,%d0
.Lbl_q1:
        move.l  #32768,%d1
        sub.l   %d0,%d1
        mulu.l  %d1,%d1
        lsr.l   #8,%d1
        lsr.l   #7,%d1
        rts

| ============================================================================
| o3_vrec -- v7.1: dEVILish's page-1 knobs as the DSP gets them.  The frame builder writes the DSP
| voice record (VREC + ping*0x200 + 64*track) with the locks, then the scene morph, then the LFOs
| (0x4000cb2a, 0x4000cc.., 0x4000cf40..0x4000d09e), before the packer calls sy_render: so the knobs
| read here follow locks, scenes, the crossfader and the LFOs.  v6.7.2..v7.0 morphed the lane bytes
| itself (o3_morph), which the LFOs never reach: an LFO on a dEVILish knob did nothing (the owner's
| MKI, 21 Oct 2026).  Knob = halfword >> 8, 0..127 (the low byte is an LFO's fraction, LFO.md 5).
| In: d1 = the lane slot (18 FX1 / 24 FX2), d2 = track, a3 = state.
| Out: a0 = S_DFK(a3), the six knobs.  Clobbers d0, d1.
| ============================================================================
o3_vrec:
        lea     -12(%sp),%sp
        movem.l %d3/%a1-%a2,(%sp)
        move.l  PINGW,%d0
        moveq   #9,%d3
        lsl.l   %d3,%d0                 | ping * 0x200
        move.l  %d2,%d3
        lsl.l   #6,%d3
        add.l   %d3,%d0                 | + 64 * track
        sub.l   #12,%d1                 | lane slot 18 / 24 -> halfword 6 / 12
        add.l   %d1,%d0
        add.l   %d1,%d0
        lea     VREC,%a1
        add.l   %d0,%a1
        lea     S_DFK(%a3),%a2
        moveq   #5,%d3
.Lvr_lp:
        mvs.w   (%a1)+,%d0
        bge     .Lvr_pos
        moveq   #0,%d0                  | below the floor: 0
.Lvr_pos:
        asr.l   #8,%d0
        moveq   #127,%d1
        cmp.l   %d1,%d0
        ble     .Lvr_k
        move.l  %d1,%d0
.Lvr_k:
        move.b  %d0,(%a2)+
        subq.l  #1,%d3
        bge     .Lvr_lp
        lea     S_DFK(%a3),%a0
        movem.l (%sp),%d3/%a1-%a2
        lea     12(%sp),%sp
        rts

| ---- o3_params: this call's record words, and dEVILish's twelve knobs on this track (from the FX
|      slot that holds it, locks applied) or the neutral twelve.  d2 = track, a4 = FP.
|      Clobbers d0, d1, a0, a1 (a2 saved).
o3_params:
        bsr     o3_setup                | v7.0: FINE before the pitch words
        moveq   #0,%d0
        move.w  0(%a4),%d0
        bsr     o3_pword
        move.l  %d0,S_PTGT(%a3)
        RAWW    2,S_CUT
        RAWW    4,S_RES
        RAWW    6,S_ENV
        RAWW    8,S_DEC
        move.l  %a2,-(%sp)
        lea     o3_df_neutral,%a0       | page 1 bytes
        lea     o3_df_neutral+6,%a2     | page 2 bytes
        lea     FXID1,%a1
        moveq   #0,%d0
        move.b  (%a1,%d2.l),%d0
        cmp.l   #DEVIL_ID,%d0
        bne     .Lp_f2
        moveq   #LANE_FX1P1,%d1
        bra     .Lp_lane
.Lp_f2:
        lea     FXID2,%a1
        moveq   #0,%d0
        move.b  (%a1,%d2.l),%d0
        cmp.l   #DEVIL_ID,%d0
        bne     .Lp_have
        moveq   #LANE_FX2P1,%d1
.Lp_lane:
        move.l  %d2,%d0                 | the lane: CURVALS + 72*track, page 1 at +d1
        move.l  %d1,-(%sp)
        moveq   #CV_STRIDE,%d1
        muls.l  %d1,%d0
        move.l  (%sp)+,%d1
        lea     CURVALS,%a0
        add.l   %d0,%a0
        lea     32(%a0,%d1.l),%a2       | page 2 = page 1 + 32 (0x32 - 18 = 0x38 - 24), both slots
        add.l   %d1,%a0
        bsr     o3_vrec                 | v7.1: page 1 as the DSP gets it (locks, scenes, LFOs)
.Lp_have:
        moveq   #0,%d1                  | v8.2 P2: dEVILish's twelve bytes (page 1 at a0, page 2 at a2) as at the last
        moveq   #0,%d0                  | call: everything down to ENVX is a pure function of them (only
        move.b  (%a0),%d0                | o3_params writes those fields); packed into three longs, d1 = 1 if one moved
        lsl.l   #8,%d0
        move.b  1(%a0),%d0
        lsl.l   #8,%d0
        move.b  2(%a0),%d0
        lsl.l   #8,%d0
        move.b  3(%a0),%d0
        cmp.l   S_P2D1(%a3),%d0
        beq     .Lp_k1
        move.l  %d0,S_P2D1(%a3)
        moveq   #1,%d1
.Lp_k1:
        moveq   #0,%d0
        move.b  4(%a0),%d0
        lsl.l   #8,%d0
        move.b  5(%a0),%d0
        lsl.l   #8,%d0
        move.b  (%a2),%d0
        lsl.l   #8,%d0
        move.b  1(%a2),%d0
        cmp.l   S_P2D2(%a3),%d0
        beq     .Lp_k2
        move.l  %d0,S_P2D2(%a3)
        moveq   #1,%d1
.Lp_k2:
        moveq   #0,%d0
        move.b  2(%a2),%d0
        lsl.l   #8,%d0
        move.b  3(%a2),%d0
        lsl.l   #8,%d0
        move.b  4(%a2),%d0
        lsl.l   #8,%d0
        move.b  5(%a2),%d0
        cmp.l   S_P2D3(%a3),%d0
        beq     .Lp_k3
        move.l  %d0,S_P2D3(%a3)
        moveq   #1,%d1
.Lp_k3:
        move.l  %a0,%d0                 | and page 1's source: dEVILish's S_DFK or the neutral bytes (with the neutral
        cmp.l   S_P2DA(%a3),%d0         | ones SETUP's SLID overrides SLIDE below, so the source is part of the key)
        beq     .Lp_k4
        move.l  %d0,S_P2DA(%a3)
        moveq   #1,%d1
.Lp_k4:
        tst.l   S_P2DV(%a3)
        beq     .Lp_new
        tst.l   %d1
        beq     .Lp_skip
.Lp_new:
        moveq   #1,%d0
        move.l  %d0,S_P2DV(%a3)
        KBTAB   0,%a0,O3_DF_GIN          | OVDR
        TABNEXT S_GIN,O3_DF_OCOMP
        TABNEXT S_OCOMP,O3_DF_OGAIN
        move.l  %d1,S_OGAIN(%a3)
        moveq   #0,%d1
        cmp.l   #DF_GIN_Q15,%d0
        bhi     .Lp_g
        moveq   #1,%d1
.Lp_g:
        move.l  %d1,S_GINQ15(%a3)
        KB      1,%a0                   | FM
        move.l  #DF_FM_MUL,%d1
        muls.l  %d1,%d0
        move.l  %d0,S_FMQ(%a3)
        KBTAB   2,%a0,O3_DF_TRK_HZ       | TRCK
        move.l  %d1,S_TRKHZ(%a3)
        KBTAB   3,%a0,O3_DF_VEG          | VDEC
        TABNEXT S_VEGD,O3_DF_VSUS
        move.l  %d1,S_VSUS(%a3)
        KBTAB   4,%a0,O3_DF_SLIDE        | SLID
        move.l  %d1,S_SLIDE(%a3)
        KBTAB   5,%a0,O3_DF_ADEC         | ADEC
        move.l  %d1,S_ADEC(%a3)
        KBTAB   0,%a2,O3_DF_SATK         | SATK (0: none, v6.1's instant attack)
        move.l  %d1,S_SATK(%a3)
        KB      1,%a2                   | SWP: ACID 0 -> 2 (the 303), WHST 1 -> 1, SELF 2 -> 0
        MIN2
        moveq   #2,%d1
        sub.l   %d0,%d1
        move.l  %d1,S_SWP(%a3)
        KB      2,%a2                   | SPD: FAST 0 -> 1, NORM 1 -> 2, SLOW 2 -> 3
        MIN2
        addq.l  #1,%d0
        move.l  %d0,S_SPD(%a3)
        KB      3,%a2                   | MUFF: OFF, SOFT, HARD
        MIN2
        move.l  %d0,S_MUFF(%a3)
        KB      4,%a2                   | CUTX: OFF, ON
        moveq   #0,%d1
        tst.l   %d0
        beq     .Lp_cx
        moveq   #1,%d1
.Lp_cx:
        move.l  %d1,S_CUTX(%a3)
        KB      5,%a2                   | ENVX: OFF, ON
        moveq   #0,%d1
        tst.l   %d0
        beq     .Lp_ex
        moveq   #1,%d1
.Lp_ex:
        move.l  %d1,S_ENVX(%a3)
.Lp_skip:
        lea     o3_df_neutral,%a1       | v7.0: no dEVILish on the track: SETUP's SLID
        cmp.l   %a1,%a0
        bne     .Lp_ns
        bsr     o3_setupptr
        KBTAB   3,%a0,O3_DF_SLIDE
        move.l  %d1,S_SLIDE(%a3)
.Lp_ns:
        move.l  (%sp)+,%a2
        rts

| ---- o3_note_on: d5 = (fab<<2)|(dist<<1)|wave (v7.9: fab = WAVE's R).  Clobbers d0-d1, d4.
o3_note_on:
        moveq   #1,%d0
        and.l   %d5,%d0
        move.l  %d0,S_WAVE(%a3)
        move.l  %d5,%d0
        lsr.l   #1,%d0
        moveq   #1,%d1
        and.l   %d1,%d0
        move.l  %d0,S_DIST(%a3)
        move.l  %d5,%d0
        lsr.l   #2,%d0
        and.l   %d1,%d0
        move.l  %d0,S_FAB(%a3)
        moveq   #0,%d4                  | ACC of the trig, raw 0..127
        move.w  10(%a4),%d4
        lsr.l   #8,%d4
        cmp.l   #127,%d4
        bls     .Ln_acc
        moveq   #127,%d4
.Ln_acc:
        moveq   #0,%d0
        move.w  0(%a4),%d0
        bsr     o3_pword
        lsl.l   #8,%d0
        move.l  %d0,S_PCUR(%a3)
        moveq   #1,%d0
        move.l  %d0,S_CS(%a3)
        moveq   #0,%d0
        tst.l   %d4
        beq     .Ln_a
        moveq   #1,%d0
.Ln_a:
        move.l  %d0,S_ACCD(%a3)
        move.l  %d4,S_ACCI(%a3)         | v7.8: VR7's position (the circuit's tables are by ACCENT raw)
        move.l  #ONE30,%d0
        move.l  %d0,S_MEG(%a3)
        move.l  %d0,S_VEG(%a3)
        tst.l   S_SATK(%a3)             | SATK: a non-accented note fades in from 0
        beq     .Ln_va
        tst.l   %d4
        bne     .Ln_va
        moveq   #0,%d0
.Ln_va:
        move.l  %d0,S_VATT(%a3)
        moveq   #1,%d0                  | v6.5: the gate opens at this frame's o3_gate
        move.l  %d0,S_GNEW(%a3)
        rts

| ---- o3_ctrl: once per CS samples.  Clobbers d0-d6, a0 (keeps a1, a3, a5, d7).
o3_ctrl:
        move.l  S_PTGT(%a3),%d0         | v8.2 P2: PCUR's step, the increment and Q8's row are a pure function of
        move.l  S_PCUR(%a3),%d1         | (PTGT, PCUR, SLIDE): with the keys of a step that left PCUR where it was,
        move.l  S_SLIDE(%a3),%d2        | nothing here changes
        tst.l   S_P2PV(%a3)
        beq     .Lc_pg
        cmp.l   S_P2PT(%a3),%d0
        bne     .Lc_pg
        cmp.l   S_P2PC(%a3),%d1
        bne     .Lc_pg
        cmp.l   S_P2PS(%a3),%d2
        beq     .Lc_pd
.Lc_pg:
        move.l  %d0,S_P2PT(%a3)
        move.l  %d1,S_P2PC(%a3)
        move.l  %d2,S_P2PS(%a3)
        lsl.l   #8,%d0                  | SLID: RC slide on the pitch CV
        sub.l   %d1,%d0
        MULQ15  %d0,%d2,%d3
        moveq   #0,%d2                  | v8.2 P2: the keys hold only if PCUR stays
        tst.l   %d0
        bne     .Lc_pv
        moveq   #1,%d2
.Lc_pv:
        move.l  %d2,S_P2PV(%a3)
        add.l   %d0,%d1
        move.l  %d1,S_PCUR(%a3)
        move.l  %d1,%d0
        asr.l   #8,%d0
        bsr     o3_inc
        move.l  %d0,S_INC(%a3)
        move.l  S_PCUR(%a3),%d0         | v7.6: Q8's square by semitone (ref303: SQC / SQK[pcur >> 16])
        asr.l   #8,%d0
        lea     O3_SQK,%a0
        asr.l   #8,%d0
        move.l  (%a0,%d0.l*4),%d1
        move.l  %d1,S_SQK(%a3)
        lsl.l   #8,%d0                  | 128 shorts a row
        lea     O3_SQC,%a0
        add.l   %a0,%d0
        move.l  %d0,S_SQTP(%a3)
.Lc_pd:
        tst.l   S_ACCD(%a3)             | v7.8, the MEG: the circuit (o3meg.py) by DECAY and level; v7.9:
        beq     .Lc_n                   | accents on O3_ADEC_T at dEVILish's ADEC (0, no dEVILish: ADEC 50)
        move.l  S_ADEC(%a3),%d1
        bne     .Lc_a
        moveq   #ADEC_Q50,%d1
.Lc_a:
        move.l  S_MEG(%a3),%d0
        ble     .Lc_m                   | at 0 it stays
        bsr     o3_megfa
        bra     .Lc_mf
.Lc_n:
        move.l  S_DEC(%a3),%d1
        move.l  S_MEG(%a3),%d0
        ble     .Lc_m                   | at 0 it stays
        bsr     o3_megf
.Lc_mf:
        move.l  S_MEG(%a3),%d1
        bsr     o3_mul30
.Lc_m:
        move.l  %d0,S_MEG(%a3)
        move.l  S_MEGS(%a3),%d1
        sub.l   %d1,%d0
        move.l  #TB_MEG_ATT,%d2
        MULQ15  %d0,%d2,%d3
        add.l   %d0,%d1
        move.l  %d1,S_MEGS(%a3)
        move.l  S_VEG(%a3),%d0          | VDEC: towards the final level, from either side
        sub.l   S_VSUS(%a3),%d0
        bmi     .Lc_vn
        move.l  S_VEGD(%a3),%d1
        bsr     o3_mul30
        bra     .Lc_vd
.Lc_vn:
        neg.l   %d0
        move.l  S_VEGD(%a3),%d1
        bsr     o3_mul30
        neg.l   %d0
.Lc_vd:
        add.l   S_VSUS(%a3),%d0
        move.l  %d0,S_VEG(%a3)
        move.l  S_SATK(%a3),%d1         | SATK
        beq     .Lc_sa
        move.l  #ONE30,%d0
        sub.l   S_VATT(%a3),%d0
        bsr     o3_mul30
        add.l   S_VATT(%a3),%d0
        cmp.l   #ONE30-64,%d0
        ble     .Lc_s1
        move.l  #ONE30,%d0
.Lc_s1:
        move.l  %d0,S_VATT(%a3)
.Lc_sa:
        moveq   #0,%d0                  | v7.8: the MEG into VR7 on accented notes (none in SWP 0)
        tst.l   S_ACCD(%a3)
        beq     .Lc_v
        tst.l   S_SWP(%a3)
        beq     .Lc_v
        move.l  S_MEGS(%a3),%d0
.Lc_v:
        bsr     o3_acc                  | d6 = the push (Q8 semitones), d4 = the VCA's extra level (Q14)
        move.l  S_RES(%a3),%d5
.Lc_env:
        move.l  S_ENVX(%a3),%d0         | v8.2 P2: the env-mod depth, a pure function of (ENV, RES, ENVX): its key
        swap    %d0                     | ENV | RES << 8 | ENVX << 16 | 1 << 30 (ENV, RES 0..127; ENVX 0 or 1)
        move.l  %d5,%d1
        lsl.l   #8,%d1
        or.l    %d1,%d0
        or.l    S_ENV(%a3),%d0
        or.l    #0x40000000,%d0
        cmp.l   S_P2EK(%a3),%d0
        bne     .Lc_eg
        move.l  S_P2EV(%a3),%d1
        bra     .Lc_ed
.Lc_eg:
        move.l  %d0,S_P2EK(%a3)
        tst.l   S_ENVX(%a3)             | env-mod depth
        bne     .Lc_ex
        lea     O3_TB_SLO,%a0
        move.l  S_ENV(%a3),%d0
        move.l  (%a0,%d0.l*4),%d1
        lea     O3_TB_SHI,%a0
        move.l  (%a0,%d0.l*4),%d2
        sub.l   %d1,%d2
        muls.l  %d5,%d2
        move.l  #258,%d3
        muls.l  %d3,%d2
        asr.l   #8,%d2
        asr.l   #7,%d2
        add.l   %d2,%d1
        bra     .Lc_edc
.Lc_ex:
        lea     O3_TB_SLO,%a0           | ENVX: the depth at ENV 127, x3, scaled by ENV from none
        move.l  508(%a0),%d1
        lea     O3_TB_SHI,%a0
        move.l  508(%a0),%d2
        sub.l   %d1,%d2
        muls.l  %d5,%d2
        move.l  #258,%d3
        muls.l  %d3,%d2
        asr.l   #8,%d2
        asr.l   #7,%d2
        add.l   %d2,%d1
        moveq   #DF_ENVX_MUL,%d2
        muls.l  %d2,%d1
        muls.l  S_ENV(%a3),%d1
        moveq   #127,%d2
        divs.l  %d2,%d1
.Lc_edc:
        move.l  %d1,S_P2EV(%a3)
.Lc_ed:
        lea     O3_TB_OFF,%a0
        move.l  S_CUT(%a3),%d0          | cutoff, Q8 semitones above 20 Hz (CUTX: the wide pot)
        move.l  (%a0,%d0.l*4),%d2
        lea     O3_TB_CUT,%a0
        tst.l   S_CUTX(%a3)
        beq     .Lc_cu
        lea     O3_DF_CUTX,%a0
.Lc_cu:
        move.l  (%a0,%d0.l*4),%d3
        move.l  %d2,-(%sp)              | v7.0: CUT's base and ENV's depth glide (~1 ms); OFF kept
        tst.l   S_SMOK(%a3)
        bne     .Lc_sm
        move.l  %d3,%d0                 | the first control step takes them
        lsl.l   #8,%d0
        move.l  %d0,S_CUTB(%a3)
        move.l  %d1,%d0
        lsl.l   #8,%d0
        move.l  %d0,S_ENVS(%a3)
        moveq   #1,%d0
        move.l  %d0,S_SMOK(%a3)
.Lc_sm:
        move.l  %d3,%d0
        lsl.l   #8,%d0
        sub.l   S_CUTB(%a3),%d0
        cmp.l   S_P2CD(%a3),%d0         | v8.2 P2: a difference whose step was 0 gives 0 again (MULQ15 is a pure
        beq     .Lc_c0                  | function of it): CUTB stays
        move.l  %d0,S_P2T(%a3)
        move.l  #SMOOTH_K,%d2
        MULQ15  %d0,%d2,%d3
        tst.l   %d0
        bne     .Lc_c1
        move.l  S_P2T(%a3),%d2
        move.l  %d2,S_P2CD(%a3)
.Lc_c1:
        add.l   S_CUTB(%a3),%d0
        move.l  %d0,S_CUTB(%a3)
        bra     .Lc_c2
.Lc_c0:
        move.l  S_CUTB(%a3),%d0
.Lc_c2:
        asr.l   #8,%d0
        move.l  %d0,-(%sp)              | the base
        move.l  %d1,%d0
        lsl.l   #8,%d0
        sub.l   S_ENVS(%a3),%d0
        cmp.l   S_P2ND(%a3),%d0         | v8.2 P2: the same for ENVS
        beq     .Lc_n0
        move.l  %d0,S_P2T(%a3)
        move.l  #SMOOTH_K,%d2
        MULQ15  %d0,%d2,%d3
        tst.l   %d0
        bne     .Lc_n1
        move.l  S_P2T(%a3),%d2
        move.l  %d2,S_P2ND(%a3)
.Lc_n1:
        add.l   S_ENVS(%a3),%d0
        move.l  %d0,S_ENVS(%a3)
        bra     .Lc_n2
.Lc_n0:
        move.l  S_ENVS(%a3),%d0
.Lc_n2:
        asr.l   #8,%d0
        move.l  %d0,%d1                 | the depth
        move.l  (%sp)+,%d3
        move.l  (%sp)+,%d2
        move.l  S_MEGS(%a3),%d0
        asr.l   #8,%d0
        asr.l   #7,%d0
        sub.l   %d2,%d0
        muls.l  %d1,%d0
        asr.l   #8,%d0
        asr.l   #7,%d0
        add.l   %d0,%d3
        add.l   %d6,%d3                 | the accent sweep (Q8 semitones)
        tst.l   S_FAB(%a3)              | v7.9: WAVE's R, TM3 as Roland trims it (ref303 ctrl)
        beq     .Lc_nfab
        add.l   #TM3_FAB,%d3
.Lc_nfab:
        CLAMP   %d3,0,S_MAX-1
        move.l  S_TRKHZ(%a3),%d0        | TRCK, linear in Hz
        beq     .Lc_nt
        bsr     o3_trck
.Lc_nt:
        move.l  %d3,S_SCTRL(%a3)
        lea     O3_LADDER_B,%a0
        asr.l   #6,%d3
        move.l  (%a0,%d3.l*4),%d0
        move.l  %d0,S_B(%a3)
        muls.l  K_C1R(%a5),%d0          | v6.7: c1 = b * C1R (Q12; v6.6: b * 2)
        asr.l   #8,%d0
        asr.l   #4,%d0
        lea     O3_LADDER_K,%a0
        move.l  %d0,S_C1(%a3)
        move.l  (%a0,%d3.l*4),%d0
        lea     O3_TB_KMUL,%a0
        move.l  (%a0,%d5.l*4),%d1
        moveq   #2,%d2                  | SWP 1/0: the feedback doubled
        cmp.l   S_SWP(%a3),%d2
        beq     .Lc_k
        moveq   #DF_HIRES,%d2
        muls.l  %d2,%d1
.Lc_k:
        move.l  %d1,S_KMUL(%a3)
        muls.l  %d1,%d0
        asr.l   #8,%d0
        lea     O3_KF,%a0               | the oscillation point and its shape by frequency (Q12)
        asr.l   #7,%d0
        move.l  (%a0,%d3.l*4),%d2
        muls.l  %d2,%d0
        asr.l   #8,%d0
        lea     O3_TB_UD,%a0            | v6.9: the ring's decay by RES (dB/ms, Q10) ...
        asr.l   #4,%d0
        move.l  (%a0,%d5.l*4),%d1
        lea     O3_KD,%a0               | ... times the feedback a dB/ms, off k; never < 0
        move.l  %d1,S_UD(%a3)
        move.l  (%a0,%d3.l*4),%d2
        muls.l  %d1,%d2
        asr.l   #8,%d2
        asr.l   #2,%d2
        sub.l   %d2,%d0
        bpl     .Lc_kp
        moveq   #0,%d0
.Lc_kp:
        move.l  %d0,S_K(%a3)
        move.l  %d3,%d0                 | v7.3: the ladder clip's operating point
        CLSET
        lea     O3_TB_GCOMP,%a0         | level comp: the RES-0 base + the resonance part * OVDR's (v7.5: one gain, the part 0)
        move.l  (%a0),%d1               | factor (overdrive swamps the resonance)
        move.l  (%a0,%d5.l*4),%d0
        sub.l   %d1,%d0
        muls.l  S_OCOMP(%a3),%d0
        asr.l   #8,%d0
        asr.l   #4,%d0
        add.l   %d1,%d0
        muls.l  S_OGAIN(%a3),%d0
        asr.l   #8,%d0
        lea     O3_LG,%a0               | v6.7: the level by frequency (Q12), the real ladder's
        asr.l   #4,%d0
        move.l  (%a0,%d3.l*4),%d2       | passband with the resonance up
        muls.l  %d2,%d0
        asr.l   #8,%d0
        asr.l   #4,%d0
        lea     O3_VP_W2,%a0            | v7.4: the VCA pair's RES path, OVDR swamping it
        move.l  %d0,S_GCOMP(%a3)
        move.l  (%a0,%d5.l*4),%d0
        muls.l  S_OCOMP(%a3),%d0
        asr.l   #8,%d0
        asr.l   #4,%d0
        move.l  %d0,S_W2(%a3)
        move.l  %d4,%d6                 | v7.8: I27 / I_Q31 (pin 1, Q14) x ACCV / 64
        muls.l  S_ACCVG(%a3),%d6
        asr.l   #6,%d6
        move.l  S_VEG(%a3),%d0          | VEG * SATK's fade-in (none: the VEG itself)
        move.l  S_VATT(%a3),%d1
        cmp.l   #ONE30,%d1
        bge     .Lc_vf
        bsr     o3_mul30
.Lc_vf:
        lsr.l   #8,%d0
        lsr.l   #8,%d0
        add.l   %d6,%d0                 | VCA target, Q14
        tst.l   S_GMODE(%a3)            | v6.5: the 303's gate scales it (HOLD INF only)
        beq     .Lc_ng
        move.l  %d0,%d6
        moveq   #0,%d0
        tst.l   S_GATE(%a3)
        beq     .Lc_g0
        move.l  #32767,%d0
.Lc_g0:
        move.l  S_GLVL(%a3),%d1
        sub.l   %d1,%d0
        move.l  #GATE_K,%d2
        MULQ15  %d0,%d2,%d3
        add.l   %d0,%d1
        move.l  %d1,S_GLVL(%a3)
        move.l  %d6,%d0                 | v7.8: exact (the target can pass 2^16)
        MULQ15  %d0,%d1,%d3
.Lc_ng:
        sub.l   S_AMP(%a3),%d0
        asr.l   #4,%d0
        move.l  %d0,S_AMPSTEP(%a3)
        rts

| ---- o3_trck: d3 = s (clamped), d0 = TRCK's Hz per octave -> d3 = the cutoff moved linearly in Hz
|      by the pitch's distance from TUNE 0, back to an index by binary search (ref303.trck).
|      Clobbers d0-d2, a0.
o3_trck:
        move.l  %d4,-(%sp)
        move.l  S_PCUR(%a3),%d1
        asr.l   #8,%d1
        sub.l   #P_CENTER,%d1
        muls.l  %d1,%d0
        move.l  #3072,%d1
        divs.l  %d1,%d0                 | Hz to add (truncated, as ref303.tdiv)
        move.l  %d3,%d1
        asr.l   #6,%d1
        lea     O3_DF_HZ,%a0
        add.l   (%a0,%d1.l*4),%d0       | f2
        cmp.l   (%a0),%d0
        bgt     .Lt_1
        moveq   #0,%d3                  | at or below the bottom: shut
        bra     .Lt_9
.Lt_1:
        moveq   #0,%d1                  | lo
        move.l  #NHZ-1,%d2              | hi
.Lt_2:
        cmp.l   %d2,%d1
        bge     .Lt_4
        move.l  %d1,%d4
        add.l   %d2,%d4
        addq.l  #1,%d4
        asr.l   #1,%d4                  | m
        cmp.l   (%a0,%d4.l*4),%d0
        blt     .Lt_3
        move.l  %d4,%d1                 | DF_HZ[m] <= f2: lo = m
        bra     .Lt_2
.Lt_3:
        move.l  %d4,%d2                 | hi = m - 1
        subq.l  #1,%d2
        bra     .Lt_2
.Lt_4:
        lsl.l   #6,%d1
        and.l   #63,%d3
        add.l   %d1,%d3
.Lt_9:
        move.l  (%sp)+,%d4
        rts

| ============================================================================
| o3_clone (a0 = the stock record, a1 = override list) -> d0 = the machine's record (v7.0, o3_mdesc):
| a RAM clone of the stock FLEX record (built once, from the user's own ROM) with the listed
| fields replaced.  Called inside the page resolver: may clobber d0/d1/a0/a1 only.  v7.9: the
| TB303* sample's PLAYBACK clone (o3_pgdesc, record 0) is gone; this is the only record.
| ============================================================================
o3_clone:
        lea     -8(%sp),%sp
        movem.l %a2-%a3,(%sp)
        lea     o3_desc,%a2
        lea     o3_built,%a3
        tst.b   (%a3)
        bne     .Lclhave
        move.l  %a2,%a3
        move.l  #FLEX_DESC_LEN,%d1      | (0x192 bytes)
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
        lea     o3_built,%a3
        moveq   #1,%d0
        move.b  %d0,(%a3)
.Lclhave:
        move.l  %a2,%d0
        movem.l (%sp),%a2-%a3
        lea     8(%sp),%sp
        rts

| >>> GENERATED TABLES (tools/octa303/gen_tables.py) -- do not edit by hand
        .align  4
O3_K:
        .long   0, 20210, 555, 41, 17398, 18830, 10923, 9618
        .long   333, 719
O3_INC_TAB:
        .long   315993, 316279, 316564, 316850, 317136, 317423, 317709, 317996
        .long   318283, 318571, 318858, 319146, 319434, 319723, 320012, 320301
        .long   320590, 320879, 321169, 321459, 321749, 322040, 322330, 322622
        .long   322913, 323204, 323496, 323788, 324081, 324373, 324666, 324959
        .long   325253, 325546, 325840, 326135, 326429, 326724, 327019, 327314
        .long   327610, 327906, 328202, 328498, 328795, 329091, 329389, 329686
        .long   329984, 330282, 330580, 330878, 331177, 331476, 331775, 332075
        .long   332375, 332675, 332975, 333276, 333577, 333878, 334180, 334481
        .long   334783, 335086, 335388, 335691, 335994, 336298, 336601, 336905
        .long   337209, 337514, 337819, 338124, 338429, 338735, 339040, 339347
        .long   339653, 339960, 340267, 340574, 340881, 341189, 341497, 341806
        .long   342114, 342423, 342732, 343042, 343352, 343662, 343972, 344282
        .long   344593, 344904, 345216, 345528, 345840, 346152, 346464, 346777
        .long   347090, 347404, 347717, 348031, 348346, 348660, 348975, 349290
        .long   349606, 349921, 350237, 350553, 350870, 351187, 351504, 351821
        .long   352139, 352457, 352775, 353094, 353413, 353732, 354051, 354371
        .long   354691, 355011, 355332, 355652, 355973, 356295, 356617, 356939
        .long   357261, 357584, 357906, 358230, 358553, 358877, 359201, 359525
        .long   359850, 360175, 360500, 360825, 361151, 361477, 361804, 362130
        .long   362457, 362785, 363112, 363440, 363768, 364097, 364426, 364755
        .long   365084, 365414, 365744, 366074, 366404, 366735, 367066, 367398
        .long   367729, 368062, 368394, 368726, 369059, 369393, 369726, 370060
        .long   370394, 370729, 371063, 371398, 371734, 372069, 372405, 372742
        .long   373078, 373415, 373752, 374090, 374428, 374766, 375104, 375443
        .long   375782, 376121, 376461, 376801, 377141, 377481, 377822, 378163
        .long   378505, 378847, 379189, 379531, 379874, 380217, 380560, 380904
        .long   381248, 381592, 381936, 382281, 382626, 382972, 383318, 383664
        .long   384010, 384357, 384704, 385051, 385399, 385747, 386095, 386444
        .long   386793, 387142, 387492, 387842, 388192, 388542, 388893, 389244
        .long   389596, 389948, 390300, 390652, 391005, 391358, 391711, 392065
        .long   392419, 392773, 393128, 393483, 393838, 394194, 394550, 394906
        .long   395263, 395620, 395977, 396334, 396692, 397050, 397409, 397768
        .long   398127, 398486, 398846, 399206, 399567, 399928, 400289, 400650
        .long   401012, 401374, 401736, 402099, 402462, 402826, 403189, 403553
        .long   403918, 404282, 404647, 405013, 405379, 405745, 406111, 406478
        .long   406845, 407212, 407580, 407948, 408316, 408685, 409054, 409423
        .long   409793, 410163, 410533, 410904, 411275, 411646, 412018, 412390
        .long   412762, 413135, 413508, 413881, 414255, 414629, 415004, 415378
        .long   415753, 416129, 416505, 416881, 417257, 417634, 418011, 418388
        .long   418766, 419144, 419523, 419902, 420281, 420660, 421040, 421420
        .long   421801, 422182, 422563, 422944, 423326, 423708, 424091, 424474
        .long   424857, 425241, 425625, 426009, 426394, 426779, 427164, 427550
        .long   427936, 428322, 428709, 429096, 429484, 429871, 430260, 430648
        .long   431037, 431426, 431816, 432206, 432596, 432986, 433377, 433769
        .long   434160, 434552, 434945, 435338, 435731, 436124, 436518, 436912
        .long   437307, 437701, 438097, 438492, 438888, 439284, 439681, 440078
        .long   440475, 440873, 441271, 441670, 442068, 442468, 442867, 443267
        .long   443667, 444068, 444469, 444870, 445272, 445674, 446076, 446479
        .long   446882, 447286, 447690, 448094, 448499, 448903, 449309, 449715
        .long   450121, 450527, 450934, 451341, 451749, 452156, 452565, 452973
        .long   453382, 453792, 454201, 454612, 455022, 455433, 455844, 456256
        .long   456668, 457080, 457493, 457906, 458319, 458733, 459147, 459562
        .long   459977, 460392, 460808, 461224, 461641, 462057, 462475, 462892
        .long   463310, 463728, 464147, 464566, 464986, 465406, 465826, 466246
        .long   466667, 467089, 467511, 467933, 468355, 468778, 469201, 469625
        .long   470049, 470474, 470898, 471324, 471749, 472175, 472601, 473028
        .long   473455, 473883, 474311, 474739, 475168, 475597, 476026, 476456
        .long   476886, 477317, 477748, 478179, 478611, 479043, 479476, 479909
        .long   480342, 480776, 481210, 481644, 482079, 482514, 482950, 483386
        .long   483823, 484259, 484697, 485134, 485572, 486011, 486450, 486889
        .long   487329, 487769, 488209, 488650, 489091, 489533, 489975, 490417
        .long   490860, 491303, 491747, 492191, 492635, 493080, 493525, 493971
        .long   494417, 494863, 495310, 495757, 496205, 496653, 497102, 497550
        .long   498000, 498449, 498899, 499350, 499801, 500252, 500704, 501156
        .long   501608, 502061, 502515, 502968, 503423, 503877, 504332, 504787
        .long   505243, 505699, 506156, 506613, 507071, 507528, 507987, 508445
        .long   508904, 509364, 509824, 510284, 510745, 511206, 511668, 512130
        .long   512592, 513055, 513518, 513982, 514446, 514911, 515376, 515841
        .long   516307, 516773, 517239, 517706, 518174, 518642, 519110, 519579
        .long   520048, 520518, 520988, 521458, 521929, 522400, 522872, 523344
        .long   523817, 524289, 524763, 525237, 525711, 526186, 526661, 527136
        .long   527612, 528089, 528566, 529043, 529520, 529999, 530477, 530956
        .long   531436, 531915, 532396, 532876, 533358, 533839, 534321, 534804
        .long   535287, 535770, 536254, 536738, 537223, 537708, 538193, 538679
        .long   539165, 539652, 540140, 540627, 541115, 541604, 542093, 542583
        .long   543073, 543563, 544054, 544545, 545037, 545529, 546021, 546514
        .long   547008, 547502, 547996, 548491, 548986, 549482, 549978, 550475
        .long   550972, 551469, 551967, 552466, 552964, 553464, 553963, 554464
        .long   554964, 555465, 555967, 556469, 556971, 557474, 557978, 558481
        .long   558986, 559490, 559996, 560501, 561007, 561514, 562021, 562528
        .long   563036, 563545, 564054, 564563, 565073, 565583, 566094, 566605
        .long   567116, 567628, 568141, 568654, 569167, 569681, 570196, 570711
        .long   571226, 571742, 572258, 572775, 573292, 573810, 574328, 574846
        .long   575365, 575885, 576405, 576925, 577446, 577968, 578489, 579012
        .long   579535, 580058, 580582, 581106, 581631, 582156, 582681, 583208
        .long   583734, 584261, 584789, 585317, 585845, 586374, 586904, 587434
        .long   587964, 588495, 589026, 589558, 590091, 590623, 591157, 591691
        .long   592225, 592760, 593295, 593830, 594367, 594903, 595440, 595978
        .long   596516, 597055, 597594, 598134, 598674, 599214, 599755, 600297
        .long   600839, 601381, 601924, 602468, 603012, 603556, 604101, 604647
        .long   605193, 605739, 606286, 606834, 607382, 607930, 608479, 609028
        .long   609578, 610129, 610680, 611231, 611783, 612335, 612888, 613442
        .long   613996, 614550, 615105, 615660, 616216, 616773, 617329, 617887
        .long   618445, 619003, 619562, 620122, 620682, 621242, 621803, 622364
        .long   622926, 623489, 624052, 624615, 625179, 625744, 626309, 626874
        .long   627440, 628007, 628574, 629141, 629710, 630278, 630847, 631417
O3_TB_CUT:
        .long   9653, 9653, 9654, 9657, 9660, 9664, 9669, 9675
        .long   9681, 9689, 9697, 9706, 9716, 9726, 9737, 9749
        .long   9762, 9775, 9789, 9803, 9818, 9834, 9850, 9867
        .long   9884, 9902, 9921, 9939, 9959, 9978, 9999, 10019
        .long   10040, 10065, 10096, 10133, 10177, 10226, 10280, 10340
        .long   10405, 10474, 10548, 10626, 10707, 10793, 10882, 10973
        .long   11068, 11165, 11265, 11366, 11470, 11575, 11681, 11788
        .long   11896, 12004, 12112, 12221, 12329, 12436, 12543, 12648
        .long   12752, 12859, 12971, 13090, 13213, 13342, 13474, 13611
        .long   13751, 13894, 14039, 14186, 14335, 14485, 14636, 14786
        .long   14936, 15086, 15234, 15381, 15525, 15666, 15805, 15940
        .long   16070, 16197, 16318, 16434, 16543, 16647, 16743, 16833
        .long   16918, 17002, 17086, 17169, 17251, 17331, 17411, 17490
        .long   17568, 17644, 17719, 17792, 17864, 17935, 18003, 18070
        .long   18136, 18199, 18260, 18320, 18377, 18432, 18485, 18536
        .long   18585, 18630, 18674, 18715, 18753, 18788, 18821, 18850
O3_TB_OFF:
        .long   11169, 11171, 11172, 11173, 11174, 11175, 11177, 11178
        .long   11179, 11180, 11181, 11183, 11184, 11185, 11186, 11187
        .long   11188, 11190, 11191, 11192, 11193, 11194, 11196, 11197
        .long   11198, 11199, 11200, 11202, 11203, 11204, 11205, 11206
        .long   11208, 11209, 11210, 11211, 11212, 11213, 11215, 11216
        .long   11217, 11218, 11219, 11221, 11222, 11223, 11224, 11225
        .long   11227, 11228, 11229, 11230, 11231, 11233, 11234, 11235
        .long   11236, 11237, 11238, 11240, 11241, 11242, 11243, 11244
        .long   11246, 11247, 11248, 11249, 11250, 11252, 11253, 11254
        .long   11255, 11256, 11258, 11259, 11260, 11261, 11262, 11264
        .long   11265, 11266, 11267, 11268, 11269, 11271, 11272, 11273
        .long   11274, 11275, 11277, 11278, 11279, 11280, 11281, 11283
        .long   11284, 11285, 11286, 11287, 11289, 11290, 11291, 11292
        .long   11293, 11294, 11296, 11297, 11298, 11299, 11300, 11302
        .long   11303, 11304, 11305, 11306, 11308, 11309, 11310, 11311
        .long   11312, 11314, 11315, 11316, 11317, 11318, 11319, 11321
O3_TB_SLO:
        .long   2504, 2515, 2527, 2540, 2554, 2569, 2585, 2603
        .long   2620, 2639, 2659, 2680, 2701, 2723, 2746, 2770
        .long   2794, 2819, 2845, 2871, 2898, 2926, 2954, 2982
        .long   3011, 3041, 3070, 3101, 3131, 3162, 3194, 3225
        .long   3257, 3289, 3322, 3355, 3388, 3422, 3457, 3492
        .long   3529, 3566, 3604, 3643, 3684, 3726, 3768, 3813
        .long   3859, 3906, 3955, 4006, 4058, 4112, 4168, 4227
        .long   4287, 4349, 4414, 4481, 4550, 4622, 4696, 4773
        .long   4853, 4944, 5053, 5179, 5322, 5480, 5653, 5838
        .long   6035, 6244, 6462, 6690, 6925, 7166, 7414, 7665
        .long   7921, 8178, 8437, 8697, 8955, 9212, 9466, 9715
        .long   9960, 10198, 10429, 10652, 10865, 11068, 11260, 11439
        .long   11610, 11780, 11949, 12116, 12282, 12447, 12609, 12771
        .long   12930, 13088, 13244, 13399, 13552, 13703, 13852, 13999
        .long   14144, 14287, 14428, 14567, 14704, 14839, 14972, 15102
        .long   15231, 15357, 15480, 15601, 15720, 15836, 15950, 16061
O3_TB_SHI:
        .long   2504, 2515, 2527, 2540, 2554, 2569, 2585, 2603
        .long   2620, 2639, 2659, 2680, 2701, 2723, 2746, 2770
        .long   2794, 2819, 2845, 2871, 2898, 2926, 2954, 2982
        .long   3011, 3041, 3070, 3101, 3131, 3162, 3194, 3225
        .long   3257, 3289, 3322, 3355, 3388, 3422, 3457, 3492
        .long   3529, 3566, 3604, 3643, 3684, 3726, 3768, 3813
        .long   3859, 3906, 3955, 4006, 4058, 4112, 4168, 4227
        .long   4287, 4349, 4414, 4481, 4550, 4622, 4696, 4773
        .long   4853, 4944, 5053, 5179, 5322, 5480, 5653, 5838
        .long   6035, 6244, 6462, 6690, 6925, 7166, 7414, 7665
        .long   7921, 8178, 8437, 8697, 8955, 9212, 9466, 9715
        .long   9960, 10198, 10429, 10652, 10865, 11068, 11260, 11439
        .long   11610, 11780, 11949, 12116, 12282, 12447, 12609, 12771
        .long   12930, 13088, 13244, 13399, 13552, 13703, 13852, 13999
        .long   14144, 14287, 14428, 14567, 14704, 14839, 14972, 15102
        .long   15231, 15357, 15480, 15601, 15720, 15836, 15950, 16061
O3_TB_KMUL:
        .long   0, 63, 130, 202, 278, 359, 443, 532
        .long   625, 721, 822, 925, 1033, 1144, 1258, 1375
        .long   1495, 1619, 1745, 1874, 2005, 2139, 2276, 2415
        .long   2556, 2699, 2844, 2991, 3140, 3290, 3442, 3596
        .long   3751, 3911, 4080, 4258, 4444, 4638, 4839, 5047
        .long   5261, 5481, 5707, 5938, 6173, 6412, 6655, 6901
        .long   7150, 7401, 7654, 7909, 8164, 8420, 8676, 8931
        .long   9185, 9439, 9690, 9939, 10185, 10428, 10668, 10903
        .long   11134, 11361, 11585, 11806, 12025, 12243, 12461, 12679
        .long   12898, 13119, 13342, 13567, 13797, 14030, 14268, 14512
        .long   14762, 15019, 15284, 15554, 15831, 16112, 16398, 16687
        .long   16980, 17275, 17571, 17869, 18168, 18466, 18763, 19059
        .long   19359, 19669, 19986, 20308, 20634, 20961, 21287, 21610
        .long   21928, 22239, 22541, 22831, 23108, 23370, 23614, 23846
        .long   24075, 24300, 24521, 24736, 24947, 25152, 25352, 25545
        .long   25732, 25913, 26086, 26252, 26410, 26561, 26703, 26836
O3_TB_GCOMP:
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
        .long   10396, 10396, 10396, 10396, 10396, 10396, 10396, 10396
O3_DF_GIN:
        .long   0, 918, 1835, 2753, 3670, 4588, 5505, 6423
        .long   7340, 8258, 9175, 10093, 11010, 11928, 12845, 13763
        .long   14680, 15598, 16515, 17433, 18350, 19268, 20185, 21103
        .long   22020, 22938, 747, 778, 811, 845, 881, 918
        .long   956, 996, 1038, 1082, 1127, 1175, 1224, 1275
        .long   1329, 1385, 1443, 1504, 1567, 1633, 1701, 1773
        .long   1847, 1925, 2006, 2090, 2178, 2270, 2365, 2464
        .long   2568, 2676, 2788, 2906, 3028, 3155, 3287, 3426
        .long   3570, 3720, 3876, 4039, 4208, 4385, 4570, 4762
        .long   4962, 5170, 5387, 5614, 5850, 6096, 6352, 6619
        .long   6897, 7187, 7489, 7803, 8131, 8473, 8829, 9200
        .long   9587, 9989, 10409, 10847, 11302, 11777, 12272, 12788
        .long   13325, 13885, 14469, 15077, 15710, 16371, 17059, 17775
        .long   18522, 19301, 20112, 20957, 21838, 22755, 23712, 24708
        .long   25746, 26828, 27956, 29130, 30354, 31630, 32959, 34344
        .long   35788, 37291, 38859, 40491, 42193, 43966, 45814, 47739
O3_DF_OCOMP:
        .long   4096, 4096, 4096, 4096, 4096, 4096, 4096, 4096
        .long   4096, 4096, 4096, 4096, 4096, 4096, 4096, 4096
        .long   4096, 4096, 4096, 4096, 4096, 4096, 4096, 4096
        .long   4096, 4096, 3851, 3620, 3403, 3200, 3008, 2828
        .long   2659, 2499, 2350, 2209, 2077, 1952, 1836, 1726
        .long   1622, 1525, 1434, 1348, 1267, 1191, 1120, 1053
        .long   990, 931, 875, 823, 773, 727, 683, 643
        .long   604, 568, 534, 502, 472, 444, 417, 392
        .long   369, 347, 326, 306, 288, 271, 254, 239
        .long   225, 211, 199, 187, 176, 165, 155, 146
        .long   137, 129, 121, 114, 107, 101, 95, 89
        .long   84, 79, 74, 70, 65, 62, 58, 54
        .long   51, 48, 45, 42, 40, 38, 35, 33
        .long   31, 29, 28, 26, 24, 23, 22, 20
        .long   19, 18, 17, 16, 15, 14, 13, 12
        .long   12, 11, 10, 10, 9, 9, 8, 8
O3_DF_OGAIN:
        .long   4096, 4096, 4096, 4096, 4096, 4096, 4096, 4096
        .long   4096, 4096, 4096, 4096, 4096, 4096, 4096, 4096
        .long   4096, 4096, 4096, 4096, 4096, 4096, 4096, 4096
        .long   4096, 4096, 4046, 3996, 3947, 3899, 3851, 3803
        .long   3757, 3711, 3665, 3620, 3576, 3532, 3489, 3446
        .long   3403, 3362, 3320, 3280, 3239, 3200, 3160, 3122
        .long   3083, 3045, 3008, 2971, 2935, 2899, 2863, 2828
        .long   2793, 2759, 2725, 2692, 2659, 2626, 2594, 2562
        .long   2530, 2499, 2469, 2438, 2408, 2379, 2350, 2321
        .long   2292, 2264, 2236, 2209, 2182, 2155, 2129, 2103
        .long   2077, 2051, 2026, 2001, 1977, 1952, 1928, 1905
        .long   1881, 1858, 1836, 1813, 1791, 1769, 1747, 1726
        .long   1704, 1683, 1663, 1642, 1622, 1602, 1583, 1563
        .long   1544, 1525, 1506, 1488, 1470, 1452, 1434, 1416
        .long   1399, 1382, 1365, 1348, 1331, 1315, 1299, 1283
        .long   1267, 1252, 1236, 1221, 1206, 1191, 1177, 1162
O3_DF_TRK_HZ:
        .long   0, 2, 5, 10, 15, 21, 28, 35
        .long   43, 51, 60, 69, 78, 88, 99, 110
        .long   121, 132, 144, 156, 169, 182, 195, 208
        .long   222, 236, 250, 265, 280, 295, 310, 326
        .long   341, 358, 374, 391, 407, 425, 442, 459
        .long   477, 495, 513, 532, 551, 569, 589, 608
        .long   627, 647, 667, 687, 707, 728, 749, 769
        .long   791, 812, 833, 855, 877, 899, 921, 943
        .long   966, 989, 1012, 1035, 1058, 1081, 1105, 1129
        .long   1153, 1177, 1201, 1225, 1250, 1275, 1300, 1325
        .long   1350, 1375, 1401, 1427, 1452, 1478, 1505, 1531
        .long   1557, 1584, 1611, 1638, 1665, 1692, 1719, 1747
        .long   1774, 1802, 1830, 1858, 1887, 1915, 1943, 1972
        .long   2001, 2030, 2059, 2088, 2117, 2147, 2176, 2206
        .long   2236, 2266, 2296, 2327, 2357, 2387, 2418, 2449
        .long   2480, 2511, 2542, 2573, 2605, 2636, 2668, 2700
O3_DF_VEG:
        .long   1049667915, 1051312798, 1052846414, 1054276140, 1055608885, 1056851114, 1058008877, 1059087833
        .long   1060093274, 1061030143, 1061903064, 1062716352, 1063474040, 1064179893, 1064837426, 1065449919
        .long   1066020435, 1066551830, 1067046768, 1067507736, 1067937052, 1068336878, 1068709229, 1069055984
        .long   1069378897, 1069679599, 1069959612, 1070220356, 1070463152, 1070689231, 1070899742, 1071095754
        .long   1071278263, 1071448197, 1071606421, 1071753740, 1071890905, 1072018613, 1072137517, 1072248222
        .long   1072351293, 1072447255, 1072536598, 1072619779, 1072697222, 1072769322, 1072836448, 1072898942
        .long   1072957124, 1073011291, 1073061721, 1073108670, 1073152379, 1073193072, 1073230955, 1073266225
        .long   1073299059, 1073329628, 1073358086, 1073384580, 1073409245, 1073432207, 1073453584, 1073473485
        .long   1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013
        .long   1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013
        .long   1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013
        .long   1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013
        .long   1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013
        .long   1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013
        .long   1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013
        .long   1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013, 1073492013
O3_DF_VSUS:
        .long   0, 0, 0, 0, 0, 0, 0, 0
        .long   0, 0, 0, 0, 0, 0, 0, 0
        .long   0, 0, 0, 0, 0, 0, 0, 0
        .long   0, 0, 0, 0, 0, 0, 0, 0
        .long   0, 0, 0, 0, 0, 0, 0, 0
        .long   0, 0, 0, 0, 0, 0, 0, 0
        .long   0, 0, 0, 0, 0, 0, 0, 0
        .long   0, 0, 0, 0, 0, 0, 0, 0
        .long   0, 17043521, 34087042, 51130563, 68174084, 85217605, 102261126, 119304647
        .long   136348168, 153391689, 170435210, 187478731, 204522252, 221565773, 238609294, 255652815
        .long   272696336, 289739857, 306783378, 323826899, 340870420, 357913941, 374957462, 392000983
        .long   409044504, 426088025, 443131546, 460175067, 477218588, 494262109, 511305630, 528349151
        .long   545392672, 562436193, 579479714, 596523235, 613566756, 630610277, 647653798, 664697319
        .long   681740840, 698784361, 715827882, 732871403, 749914924, 766958445, 784001966, 801045487
        .long   818089008, 835132529, 852176050, 869219571, 886263092, 903306613, 920350134, 937393655
        .long   954437176, 971480697, 988524218, 1005567739, 1022611260, 1039654781, 1056698302, 1073741823
O3_DF_SLIDE:
        .long   519, 500, 482, 466, 451, 436, 423, 410
        .long   398, 387, 377, 367, 357, 348, 339, 331
        .long   323, 316, 309, 302, 296, 289, 283, 278
        .long   272, 267, 262, 257, 252, 248, 243, 239
        .long   235, 231, 227, 223, 220, 216, 213, 210
        .long   207, 204, 201, 198, 195, 192, 189, 187
        .long   184, 182, 180, 177, 175, 173, 171, 169
        .long   166, 164, 163, 161, 159, 157, 155, 153
        .long   152, 150, 148, 147, 145, 144, 142, 141
        .long   139, 138, 137, 135, 134, 133, 131, 130
        .long   129, 128, 127, 125, 124, 123, 122, 121
        .long   120, 119, 118, 117, 116, 115, 114, 113
        .long   112, 111, 110, 109, 109, 108, 107, 106
        .long   105, 104, 104, 103, 102, 101, 101, 100
        .long   99, 98, 98, 97, 96, 96, 95, 94
        .long   94, 93, 92, 92, 91, 91, 90, 89
O3_DF_ADEC:
        .long   2, 3, 4, 5, 6, 7, 8, 9
        .long   10, 11, 12, 13, 14, 15, 16, 17
        .long   18, 19, 20, 21, 22, 23, 24, 25
        .long   26, 27, 28, 29, 30, 31, 32, 33
        .long   34, 35, 36, 37, 38, 39, 40, 41
        .long   42, 43, 44, 45, 46, 47, 48, 49
        .long   50, 51, 52, 53, 54, 55, 56, 57
        .long   58, 59, 60, 61, 62, 63, 64, 65
        .long   66, 67, 68, 69, 70, 71, 72, 73
        .long   74, 75, 76, 77, 78, 79, 80, 81
        .long   82, 83, 84, 85, 86, 87, 88, 89
        .long   90, 91, 92, 93, 94, 95, 96, 97
        .long   98, 99, 100, 101, 102, 103, 104, 105
        .long   106, 107, 108, 109, 110, 111, 112, 113
        .long   114, 115, 116, 117, 118, 119, 120, 121
        .long   122, 123, 124, 125, 126, 127, 128, 129
O3_DF_SATK:
        .long   903499878, 1007439732, 1000471088, 993059915, 985205808, 976910498, 968177822, 959013679
        .long   949425959, 939424457, 929020773, 918228195, 907061574, 895537185, 883672587, 871486473
        .long   858998522, 846229246, 833199839, 819932031, 806447945, 792769954, 778920551, 764922226
        .long   750797344, 736568037, 722256105, 707882922, 693469355, 679035687, 664601558, 650185904
        .long   635806910, 621481975, 607227672, 593059733, 578993024, 565041539, 551218392, 537535816
        .long   524005173, 510636957, 497440813, 484425551, 471599166, 458968862, 446541073, 434321497
        .long   422315115, 410526226, 398958478, 387614894, 376497907, 365609389, 354950684, 344522638
        .long   334325629, 324359599, 314624082, 305118232, 295840853, 286790423, 277965122, 269362859
        .long   260981292, 252817852, 244869766, 237134080, 229607673, 222287280, 215169510, 208250859
        .long   201527730, 194996446, 188653262, 182494380, 176515962, 170714137, 165085016, 159624698
        .long   154329281, 149194870, 144217583, 139393557, 134718959, 130189987, 125802874, 121553900
        .long   117439385, 113455705, 109599283, 105866603, 102254204, 98758685, 95376710, 92105004
        .long   88940358, 85879630, 82919742, 80057685, 77290517, 74615365, 72029422, 69529950
        .long   67114277, 64779798, 62523976, 60344338, 58238478, 56204051, 54238780, 52340447
        .long   50506897, 48736034, 47025825, 45374292, 43779516, 42239634, 40752837, 39317370
        .long   37931533, 36593674, 35302194, 34055541, 32852212, 31690751, 30569747, 29487834
O3_DF_CUTX:
        .long   9132, 9251, 9371, 9490, 9609, 9728, 9848, 9967
        .long   10086, 10206, 10325, 10444, 10563, 10683, 10802, 10921
        .long   11040, 11160, 11279, 11398, 11517, 11637, 11756, 11875
        .long   11994, 12114, 12233, 12352, 12472, 12591, 12710, 12829
        .long   12949, 13068, 13187, 13306, 13426, 13545, 13664, 13783
        .long   13903, 14022, 14141, 14261, 14380, 14499, 14618, 14738
        .long   14857, 14976, 15095, 15215, 15334, 15453, 15572, 15692
        .long   15811, 15930, 16050, 16169, 16288, 16407, 16527, 16646
        .long   16765, 16884, 17004, 17123, 17242, 17361, 17481, 17600
        .long   17719, 17839, 17958, 18077, 18196, 18316, 18435, 18554
        .long   18673, 18793, 18912, 19031, 19150, 19270, 19389, 19508
        .long   19628, 19747, 19866, 19985, 20105, 20224, 20343, 20462
        .long   20582, 20701, 20820, 20939, 21059, 21178, 21297, 21416
        .long   21536, 21655, 21774, 21894, 22013, 22132, 22251, 22371
        .long   22490, 22609, 22728, 22848, 22967, 23086, 23205, 23325
        .long   23444, 23563, 23683, 23802, 23921, 24040, 24160, 24279
O3_DF_HZ:
        .long   20, 20, 21, 21, 21, 21, 22, 22
        .long   22, 23, 23, 23, 24, 24, 24, 25
        .long   25, 26, 26, 26, 27, 27, 27, 28
        .long   28, 29, 29, 30, 30, 30, 31, 31
        .long   32, 32, 33, 33, 34, 34, 35, 35
        .long   36, 36, 37, 37, 38, 38, 39, 39
        .long   40, 41, 41, 42, 42, 43, 44, 44
        .long   45, 46, 46, 47, 48, 48, 49, 50
        .long   50, 51, 52, 53, 53, 54, 55, 56
        .long   57, 57, 58, 59, 60, 61, 62, 63
        .long   63, 64, 65, 66, 67, 68, 69, 70
        .long   71, 72, 73, 74, 76, 77, 78, 79
        .long   80, 81, 82, 84, 85, 86, 87, 89
        .long   90, 91, 92, 94, 95, 97, 98, 99
        .long   101, 102, 104, 105, 107, 108, 110, 112
        .long   113, 115, 116, 118, 120, 122, 123, 125
        .long   127, 129, 131, 133, 135, 137, 138, 141
        .long   143, 145, 147, 149, 151, 153, 155, 158
        .long   160, 162, 165, 167, 170, 172, 174, 177
        .long   180, 182, 185, 188, 190, 193, 196, 199
        .long   202, 205, 207, 211, 214, 217, 220, 223
        .long   226, 230, 233, 236, 240, 243, 247, 250
        .long   254, 258, 261, 265, 269, 273, 277, 281
        .long   285, 289, 293, 298, 302, 306, 311, 315
        .long   320, 325, 329, 334, 339, 344, 349, 354
        .long   359, 364, 370, 375, 381, 386, 392, 397
        .long   403, 409, 415, 421, 427, 433, 440, 446
        .long   453, 459, 466, 473, 479, 486, 494, 501
        .long   508, 515, 523, 530, 538, 546, 554, 562
        .long   570, 578, 587, 595, 604, 613, 622, 631
        .long   640, 649, 659, 668, 678, 688, 698, 708
        .long   718, 729, 739, 750, 761, 772, 783, 795
        .long   806, 818, 830, 842, 854, 867, 879, 892
        .long   905, 918, 932, 945, 959, 973, 987, 1001
        .long   1016, 1031, 1046, 1061, 1076, 1092, 1108, 1124
        .long   1140, 1157, 1174, 1191, 1208, 1226, 1244, 1262
        .long   1280, 1299, 1318, 1337, 1356, 1376, 1396, 1416
        .long   1437, 1458, 1479, 1500, 1522, 1544, 1567, 1590
        .long   1613, 1636, 1660, 1684, 1709, 1733, 1759, 1784
        .long   1810, 1837, 1863, 1890, 1918, 1946, 1974, 2003
        .long   2032, 2061, 2091, 2122, 2153, 2184, 2216, 2248
        .long   2281, 2314, 2348, 2382, 2416, 2451, 2487, 2523
        .long   2560, 2597, 2635, 2673, 2712, 2752, 2792, 2832
        .long   2874, 2915, 2958, 3001, 3044, 3089, 3134, 3179
        .long   3225, 3272, 3320, 3368, 3417, 3467, 3517, 3568
        .long   3620, 3673, 3726, 3781, 3836, 3891, 3948, 4005
        .long   4064, 4123, 4183, 4244, 4305, 4368, 4432, 4496
        .long   4561, 4628, 4695, 4763, 4833, 4903, 4974, 5047
        .long   5120, 5194, 5270, 5347, 5424, 5503, 5583, 5665
        .long   5747, 5831, 5915, 6001, 6089, 6177, 6267, 6358
        .long   6451, 6545, 6640, 6736, 6834, 6934, 7035, 7137
        .long   7241, 7346, 7453, 7561, 7671, 7783, 7896, 8011
        .long   8127, 8246, 8366, 8487, 8611, 8736, 8863, 8992
        .long   9123, 9255, 9390, 9527, 9665, 9806, 9948, 10093
        .long   10240, 10389, 10540, 10693, 10849, 11007, 11167, 11329
        .long   11494, 11661, 11831, 12003, 12177, 12355
O3_LADDER_B:
        .long   66, 67, 68, 69, 70, 71, 72, 73
        .long   74, 75, 76, 77, 78, 79, 80, 82
        .long   83, 84, 85, 86, 88, 89, 90, 92
        .long   93, 94, 96, 97, 98, 100, 101, 103
        .long   104, 106, 107, 109, 110, 112, 113, 115
        .long   117, 118, 120, 122, 124, 125, 127, 129
        .long   131, 133, 135, 137, 139, 141, 143, 145
        .long   147, 149, 151, 153, 155, 158, 160, 162
        .long   165, 167, 169, 172, 174, 177, 179, 182
        .long   185, 187, 190, 193, 195, 198, 201, 204
        .long   207, 210, 213, 216, 219, 222, 225, 229
        .long   232, 235, 239, 242, 245, 249, 253, 256
        .long   260, 263, 267, 271, 275, 279, 283, 287
        .long   291, 295, 299, 304, 308, 312, 317, 321
        .long   326, 331, 335, 340, 345, 350, 355, 360
        .long   365, 370, 375, 381, 386, 392, 397, 403
        .long   408, 414, 420, 426, 432, 438, 444, 451
        .long   457, 463, 470, 477, 483, 490, 497, 504
        .long   511, 518, 526, 533, 541, 548, 556, 564
        .long   572, 580, 588, 596, 604, 613, 621, 630
        .long   639, 648, 657, 666, 675, 684, 694, 704
        .long   713, 723, 733, 744, 754, 764, 775, 786
        .long   796, 807, 819, 830, 841, 853, 865, 876
        .long   888, 901, 913, 926, 938, 951, 964, 977
        .long   991, 1004, 1018, 1032, 1046, 1060, 1074, 1089
        .long   1103, 1118, 1133, 1149, 1164, 1180, 1196, 1212
        .long   1228, 1245, 1261, 1278, 1295, 1312, 1330, 1348
        .long   1366, 1384, 1402, 1421, 1439, 1458, 1478, 1497
        .long   1517, 1537, 1557, 1577, 1598, 1619, 1640, 1661
        .long   1683, 1705, 1727, 1749, 1772, 1795, 1818, 1841
        .long   1865, 1889, 1913, 1937, 1962, 1987, 2012, 2038
        .long   2063, 2089, 2116, 2142, 2169, 2196, 2224, 2252
        .long   2280, 2308, 2337, 2366, 2395, 2424, 2454, 2484
        .long   2515, 2545, 2576, 2608, 2639, 2671, 2703, 2736
        .long   2769, 2802, 2835, 2869, 2903, 2938, 2972, 3007
        .long   3043, 3078, 3114, 3151, 3187, 3224, 3261, 3299
        .long   3337, 3375, 3413, 3452, 3491, 3531, 3571, 3611
        .long   3651, 3692, 3733, 3774, 3816, 3858, 3900, 3943
        .long   3986, 4029, 4072, 4116, 4160, 4205, 4249, 4294
        .long   4340, 4385, 4431, 4477, 4524, 4571, 4618, 4665
        .long   4713, 4760, 4809, 4857, 4906, 4955, 5004, 5053
        .long   5103, 5153, 5203, 5254, 5304, 5355, 5406, 5458
        .long   5509, 5561, 5613, 5665, 5718, 5770, 5823, 5876
        .long   5930, 5983, 6037, 6090, 6144, 6198, 6253, 6307
        .long   6361, 6416, 6471, 6526, 6581, 6636, 6691, 6747
        .long   6802, 6858, 6913, 6969, 7025, 7081, 7137, 7193
        .long   7249, 7305, 7361, 7417, 7473, 7529, 7585, 7642
        .long   7698, 7754, 7810, 7866, 7922, 7978, 8034, 8090
        .long   8146, 8201, 8257, 8313, 8368, 8423, 8479, 8534
        .long   8589, 8644, 8698, 8753, 8807, 8862, 8916, 8970
        .long   9023, 9077, 9130, 9183, 9236, 9289, 9341, 9393
        .long   9445, 9497, 9548, 9600, 9650, 9701, 9751, 9801
        .long   9851, 9900, 9949, 9998, 10047, 10095, 10142, 10190
        .long   10236, 10283, 10329, 10375, 10420, 10465, 10510, 10554
        .long   10598, 10641, 10684, 10726, 10768, 10809, 10850, 10891
        .long   10931, 10970, 11009, 11047, 11085, 11122
O3_LADDER_K:
        .long   4370, 4370, 4370, 4370, 4371, 4371, 4371, 4371
        .long   4372, 4372, 4372, 4373, 4373, 4373, 4373, 4374
        .long   4374, 4374, 4375, 4375, 4375, 4376, 4376, 4376
        .long   4377, 4377, 4378, 4378, 4378, 4379, 4379, 4379
        .long   4380, 4380, 4381, 4381, 4382, 4382, 4382, 4383
        .long   4383, 4384, 4384, 4385, 4385, 4386, 4386, 4387
        .long   4387, 4388, 4388, 4389, 4389, 4390, 4390, 4391
        .long   4391, 4392, 4393, 4393, 4394, 4394, 4395, 4396
        .long   4396, 4397, 4398, 4398, 4399, 4400, 4400, 4401
        .long   4402, 4402, 4403, 4404, 4405, 4405, 4406, 4407
        .long   4408, 4409, 4409, 4410, 4411, 4412, 4413, 4414
        .long   4415, 4416, 4417, 4417, 4418, 4419, 4420, 4421
        .long   4422, 4423, 4424, 4426, 4427, 4428, 4429, 4430
        .long   4431, 4432, 4433, 4435, 4436, 4437, 4438, 4440
        .long   4441, 4442, 4443, 4445, 4446, 4447, 4449, 4450
        .long   4452, 4453, 4455, 4456, 4458, 4459, 4461, 4462
        .long   4464, 4466, 4467, 4469, 4471, 4472, 4474, 4476
        .long   4478, 4480, 4482, 4483, 4485, 4487, 4489, 4491
        .long   4493, 4495, 4498, 4500, 4502, 4504, 4506, 4509
        .long   4511, 4513, 4516, 4518, 4520, 4523, 4525, 4528
        .long   4530, 4533, 4536, 4538, 4541, 4544, 4547, 4550
        .long   4553, 4555, 4558, 4561, 4565, 4568, 4571, 4574
        .long   4577, 4581, 4584, 4587, 4591, 4594, 4598, 4602
        .long   4605, 4609, 4613, 4617, 4621, 4625, 4629, 4633
        .long   4637, 4641, 4645, 4650, 4654, 4658, 4663, 4668
        .long   4672, 4677, 4682, 4687, 4692, 4697, 4702, 4707
        .long   4712, 4718, 4723, 4728, 4734, 4740, 4745, 4751
        .long   4757, 4763, 4769, 4776, 4782, 4788, 4795, 4801
        .long   4808, 4815, 4822, 4829, 4836, 4843, 4850, 4858
        .long   4865, 4873, 4881, 4889, 4897, 4905, 4913, 4921
        .long   4930, 4939, 4947, 4956, 4965, 4974, 4984, 4993
        .long   5003, 5013, 5023, 5033, 5043, 5053, 5064, 5075
        .long   5085, 5097, 5108, 5119, 5131, 5142, 5154, 5167
        .long   5179, 5191, 5204, 5217, 5230, 5243, 5257, 5271
        .long   5285, 5299, 5313, 5328, 5343, 5358, 5373, 5389
        .long   5404, 5420, 5437, 5453, 5470, 5487, 5505, 5522
        .long   5540, 5558, 5577, 5596, 5615, 5634, 5654, 5674
        .long   5694, 5715, 5736, 5758, 5779, 5801, 5824, 5847
        .long   5870, 5893, 5917, 5942, 5966, 5991, 6017, 6043
        .long   6069, 6096, 6123, 6151, 6179, 6208, 6237, 6267
        .long   6297, 6327, 6358, 6390, 6422, 6455, 6488, 6522
        .long   6556, 6591, 6626, 6662, 6699, 6736, 6774, 6813
        .long   6852, 6892, 6932, 6974, 7015, 7058, 7101, 7145
        .long   7190, 7236, 7282, 7329, 7377, 7426, 7476, 7526
        .long   7578, 7630, 7683, 7737, 7792, 7848, 7904, 7962
        .long   8021, 8081, 8142, 8204, 8266, 8331, 8396, 8462
        .long   8529, 8598, 8668, 8738, 8811, 8884, 8959, 9035
        .long   9112, 9190, 9270, 9351, 9434, 9518, 9604, 9691
        .long   9779, 9869, 9961, 10054, 10148, 10244, 10342, 10442
        .long   10543, 10646, 10750, 10856, 10964, 11074, 11186, 11299
        .long   11415, 11532, 11651, 11772, 11895, 12020, 12147, 12276
        .long   12407, 12540, 12675, 12812, 12951, 13092, 13235, 13381
        .long   13528, 13678, 13830, 13984, 14140, 14298, 14459, 14621
        .long   14786, 14953, 15122, 15293, 15466, 15641, 15819, 15998
        .long   16179, 16362, 16547, 16734, 16923, 17113, 17305, 17499
        .long   17694, 17890, 18088, 18287, 18487, 18688
O3_KF:
        .long   10280, 10280, 10280, 10280, 10280, 10280, 10280, 10280
        .long   10280, 10280, 10280, 10280, 10280, 10280, 10280, 10280
        .long   10280, 10280, 10280, 10280, 10280, 10280, 10280, 10280
        .long   10280, 10280, 10280, 10280, 10280, 10280, 10280, 10280
        .long   10280, 10280, 10280, 10280, 10280, 10280, 10280, 10280
        .long   10280, 10280, 10280, 10280, 10280, 10280, 10280, 10280
        .long   10280, 10280, 10280, 10280, 10280, 10280, 10280, 10280
        .long   10280, 10280, 10280, 10280, 10280, 10280, 10280, 10280
        .long   10280, 10280, 10280, 10280, 10280, 10280, 10280, 10280
        .long   10280, 10280, 10280, 10280, 10280, 10280, 10280, 10280
        .long   10280, 10280, 10280, 10280, 10280, 10280, 10280, 10280
        .long   10280, 10280, 10280, 10280, 10280, 10280, 10280, 10280
        .long   10280, 10280, 10280, 10280, 10280, 10280, 10280, 10280
        .long   10280, 10280, 10280, 10280, 10280, 10280, 10280, 10280
        .long   10280, 10188, 10122, 10031, 9949, 9867, 9786, 9713
        .long   9638, 9567, 9500, 9415, 9350, 9274, 9214, 9140
        .long   9087, 9017, 8952, 8887, 8827, 8769, 8711, 8641
        .long   8590, 8539, 8477, 8419, 8373, 8318, 8265, 8213
        .long   8164, 8117, 8060, 8016, 7965, 7923, 7875, 7828
        .long   7783, 7741, 7697, 7658, 7619, 7575, 7539, 7496
        .long   7457, 7419, 7381, 7346, 7311, 7275, 7238, 7201
        .long   7170, 7138, 7104, 7068, 7035, 7005, 6972, 6941
        .long   6914, 6883, 6851, 6825, 6796, 6767, 6737, 6712
        .long   6685, 6656, 6630, 6602, 6579, 6552, 6528, 6503
        .long   6478, 6457, 6433, 6409, 6387, 6367, 6345, 6324
        .long   6305, 6285, 6265, 6244, 6227, 6207, 6189, 6172
        .long   6155, 6136, 6121, 6104, 6089, 6073, 6058, 6042
        .long   6027, 6011, 5998, 5983, 5970, 5958, 5942, 5931
        .long   5918, 5904, 5892, 5880, 5869, 5857, 5846, 5834
        .long   5824, 5813, 5802, 5792, 5781, 5772, 5761, 5752
        .long   5742, 5732, 5724, 5715, 5706, 5697, 5688, 5680
        .long   5672, 5664, 5654, 5646, 5639, 5632, 5623, 5616
        .long   5609, 5602, 5594, 5587, 5580, 5574, 5567, 5559
        .long   5552, 5546, 5539, 5533, 5526, 5520, 5513, 5506
        .long   5500, 5494, 5489, 5482, 5476, 5471, 5465, 5460
        .long   5455, 5450, 5444, 5439, 5434, 5429, 5424, 5420
        .long   5415, 5410, 5405, 5401, 5397, 5394, 5390, 5386
        .long   5383, 5379, 5375, 5371, 5368, 5366, 5361, 5358
        .long   5356, 5353, 5351, 5347, 5345, 5343, 5340, 5337
        .long   5336, 5333, 5331, 5330, 5328, 5327, 5325, 5323
        .long   5322, 5321, 5320, 5319, 5318, 5317, 5317, 5316
        .long   5315, 5316, 5315, 5315, 5315, 5315, 5315, 5316
        .long   5316, 5316, 5318, 5318, 5320, 5320, 5323, 5323
        .long   5325, 5326, 5328, 5330, 5333, 5334, 5337, 5339
        .long   5341, 5343, 5347, 5349, 5352, 5355, 5359, 5362
        .long   5365, 5368, 5372, 5375, 5380, 5383, 5388, 5391
        .long   5397, 5400, 5405, 5410, 5414, 5419, 5423, 5429
        .long   5434, 5440, 5445, 5452, 5457, 5463, 5469, 5475
        .long   5482, 5487, 5495, 5501, 5508, 5515, 5523, 5529
        .long   5537, 5545, 5553, 5561, 5568, 5578, 5585, 5594
        .long   5602, 5611, 5620, 5630, 5639, 5648, 5658, 5667
        .long   5677, 5687, 5698, 5710, 5719, 5731, 5742, 5753
        .long   5765, 5777, 5788, 5800, 5813, 5827, 5838, 5852
        .long   5863, 5877, 5891, 5904, 5917, 5931, 5946, 5959
        .long   5971, 5983, 5995, 6007, 6020, 6032, 6045, 6059
        .long   6073, 6086, 6099, 6112, 6127, 6140
O3_LG:
        .long   2327, 2327, 2327, 2327, 2327, 2327, 2327, 2327
        .long   2327, 2327, 2327, 2327, 2327, 2327, 2327, 2327
        .long   2327, 2327, 2327, 2327, 2327, 2327, 2327, 2327
        .long   2327, 2327, 2327, 2327, 2327, 2327, 2327, 2327
        .long   2327, 2327, 2327, 2327, 2327, 2327, 2327, 2327
        .long   2327, 2327, 2327, 2327, 2327, 2327, 2327, 2327
        .long   2327, 2327, 2327, 2327, 2327, 2327, 2327, 2327
        .long   2327, 2327, 2327, 2327, 2327, 2327, 2327, 2327
        .long   2327, 2327, 2327, 2327, 2327, 2327, 2327, 2327
        .long   2327, 2327, 2327, 2327, 2327, 2327, 2327, 2327
        .long   2327, 2327, 2327, 2327, 2327, 2327, 2327, 2327
        .long   2327, 2327, 2327, 2327, 2327, 2327, 2327, 2327
        .long   2327, 2327, 2327, 2327, 2327, 2327, 2327, 2327
        .long   2327, 2327, 2327, 2327, 2327, 2327, 2327, 2327
        .long   2318, 2302, 2286, 2270, 2255, 2239, 2224, 2209
        .long   2195, 2180, 2166, 2152, 2138, 2125, 2112, 2099
        .long   2086, 2073, 2061, 2048, 2036, 2025, 2013, 2002
        .long   1991, 1980, 1969, 1959, 1948, 1938, 1928, 1919
        .long   1909, 1900, 1891, 1882, 1874, 1865, 1857, 1849
        .long   1841, 1834, 1826, 1819, 1812, 1806, 1799, 1793
        .long   1787, 1781, 1775, 1770, 1765, 1760, 1755, 1750
        .long   1746, 1741, 1737, 1734, 1730, 1727, 1724, 1721
        .long   1718, 1715, 1713, 1711, 1709, 1708, 1706, 1705
        .long   1704, 1704, 1703, 1703, 1703, 1703, 1703, 1704
        .long   1704, 1705, 1706, 1707, 1708, 1709, 1711, 1712
        .long   1714, 1716, 1717, 1720, 1722, 1724, 1726, 1729
        .long   1731, 1734, 1737, 1740, 1743, 1746, 1749, 1752
        .long   1756, 1759, 1763, 1767, 1770, 1774, 1778, 1782
        .long   1786, 1790, 1795, 1799, 1803, 1808, 1812, 1817
        .long   1822, 1826, 1831, 1836, 1841, 1846, 1851, 1856
        .long   1861, 1866, 1871, 1877, 1882, 1887, 1892, 1898
        .long   1903, 1909, 1914, 1919, 1925, 1930, 1936, 1941
        .long   1947, 1952, 1958, 1963, 1969, 1974, 1980, 1985
        .long   1991, 1996, 2002, 2007, 2012, 2018, 2023, 2028
        .long   2034, 2039, 2044, 2049, 2055, 2060, 2065, 2070
        .long   2076, 2081, 2086, 2092, 2097, 2102, 2108, 2113
        .long   2119, 2124, 2130, 2135, 2141, 2147, 2152, 2158
        .long   2164, 2170, 2176, 2182, 2188, 2194, 2201, 2207
        .long   2213, 2220, 2226, 2233, 2240, 2247, 2254, 2261
        .long   2268, 2275, 2282, 2290, 2297, 2305, 2313, 2321
        .long   2329, 2337, 2346, 2354, 2363, 2372, 2381, 2390
        .long   2399, 2409, 2418, 2428, 2438, 2448, 2459, 2469
        .long   2480, 2491, 2502, 2514, 2526, 2537, 2550, 2562
        .long   2575, 2587, 2601, 2614, 2628, 2642, 2657, 2673
        .long   2690, 2707, 2725, 2743, 2762, 2782, 2802, 2824
        .long   2846, 2868, 2892, 2916, 2941, 2966, 2993, 3020
        .long   3048, 3077, 3106, 3137, 3168, 3200, 3233, 3267
        .long   3301, 3337, 3373, 3411, 3449, 3489, 3529, 3570
        .long   3613, 3656, 3701, 3746, 3793, 3840, 3889, 3939
        .long   3990, 4043, 4096, 4151, 4207, 4264, 4323, 4383
        .long   4444, 4506, 4570, 4636, 4703, 4771, 4841, 4912
        .long   4985, 5059, 5135, 5213, 5292, 5373, 5456, 5540
        .long   5627, 5715, 5804, 5896, 5990, 6086, 6183, 6283
        .long   6384, 6488, 6594, 6702, 6812, 6924, 7039, 7080
        .long   7080, 7080, 7080, 7080, 7080, 7080, 7080, 7080
        .long   7080, 7080, 7080, 7080, 7080, 7080
O3_TB_UD:
        .long   0, 29, 57, 85, 113, 140, 167, 193
        .long   218, 244, 268, 292, 315, 337, 359, 379
        .long   399, 418, 436, 453, 469, 484, 498, 510
        .long   522, 532, 541, 549, 555, 560, 564, 566
        .long   567, 567, 566, 564, 561, 558, 554, 549
        .long   544, 539, 533, 527, 521, 515, 508, 501
        .long   494, 487, 481, 474, 468, 461, 455, 450
        .long   444, 439, 435, 431, 428, 425, 423, 422
        .long   421, 422, 422, 423, 424, 425, 426, 428
        .long   429, 431, 433, 435, 438, 440, 442, 444
        .long   447, 449, 452, 455, 459, 462, 467, 471
        .long   475, 480, 485, 490, 495, 500, 506, 511
        .long   517, 524, 532, 540, 549, 558, 567, 576
        .long   585, 594, 601, 608, 615, 619, 623, 626
        .long   629, 631, 634, 636, 639, 641, 643, 645
        .long   647, 648, 650, 651, 652, 652, 653, 653
O3_KD:
        .long   78935, 76988, 75111, 73302, 71557, 69873, 68249, 66680
        .long   65166, 63703, 62289, 60923, 59602, 58324, 57088, 54734
        .long   53613, 52526, 51474, 50454, 48506, 47576, 46674, 44947
        .long   44121, 43319, 41783, 41047, 40331, 38957, 38298, 37032
        .long   36424, 35255, 34693, 33611, 33091, 32088, 31605, 30673
        .long   29785, 29356, 28529, 27739, 26984, 26619, 25914, 25238
        .long   24591, 23971, 23376, 22805, 22257, 21731, 21225, 20738
        .long   20270, 19819, 19385, 18966, 18562, 17983, 17614, 17257
        .long   16745, 16417, 16100, 15644, 15352, 14931, 14661, 14272
        .long   13900, 13661, 13315, 12985, 12772, 12464, 12169, 11885
        .long   11613, 11352, 11100, 10859, 10626, 10401, 10185, 9909
        .long   9711, 9519, 9273, 9097, 8925, 8706, 8496, 8344
        .long   8150, 8009, 7827, 7653, 7486, 7325, 7170, 7021
        .long   6878, 6740, 6606, 6446, 6323, 6204, 6061, 5950
        .long   5818, 5690, 5592, 5473, 5359, 5249, 5143, 5041
        .long   4943, 4848, 4756, 4651, 4566, 4468, 4389, 4298
        .long   4224, 4139, 4057, 3978, 3902, 3829, 3758, 3678
        .long   3612, 3549, 3477, 3408, 3351, 3287, 3225, 3165
        .long   3107, 3051, 2990, 2938, 2881, 2832, 2779, 2727
        .long   2677, 2629, 2583, 2538, 2495, 2448, 2407, 2363
        .long   2321, 2279, 2240, 2201, 2164, 2128, 2090, 2053
        .long   2020, 1985, 1952, 1916, 1884, 1854, 1822, 1790
        .long   1763, 1733, 1702, 1675, 1648, 1620, 1593, 1569
        .long   1544, 1517, 1493, 1468, 1446, 1422, 1400, 1378
        .long   1355, 1334, 1313, 1292, 1272, 1252, 1233, 1214
        .long   1196, 1178, 1160, 1141, 1124, 1107, 1090, 1074
        .long   1058, 1042, 1027, 1011, 997, 982, 967, 953
        .long   939, 925, 912, 899, 887, 874, 861, 849
        .long   837, 825, 814, 802, 791, 780, 769, 759
        .long   748, 738, 728, 719, 709, 699, 690, 681
        .long   672, 663, 654, 646, 637, 629, 621, 613
        .long   605, 598, 590, 583, 575, 568, 561, 554
        .long   547, 541, 534, 528, 521, 515, 509, 503
        .long   497, 491, 486, 480, 475, 469, 464, 459
        .long   453, 448, 443, 439, 434, 429, 424, 420
        .long   415, 411, 407, 403, 398, 394, 390, 386
        .long   383, 379, 375, 371, 368, 364, 361, 357
        .long   354, 351, 348, 344, 341, 338, 335, 332
        .long   329, 327, 324, 321, 319, 316, 313, 311
        .long   308, 306, 304, 301, 299, 297, 295, 293
        .long   291, 289, 287, 285, 283, 281, 279, 277
        .long   276, 274, 272, 271, 269, 268, 266, 265
        .long   263, 262, 261, 259, 258, 257, 256, 255
        .long   254, 252, 251, 250, 250, 249, 248, 247
        .long   246, 245, 245, 244, 243, 243, 242, 241
        .long   241, 240, 240, 240, 239, 239, 239, 238
        .long   238, 238, 238, 238, 237, 237, 237, 237
        .long   237, 237, 238, 238, 238, 238, 238, 239
        .long   239, 239, 240, 240, 241, 241, 242, 242
        .long   243, 244, 244, 245, 246, 247, 248, 249
        .long   250, 251, 252, 253, 254, 255, 256, 258
        .long   259, 260, 262, 263, 265, 266, 268, 269
        .long   271, 273, 275, 276, 278, 280, 282, 284
        .long   286, 288, 291, 293, 295, 297, 300, 302
        .long   305, 307, 310, 312, 315, 318, 320, 323
        .long   326, 329, 332, 335, 338, 341
O3_DRV_G:
        .long   4096, 4133, 4171, 4209, 4247, 4286, 4325, 4364
        .long   4404, 4444, 4485, 4526, 4567, 4608, 4650, 4693
        .long   4735, 4778, 4822, 4866, 4910, 4955, 5000, 5046
        .long   5092, 5138, 5185, 5232, 5280, 5328, 5376, 5425
        .long   5474, 5524, 5575, 5625, 5677, 5728, 5781, 5833
        .long   5886, 5940, 5994, 6049, 6104, 6159, 6215, 6272
        .long   6329, 6387, 6445, 6504, 6563, 6622, 6683, 6744
        .long   6805, 6867, 6930, 6993, 7056, 7121, 7185, 7251
        .long   7317, 7384, 7451, 7519, 7587, 7656, 7726, 7796
        .long   7867, 7939, 8011, 8084, 8158, 8232, 8307, 8383
        .long   8459, 8536, 8614, 8692, 8771, 8851, 8932, 9013
        .long   9095, 9178, 9262, 9346, 9431, 9517, 9604, 9691
        .long   9779, 9868, 9958, 10049, 10141, 10233, 10326, 10420
        .long   10515, 10611, 10707, 10805, 10903, 11003, 11103, 11204
        .long   11306, 11409, 11513, 11618, 11723, 11830, 11938, 12047
        .long   12156, 12267, 12379, 12491, 12605, 12720, 12836, 12953
O3_DRV_TH:
        .long   0, 256, 512, 767, 1023, 1277, 1532, 1785
        .long   2037, 2289, 2539, 2789, 3036, 3283, 3528, 3771
        .long   4013, 4252, 4490, 4726, 4960, 5191, 5420, 5647
        .long   5871, 6093, 6312, 6529, 6743, 6954, 7163, 7369
        .long   7571, 7771, 7968, 8162, 8353, 8541, 8726, 8908
        .long   9087, 9262, 9435, 9604, 9771, 9934, 10095, 10252
        .long   10406, 10557, 10706, 10851, 10993, 11132, 11269, 11402
        .long   11533, 11661, 11785, 11908, 12027, 12144, 12258, 12369
        .long   12478, 12584, 12688, 12789, 12888, 12984, 13078, 13170
        .long   13260, 13347, 13432, 13515, 13595, 13674, 13751, 13826
        .long   13898, 13969, 14038, 14105, 14171, 14234, 14296, 14356
        .long   14415, 14472, 14528, 14582, 14634, 14685, 14735, 14783
        .long   14830, 14876, 14920, 14963, 15005, 15046, 15085, 15124
        .long   15161, 15197, 15232, 15267, 15300, 15332, 15363, 15394
        .long   15423, 15452, 15480, 15507, 15533, 15559, 15584, 15608
        .long   15631, 15654, 15676, 15697, 15718, 15738, 15757, 15776
        .long   15795, 15812, 15830, 15847, 15863, 15879, 15894, 15909
        .long   15923, 15937, 15951, 15964, 15977, 15989, 16001, 16013
        .long   16024, 16035, 16046, 16056, 16066, 16076, 16085, 16094
        .long   16103, 16112, 16120, 16128, 16136, 16143, 16151, 16158
        .long   16165, 16171, 16178, 16184, 16190, 16196, 16202, 16208
        .long   16213, 16218, 16223, 16228, 16233, 16238, 16242, 16246
        .long   16251, 16255, 16259, 16263, 16266, 16270, 16273, 16277
        .long   16280, 16283, 16286, 16289, 16292, 16295, 16298, 16300
        .long   16303, 16305, 16308, 16310, 16312, 16315, 16317, 16319
        .long   16321, 16323, 16325, 16327, 16328, 16330, 16332, 16333
        .long   16335, 16336, 16338, 16339, 16341, 16342, 16343, 16344
        .long   16346, 16347, 16348, 16349, 16350, 16351, 16352, 16353
        .long   16354, 16355, 16356, 16357, 16358, 16358, 16359, 16360
        .long   16361, 16361, 16362, 16363, 16363, 16364, 16365, 16365
        .long   16366, 16366, 16367, 16368, 16368, 16369, 16369, 16369
        .long   16370, 16370, 16371, 16371, 16372, 16372, 16372, 16373
        .long   16373, 16373
O3_CL_G:
        .long   4096, 4036, 3977, 3917, 3857, 3797, 3738, 3678
        .long   3618, 3558, 3499, 3439, 3379, 3319, 3260, 3200
        .long   3140, 3081, 3021, 2961, 2901, 2842, 2782, 2722
        .long   2662, 2603, 2543, 2483, 2423, 2364, 2304, 2244
        .long   2185, 2125, 2065, 2005, 1946, 1886, 1826, 1766
        .long   1707, 1647, 1587, 1527, 1468, 1408, 1348, 1289
        .long   1229, 1229, 1229, 1229, 1229, 1229, 1229, 1229
        .long   1229, 1229, 1229, 1229, 1229, 1229, 1229
O3_CL_INV:
        .long   4096, 4157, 4219, 4283, 4350, 4419, 4488, 4562
        .long   4637, 4715, 4795, 4879, 4965, 5055, 5146, 5243
        .long   5343, 5445, 5554, 5666, 5783, 5903, 6031, 6164
        .long   6302, 6445, 6597, 6757, 6924, 7097, 7282, 7476
        .long   7678, 7895, 8125, 8368, 8621, 8896, 9188, 9500
        .long   9828, 10187, 10572, 10987, 11429, 11916, 12446, 13016
        .long   13651, 13651, 13651, 13651, 13651, 13651, 13651, 13651
        .long   13651, 13651, 13651, 13651, 13651, 13651, 13651
O3_CL_LIM:
        .long   1482910, 1504955, 1527281, 1550676, 1574798, 1599683, 1624932, 1651440
        .long   1678827, 1707138, 1735924, 1766210, 1797573, 1830069, 1863189, 1898124
        .long   1934394, 1971437, 2010592, 2051333, 2093760, 2137227, 2183321, 2231447
        .long   2281742, 2333461, 2388517, 2446234, 2506809, 2569373, 2636284, 2706773
        .long   2779862, 2858352, 2941404, 3029426, 3121274, 3220572, 3326396, 3439410
        .long   3558289, 3687917, 3827346, 3977733, 4137601, 4313920, 4505934, 4712179
        .long   4942228, 4942228, 4942228, 4942228, 4942228, 4942228, 4942228, 4942228
        .long   4942228, 4942228, 4942228, 4942228, 4942228, 4942228, 4942228
O3_VP_W2:
        .long   0, 20, 41, 62, 85, 108, 132, 158
        .long   184, 211, 239, 269, 299, 330, 363, 397
        .long   432, 468, 505, 544, 584, 625, 667, 711
        .long   756, 802, 850, 899, 949, 1001, 1054, 1108
        .long   1164, 1221, 1280, 1340, 1401, 1464, 1528, 1593
        .long   1660, 1728, 1798, 1869, 1941, 2014, 2089, 2165
        .long   2243, 2322, 2402, 2483, 2566, 2650, 2735, 2822
        .long   2909, 2998, 3088, 3180, 3272, 3366, 3460, 3556
        .long   3653, 3751, 3850, 3950, 4050, 4152, 4254, 4357
        .long   4461, 4565, 4670, 4776, 4882, 4988, 5094, 5201
        .long   5308, 5414, 5521, 5627, 5733, 5839, 5944, 6049
        .long   6153, 6256, 6358, 6459, 6559, 6658, 6756, 6852
        .long   6947, 7041, 7133, 7224, 7312, 7400, 7485, 7569
        .long   7650, 7730, 7808, 7884, 7959, 8031, 8101, 8169
        .long   8236, 8300, 8363, 8424, 8482, 8539, 8594, 8647
        .long   8699, 8748, 8796, 8843, 8887, 8930, 8971, 9011
O3_SQK:
        .long   -29658, -29658, -29658, -29658, -29658, -29658, -29658, -29658
        .long   -29658, -29658, -29658, -29658, -29658, -29658, -29658, -29658
        .long   -29658, -29658, -29658, -29658, -29658, -29658, -29658, -29658
        .long   -29658, -29658, -29658, -29658, -29658, -29499, -29314, -29104
        .long   -28871, -28616, -28334, -28029, -27700, -27346, -26970, -26580
        .long   -26178, -25777, -25379, -24988, -24611, -24247, -23896, -23565
        .long   -23250, -22953, -22674, -22413, -22167, -21942, -21733, -21540
        .long   -21363, -21203, -21056, -20928, -20810, -20710, -20623, -20551
        .long   -20489, -20443, -20412, -20392, -20388, -20397, -20418, -20454
        .long   -20502, -20568, -20645, -20743, -20851, -20978, -21124, -21283
        .long   -21461, -21650, -21846, -22047, -22240, -22426, -22588, -22728
        .long   -22836, -22920, -22974, -23003, -23014, -23005, -22984, -22950
        .long   -22905, -22858, -22802, -22744, -22682, -22682, -22682, -22682
        .long   -22682, -22682, -22682, -22682, -22682, -22682, -22682, -22682
        .long   -22682, -22682, -22682, -22682, -22682, -22682, -22682, -22682
        .long   -22682, -22682, -22682, -22682, -22682, -22682, -22682, -22682
O3_P6_F:
        .long   0, 7486, 14973, 22459, 29945, 37431, 44917, 52402
        .long   59887, 67370, 74852, 82332, 89808, 97281, 104749, 112210
        .long   119664, 127110, 134544, 141965, 149372, 156760, 164129, 171475
        .long   178794, 186084, 193341, 200561, 207740, 214874, 221958, 228988
        .long   235959, 242866, 249705, 256469, 263155, 269757, 276270, 282688
        .long   289008, 295224, 301332, 307327, 313205, 318962, 324596, 330101
        .long   335477, 340719, 345826, 350797, 355630, 360323, 364877, 369292
        .long   373567, 377703, 381702, 385564, 389291, 392886, 396349, 399685
        .long   402894, 405981, 408947, 411797, 414533, 417159, 419677, 422092
        .long   424407, 426624, 428749, 430783, 432730, 434594, 436378, 438085
        .long   439718, 441280, 442775, 444204, 445571, 446879, 448130, 449326
        .long   450470, 451565, 452612, 453614, 454572, 455489, 456367, 457208
        .long   458012, 458782, 459519, 460226, 460902, 461551, 462172, 462767
        .long   463338, 463885, 464410, 464913, 465396, 465860, 466304, 466732
        .long   467142, 467535, 467914, 468277, 468627, 468963, 469286, 469597
        .long   469895, 470183, 470460, 470726, 470982, 471230, 471467, 471697
        .long   471918, 472131, 472336, 472534, 472725, 472909, 473087, 473258
        .long   473424, 473584, 473738, 473888, 474032, 474171, 474306, 474436
        .long   474562, 474683, 474801, 474915, 475025, 475132, 475235, 475335
        .long   475432, 475526, 475617, 475705, 475790, 475873, 475953, 476031
        .long   476106, 476179, 476250, 476319, 476386, 476451, 476514, 476575
        .long   476634, 476692, 476748, 476803, 476856, 476907, 476957, 477005
        .long   477053, 477099, 477143, 477187, 477229, 477270, 477310, 477349
        .long   477387, 477424, 477460, 477495, 477529, 477562, 477595, 477626
        .long   477657, 477687, 477716, 477745, 477772, 477799, 477826, 477852
        .long   477877, 477901, 477925, 477948, 477971, 477993, 478015, 478036
        .long   478057, 478077, 478097, 478116, 478135, 478153, 478171, 478189
        .long   478206, 478222, 478239, 478255, 478270, 478286, 478301, 478315
        .long   478330, 478344, 478357, 478371, 478384, 478397, 478409, 478421
        .long   478433, 478445, 478457, 478468, 478479, 478490, 478500, 478511
        .long   478521, 478531, 478540, 478550, 478559, 478568, 478577, 478586
        .long   478595, 478603, 478611, 478620, 478628, 478635, 478643, 478650
        .long   478658, 478665
O3_P6_FP:
        .long   0, 10930, 21860, 32790, 43720, 54650, 65579, 76507
        .long   87435, 98361, 109284, 120204, 131120, 142030, 152933, 163827
        .long   174710, 185580, 196434, 207269, 218082, 228870, 239628, 250353
        .long   261040, 271683, 282278, 292819, 303300, 313715, 324058, 334322
        .long   344500, 354584, 364569, 374445, 384206, 393845, 403354, 412725
        .long   421952, 431027, 439944, 448697, 457279, 465685, 473910, 481948
        .long   489796, 497450, 504906, 512164, 519219, 526072, 532721, 539166
        .long   545407, 551447, 557285, 562923, 568365, 573613, 578670, 583539
        .long   588225, 592732, 597063, 601224, 605218, 609052, 612729, 616254
        .long   619634, 622872, 625973, 628943, 631786, 634508, 637112, 639604
        .long   641989, 644269, 646451, 648538, 650534, 652443, 654269, 656016
        .long   657687, 659285, 660813, 662276, 663675, 665015, 666296, 667523
        .long   668697, 669822, 670898, 671930, 672917, 673864, 674771, 675640
        .long   676473, 677272, 678038, 678773, 679478, 680155, 680804, 681428
        .long   682027, 682602, 683154, 683685, 684195, 684686, 685157, 685611
        .long   686047, 686467, 686871, 687260, 687634, 687995, 688342, 688677
        .long   689000, 689311, 689610, 689899, 690178, 690447, 690707, 690957
        .long   691199, 691432, 691658, 691876, 692086, 692290, 692486, 692676
        .long   692860, 693038, 693210, 693376, 693537, 693693, 693843, 693989
        .long   694131, 694268, 694400, 694529, 694654, 694774, 694891, 695005
        .long   695115, 695222, 695326, 695426, 695524, 695618, 695710, 695800
        .long   695886, 695971, 696052, 696132, 696209, 696284, 696357, 696428
        .long   696497, 696564, 696629, 696693, 696754, 696815, 696873, 696930
        .long   696985, 697039, 697092, 697143, 697193, 697241, 697288, 697334
        .long   697379, 697423, 697466, 697507, 697548, 697587, 697626, 697663
        .long   697700, 697736, 697771, 697805, 697838, 697870, 697902, 697933
        .long   697963, 697992, 698021, 698049, 698077, 698104, 698130, 698155
        .long   698180, 698205, 698229, 698252, 698275, 698297, 698319, 698340
        .long   698361, 698382, 698402, 698421, 698440, 698459, 698477, 698495
        .long   698513, 698530, 698547, 698563, 698579, 698595, 698610, 698625
        .long   698640, 698655, 698669, 698683, 698696, 698710, 698723, 698736
        .long   698748, 698761, 698773, 698785, 698796, 698808, 698819, 698830
        .long   698840, 698851
O3_MEG_T:
        .long   1068440655, 1068465975, 1068501541, 1068543352, 1068595212, 1068659427, 1068742542, 1068794064
        .long   1068854643, 1068927279, 1069016071, 1069125052, 1069265188, 1069350649, 1069450049, 1069568316
        .long   1069711243, 1069883847, 1070101602, 1070231822, 1070381885, 1070574853, 1070813859, 1071088848
        .long   1071417147, 1071602529, 1071806768, 1072024817, 1072258314, 1072502304, 1072749562, 1072869231
        .long   1072985367, 1073094728, 1073196032, 1073287405, 1073368343, 1073405089, 1073438728, 1073469954
        .long   1073487577, 1073487577, 1073487577, 1073487577, 1073487577, 1073487577, 1073487577, 1073487577
        .long   1073487577, 1073487577, 1073487577, 1073487577, 1073487577, 1073487577, 1073487577, 1073487577
        .long   1073487577, 1073487577, 1073487577, 1073487577, 1073487577, 536870912, 536870912, 536870912
        .long   1068443913, 1068469199, 1068504715, 1068546465, 1068598248, 1068662364, 1068745347, 1068796785
        .long   1068857265, 1068929779, 1069018421, 1069127217, 1069267113, 1069352430, 1069453831, 1069571991
        .long   1069712428, 1069887029, 1070102198, 1070232239, 1070382101, 1070577309, 1070813340, 1071092045
        .long   1071416968, 1071605626, 1071806615, 1072025546, 1072258304, 1072502608, 1072749126, 1072869296
        .long   1072985461, 1073095001, 1073196058, 1073287445, 1073368411, 1073397859, 1073397859, 1073397859
        .long   1073397859, 1073397859, 1073397859, 1073397859, 1073397859, 1073397859, 1073397859, 1073397859
        .long   1073397859, 1073397859, 1073397859, 1073397859, 1073397859, 1073397859, 1073397859, 1073397859
        .long   1073397859, 1073397859, 1073397859, 1073397859, 1073397859, 536870912, 536870912, 536870912
        .long   1068497271, 1068522495, 1068557621, 1068599435, 1068650149, 1068712836, 1068796022, 1068846952
        .long   1068906163, 1068978638, 1069063740, 1069173645, 1069310852, 1069396017, 1069494104, 1069610828
        .long   1069750454, 1069923615, 1070136605, 1070264617, 1070412905, 1070601407, 1070838344, 1071111583
        .long   1071435132, 1071620277, 1071820791, 1072036577, 1072267803, 1072509728, 1072753513, 1072872594
        .long   1072987820, 1073096733, 1073197241, 1073288283, 1073368825, 1073397213, 1073397213, 1073397213
        .long   1073397213, 1073397213, 1073397213, 1073397213, 1073397213, 1073397213, 1073397213, 1073397213
        .long   1073397213, 1073397213, 1073397213, 1073397213, 1073397213, 1073397213, 1073397213, 1073397213
        .long   1073397213, 1073397213, 1073397213, 1073397213, 1073397213, 536870912, 536870912, 536870912
        .long   1068581247, 1068606404, 1068640326, 1068680866, 1068730529, 1068792977, 1068873482, 1068924138
        .long   1068982435, 1069052379, 1069137545, 1069243740, 1069379811, 1069463478, 1069560775, 1069673504
        .long   1069811659, 1069977729, 1070189773, 1070314096, 1070459845, 1070644713, 1070876990, 1071145271
        .long   1071464685, 1071644298, 1071842138, 1072053533, 1072280983, 1072518573, 1072759721, 1072877583
        .long   1072991690, 1073099613, 1073199139, 1073289490, 1073369703, 1073396853, 1073396853, 1073396853
        .long   1073396853, 1073396853, 1073396853, 1073396853, 1073396853, 1073396853, 1073396853, 1073396853
        .long   1073396853, 1073396853, 1073396853, 1073396853, 1073396853, 1073396853, 1073396853, 1073396853
        .long   1073396853, 1073396853, 1073396853, 1073396853, 1073396853, 536870912, 536870912, 536870912
        .long   1068691394, 1068715836, 1068749352, 1068788017, 1068836651, 1068898752, 1068976539, 1069025355
        .long   1069083351, 1069150389, 1069233108, 1069337634, 1069469468, 1069550845, 1069644531, 1069757928
        .long   1069891119, 1070053837, 1070258066, 1070379661, 1070521220, 1070702860, 1070928174, 1071189933
        .long   1071501482, 1071677197, 1071868852, 1072077249, 1072299628, 1072532148, 1072768601, 1072884234
        .long   1072996771, 1073102982, 1073201637, 1073291267, 1073370756, 1073396333, 1073396333, 1073396333
        .long   1073396333, 1073396333, 1073396333, 1073396333, 1073396333, 1073396333, 1073396333, 1073396333
        .long   1073396333, 1073396333, 1073396333, 1073396333, 1073396333, 1073396333, 1073396333, 1073396333
        .long   1073396333, 1073396333, 1073396333, 1073396333, 1073396333, 536870912, 536870912, 536870912
        .long   1068823816, 1068847642, 1068879542, 1068917465, 1068964658, 1069023911, 1069099481, 1069146936
        .long   1069202700, 1069268364, 1069349507, 1069448861, 1069576206, 1069655751, 1069747350, 1069855425
        .long   1069985152, 1070142860, 1070340005, 1070458352, 1070595226, 1070774201, 1070990616, 1071244567
        .long   1071545066, 1071716752, 1071902478, 1072104540, 1072320470, 1072547741, 1072779606, 1072892766
        .long   1073003178, 1073107709, 1073204797, 1073293290, 1073371197, 1073383447, 1073383447, 1073383447
        .long   1073383447, 1073383447, 1073383447, 1073383447, 1073383447, 1073383447, 1073383447, 1073383447
        .long   1073383447, 1073383447, 1073383447, 1073383447, 1073383447, 1073383447, 1073383447, 1073383447
        .long   1073383447, 1073383447, 1073383447, 1073383447, 1073383447, 536870912, 536870912, 536870912
        .long   1068972450, 1068995107, 1069026180, 1069063124, 1069108756, 1069164894, 1069238337, 1069284457
        .long   1069337573, 1069401197, 1069478559, 1069574862, 1069698001, 1069773578, 1069862160, 1069966602
        .long   1070090945, 1070243977, 1070435612, 1070549526, 1070679828, 1070849951, 1071058231, 1071305797
        .long   1071596949, 1071760605, 1071940862, 1072135989, 1072346553, 1072566174, 1072791481, 1072902352
        .long   1073010654, 1073113073, 1073208533, 1073295729, 1073371507, 1073382133, 1073382133, 1073382133
        .long   1073382133, 1073382133, 1073382133, 1073382133, 1073382133, 1073382133, 1073382133, 1073382133
        .long   1073382133, 1073382133, 1073382133, 1073382133, 1073382133, 1073382133, 1073382133, 1073382133
        .long   1073382133, 1073382133, 1073382133, 1073382133, 1073382133, 536870912, 536870912, 536870912
        .long   1069133583, 1069155598, 1069185580, 1069221267, 1069264498, 1069318638, 1069389420, 1069432782
        .long   1069484872, 1069546277, 1069619537, 1069711996, 1069830218, 1069902731, 1069986892, 1070086659
        .long   1070206734, 1070353072, 1070536123, 1070644868, 1070769260, 1070935489, 1071136606, 1071372647
        .long   1071650918, 1071809798, 1071982946, 1072171297, 1072373561, 1072587469, 1072806123, 1072913353
        .long   1073018860, 1073119140, 1073212825, 1073298658, 1073371825, 1073380505, 1073380505, 1073380505
        .long   1073380505, 1073380505, 1073380505, 1073380505, 1073380505, 1073380505, 1073380505, 1073380505
        .long   1073380505, 1073380505, 1073380505, 1073380505, 1073380505, 1073380505, 1073380505, 1073380505
        .long   1073380505, 1073380505, 1073380505, 1073380505, 1073380505, 536870912, 536870912, 536870912
        .long   1069302995, 1069323602, 1069352252, 1069386340, 1069428402, 1069480186, 1069547822, 1069589239
        .long   1069638951, 1069697531, 1069768522, 1069856776, 1069969395, 1070038420, 1070119167, 1070214245
        .long   1070328106, 1070469406, 1070642977, 1070748264, 1070867193, 1071022906, 1071217614, 1071442237
        .long   1071710755, 1071862410, 1072028903, 1072208873, 1072403023, 1072609867, 1072820800, 1072924999
        .long   1073027871, 1073125715, 1073217443, 1073301777, 1073366361, 1073366361, 1073366361, 1073366361
        .long   1073366361, 1073366361, 1073366361, 1073366361, 1073366361, 1073366361, 1073366361, 1073366361
        .long   1073366361, 1073366361, 1073366361, 1073366361, 1073366361, 1073366361, 1073366361, 1073366361
        .long   1073366361, 1073366361, 1073366361, 1073366361, 1073366361, 536870912, 536870912, 536870912
        .long   1069568939, 1069588294, 1069614443, 1069646455, 1069685284, 1069733309, 1069796488, 1069835146
        .long   1069880068, 1069934650, 1070000858, 1070083114, 1070187953, 1070252126, 1070327107, 1070415294
        .long   1070520751, 1070651284, 1070811454, 1070908406, 1071019422, 1071164570, 1071344032, 1071554000
        .long   1071803949, 1071944682, 1072100209, 1072269488, 1072451590, 1072645751, 1072845535, 1072944844
        .long   1073042731, 1073136679, 1073225233, 1073307083, 1073363096, 1073363096, 1073363096, 1073363096
        .long   1073363096, 1073363096, 1073363096, 1073363096, 1073363096, 1073363096, 1073363096, 1073363096
        .long   1073363096, 1073363096, 1073363096, 1073363096, 1073363096, 1073363096, 1073363096, 1073363096
        .long   1073363096, 1073363096, 1073363096, 1073363096, 1073363096, 536870912, 536870912, 536870912
        .long   1069971984, 1069989226, 1070013015, 1070040738, 1070075332, 1070118109, 1070173767, 1070207800
        .long   1070247975, 1070295974, 1070354821, 1070427700, 1070520251, 1070576231, 1070642526, 1070720667
        .long   1070814595, 1070929207, 1071071013, 1071156513, 1071254195, 1071382353, 1071541925, 1071727097
        .long   1071948931, 1072075036, 1072213274, 1072364352, 1072528504, 1072703387, 1072885812, 1072976957
        .long   1073067459, 1073155374, 1073238422, 1073316014, 1073344105, 1073344105, 1073344105, 1073344105
        .long   1073344105, 1073344105, 1073344105, 1073344105, 1073344105, 1073344105, 1073344105, 1073344105
        .long   1073344105, 1073344105, 1073344105, 1073344105, 1073344105, 1073344105, 1073344105, 1073344105
        .long   1073344105, 1073344105, 1073344105, 1073344105, 1073344105, 536870912, 536870912, 536870912
        .long   1070440806, 1070455300, 1070475398, 1070499775, 1070528767, 1070565432, 1070613370, 1070642691
        .long   1070676770, 1070717328, 1070767620, 1070829151, 1070907996, 1070956207, 1071012343, 1071077836
        .long   1071157401, 1071254415, 1071375510, 1071447047, 1071529258, 1071639227, 1071774938, 1071934474
        .long   1072123512, 1072232147, 1072351208, 1072481513, 1072623644, 1072776389, 1072937007, 1073018838
        .long   1073100365, 1073179890, 1073256397, 1073327894, 1073337000, 1073337000, 1073337000, 1073337000
        .long   1073337000, 1073337000, 1073337000, 1073337000, 1073337000, 1073337000, 1073337000, 1073337000
        .long   1073337000, 1073337000, 1073337000, 1073337000, 1073337000, 1073337000, 1073337000, 1073337000
        .long   1073337000, 1073337000, 1073337000, 1073337000, 1073337000, 536870912, 536870912, 536870912
        .long   1070914455, 1070926630, 1070943265, 1070963095, 1070987634, 1071017988, 1071057506, 1071081653
        .long   1071110045, 1071144237, 1071184974, 1071236346, 1071301468, 1071341476, 1071387398, 1071442085
        .long   1071507507, 1071586960, 1071686799, 1071746039, 1071813848, 1071904188, 1072017371, 1072149411
        .long   1072307026, 1072397745, 1072497573, 1072606844, 1072727096, 1072857143, 1072995695, 1073066750
        .long   1073138225, 1073209063, 1073277813, 1073343597, 1073389601, 1073389601, 1073389601, 1073389601
        .long   1073389601, 1073389601, 1073389601, 1073389601, 1073389601, 1073389601, 1073389601, 1073389601
        .long   1073389601, 1073389601, 1073389601, 1073389601, 1073389601, 1073389601, 1073389601, 1073389601
        .long   1073389601, 1073389601, 1073389601, 1073389601, 1073389601, 536870912, 536870912, 536870912
        .long   1071350107, 1071360047, 1071373542, 1071390057, 1071409962, 1071434919, 1071466842, 1071486859
        .long   1071510015, 1071537728, 1071571197, 1071612761, 1071665972, 1071698409, 1071735957, 1071780315
        .long   1071833110, 1071897688, 1071977454, 1072025468, 1072080367, 1072153929, 1072246596, 1072354952
        .long   1072483767, 1072558397, 1072640244, 1072730678, 1072829972, 1072939155, 1073056489, 1073117283
        .long   1073178992, 1073240855, 1073301857, 1073360908, 1073416568, 1073425953, 1073425953, 1073425953
        .long   1073425953, 1073425953, 1073425953, 1073425953, 1073425953, 1073425953, 1073425953, 1073425953
        .long   1073425953, 1073425953, 1073425953, 1073425953, 1073425953, 1073425953, 1073425953, 1073425953
        .long   1073425953, 1073425953, 1073425953, 1073425953, 1073425953, 536870912, 536870912, 536870912
        .long   1071722040, 1071730074, 1071741249, 1071754650, 1071771019, 1071791212, 1071817351, 1071833480
        .long   1071852463, 1071874983, 1071902241, 1071935902, 1071978635, 1072004798, 1072035409, 1072071249
        .long   1072113961, 1072165684, 1072230460, 1072268891, 1072312706, 1072372545, 1072447883, 1072535796
        .long   1072641476, 1072702075, 1072769079, 1072843449, 1072925907, 1073016394, 1073114691, 1073166542
        .long   1073219584, 1073273092, 1073326624, 1073379107, 1073429731, 1073454122, 1073464905, 1073464905
        .long   1073464905, 1073464905, 1073464905, 1073464905, 1073464905, 1073464905, 1073464905, 1073464905
        .long   1073464905, 1073464905, 1073464905, 1073464905, 1073464905, 1073464905, 1073464905, 1073464905
        .long   1073464905, 1073464905, 1073464905, 1073464905, 1073464905, 536870912, 536870912, 536870912
        .long   1072024418, 1072031045, 1072040269, 1072051132, 1072064596, 1072081199, 1072102738, 1072115895
        .long   1072131483, 1072149938, 1072172078, 1072199675, 1072234747, 1072255961, 1072280674, 1072309807
        .long   1072344536, 1072386649, 1072438864, 1072470022, 1072505506, 1072554560, 1072616073, 1072688207
        .long   1072774849, 1072824659, 1072880064, 1072941416, 1073009664, 1073085248, 1073168160, 1073212112
        .long   1073257533, 1073303845, 1073350587, 1073397107, 1073442638, 1073464926, 1073486457, 1073496128
        .long   1073496128, 1073496128, 1073496128, 1073496128, 1073496128, 1073496128, 1073496128, 1073496128
        .long   1073496128, 1073496128, 1073496128, 1073496128, 1073496128, 1073496128, 1073496128, 1073496128
        .long   1073496128, 1073496128, 1073496128, 1073496128, 1073496128, 536870912, 536870912, 536870912
        .long   1072254464, 1072260056, 1072267761, 1072276995, 1072288237, 1072302271, 1072320239, 1072331257
        .long   1072344262, 1072359647, 1072378278, 1072401233, 1072430362, 1072448275, 1072468850, 1072492974
        .long   1072521809, 1072556785, 1072599838, 1072625666, 1072655042, 1072695624, 1072747273, 1072807902
        .long   1072880231, 1072921969, 1072968450, 1073020219, 1073077968, 1073141999, 1073212925, 1073250858
        .long   1073290207, 1073330728, 1073371968, 1073413441, 1073454565, 1073474893, 1073494707, 1073513514
        .long   1073516369, 1073516369, 1073516369, 1073516369, 1073516369, 1073516369, 1073516369, 1073516369
        .long   1073516369, 1073516369, 1073516369, 1073516369, 1073516369, 1073516369, 1073516369, 1073516369
        .long   1073516369, 1073516369, 1073516369, 1073516369, 1073516369, 536870912, 536870912, 536870912
        .long   1072443177, 1072447944, 1072454511, 1072462312, 1072471812, 1072483620, 1072498894, 1072508269
        .long   1072519185, 1072532197, 1072547879, 1072567222, 1072591768, 1072606704, 1072623974, 1072644213
        .long   1072668378, 1072697581, 1072733770, 1072755176, 1072779551, 1072813906, 1072857500, 1072908493
        .long   1072969675, 1073004955, 1073044335, 1073088099, 1073137227, 1073192014, 1073253040, 1073285730
        .long   1073320010, 1073355518, 1073391980, 1073429054, 1073466176, 1073484697, 1073502884, 1073520815
        .long   1073536572, 1073537572, 1073537572, 1073537572, 1073537572, 1073537572, 1073537572, 1073537572
        .long   1073537572, 1073537572, 1073537572, 1073537572, 1073537572, 1073537572, 1073537572, 1073537572
        .long   1073537572, 1073537572, 1073537572, 1073537572, 1073537572, 536870912, 536870912, 536870912
        .long   1072614620, 1072618598, 1072624113, 1072630681, 1072638688, 1072648635, 1072661393, 1072669242
        .long   1072678390, 1072689280, 1072702413, 1072718595, 1072738992, 1072751410, 1072765842, 1072782661
        .long   1072802718, 1072826882, 1072856671, 1072874390, 1072894537, 1072923082, 1072959519, 1073002371
        .long   1073053461, 1073083066, 1073116056, 1073152949, 1073194204, 1073240594, 1073292497, 1073320541
        .long   1073350063, 1073380798, 1073412720, 1073445413, 1073478549, 1073495250, 1073511778, 1073528177
        .long   1073544681, 1073552770, 1073552770, 1073552770, 1073552770, 1073552770, 1073552770, 1073552770
        .long   1073552770, 1073552770, 1073552770, 1073552770, 1073552770, 1073552770, 1073552770, 1073552770
        .long   1073552770, 1073552770, 1073552770, 1073552770, 1073552770, 536870912, 536870912, 536870912
        .long   1072764512, 1072767854, 1072772477, 1072777998, 1072784703, 1072793020, 1072803710, 1072810273
        .long   1072817899, 1072827019, 1072837934, 1072851381, 1072868391, 1072878736, 1072890672, 1072904592
        .long   1072921124, 1072941016, 1072965661, 1072980229, 1072996683, 1073020414, 1073050868, 1073086499
        .long   1073129080, 1073153790, 1073181413, 1073212268, 1073246879, 1073285962, 1073329899, 1073353777
        .long   1073379003, 1073405542, 1073433211, 1073461861, 1073491235, 1073506197, 1073521076, 1073535961
        .long   1073551072, 1073565932, 1073569677, 1073569677, 1073569677, 1073569677, 1073569677, 1073569677
        .long   1073569677, 1073569677, 1073569677, 1073569677, 1073569677, 1073569677, 1073569677, 1073569677
        .long   1073569677, 1073569677, 1073569677, 1073569677, 1073569677, 536870912, 536870912, 536870912
        .long   1072891338, 1072894170, 1072898068, 1072902711, 1072908338, 1072915348, 1072924306, 1072929824
        .long   1072936229, 1072943817, 1072952965, 1072964196, 1072978391, 1072986969, 1072996897, 1073008475
        .long   1073022192, 1073038692, 1073058971, 1073070965, 1073084478, 1073104253, 1073129711, 1073159509
        .long   1073195168, 1073215883, 1073238916, 1073264749, 1073293901, 1073326799, 1073364007, 1073384357
        .long   1073405976, 1073428763, 1073452742, 1073477775, 1073503715, 1073517029, 1073530381, 1073543839
        .long   1073557602, 1073571382, 1073584235, 1073584235, 1073584235, 1073584235, 1073584235, 1073584235
        .long   1073584235, 1073584235, 1073584235, 1073584235, 1073584235, 1073584235, 1073584235, 1073584235
        .long   1073584235, 1073584235, 1073584235, 1073584235, 1073584235, 536870912, 536870912, 536870912
        .long   1072995366, 1072997779, 1073001088, 1073005034, 1073009822, 1073015771, 1073023371, 1073028040
        .long   1073033459, 1073039882, 1073047592, 1073057078, 1073069001, 1073076231, 1073084567, 1073094254
        .long   1073105742, 1073119478, 1073136356, 1073146301, 1073157547, 1073174102, 1073195692, 1073220790
        .long   1073250886, 1073268349, 1073287862, 1073309711, 1073334357, 1073362300, 1073394037, 1073411455
        .long   1073430024, 1073449728, 1073470574, 1073492517, 1073515459, 1073527323, 1073539306, 1073551442
        .long   1073563983, 1073576626, 1073589287, 1073595217, 1073596135, 1073596135, 1073596135, 1073596135
        .long   1073596135, 1073596135, 1073596135, 1073596135, 1073596135, 1073596135, 1073596135, 1073596135
        .long   1073596135, 1073596135, 1073596135, 1073596135, 1073596135, 536870912, 536870912, 536870912
        .long   1073077821, 1073079901, 1073082764, 1073086177, 1073090317, 1073095441, 1073101987, 1073105982
        .long   1073110669, 1073116179, 1073122801, 1073130920, 1073141119, 1073147289, 1073154396, 1073162662
        .long   1073172429, 1073184093, 1073198381, 1073206792, 1073216242, 1073230402, 1073248884, 1073270434
        .long   1073296212, 1073311194, 1073327919, 1073346659, 1073367850, 1073391900, 1073419336, 1073434451
        .long   1073450594, 1073467815, 1073486121, 1073505518, 1073525946, 1073536599, 1073547409, 1073558437
        .long   1073569891, 1073581526, 1073593250, 1073599658, 1073605460, 1073607272, 1073607272, 1073607272
        .long   1073607272, 1073607272, 1073607272, 1073607272, 1073607272, 1073607272, 1073607272, 1073607272
        .long   1073607272, 1073607272, 1073607272, 1073607272, 1073607272, 536870912, 536870912, 536870912
        .long   1073140267, 1073142104, 1073144637, 1073147649, 1073151305, 1073155823, 1073161588, 1073165118
        .long   1073169218, 1073174076, 1073179882, 1073186999, 1073195933, 1073201332, 1073207531, 1073214734
        .long   1073223238, 1073233390, 1073245778, 1073253048, 1073261187, 1073273575, 1073289833, 1073308737
        .long   1073331334, 1073344446, 1073359117, 1073375544, 1073394153, 1073415304, 1073439499, 1073452885
        .long   1073467211, 1073482514, 1073498885, 1073516288, 1073534762, 1073544429, 1073554296, 1073564408
        .long   1073574982, 1073585788, 1073596738, 1073602771, 1073608584, 1073613245, 1073613245, 1073613245
        .long   1073613245, 1073613245, 1073613245, 1073613245, 1073613245, 1073613245, 1073613245, 1073613245
        .long   1073613245, 1073613245, 1073613245, 1073613245, 1073613245, 536870912, 536870912, 536870912
        .long   1073184521, 1073186195, 1073188491, 1073191225, 1073194545, 1073198645, 1073203871, 1073207057
        .long   1073210774, 1073215163, 1073220413, 1073226843, 1073234899, 1073239767, 1073245337, 1073251827
        .long   1073259442, 1073268531, 1073279616, 1073286083, 1073293362, 1073304508, 1073319171, 1073336251
        .long   1073356649, 1073368458, 1073381684, 1073396537, 1073413352, 1073432492, 1073454382, 1073466526
        .long   1073479570, 1073493539, 1073508492, 1073524471, 1073541509, 1073550462, 1073559638, 1073569075
        .long   1073578983, 1073589153, 1073599512, 1073605255, 1073610794, 1073616802, 1073618806, 1073618806
        .long   1073618806, 1073618806, 1073618806, 1073618806, 1073618806, 1073618806, 1073618806, 1073618806
        .long   1073618806, 1073618806, 1073618806, 1073618806, 1073618806, 536870912, 536870912, 536870912
        .long   1073221184, 1073222718, 1073224832, 1073227337, 1073230376, 1073234134, 1073238920, 1073241841
        .long   1073245240, 1073249250, 1073254044, 1073259916, 1073267253, 1073271685, 1073276761, 1073282641
        .long   1073289563, 1073297792, 1073307805, 1073313657, 1073320207, 1073330355, 1073343738, 1073359328
        .long   1073377903, 1073388700, 1073400750, 1073414297, 1073429624, 1073447094, 1073467149, 1073478281
        .long   1073490252, 1073503070, 1073516872, 1073531658, 1073547475, 1073555821, 1073564406, 1073573256
        .long   1073582587, 1073592204, 1073602041, 1073607525, 1073612821, 1073618643, 1073623417, 1073623417
        .long   1073623417, 1073623417, 1073623417, 1073623417, 1073623417, 1073623417, 1073623417, 1073623417
        .long   1073623417, 1073623417, 1073623417, 1073623417, 1073623417, 536870912, 536870912, 536870912
        .long   1073253992, 1073255407, 1073257348, 1073259659, 1073262455, 1073265907, 1073270308, 1073272991
        .long   1073276107, 1073279786, 1073284181, 1073289556, 1073296271, 1073300307, 1073304936, 1073310307
        .long   1073316603, 1073324097, 1073333173, 1073338471, 1073344391, 1073353651, 1073365936, 1073380192
        .long   1073397186, 1073407041, 1073418077, 1073430463, 1073444496, 1073460513, 1073478902, 1073489124
        .long   1073500133, 1073511956, 1073524717, 1073538416, 1073553128, 1073560922, 1073568955, 1073577259
        .long   1073586053, 1073595161, 1073604501, 1073609740, 1073614804, 1073620399, 1073626009, 1073627938
        .long   1073627938, 1073627938, 1073627938, 1073627938, 1073627938, 1073627938, 1073627938, 1073627938
        .long   1073627938, 1073627938, 1073627938, 1073627938, 1073627938, 536870912, 536870912, 536870912
        .long   1073282596, 1073283905, 1073285706, 1073287844, 1073290433, 1073293627, 1073297689, 1073300172
        .long   1073303049, 1073306435, 1073310488, 1073315442, 1073321611, 1073325326, 1073329576, 1073334498
        .long   1073340272, 1073347128, 1073355413, 1073360229, 1073365610, 1073374117, 1073385435, 1073398568
        .long   1073414208, 1073423285, 1073433419, 1073444821, 1073457722, 1073472480, 1073489434, 1073498877
        .long   1073509059, 1073520001, 1073531842, 1073544593, 1073558324, 1073565627, 1073573167, 1073580986
        .long   1073589299, 1073597933, 1073606820, 1073611839, 1073616688, 1073622066, 1073627414, 1073628847
        .long   1073628847, 1073628847, 1073628847, 1073628847, 1073628847, 1073628847, 1073628847, 1073628847
        .long   1073628847, 1073628847, 1073628847, 1073628847, 1073628847, 536870912, 536870912, 536870912
        .long   1073306766, 1073307989, 1073309668, 1073311664, 1073314076, 1073317054, 1073320840, 1073323148
        .long   1073325832, 1073328984, 1073332747, 1073337340, 1073343069, 1073346515, 1073350454, 1073355002
        .long   1073360333, 1073366651, 1073374279, 1073378708, 1073383654, 1073391541, 1073402039, 1073414230
        .long   1073428743, 1073437155, 1073446566, 1073457137, 1073469106, 1073482798, 1073498565, 1073507342
        .long   1073516827, 1073527038, 1073538085, 1073550031, 1073562928, 1073569801, 1073576917, 1073584318
        .long   1073592213, 1073600437, 1073608923, 1073613745, 1073618403, 1073623590, 1073626367, 1073626367
        .long   1073626367, 1073626367, 1073626367, 1073626367, 1073626367, 1073626367, 1073626367, 1073626367
        .long   1073626367, 1073626367, 1073626367, 1073626367, 1073626367, 536870912, 536870912, 536870912
        .long   1073326330, 1073327481, 1073329068, 1073330947, 1073333220, 1073336026, 1073339593, 1073341762
        .long   1073344280, 1073347250, 1073350782, 1073355093, 1073360463, 1073363691, 1073367376, 1073371634
        .long   1073376615, 1073382516, 1073389620, 1073393737, 1073398323, 1073405701, 1073415576, 1073427003
        .long   1073440619, 1073448506, 1073457326, 1073467237, 1073478468, 1073491300, 1073506098, 1073514351
        .long   1073523268, 1073532885, 1073543312, 1073554588, 1073566812, 1073573340, 1073580105, 1073587154
        .long   1073594698, 1073602579, 1073610735, 1073615387, 1073619885, 1073624657, 1073625697, 1073625697
        .long   1073625697, 1073625697, 1073625697, 1073625697, 1073625697, 1073625697, 1073625697, 1073625697
        .long   1073625697, 1073625697, 1073625697, 1073625697, 1073625697, 536870912, 536870912, 536870912
        .long   1073341124, 1073342225, 1073343739, 1073345535, 1073347706, 1073350379, 1073353778, 1073355847
        .long   1073358247, 1073361070, 1073364438, 1073368533, 1073373642, 1073376701, 1073380204, 1073384243
        .long   1073388959, 1073394545, 1073401264, 1073405147, 1073409475, 1073416471, 1073425873, 1073436734
        .long   1073449665, 1073457164, 1073465538, 1073474956, 1073485623, 1073497830, 1073511903, 1073519763
        .long   1073528252, 1073537423, 1073547367, 1073558149, 1073569845, 1073576102, 1073582605, 1073589388
        .long   1073596664, 1073604279, 1073612173, 1073616693, 1073621063, 1073622919, 1073622919, 1073622919
        .long   1073622919, 1073622919, 1073622919, 1073622919, 1073622919, 1073622919, 1073622919, 1073622919
        .long   1073622919, 1073622919, 1073622919, 1073622919, 1073622919, 536870912, 536870912, 536870912
        .long   1073350947, 1073352015, 1073353481, 1073355221, 1073357321, 1073359906, 1073363196, 1073365195
        .long   1073367519, 1073370248, 1073373500, 1073377465, 1073382396, 1073385350, 1073388722, 1073392623
        .long   1073397171, 1073402544, 1073408999, 1073412737, 1073416896, 1073423644, 1073432723, 1073443227
        .long   1073455711, 1073462948, 1073471037, 1073480124, 1073490421, 1073502217, 1073515807, 1073523401
        .long   1073531606, 1073540474, 1073550106, 1073560557, 1073571905, 1073577987, 1073584310, 1073590918
        .long   1073598010, 1073605444, 1073613163, 1073617596, 1073621730, 1073623260, 1073623260, 1073623260
        .long   1073623260, 1073623260, 1073623260, 1073623260, 1073623260, 1073623260, 1073623260, 1073623260
        .long   1073623260, 1073623260, 1073623260, 1073623260, 1073623260, 536870912, 536870912, 536870912
        .long   1073356176, 1073357225, 1073358666, 1073360375, 1073362437, 1073364984, 1073368210, 1073370177
        .long   1073372458, 1073375136, 1073378332, 1073382221, 1073387061, 1073389962, 1073393268, 1073397084
        .long   1073401536, 1073406805, 1073413134, 1073416785, 1073420842, 1073427484, 1073436398, 1073446689
        .long   1073458937, 1073466033, 1073473964, 1073482889, 1073493001, 1073504560, 1073517897, 1073525343
        .long   1073533407, 1073542123, 1073551592, 1073561859, 1073573025, 1073579011, 1073585239, 1073591742
        .long   1073598735, 1073606075, 1073613704, 1073618086, 1073621117, 1073620607, 1073620607, 1073620607
        .long   1073620607, 1073620607, 1073620607, 1073620607, 1073620607, 1073620607, 1073620607, 1073620607
        .long   1073620607, 1073620607, 1073620607, 1073620607, 1073620607, 536870912, 536870912, 536870912
O3_ADEC_T:
        .long   1032215993, 1032572143, 1032906255, 1033396143, 1033990477, 1034725154, 1035657123, 1036222975
        .long   1036876624, 1037640290, 1038687486, 1039936665, 1041471054, 1042535537, 1043738260, 1045102993
        .long   1046658366, 1048437017, 1050965320, 1052534795, 1054014558, 1056134805, 1058496457, 1061292091
        .long   1064221641, 1065741399, 1067290494, 1068765540, 1070080638, 1071200420, 1072044513, 1072374261
        .long   1072651628, 1072755582, 1072755582, 1072755582, 1072755582, 1072755582, 1072755582, 1072755582
        .long   1072755582, 1072755582, 1072755582, 1072755582, 1072755582, 1072755582, 1072755582, 1072755582
        .long   1072755582, 1072755582, 1072755582, 1072755582, 1072755582, 1072755582, 1072755582, 1072755582
        .long   1072755582, 1072755582, 1072755582, 1072755582, 1072755582, 536870912, 536870912, 536870912
        .long   1038298495, 1038581351, 1038897624, 1039307106, 1039752225, 1040313982, 1041174944, 1041611005
        .long   1042153505, 1042878084, 1043741032, 1044786995, 1046073071, 1046833454, 1047748493, 1048919176
        .long   1050231215, 1051831084, 1053894776, 1055110427, 1056529146, 1058213462, 1060214043, 1062521067
        .long   1065060168, 1066395118, 1067744488, 1069079445, 1070251059, 1071280950, 1072080675, 1072397527
        .long   1072665083, 1072866853, 1072866853, 1072866853, 1072866853, 1072866853, 1072866853, 1072866853
        .long   1072866853, 1072866853, 1072866853, 1072866853, 1072866853, 1072866853, 1072866853, 1072866853
        .long   1072866853, 1072866853, 1072866853, 1072866853, 1072866853, 1072866853, 1072866853, 1072866853
        .long   1072866853, 1072866853, 1072866853, 1072866853, 1072866853, 536870912, 536870912, 536870912
        .long   1043486848, 1043685945, 1043960635, 1044287360, 1044682988, 1045171012, 1045823995, 1046288109
        .long   1046728606, 1047242998, 1047993120, 1048766653, 1049907136, 1050584903, 1051351091, 1052314833
        .long   1053362038, 1054742839, 1056498925, 1057526914, 1058626738, 1060125382, 1061795208, 1063738854
        .long   1065925652, 1067069374, 1068236462, 1069361199, 1070437619, 1071372160, 1072120452, 1072423699
        .long   1072680691, 1072892999, 1072963308, 1072963308, 1072963308, 1072963308, 1072963308, 1072963308
        .long   1072963308, 1072963308, 1072963308, 1072963308, 1072963308, 1072963308, 1072963308, 1072963308
        .long   1072963308, 1072963308, 1072963308, 1072963308, 1072963308, 1072963308, 1072963308, 1072963308
        .long   1072963308, 1072963308, 1072963308, 1072963308, 1072963308, 536870912, 536870912, 536870912
        .long   1047950638, 1048119241, 1048323702, 1048606750, 1048932946, 1049367616, 1049880824, 1050216561
        .long   1050605837, 1051062461, 1051656563, 1052371255, 1053252507, 1053832682, 1054489885, 1055238680
        .long   1056199750, 1057289227, 1058697816, 1059551412, 1060576365, 1061806595, 1063177563, 1064822531
        .long   1066671235, 1067643763, 1068638684, 1069655506, 1070604483, 1071459707, 1072165702, 1072450833
        .long   1072698100, 1072904233, 1073046223, 1073046223, 1073046223, 1073046223, 1073046223, 1073046223
        .long   1073046223, 1073046223, 1073046223, 1073046223, 1073046223, 1073046223, 1073046223, 1073046223
        .long   1073046223, 1073046223, 1073046223, 1073046223, 1073046223, 1073046223, 1073046223, 1073046223
        .long   1073046223, 1073046223, 1073046223, 1073046223, 1073046223, 536870912, 536870912, 536870912
        .long   1051724257, 1051854303, 1052053848, 1052274539, 1052556119, 1052880025, 1053343703, 1053630410
        .long   1053963548, 1054355047, 1054820433, 1055384064, 1056127266, 1056609903, 1057157304, 1057781969
        .long   1058573097, 1059523553, 1060712509, 1061419844, 1062245829, 1063242570, 1064408111, 1065796472
        .long   1067327704, 1068192546, 1069074984, 1069939087, 1070786679, 1071560852, 1072211311, 1072481875
        .long   1072717276, 1072915841, 1073078155, 1073118321, 1073118321, 1073118321, 1073118321, 1073118321
        .long   1073118321, 1073118321, 1073118321, 1073118321, 1073118321, 1073118321, 1073118321, 1073118321
        .long   1073118321, 1073118321, 1073118321, 1073118321, 1073118321, 1073118321, 1073118321, 1073118321
        .long   1073118321, 1073118321, 1073118321, 1073118321, 1073118321, 536870912, 536870912, 536870912
        .long   1054950920, 1055064090, 1055215401, 1055415916, 1055634008, 1055925198, 1056289858, 1056526678
        .long   1056781049, 1057100515, 1057508640, 1057987278, 1058612862, 1058979341, 1059439731, 1060000730
        .long   1060640550, 1061440320, 1062423680, 1062999989, 1063694417, 1064527390, 1065529886, 1066653788
        .long   1067982321, 1068712831, 1069463059, 1070223931, 1070965344, 1071664044, 1072262411, 1072515384
        .long   1072739374, 1072929050, 1073088511, 1073180517, 1073180517, 1073180517, 1073180517, 1073180517
        .long   1073180517, 1073180517, 1073180517, 1073180517, 1073180517, 1073180517, 1073180517, 1073180517
        .long   1073180517, 1073180517, 1073180517, 1073180517, 1073180517, 1073180517, 1073180517, 1073180517
        .long   1073180517, 1073180517, 1073180517, 1073180517, 1073180517, 536870912, 536870912, 536870912
        .long   1057701541, 1057802327, 1057928090, 1058086029, 1058270207, 1058509449, 1058824892, 1059017351
        .long   1059240824, 1059503339, 1059815382, 1060233898, 1060749462, 1061081350, 1061445706, 1061888271
        .long   1062413617, 1063073012, 1063902849, 1064384405, 1064931711, 1065638477, 1066489673, 1067468340
        .long   1068584046, 1069193249, 1069831226, 1070491584, 1071145454, 1071767426, 1072317288, 1072552743
        .long   1072762891, 1072944627, 1073097876, 1073221742, 1073235314, 1073235314, 1073235314, 1073235314
        .long   1073235314, 1073235314, 1073235314, 1073235314, 1073235314, 1073235314, 1073235314, 1073235314
        .long   1073235314, 1073235314, 1073235314, 1073235314, 1073235314, 1073235314, 1073235314, 1073235314
        .long   1073235314, 1073235314, 1073235314, 1073235314, 1073235314, 536870912, 536870912, 536870912
        .long   1060056797, 1060134946, 1060242976, 1060367045, 1060526636, 1060724129, 1060975480, 1061130266
        .long   1061328043, 1061538820, 1061813261, 1062150588, 1062586234, 1062849203, 1063156878, 1063520558
        .long   1063971144, 1064512922, 1065193327, 1065598210, 1066056450, 1066645069, 1067351168, 1068168150
        .long   1069115193, 1069637929, 1070184655, 1070752344, 1071320534, 1071877179, 1072373282, 1072591977
        .long   1072788513, 1072961216, 1073108035, 1073231938, 1073283114, 1073283114, 1073283114, 1073283114
        .long   1073283114, 1073283114, 1073283114, 1073283114, 1073283114, 1073283114, 1073283114, 1073283114
        .long   1073283114, 1073283114, 1073283114, 1073283114, 1073283114, 1073283114, 1073283114, 1073283114
        .long   1073283114, 1073283114, 1073283114, 1073283114, 1073283114, 536870912, 536870912, 536870912
        .long   1062059628, 1062125237, 1062212421, 1062322869, 1062453310, 1062613984, 1062824764, 1062957605
        .long   1063112032, 1063293667, 1063518812, 1063806761, 1064164242, 1064377582, 1064637250, 1064943144
        .long   1065318843, 1065757145, 1066331287, 1066664260, 1067040132, 1067535255, 1068126386, 1068809701
        .long   1069599430, 1070040924, 1070504229, 1070996979, 1071494913, 1071981722, 1072431400, 1072633506
        .long   1072817146, 1072979585, 1073119288, 1073238943, 1073324955, 1073324955, 1073324955, 1073324955
        .long   1073324955, 1073324955, 1073324955, 1073324955, 1073324955, 1073324955, 1073324955, 1073324955
        .long   1073324955, 1073324955, 1073324955, 1073324955, 1073324955, 1073324955, 1073324955, 1073324955
        .long   1073324955, 1073324955, 1073324955, 1073324955, 1073324955, 536870912, 536870912, 536870912
        .long   1063760276, 1063813993, 1063888101, 1063976517, 1064084971, 1064224999, 1064397053, 1064508647
        .long   1064638456, 1064791410, 1064979904, 1065205029, 1065502834, 1065692838, 1065900924, 1066161199
        .long   1066468295, 1066835689, 1067298967, 1067583726, 1067903669, 1068303586, 1068792698, 1069374441
        .long   1070036215, 1070415308, 1070812412, 1071229942, 1071660590, 1072089679, 1072494030, 1072677529
        .long   1072846647, 1072999284, 1073132392, 1073246764, 1073343478, 1073375243, 1073375243, 1073375243
        .long   1073375243, 1073375243, 1073375243, 1073375243, 1073375243, 1073375243, 1073375243, 1073375243
        .long   1073375243, 1073375243, 1073375243, 1073375243, 1073375243, 1073375243, 1073375243, 1073375243
        .long   1073375243, 1073375243, 1073375243, 1073375243, 1073375243, 536870912, 536870912, 536870912
        .long   1065225951, 1065271530, 1065332999, 1065406169, 1065494733, 1065610092, 1065752703, 1065844026
        .long   1065950074, 1066078556, 1066233292, 1066421777, 1066673323, 1066821649, 1067001871, 1067206718
        .long   1067463042, 1067769897, 1068153067, 1068387660, 1068653172, 1068992586, 1069404404, 1069881924
        .long   1070437542, 1070753146, 1071088845, 1071448642, 1071820730, 1072196160, 1072556885, 1072723616
        .long   1072879260, 1073020921, 1073146274, 1073255497, 1073348703, 1073389759, 1073406194, 1073406194
        .long   1073406194, 1073406194, 1073406194, 1073406194, 1073406194, 1073406194, 1073406194, 1073406194
        .long   1073406194, 1073406194, 1073406194, 1073406194, 1073406194, 1073406194, 1073406194, 1073406194
        .long   1073406194, 1073406194, 1073406194, 1073406194, 1073406194, 536870912, 536870912, 536870912
        .long   1066473008, 1066510769, 1066560566, 1066622140, 1066696341, 1066790725, 1066911073, 1066984950
        .long   1067075243, 1067181776, 1067308905, 1067468651, 1067671841, 1067796453, 1067942248, 1068115893
        .long   1068322552, 1068577909, 1068902091, 1069088448, 1069309362, 1069591001, 1069932411, 1070334536
        .long   1070800936, 1071065895, 1071350781, 1071653860, 1071973966, 1072301216, 1072619981, 1072770872
        .long   1072913308, 1073044176, 1073161649, 1073265024, 1073354448, 1073394389, 1073429379, 1073433692
        .long   1073433692, 1073433692, 1073433692, 1073433692, 1073433692, 1073433692, 1073433692, 1073433692
        .long   1073433692, 1073433692, 1073433692, 1073433692, 1073433692, 1073433692, 1073433692, 1073433692
        .long   1073433692, 1073433692, 1073433692, 1073433692, 1073433692, 536870912, 536870912, 536870912
        .long   1067535084, 1067566291, 1067608602, 1067659336, 1067721799, 1067799242, 1067900358, 1067962428
        .long   1068033645, 1068121370, 1068228644, 1068360430, 1068530171, 1068632294, 1068755863, 1068898951
        .long   1069070143, 1069279689, 1069542926, 1069701872, 1069881009, 1070114208, 1070400704, 1070735084
        .long   1071125624, 1071350129, 1071589062, 1071845994, 1072119526, 1072403925, 1072684596, 1072819410
        .long   1072948685, 1073068676, 1073178067, 1073275807, 1073361047, 1073399440, 1073434438, 1073463047
        .long   1073466374, 1073466374, 1073466374, 1073466374, 1073466374, 1073466374, 1073466374, 1073466374
        .long   1073466374, 1073466374, 1073466374, 1073466374, 1073466374, 1073466374, 1073466374, 1073466374
        .long   1073466374, 1073466374, 1073466374, 1073466374, 1073466374, 536870912, 536870912, 536870912
        .long   1068440655, 1068465975, 1068501541, 1068543352, 1068595212, 1068659427, 1068742542, 1068794064
        .long   1068854643, 1068927279, 1069016071, 1069125052, 1069265188, 1069350649, 1069450049, 1069568316
        .long   1069711243, 1069883847, 1070101602, 1070231822, 1070381885, 1070574853, 1070813859, 1071088848
        .long   1071417147, 1071602529, 1071806768, 1072024817, 1072258314, 1072502304, 1072749562, 1072869231
        .long   1072985367, 1073094728, 1073196032, 1073287405, 1073368343, 1073405089, 1073438728, 1073469954
        .long   1073487577, 1073487577, 1073487577, 1073487577, 1073487577, 1073487577, 1073487577, 1073487577
        .long   1073487577, 1073487577, 1073487577, 1073487577, 1073487577, 1073487577, 1073487577, 1073487577
        .long   1073487577, 1073487577, 1073487577, 1073487577, 1073487577, 536870912, 536870912, 536870912
        .long   1069164602, 1069186289, 1069215812, 1069250936, 1069294555, 1069348439, 1069418757, 1069461756
        .long   1069512187, 1069572605, 1069647099, 1069738302, 1069854976, 1069927672, 1070011333, 1070110520
        .long   1070228853, 1070374808, 1070555228, 1070664237, 1070786839, 1070950709, 1071151231, 1071385147
        .long   1071661309, 1071820818, 1071991916, 1072178015, 1072379191, 1072591755, 1072808462, 1072915562
        .long   1073020521, 1073120199, 1073213774, 1073299194, 1073375860, 1073410917, 1073443237, 1073473383
        .long   1073501685, 1073510687, 1073510687, 1073510687, 1073510687, 1073510687, 1073510687, 1073510687
        .long   1073510687, 1073510687, 1073510687, 1073510687, 1073510687, 1073510687, 1073510687, 1073510687
        .long   1073510687, 1073510687, 1073510687, 1073510687, 1073510687, 536870912, 536870912, 536870912
        .long   1069786308, 1069804490, 1069829257, 1069858816, 1069895512, 1069940793, 1070000085, 1070036782
        .long   1070079457, 1070129692, 1070191333, 1070268034, 1070366959, 1070427464, 1070497552, 1070580339
        .long   1070679580, 1070800056, 1070951017, 1071041999, 1071145653, 1071282924, 1071449226, 1071648031
        .long   1071881383, 1072014618, 1072160918, 1072320469, 1072492680, 1072676612, 1072866654, 1072961956
        .long   1073055842, 1073146499, 1073232184, 1073311767, 1073383917, 1073417268, 1073448198, 1073477189
        .long   1073504558, 1073526988, 1073526988, 1073526988, 1073526988, 1073526988, 1073526988, 1073526988
        .long   1073526988, 1073526988, 1073526988, 1073526988, 1073526988, 1073526988, 1073526988, 1073526988
        .long   1073526988, 1073526988, 1073526988, 1073526988, 1073526988, 536870912, 536870912, 536870912
        .long   1070325275, 1070340392, 1070361360, 1070386300, 1070417095, 1070455602, 1070504693, 1070535247
        .long   1070571022, 1070613747, 1070665885, 1070729904, 1070811362, 1070862088, 1070920379, 1070989899
        .long   1071072360, 1071172909, 1071299969, 1071375246, 1071461079, 1071575001, 1071716885, 1071882396
        .long   1072079906, 1072192895, 1072316759, 1072452301, 1072598967, 1072757479, 1072923878, 1073007926
        .long   1073091815, 1073173342, 1073251590, 1073325133, 1073392704, 1073424295, 1073453727, 1073481421
        .long   1073507778, 1073532333, 1073545373, 1073545373, 1073545373, 1073545373, 1073545373, 1073545373
        .long   1073545373, 1073545373, 1073545373, 1073545373, 1073545373, 1073545373, 1073545373, 1073545373
        .long   1073545373, 1073545373, 1073545373, 1073545373, 1073545373, 536870912, 536870912, 536870912
        .long   1070789296, 1070802173, 1070819606, 1070840661, 1070866102, 1070898507, 1070940098, 1070965461
        .long   1070995298, 1071031258, 1071074541, 1071128197, 1071196823, 1071239033, 1071287771, 1071345667
        .long   1071414472, 1071498602, 1071603271, 1071665940, 1071737960, 1071833748, 1071952841, 1072091796
        .long   1072257999, 1072353066, 1072457548, 1072572569, 1072698821, 1072835139, 1072979356, 1073053390
        .long   1073127656, 1073200722, 1073271701, 1073339311, 1073402185, 1073431823, 1073459666, 1073486090
        .long   1073511338, 1073535003, 1073557061, 1073562412, 1073562412, 1073562412, 1073562412, 1073562412
        .long   1073562412, 1073562412, 1073562412, 1073562412, 1073562412, 1073562412, 1073562412, 1073562412
        .long   1073562412, 1073562412, 1073562412, 1073562412, 1073562412, 536870912, 536870912, 536870912
        .long   1071190315, 1071201034, 1071215823, 1071233394, 1071254992, 1071281864, 1071316736, 1071338203
        .long   1071363127, 1071393055, 1071429419, 1071474390, 1071532152, 1071567314, 1071607644, 1071655533
        .long   1071713187, 1071782947, 1071870247, 1071922322, 1071981950, 1072061669, 1072161469, 1072278537
        .long   1072418442, 1072498310, 1072586442, 1072684157, 1072791280, 1072907947, 1073033157, 1073097665
        .long   1073163175, 1073228608, 1073292486, 1073354087, 1073412276, 1073439979, 1073466198, 1073491205
        .long   1073515262, 1073537975, 1073559332, 1073570089, 1073575016, 1073575016, 1073575016, 1073575016
        .long   1073575016, 1073575016, 1073575016, 1073575016, 1073575016, 1073575016, 1073575016, 1073575016
        .long   1073575016, 1073575016, 1073575016, 1073575016, 1073575016, 536870912, 536870912, 536870912
        .long   1071535823, 1071544849, 1071557257, 1071572006, 1071590084, 1071612724, 1071641899, 1071659701
        .long   1071680948, 1071706143, 1071736220, 1071773873, 1071822015, 1071851273, 1071885285, 1071925157
        .long   1071972928, 1072030876, 1072103085, 1072146345, 1072195862, 1072262555, 1072346047, 1072444546
        .long   1072561397, 1072628988, 1072703738, 1072785976, 1072877029, 1072976658, 1073084697, 1073141057
        .long   1073198473, 1073256268, 1073313618, 1073369530, 1073422948, 1073448679, 1073473185, 1073496744
        .long   1073519573, 1073541265, 1073561781, 1073572177, 1073581991, 1073589263, 1073589263, 1073589263
        .long   1073589263, 1073589263, 1073589263, 1073589263, 1073589263, 1073589263, 1073589263, 1073589263
        .long   1073589263, 1073589263, 1073589263, 1073589263, 1073589263, 536870912, 536870912, 536870912
        .long   1071836025, 1071843529, 1071853983, 1071866345, 1071881604, 1071900564, 1071924918, 1071939879
        .long   1071957507, 1071978377, 1072003825, 1072035236, 1072075072, 1072099445, 1072127564, 1072160722
        .long   1072200463, 1072248767, 1072308672, 1072344262, 1072385161, 1072440555, 1072510661, 1072592751
        .long   1072690919, 1072747368, 1072810226, 1072879835, 1072956642, 1073041743, 1073134226, 1073183149
        .long   1073233333, 1073284145, 1073335203, 1073385517, 1073434262, 1073457960, 1073480759, 1073502801
        .long   1073524314, 1073544908, 1073564525, 1073574529, 1073583985, 1073593778, 1073599238, 1073599238
        .long   1073599238, 1073599238, 1073599238, 1073599238, 1073599238, 1073599238, 1073599238, 1073599238
        .long   1073599238, 1073599238, 1073599238, 1073599238, 1073599238, 536870912, 536870912, 536870912
        .long   1072094509, 1072100843, 1072109633, 1072119987, 1072132779, 1072148659, 1072169024, 1072181522
        .long   1072196200, 1072213774, 1072234921, 1072260927, 1072294278, 1072314472, 1072337908, 1072365508
        .long   1072398366, 1072438339, 1072487844, 1072517284, 1072550983, 1072597229, 1072655779, 1072724351
        .long   1072806614, 1072853884, 1072906455, 1072964989, 1073029987, 1073102209, 1073181398, 1073223483
        .long   1073267066, 1073311717, 1073356830, 1073401844, 1073446043, 1073467742, 1073488785, 1073509295
        .long   1073529444, 1073548892, 1073567543, 1073577121, 1073586206, 1073595648, 1073604805, 1073610011
        .long   1073610011, 1073610011, 1073610011, 1073610011, 1073610011, 1073610011, 1073610011, 1073610011
        .long   1073610011, 1073610011, 1073610011, 1073610011, 1073610011, 536870912, 536870912, 536870912
        .long   1072318287, 1072323623, 1072330972, 1072339700, 1072350281, 1072363589, 1072380609, 1072391145
        .long   1072403358, 1072417952, 1072435546, 1072457360, 1072484972, 1072501746, 1072521218, 1072544078
        .long   1072571295, 1072604141, 1072644956, 1072669248, 1072696865, 1072735429, 1072784344, 1072841613
        .long   1072910103, 1072949800, 1072993738, 1073042783, 1073097562, 1073158547, 1073226125, 1073262271
        .long   1073299950, 1073338827, 1073378440, 1073418475, 1073458299, 1073478023, 1073497304, 1073516232
        .long   1073534995, 1073553246, 1073570866, 1073579993, 1073588673, 1073597729, 1073606550, 1073615703
        .long   1073619909, 1073619909, 1073619909, 1073619909, 1073619909, 1073619909, 1073619909, 1073619909
        .long   1073619909, 1073619909, 1073619909, 1073619909, 1073619909, 536870912, 536870912, 536870912
        .long   1072511459, 1072515903, 1072521996, 1072529336, 1072538249, 1072549284, 1072563533, 1072572286
        .long   1072582562, 1072594693, 1072609352, 1072627369, 1072650303, 1072664236, 1072680418, 1072699264
        .long   1072721723, 1072748898, 1072782487, 1072802488, 1072825124, 1072856997, 1072897918, 1072945606
        .long   1073002618, 1073035733, 1073072564, 1073113591, 1073159591, 1073210909, 1073268299, 1073299224
        .long   1073331626, 1073365277, 1073399937, 1073435301, 1073470874, 1073488679, 1073506223, 1073523576
        .long   1073540935, 1073557937, 1073574493, 1073583139, 1073591377, 1073600040, 1073608496, 1073617308
        .long   1073626596, 1073630580, 1073630580, 1073630580, 1073630580, 1073630580, 1073630580, 1073630580
        .long   1073630580, 1073630580, 1073630580, 1073630580, 1073630580, 536870912, 536870912, 536870912
        .long   1072678059, 1072681783, 1072686921, 1072693018, 1072700492, 1072709737, 1072721635, 1072728911
        .long   1072737453, 1072747530, 1072759707, 1072774715, 1072793687, 1072805270, 1072818597, 1072834184
        .long   1072852746, 1072875013, 1072902636, 1072919033, 1072937571, 1072964032, 1072997964, 1073037690
        .long   1073085146, 1073112673, 1073143464, 1073177735, 1073216137, 1073259394, 1073307941, 1073334273
        .long   1073361999, 1073390983, 1073421104, 1073452109, 1073483686, 1073499646, 1073515501, 1073531292
        .long   1073547230, 1073562975, 1073578424, 1073586569, 1073594352, 1073602578, 1073610640, 1073619094
        .long   1073628052, 1073632766, 1073637596, 1073637831, 1073637831, 1073637831, 1073637831, 1073637831
        .long   1073637831, 1073637831, 1073637831, 1073637831, 1073637831, 536870912, 536870912, 536870912
        .long   1072822251, 1072825363, 1072829665, 1072834776, 1072840981, 1072848711, 1072858581, 1072864664
        .long   1072871731, 1072880141, 1072890260, 1072902685, 1072918374, 1072927904, 1072938953, 1072951794
        .long   1072967053, 1072985391, 1073007986, 1073021382, 1073036490, 1073058324, 1073086553, 1073119560
        .long   1073158959, 1073181821, 1073207362, 1073235922, 1073268022, 1073304199, 1073345088, 1073367373
        .long   1073390993, 1073415812, 1073441819, 1073468871, 1073496695, 1073510919, 1073525116, 1073539372
        .long   1073553896, 1073568366, 1073582674, 1073590295, 1073597595, 1073605366, 1073613010, 1073621074
        .long   1073629669, 1073634216, 1073638938, 1073643826, 1073645250, 1073645250, 1073645250, 1073645250
        .long   1073645250, 1073645250, 1073645250, 1073645250, 1073645250, 536870912, 536870912, 536870912
        .long   1072946932, 1072949527, 1072953112, 1072957370, 1072962564, 1072968990, 1072977235, 1072982275
        .long   1072988166, 1072995120, 1073003489, 1073013795, 1073026757, 1073034594, 1073043685, 1073054260
        .long   1073066728, 1073081765, 1073100206, 1073111090, 1073123379, 1073141455, 1073164777, 1073192086
        .long   1073224765, 1073243701, 1073264862, 1073288576, 1073315314, 1073345515, 1073379797, 1073398591
        .long   1073418589, 1073439715, 1073462047, 1073485446, 1073509797, 1073522339, 1073534982, 1073547755
        .long   1073560878, 1073574070, 1073587226, 1073594315, 1073601109, 1073608402, 1073615609, 1073623257
        .long   1073631463, 1073635826, 1073640372, 1073645089, 1073649969, 1073654830, 1073654830, 1073654830
        .long   1073654830, 1073654830, 1073654830, 1073654830, 1073654830, 536870912, 536870912, 536870912
        .long   1073054492, 1073056664, 1073059653, 1073063214, 1073067531, 1073072890, 1073079734, 1073083919
        .long   1073088801, 1073094570, 1073101495, 1073110005, 1073120699, 1073127166, 1073134598, 1073143257
        .long   1073153503, 1073165779, 1073180781, 1073189620, 1073199560, 1073214394, 1073233739, 1073256316
        .long   1073283305, 1073298988, 1073316471, 1073336082, 1073358234, 1073383364, 1073412025, 1073427799
        .long   1073444631, 1073462565, 1073481597, 1073501710, 1073522859, 1073533858, 1073545007, 1073556362
        .long   1073568130, 1073580060, 1073592065, 1073598599, 1073604891, 1073611686, 1073618434, 1073625645
        .long   1073633437, 1073637604, 1073641954, 1073646491, 1073651191, 1073656585, 1073660436, 1073660436
        .long   1073660436, 1073660436, 1073660436, 1073660436, 1073660436, 536870912, 536870912, 536870912
        .long   1073147462, 1073149276, 1073151771, 1073154736, 1073158333, 1073162778, 1073168462, 1073171931
        .long   1073175977, 1073180749, 1073186462, 1073193482, 1073202276, 1073207587, 1073213677, 1073220767
        .long   1073229115, 1073239109, 1073251262, 1073258395, 1073266417, 1073278597, 1073294554, 1073313198
        .long   1073335434, 1073348321, 1073362742, 1073378912, 1073397221, 1073418056, 1073441876, 1073455054
        .long   1073469171, 1073484281, 1073500407, 1073517591, 1073535826, 1073545385, 1073555143, 1073565148
        .long   1073575613, 1073586314, 1073597172, 1073603156, 1073608926, 1073615216, 1073621488, 1073628242
        .long   1073635603, 1073639558, 1073643705, 1073648041, 1073652552, 1073657755, 1073663159, 1073666320
        .long   1073668836, 1073668836, 1073668836, 1073668836, 1073668836, 536870912, 536870912, 536870912
        .long   1073227866, 1073229375, 1073231455, 1073233919, 1073236909, 1073240600, 1073245311, 1073248183
        .long   1073251524, 1073255465, 1073260175, 1073265953, 1073273157, 1073277508, 1073282490, 1073288259
        .long   1073295048, 1073303140, 1073312963, 1073318699, 1073325125, 1073335083, 1073348262, 1073363539
        .long   1073381822, 1073392414, 1073404245, 1073417570, 1073432613, 1073449807, 1073469519, 1073480451
        .long   1073492227, 1073504848, 1073518443, 1073533007, 1073548602, 1073556841, 1073565310, 1073574046
        .long   1073583267, 1073592789, 1073602523, 1073607962, 1073613211, 1073618987, 1073624773, 1073631059
        .long   1073637961, 1073641692, 1073645624, 1073649750, 1073654055, 1073659054, 1073664257, 1073667320
        .long   1073670565, 1073673615, 1073674381, 1073674381, 1073674381, 536870912, 536870912, 536870912
        .long   1073297440, 1073298695, 1073300423, 1073302473, 1073304953, 1073308013, 1073311910, 1073314284
        .long   1073317039, 1073320281, 1073324152, 1073328892, 1073334787, 1073338333, 1073342394, 1073347085
        .long   1073352583, 1073359112, 1073366990, 1073371571, 1073376685, 1073384795, 1073395612, 1073408155
        .long   1073423109, 1073431780, 1073441470, 1073452362, 1073464697, 1073478788, 1073495008, 1073504052
        .long   1073513801, 1073524298, 1073535651, 1073547898, 1073561131, 1073568166, 1073575445, 1073583008
        .long   1073591072, 1073599453, 1073608098, 1073612992, 1073617724, 1073622991, 1073628285, 1073634085
        .long   1073640518, 1073644020, 1073647720, 1073651623, 1073655710, 1073660489, 1073665481, 1073668433
        .long   1073671568, 1073674517, 1073678165, 1073682335, 1073682420, 536870912, 536870912, 536870912
        .long   1073357471, 1073358517, 1073359951, 1073361653, 1073363708, 1073366241, 1073369456, 1073371413
        .long   1073373680, 1073376353, 1073379528, 1073383402, 1073388217, 1073391101, 1073394395, 1073398188
        .long   1073402626, 1073407863, 1073414159, 1073417791, 1073421830, 1073428439, 1073437296, 1073447543
        .long   1073459740, 1073466799, 1073474697, 1073483568, 1073493637, 1073505147, 1073518418, 1073525838
        .long   1073533861, 1073542529, 1073551950, 1073562181, 1073573301, 1073579266, 1073585468, 1073591947
        .long   1073598923, 1073606236, 1073613837, 1073618208, 1073622439, 1073627193, 1073631997, 1073637311
        .long   1073643263, 1073646522, 1073649990, 1073653658, 1073657516, 1073662061, 1073666825, 1073669660
        .long   1073672680, 1073675518, 1073679048, 1073683181, 1073687174, 536870912, 536870912, 536870912
        .long   1073409398, 1073410264, 1073411452, 1073412864, 1073414562, 1073416654, 1073419306, 1073420915
        .long   1073422778, 1073424965, 1073427564, 1073430723, 1073434638, 1073436977, 1073439638, 1073442700
        .long   1073446257, 1073450440, 1073455426, 1073458289, 1073461451, 1073466789, 1073474032, 1073482382
        .long   1073492285, 1073498012, 1073504416, 1073511612, 1073519764, 1073529107, 1073539904, 1073545950
        .long   1073552509, 1073559612, 1073567365, 1073575820, 1073585088, 1073590090, 1073595319, 1073600818
        .long   1073606792, 1073613106, 1073619721, 1073623589, 1073627328, 1073631584, 1073635903, 1073640729
        .long   1073646192, 1073649208, 1073652430, 1073655859, 1073659478, 1073663778, 1073668301, 1073671011
        .long   1073673906, 1073676625, 1073680029, 1073684032, 1073687899, 536870912, 536870912, 536870912
        .long   1073454308, 1073455028, 1073456012, 1073457177, 1073458580, 1073460304, 1073462485, 1073463806
        .long   1073465332, 1073467119, 1073469241, 1073471809, 1073474978, 1073476864, 1073479007, 1073481458
        .long   1073484297, 1073487613, 1073491535, 1073493766, 1073496213, 1073500511, 1073506400, 1073513173
        .long   1073521179, 1073525802, 1073530961, 1073536758, 1073543328, 1073550862, 1073559577, 1073564466
        .long   1073569780, 1073575548, 1073581870, 1073588797, 1073596437, 1073600586, 1073604952, 1073609562
        .long   1073614624, 1073620014, 1073625705, 1073629091, 1073632361, 1073636135, 1073639980, 1073644326
        .long   1073649299, 1073652069, 1073655044, 1073658224, 1073661595, 1073665641, 1073669909, 1073672488
        .long   1073675249, 1073677844, 1073681110, 1073684973, 1073688709, 536870912, 536870912, 536870912
O3_AC_A1:
        .long   199, 22194, 45089, 68912, 93690, 119450, 146222, 174033
        .long   202910, 232880, 263971, 296209, 329620, 364229, 400061, 437140
        .long   475489, 515130, 556084, 598372, 642011, 687020, 733415, 781211
        .long   830421, 881057, 933132, 986653, 1041629, 1098066, 1155970, 1215345
        .long   1276193, 1338517, 1402316, 1467590, 1534337, 1602556, 1672242, 1743393
        .long   1816004, 1890070, 1965586, 2042546, 2120946, 2200778, 2282038, 2364718
        .long   2448813, 2534316, 2621219, 2709517, 2799201, 2890262, 2982693, 3076483
        .long   3171622, 3268096, 3365893, 3464996, 3565387, 3667048, 3769954, 3874080
        .long   3979397, 4085873, 4193472, 4302154, 4411874, 4522585, 4634233, 4746760
        .long   4860106, 4974202, 5088979, 5204359, 5320263, 5436606, 5553300, 5670251
        .long   5787365, 5904542, 6021680, 6138676, 6255424, 6371817, 6487747, 6603106
        .long   6717785, 6831678, 6944679, 7056684, 7167591, 7277302, 7385722, 7492758
        .long   7598323, 7702335, 7804714, 7905389, 8004292, 8101361, 8196539, 8289775
        .long   8381026, 8470251, 8557419, 8642502, 8725478, 8806332, 8885052, 8961633
        .long   9036075, 9108381, 9178560, 9246626, 9312595, 9376487, 9438327, 9498141
        .long   9555960, 9611816, 9665743, 9717778, 9767961, 9816331, 9862930, 9907800
O3_AC_A2:
        .long   22845, 2542324, 5152965, 7856384, 10654063, 13547337, 16537374, 19625155
        .long   22811457, 26096832, 29481586, 32965760, 36549106, 40231068, 44010764, 47886959
        .long   51858050, 55922045, 60076546, 64318732, 68645341, 73052659, 77536508, 82092237
        .long   86714712, 91398318, 96136950, 100924023, 105752472, 110614762, 115502905, 120408469
        .long   125322602, 130236058, 135139218, 140022129, 144874531, 149685899, 154445481, 159142345
        .long   163765419, 168303546, 172745525, 177080171, 181296359, 185383080, 189329494, 193124978
        .long   196759183, 200222079, 203504007, 206595727, 209488458, 212173926, 214644403, 216892741
        .long   218912413, 220697535, 222242904, 223544016, 224597088, 225399078, 225947699, 226241427
        .long   226279509, 226061969, 225589604, 224863982, 223887433, 222663042, 221194628, 219486730
        .long   217544585, 215374101, 212981831, 210374939, 207561166, 204548794, 201346604, 197963832
        .long   194410127, 190695500, 186830279, 182825057, 178690639, 174437994, 170078200, 165622392
        .long   161081713, 156467261, 151790043, 147060923, 142290582, 137489472, 132667778, 127835377
        .long   123001810, 118176247, 113367463, 108583812, 103833211, 99123120, 94460534, 89851973
        .long   85303474, 80820595, 76408410, 72071518, 67814049, 63639671, 59551607, 55552642
        .long   51645143, 47831076, 44112022, 40489196, 36963469, 33535388, 30205194, 26972846
        .long   23838039, 20800228, 17858645, 15012319, 12260098, 9600664, 7032555, 4554176
O3_AC_RE:
        .long   1, 111, 226, 344, 466, 593, 724, 859
        .long   999, 1142, 1290, 1443, 1600, 1761, 1926, 2096
        .long   2270, 2448, 2630, 2815, 3005, 3198, 3394, 3593
        .long   3796, 4001, 4208, 4418, 4629, 4842, 5056, 5271
        .long   5486, 5701, 5915, 6129, 6341, 6552, 6760, 6966
        .long   7168, 7367, 7561, 7751, 7936, 8115, 8287, 8453
        .long   8613, 8764, 8908, 9043, 9170, 9287, 9395, 9494
        .long   9582, 9660, 9728, 9785, 9831, 9866, 9890, 9903
        .long   9905, 9895, 9875, 9843, 9800, 9746, 9682, 9607
        .long   9522, 9427, 9323, 9209, 9085, 8954, 8813, 8665
        .long   8510, 8347, 8178, 8003, 7822, 7636, 7445, 7250
        .long   7051, 6849, 6644, 6437, 6228, 6018, 5807, 5596
        .long   5384, 5173, 4962, 4753, 4545, 4339, 4135, 3933
        .long   3734, 3538, 3345, 3155, 2968, 2786, 2607, 2432
        .long   2261, 2094, 1931, 1772, 1618, 1468, 1322, 1181
        .long   1043, 910, 782, 657, 537, 420, 308, 199
O3_AC_RA:
        .long   80335, 80396, 80461, 80528, 80598, 80671, 80747, 80827
        .long   80910, 80996, 81086, 81180, 81278, 81380, 81486, 81596
        .long   81710, 81829, 81952, 82080, 82213, 82351, 82493, 82641
        .long   82793, 82951, 83114, 83282, 83456, 83635, 83819, 84009
        .long   84204, 84404, 84609, 84820, 85036, 85256, 85482, 85712
        .long   85947, 86185, 86428, 86675, 86926, 87179, 87436, 87695
        .long   87957, 88221, 88486, 88752, 89019, 89287, 89554, 89820
        .long   90086, 90350, 90613, 90873, 91130, 91384, 91634, 91880
        .long   92122, 92359, 92591, 92817, 93038, 93252, 93461, 93663
        .long   93858, 94046, 94228, 94402, 94570, 94730, 94883, 95029
        .long   95168, 95300, 95426, 95545, 95657, 95762, 95862, 95955
        .long   96043, 96125, 96201, 96273, 96339, 96401, 96458, 96511
        .long   96559, 96604, 96645, 96683, 96718, 96750, 96779, 96805
        .long   96829, 96850, 96870, 96887, 96903, 96917, 96929, 96941
        .long   96950, 96959, 96967, 96973, 96979, 96984, 96988, 96991
        .long   96994, 96996, 96998, 97000, 97001, 97001, 97002, 97002
O3_AC_RP:
        .long   33334, 33284, 33233, 33179, 33122, 33063, 33001, 32936
        .long   32868, 32797, 32722, 32645, 32563, 32478, 32389, 32296
        .long   32199, 32098, 31992, 31882, 31766, 31646, 31521, 31390
        .long   31254, 31112, 30964, 30810, 30650, 30483, 30310, 30130
        .long   29943, 29749, 29548, 29339, 29123, 28899, 28667, 28427
        .long   28178, 27922, 27657, 27384, 27102, 26812, 26513, 26206
        .long   25890, 25566, 25233, 24892, 24543, 24186, 23820, 23447
        .long   23066, 22679, 22284, 21882, 21474, 21060, 20640, 20215
        .long   19785, 19351, 18913, 18471, 18027, 17580, 17131, 16680
        .long   16229, 15778, 15327, 14876, 14427, 13980, 13536, 13094
        .long   12656, 12221, 11791, 11366, 10946, 10532, 10123, 9721
        .long   9326, 8938, 8557, 8184, 7818, 7460, 7111, 6769
        .long   6436, 6111, 5795, 5488, 5189, 4898, 4616, 4343
        .long   4077, 3821, 3572, 3332, 3099, 2875, 2658, 2449
        .long   2248, 2053, 1866, 1686, 1512, 1346, 1185, 1031
        .long   883, 741, 604, 473, 348, 227, 112, 1
O3_AC_B1:
        .long   715823111, 716352234, 716906476, 717486951, 718094809, 718731248, 719397505, 720094860
        .long   720824639, 721588208, 722386981, 723222414, 724096006, 725009302, 725963888, 726961393
        .long   728003486, 729091877, 730228313, 731414580, 732652495, 733943906, 735290692, 736694753
        .long   738158012, 739682408, 741269890, 742922413, 744641932, 746430393, 748289732, 750221857
        .long   752228650, 754311951, 756473552, 758715184, 761038508, 763445105, 765936460, 768513954
        .long   771178848, 773932272, 776775210, 779708488, 782732760, 785848494, 789055957, 792355206
        .long   795746070, 799228144, 802800770, 806463034, 810213752, 814051462, 817974419, 821980589
        .long   826067645, 830232964, 834473631, 838786438, 843167888, 847614205, 852121341, 856684988
        .long   861300587, 865963353, 870668284, 875410186, 880183690, 884983282, 889803322, 894638073
        .long   899481727, 904328432, 909172324, 914007549, 918828297, 923628828, 928403497, 933146784
        .long   937853315, 942517887, 947135492, 951701333, 956210844, 960659706, 965043859, 969359516
        .long   973603169, 977771599, 981861878, 985871372, 989797741, 993638941, 997393213, 1001059085
        .long   1004635362, 1008121118, 1011515687, 1014818652, 1018029833, 1021149279, 1024177248, 1027114201
        .long   1029960784, 1032717816, 1035386275, 1037967285, 1040462104, 1042872106, 1045198774, 1047443683
        .long   1049608492, 1051694931, 1053704788, 1055639901, 1057502151, 1059293447, 1061015720, 1062670919
        .long   1064260998, 1065787911, 1067253610, 1068660031, 1070009100, 1071302718, 1072542763, 1073731087
O3_AC_K2:
        .long   1296977, 1297934, 1298937, 1299988, 1301088, 1302240, 1303445, 1304707
        .long   1306028, 1307410, 1308855, 1310367, 1311948, 1313601, 1315328, 1317133
        .long   1319019, 1320988, 1323045, 1325192, 1327432, 1329769, 1332206, 1334746
        .long   1337394, 1340153, 1343025, 1346016, 1349127, 1352363, 1355728, 1359224
        .long   1362855, 1366625, 1370536, 1374592, 1378796, 1383150, 1387658, 1392322
        .long   1397144, 1402125, 1407269, 1412576, 1418048, 1423685, 1429488, 1435457
        .long   1441592, 1447892, 1454355, 1460981, 1467766, 1474709, 1481806, 1489053
        .long   1496447, 1503982, 1511653, 1519455, 1527380, 1535423, 1543576, 1551831
        .long   1560180, 1568614, 1577124, 1585700, 1594334, 1603015, 1611733, 1620477
        .long   1629237, 1638002, 1646763, 1655507, 1664225, 1672907, 1681541, 1690119
        .long   1698630, 1707065, 1715415, 1723671, 1731825, 1739870, 1747797, 1755600
        .long   1763273, 1770810, 1778206, 1785455, 1792554, 1799499, 1806286, 1812914
        .long   1819380, 1825682, 1831819, 1837790, 1843595, 1849235, 1854709, 1860018
        .long   1865164, 1870148, 1874972, 1879638, 1884148, 1888504, 1892710, 1896768
        .long   1900681, 1904453, 1908086, 1911584, 1914950, 1918188, 1921301, 1924293
        .long   1927167, 1929927, 1932576, 1935118, 1937557, 1939895, 1942137, 1944284
O3_AC_F:
        .long   0, 246, 746, 1742, 3670, 7211, 13210, 22396
        .long   35049, 50960, 69640, 90552, 113223, 137282, 162441, 188483
        .long   215245, 242600, 270451, 298720, 327347, 356282, 385484, 414921
        .long   444566, 474394, 504387, 534527, 564801, 595196, 625702, 656308
        .long   687006, 717789, 748652, 779586, 810589, 841654, 872778, 903957
        .long   935187, 966465, 997789, 1029155, 1060562, 1092007, 1123488, 1155004
        .long   1186552, 1218130, 1249738, 1281374, 1313037, 1344725, 1376438, 1408174
        .long   1439932, 1471711, 1503511, 1535331, 1567169, 1599026, 1630900, 1662791
        .long   1694699, 1726622, 1758560, 1790512, 1822479, 1854459, 1886453, 1918459
        .long   1950477, 1982508, 2014550, 2046603, 2078667, 2110741, 2142826, 2174921
        .long   2207026, 2239139, 2271262, 2303394, 2335535, 2367684, 2399841, 2432006
        .long   2464179, 2496359, 2528547, 2560742, 2592944, 2625153, 2657369, 2689591
        .long   2721819, 2754054, 2786295, 2818542, 2850795, 2883053, 2915317, 2947587
        .long   2979862, 3012142, 3044427, 3076717, 3109012, 3141312, 3173617, 3205926
        .long   3238240, 3270558, 3302881, 3335208, 3367539, 3399874, 3432213, 3464557
        .long   3496904, 3529255, 3561609, 3593968, 3626330, 3658696, 3691065, 3723437
        .long   3755813, 3788192, 3820575, 3852961, 3885350, 3917742, 3950137, 3982535
        .long   4014936, 4047340, 4079747, 4112156, 4144569, 4176984, 4209402, 4241822
        .long   4274245, 4306671, 4339099, 4371530, 4403963, 4436399, 4468837, 4501278
        .long   4533720, 4566165, 4598613, 4631062, 4663514, 4695968, 4728424, 4760882
        .long   4793343, 4825805, 4858269, 4890736, 4923204, 4955674, 4988147, 5020621
        .long   5053097, 5085575, 5118054, 5150536, 5183019, 5215504, 5247991, 5280479
        .long   5312970, 5345461, 5377955, 5410450, 5442947, 5475445, 5507945, 5540447
        .long   5572950, 5605455, 5637961, 5670468, 5702977, 5735488, 5768000, 5800514
        .long   5833028, 5865545, 5898062, 5930581, 5963102, 5995623, 6028146, 6060671
        .long   6093196, 6125723, 6158251, 6190781, 6223311, 6255843, 6288376, 6320911
        .long   6353446, 6385983, 6418521, 6451060, 6483600, 6516141, 6548683, 6581227
        .long   6613771, 6646317, 6678864, 6711412, 6743961, 6776511, 6809062, 6841614
        .long   6874167, 6906721, 6939276, 6971832, 7004389, 7036947, 7069506, 7102066
        .long   7134626, 7167188, 7199751, 7232315, 7264879, 7297444, 7330011, 7362578
        .long   7395146, 7427715, 7460285, 7492856, 7525427, 7558000, 7590573, 7623147
        .long   7655722, 7688298, 7720874, 7753451, 7786030, 7818608, 7851188, 7883769
        .long   7916350, 7948932, 7981515, 8014098, 8046682, 8079267, 8111853, 8144439
        .long   8177027, 8209614, 8242203, 8274792, 8307382, 8339973, 8372564, 8405156
        .long   8437749, 8470342, 8502937, 8535531, 8568127, 8600723, 8633319, 8665917
        .long   8698515, 8731113, 8763712, 8796312, 8828913, 8861514, 8894116, 8926718
        .long   8959321, 8991924, 9024528, 9057133, 9089738, 9122344, 9154951, 9187558
        .long   9220165, 9252773, 9285382, 9317991, 9350601, 9383211, 9415822, 9448434
        .long   9481045, 9513658, 9546271, 9578885, 9611499, 9644113, 9676728, 9709344
        .long   9741960, 9774577, 9807194, 9839811, 9872429, 9905048, 9937667, 9970287
        .long   10002907, 10035527, 10068148, 10100770, 10133392, 10166014, 10198637, 10231261
        .long   10263884, 10296509, 10329133, 10361759, 10394384, 10427010, 10459637, 10492264
        .long   10524891, 10557519, 10590147, 10622776, 10655405, 10688035, 10720665, 10753295
        .long   10785926, 10818557, 10851188, 10883820, 10916453, 10949086, 10981719, 11014353
        .long   11046987, 11079621, 11112256, 11144891, 11177527, 11210163, 11242799, 11275436
        .long   11308073, 11340710, 11373348, 11405986, 11438625, 11471264, 11503903, 11536543
        .long   11569183, 11601823, 11634464, 11667105, 11699747, 11732388, 11765031, 11797673
        .long   11830316, 11862959, 11895603, 11928247, 11960891, 11993535, 12026180, 12058826
        .long   12091471, 12124117, 12156763, 12189410, 12222057, 12254704, 12287351, 12319999
        .long   12352647, 12385296, 12417945, 12450594, 12483243, 12515893, 12548543, 12581193
O3_AC_F27:
        .long   0, 72, 219, 520, 1128, 2332, 4635, 8781
        .long   15619, 25775, 39384, 56130, 75491, 96941, 120037, 144431
        .long   169858, 196118, 223058, 250562, 278537, 306913, 335631, 364644
        .long   393916, 423414, 453112, 482989, 513025, 543204, 573514, 603941
        .long   634475, 665108, 695831, 726637, 757520, 788475, 819495, 850577
        .long   881717, 912911, 944155, 975446, 1006782, 1038160, 1069578, 1101034
        .long   1132525, 1164049, 1195606, 1227193, 1258809, 1290453, 1322123, 1353818
        .long   1385537, 1417279, 1449043, 1480829, 1512634, 1544459, 1576303, 1608165
        .long   1640044, 1671940, 1703851, 1735779, 1767721, 1799678, 1831648, 1863632
        .long   1895629, 1927639, 1959661, 1991694, 2023740, 2055796, 2087863, 2119940
        .long   2152028, 2184125, 2216233, 2248349, 2280474, 2312609, 2344752, 2376903
        .long   2409062, 2441230, 2473405, 2505587, 2537777, 2569974, 2602178, 2634389
        .long   2666606, 2698830, 2731061, 2763297, 2795540, 2827789, 2860043, 2892303
        .long   2924568, 2956840, 2989116, 3021397, 3053684, 3085976, 3118272, 3150573
        .long   3182879, 3215190, 3247505, 3279825, 3312148, 3344476, 3376809, 3409145
        .long   3441486, 3473830, 3506178, 3538530, 3570886, 3603245, 3635608, 3667975
        .long   3700345, 3732719, 3765095, 3797476, 3829859, 3862246, 3894636, 3927028
        .long   3959424, 3991823, 4024225, 4056630, 4089038, 4121448, 4153861, 4186277
        .long   4218696, 4251117, 4283541, 4315967, 4348396, 4380828, 4413262, 4445698
        .long   4478137, 4510578, 4543021, 4575467, 4607915, 4640365, 4672818, 4705272
        .long   4737729, 4770188, 4802649, 4835111, 4867576, 4900043, 4932512, 4964983
        .long   4997456, 5029930, 5062407, 5094885, 5127366, 5159848, 5192331, 5224817
        .long   5257304, 5289793, 5322284, 5354776, 5387270, 5419766, 5452263, 5484762
        .long   5517262, 5549764, 5582268, 5614773, 5647279, 5679788, 5712297, 5744808
        .long   5777320, 5809834, 5842350, 5874866, 5907384, 5939904, 5972424, 6004946
        .long   6037470, 6069994, 6102520, 6135048, 6167576, 6200106, 6232637, 6265169
        .long   6297703, 6330237, 6362773, 6395310, 6427848, 6460387, 6492928, 6525470
        .long   6558012, 6590556, 6623101, 6655647, 6688194, 6720742, 6753291, 6785842
        .long   6818393, 6850945, 6883498, 6916053, 6948608, 6981164, 7013722, 7046280
        .long   7078839, 7111399, 7143960, 7176522, 7209085, 7241649, 7274214, 7306780
        .long   7339346, 7371914, 7404482, 7437051, 7469622, 7502193, 7534764, 7567337
        .long   7599910, 7632485, 7665060, 7697636, 7730213, 7762790, 7795368, 7827948
        .long   7860527, 7893108, 7925690, 7958272, 7990855, 8023438, 8056023, 8088608
        .long   8121194, 8153781, 8186368, 8218956, 8251545, 8284134, 8316724, 8349315
        .long   8381907, 8414499, 8447092, 8479686, 8512280, 8544875, 8577470, 8610067
        .long   8642663, 8675261, 8707859, 8740458, 8773057, 8805657, 8838258, 8870859
        .long   8903461, 8936064, 8968667, 9001270, 9033874, 9066479, 9099085, 9131691
        .long   9164297, 9196904, 9229512, 9262120, 9294729, 9327339, 9359949, 9392559
        .long   9425170, 9457782, 9490394, 9523006, 9555620, 9588233, 9620848, 9653462
        .long   9686077, 9718693, 9751310, 9783926, 9816544, 9849161, 9881780, 9914398
        .long   9947018, 9979637, 10012257, 10044878, 10077499, 10110121, 10142743, 10175366
        .long   10207989, 10240612, 10273236, 10305861, 10338485, 10371111, 10403736, 10436363
        .long   10468989, 10501616, 10534244, 10566872, 10599500, 10632129, 10664758, 10697388
        .long   10730018, 10762648, 10795279, 10827911, 10860542, 10893174, 10925807, 10958440
        .long   10991073, 11023707, 11056341, 11088976, 11121611, 11154246, 11186882, 11219518
        .long   11252154, 11284791, 11317428, 11350066, 11382704, 11415342, 11447981, 11480620
        .long   11513259, 11545899, 11578539, 11611180, 11643820, 11676462, 11709103, 11741745
        .long   11774387, 11807030, 11839673, 11872316, 11904960, 11937604, 11970248, 12002893
        .long   12035538, 12068183, 12100829, 12133475, 12166121, 12198768, 12231415, 12264062
        .long   12296710, 12329358, 12362006, 12394654, 12427303, 12459952, 12492602, 12525252
O3_AC_L69:
        .long   0, 1279, 2497, 3661, 4775, 5842, 6867, 7853
        .long   8803, 9719, 10604, 11460, 12288, 13090, 13869, 14624
        .long   15358, 16072, 16767, 17443, 18102, 18745, 19372, 19984
        .long   20583, 21167, 21739, 22298, 22846, 23382, 23907, 24422
        .long   24927, 25422, 25907, 26384, 26852, 27312, 27764, 28208
        .long   28645, 29074, 29496, 29912, 30320, 30723, 31119, 31510
        .long   31894, 32273, 32647, 33015, 33378, 33736, 34089, 34437
        .long   34781, 35120, 35455, 35785, 36112, 36434, 36752, 37067
        .long   37377, 37684, 37987, 38287, 38584, 38877, 39166, 39453
        .long   39736, 40017, 40294, 40568, 40840, 41109, 41374, 41638
        .long   41898, 42156, 42411, 42664, 42915, 43163, 43409, 43652
        .long   43893, 44132, 44369, 44603, 44836, 45066, 45294, 45521
        .long   45745, 45967, 46188, 46407, 46623, 46838, 47052, 47263
        .long   47473, 47681, 47887, 48092, 48295, 48497, 48697, 48896
        .long   49093, 49288, 49482, 49675, 49866, 50056, 50244, 50431
        .long   50617, 50801, 50984, 51166, 51346, 51526, 51704, 51881
        .long   52056
        .align  4
O3_SQC:
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12289, 10556, 8558, 6787, 5176, 3712, 2390, 1194, 121, -845, -1703, -2469, -3142, -3735, -4248, -4693
        .short  -5068, -5384, -5640, -5845, -5998, -6108, -6172, -6199, -6186, -6142, -6063, -5958, -5821, -5663, -5477, -5274
        .short  -5045, -4802, -4536, -4259, -3961, -3655, -3330, -2999, -2649, -2297, -1926, -1556, -1166, -783, -374, 18
        .short  447, 836, 1307, 872, -1185, -3111, -4274, -5048, -5545, -5838, -5989, -6030, -5996, -5904, -5773, -5610
        .short  -5428, -5228, -5019, -4799, -4575, -4344, -4112, -3875, -3639, -3399, -3160, -2919, -2678, -2435, -2193, -1949
        .short  -1706, -1461, -1217, -972, -727, -480, -234, 14, 261, 510, 758, 1009, 1259, 1512, 1764, 2018
        .short  2273, 2530, 2788, 3048, 3310, 3574, 3840, 4109, 4381, 4657, 4935, 5220, 5507, 5802, 6101, 6409
        .short  6722, 7046, 7377, 7721, 8072, 8438, 8812, 9202, 9598, 10012, 10429, 10864, 11295, 11749, 12184, 12650
        .short  12230, 10610, 8748, 7098, 5591, 4216, 2970, 1836, 815, -108, -932, -1672, -2325, -2905, -3410, -3851
        .short  -4226, -4547, -4809, -5024, -5188, -5312, -5391, -5435, -5439, -5414, -5354, -5268, -5151, -5014, -4848, -4664
        .short  -4455, -4232, -3986, -3729, -3450, -3163, -2856, -2543, -2211, -1876, -1522, -1168, -795, -426, -33, 346
        .short  760, 1137, 1602, 1409, -564, -2727, -4072, -4979, -5590, -5979, -6207, -6313, -6330, -6280, -6183, -6047
        .short  -5886, -5703, -5507, -5299, -5083, -4860, -4633, -4403, -4170, -3934, -3698, -3459, -3220, -2980, -2739, -2498
        .short  -2256, -2013, -1769, -1525, -1281, -1035, -789, -543, -295, -47, 203, 453, 705, 958, 1212, 1468
        .short  1725, 1984, 2246, 2509, 2776, 3045, 3317, 3594, 3874, 4159, 4449, 4745, 5047, 5357, 5675, 6002
        .short  6337, 6684, 7041, 7410, 7789, 8182, 8583, 8998, 9418, 9852, 10287, 10735, 11178, 11640, 12081, 12550
        .short  12144, 10635, 8903, 7371, 5966, 4679, 3508, 2439, 1473, 595, -193, -903, -1533, -2096, -2588, -3022
        .short  -3394, -3715, -3980, -4201, -4374, -4508, -4599, -4657, -4676, -4667, -4624, -4555, -4457, -4337, -4191, -4026
        .short  -3837, -3632, -3406, -3167, -2908, -2638, -2351, -2054, -1742, -1422, -1087, -748, -393, -36, 336, 706
        .short  1098, 1472, 1904, 1946, 178, -2207, -3775, -4830, -5570, -6069, -6386, -6568, -6646, -6648, -6590, -6489
        .short  -6354, -6195, -6015, -5822, -5618, -5406, -5186, -4963, -4735, -4505, -4271, -4037, -3800, -3563, -3324, -3085
        .short  -2844, -2603, -2361, -2118, -1874, -1630, -1384, -1137, -889, -641, -390, -139, 115, 369, 626, 884
        .short  1146, 1409, 1676, 1945, 2219, 2496, 2778, 3065, 3358, 3657, 3963, 4277, 4599, 4930, 5271, 5623
        .short  5986, 6360, 6745, 7141, 7547, 7964, 8388, 8822, 9259, 9705, 10150, 10605, 11053, 11516, 11959, 12427
        .short  12030, 10626, 9019, 7601, 6295, 5096, 4001, 2998, 2086, 1256, 508, -169, -774, -1316, -1793, -2215
        .short  -2581, -2897, -3163, -3386, -3565, -3706, -3807, -3874, -3907, -3910, -3883, -3829, -3748, -3643, -3515, -3366
        .short  -3197, -3008, -2802, -2579, -2340, -2086, -1819, -1538, -1245, -940, -625, -299, 35, 381, 732, 1094
        .short  1460, 1836, 2222, 2474, 1038, -1526, -3369, -4590, -5475, -6097, -6516, -6786, -6936, -6999, -6990, -6931
        .short  -6828, -6698, -6540, -6367, -6177, -5978, -5769, -5555, -5333, -5110, -4881, -4652, -4419, -4185, -3948, -3712
        .short  -3472, -3234, -2992, -2750, -2506, -2263, -2016, -1770, -1520, -1271, -1018, -765, -508, -250, 12, 275
        .short  543, 813, 1088, 1367, 1652, 1942, 2238, 2541, 2852, 3171, 3499, 3837, 4184, 4543, 4912, 5293
        .short  5683, 6085, 6496, 6916, 7342, 7777, 8215, 8660, 9105, 9557, 10005, 10462, 10909, 11371, 11813, 12277
        .short  11884, 10581, 9094, 7786, 6577, 5465, 4444, 3507, 2653, 1872, 1165, 523, -53, -570, -1030, -1437
        .short  -1793, -2102, -2365, -2587, -2768, -2912, -3020, -3095, -3138, -3151, -3137, -3095, -3029, -2938, -2827, -2692
        .short  -2540, -2367, -2179, -1971, -1751, -1513, -1265, -998, -725, -434, -139, 174, 488, 822, 1151, 1506
        .short  1846, 2223, 2565, 2949, 1957, -668, -2837, -4250, -5293, -6051, -6587, -6957, -7189, -7323, -7373, -7364
        .short  -7302, -7207, -7077, -6928, -6757, -6575, -6379, -6177, -5965, -5749, -5527, -5304, -5074, -4845, -4611, -4377
        .short  -4140, -3902, -3661, -3420, -3176, -2932, -2684, -2436, -2184, -1932, -1675, -1417, -1155, -891, -622, -350
        .short  -72, 210, 498, 792, 1093, 1402, 1719, 2045, 2380, 2725, 3081, 3447, 3824, 4212, 4609, 5017
        .short  5432, 5856, 6284, 6720, 7158, 7602, 8046, 8495, 8941, 9393, 9840, 10295, 10739, 11199, 11637, 12098
        .short  11706, 10498, 9126, 7923, 6809, 5782, 4835, 3964, 3166, 2436, 1771, 1168, 622, 132, -307, -696
        .short  -1039, -1337, -1595, -1812, -1993, -2137, -2250, -2328, -2379, -2400, -2396, -2364, -2310, -2231, -2134, -2013
        .short  -1876, -1717, -1545, -1352, -1149, -926, -694, -444, -188, 88, 366, 664, 961, 1280, 1593, 1933
        .short  2256, 2621, 2940, 3361, 2856, 362, -2160, -3804, -5018, -5925, -6590, -7070, -7398, -7612, -7731, -7780
        .short  -7768, -7713, -7619, -7499, -7353, -7191, -7013, -6824, -6625, -6419, -6206, -5988, -5765, -5539, -5310, -5078
        .short  -4843, -4605, -4365, -4123, -3879, -3631, -3382, -3129, -2874, -2615, -2352, -2086, -1815, -1539, -1259, -972
        .short  -679, -379, -72, 245, 569, 904, 1248, 1603, 1967, 2344, 2728, 3124, 3527, 3941, 4360, 4787
        .short  5217, 5654, 6091, 6534, 6975, 7421, 7864, 8313, 8756, 9206, 9649, 10101, 10542, 10997, 11432, 11890
        .short  11490, 10375, 9112, 8011, 6989, 6044, 5170, 4365, 3625, 2947, 2326, 1762, 1250, 788, 373, 4
        .short  -323, -609, -857, -1067, -1244, -1387, -1499, -1581, -1635, -1662, -1664, -1641, -1597, -1529, -1442, -1333
        .short  -1209, -1064, -905, -727, -537, -330, -112, 121, 364, 622, 887, 1167, 1452, 1752, 2054, 2372
        .short  2688, 3027, 3347, 3733, 3662, 1523, -1313, -3248, -4643, -5712, -6518, -7118, -7553, -7856, -8055, -8169
        .short  -8216, -8208, -8158, -8071, -7957, -7818, -7663, -7491, -7308, -7113, -6911, -6701, -6486, -6264, -6039, -5809
        .short  -5576, -5338, -5098, -4853, -4606, -4353, -4099, -3838, -3576, -3306, -3033, -2752, -2468, -2174, -1876, -1567
        .short  -1252, -925, -592, -246, 107, 474, 847, 1233, 1626, 2030, 2439, 2858, 3279, 3709, 4139, 4575
        .short  5010, 5451, 5889, 6332, 6772, 7216, 7656, 8101, 8540, 8987, 9425, 9873, 10309, 10760, 11191, 11644
        .short  11238, 10210, 9051, 8047, 7113, 6248, 5447, 4707, 4025, 3397, 2823, 2298, 1822, 1390, 1002, 654
        .short  347, 75, -160, -362, -531, -670, -779, -861, -916, -947, -953, -937, -898, -840, -761, -664
        .short  -548, -417, -268, -105, 74, 265, 472, 689, 921, 1160, 1415, 1676, 1951, 2230, 2525, 2820
        .short  3132, 3441, 3771, 4096, 4326, 2736, -281, -2576, -4169, -5409, -6366, -7096, -7648, -8050, -8337, -8524
        .short  -8638, -8684, -8683, -8636, -8559, -8449, -8320, -8169, -8005, -7824, -7635, -7433, -7226, -7009, -6789, -6559
        .short  -6327, -6087, -5844, -5593, -5340, -5079, -4815, -4542, -4266, -3979, -3689, -3387, -3081, -2762, -2437, -2099
        .short  -1755, -1397, -1033, -655, -272, 124, 524, 935, 1348, 1770, 2194, 2623, 3053, 3487, 3920, 4357
        .short  4792, 5231, 5666, 6106, 6541, 6981, 7417, 7857, 8292, 8734, 9168, 9610, 10042, 10488, 10915, 11362
        .short  10946, 9999, 8941, 8028, 7181, 6393, 5664, 4986, 4362, 3785, 3258, 2773, 2334, 1933, 1574, 1249
        .short  964, 709, 489, 298, 139, 6, -97, -178, -231, -263, -270, -259, -224, -173, -99, -12
        .short  97, 217, 357, 507, 677, 854, 1051, 1253, 1474, 1698, 1942, 2186, 2450, 2712, 2997, 3272
        .short  3578, 3863, 4193, 4474, 4844, 3899, 927, -1779, -3601, -5020, -6136, -7005, -7680, -8189, -8571, -8840
        .short  -9026, -9134, -9187, -9187, -9149, -9074, -8973, -8846, -8702, -8538, -8362, -8171, -7971, -7759, -7540, -7311
        .short  -7076, -6831, -6581, -6321, -6055, -5780, -5499, -5207, -4909, -4599, -4282, -3953, -3616, -3267, -2909, -2541
        .short  -2164, -1777, -1384, -982, -574, -160, 257, 679, 1103, 1531, 1959, 2390, 2820, 3252, 3683, 4116
        .short  4548, 4981, 5413, 5847, 6278, 6712, 7144, 7578, 8009, 8444, 8874, 9311, 9739, 10178, 10601, 11042
        .short  10613, 9745, 8781, 7956, 7192, 6478, 5818, 5201, 4635, 4109, 3629, 3185, 2783, 2415, 2086, 1786
        .short  1523, 1287, 1085, 907, 760, 636, 540, 464, 415, 384, 377, 387, 420, 466, 535, 616
        .short  718, 831, 963, 1104, 1264, 1431, 1616, 1807, 2016, 2229, 2460, 2692, 2943, 3193, 3462, 3727
        .short  4016, 4292, 4603, 4877, 5247, 4890, 2247, -842, -2949, -4551, -5829, -6845, -7647, -8272, -8753, -9112
        .short  -9373, -9551, -9660, -9712, -9716, -9679, -9608, -9509, -9384, -9239, -9074, -8894, -8698, -8489, -8268, -8036
        .short  -7792, -7538, -7273, -6998, -6712, -6416, -6109, -5792, -5463, -5124, -4775, -4415, -4046, -3668, -3281, -2887
        .short  -2486, -2079, -1668, -1253, -834, -414, 9, 433, 858, 1284, 1710, 2136, 2563, 2990, 3418, 3845
        .short  4272, 4699, 5126, 5554, 5981, 6408, 6835, 7263, 7689, 8118, 8543, 8973, 9397, 9830, 10248, 10683
        .short  10242, 9450, 8574, 7833, 7147, 6505, 5911, 5356, 4844, 4369, 3934, 3532, 3168, 2834, 2534, 2263
        .short  2023, 1808, 1623, 1462, 1328, 1215, 1127, 1060, 1015, 988, 983, 994, 1025, 1072, 1136, 1215
        .short  1310, 1419, 1542, 1678, 1827, 1988, 2162, 2346, 2542, 2747, 2963, 3188, 3423, 3666, 3917, 4178
        .short  4444, 4720, 5002, 5288, 5599, 5664, 3584, 240, -2221, -4011, -5456, -6621, -7554, -8300, -8883, -9338
        .short  -9677, -9928, -10096, -10203, -10250, -10253, -10212, -10140, -10034, -9905, -9749, -9575, -9380, -9169, -8940, -8698
        .short  -8439, -8168, -7880, -7583, -7269, -6946, -6608, -6261, -5902, -5534, -5155, -4771, -4377, -3979, -3574, -3166
        .short  -2754, -2340, -1923, -1506, -1087, -668, -247, 173, 595, 1015, 1437, 1858, 2279, 2700, 3122, 3543
        .short  3965, 4386, 4808, 5229, 5650, 6072, 6493, 6915, 7335, 7758, 8178, 8602, 9019, 9446, 9859, 10288
        .short  9840, 9120, 8327, 7665, 7052, 6480, 5948, 5452, 4993, 4569, 4178, 3818, 3490, 3191, 2921, 2678
        .short  2462, 2271, 2104, 1961, 1840, 1742, 1663, 1606, 1566, 1547, 1544, 1560, 1590, 1639, 1700, 1779
        .short  1869, 1975, 2092, 2224, 2365, 2521, 2684, 2863, 3047, 3247, 3449, 3668, 3888, 4126, 4360, 4616
        .short  4863, 5137, 5393, 5689, 5945, 6236, 4836, 1452, -1414, -3412, -5025, -6340, -7407, -8274, -8964, -9514
        .short  -9937, -10261, -10491, -10652, -10744, -10785, -10773, -10724, -10635, -10516, -10365, -10191, -9990, -9769, -9525, -9265
        .short  -8983, -8688, -8374, -8048, -7706, -7355, -6990, -6617, -6234, -5846, -5450, -5050, -4646, -4239, -3830, -3419
        .short  -3006, -2593, -2179, -1765, -1350, -935, -520, -105, 310, 725, 1141, 1556, 1971, 2387, 2802, 3217
        .short  3632, 4048, 4463, 4879, 5293, 5709, 6124, 6540, 6954, 7371, 7784, 8202, 8614, 9035, 9441, 9864
        .short  9417, 8765, 8049, 7462, 6917, 6411, 5939, 5500, 5092, 4715, 4367, 4049, 3757, 3493, 3252, 3038
        .short  2846, 2679, 2531, 2407, 2301, 2217, 2150, 2104, 2072, 2060, 2062, 2083, 2115, 2166, 2228, 2306
        .short  2394, 2499, 2611, 2741, 2876, 3028, 3184, 3357, 3532, 3725, 3918, 4130, 4339, 4569, 4792, 5039
        .short  5275, 5540, 5783, 6071, 6306, 6657, 5910, 2746, -523, -2768, -4545, -6008, -7210, -8197, -8997, -9642
        .short  -10150, -10547, -10841, -11054, -11190, -11264, -11280, -11249, -11171, -11056, -10904, -10721, -10508, -10269, -10005, -9720
        .short  -9414, -9092, -8753, -8401, -8037, -7663, -7281, -6892, -6498, -6100, -5699, -5295, -4891, -4484, -4077, -3669
        .short  -3261, -2852, -2444, -2034, -1626, -1216, -808, -398, 10, 420, 828, 1238, 1646, 2056, 2464, 2874
        .short  3282, 3692, 4100, 4510, 4918, 5328, 5735, 6147, 6553, 6965, 7371, 7784, 8188, 8603, 9003, 9420
        .short  8986, 8396, 7751, 7232, 6753, 6308, 5892, 5506, 5147, 4816, 4510, 4231, 3975, 3743, 3533, 3347
        .short  3180, 3035, 2908, 2803, 2714, 2644, 2590, 2555, 2533, 2529, 2538, 2564, 2601, 2655, 2719, 2798
        .short  2886, 2989, 3101, 3227, 3360, 3506, 3659, 3825, 3997, 4181, 4370, 4571, 4776, 4993, 5213, 5446
        .short  5678, 5926, 6168, 6435, 6677, 6994, 6758, 4044, 459, -2084, -4025, -5634, -6969, -8074, -8984, -9723
        .short  -10318, -10785, -11144, -11406, -11585, -11689, -11728, -11708, -11638, -11519, -11359, -11161, -10931, -10669, -10383, -10073
        .short  -9745, -9399, -9041, -8671, -8294, -7908, -7519, -7124, -6729, -6329, -5930, -5528, -5128, -4725, -4324, -3920
        .short  -3519, -3115, -2714, -2309, -1908, -1504, -1103, -698, -297, 107, 508, 913, 1314, 1718, 2119, 2524
        .short  2925, 3329, 3730, 4135, 4536, 4940, 5341, 5746, 6146, 6552, 6951, 7358, 7756, 8165, 8559, 8970
        .short  8553, 8021, 7443, 6987, 6568, 6180, 5817, 5481, 5169, 4880, 4615, 4373, 4152, 3952, 3772, 3611
        .short  3470, 3347, 3242, 3154, 3083, 3028, 2988, 2964, 2954, 2958, 2976, 3007, 3052, 3108, 3176, 3256
        .short  3347, 3449, 3562, 3684, 3818, 3959, 4111, 4270, 4440, 4616, 4803, 4995, 5197, 5403, 5620, 5839
        .short  6071, 6302, 6547, 6789, 7046, 7307, 7405, 5274, 1520, -1365, -3475, -5226, -6690, -7911, -8929, -9761
        .short  -10441, -10979, -11400, -11709, -11928, -12057, -12116, -12103, -12033, -11906, -11735, -11518, -11269, -10985, -10678, -10347
        .short  -10003, -9641, -9272, -8893, -8511, -8121, -7732, -7338, -6945, -6549, -6155, -5757, -5363, -4965, -4570, -4172
        .short  -3777, -3379, -2984, -2586, -2191, -1793, -1398, -1000, -605, -207, 188, 586, 981, 1379, 1774, 2172
        .short  2567, 2965, 3360, 3759, 4153, 4552, 4946, 5345, 5739, 6138, 6532, 6932, 7324, 7726, 8115, 8518
        .short  8128, 7648, 7132, 6733, 6371, 6034, 5722, 5432, 5164, 4916, 4690, 4482, 4294, 4124, 3974, 3839
        .short  3723, 3621, 3538, 3467, 3414, 3373, 3349, 3336, 3338, 3351, 3379, 3416, 3468, 3528, 3602, 3683
        .short  3779, 3880, 3996, 4116, 4250, 4388, 4540, 4695, 4864, 5033, 5218, 5402, 5602, 5799, 6014, 6222
        .short  6452, 6670, 6915, 7138, 7404, 7623, 7888, 6365, 2630, -614, -2908, -4795, -6383, -7716, -8837, -9762
        .short  -10524, -11131, -11611, -11967, -12221, -12374, -12447, -12437, -12364, -12226, -12040, -11806, -11538, -11236, -10913, -10568
        .short  -10213, -9843, -9470, -9088, -8706, -8318, -7932, -7541, -7153, -6762, -6373, -5982, -5593, -5201, -4812, -4420
        .short  -4031, -3640, -3250, -2859, -2469, -2078, -1689, -1297, -908, -516, -127, 265, 654, 1045, 1435, 1826
        .short  2216, 2607, 2997, 3388, 3777, 4169, 4558, 4950, 5339, 5731, 6119, 6512, 6899, 7294, 7678, 8075
        .short  7714, 7283, 6823, 6476, 6166, 5878, 5613, 5364, 5138, 4928, 4738, 4563, 4408, 4266, 4143, 4033
        .short  3941, 3861, 3798, 3745, 3710, 3684, 3674, 3673, 3688, 3710, 3748, 3792, 3852, 3917, 3997, 4082
        .short  4181, 4285, 4402, 4523, 4658, 4795, 4946, 5099, 5266, 5432, 5614, 5794, 5990, 6182, 6392, 6595
        .short  6819, 7030, 7270, 7485, 7747, 7950, 8268, 7290, 3744, 167, -2333, -4352, -6056, -7498, -8717, -9731
        .short  -10572, -11248, -11783, -12183, -12469, -12645, -12727, -12720, -12640, -12492, -12290, -12041, -11756, -11441, -11107, -10755
        .short  -10393, -10022, -9647, -9267, -8887, -8504, -8121, -7737, -7353, -6968, -6584, -6199, -5815, -5430, -5046, -4661
        .short  -4277, -3892, -3508, -3123, -2739, -2354, -1970, -1585, -1201, -816, -432, -47, 337, 722, 1106, 1491
        .short  1875, 2260, 2644, 3029, 3413, 3798, 4182, 4567, 4951, 5337, 5720, 6106, 6488, 6876, 7255, 7645
        .short  7315, 6930, 6521, 6222, 5959, 5715, 5493, 5285, 5097, 4922, 4766, 4622, 4497, 4383, 4286, 4200
        .short  4131, 4071, 4028, 3994, 3975, 3964, 3968, 3980, 4006, 4039, 4087, 4140, 4206, 4278, 4364, 4454
        .short  4557, 4664, 4784, 4907, 5042, 5180, 5331, 5483, 5648, 5814, 5993, 6171, 6363, 6552, 6757, 6957
        .short  7174, 7383, 7614, 7828, 8078, 8283, 8594, 8063, 4824, 965, -1763, -3909, -5723, -7266, -8577, -9678
        .short  -10592, -11334, -11921, -12365, -12679, -12875, -12964, -12959, -12871, -12713, -12497, -12236, -11938, -11615, -11273, -10918
        .short  -10553, -10184, -9810, -9435, -9058, -8680, -8302, -7924, -7544, -7166, -6787, -6408, -6029, -5651, -5272, -4893
        .short  -4514, -4135, -3756, -3378, -2998, -2620, -2241, -1862, -1483, -1105, -725, -347, 32, 411, 790, 1168
        .short  1548, 1926, 2305, 2684, 3063, 3442, 3821, 4199, 4578, 4957, 5335, 5715, 6093, 6474, 6848, 7231
        .short  6934, 6592, 6230, 5974, 5755, 5552, 5369, 5198, 5045, 4904, 4779, 4665, 4568, 4480, 4408, 4345
        .short  4297, 4258, 4233, 4217, 4214, 4218, 4236, 4261, 4299, 4343, 4399, 4461, 4535, 4615, 4706, 4802
        .short  4909, 5021, 5143, 5269, 5406, 5546, 5697, 5850, 6014, 6180, 6356, 6534, 6721, 6911, 7109, 7309
        .short  7519, 7728, 7949, 8166, 8400, 8616, 8893, 8673, 5807, 1759, -1209, -3477, -5395, -7032, -8428, -9609
        .short  -10592, -11397, -12032, -12517, -12857, -13071, -13166, -13160, -13065, -12898, -12670, -12400, -12093, -11765, -11419, -11064
        .short  -10699, -10333, -9962, -9592, -9218, -8847, -8472, -8100, -7726, -7354, -6979, -6607, -6233, -5860, -5486, -5113
        .short  -4739, -4367, -3992, -3620, -3246, -2873, -2499, -2127, -1752, -1380, -1006, -633, -259, 114, 488, 860
        .short  1235, 1607, 1981, 2354, 2728, 3101, 3474, 3848, 4221, 4595, 4968, 5342, 5714, 6090, 6459, 6836
        .short  6573, 6270, 5950, 5734, 5553, 5389, 5242, 5106, 4985, 4875, 4779, 4693, 4621, 4559, 4509, 4469
        .short  4441, 4422, 4414, 4415, 4427, 4447, 4478, 4516, 4565, 4621, 4686, 4758, 4839, 4927, 5024, 5127
        .short  5237, 5355, 5479, 5610, 5748, 5892, 6042, 6198, 6360, 6529, 6702, 6881, 7065, 7255, 7448, 7649
        .short  7852, 8063, 8274, 8495, 8715, 8942, 9184, 9178, 6691, 2530, -679, -3068, -5080, -6804, -8278, -9534
        .short  -10581, -11443, -12124, -12645, -13009, -13238, -13338, -13332, -13230, -13055, -12818, -12541, -12228, -11898, -11550, -11196
        .short  -10833, -10471, -10103, -9738, -9369, -9002, -8633, -8266, -7897, -7530, -7160, -6793, -6424, -6057, -5688, -5321
        .short  -4951, -4584, -4215, -3848, -3479, -3111, -2742, -2375, -2006, -1639, -1269, -902, -533, -166, 203, 571
        .short  940, 1307, 1676, 2044, 2412, 2780, 3149, 3517, 3885, 4253, 4621, 4990, 5357, 5727, 6091, 6464
        .short  6233, 5966, 5685, 5505, 5360, 5231, 5116, 5012, 4921, 4840, 4771, 4712, 4664, 4625, 4597, 4577
        .short  4568, 4568, 4577, 4595, 4622, 4657, 4700, 4751, 4810, 4877, 4952, 5034, 5122, 5218, 5321, 5431
        .short  5546, 5669, 5797, 5933, 6073, 6220, 6371, 6530, 6692, 6862, 7034, 7215, 7396, 7587, 7777, 7979
        .short  8176, 8388, 8593, 8816, 9025, 9260, 9476, 9599, 7451, 3244, -189, -2694, -4793, -6593, -8138, -9460
        .short  -10566, -11480, -12202, -12755, -13141, -13383, -13486, -13479, -13371, -13190, -12946, -12663, -12347, -12015, -11668, -11316
        .short  -10956, -10598, -10234, -9873, -9509, -9147, -8783, -8421, -8056, -7694, -7330, -6968, -6603, -6241, -5877, -5515
        .short  -5150, -4788, -4424, -4062, -3697, -3335, -2971, -2608, -2244, -1882, -1518, -1155, -791, -429, -65, 298
        .short  662, 1024, 1388, 1751, 2114, 2478, 2841, 3204, 3567, 3931, 4294, 4658, 5019, 5385, 5744, 6112
        .short  5915, 5682, 5435, 5288, 5175, 5078, 4993, 4919, 4855, 4801, 4757, 4722, 4696, 4679, 4671, 4672
        .short  4681, 4699, 4724, 4757, 4798, 4847, 4903, 4967, 5036, 5114, 5198, 5289, 5386, 5490, 5599, 5716
        .short  5836, 5965, 6097, 6237, 6380, 6531, 6684, 6846, 7008, 7181, 7352, 7535, 7715, 7907, 8095, 8297
        .short  8491, 8704, 8904, 9128, 9330, 9569, 9767, 9967, 8094, 3880, 251, -2365, -4541, -6409, -8016, -9397
        .short  -10554, -11513, -12272, -12853, -13257, -13509, -13616, -13606, -13493, -13306, -13056, -12770, -12452, -12120, -11774, -11425
        .short  -11069, -10714, -10355, -9998, -9638, -9281, -8921, -8564, -8204, -7846, -7487, -7129, -6769, -6412, -6052, -5695
        .short  -5335, -4977, -4618, -4260, -3901, -3543, -3183, -2825, -2466, -2108, -1749, -1391, -1032, -673, -315, 44
        .short  403, 761, 1120, 1479, 1837, 2196, 2554, 2913, 3271, 3631, 3988, 4348, 4705, 5066, 5421, 5784
        .short  5619, 5417, 5202, 5085, 5000, 4933, 4876, 4829, 4790, 4761, 4740, 4727, 4722, 4726, 4737, 4756
        .short  4782, 4817, 4857, 4906, 4960, 5023, 5090, 5166, 5246, 5335, 5427, 5528, 5632, 5745, 5860, 5984
        .short  6110, 6245, 6381, 6526, 6672, 6827, 6983, 7148, 7312, 7486, 7659, 7843, 8022, 8216, 8403, 8605
        .short  8798, 9010, 9208, 9432, 9629, 9871, 10058, 10298, 8623, 4415, 624, -2091, -4334, -6261, -7922, -9351
        .short  -10554, -11551, -12341, -12944, -13363, -13622, -13729, -13717, -13598, -13406, -13153, -12863, -12545, -12214, -11869, -11523
        .short  -11170, -10819, -10464, -10112, -9756, -9403, -9048, -8695, -8339, -7986, -7631, -7278, -6922, -6569, -6214, -5860
        .short  -5505, -5152, -4797, -4443, -4088, -3735, -3380, -3026, -2671, -2317, -1963, -1609, -1254, -900, -546, -192
        .short  163, 517, 871, 1226, 1579, 1934, 2288, 2643, 2996, 3352, 3705, 4060, 4413, 4770, 5120, 5478
        .short  5346, 5172, 4986, 4896, 4838, 4797, 4765, 4743, 4728, 4721, 4722, 4730, 4745, 4768, 4796, 4833
        .short  4875, 4925, 4980, 5043, 5110, 5186, 5265, 5352, 5443, 5541, 5643, 5752, 5865, 5985, 6107, 6238
        .short  6369, 6510, 6651, 6801, 6951, 7110, 7268, 7437, 7603, 7780, 7954, 8139, 8320, 8514, 8701, 8904
        .short  9097, 9309, 9505, 9729, 9924, 10166, 10348, 10606, 9042, 4829, 916, -1881, -4182, -6156, -7861, -9331
        .short  -10570, -11598, -12412, -13033, -13462, -13724, -13831, -13814, -13690, -13493, -13236, -12945, -12626, -12296, -11954, -11610
        .short  -11261, -10914, -10563, -10214, -9863, -9514, -9163, -8813, -8462, -8113, -7762, -7413, -7062, -6712, -6361, -6012
        .short  -5661, -5311, -4961, -4611, -4260, -3911, -3560, -3210, -2860, -2510, -2159, -1809, -1459, -1109, -759, -408
        .short  -58, 292, 642, 992, 1342, 1693, 2042, 2393, 2743, 3094, 3443, 3795, 4143, 4496, 4842, 5196
        .short  5094, 4948, 4789, 4723, 4689, 4672, 4663, 4664, 4670, 4685, 4705, 4733, 4766, 4806, 4852, 4905
        .short  4962, 5027, 5096, 5172, 5252, 5339, 5429, 5527, 5628, 5736, 5847, 5965, 6085, 6213, 6342, 6479
        .short  6617, 6763, 6909, 7064, 7218, 7381, 7543, 7715, 7884, 8063, 8239, 8427, 8609, 8805, 8992, 9196
        .short  9389, 9601, 9797, 10020, 10215, 10456, 10636, 10896, 9351, 5105, 1112, -1747, -4091, -6102, -7842, -9343
        .short  -10610, -11660, -12492, -13123, -13557, -13819, -13921, -13899, -13769, -13567, -13307, -13014, -12696, -12367, -12028, -11687
        .short  -11342, -10997, -10650, -10305, -9958, -9613, -9265, -8920, -8573, -8227, -7880, -7534, -7187, -6842, -6495, -6149
        .short  -5802, -5456, -5109, -4763, -4417, -4071, -3724, -3378, -3031, -2685, -2339, -1992, -1646, -1300, -953, -607
        .short  -261, 86, 432, 779, 1124, 1471, 1817, 2164, 2510, 2857, 3202, 3550, 3894, 4243, 4586, 4936
        .short  4867, 4744, 4610, 4565, 4553, 4557, 4570, 4591, 4618, 4651, 4690, 4736, 4786, 4843, 4904, 4972
        .short  5044, 5122, 5204, 5293, 5385, 5483, 5584, 5693, 5803, 5921, 6040, 6166, 6294, 6429, 6565, 6709
        .short  6853, 7005, 7156, 7316, 7474, 7642, 7807, 7982, 8154, 8337, 8515, 8705, 8889, 9086, 9275, 9480
        .short  9673, 9886, 10082, 10306, 10500, 10740, 10921, 11175, 9564, 5243, 1207, -1689, -4064, -6103, -7867, -9390
        .short  -10676, -11741, -12582, -13218, -13651, -13909, -14004, -13975, -13839, -13631, -13368, -13074, -12756, -12429, -12092, -11754
        .short  -11412, -11071, -10727, -10386, -10042, -9700, -9357, -9015, -8671, -8329, -7985, -7643, -7300, -6958, -6614, -6272
        .short  -5928, -5586, -5243, -4900, -4557, -4215, -3872, -3529, -3186, -2843, -2500, -2158, -1815, -1472, -1129, -786
        .short  -443, -100, 242, 585, 928, 1271, 1613, 1957, 2299, 2643, 2984, 3329, 3670, 4015, 4354, 4701
        .short  4661, 4561, 4450, 4424, 4431, 4455, 4488, 4528, 4573, 4625, 4681, 4742, 4809, 4881, 4957, 5038
        .short  5124, 5215, 5309, 5410, 5513, 5622, 5734, 5852, 5972, 6098, 6226, 6360, 6496, 6638, 6781, 6931
        .short  7081, 7238, 7395, 7559, 7723, 7894, 8064, 8242, 8418, 8603, 8785, 8976, 9163, 9362, 9553, 9758
        .short  9953, 10167, 10364, 10587, 10783, 11021, 11207, 11431, 9644, 5220, 1190, -1719, -4112, -6166, -7944, -9479
        .short  -10773, -11845, -12687, -13320, -13746, -13995, -14080, -14041, -13897, -13685, -13418, -13124, -12806, -12481, -12146, -11811
        .short  -11471, -11134, -10793, -10455, -10114, -9776, -9435, -9097, -8756, -8418, -8077, -7739, -7398, -7059, -6719, -6380
        .short  -6040, -5701, -5361, -5022, -4682, -4343, -4003, -3664, -3324, -2984, -2645, -2305, -1966, -1626, -1286, -947
        .short  -607, -268, 72, 411, 751, 1091, 1430, 1770, 2109, 2449, 2788, 3128, 3466, 3808, 4144, 4487
        .short  4477, 4398, 4308, 4299, 4325, 4367, 4417, 4474, 4537, 4604, 4677, 4753, 4835, 4921, 5011, 5105
        .short  5203, 5306, 5413, 5524, 5638, 5757, 5879, 6006, 6135, 6270, 6406, 6548, 6691, 6840, 6990, 7146
        .short  7302, 7464, 7627, 7796, 7964, 8140, 8314, 8496, 8675, 8863, 9048, 9242, 9431, 9632, 9825, 10032
        .short  10229, 10443, 10643, 10865, 11064, 11298, 11493, 11667, 9602, 5040, 1059, -1839, -4235, -6294, -8075, -9612
        .short  -10906, -11973, -12808, -13430, -13843, -14078, -14151, -14100, -13947, -13729, -13459, -13164, -12846, -12523, -12190, -11858
        .short  -11521, -11186, -10848, -10514, -10176, -9840, -9503, -9167, -8829, -8494, -8156, -7821, -7483, -7148, -6810, -6475
        .short  -6137, -5802, -5464, -5129, -4791, -4455, -4118, -3782, -3445, -3109, -2772, -2436, -2099, -1763, -1426, -1090
        .short  -753, -417, -80, 256, 593, 930, 1266, 1603, 1939, 2276, 2612, 2949, 3285, 3623, 3957, 4296
        .short  4315, 4256, 4185, 4192, 4234, 4292, 4359, 4432, 4510, 4592, 4680, 4770, 4866, 4964, 5067, 5174
        .short  5284, 5398, 5516, 5637, 5762, 5890, 6022, 6157, 6296, 6438, 6583, 6731, 6882, 7037, 7194, 7355
        .short  7518, 7685, 7854, 8027, 8201, 8380, 8559, 8744, 8928, 9118, 9307, 9503, 9696, 9897, 10095, 10301
        .short  10503, 10715, 10920, 11139, 11345, 11570, 11785, 11849, 9380, 4696, 814, -2052, -4437, -6488, -8261, -9790
        .short  -11073, -12127, -12945, -13550, -13943, -14160, -14215, -14151, -13988, -13764, -13490, -13194, -12877, -12555, -12224, -11894
        .short  -11560, -11228, -10893, -10561, -10225, -9893, -9558, -9225, -8890, -8558, -8223, -7890, -7555, -7223, -6888, -6555
        .short  -6220, -5887, -5552, -5220, -4885, -4552, -4217, -3885, -3550, -3217, -2882, -2549, -2215, -1882, -1547, -1214
        .short  -880, -547, -212, 121, 455, 789, 1123, 1456, 1790, 2124, 2458, 2792, 3125, 3460, 3791, 4128
        .short  4175, 4134, 4081, 4102, 4159, 4231, 4314, 4400, 4494, 4589, 4691, 4794, 4903, 5013, 5128, 5245
        .short  5368, 5492, 5621, 5751, 5886, 6023, 6164, 6307, 6455, 6604, 6757, 6912, 7071, 7231, 7396, 7561
        .short  7731, 7903, 8078, 8254, 8435, 8616, 8801, 8988, 9178, 9369, 9564, 9760, 9959, 10160, 10363, 10568
        .short  10776, 10985, 11197, 11410, 11627, 11838, 12085, 11939, 8956, 4199, 461, -2357, -4717, -6748, -8504, -10013
        .short  -11276, -12306, -13100, -13677, -14046, -14238, -14275, -14194, -14021, -13789, -13513, -13214, -12898, -12577, -12248, -11920
        .short  -11588, -11259, -10926, -10597, -10264, -9934, -9601, -9271, -8939, -8609, -8276, -7946, -7614, -7284, -6951, -6621
        .short  -6289, -5958, -5626, -5296, -4963, -4633, -4301, -3971, -3638, -3308, -2976, -2645, -2313, -1983, -1651, -1320
        .short  -988, -658, -326, 5, 337, 668, 1000, 1330, 1662, 1993, 2324, 2656, 2987, 3319, 3648, 3981
        .short  4055, 4032, 3997, 4031, 4102, 4186, 4283, 4383, 4490, 4598, 4712, 4827, 4948, 5069, 5196, 5324
        .short  5457, 5590, 5729, 5868, 6013, 6158, 6309, 6459, 6615, 6770, 6932, 7092, 7259, 7425, 7597, 7767
        .short  7944, 8119, 8301, 8481, 8667, 8851, 9042, 9231, 9427, 9619, 9820, 10016, 10221, 10421, 10631, 10834
        .short  11049, 11254, 11475, 11680, 11912, 12104, 12389, 11880, 8295, 3554, -5, -2759, -5079, -7078, -8806, -10283
        .short  -11516, -12510, -13272, -13813, -14151, -14313, -14328, -14229, -14045, -13804, -13525, -13224, -12909, -12588, -12262, -11935
        .short  -11607, -11279, -10949, -10621, -10291, -9963, -9633, -9305, -8975, -8647, -8317, -7989, -7659, -7331, -7001, -6673
        .short  -6343, -6015, -5685, -5357, -5027, -4699, -4369, -4041, -3711, -3383, -3053, -2725, -2395, -2067, -1737, -1409
        .short  -1079, -751, -421, -93, 237, 565, 895, 1223, 1552, 1881, 2210, 2539, 2868, 3198, 3525, 3856
        .short  3958, 3951, 3930, 3977, 4059, 4156, 4265, 4377, 4496, 4616, 4742, 4868, 5000, 5132, 5270, 5407
        .short  5550, 5693, 5841, 5989, 6142, 6295, 6454, 6612, 6775, 6938, 7106, 7273, 7447, 7618, 7796, 7972
        .short  8155, 8335, 8522, 8706, 8898, 9086, 9282, 9473, 9674, 9869, 10074, 10272, 10482, 10683, 10898, 11100
        .short  11321, 11524, 11753, 11952, 12196, 12376, 12673, 11588, 7404, 2802, -566, -3246, -5514, -7469, -9159, -10593
        .short  -11786, -12736, -13456, -13954, -14256, -14385, -14375, -14256, -14061, -13811, -13529, -13226, -12912, -12591, -12267, -11941
        .short  -11615, -11288, -10962, -10634, -10308, -9981, -9654, -9327, -9000, -8673, -8346, -8019, -7692, -7365, -7038, -6711
        .short  -6384, -6057, -5730, -5403, -5076, -4749, -4422, -4095, -3768, -3441, -3114, -2787, -2460, -2133, -1806, -1479
        .short  -1152, -825, -498, -171, 156, 483, 810, 1137, 1464, 1791, 2118, 2445, 2771, 3099, 3425, 3753
        .short  3880, 3890, 3883, 3942, 4034, 4143, 4262, 4387, 4516, 4648, 4784, 4922, 5063, 5206, 5352, 5500
        .short  5651, 5803, 5960, 6116, 6277, 6439, 6604, 6770, 6940, 7110, 7285, 7459, 7637, 7816, 7999, 8181
        .short  8368, 8554, 8745, 8935, 9130, 9323, 9523, 9719, 9923, 10122, 10330, 10532, 10744, 10948, 11165, 11371
        .short  11594, 11800, 12030, 12233, 12475, 12668, 12878, 10959, 6280, 1945, -1233, -3823, -6028, -7928, -9566, -10947
        .short  -12087, -12982, -13651, -14099, -14359, -14450, -14414, -14273, -14066, -13807, -13523, -13216, -12904, -12582, -12261, -11936
        .short  -11613, -11286, -10963, -10636, -10312, -9986, -9662, -9335, -9012, -8685, -8361, -8035, -7711, -7385, -7061, -6734
        .short  -6410, -6084, -5760, -5434, -5110, -4784, -4459, -4133, -3809, -3483, -3159, -2833, -2508, -2182, -1858, -1532
        .short  -1208, -882, -557, -232, 93, 419, 743, 1069, 1394, 1719, 2044, 2370, 2694, 3021, 3343, 3671
        .short  3824, 3849, 3855, 3925, 4026, 4146, 4274, 4410, 4549, 4692, 4837, 4985, 5135, 5288, 5443, 5600
        .short  5759, 5921, 6084, 6250, 6417, 6588, 6759, 6933, 7108, 7287, 7466, 7648, 7831, 8016, 8203, 8392
        .short  8583, 8776, 8970, 9166, 9364, 9563, 9765, 9967, 10172, 10378, 10586, 10795, 11006, 11218, 11433, 11648
        .short  11866, 12083, 12304, 12525, 12744, 12990, 12885, 9929, 5002, 1018, -1986, -4477, -6607, -8442, -10016, -11334
        .short  -12409, -13242, -13850, -14244, -14456, -14509, -14443, -14283, -14062, -13796, -13507, -13199, -12886, -12565, -12245, -11921
        .short  -11600, -11275, -10953, -10628, -10306, -9980, -9658, -9333, -9011, -8686, -8364, -8039, -7717, -7392, -7070, -6745
        .short  -6423, -6098, -5775, -5450, -5128, -4803, -4481, -4156, -3834, -3509, -3187, -2862, -2540, -2215, -1892, -1567
        .short  -1245, -920, -598, -273, 49, 374, 696, 1021, 1343, 1668, 1990, 2316, 2637, 2963, 3284, 3611
        .short  3789, 3827, 3847, 3927, 4036, 4166, 4303, 4449, 4596, 4750, 4903, 5061, 5220, 5382, 5544, 5711
        .short  5877, 6048, 6218, 6392, 6566, 6744, 6921, 7103, 7284, 7469, 7653, 7843, 8030, 8223, 8413, 8609
        .short  8803, 9003, 9199, 9403, 9602, 9809, 10011, 10221, 10426, 10639, 10847, 11064, 11273, 11494, 11705, 11930
        .short  12141, 12373, 12581, 12826, 13014, 13318, 12488, 8467, 3634, 18, -2822, -5205, -7248, -9008, -10504, -11750
        .short  -12748, -13511, -14049, -14385, -14544, -14559, -14461, -14282, -14046, -13774, -13480, -13172, -12857, -12539, -12218, -11897
        .short  -11575, -11253, -10931, -10608, -10286, -9964, -9642, -9319, -8997, -8675, -8353, -8030, -7709, -7386, -7064, -6741
        .short  -6420, -6097, -5775, -5452, -5131, -4808, -4486, -4163, -3842, -3519, -3198, -2875, -2553, -2230, -1909, -1586
        .short  -1264, -941, -620, -297, 24, 348, 669, 992, 1313, 1637, 1958, 2282, 2602, 2926, 3245, 3571
        .short  3775, 3826, 3858, 3946, 4065, 4202, 4348, 4502, 4659, 4820, 4983, 5149, 5317, 5487, 5658, 5831
        .short  6006, 6183, 6361, 6542, 6723, 6908, 7092, 7280, 7467, 7658, 7849, 8043, 8236, 8434, 8630, 8831
        .short  9030, 9234, 9436, 9643, 9847, 10058, 10265, 10478, 10687, 10904, 11115, 11335, 11548, 11772, 11986, 12215
        .short  12428, 12663, 12873, 13119, 13320, 13519, 11496, 6694, 2244, -1050, -3729, -5997, -7943, -9616, -11023, -12185
        .short  -13097, -13782, -14244, -14518, -14622, -14598, -14468, -14271, -14020, -13743, -13443, -13135, -12819, -12502, -12181, -11862
        .short  -11540, -11220, -10898, -10578, -10255, -9936, -9613, -9293, -8971, -8651, -8329, -8009, -7687, -7367, -7045, -6724
        .short  -6402, -6082, -5760, -5440, -5118, -4798, -4476, -4155, -3834, -3513, -3191, -2871, -2549, -2229, -1907, -1586
        .short  -1265, -944, -623, -302, 19, 340, 662, 983, 1304, 1625, 1946, 2267, 2588, 2910, 3229, 3552
        .short  3782, 3845, 3891, 3986, 4114, 4257, 4413, 4573, 4741, 4908, 5081, 5253, 5430, 5606, 5786, 5966
        .short  6149, 6332, 6519, 6704, 6894, 7083, 7275, 7467, 7663, 7857, 8056, 8253, 8454, 8654, 8859, 9061
        .short  9268, 9474, 9683, 9891, 10104, 10314, 10529, 10742, 10960, 11175, 11395, 11612, 11836, 12055, 12281, 12501
        .short  12732, 12951, 13189, 13397, 13680, 13288, 9786, 4768, 836, -2192, -4707, -6850, -8690, -10259, -11569, -12631
        .short  -13451, -14046, -14430, -14635, -14686, -14619, -14462, -14244, -13983, -13698, -13395, -13085, -12769, -12452, -12132, -11813
        .short  -11493, -11173, -10852, -10533, -10212, -9893, -9572, -9253, -8932, -8612, -8291, -7972, -7651, -7332, -7011, -6692
        .short  -6371, -6051, -5730, -5411, -5090, -4771, -4450, -4131, -3809, -3490, -3169, -2850, -2529, -2210, -1889, -1570
        .short  -1248, -929, -608, -289, 32, 351, 672, 992, 1313, 1632, 1953, 2272, 2593, 2913, 3232, 3553
        .short  3810, 3885, 3942, 4046, 4180, 4331, 4494, 4662, 4836, 5012, 5192, 5372, 5556, 5739, 5926, 6113
        .short  6303, 6493, 6686, 6878, 7074, 7269, 7468, 7665, 7866, 8066, 8271, 8473, 8680, 8884, 9094, 9301
        .short  9514, 9723, 9938, 10149, 10367, 10580, 10801, 11015, 11239, 11455, 11682, 11899, 12130, 12347, 12582, 12799
        .short  13040, 13252, 13507, 13702, 13959, 12254, 7549, 2887, -582, -3378, -5731, -7741, -9467, -10920, -12123, -13075
        .short  -13797, -14294, -14601, -14734, -14734, -14625, -14444, -14205, -13936, -13642, -13339, -13025, -12711, -12392, -12075, -11754
        .short  -11436, -11116, -10797, -10477, -10159, -9838, -9520, -9199, -8881, -8561, -8242, -7922, -7603, -7283, -6964, -6644
        .short  -6325, -6005, -5687, -5367, -5048, -4728, -4409, -4089, -3770, -3450, -3131, -2811, -2492, -2172, -1853, -1534
        .short  -1214, -895, -576, -256, 63, 383, 702, 1022, 1341, 1661, 1980, 2299, 2618, 2939, 3257, 3577
        .short  3859, 3947, 4012, 4126, 4265, 4424, 4592, 4769, 4948, 5132, 5317, 5507, 5696, 5888, 6080, 6275
        .short  6470, 6668, 6865, 7066, 7265, 7469, 7671, 7876, 8081, 8289, 8495, 8706, 8915, 9127, 9339, 9554
        .short  9767, 9985, 10200, 10420, 10637, 10859, 11079, 11303, 11524, 11751, 11974, 12203, 12427, 12659, 12884, 13120
        .short  13344, 13587, 13800, 14086, 13710, 10213, 5126, 1090, -2025, -4603, -6791, -8664, -10259, -11591, -12672, -13510
        .short  -14122, -14524, -14746, -14814, -14762, -14617, -14409, -14155, -13875, -13576, -13270, -12956, -12641, -12322, -12005, -11685
        .short  -11367, -11047, -10729, -10409, -10092, -9772, -9454, -9134, -8816, -8496, -8178, -7858, -7540, -7220, -6902, -6582
        .short  -6264, -5944, -5627, -5306, -4989, -4669, -4351, -4031, -3713, -3393, -3075, -2755, -2437, -2117, -1799, -1479
        .short  -1162, -841, -524, -203, 114, 434, 752, 1072, 1390, 1710, 2028, 2348, 2665, 2987, 3303, 3624
        .short  3931, 4029, 4106, 4226, 4373, 4537, 4712, 4894, 5081, 5271, 5464, 5659, 5855, 6053, 6252, 6453
        .short  6655, 6858, 7062, 7268, 7474, 7682, 7890, 8101, 8311, 8524, 8736, 8951, 9165, 9383, 9599, 9819
        .short  10036, 10258, 10477, 10702, 10923, 11150, 11372, 11601, 11825, 12057, 12281, 12517, 12741, 12980, 13203, 13448
        .short  13668, 13923, 14132, 14342, 12329, 7445, 2807, -672, -3492, -5861, -7880, -9608, -11059, -12259, -13206, -13924
        .short  -14420, -14727, -14864, -14869, -14766, -14590, -14356, -14091, -13800, -13499, -13187, -12875, -12557, -12240, -11921, -11604
        .short  -11284, -10967, -10647, -10329, -10010, -9692, -9372, -9055, -8735, -8418, -8098, -7780, -7461, -7143, -6824, -6506
        .short  -6186, -5869, -5549, -5231, -4912, -4594, -4275, -3957, -3638, -3320, -3001, -2682, -2363, -2045, -1726, -1408
        .short  -1089, -770, -452, -133, 185, 504, 823, 1141, 1460, 1779, 2097, 2416, 2734, 3054, 3371, 3691
        .short  4026, 4133, 4221, 4347, 4501, 4670, 4852, 5038, 5232, 5427, 5628, 5827, 6031, 6234, 6441, 6646
        .short  6856, 7063, 7275, 7484, 7698, 7909, 8125, 8339, 8557, 8772, 8992, 9209, 9431, 9650, 9874, 10094
        .short  10321, 10543, 10771, 10994, 11225, 11450, 11683, 11909, 12144, 12371, 12609, 12836, 13077, 13304, 13550, 13772
        .short  14031, 14233, 14548, 13733, 9647, 4579, 673, -2402, -4957, -7124, -8975, -10542, -11846, -12898, -13711, -14299
        .short  -14685, -14892, -14953, -14896, -14751, -14543, -14291, -14012, -13716, -13409, -13097, -12781, -12464, -12147, -11828, -11510
        .short  -11191, -10873, -10554, -10236, -9917, -9599, -9280, -8962, -8643, -8325, -8006, -7688, -7368, -7050, -6731, -6413
        .short  -6094, -5776, -5457, -5139, -4820, -4502, -4183, -3865, -3546, -3228, -2909, -2591, -2271, -1954, -1634, -1316
        .short  -997, -679, -360, -42, 277, 595, 914, 1232, 1551, 1869, 2188, 2506, 2825, 3144, 3462, 3781
        .short  4143, 4262, 4357, 4491, 4649, 4826, 5011, 5205, 5403, 5606, 5810, 6018, 6226, 6436, 6647, 6860
        .short  7073, 7288, 7503, 7721, 7938, 8157, 8375, 8596, 8817, 9039, 9262, 9486, 9711, 9936, 10163, 10390
        .short  10618, 10847, 11077, 11307, 11539, 11771, 12004, 12238, 12473, 12708, 12944, 13181, 13419, 13657, 13896, 14137
        .short  14372, 14637, 14523, 11485, 6317, 1966, -1371, -4111, -6421, -8387, -10060, -11458, -12604, -13501, -14172, -14630
        .short  -14905, -15019, -15008, -14894, -14712, -14476, -14209, -13918, -13617, -13305, -12993, -12675, -12359, -12039, -11722, -11402
        .short  -11085, -10765, -10448, -10127, -9810, -9490, -9173, -8853, -8535, -8215, -7898, -7578, -7260, -6941, -6623, -6303
        .short  -5986, -5666, -5348, -5028, -4711, -4391, -4074, -3754, -3436, -3116, -2799, -2479, -2161, -1841, -1524, -1204
        .short  -887, -567, -249, 71, 388, 708, 1026, 1346, 1663, 1983, 2300, 2620, 2938, 3258, 3574, 3896
        .short  4284, 4412, 4518, 4659, 4823, 5004, 5195, 5394, 5598, 5806, 6016, 6229, 6443, 6659, 6875, 7094
        .short  7312, 7533, 7753, 7976, 8198, 8422, 8646, 8872, 9097, 9325, 9552, 9782, 10010, 10241, 10470, 10704
        .short  10934, 11170, 11401, 11639, 11871, 12111, 12344, 12586, 12819, 13064, 13297, 13545, 13777, 14030, 14258, 14520
        .short  14740, 14943, 12871, 7911, 3170, -428, -3347, -5791, -7863, -9631, -11112, -12338, -13309, -14053, -14575, -14910
        .short  -15073, -15104, -15023, -14866, -14646, -14391, -14107, -13811, -13502, -13191, -12873, -12557, -12237, -11920, -11600, -11282
        .short  -10962, -10644, -10324, -10006, -9686, -9368, -9048, -8730, -8410, -8092, -7772, -7454, -7134, -6816, -6496, -6178
        .short  -5858, -5540, -5220, -4902, -4582, -4264, -3944, -3626, -3306, -2988, -2668, -2349, -2030, -1711, -1392, -1073
        .short  -754, -435, -116, 203, 522, 841, 1160, 1479, 1798, 2117, 2436, 2755, 3074, 3394, 3711, 4032
        .short  4450, 4587, 4703, 4849, 5020, 5205, 5402, 5605, 5815, 6027, 6244, 6460, 6681, 6901, 7125, 7347
        .short  7573, 7797, 8024, 8250, 8479, 8706, 8938, 9166, 9399, 9628, 9863, 10094, 10330, 10562, 10800, 11034
        .short  11273, 11507, 11749, 11984, 12228, 12463, 12709, 12945, 13194, 13429, 13681, 13915, 14173, 14400, 14671, 14878
        .short  15183, 13840, 9267, 4249, 401, -2682, -5247, -7417, -9265, -10820, -12112, -13148, -13951, -14530, -14915, -15124
        .short  -15192, -15142, -15007, -14805, -14561, -14285, -13993, -13687, -13376, -13060, -12743, -12424, -12106, -11786, -11467, -11147
        .short  -10828, -10507, -10188, -9868, -9549, -9229, -8910, -8590, -8271, -7951, -7632, -7312, -6992, -6673, -6353, -6033
        .short  -5714, -5394, -5075, -4755, -4436, -4116, -3796, -3477, -3157, -2838, -2518, -2199, -1879, -1559, -1240, -920
        .short  -600, -281, 39, 358, 678, 997, 1317, 1636, 1956, 2276, 2596, 2915, 3235, 3554, 3873, 4194
        .short  4641, 4789, 4912, 5067, 5242, 5434, 5634, 5843, 6056, 6275, 6495, 6719, 6943, 7171, 7397, 7627
        .short  7855, 8087, 8317, 8550, 8782, 9017, 9249, 9486, 9720, 9959, 10193, 10434, 10669, 10911, 11148, 11391
        .short  11629, 11874, 12113, 12360, 12599, 12848, 13087, 13338, 13578, 13832, 14070, 14329, 14562, 14833, 15046, 15370
        .short  14492, 10302, 5121, 1064, -2156, -4824, -7074, -8987, -10602, -11945, -13032, -13881, -14506, -14931, -15177, -15276
        .short  -15253, -15137, -14951, -14717, -14449, -14160, -13858, -13547, -13232, -12915, -12596, -12276, -11956, -11636, -11316, -10995
        .short  -10675, -10355, -10035, -9714, -9394, -9073, -8753, -8433, -8113, -7792, -7472, -7151, -6831, -6511, -6191, -5870
        .short  -5550, -5229, -4910, -4589, -4269, -3948, -3628, -3307, -2988, -2666, -2347, -2026, -1706, -1385, -1066, -744
        .short  -425, -104, 216, 537, 856, 1178, 1497, 1818, 2137, 2459, 2778, 3100, 3419, 3741, 4059, 4382
        .short  4861, 5015, 5149, 5308, 5490, 5685, 5892, 6104, 6324, 6545, 6772, 6999, 7230, 7460, 7694, 7927
        .short  8163, 8397, 8635, 8870, 9110, 9346, 9587, 9825, 10068, 10307, 10551, 10791, 11036, 11277, 11524, 11766
        .short  12014, 12257, 12506, 12750, 13001, 13246, 13499, 13743, 13999, 14242, 14502, 14741, 15010, 15233, 15554, 14933
        .short  11032, 5772, 1558, -1769, -4519, -6833, -8798, -10457, -11841, -12965, -13849, -14508, -14964, -15240, -15363, -15362
        .short  -15262, -15090, -14865, -14604, -14319, -14019, -13709, -13395, -13076, -12757, -12436, -12116, -11794, -11474, -11152, -10831
        .short  -10509, -10188, -9866, -9545, -9223, -8903, -8581, -8260, -7938, -7617, -7295, -6974, -6652, -6332, -6010, -5689
        .short  -5367, -5046, -4724, -4404, -4081, -3761, -3439, -3118, -2796, -2475, -2153, -1833, -1510, -1190, -868, -547
        .short  -225, 96, 418, 738, 1061, 1381, 1703, 2024, 2346, 2667, 2989, 3309, 3631, 3952, 4274, 4595
        .short  5105, 5271, 5412, 5581, 5766, 5968, 6178, 6397, 6619, 6848, 7077, 7311, 7545, 7782, 8019, 8259
        .short  8497, 8739, 8978, 9222, 9463, 9708, 9950, 10196, 10440, 10687, 10932, 11181, 11426, 11676, 11922, 12174
        .short  12421, 12674, 12921, 13176, 13424, 13680, 13928, 14186, 14434, 14696, 14940, 15211, 15439, 15760, 15220, 11409
        .short  6107, 1813, -1577, -4378, -6732, -8728, -10414, -11819, -12965, -13869, -14548, -15022, -15316, -15456, -15469, -15382
        .short  -15219, -15001, -14745, -14463, -14165, -13855, -13541, -13222, -12902, -12580, -12259, -11936, -11614, -11291, -10969, -10646
        .short  -10324, -10001, -9679, -9356, -9034, -8710, -8389, -8065, -7744, -7420, -7099, -6775, -6453, -6130, -5808, -5485
        .short  -5163, -4840, -4518, -4194, -3873, -3549, -3228, -2904, -2583, -2259, -1938, -1614, -1292, -969, -647, -324
        .short  -2, 322, 643, 967, 1288, 1612, 1933, 2257, 2578, 2902, 3223, 3547, 3868, 4193, 4513, 4838
        .short  5383, 5555, 5706, 5879, 6072, 6276, 6493, 6714, 6943, 7174, 7410, 7646, 7888, 8127, 8371, 8613
        .short  8859, 9103, 9351, 9596, 9845, 10092, 10342, 10590, 10841, 11090, 11343, 11592, 11846, 12096, 12352, 12603
        .short  12860, 13111, 13369, 13621, 13881, 14133, 14395, 14645, 14912, 15159, 15434, 15664, 15990, 15385, 11485, 6165
        .short  1857, -1559, -4382, -6754, -8765, -10461, -11875, -13028, -13939, -14626, -15109, -15412, -15560, -15582, -15502, -15346
        .short  -15132, -14880, -14599, -14302, -13993, -13678, -13358, -13037, -12714, -12391, -12067, -11744, -11419, -11096, -10771, -10447
        .short  -10123, -9799, -9474, -9151, -8826, -8503, -8178, -7855, -7530, -7207, -6882, -6558, -6233, -5910, -5585, -5262
        .short  -4937, -4614, -4289, -3966, -3641, -3317, -2992, -2669, -2344, -2021, -1696, -1373, -1048, -725, -400, -77
        .short  248, 572, 897, 1220, 1545, 1868, 2193, 2516, 2841, 3164, 3489, 3813, 4137, 4461, 4785, 5109
        .short  5688, 5872, 6030, 6212, 6408, 6620, 6839, 7067, 7298, 7536, 7775, 8019, 8261, 8509, 8754, 9005
        .short  9252, 9504, 9753, 10007, 10257, 10512, 10763, 11020, 11272, 11529, 11782, 12041, 12294, 12555, 12809, 13070
        .short  13325, 13588, 13842, 14107, 14361, 14629, 14881, 15154, 15401, 15684, 15911, 16248, 15391, 11183, 5870, 1626
        .short  -1767, -4577, -6939, -8940, -10625, -12029, -13171, -14073, -14752, -15230, -15529, -15677, -15698, -15620, -15464, -15253
        .short  -15001, -14721, -14423, -14114, -13798, -13478, -13155, -12830, -12506, -12180, -11855, -11529, -11203, -10877, -10552, -10226
        .short  -9900, -9574, -9249, -8923, -8597, -8271, -7946, -7619, -7294, -6968, -6643, -6316, -5991, -5665, -5339, -5013
        .short  -4688, -4361, -4036, -3710, -3385, -3058, -2733, -2407, -2082, -1755, -1430, -1104, -779, -452, -127, 200
        .short  524, 851, 1176, 1503, 1827, 2154, 2479, 2806, 3130, 3458, 3782, 4109, 4433, 4761, 5085, 5413
        .short  6028, 6218, 6387, 6574, 6778, 6993, 7219, 7449, 7687, 7927, 8173, 8418, 8669, 8918, 9172, 9423
        .short  9679, 9932, 10190, 10445, 10704, 10959, 11220, 11476, 11738, 11995, 12258, 12516, 12780, 13038, 13304, 13562
        .short  13830, 14088, 14358, 14614, 14887, 15142, 15420, 15668, 15959, 16187, 16510, 15181, 10540, 5299, 1170, -2164
        .short  -4933, -7262, -9235, -10891, -12270, -13385, -14265, -14922, -15385, -15670, -15809, -15823, -15741, -15582, -15369, -15115
        .short  -14835, -14535, -14226, -13907, -13586, -13260, -12935, -12608, -12281, -11953, -11626, -11297, -10970, -10642, -10315, -9986
        .short  -9659, -9331, -9003, -8675, -8348, -8020, -7692, -7364, -7037, -6709, -6381, -6053, -5726, -5398, -5070, -4742
        .short  -4414, -4087, -3759, -3431, -3103, -2776, -2448, -2120, -1792, -1465, -1137, -809, -481, -154, 174, 502
        .short  830, 1157, 1486, 1813, 2141, 2468, 2797, 3124, 3452, 3779, 4108, 4435, 4763, 5091, 5418, 5746
        .short  6400, 6599, 6775, 6970, 7178, 7400, 7628, 7865, 8106, 8353, 8601, 8853, 9106, 9362, 9618, 9877
        .short  10135, 10397, 10656, 10919, 11179, 11443, 11705, 11970, 12232, 12499, 12761, 13030, 13292, 13562, 13825, 14096
        .short  14359, 14632, 14894, 15170, 15430, 15710, 15966, 16255, 16500, 16733, 14684, 9579, 4490, 506, -2742, -5448
        .short  -7724, -9650, -11260, -12597, -13671, -14515, -15139, -15574, -15835, -15957, -15957, -15866, -15699, -15482, -15223, -14941
        .short  -14639, -14327, -14006, -13683, -13355, -13028, -12698, -12370, -12038, -11710, -11379, -11050, -10719, -10390, -10058, -9729
        .short  -9398, -9069, -8738, -8409, -8078, -7749, -7418, -7089, -6758, -6429, -6098, -5769, -5438, -5108, -4778, -4448
        .short  -4118, -3788, -3458, -3128, -2798, -2468, -2137, -1808, -1477, -1148, -817, -487, -157, 173, 503, 833
        .short  1163, 1493, 1823, 2153, 2483, 2813, 3143, 3473, 3803, 4134, 4463, 4794, 5123, 5454, 5783, 6114
        .short  6804, 7012, 7197, 7399, 7614, 7840, 8074, 8316, 8562, 8812, 9066, 9322, 9580, 9841, 10102, 10365
        .short  10629, 10894, 11159, 11426, 11693, 11960, 12228, 12497, 12766, 13035, 13305, 13575, 13846, 14116, 14388, 14659
        .short  14932, 15203, 15477, 15749, 16024, 16297, 16569, 16863, 16803, 13768, 8306, 3452, -372, -3512, -6132, -8336
        .short  -10194, -11742, -13017, -14035, -14826, -15402, -15796, -16024, -16118, -16097, -15990, -15811, -15586, -15321, -15034, -14728
        .short  -14414, -14090, -13764, -13434, -13104, -12771, -12441, -12107, -11776, -11442, -11111, -10777, -10446, -10112, -9781, -9447
        .short  -9116, -8782, -8451, -8117, -7786, -7452, -7121, -6787, -6456, -6122, -5790, -5457, -5125, -4792, -4460, -4127
        .short  -3795, -3462, -3130, -2797, -2465, -2132, -1800, -1466, -1135, -801, -470, -136, 195, 529, 860, 1194
        .short  1525, 1859, 2190, 2524, 2855, 3189, 3521, 3854, 4186, 4519, 4851, 5184, 5516, 5849, 6180, 6515
        .short  7241, 7455, 7650, 7857, 8079, 8309, 8550, 8794, 9047, 9300, 9560, 9820, 10085, 10348, 10616, 10882
        .short  11153, 11421, 11693, 11962, 12236, 12507, 12782, 13053, 13329, 13601, 13879, 14150, 14429, 14701, 14982, 15254
        .short  15536, 15806, 16093, 16359, 16654, 16902, 17250, 16612, 12532, 6921, 2307, -1374, -4406, -6935, -9058, -10836
        .short  -12311, -13511, -14462, -15186, -15707, -16049, -16237, -16295, -16248, -16119, -15927, -15689, -15417, -15123, -14813, -14494
        .short  -14168, -13838, -13505, -13172, -12837, -12503, -12168, -11833, -11497, -11162, -10827, -10492, -10156, -9821, -9485, -9151
        .short  -8815, -8480, -8144, -7809, -7473, -7139, -6803, -6468, -6132, -5798, -5461, -5127, -4791, -4456, -4120, -3786
        .short  -3450, -3115, -2779, -2444, -2108, -1774, -1438, -1103, -767, -433, -96, 238, 574, 909, 1245, 1579
        .short  1916, 2250, 2586, 2920, 3257, 3591, 3927, 4262, 4598, 4932, 5269, 5603, 5939, 6274, 6610, 6944
        .short  7701, 7926, 8126, 8344, 8569, 8808, 9050, 9304, 9557, 9819, 10080, 10348, 10615, 10885, 11157, 11428
        .short  11704, 11976, 12255, 12527, 12808, 13081, 13364, 13637, 13921, 14196, 14479, 14757, 15038, 15320, 15598, 15885
        .short  16158, 16453, 16716, 17027, 17266, 17608, 16112, 11116, 5506, 1088, -2486, -5409, -7856, -9884, -11581, -12962
        .short  -14083, -14947, -15599, -16048, -16332, -16468, -16486, -16407, -16252, -16043, -15789, -15510, -15205, -14893, -14565, -14238
        .short  -13902, -13569, -13231, -12895, -12556, -12218, -11880, -11541, -11204, -10864, -10528, -10188, -9852, -9511, -9175, -8835
        .short  -8498, -8159, -7821, -7483, -7144, -6807, -6467, -6130, -5791, -5454, -5114, -4778, -4438, -4101, -3761, -3424
        .short  -3085, -2747, -2409, -2070, -1733, -1393, -1056, -717, -380, -40, 296, 636, 973, 1313, 1650, 1989
        .short  2327, 2665, 3004, 3341, 3681, 4017, 4357, 4694, 5034, 5370, 5710, 6047, 6386, 6724, 7062, 7401
        .short  8181, 8410, 8624, 8844, 9081, 9322, 9572, 9830, 10088, 10356, 10620, 10895, 11164, 11442, 11716, 11994
        .short  12274, 12550, 12836, 13111, 13400, 13676, 13963, 14245, 14528, 14816, 15093, 15389, 15661, 15962, 16233, 16533
        .short  16810, 17100, 17392, 17667, 17871, 15444, 9759, 4181, -136, -3646, -6484, -8859, -10794, -12403, -13687, -14711
        .short  -15487, -16047, -16426, -16634, -16721, -16685, -16576, -16389, -16160, -15892, -15597, -15290, -14964, -14639, -14300, -13967
        .short  -13625, -13287, -12946, -12604, -12265, -11921, -11583, -11238, -10900, -10557, -10216, -9875, -9532, -9193, -8849, -8511
        .short  -8167, -7827, -7485, -7144, -6803, -6460, -6121, -5777, -5439, -5095, -4755, -4413, -4071, -3732, -3388, -3049
        .short  -2705, -2366, -2023, -1683, -1341, -999, -660, -316, 23, 367, 706, 1049, 1389, 1730, 2073, 2412
        .short  2756, 3095, 3439, 3778, 4121, 4462, 4802, 5145, 5484, 5828, 6167, 6511, 6850, 7193, 7533, 7874
        .short  8662, 8906, 9123, 9353, 9597, 9840, 10102, 10358, 10626, 10897, 11165, 11447, 11717, 12003, 12281, 12563
        .short  12852, 13127, 13423, 13700, 13992, 14280, 14561, 14862, 15136, 15440, 15719, 16011, 16311, 16581, 16903, 17157
        .short  17487, 17743, 18073, 18094, 14949, 8754, 3077, -1256, -4780, -7573, -9898, -11756, -13268, -14468, -15375, -16068
        .short  -16523, -16825, -16962, -16980, -16908, -16744, -16543, -16281, -16001, -15696, -15372, -15050, -14708, -14375, -14030, -13688
        .short  -13348, -12998, -12661, -12311, -11970, -11625, -11278, -10938, -10588, -10249, -9901, -9557, -9215, -8866, -8527, -8178
        .short  -7837, -7491, -7145, -6804, -6455, -6115, -5767, -5424, -5081, -4733, -4393, -4044, -3703, -3357, -3012, -2670
        .short  -2322, -1982, -1633, -1291, -947, -600, -259, 90, 430, 777, 1122, 1464, 1812, 2152, 2500, 2843
        .short  3187, 3534, 3874, 4224, 4564, 4911, 5255, 5597, 5946, 6285, 6635, 6976, 7321, 7668, 8007, 8358
        .short  9138, 9395, 9612, 9857, 10103, 10353, 10624, 10880, 11157, 11432, 11702, 11994, 12265, 12555, 12844, 13120
        .short  13424, 13700, 13996, 14292, 14569, 14881, 15158, 15455, 15760, 16030, 16355, 16626, 16926, 17243, 17490, 17855
        .short  18075, 18451, 18400, 14907, 8270, 2261, -2211, -5842, -8647, -10931, -12753, -14150, -15275, -16069, -16651, -17032
        .short  -17220, -17306, -17249, -17124, -16938, -16683, -16421, -16111, -15795, -15474, -15127, -14797, -14448, -14102, -13763, -13406
        .short  -13068, -12717, -12367, -12027, -11671, -11330, -10980, -10630, -10289, -9934, -9592, -9244, -8892, -8552, -8197, -7854
        .short  -7507, -7154, -6814, -6460, -6116, -5770, -5417, -5076, -4723, -4378, -4033, -3679, -3338, -2987, -2640, -2296
        .short  -1942, -1601, -1250, -902, -559, -205, 137, 487, 836, 1179, 1533, 1875, 2224, 2574, 2916, 3270
        .short  3613, 3961, 4312, 4653, 5007, 5351, 5698, 6050, 6390, 6744, 7089, 7434, 7788, 8128, 8481, 8828
        .short  9590, 9852, 10074, 10332, 10581, 10834, 11116, 11373, 11653, 11941, 12206, 12506, 12790, 13067, 13378, 13653
        .short  13948, 14258, 14528, 14843, 15138, 15415, 15745, 16018, 16316, 16646, 16897, 17236, 17535, 17783, 18178, 18376
        .short  18749, 18897, 15715, 8804, 2071, -2774, -6625, -9596, -11849, -13689, -15019, -16027, -16776, -17219, -17522, -17648
        .short  -17622, -17547, -17357, -17124, -16874, -16557, -16253, -15929, -15577, -15252, -14898, -14546, -14212, -13848, -13504, -13159
        .short  -12796, -12458, -12104, -11747, -11409, -11048, -10700, -10356, -9994, -9653, -9301, -8944, -8605, -8246, -7896, -7553
        .short  -7192, -6849, -6499, -6141, -5801, -5444, -5092, -4750, -4390, -4045, -3697, -3338, -2997, -2642, -2288, -1947
        .short  -1587, -1241, -894, -535, -193, 160, 515, 857, 1215, 1564, 1908, 2268, 2611, 2963, 3319, 3660
        .short  4017, 4368, 4711, 5071, 5415, 5765, 6123, 6463, 6820, 7172, 7513, 7874, 8220, 8566, 8927, 9267
        .short  10005, 10274, 10498, 10768, 11026, 11276, 11570, 11837, 12105, 12414, 12685, 12967, 13284, 13554, 13849, 14171
        .short  14437, 14745, 15068, 15328, 15652, 15970, 16224, 16569, 16875, 17122, 17497, 17775, 18021, 18450, 18643, 18949
        .short  19417, 17116, 10386, 2665, -2954, -7075, -10368, -12696, -14485, -15868, -16746, -17394, -17816, -17963, -18033, -17980
        .short  -17789, -17600, -17342, -17022, -16737, -16403, -16046, -15730, -15370, -15010, -14683, -14315, -13958, -13625, -13254, -12904
        .short  -12566, -12194, -11848, -11505, -11134, -10792, -10444, -10075, -9736, -9383, -9017, -8679, -8322, -7959, -7621, -7261
        .short  -6902, -6563, -6200, -5845, -5505, -5139, -4788, -4445, -4079, -3731, -3386, -3019, -2674, -2325, -1960, -1618
        .short  -1265, -901, -561, -204, 157, 497, 857, 1215, 1555, 1917, 2273, 2613, 2978, 3330, 3672, 4039
        .short  4386, 4731, 5099, 5443, 5791, 6159, 6499, 6852, 7218, 7556, 7913, 8276, 8613, 8974, 9334, 9670
        .short  10342, 10638, 10886, 11122, 11413, 11683, 11935, 12243, 12527, 12787, 13108, 13401, 13665, 13995, 14295, 14558
        .short  14897, 15201, 15460, 15810, 16117, 16368, 16731, 17040, 17275, 17662, 17969, 18173, 18615, 18896, 19035, 19704
        .short  18902, 13450, 4925, -2218, -6958, -10620, -13335, -15112, -16495, -17446, -17939, -18294, -18454, -18376, -18284, -18113
        .short  -17815, -17553, -17263, -16894, -16577, -16251, -15866, -15532, -15196, -14810, -14471, -14132, -13748, -13406, -13065, -12684
        .short  -12340, -11999, -11619, -11275, -10933, -10555, -10209, -9867, -9490, -9144, -8801, -8425, -8078, -7736, -7361, -7013
        .short  -6670, -6296, -5947, -5604, -5231, -4882, -4539, -4166, -3816, -3473, -3101, -2751, -2408, -2035, -1685, -1343
        .short  -970, -619, -277, 95, 446, 788, 1160, 1512, 1853, 2225, 2577, 2918, 3291, 3643, 3983, 4356
        .short  4709, 5048, 5421, 5775, 6113, 6487, 6840, 7178, 7552, 7906, 8243, 8618, 8973, 9307, 9684, 10039
        .short  10643, 10937, 11220, 11450, 11722, 12035, 12290, 12556, 12889, 13170, 13426, 13765, 14075, 14323, 14655, 14995
        .short  15239, 15552, 15923, 16173, 16453, 16852, 17123, 17358, 17779, 18091, 18259, 18702, 19090, 19120, 19664, 20071
        .short  16876, 8873, -66, -6322, -10361, -13528, -15694, -16951, -17912, -18536, -18706, -18779, -18797, -18578, -18316, -18112
        .short  -17786, -17413, -17128, -16791, -16389, -16065, -15739, -15337, -14988, -14670, -14280, -13911, -13594, -13221, -12838, -12515
        .short  -12159, -11769, -11435, -11094, -10704, -10355, -10024, -9642, -9278, -8951, -8580, -8205, -7875, -7517, -7134, -6797
        .short  -6451, -6067, -5720, -5383, -5003, -4643, -4311, -3940, -3568, -3237, -2876, -2497, -2160, -1811, -1429, -1083
        .short  -743, -364, -6, 327, 700, 1069, 1401, 1764, 2142, 2477, 2828, 3211, 3555, 3894, 4277, 4632
        .short  4964, 5340, 5708, 6037, 6403, 6782, 7113, 7466, 7852, 8192, 8530, 8919, 9271, 9598, 9982, 10350
        .short  10925, 11173, 11422, 11739, 12007, 12243, 12565, 12884, 13122, 13418, 13775, 14043, 14300, 14667, 14987, 15217
        .short  15554, 15934, 16171, 16444, 16863, 17156, 17354, 17763, 18158, 18299, 18625, 19170, 19291, 19417, 20291, 19780
        .short  14417, 4937, -3912, -9465, -12968, -15696, -17397, -18212, -18823, -19207, -19155, -19011, -18933, -18667, -18287, -18027
        .short  -17741, -17322, -16968, -16685, -16296, -15893, -15590, -15247, -14832, -14490, -14177, -13780, -13400, -13090, -12728, -12326
        .short  -11995, -11664, -11266, -10903, -10586, -10211, -9822, -9496, -9151, -8755, -8404, -8079, -7696, -7319, -6995, -6637
        .short  -6246, -5905, -5571, -5183, -4817, -4492, -4124, -3739, -3405, -3061, -2671, -2316, -1988, -1610, -1233, -904
        .short  -550, -160, 185, 518, 903, 1271, 1597, 1962, 2349, 2685, 3026, 3416, 3774, 4100, 4475, 4857
        .short  5185, 5535, 5929, 6275, 6604, 6990, 7363, 7684, 8047, 8441, 8774, 9109, 9505, 9866, 10184, 10561
        .short  11048, 11397, 11671, 11884, 12186, 12531, 12779, 13025, 13383, 13712, 13937, 14237, 14627, 14908, 15133, 15504
        .short  15886, 16104, 16372, 16811, 17130, 17297, 17667, 18142, 18324, 18499, 19060, 19455, 19372, 19833, 20763, 18975
        .short  11766, 1410, -7151, -12060, -15017, -17309, -18633, -19063, -19348, -19578, -19417, -19085, -18912, -18688, -18257, -17883
        .short  -17639, -17282, -16835, -16512, -16226, -15812, -15406, -15114, -14776, -14348, -13993, -13698, -13314, -12903, -12585, -12261
        .short  -11852, -11476, -11171, -10810, -10400, -10061, -9744, -9352, -8963, -8646, -8302, -7897, -7540, -7225, -6850, -6453
        .short  -6123, -5791, -5395, -5022, -4704, -4345, -3945, -3601, -3277, -2892, -2507, -2183, -1838, -1439, -1080, -761
        .short  -388, 6, 339, 672, 1065, 1439, 1758, 2116, 2515, 2861, 3184, 3569, 3956, 4279, 4622, 5023
        .short  5383, 5699, 6071, 6470, 6802, 7129, 7527, 7905, 8217, 8573, 8981, 9327, 9638, 10027, 10426, 10739
        .short  11251, 11476, 11754, 12109, 12383, 12595, 12915, 13292, 13551, 13774, 14136, 14520, 14753, 14991, 15397, 15774
        .short  15971, 16233, 16690, 17044, 17189, 17495, 18021, 18314, 18380, 18788, 19424, 19537, 19452, 20290, 21018, 18029
        .short  9526, -1330, -9681, -14097, -16511, -18395, -19482, -19639, -19605, -19717, -19582, -19134, -18797, -18625, -18282, -17794
        .short  -17459, -17222, -16828, -16367, -16056, -15783, -15367, -14936, -14640, -14338, -13911, -13508, -13218, -12890, -12460, -12082
        .short  -11792, -11440, -11013, -10656, -10361, -9990, -9570, -9231, -8927, -8540, -8131, -7806, -7489, -7090, -6695, -6379
        .short  -6049, -5642, -5261, -4952, -4606, -4195, -3830, -3522, -3161, -2751, -2401, -2090, -1714, -1308, -972, -656
        .short  -266, 131, 455, 781, 1182, 1568, 1883, 2221, 2629, 3002, 3311, 3664, 4076, 4434, 4740, 5109
        .short  5521, 5863, 6171, 6557, 6965, 7289, 7604, 8006, 8405, 8714, 9041, 9457, 9842, 10137, 10482, 10909
        .short  11250, 11642, 11930, 12117, 12398, 12794, 13106, 13298, 13580, 14000, 14336, 14521, 14796, 15242, 15601, 15770
        .short  16029, 16508, 16897, 17032, 17262, 17795, 18229, 18294, 18469, 19118, 19634, 19492, 19559, 20698, 21160, 17338
        .short  8085, -3110, -11499, -15659, -17558, -19028, -20016, -20083, -19752, -19669, -19641, -19256, -18727, -18444, -18266, -17863
        .short  -17351, -17029, -16810, -16423, -15935, -15596, -15355, -14982, -14512, -14160, -13904, -13541, -13084, -12724, -12456, -12102
        .short  -11655, -11287, -11010, -10662, -10224, -9849, -9565, -9223, -8792, -8411, -8120, -7784, -7359, -6974, -6677, -6346
        .short  -5926, -5536, -5234, -4907, -4492, -4098, -3791, -3468, -3058, -2660, -2348, -2030, -1624, -1222, -906, -591
        .short  -190, 216, 537, 847, 1244, 1655, 1979, 2286, 2678, 3093, 3422, 3724, 4112, 4531, 4865, 5163
        .short  5545, 5969, 6308, 6601, 6979, 7407, 7752, 8040, 8411, 8845, 9197, 9478, 9842, 10283, 10644, 10916
        .short  11401, 11598, 11861, 12257, 12604, 12800, 13019, 13410, 13826, 14065, 14238, 14590, 15062, 15372, 15510, 15789
        .short  16295, 16704, 16832, 17001, 17507, 18053, 18208, 18217, 18674, 19432, 19675, 19375, 19710, 21082, 21238, 16794
        .short  7098, -4318, -12857, -16936, -18375, -19364, -20263, -20432, -19942, -19547, -19506, -19355, -18832, -18292, -18052, -17884
        .short  -17466, -16925, -16579, -16387, -16053, -15547, -15130, -14893, -14615, -14161, -13703, -13410, -13158, -12761, -12292, -11941
        .short  -11689, -11346, -10888, -10490, -10215, -9913, -9486, -9055, -8744, -8466, -8078, -7633, -7281, -7006, -6660, -6221
        .short  -5829, -5540, -5230, -4813, -4392, -4073, -3785, -3402, -2967, -2612, -2329, -1983, -1551, -1160, -866, -554
        .short  -141, 279, 599, 889, 1271, 1706, 2061, 2343, 2688, 3122, 3514, 3807, 4116, 4532, 4955, 5274
        .short  5557, 5940, 6383, 6739, 7012, 7354, 7798, 8196, 8478, 8778, 9204, 9641, 9950, 10216, 10607, 11069
        .short  11290, 11576, 11989, 12346, 12539, 12734, 13111, 13556, 13833, 13982, 14270, 14749, 15149, 15313, 15482, 15918
        .short  16444, 16705, 16771, 17070, 17682, 18133, 18157, 18220, 18826, 19585, 19684, 19330, 19787, 21278, 21399, 16810
        .short  6917, -4791, -13654, -17822, -18979, -19581, -20351, -20617, -20118, -19521, -19357, -19325, -18936, -18308, -17902, -17767
        .short  -17522, -16999, -16487, -16228, -16039, -15643, -15117, -14737, -14526, -14235, -13759, -13298, -13015, -12777, -12386, -11902
        .short  -11532, -11288, -10978, -10524, -10087, -9793, -9530, -9141, -8678, -8314, -8053, -7732, -7290, -6866, -6566, -6290
        .short  -5901, -5451, -5090, -4820, -4493, -4056, -3640, -3338, -3055, -2665, -2220, -1862, -1589, -1258, -822, -409
        .short  -108, 177, 569, 1013, 1369, 1641, 1974, 2412, 2824, 3122, 3406, 3802, 4249, 4601, 4869, 5203
        .short  5648, 6061, 6352, 6631, 7034, 7489, 7837, 8093, 8428, 8885, 9304, 9581, 9850, 10263, 10737, 11077
        .short  11402, 11770, 11943, 12111, 12472, 12944, 13277, 13419, 13610, 14035, 14538, 14835, 14935, 15153, 15655, 16187
        .short  16421, 16456, 16717, 17334, 17894, 18006, 17931, 18288, 19128, 19707, 19496, 19170, 19933, 21565, 21552, 16898
        .short  7146, -4590, -13917, -18581, -19660, -19699, -20131, -20628, -20448, -19702, -19126, -19032, -19003, -18587, -17921, -17466
        .short  -17331, -17169, -16708, -16122, -15741, -15580, -15341, -14861, -14331, -13997, -13811, -13518, -13031, -12544, -12241, -12033
        .short  -11699, -11210, -10761, -10479, -10248, -9881, -9396, -8979, -8712, -8458, -8065, -7587, -7200, -6942, -6665, -6250
        .short  -5783, -5422, -5168, -4868, -4437, -3982, -3645, -3392, -3068, -2624, -2184, -1869, -1613, -1266, -812, -390
        .short  -94, 168, 538, 999, 1401, 1680, 1952, 2346, 2809, 3189, 3453, 3739, 4155, 4618, 4974, 5225
        .short  5529, 5967, 6425, 6755, 6997, 7322, 7782, 8230, 8532, 8768, 9119, 9600, 10033, 10305, 10541, 10919
        .short  11438, 11605, 11782, 12156, 12638, 12980, 13119, 13283, 13681, 14208, 14568, 14682, 14819, 15243, 15830, 16210
        .short  16272, 16359, 16822, 17508, 17912, 17865, 17849, 18398, 19298, 19730, 19373, 19092, 20017, 21734, 21702, 17054
        .short  7350, -4472, -14117, -19110, -20191, -19884, -19992, -20506, -20561, -19891, -19107, -18803, -18847, -18675, -18081, -17426
        .short  -17105, -17032, -16808, -16273, -15688, -15358, -15224, -14974, -14474, -13931, -13594, -13422, -13157, -12680, -12162, -11820
        .short  -11623, -11349, -10888, -10388, -10041, -9827, -9547, -9098, -8609, -8259, -8032, -7748, -7308, -6827, -6474, -6239
        .short  -5952, -5519, -5044, -4688, -4446, -4159, -3730, -3258, -2900, -2654, -2367, -1941, -1471, -1111, -863, -576
        .short  -154, 317, 680, 928, 1212, 1634, 2106, 2471, 2719, 3000, 3421, 3896, 4264, 4509, 4786, 5207
        .short  5688, 6059, 6299, 6569, 6992, 7481, 7855, 8089, 8351, 8776, 9277, 9654, 9877, 10129, 10561, 11074
        .short  11080, 11546, 12034, 12332, 12438, 12586, 12973, 13520, 13948, 14107, 14169, 14442, 15000, 15571, 15841, 15843
        .short  15951, 16451, 17169, 17632, 17621, 17496, 17830, 18709, 19512, 19565, 19026, 18948, 20168, 21964, 21944, 17618
        .short  8521, -2999, -13148, -19164, -20909, -20376, -19783, -19989, -20443, -20321, -19535, -18703, -18370, -18436, -18372, -17867
        .short  -17142, -16638, -16498, -16438, -16112, -15508, -14933, -14634, -14523, -14304, -13824, -13243, -12825, -12631, -12460, -12094
        .short  -11554, -11061, -10771, -10596, -10320, -9851, -9328, -8946, -8730, -8509, -8123, -7611, -7159, -6876, -6671, -6363
        .short  -5896, -5403, -5045, -4820, -4570, -4169, -3671, -3243, -2969, -2749, -2419, -1949, -1473, -1133, -907, -640
        .short  -224, 271, 680, 942, 1170, 1517, 1997, 2463, 2786, 3005, 3284, 3718, 4216, 4611, 4855, 5082
        .short  5448, 5945, 6408, 6708, 6911, 7199, 7659, 8171, 8550, 8765, 8982, 9371, 9900, 10367, 10636, 10802
        .short  11239, 11722, 11973, 12053, 12212, 12624, 13187, 13624, 13786, 13828, 14055, 14588, 15205, 15571, 15610, 15617
        .short  15958, 16653, 17311, 17531, 17373, 17359, 17930, 18905, 19568, 19413, 18823, 18884, 20263, 22107, 22103, 17932
        .short  9122, -2239, -12606, -19150, -21335, -20806, -19830, -19680, -20155, -20364, -19828, -18886, -18217, -18103, -18213, -18035
        .short  -17417, -16686, -16246, -16156, -16101, -15760, -15141, -14546, -14226, -14123, -13952, -13519, -12923, -12430, -12181, -12048
        .short  -11784, -11297, -10738, -10329, -10120, -9944, -9605, -9090, -8577, -8237, -8045, -7820, -7419, -6896, -6435, -6149
        .short  -5957, -5679, -5230, -4716, -4309, -4064, -3856, -3523, -3040, -2549, -2196, -1978, -1741, -1355, -853, -395
        .short  -94, 112, 388, 823, 1330, 1743, 1999, 2208, 2532, 3008, 3505, 3867, 4086, 4312, 4690, 5199
        .short  5670, 5977, 6169, 6429, 6864, 7392, 7823, 8071, 8252, 8559, 9052, 9584, 9958, 10151, 10337, 10706
        .short  11351, 11555, 11625, 11812, 12255, 12828, 13265, 13426, 13455, 13645, 14144, 14786, 15241, 15350, 15306, 15487
        .short  16073, 16828, 17307, 17304, 17111, 17272, 18039, 19035, 19545, 19235, 18630, 18782, 20240, 22149, 22353, 18664
        .short  10464, -561, -11208, -18562, -21583, -21378, -20107, -19445, -19715, -20195, -20091, -19292, -18345, -17837, -17850, -17960
        .short  -17709, -17038, -16299, -15870, -15793, -15764, -15461, -14855, -14216, -13823, -13697, -13594, -13264, -12696, -12113, -11742
        .short  -11587, -11438, -11091, -10546, -10000, -9643, -9469, -9291, -8931, -8401, -7881, -7534, -7348, -7149, -6779, -6259
        .short  -5756, -5419, -5226, -5011, -4633, -4117, -3628, -3299, -3102, -2876, -2490, -1977, -1497, -1176, -979, -744
        .short  -350, 164, 637, 950, 1145, 1385, 1788, 2306, 2775, 3077, 3266, 3510, 3924, 4449, 4915, 5207
        .short  5386, 5632, 6058, 6595, 7060, 7337, 7503, 7749, 8191, 8745, 9210, 9469, 9615, 9861, 10324, 10899
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
        .short  10767, 11197, 11779, 12292, 12561, 12607, 12652, 12931, 13493, 14143, 14596, 14718, 14658, 14739, 15191, 15937
        .short  16630, 16931, 16814, 16627, 16832, 17606, 18633, 19302, 19209, 18578, 18213, 18917, 20724, 22516, 22388, 18666
        .short  10974, 665, -9698, -17571, -21618, -22198, -20904, -19514, -19039, -19417, -19911, -19840, -19086, -18079, -17378, -17218
        .short  -17374, -17396, -16995, -16254, -15520, -15101, -15023, -15030, -14821, -14292, -13610, -13054, -12782, -12710, -12591, -12235
        .short  -11655, -11049, -10628, -10438, -10333, -10101, -9646, -9060, -8540, -8223, -8071, -7909, -7577, -7060, -6500, -6070
        .short  -5831, -5681, -5448, -5030, -4485, -3975, -3631, -3441, -3266, -2953, -2468, -1924, -1481, -1214, -1047, -822
        .short  -429, 99, 615, 981, 1187, 1359, 1651, 2118, 2665, 3128, 3414, 3579, 3784, 4157, 4684, 5220
        .short  5610, 5821, 5971, 6235, 6693, 7261, 7758, 8059, 8205, 8370, 8718, 9262, 9845, 10271, 10472, 10566
| <<< GENERATED TABLES

| ---- the machine record's PLAYBACK fields (o3_mover; poly.s po_pgdesc's {offset.w, length.w, source.l} list;
|      offsets from page.s 2.9 and PARAM_PAGES.md: names P+0x16 + 6*slot, defaults P+0x5e +
|      slot, formatters P+0xca + 4*slot).  Slot 0 is TUNE (the 303's notes); v6.4, Tim Hastie's
|      tuning system (modules/synth page.s): its minimum and count (P+0x6a, P+0x9a, longs) make
|      raw 40..88 = -24..+24 semitones, four octaves, 0 in the middle (v6.5c; 40..88 sits
|      inside the Part validator's FLEX clamp 4..124, so no validator hook is needed); its knob
|      handler (P+0x12a) is 0 = one raw a detent (the stock 0x40032d08 is built for 5 a semitone
|      and swallows detents); its formatter prints raw - 64 as "-24" "0" "+24".  The default stays
|      the stock 64 = 0 semitones = C3.
        .align  4
o3_tune_min:
        .long   64 + TUNE_LO
o3_tune_cnt:
        .long   TUNE_HI - TUNE_LO + 1
o3_zero:
        .long   0
o3_fmts:
        .long   o3_fmt_tune, FMT_PLAIN, FMT_PLAIN, FMT_PLAIN, FMT_PLAIN, FMT_PLAIN
o3_title:
        .ascii  "OCTA-303"                     | v7.0: the machine's name (9 bytes with its 0, the field's size)
        .byte   0
o3_names:                               | slots 0..5 (PTCH STRT LEN RATE RTRG RTIM), P+0x16 + 6*slot
        .ascii  "TUNE"
        .byte   0, 0
        .ascii  "CUT"
        .byte   0, 0, 0
        .ascii  "RES"
        .byte   0, 0, 0
        .ascii  "ENV"
        .byte   0, 0, 0
        .ascii  "DEC"
        .byte   0, 0, 0
        .ascii  "ACC"
        .byte   0, 0, 0
o3_defaults:                            | CUT RES ENV DEC ACC: v6.9, the knobs in the middle
        .byte   64, 64, 64, 64, 0

| ---- dEVILish neutral: the knobs that make the 303 of v6.1.1 (o3tables.DF_NEUTRAL); page 1, page 2
| ---- v7.0: the machine's record: the PLAYBACK fields above, then the SETUP page (slots 6..11)
        .align  4
o3_mover:
        .short  0x009, 9
        .long   o3_title
        .short  0x016, 36
        .long   o3_names
        .short  0x05f, 5
        .long   o3_defaults
        .short  0x06a, 4
        .long   o3_tune_min
        .short  0x09a, 4
        .long   o3_tune_cnt
        .short  0x0ca, 24
        .long   o3_fmts
        .short  0x12a, 4
        .long   o3_zero
        .short  0x03a, 36                       | SETUP's names
        .long   o3_mnames
        .short  0x064, 6                        | defaults
        .long   o3_mdefs+6
        .short  0x082, 24                       | minimums
        .long   o3_zero6
        .short  0x0b2, 24                       | counts
        .long   o3_mcnt
        .short  0x0e2, 24                       | formatters
        .long   o3_mfmts
        .short  0x112, 24                       | no list handlers (ANALOG BD's: none)
        .long   o3_zero6
        .short  0x142, 24
        .long   o3_zero6
        .short  0x18a, 8                        | slot flags: SETUP's six plain, PLAYBACK's as FLEX's
        .long   o3_mflags
        .short  -1, 0
        .long   0
o3_zero6:
        .long   0, 0, 0, 0, 0, 0
o3_mcnt:                                | o3tables.SETUP_COUNT
        .long   8, 2, 128, 128, 128, 128
o3_mfmts:
        .long   o3_fmt_wave, o3_fmt_gate, o3_fmt_fine, FMT_PLAIN, FMT_PLAIN, FMT_PLAIN
o3_mflags:
        .long   0x00001111, 0x11311311
o3_mnames:                              | o3tables.SETUP_NAMES
        .ascii  "WAVE"
        .byte   0, 0
        .ascii  "GATE"
        .byte   0, 0
        .ascii  "FINE"
        .byte   0, 0
        .ascii  "SLID"
        .byte   0, 0
        .ascii  "DRIV"
        .byte   0, 0
        .ascii  "ACCV"
        .byte   0, 0
o3_mdefs:                               | a new TB-303 track: PLAYBACK, SETUP (o3tables.SETUP_NEUTRAL)
        .byte   64, 64, 64, 64, 64, 0
        .byte   0, 0, 64, 0, 0, 64
o3_lwave:                               | o3tables.WAVE_LABELS
        .asciz  "SAW"
        .byte   0, 0
        .asciz  "SQR"
        .byte   0, 0
        .asciz  "SAW+D"
        .asciz  "SQR+D"
        .asciz  "RSAW"                  | v7.9: R, the factory preset
        .byte   0
        .asciz  "RSQR"
        .byte   0
        .asciz  "RSAWD"
        .asciz  "RSQRD"
o3_lgate:                               | o3tables.GATE_LABELS
        .asciz  "OFF"
        .byte   0, 0
        .asciz  "303"
        .byte   0, 0

o3_df_neutral:
        .byte   25, 0, 0, 64, 0, 50, 0, 0, 1, 0, 0, 0
o3_f_plus:
        .asciz  "+%d"
o3_notes:                               | v7.0: o3_fmt_tune's names, two bytes each
        .ascii  "C C#D D#E F F#G G#A A#B "
        .align  4
o3_maxmsg:
        .if     HK_MACHINE_ROWS
        .asciz  "MAX 2 MACHINES"         | one limit for every kind of machine (modules/hooks MC_LIMIT)
        .else
        .asciz  "MAX 2 OCTA-303"
        .endif
        .align  4
o3_obuf:                                | v7.1: o3_octave's toast
        .space  16
        .align  4
o3_snap:                                | v7.1: the trigless masks at the trig handler's entry
        .space  16
o3_snapt:
        .long   -1

| ---- ACIDV91 stopwatch: per track 8 longs {calls, call sum, call max, entry-to-loop sum, loop sum, loop max,
|      samples, 0}, read over USB (0xc0/0x57 block 4, modules/usb; tools/octa303/prof/o3prof.py).  Only adds:
|      the readers take deltas.  DMA timer 3 runs free at 132 MHz (the OS reads it too; load-meter/meter.s).
        .set    O3_DTCN3,0xfc07c00c
        .align  4
        .globl  O3_PROF
O3_PROF:
        .fill   256, 1, 0
o3_pt0: .long   0
o3_pt1: .long   0
o3_pn:  .long   0
o3_pflag: .long 0

| ---- runtime state: zeros, depacked by the loader at every boot (poly.s keeps its the same way)
        .align  4
o3_state:
        .fill   ST_SIZE*NTRACKS, 1, 0
        .if     O3_SEAM
o3_hyb:                                 | v9.0: the hybrid's block a track (H_*), 256 bytes
        .fill   256*NTRACKS, 1, 0
        .endif
o3_desc:
        .fill   O3_DLEN, 1, 0                   | v7.0: the machine's record (v7.9: the TB303* sample's clone is gone)
        .align  4
o3_built:
        .fill   4, 1, 0                 | byte 0: the machine's record is built
