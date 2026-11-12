| MORPH v1 -- [TRACK]+[UP] / [TRACK]+[DOWN]: the held tracks' scene morph runs by itself.
|
| A morphing track's A/B weight is not the crossfader's: every frame this unit writes it from a
| triangle A -> B -> A over one cycle of N sequencer 16th steps, always starting on A. The other
| tracks keep the crossfader. [TRACK]+[DOWN] lets the cycle finish on A; the track then stays
| PARKED on A until the crossfader reaches its A end (xf 127), and only then follows the fader.
|
| v1 (22 Oct 2026; v0 on the owner's MKI, ACIDV73MP, 21 Oct: the triangle, the keys, the parking;
| v1 on the unit as ACIDV74MP, 22 Oct):
|   * per track: STEPS (0 = the track's pattern length, 1..64), x (1..16, or 41.625 for the
|     insistent), MODE (SMOOTH / TRIG HOLD); N = STEPS * x, at most 1024 (2664 for 41.625). The
|     defaults, 16 x 8 SMOOTH, are v0's 128 steps.
|   * the cycle follows the sequencer's step word instead of counting frames: k = the steps since
|     the start, so TRIG HOLD changes exactly on the steps and nothing drifts over many cycles;
|     SMOOTH adds the fraction of the step from the frames since the last step and the tempo.
|   * a start waits for the next step (ARMED), so the cycle begins on the grid.
|   * the window ([TRACK]+[UP], below) arms the held tracks; they start on the step after the
|     track keys are released.
|   * the settings and which tracks morph are saved with the project (morph.work, through STORE,
|     below); a loaded project's morphs start again from A on the first step after PLAY.
|
| Measured from the user's 1.40C (morph_disasm.txt, 21 Oct 2026; base 0x40000400):
|   * per-track weight longs 0x80003c60 + 4*t, ten of them (8 tracks + 2 unknown). Written only by
|     the two crossfader writers 0x40061e2e / 0x400626a8, read only by the frame builder's six
|     morph paths (0x4000cca4, cd2a, cd84, ce06, ce4c, cf04), all after 0x4000cc6c.
|   * writer formula, replicated here: w = (short) curve[xf] at 0x400bcd90 (0, -258 .. -32768),
|     weight = (w << 16) | ((0xffff8000 - w) & 0xffff). The morph multiplies the HIGH word with
|     scene A's value and the LOW word with scene B's (path 0x4000ce60): xf 127 = all A, 0 = all B.
|   * the per-frame hook: 0x4000cc62 `move.l #96,%macsr ; lea 12(%sp),%sp` (10 bytes), after the
|     per-track loop and before 0x4000cc6c, where every morph path starts. No branch in the
|     image targets 0x4000cc63..0x4000cc6b. This stub saves and restores what it uses.
|   * tempo24 = BPM*24 at 0x8000181c (latched per frame; docs/firmware/DSP.md); transport
|     0x800065b8 is running if and only if it holds 1 (docs/firmware/STEM_REC.md 1.0).
|   * the sequencer's step word 0x800065b2 (u16) and the current pattern's track record (bank blob
|     0x46c82456 + pattern 0x100b14d0 * 0x8ed8 + track * 0x91a, the length at +0x50): OCTA303's
|     303 gate reads both on the unit (modules/octa303/octa303.s o3_gate).
|   * the [TRACK]-held key layer's table 0x400d1594 (6 records + terminator); this unit carries a
|     copy with UP (0x33) and DOWN (0x20) added, and the build repoints the layer's keys field
|     0x400d164e at it. Handler convention (stock 0x40083488, Zac Kyoti's REC_TRIG_MUTE):
|     handler(keycode @4, event @8), event 1 = press; d0/d1/a0/a1 only, d2-d7 are the caller's.
| Inferred, not measured: that the frame builder runs once per 16-sample frame (a step is
| 992,250 / tempo24 frames on that assumption: SMOOTH's fraction of a step uses it); that the
| step word counts every 16th of the master length while playing.

        .text
        .globl  morph_frame, morph_up, morph_down, mp_keys

| a key record, 0x1a bytes: code, 0, press, release, 16 zero bytes (repeat 0: replaces the layer
| below's, as stock's and SEQ's records do)
        .macro  KEYREC code, press, release
        .byte   \code, 0
        .long   \press, \release
        .space  16
        .endm

        .set    WEIGHTS,  0x80003c60     | long per track (8 used here)
        .set    CURVE,    0x400bcd90     | the crossfader curve, short per xf 0..127
        .set    XF,       0x460d16c8     | the crossfader position, long 0..127 (127 = scene A)
        .set    TEMPO24,  0x8000181c     | BPM * 24
        .set    TRANSPORT,0x800065b8     | 1 = running
        .set    STEPW,    0x800065b2     | the sequencer's step word (u16)
        .set    BANK_PTR, 0x46c82456     | the bank blob
        .set    PAT_IDX,  0x100b14d0     | the current pattern
        .set    PAT_STRIDE,0x8ed8
        .set    TRK_STRIDE,0x91a         | the track record; its length at +0x50
        .set    HELD,     0x460fab40     | held track keys, bit t
        .set    NOTIFY,   0x4005a2b8     | FUN_4005a2b8(text, dur): the toast, key-handler context
        .set    RESUME,   0x4000cc6c     | the frame builder after the displaced instructions
        .set    SUB_K,    4329           | 2^32 / 992,250: a step's fraction = frames * tempo24 * K >> 24
        .set    JUMP,     8              | a step word moving by more than this is a jump: one step

| state per track
        .set    S_FADER,  0              | the crossfader's
        .set    S_RUN,    1              | morphing
        .set    S_STOP,   2              | morphing to its last A
        .set    S_PARK,   3              | parked on A until the fader is at A
        .set    S_ARMED,  4              | starts on the next step
        .set    S_HELD,   5              | armed in the window: starts on the step after its release
        .set    X_EGG,    17             | x past 16, insisted on: 41.625 (16 x 41.625 = 666)
        .set    EGG_PUSH, 16             | detents to the right at x 16 before it gives in

| ---------------------------------------------------------------- the frame hook
| Detour 0x4000cc62 (jmp + 4 bytes of nop): replays `move.l #96,%macsr ; lea 12(%sp),%sp`.
morph_frame:
        move.l  #96,%macsr              | displaced
        lea     12(%sp),%sp             | displaced
mf_body:                                | (the source simulator enters here: it has no MACSR)
        lea     -44(%sp),%sp
        movem.l %d0-%d6/%a0-%a3,(%sp)
| ---- the sequencer's clock, every frame (cheap), so the step word is never stale:
|      d5 = the steps since the last frame (0 or 1, a jump counts one), mp_fsince = the frames
|      since the last step (frozen while stopped)
        moveq   #0,%d5
        mvz.w   STEPW,%d0
        move.l  mp_lastw,%d1
        move.l  %d0,mp_lastw
        moveq   #1,%d2
        cmp.l   TRANSPORT,%d2
        bne     mf_c9                   | stopped: nothing counts
        sub.l   %d1,%d0
        and.l   #0xffff,%d0
        bne     mf_c1
        addq.l  #1,mp_fsince            | the same step: one frame further into it
        bra     mf_c9
mf_c1:  moveq   #JUMP,%d5
        cmp.l   %d5,%d0
        bls     mf_c2
        moveq   #1,%d0                  | a jump (a restart, a pattern change): one step
mf_c2:  move.l  %d0,%d5
        clr.l   mp_fsince
mf_c9:
        move.l  mp_state,%d0            | any track not on the fader?
        or.l    mp_state+4,%d0
        beq     mf_9
| ---- d6 = the fraction of the step that has gone, 0..255 (SMOOTH)
        move.l  mp_fsince,%d6
        move.l  #0xffff,%d0             | a step word standing still for 23 s: no overflow below
        cmp.l   %d0,%d6
        bls     mf_c4
        move.l  %d0,%d6
mf_c4:  move.l  TEMPO24,%d0
        mulu.l  %d0,%d6
        lsr.l   #8,%d6
        move.l  #SUB_K,%d0
        mulu.l  %d0,%d6
        moveq   #16,%d0
        lsr.l   %d0,%d6
        move.l  #255,%d0
        cmp.l   %d0,%d6
        bls     mf_c3
        move.l  %d0,%d6                 | a step longer than the tempo says: hold at its end
mf_c3:  lea     mp_state,%a0
        lea     mp_k,%a1
        lea     WEIGHTS,%a2
        lea     mp_set,%a3              | per track: STEPS, x, MODE, (pad)
        moveq   #0,%d4                  | t
mf_2:   mvz.b   (%a0),%d1
        beq     mf_8                    | the fader's: leave its weight alone
        moveq   #S_PARK,%d2
        cmp.l   %d2,%d1
        bne     mf_3
        moveq   #127,%d2                | parked: A, until the fader is at A too
        cmp.l   XF,%d2
        bne     mf_w
        clr.b   (%a0)                   | the fader is at A: it has the track again
        bra     mf_8
mf_3:   bcs     mf_run                  | 1 or 2: morphing
        moveq   #S_HELD,%d2
        cmp.l   %d2,%d1
        beq     mf_8                    | still in the window: the fader keeps it
        tst.l   %d5                     | armed: waits for a step
        beq     mf_8
        moveq   #S_RUN,%d1
        move.b  %d1,(%a0)
        clr.l   (%a1)                   | k = 0: this step is the cycle's first
        moveq   #127,%d2
        bra     mf_w
mf_run: bsr     mp_len                  | d3 = N
        move.l  (%a1),%d0
        add.l   %d5,%d0                 | k += the steps of this frame
        cmp.l   %d3,%d0
        bcs     mf_4
        sub.l   %d3,%d0                 | the cycle ends
        moveq   #S_STOP,%d2
        cmp.l   %d2,%d1
        bne     mf_4
        moveq   #S_PARK,%d1             | ... on A, as asked: parked
        move.b  %d1,(%a0)
        clr.l   (%a1)
        moveq   #127,%d2
        bra     mf_w
mf_4:   cmp.l   %d3,%d0
        bcs     mf_41
        moveq   #0,%d0                  | N shrank under k (a shorter pattern): from A again
mf_41:  move.l  %d0,(%a1)
        lsl.l   #8,%d0                  | pos = k * 256 + the fraction of the step (SMOOTH)
        tst.b   2(%a3)
        bne     mf_42                   | TRIG HOLD: the step's own value, for the whole step
        add.l   %d6,%d0
mf_42:  divu.l  %d3,%d0                 | x = pos / N, 0..255 (pos < N * 256)
        moveq   #127,%d2
        cmp.l   %d2,%d0
        bhi     mf_43
        sub.l   %d0,%d2                 | rising half: xf = 127 - x (A -> B)
        bra     mf_w
mf_43:  move.l  %d0,%d2
        add.l   #-128,%d2               | falling half: xf = x - 128 (B -> A)
mf_w:   lea     CURVE,%a1               | d2 = xf: the weight, exactly as the fader writers make it
        move.w  (%a1,%d2.l*2),%d1
        move.l  #-32768,%d3
        sub.l   %d1,%d3
        mvz.w   %d3,%d3
        swap    %d1
        clr.w   %d1
        or.l    %d1,%d3
        move.l  %d3,(%a2)
        lea     mp_k,%a1                | a1 again: this track's k
        move.l  %d4,%d0
        lsl.l   #2,%d0
        add.l   %d0,%a1
mf_8:   addq.l  #1,%a0
        addq.l  #4,%a1
        addq.l  #4,%a2
        addq.l  #4,%a3
        addq.l  #1,%d4
        moveq   #8,%d0
        cmp.l   %d0,%d4
        bne     mf_2
mf_9:   movem.l (%sp),%d0-%d6/%a0-%a3
        lea     44(%sp),%sp
        jmp     RESUME

| mp_len -- d3 = N = STEPS * x for track d4 (a3 = its settings); STEPS 0 = the track's length in
| the current pattern (1..64, else 16). x 1..16 (N at most 1024), or X_EGG: N = STEPS x 333 / 8. Clobbers d0, d2 (d1 is the state).
mp_len:
        mvz.b   (%a3),%d3
        bne     ml_2
        moveq   #16,%d3                 | the track's length (16 without a record)
        move.l  BANK_PTR,%d0
        beq     ml_2
        move.l  %d0,%a1
        mvz.b   PAT_IDX,%d0
        and.l   #15,%d0
        move.l  #PAT_STRIDE,%d2
        muls.l  %d2,%d0
        add.l   %d0,%a1
        move.l  %d4,%d0
        move.l  #TRK_STRIDE,%d2
        muls.l  %d2,%d0
        add.l   %d0,%a1
        mvz.b   0x50(%a1),%d3
        moveq   #64,%d0
        cmp.l   %d0,%d3
        bls     ml_1
        moveq   #16,%d3
ml_1:   tst.l   %d3
        bne     ml_2
        moveq   #16,%d3
ml_2:   mvz.b   1(%a3),%d0              | x, 1..16, or X_EGG
        moveq   #X_EGG,%d2
        cmp.l   %d2,%d0
        bne     ml_2b
        move.l  #333,%d0                | 41.625 = 333 / 8
        mulu.l  %d0,%d3
        lsr.l   #3,%d3
        bne     ml_5
        moveq   #1,%d3
        bra     ml_5
ml_2b:  moveq   #16,%d2
        cmp.l   %d2,%d0
        bls     ml_3
        move.l  %d2,%d0
ml_3:   tst.l   %d0
        bne     ml_4
        moveq   #1,%d0
ml_4:   mulu.l  %d0,%d3
        move.l  #1024,%d0               | STEPS above 64 (a stray byte): 64 x 16
        cmp.l   %d0,%d3
        bls     ml_5
        move.l  %d0,%d3
ml_5:   lea     mp_k,%a1                | a1 = this track's k (the caller's pointer)
        move.l  %d4,%d0
        lsl.l   #2,%d0
        add.l   %d0,%a1
        rts

| ---------------------------------------------------------------- the keys
| morph_up ([TRACK]+[UP], the [TRACK] layer): on press, opens the MORPH window for the held tracks
| (or closes it, when it is open and [UP] reaches this layer).
morph_up:
        moveq   #1,%d0
        cmp.l   8(%sp),%d0              | press only
        bne     mu_9
        tst.l   mw_win
        bne     mw_close
        move.l  HELD,%d1
        beq     mu_9
        lea     mp_state,%a0            | every held track: armed in the window (one already
mu_2:   btst    #0,%d1                  | morphing stays on; one stopping carries on)
        beq     mu_3
        bsr     mp_hold1
mu_3:   addq.l  #1,%a0
        lsr.l   #1,%d1
        bne     mu_2
        move.l  HELD,%d1
        bra     mw_open
mu_9:   rts

| mp_hold1 -- the track at a0: the fader's or parked -> held (starts after the window); stopping ->
| morphing again; morphing, armed or held -> unchanged. Clobbers d0.
mp_hold1:
        mvz.b   (%a0),%d0
        beq     mh_hold
        subq.l  #S_STOP,%d0
        beq     mst_run
        subq.l  #S_PARK-S_STOP,%d0
        bne     mst_9
mh_hold: moveq  #S_HELD,%d0
        move.b  %d0,(%a0)
        rts

| mp_start1 -- the track at a0: the fader's or parked -> armed (starts on the next step, from A);
| stopping -> morphing again (the stop is cancelled); morphing or armed -> unchanged. Clobbers d0.
mp_start1:
        mvz.b   (%a0),%d0
        beq     mst_arm                 | the fader's
        subq.l  #S_STOP,%d0
        beq     mst_run                 | stopping: carry on
        subq.l  #S_PARK-S_STOP,%d0
        bne     mst_9                   | morphing or armed: unchanged
mst_arm: moveq  #S_ARMED,%d0
        move.b  %d0,(%a0)
mst_9:  rts
mst_run: moveq  #S_RUN,%d0
        move.b  %d0,(%a0)
        rts

| morph_down ([TRACK]+[DOWN]): on press, every held morphing track finishes its cycle on A, then
| parks there; an armed one goes back to the fader. Toast MORPH STOP.
morph_down:
        moveq   #1,%d0
        cmp.l   8(%sp),%d0
        bne     mu_9
        move.l  HELD,%d1
        beq     mu_9
        bsr     mp_stopmask
        move.l  #S_STOP_T,%d0
toast:                                  | tail-call NOTIFY(text, 0x30) in our caller's frame
        move.l  %d0,4(%sp)
        moveq   #0x30,%d0
        move.l  %d0,8(%sp)
        jmp     NOTIFY

| mp_stopmask -- mp_stop1 on every track of the mask d1. Clobbers d0, d1, a0.
mp_stopmask:
        lea     mp_state,%a0
msm_1:  btst    #0,%d1
        beq     msm_2
        bsr     mp_stop1
msm_2:  addq.l  #1,%a0
        lsr.l   #1,%d1
        bne     msm_1
        rts

| mp_stop1 -- the track at a0: morphing -> stopping; armed or held -> the fader's. Clobbers d0.
mp_stop1:
        mvz.b   (%a0),%d0
        subq.l  #S_RUN,%d0
        bne     ms_1
        moveq   #S_STOP,%d0
        move.b  %d0,(%a0)
        rts
ms_1:   subq.l  #S_ARMED-S_RUN,%d0
        beq     ms_3
        subq.l  #S_HELD-S_ARMED,%d0
        bne     ms_2
ms_3:   clr.b   (%a0)
ms_2:   rts

| ---------------------------------------------------------------- the window
| [TRACK]+[UP] opens a TEMPO-class window over the page for the tracks held at that moment (the
| structure of ilia-murzinov's SEQ, modules/seq: WCREATE / WFRAME / WDESTROY, an
| input layer pushed over everything, the stock text and box routines, y counted up from the
| bottom). While it is open:
|   A  STEPS (0 = TRK, the track's length, 1..64)     B  x (1..8)     C  MODE (SMOOTH / HOLD)
|   YES  MORPH on / off for the window's tracks        DOWN  stop (as [TRACK]+[DOWN])
|   NO or UP  close; releasing every window track key closes it too (a soft timer, ~60 Hz,
|   watches the held keys and redraws the state and the step when they change).
| The settings shown are the first window track's; an edit sets every window track to the value.
| From a key handler, as SEQ opens its window from the PAGE handler.

        .set    WCREATE,  0x4005829c    | (w, h, 0, 0, class, closed) -> window
        .set    WFRAME,   0x40056f4c    | (window)
        .set    WDESTROY, 0x40055db4    | (&window)
        .set    CLEAR,    0x40035624    | (surface)
        .set    FONT,     0x400ba876    | the small UI font, 6 px
        .set    TEXT,     0x40012bd8    | (font, surface, x, y, limit, str)
        .set    TWIDTH,   0x40012f30    | (font, limit, str) -> pixels
        .set    RULE,     0x40011910    | (surface, x, y, x2, 1)
        .set    INVERT,   0x40012254    | (surface, x1, y1, x2, y2, -1): an EOR bar
        .set    SPRINTF,  0x40013a08
        .set    LPUSH,    0x40031494    | (layer)
        .set    LPOP,     0x4003146c    | (layer)
        .set    TIMER,    0x40031a0c    | (period, callback) -> slot; ~0.5 s = 60
        .set    UNTIMER,  0x40031abc    | (slot)
        .set    SCRDIRTY, 0x46c7c72c
        .set    WINW,     92
        .set    WINH,     64
        .set    Y_TITLE,  52
        .set    Y_RULE,   49
        .set    Y_MORPH,  40
        .set    Y_STEPS,  32
        .set    Y_MULT,   24
        .set    Y_MODE,   16
        .set    Y_POS,    4
        .set    X_LAB,    6
        .set    X_VAL,    88
        .set    TICK,     2             | the soft timer's period: two ticks, ~17 ms

| mw_open -- d1 = the held tracks. Clobbers d0, d1, a0, a1.
mw_open:
        move.l  %d1,mw_targets
        moveq   #-1,%d0
        move.l  %d0,mw_last             | force the first paint
        pea     mw_closed
        pea     5                       | TEMPO class: windows of the class evict each other
        clr.l   -(%sp)
        clr.l   -(%sp)
        pea     WINH
        pea     WINW
        jsr     WCREATE
        lea     24(%sp),%sp
        move.l  %d0,mw_win
        beq     mw_o9
        move.l  %d0,-(%sp)
        jsr     WFRAME
        addq.l  #4,%sp
        pea     MW_LAYER
        jsr     LPUSH
        addq.l  #4,%sp
        moveq   #1,%d0
        move.l  %d0,mw_pushed
        pea     mw_tick
        pea     TICK
        jsr     TIMER
        addq.l  #8,%sp
        move.l  %d0,mw_timer
        bra     mw_draw
mw_o9:  rts

| mw_close -- the window, the layer and the timer gone; safe when already closed.
mw_close:
        tst.l   mw_win
        beq     mw_c9
        pea     mw_win
        jsr     WDESTROY
        addq.l  #4,%sp
mw_closed:                              | WCREATE's callback: another window of the class took over
        clr.l   mw_win
        lea     mp_state,%a0            | the window is gone: its held tracks start on the next step
        moveq   #7,%d1
mw_cr:  mvz.b   (%a0,%d1.l),%d0
        subq.l  #S_HELD,%d0             | (d0, d1, a0 only: a callback keeps d2-d7)
        bne     mw_cr2
        moveq   #S_ARMED,%d0
        move.b  %d0,(%a0,%d1.l)
mw_cr2: subq.l  #1,%d1
        bpl     mw_cr
        move.l  mw_timer,%d0
        bmi     mw_c1
        move.l  %d0,-(%sp)
        jsr     UNTIMER
        addq.l  #4,%sp
        moveq   #-1,%d0
        move.l  %d0,mw_timer
mw_c1:  tst.l   mw_pushed               | once: WDESTROY may call mw_closed itself
        beq     mw_c9
        clr.l   mw_pushed
        pea     MW_LAYER
        jsr     LPOP
        addq.l  #4,%sp
mw_c9:  rts

| mw_tick -- the soft timer: closes when no window track key is held any more, else repaints when
| the first track's state or step changed (once a step at most while morphing).
mw_tick:
        tst.l   mw_win
        beq     mw_close                | (closed elsewhere: drops the timer and the layer)
        move.l  HELD,%d0
        and.l   mw_targets,%d0
        beq     mw_close
        bsr     mw_first                | a0 = the first track's state, d0 = its index
        move.l  %d0,%d1
        lsl.l   #2,%d1
        lea     mp_k,%a1
        move.l  (%a1,%d1.l),%d1
        mvz.b   (%a0),%d0
        swap    %d0
        clr.w   %d0                     | state << 16 | k (k < 512)
        or.l    %d1,%d0
        cmp.l   mw_last,%d0
        beq     mw_t9
        bra     mw_draw
mw_t9:  rts

| mw_first -- d0 = the first window track, a0 = its state byte, a1 = its settings. Clobbers d1.
mw_first:
        moveq   #0,%d0
        move.l  mw_targets,%d1
mf1_1:  btst    %d0,%d1
        bne     mf1_2
        addq.l  #1,%d0
        moveq   #7,%d1
        cmp.l   %d1,%d0
        bcc     mf1_2                   | (never: the mask is not empty)
        move.l  mw_targets,%d1
        bra     mf1_1
mf1_2:  lea     mp_state,%a0
        add.l   %d0,%a0
        lea     mp_set,%a1
        move.l  %d0,%d1
        lsl.l   #2,%d1
        add.l   %d1,%a1
        rts

| ---- the window's keys: handler(keycode @4, event @8), event 1 = press
mw_yes:                                 | YES: swallowed (stock under [TRACK] would arm recording)
        rts

mw_no:                                  | NO, UP: close
        moveq   #1,%d0
        cmp.l   8(%sp),%d0
        beq     mw_close
mw_k9:  rts

mw_down:
        moveq   #1,%d0
        cmp.l   8(%sp),%d0
        bne     mw_k9
        move.l  mw_targets,%d1
        bsr     mp_stopmask
        bra     mw_draw

| mw_enc -- encoder (index @4, delta @8): A STEPS 0..64, B x 1..16 (then, insisted on, 41.625), C MODE 0..1 (any turn to the
| right HOLD, to the left SMOOTH), on every window track; the first track's value is the base.
mw_enc:
        tst.l   8(%sp)                  | delta 0: nothing
        beq     mw_k9
        bsr     mw_first                | a1 = the first track's settings (d0, d1 clobbered)
        move.l  8(%sp),%d1              | delta
        move.l  4(%sp),%d0              | index
        beq     mw_e_steps
        subq.l  #1,%d0
        beq     mw_e_mult
        subq.l  #1,%d0
        bne     mw_k9                   | D..F: nothing
        moveq   #0,%d0                  | MODE
        tst.l   %d1
        bmi     mw_e_set2
        moveq   #1,%d0
mw_e_set2:
        moveq   #2,%d1                  | the byte: MODE at +2
        bra     mw_e_set
mw_e_steps:
        mvz.b   (%a1),%d0
        add.l   %d1,%d0
        bpl     mw_e_s1
        moveq   #0,%d0
mw_e_s1: moveq  #64,%d1
        cmp.l   %d1,%d0
        ble     mw_e_s2
        move.l  %d1,%d0
mw_e_s2: moveq  #0,%d1
        bra     mw_e_set
mw_e_mult:                              | (d0, d1 only: a key handler keeps d2-d7)
        mvz.b   1(%a1),%d0
        cmp.l   #X_EGG,%d0
        bne     mw_e_m0
        tst.l   %d1                     | at 41.625: left goes back to 16, right stays
        bpl     mw_e_m2
        moveq   #16,%d0
        clr.l   mw_insist
        bra     mw_e_m2
mw_e_m0: tst.l  %d1
        bmi     mw_e_dn
        cmp.l   #16,%d0
        bne     mw_e_up
        add.l   %d1,mw_insist           | at 16, turning right: insisting
        move.l  mw_insist,%d1
        cmp.l   #EGG_PUSH,%d1
        blt     mw_e_m2
        moveq   #X_EGG,%d0
        clr.l   mw_insist
        bra     mw_e_m2
mw_e_up: clr.l  mw_insist
        add.l   %d1,%d0
        cmp.l   #16,%d0
        ble     mw_e_m2
        moveq   #16,%d0
        bra     mw_e_m2
mw_e_dn: clr.l  mw_insist
        add.l   %d1,%d0
        cmp.l   #1,%d0
        bge     mw_e_m2
        moveq   #1,%d0
mw_e_m2: moveq  #1,%d1
| d0 = the value, d1 = the byte (0 STEPS, 1 x, 2 MODE): set on every window track
mw_e_set:
        lea     mp_set,%a0
        add.l   %d1,%a0
        move.l  mw_targets,%d1
mw_e_t: btst    #0,%d1
        beq     mw_e_n
        move.b  %d0,(%a0)
mw_e_n: addq.l  #4,%a0
        lsr.l   #1,%d1
        bne     mw_e_t
        bra     mw_draw

| ---- the paint
| MORPH  T1              (the window tracks)
| ─────────────
|  MORPH        ON       (OFF / WAIT / ON / STOP / PARK)
|  STEPS (A)    16       (TRK = the track's length)
|  x (B)         8
|  MODE (C)  SMOOTH      (SMOOTH / HOLD)
|  STEP 12 / 128         (while morphing)
mw_draw:
        tst.l   mw_win
        beq     mw_d99
        lea     -44(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        move.l  mw_win,%a2
        lea     36(%a2),%a5             | the window's surface
        move.l  %a5,-(%sp)
        jsr     CLEAR
        addq.l  #4,%sp
        moveq   #4,%d0
        moveq   #Y_TITLE,%d1
        lea     T_TITLE,%a0
        bsr     mw_text
        bsr     mw_fmt_tracks
        moveq   #X_VAL,%d0
        moveq   #Y_TITLE,%d1
        lea     mw_buf,%a0
        bsr     mw_rtext
        pea     1
        pea     WINW-4
        pea     Y_RULE
        pea     4
        move.l  %a5,-(%sp)
        jsr     RULE
        lea     20(%sp),%sp
        bsr     mw_first                | d0 = track, a0 = state, a1 = settings
        move.l  %d0,%d6
        move.l  %a1,%a3
        mvz.b   (%a0),%d7               | the state
| MORPH row
        moveq   #X_LAB,%d0
        moveq   #Y_MORPH,%d1
        lea     L_MORPH,%a0
        bsr     mw_text
        lea     V_STATE,%a0             | 5 bytes a name: OFF ON STOP PARK WAIT
        move.l  %d7,%d0
        mulu.w  #5,%d0
        add.l   %d0,%a0
        moveq   #X_VAL,%d0
        moveq   #Y_MORPH,%d1
        bsr     mw_rtext
| STEPS row
        moveq   #X_LAB,%d0
        moveq   #Y_STEPS,%d1
        lea     L_STEPS,%a0
        bsr     mw_text
        mvz.b   (%a3),%d0
        lea     V_TRK,%a0
        tst.l   %d0
        beq     mw_d1
        bsr     mw_num
mw_d1:  moveq   #X_VAL,%d0
        moveq   #Y_STEPS,%d1
        bsr     mw_rtext
| x row
        moveq   #X_LAB,%d0
        moveq   #Y_MULT,%d1
        lea     L_MULT,%a0
        bsr     mw_text
        mvz.b   1(%a3),%d0
        lea     V_EGG,%a0
        moveq   #X_EGG,%d1
        cmp.l   %d1,%d0
        beq     mw_dx
        bsr     mw_num
mw_dx:  moveq   #X_VAL,%d0
        moveq   #Y_MULT,%d1
        bsr     mw_rtext
| MODE row
        moveq   #X_LAB,%d0
        moveq   #Y_MODE,%d1
        lea     L_MODE,%a0
        bsr     mw_text
        lea     V_SMOOTH,%a0
        tst.b   2(%a3)
        beq     mw_d2
        lea     V_HOLD,%a0
mw_d2:  moveq   #X_VAL,%d0
        moveq   #Y_MODE,%d1
        bsr     mw_rtext
| the step, while morphing
        moveq   #S_RUN,%d0
        cmp.l   %d0,%d7
        beq     mw_d3
        moveq   #S_STOP,%d0
        cmp.l   %d0,%d7
        beq     mw_d3
        move.l  %d6,%d4                 | not morphing: the cycle the settings make
        bsr     mp_len
        move.l  %d3,-(%sp)
        pea     F_CYC
        pea     mw_buf
        jsr     SPRINTF
        lea     12(%sp),%sp
        bra     mw_d5
mw_d3:  move.l  %d6,%d4                 | mp_len: d4 = the track, a3 = its settings
        move.l  %d6,%d0
        lsl.l   #2,%d0
        lea     mp_k,%a0
        move.l  (%a0,%d0.l),%d5         | k
        bsr     mp_len                  | d3 = N
        move.l  %d3,-(%sp)
        addq.l  #1,%d5
        move.l  %d5,-(%sp)              | the step, from 1
        pea     F_POS
        pea     mw_buf
        jsr     SPRINTF
        lea     16(%sp),%sp
mw_d5:  moveq   #X_LAB,%d0
        moveq   #Y_POS,%d1
        lea     mw_buf,%a0
        bsr     mw_text
mw_d4:
| what this paint showed, for mw_tick
        move.l  %d6,%d0
        lsl.l   #2,%d0
        lea     mp_k,%a0
        move.l  (%a0,%d0.l),%d0
        swap    %d7
        clr.w   %d7
        or.l    %d0,%d7
        move.l  %d7,mw_last
        moveq   #1,%d0
        move.l  %d0,SCRDIRTY
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     44(%sp),%sp
mw_d99: rts

| mw_num -- d0 -> "%d" in mw_buf, a0 = mw_buf. Clobbers d0, d1, a0, a1.
mw_num:
        move.l  %d0,-(%sp)
        pea     F_NUM
        pea     mw_buf
        jsr     SPRINTF
        lea     12(%sp),%sp
        lea     mw_buf,%a0
        rts

| mw_text -- d0 = x, d1 = y, a0 = str; a5 = surface. Clobbers d0, d1, a0, a1.
mw_text:
        move.l  %a0,-(%sp)
        pea     -1
        move.l  %d1,-(%sp)
        move.l  %d0,-(%sp)
        move.l  %a5,-(%sp)
        pea     FONT
        jsr     TEXT
        lea     24(%sp),%sp
        rts

| mw_rtext -- a0 right-aligned at x = d0, row d1 (the pointer parked across TWIDTH, as SEQ
| learnt). Clobbers d0, d1, a0, a1.
mw_rtext:
        move.l  %a0,mw_rstr
        move.l  %d0,mw_rx
        move.l  %d1,mw_ry
        move.l  %a0,-(%sp)
        pea     -1
        pea     FONT
        jsr     TWIDTH
        lea     12(%sp),%sp
        move.l  mw_rx,%d1
        sub.l   %d0,%d1
        bpl     mw_r1
        moveq   #0,%d1
mw_r1:  move.l  %d1,%d0
        move.l  mw_ry,%d1
        move.l  mw_rstr,%a0
        bra     mw_text

| mw_fmt_tracks -- "T135" (1-based) for the window tracks into mw_buf. Clobbers d0, d1, a0.
mw_fmt_tracks:
        lea     mw_buf,%a0
        moveq   #0x54,%d0               | 'T'
        move.b  %d0,(%a0)+
        moveq   #0,%d1
mwf_1:  move.l  mw_targets,%d0
        btst    %d1,%d0
        beq     mwf_2
        moveq   #0x31,%d0               | '1'
        add.l   %d1,%d0
        move.b  %d0,(%a0)+
mwf_2:  addq.l  #1,%d1
        moveq   #8,%d0
        cmp.l   %d0,%d1
        bcs     mwf_1
        clr.b   (%a0)
        rts

S_STOP_T: .asciz "MORPH STOP"
T_TITLE: .asciz "MORPH"
L_MORPH: .asciz "MORPH"
L_STEPS: .asciz "STEPS (A)"
L_MULT: .asciz  "x (B)"
L_MODE: .asciz  "MODE (C)"
V_STATE: .asciz "OFF"                   | 5 bytes a name, by the state
         .byte  0
        .asciz  "ON"
        .byte   0, 0
        .asciz  "STOP"
        .asciz  "PARK"
        .asciz  "WAIT"
        .asciz  "ARM"
        .byte   0
V_TRK:  .asciz  "TRK"
V_SMOOTH: .asciz "SMOOTH"
V_HOLD: .asciz  "HOLD"
F_NUM:  .asciz  "%d"
F_POS:  .asciz  "STEP %d / %d"
F_CYC:  .asciz  "CYCLE %d STEPS"
V_EGG:  .asciz  "41.625"

| ---- the window's layer (pushed while it is open): {next, keys, encoders, +12, +16, -1, -1}
        .balign 4
MW_LAYER:
        .long   0, MW_KEYS, MW_ENCS, 0, 0, -1, -1
MW_KEYS:
        KEYREC  0x31, mw_yes, 0                     | YES:  swallowed
        KEYREC  0x32, mw_no, 0                      | NO:   close
        KEYREC  0x33, mw_no, 0                      | UP:   close
        KEYREC  0x20, mw_down, 0                    | DOWN: stop
        .byte   0xff, 0
        .space  24
MW_ENCS:
        .byte   0, 0                                | A: STEPS
        .long   mw_enc, 0, 0, 0, 0
        .byte   1, 0                                | B: x
        .long   mw_enc, 0, 0, 0, 0
        .byte   2, 0                                | C: MODE
        .long   mw_enc, 0, 0, 0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0

| ---------------------------------------------------------------- saving (STORE's client)
| morph.work beside the bank files: 'MRPW', version 1, payload length 40, CRC-32 of the payload
| (zlib's, store_crc32); then the payload: mp_set (8 tracks x STEPS, x, MODE, pad), one byte of the
| tracks that morph (bit t: running, armed or held in the window), 7 zero bytes. Written when the
| payload differs from the one last read or written (mp_saved), at the bank writer and the project
| store; copied to morph.strd at the store and back at a reload, as MIDI SCENES keeps scenes.work.
| A file that is not that is never written over: STORE lists it (client 4) and asks.
| STORE's handlers may clobber every register (modules/store/README.md).
        .globl  mrp_st_loadall_post, mrp_st_loadmask_post, mrp_st_newproj, mrp_st_bankw_post
        .globl  mrp_st_pstore_pre, mrp_st_pstore_post, mrp_st_preload_post, mrp_st_answer
| store_path, store_fopen, store_fread, store_fwrite, store_fclose, store_crc32 and store_refuse
| are STORE's (undefined here: the link resolves them).
        .set    MP_MAGIC, 0x4d525057     | 'MRPW'
        .set    MP_LEN,   40
        .set    MP_CLIENT,4              | STORE's CLIENT_IDS
        .set    F_COPY,   0x40016388     | (dst path, src path, 0) -> < 0 error (MIDI SCENES)

| mp_build -- the payload of the current settings and states into mp_buf. Clobbers d0-d2, a0, a1.
mp_build:
        lea     mp_set,%a0
        lea     mp_buf,%a1
        moveq   #8,%d1
mb_1:   move.l  (%a0)+,(%a1)+
        subq.l  #1,%d1
        bne     mb_1
        moveq   #0,%d0                  | the tracks that morph
        moveq   #7,%d1
        lea     mp_state,%a0
mb_2:   mvz.b   (%a0,%d1.l),%d2
        subq.l  #S_RUN,%d2
        beq     mb_on
        subq.l  #S_ARMED-S_RUN,%d2
        beq     mb_on
        subq.l  #S_HELD-S_ARMED,%d2
        bne     mb_3
mb_on:  moveq   #1,%d2
        lsl.l   %d1,%d2
        or.l    %d2,%d0
mb_3:   subq.l  #1,%d1
        bpl     mb_2
        move.l  %d0,%d1
        lsl.l   #8,%d1
        lsl.l   #8,%d1
        lsl.l   #8,%d1                  | the mask in the first byte, three zero bytes
        move.l  %d1,(%a1)+
        clr.l   (%a1)
        rts

| mp_save -- write morph.work when the payload differs from mp_saved. Clobbers everything.
mp_save:
        tst.l   mp_nowrite
        bne     mps_9
        bsr     mp_build
        lea     mp_buf,%a0
        lea     mp_saved,%a1
        moveq   #MP_LEN/4,%d1
mps_1:  move.l  (%a0)+,%d0
        cmp.l   (%a1)+,%d0
        bne     mps_2
        subq.l  #1,%d1
        bne     mps_1
mps_9:  rts                             | nothing changed
mps_2:  tst.l   mp_backup
        beq     mps_3
        clr.l   mp_backup               | the refused file kept as morph.bak first
        lea     FMT_MWORK,%a0
        lea     mp_psrc,%a1
        moveq   #0,%d0
        jsr     store_path
        lea     FMT_MBAK,%a0
        lea     mp_path,%a1
        moveq   #0,%d0
        jsr     store_path
        clr.l   -(%sp)
        pea     mp_psrc
        pea     mp_path
        jsr     F_COPY
        lea     12(%sp),%sp
mps_3:  lea     mp_buf,%a0
        moveq   #MP_LEN,%d0
        moveq   #0,%d1
        jsr     store_crc32
        lea     mp_hdr,%a0
        move.l  %d0,12(%a0)
        move.l  #MP_MAGIC,%d0
        move.l  %d0,(%a0)
        moveq   #1,%d0
        move.l  %d0,4(%a0)
        moveq   #MP_LEN,%d0
        move.l  %d0,8(%a0)
        lea     FMT_MWORK,%a0
        lea     mp_path,%a1
        moveq   #0,%d0
        jsr     store_path
        lea     mp_path,%a0
        lea     MP_MODE_W,%a1
        lea     mp_ctx,%a2
        jsr     store_fopen
        tst.l   %d0
        bmi     mps_8
        lea     mp_hdr,%a0
        moveq   #16,%d0
        jsr     store_fwrite
        move.l  %d0,%d2
        lea     mp_buf,%a0
        moveq   #MP_LEN,%d0
        jsr     store_fwrite
        move.l  %d0,%d3
        jsr     store_fclose
        subq.l  #1,%d2
        bne     mps_8
        subq.l  #1,%d3
        bne     mps_8
        lea     mp_buf,%a0              | written: the payload on the card
        lea     mp_saved,%a1
        moveq   #MP_LEN/4,%d1
mps_4:  move.l  (%a0)+,(%a1)+
        subq.l  #1,%d1
        bne     mps_4
        rts
mps_8:  addq.l  #1,mp_ioerr
        rts

| mp_load -- read morph.work and apply it; no file: the defaults; a bad file: the defaults, and
| the file is listed with STORE and never written over. Clobbers everything.
mp_load:
        clr.l   mp_nowrite
        clr.l   mp_backup
        lea     FMT_MWORK,%a0
        lea     mp_path,%a1
        moveq   #0,%d0
        jsr     store_path
        lea     mp_path,%a0
        lea     MP_MODE_R,%a1
        lea     mp_ctx,%a2
        jsr     store_fopen
        tst.l   %d0
        bmi     mp_defaults             | no file
        lea     mp_hdr,%a0
        moveq   #16,%d0
        jsr     store_fread
        subq.l  #1,%d0
        bne     mpl_bad
        lea     mp_hdr,%a0
        move.l  (%a0),%d0
        cmp.l   #MP_MAGIC,%d0
        bne     mpl_bad
        moveq   #1,%d0
        cmp.l   4(%a0),%d0
        bne     mpl_bad
        moveq   #MP_LEN,%d0
        cmp.l   8(%a0),%d0
        bne     mpl_bad
        lea     mp_buf,%a0
        moveq   #MP_LEN,%d0
        jsr     store_fread
        subq.l  #1,%d0
        bne     mpl_bad
        jsr     store_fclose
        lea     mp_buf,%a0
        moveq   #MP_LEN,%d0
        moveq   #0,%d1
        jsr     store_crc32
        cmp.l   mp_hdr+12,%d0
        bne     mpl_crc
        bra     mp_apply
mpl_bad:
        jsr     store_fclose
mpl_crc:
        addq.l  #1,mp_bad
        moveq   #1,%d0
        move.l  %d0,mp_nowrite
        moveq   #MP_CLIENT,%d0
        moveq   #0,%d1
        jsr     store_refuse
        bra     mp_defaults

| mp_defaults -- every track 16 x 8 SMOOTH and on the fader; mp_saved = that payload, so an
| untouched project gets no file.
mp_defaults:
        lea     mp_buf,%a0
        moveq   #8,%d1
        move.l  #0x10080000,%d0         | 16, 8, SMOOTH, pad
mpd_1:  move.l  %d0,(%a0)+
        subq.l  #1,%d1
        bne     mpd_1
        clr.l   (%a0)+
        clr.l   (%a0)
| mp_apply -- mp_buf (a payload) into mp_set and the states, each value clamped; mp_saved = it.
| The tracks that morphed are armed: they start from A on the first step after PLAY. The others
| go to the fader, a track that was not on the fader by way of PARK (held on A until the fader
| is at A, as after a stop: its weight is not left where its morph was).
mp_apply:
        lea     mp_buf,%a0
        lea     mp_set,%a1
        moveq   #0,%d1                  | t
mpa_1:  mvz.b   (%a0),%d0               | STEPS 0..64
        cmp.l   #64,%d0
        bls     mpa_2
        moveq   #16,%d0
mpa_2:  move.b  %d0,(%a1)
        mvz.b   1(%a0),%d0              | x 1..16, X_EGG
        cmp.l   #X_EGG,%d0
        bls     mpa_3
        moveq   #8,%d0
mpa_3:  tst.l   %d0
        bne     mpa_4
        moveq   #8,%d0
mpa_4:  move.b  %d0,1(%a1)
        mvz.b   2(%a0),%d0              | MODE 0..1
        moveq   #1,%d2
        cmp.l   %d2,%d0
        bls     mpa_5
        moveq   #0,%d0
mpa_5:  move.b  %d0,2(%a1)
        clr.b   3(%a1)
        addq.l  #4,%a0
        addq.l  #4,%a1
        addq.l  #1,%d1
        moveq   #8,%d0
        cmp.l   %d0,%d1
        bne     mpa_1
        mvz.b   (%a0),%d3               | the tracks that morph
        lea     mp_state,%a0
        lea     mp_k,%a1
        moveq   #0,%d1
mpa_6:  clr.l   (%a1)+
        btst    %d1,%d3
        beq     mpa_7
        moveq   #S_ARMED,%d0
        bra     mpa_8
mpa_7:  mvz.b   (%a0),%d0
        beq     mpa_9                   | on the fader: stays
        moveq   #S_PARK,%d0
mpa_8:  move.b  %d0,(%a0)
mpa_9:  addq.l  #1,%a0
        addq.l  #1,%d1
        moveq   #8,%d0
        cmp.l   %d0,%d1
        bne     mpa_6
        bsr     mp_build                | what is on the card (clamped values: a rewrite if any was)
        lea     mp_buf,%a0
        lea     mp_saved,%a1
        moveq   #MP_LEN/4,%d1
mpa_10: move.l  (%a0)+,(%a1)+
        subq.l  #1,%d1
        bne     mpa_10
        rts

| ---- STORE's events
mrp_st_loadall_post:
mrp_st_loadmask_post:
        bra     mp_load

mrp_st_newproj:
        clr.l   mp_nowrite
        clr.l   mp_backup
        bra     mp_defaults

mrp_st_bankw_post:
mrp_st_pstore_pre:
        bra     mp_save

mrp_st_pstore_post:                     | morph.work -> morph.strd (the saved project)
        tst.l   mp_nowrite
        bne     mrs_9
        lea     FMT_MSTRD,%a0
        lea     mp_psrc,%a1
        moveq   #0,%d0
        jsr     store_path
        lea     FMT_MWORK,%a0
        lea     mp_path,%a1
        moveq   #0,%d0
        jsr     store_path
        clr.l   -(%sp)
        pea     mp_path
        pea     mp_psrc
        jsr     F_COPY
        lea     12(%sp),%sp
mrs_9:  rts

mrp_st_preload_post:                    | the saved project back: morph.strd -> morph.work, read
        lea     FMT_MWORK,%a0
        lea     mp_psrc,%a1
        moveq   #0,%d0
        jsr     store_path
        lea     FMT_MSTRD,%a0
        lea     mp_path,%a1
        moveq   #0,%d0
        jsr     store_path
        clr.l   -(%sp)
        pea     mp_path
        pea     mp_psrc
        jsr     F_COPY
        lea     12(%sp),%sp
        tst.l   %d0
        bmi     mrs_9                   | no saved copy: as it is
        bra     mp_load

| mrp_st_answer: d0 = IGNORE (0) / OVERWRITE (1) / BACKUP (2) for a refused morph.work. Both
| writes happen at the next save (the answer runs in the UI task, the card is the engine's).
mrp_st_answer:
        tst.l   %d0
        beq     mra_9
        moveq   #2,%d1
        cmp.l   %d1,%d0
        bne     mra_1
        moveq   #1,%d1
        move.l  %d1,mp_backup
mra_1:  clr.l   mp_nowrite
        moveq   #-1,%d0                 | mp_saved matches nothing: the next save writes
        move.l  %d0,mp_saved
mra_9:  rts

FMT_MWORK: .asciz "%s/morph.work"
FMT_MSTRD: .asciz "%s/morph.strd"
FMT_MBAK:  .asciz "%s/morph.bak"
MP_MODE_R: .asciz "r"
MP_MODE_W: .asciz "w"

| ---------------------------------------------------------------- the [TRACK]-held key table
| The stock table 0x400d1594 record for record (0x1a bytes: code, 0, press, release, 16 zero
| bytes), UP and DOWN added before the terminator.
        .balign 4
mp_keys:
        KEYREC  0x27, 0x40083a7c, 0                 | STOP (stock)
        KEYREC  0x28, 0x40083a30, 0                 | PLAY (stock)
        KEYREC  0x2f, 0x40083ce0, 0                 | BANK (stock)
        KEYREC  0x31, 0x400834d8, 0x400834d8        | YES  (stock: ARM REC TRK)
        KEYREC  0x32, 0x40083488, 0x40083488        | NO   (stock: DISARM REC TRK)
        KEYREC  0x18, 0x400839dc, 0                 | 0x18 (stock)
        KEYREC  0x33, morph_up, 0                   | UP:   the MORPH window
        KEYREC  0x20, morph_down, 0                 | DOWN: MORPH STOP
        .byte   0xff, 0                             | terminator, as stock 0x400d1630
        .space  24

| ---------------------------------------------------------------- state (DRAM, writable)
        .balign 4
        .globl  mp_set
mp_state:  .byte 0, 0, 0, 0, 0, 0, 0, 0
mp_k:      .long 0, 0, 0, 0, 0, 0, 0, 0     | steps since the cycle began
mp_lastw:  .long 0                          | the step word at the last frame
mp_fsince: .long 0                          | frames since the last step (while playing)
| per track: STEPS (0 = the track's length), x, MODE (0 SMOOTH, 1 TRIG HOLD), pad
mp_set:    .byte 16, 8, 0, 0
           .byte 16, 8, 0, 0
           .byte 16, 8, 0, 0
           .byte 16, 8, 0, 0
           .byte 16, 8, 0, 0
           .byte 16, 8, 0, 0
           .byte 16, 8, 0, 0
           .byte 16, 8, 0, 0
        .balign 4
mw_win:    .long 0                          | the window, 0 = closed
mw_timer:  .long -1                         | its soft timer slot
mw_pushed: .long 0                          | the layer is pushed
mw_targets: .long 0                         | the window's tracks (bits)
mw_last:   .long -1                         | state << 16 | k the last paint showed
mw_insist: .long 0                          | detents to the right at x 16 (the easter egg)
mw_rx:     .long 0
mw_ry:     .long 0
mw_rstr:   .long 0
mw_buf:    .space 24
        .balign 4
| saving (morph.work)
mp_saved:  .byte 16, 8, 0, 0, 16, 8, 0, 0, 16, 8, 0, 0, 16, 8, 0, 0     | the payload on the card
           .byte 16, 8, 0, 0, 16, 8, 0, 0, 16, 8, 0, 0, 16, 8, 0, 0     | (no file: the defaults)
           .long 0, 0
mp_buf:    .space 40
mp_hdr:    .space 16
mp_nowrite: .long 0                         | morph.work refused: never written over
mp_backup: .long 0                          | the next write first copies it to morph.bak
mp_bad:    .long 0                          | morph.work refused (count)
mp_ioerr:  .long 0                          | morph.work not written (count)
mp_ctx:    .space 4120                      | STORE_CTX: the file object and its 4 KB buffer
mp_path:   .space 260
mp_psrc:   .space 260
