| MORPH v1.2 -- [TRACK]+[UP] / [TRACK]+[DOWN] / a track key held: a track's scene morph runs by itself.
|
| v1.2 (22 Nov 2026, the owner's ask: risers that come back "as if by hand"): three settings more
| per track on the window's encoders D, E, F (mp_ext), all 0 = v1.1 exactly:
|   * RET (D): how long the way back B -> A takes: SAME (as v1.1: half the cycle), 1/2 1/4 1/8 1/16
|     of the way up, BAR (16 steps), BEAT (4), STEP (1), CUT (none: back on A by the next step). The
|     way up is v1.1's (half of STEPS x x); the cycle is the way up plus the way back, rounded up to
|     whole steps (the morph stays on A for what is left of the last step).
|   * CURV (E): LIN, HAND (the way back fast at first, then soft: (1 - u)^2), RISE (the way up slow
|     at first, then fast: v^2), BOTH.
|   * END (F): LOOP (v1.1), ONCE (one cycle, then parked on A), STAY (up to B and held there, TOP;
|     the long press, [TRACK]+[DOWN] or the window's DOWN starts the way back on the next step, RET
|     long, then parked on A; a stop asked while still going up comes straight back at B).
|   * morph.work version 3 (72 bytes: version 2's 40 + the 8 tracks' RET, CURV, END, pad), written
|     only when one of them is not 0; otherwise version 2, as v1.1 writes, so v1.1 still reads it.
|
| A morphing track's A/B weight is not the crossfader's: every frame this unit writes it from a
| triangle A -> B -> A over one cycle of N sequencer 16th steps, always starting on A. The other
| tracks keep the crossfader. [TRACK]+[DOWN] lets the cycle finish on A; the track then stays
| PARKED on A until the crossfader reaches its A end (xf 127), and only then follows the fader.
|
| v1 (22 Oct 2026; v0 on the owner's MKI, ACIDV73MP, 21 Oct: the triangle, the keys, the parking;
| v1 on the unit as ACIDV74MP, 22 Oct):
|   * per track: STEPS (0 = the track's pattern length, 1..64), x (1..100; v1 had 1..16 and
|     41.625), MODE (SMOOTH / TRIG HOLD); N = STEPS * x, at most 6400. The defaults, 16 x 8
|     SMOOTH, are v0's 128 steps.
|   * the cycle follows the sequencer's step word instead of counting frames: k = the steps since
|     the start, so TRIG HOLD changes exactly on the steps and nothing drifts over many cycles;
|     SMOOTH adds the fraction of the step from the frames since the last step and the tempo.
|   * a start waits for the next step (ARMED), so the cycle begins on the grid.
|   * the window ([TRACK]+[UP], below) stays open; YES starts the held tracks on the next step,
|     NO starts nothing; either way they are ARMED, and a track key held ~1 s alone then starts and
|     stops that track (v1.1, 26 Oct 2026: the long press, below; also on the MIXER page). The
|     window shows the main page's scene indicator for its track.
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
        .globl  morph_frame, morph_up, morph_down, mp_keys, lp_tpress

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
        .set    S_HELD,   5              | in the window (was on the fader): YES starts it, NO leaves it
        .set    S_HELDP,  6              | in the window (was parked on A): YES starts it, NO parks it again
        .set    S_TOP,    7              | END STAY: held on B, the way back waits for the key
        .set    S_RETW,   8              | the way back asked: starts on the next step
        .set    S_RET,    9              | on the way back (END STAY), then parked on A
        .set    XMAX,     100            | x 1..100
        .set    RETMAX,   8              | RET: SAME 1/2 1/4 1/8 1/16 BAR BEAT STEP CUT
        .set    CURVMAX,  3              | CURV: LIN HAND RISE BOTH (bit 0 the way back, bit 1 the way up)
        .set    ENDMAX,   2              | END: LOOP ONCE STAY
        .set    E_ONCE,   1
        .set    E_STAY,   2
        .set    NMAX,     6400           | N = STEPS x x at most 64 x 100

| ---------------------------------------------------------------- the frame hook
| Detour 0x4000cc62 (jmp + 4 bytes of nop): replays `move.l #96,%macsr ; lea 12(%sp),%sp`.
morph_frame:
        move.l  #96,%macsr              | displaced
        lea     12(%sp),%sp             | displaced
mf_body:                                | (the source simulator enters here: it has no MACSR)
        lea     -48(%sp),%sp
        movem.l %d0-%d6/%a0-%a4,(%sp)
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
        lea     mp_ext,%a4              | per track: RET, CURV, END, (pad) (v1.2)
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
        beq     mf_8                    | in the window, from the fader: the fader keeps it
        bcs     mf_arm                  | 4: armed
        moveq   #S_HELDP,%d2
        cmp.l   %d2,%d1
        bne     mf_3t
        moveq   #127,%d2                | in the window, from PARK: A until the fader is at A
        cmp.l   XF,%d2
        bne     mf_w
        moveq   #S_HELD,%d1             | the fader is at A: in the window, the fader's
        move.b  %d1,(%a0)
        bra     mf_8
mf_3t:  moveq   #S_RETW,%d2
        cmp.l   %d2,%d1
        bcc     mf_3u
        moveq   #E_STAY,%d2             | 7: on B (END STAY)
        cmp.b   2(%a4),%d2
        beq     mf_top
        moveq   #S_RETW,%d1             | END turned from STAY: the way back, from the next step
        move.b  %d1,(%a0)
        bra     mf_top
mf_3u:
        bne     mf_ret                  | 9: on the way back
        tst.l   %d5                     | 8: the way back starts on the next step
        beq     mf_top
        moveq   #S_RET,%d1
        move.b  %d1,(%a0)
        clr.l   (%a1)
        bra     mf_r1                   | k = 0 is this step
mf_top: moveq   #0,%d2                  | B
        bra     mf_w
mf_arm:
        tst.l   %d5                     | armed: waits for a step
        beq     mf_8
        moveq   #S_RUN,%d1
        move.b  %d1,(%a0)
        clr.l   (%a1)                   | k = 0: this step is the cycle's first
        moveq   #127,%d2
        bra     mf_w
| ---- morphing (1, 2): the way up over L = N * 128 (a fraction of a step is 256), the way back
|      over T (mp_tlen), the cycle C = ceil((L + T) / 256) steps; END STAY: the way up only.
mf_run: bsr     mp_cycle                | d3 = N, d0 = C, a1 = this track's k
        move.l  %d0,mp_cyc              | (mp_cyc, mp_lup, mp_ldn: the frame's own scratch)
        move.l  %d3,%d0
        lsl.l   #7,%d0
        move.l  %d0,mp_lup              | L
        bsr     mp_tlen
        move.l  %d0,mp_ldn              | T
        moveq   #E_STAY,%d2             | STAY turned on while going back (k already past the
        cmp.b   2(%a4),%d2              | way up): parked on A, not a jump to B
        bne     mf_r0
        move.l  (%a1),%d0
        cmp.l   mp_cyc,%d0
        bcc     mf_park
mf_r0:  move.l  (%a1),%d0
        add.l   %d5,%d0                 | k += the steps of this frame
        cmp.l   mp_cyc,%d0
        bcs     mf_4
        moveq   #E_STAY,%d2             | the cycle ends
        cmp.b   2(%a4),%d2
        beq     mf_up_end               | (STAY: the step jumped past B)
        sub.l   mp_cyc,%d0
        moveq   #S_STOP,%d2
        cmp.l   %d2,%d1
        beq     mf_park                 | ... on A, as asked: parked
        moveq   #E_ONCE,%d2
        cmp.b   2(%a4),%d2
        beq     mf_park                 | ONCE: one cycle
mf_4:   cmp.l   mp_cyc,%d0
        bcs     mf_41
        moveq   #0,%d0                  | C shrank under k (a shorter pattern, a setting): from A again
mf_41:  move.l  %d0,(%a1)
        lsl.l   #8,%d0                  | pos = k * 256 + the fraction of the step (SMOOTH)
        tst.b   2(%a3)
        bne     mf_42                   | TRIG HOLD: the step's own value, for the whole step
        add.l   %d6,%d0
mf_42:  cmp.l   mp_lup,%d0
        bcc     mf_down
        lsl.l   #8,%d0                  | the way up: v = pos * 256 / L, 0..255
        move.l  mp_lup,%d2
        divu.l  %d2,%d0
        btst    #1,1(%a4)
        beq     mf_42l
        mulu.w  %d0,%d0                 | RISE: v^2 / 512, slow at first
        lsr.l   #8,%d0
mf_42l: lsr.l   #1,%d0                  | (LIN: v / 2 = v1.1's pos / N)
        moveq   #127,%d2
        sub.l   %d0,%d2                 | xf = 127 - that (A -> B)
        bra     mf_w
mf_down:                                | the way back: u = (pos - L) * 256 / T, 0..255
        moveq   #E_STAY,%d2
        cmp.b   2(%a4),%d2
        beq     mf_up_end               | STAY: B is reached
        sub.l   mp_lup,%d0
        move.l  mp_ldn,%d2
        bne     mf_back
        moveq   #127,%d2                | CUT: A for what is left of the cycle's last step
        bra     mf_w
mf_up_end:                              | STAY: on B; asked to stop meanwhile: the way back next
        clr.l   (%a1)
        moveq   #S_STOP,%d2
        cmp.l   %d2,%d1
        beq     mf_ue1
        moveq   #S_TOP,%d1
        move.b  %d1,(%a0)
        bra     mf_top
mf_ue1: moveq   #S_RETW,%d1
        move.b  %d1,(%a0)
        bra     mf_top
| ---- on the way back after STAY (9): T long from its first step, then parked on A
mf_ret: move.l  (%a1),%d0               | a1 = this track's k
        add.l   %d5,%d0
        move.l  %d0,(%a1)
mf_r1:  bsr     mp_len                  | d3 = N (RET's fractions), a1 again
        bsr     mp_tlen
        move.l  %d0,%d2                 | d2 = T
        move.l  (%a1),%d0
        lsl.l   #8,%d0
        tst.b   2(%a3)
        bne     mf_r3
        add.l   %d6,%d0
mf_r3:  cmp.l   %d2,%d0
        bcc     mf_park                 | the way back is over (CUT: at once)
mf_back:                                | d0 = the time into the way back, d2 = T (> d0)
        lsl.l   #8,%d0
        divu.l  %d2,%d0                 | u, 0..255
        move.l  #255,%d2
        cmp.l   %d2,%d0
        bls     mf_b1
        move.l  %d2,%d0
mf_b1:  btst    #0,1(%a4)
        beq     mf_b2
        sub.l   %d0,%d2                 | HAND: 127 - (255 - u)^2 / 512, fast at first
        mulu.w  %d2,%d2
        moveq   #9,%d0
        lsr.l   %d0,%d2
        moveq   #127,%d0
        sub.l   %d2,%d0
        move.l  %d0,%d2
        bra     mf_w
mf_b2:  lsr.l   #1,%d0                  | LIN: u / 2 (SAME: v1.1's pos / N - 128)
        move.l  %d0,%d2
        bra     mf_w
mf_park:
        moveq   #S_PARK,%d1
        move.b  %d1,(%a0)
        clr.l   (%a1)
        moveq   #127,%d2
mf_w:   lea     mp_xf,%a1               | d2 = xf: kept for the window's scene indicator
        move.b  %d2,(%a1,%d4.l)
        lea     CURVE,%a1               | the weight, exactly as the fader writers make it
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
        addq.l  #4,%a4
        addq.l  #1,%d4
        moveq   #8,%d0
        cmp.l   %d0,%d4
        bne     mf_2
mf_9:   movem.l (%sp),%d0-%d6/%a0-%a4
        lea     48(%sp),%sp
        jmp     RESUME

| mp_cycle -- d0 = C, the cycle in steps: ceil((L + T) / 256), L = N * 128 the way up, T the way
| back (END STAY: L alone), at least 1; d3 = N, a1 = this track's k (mp_len). d4 = the track, a3
| its settings, a4 its v1.2 settings. Registers only (the window calls it too). Clobbers d0, d2.
mp_cycle:
        bsr     mp_len
        bsr     mp_tlen
        moveq   #E_STAY,%d2
        cmp.b   2(%a4),%d2
        bne     mc_1
        moveq   #0,%d0                  | STAY: no way back in the cycle
mc_1:   move.l  %d3,%d2
        lsl.l   #7,%d2
        add.l   %d2,%d0
        add.l   #255,%d0
        lsr.l   #8,%d0
        rts

| mp_tlen -- d0 = T, the way back in 1/256 steps, from RET of the settings a4 and N = d3:
| SAME N * 128 (v1.1), 1/2 .. 1/16 of that, BAR 16 steps, BEAT 4, STEP 1, CUT 0. Clobbers d0, d2.
mp_tlen:
        mvz.b   (%a4),%d2               | RET
        moveq   #RETMAX,%d0
        cmp.l   %d0,%d2
        bls     mt_1
        moveq   #0,%d2                  | a stray value: SAME
mt_1:   moveq   #5,%d0
        cmp.l   %d0,%d2
        bcc     mt_fix
        moveq   #7,%d0                  | SAME .. 1/16: N << (7 - RET)
        sub.l   %d2,%d0
        move.l  %d3,%d2
        lsl.l   %d0,%d2
        move.l  %d2,%d0
        rts
mt_fix: subq.l  #5,%d2                  | BAR BEAT STEP CUT: 4096 >> (2 * (RET - 5)), CUT 0
        moveq   #3,%d0
        cmp.l   %d0,%d2
        bcs     mt_2
        moveq   #0,%d0
        rts
mt_2:   add.l   %d2,%d2
        move.l  #4096,%d0
        lsr.l   %d2,%d0
        rts

| mp_len -- d3 = N = STEPS * x for track d4 (a3 = its settings); STEPS 0 = the track's length in
| the current pattern (1..64, else 16). x 1..100 (N at most 6400). Clobbers d0, d2 (d1 is the state).
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
ml_2:   mvz.b   1(%a3),%d0              | x, 1..100
        moveq   #XMAX,%d2
        cmp.l   %d2,%d0
        bls     ml_3
        move.l  %d2,%d0
ml_3:   tst.l   %d0
        bne     ml_4
        moveq   #1,%d0
ml_4:   mulu.l  %d0,%d3
        move.l  #NMAX,%d0               | STEPS above 64 (a stray byte): 64 x 100
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
        bsr     lp_undo                 | a slow TRACK + UP: the long press it fired is undone
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

| mp_hold1 -- the track at a0: the fader's -> held, parked -> held from PARK (YES starts them, NO
| leaves them as they were); stopping -> morphing again; morphing, armed or held -> unchanged.
| Clobbers d0.
mp_hold1:
        mvz.b   (%a0),%d0
        beq     mh_hold
        subq.l  #S_STOP,%d0
        beq     mst_run
        subq.l  #S_PARK-S_STOP,%d0
        bne     mst_9
        moveq   #S_HELDP,%d0
        move.b  %d0,(%a0)
        rts
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
        bsr     lp_undo
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

| mp_stop1 -- the track at a0: morphing -> stopping (its cycle ends on A, then it is parked; END
| STAY: it comes back as soon as it is on B); on B (STAY) -> the way back on the next step; armed
| -> the fader's; anything else unchanged (a held track is the window's). Clobbers d0.
mp_stop1:
        mvz.b   (%a0),%d0
        subq.l  #S_RUN,%d0
        bne     ms_1
        moveq   #S_STOP,%d0
        move.b  %d0,(%a0)
        rts
ms_1:   subq.l  #S_ARMED-S_RUN,%d0
        bne     ms_3
        clr.b   (%a0)
ms_2:   rts
ms_3:   subq.l  #S_TOP-S_ARMED,%d0
        bne     ms_2
        moveq   #S_RETW,%d0
        move.b  %d0,(%a0)
        rts

| ---------------------------------------------------------------- the window
| [TRACK]+[UP] opens a TEMPO-class window over the page for the tracks held at that moment (the
| structure of ilia-murzinov's SEQ, modules/seq: WCREATE / WFRAME / WDESTROY, an
| input layer pushed over everything, the stock text and box routines, y counted up from the
| bottom). It stays open when the track keys are let go. While it is open:
|   A  STEPS (0 = TRK, the track's length, 1..64)     B  x (1..100)     C  MODE (SMOOTH / HOLD)
|   YES  close, and the held tracks start on the next step (from A)
|   NO or UP  close, nothing starts; the window's tracks stay ARMED for the long press (below)
|   DOWN  stop (as [TRACK]+[DOWN])
| Either way the window's tracks are ARMED (mp_prime): a track key held ~1 s alone then starts and
| stops that track's morph (the long press, below). A soft timer (~60 Hz) redraws the state, the
| step and the scenes when they change.
| The settings shown are the first window track's; an edit sets every window track to the value.
| From a key handler, as SEQ opens its window from the PAGE handler.
|
| The bottom row's right end is the stock scene indicator of the main page's footer, drawn the way
| stock draws it (measured, 26 Oct 2026): 0x4004d640 sets two boxes x 95..103 and 109..117, y 0..6,
| on the footer, writes scene A and scene B (bank + part * 0x18b2 + 0x8ed90 / 0x8ed91, from 0,
| shown from 1) with 0x40013904 (FONT, x 0x60 / 0x6e, y 1, "%02d" 0x400b437c, width "00"
| 0x400b4382, inverted); 0x4003577c sets the box x 104..108, y 0..6, clears y 2..4 and draws the
| 5 x 3 sprite 0x400bcd7c[4 - ((xf + 16) >> 5)], 0..4, at (104, 2). Here the same calls, moved to
| the window's bottom right corner, with the xf of the window's first track: its morph's while it
| morphs, A while it is parked, else the crossfader's.

        .set    WCREATE,  0x4005829c    | (w, h, 0, 0, class, closed) -> window
        .set    WFRAME,   0x40056f4c    | (window)
        .set    WDESTROY, 0x40055db4    | (&window)
        .set    CLEAR,    0x40035624    | (surface)
        .set    FONT,     0x400ba876    | the small UI font, 6 px
        .set    TEXT,     0x40012bd8    | (font, surface, x, y, limit, str)
        .set    TWIDTH,   0x40012f30    | (font, limit, str) -> pixels
        .set    RULE,     0x40011910    | (surface, x, y, x2, 1)
        .set    INVERT,   0x40012254    | (surface, x1, y1, x2, y2, mode): 1 set, 0 clear, -1 EOR
        .set    NUMTEXT,  0x40013904    | (font, surface, x, y, align, invert, width str, fmt, value)
        .set    SPRITE,   0x400128a8    | (sprite, surface, x, y)
        .set    SC_SPR,   0x400bcd7c    | the five indicator sprites, 5 x 3
        .set    SC_FMT,   0x400b437c    | "%02d"
        .set    SC_W,     0x400b4382    | "00"
        .set    PART,     0x80000003    | the current part (byte)
        .set    SCENES,   0x8ed90       | in the bank: scene A, scene B (bytes) + part * 0x18b2
        .set    PART_STRIDE,0x18b2
        .set    SPRINTF,  0x40013a08
        .set    LPUSH,    0x40031494    | (layer)
        .set    LPOP,     0x4003146c    | (layer)
        .set    TIMER,    0x40031a0c    | (period, callback) -> slot; ~0.5 s = 60
        .set    UNTIMER,  0x40031abc    | (slot)
        .set    SCRDIRTY, 0x46c7c72c
        .set    STOCK_TKEY, 0x40040250  | the stock track key handler (press, release, repeat)
        .set    ROWS,     0x46100b18    | the panel's key rows: code = row * 8 + bit
        .set    MIDIMODE, 0x80000012    | nonzero = MIDI mode
        .set    T_MASKS,  0x00240000    | rows 4..7 as a long: FUNC 0x2d, CUE 0x2a
        .set    WINW,     116
        .set    WINH,     64
        .set    Y_TITLE,  52            | v1.2: eight rows 7 px apart (the font is 6 high), in v1.1's
        .set    Y_MORPH,  45            | y 3..58 (WFRAME's frame and CLEAR's rim outside), no rule;
        .set    Y_STEPS,  38            | the state at the title's right, the step under the title
        .set    Y_MULT,   31
        .set    Y_MODE,   24
        .set    Y_RET,    17
        .set    Y_CURV,   10
        .set    Y_END,    3
        .set    X_LAB,    6
        .set    X_VAL,    112
        .set    X_TRK,    40            | the window tracks, after the title
        .set    X_SC,     89            | the scene indicator: x 89..111 (stock's 95..117)
        .set    Y_SC,     45            | y 45..51, in the step row (v1.1: y 3..9)
        .set    TICK,     2             | the soft timer's period: two ticks, ~17 ms
        .set    LONG,     58            | ~1 s of ticks for the long press

| mw_open -- d1 = the held tracks. Clobbers d0, d1, a0, a1.
mw_open:
        move.l  %d1,mw_targets
        moveq   #-1,%d0
        move.l  %d0,mw_last             | force the first paint
        move.l  mp_gen,%d0              | the project it belongs to (mp_apply counts loads)
        move.l  %d0,mw_gen
        clr.l   mw_go
        pea     mw_closed
        pea     5                       | TEMPO class: windows of the class evict each other
        clr.l   -(%sp)
        clr.l   -(%sp)
        pea     WINH
        pea     WINW
        jsr     WCREATE
        lea     24(%sp),%sp
        move.l  %d0,mw_win
        bne     mw_o1
        moveq   #-1,%d0                 | no window: the held tracks back as they were,
        move.l  %d0,mw_gen              | nothing ARMED
        bra     mw_closed
mw_o1:
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

| mw_close -- the window, the layer and the timer gone; safe when already closed. mw_go = 1 (YES):
| the held tracks start on the next step; 0: they go back to the fader, or to PARK.
mw_close:
        tst.l   mw_win
        beq     mw_c9
        pea     mw_win
        jsr     WDESTROY
        addq.l  #4,%sp
mw_closed:                              | WCREATE's callback: another window of the class took over
        clr.l   mw_win
        lea     mp_state,%a0            | (d0, d1, a0 only: a callback keeps d2-d7)
        moveq   #7,%d1
mw_cr:  mvz.b   (%a0,%d1.l),%d0
        subq.l  #S_HELD,%d0
        bcs     mw_cr2                  | not held
        cmp.l   #S_HELDP-S_HELD,%d0
        bhi     mw_cr2                  | (7..9: morphing, v1.2's)
        tst.l   mw_go
        bne     mw_cr_go
        tst.l   %d0
        beq     mw_cr_f
        moveq   #S_PARK,%d0             | it was parked: parked again
        bra     mw_cr_s
mw_cr_f: moveq  #S_FADER,%d0
        bra     mw_cr_s
mw_cr_go: moveq #S_ARMED,%d0
mw_cr_s: move.b %d0,(%a0,%d1.l)
mw_cr2: subq.l  #1,%d1
        bpl     mw_cr
        move.l  mw_gen,%d0              | a project loaded meanwhile, or no window: not ARMED
        cmp.l   mp_gen,%d0
        bne     mw_cr3
        move.l  mp_prime,%d0            | the window's tracks: ARMED for the long press
        or.l    mw_targets,%d0
        move.l  %d0,mp_prime
mw_cr3:
        clr.l   mw_go
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

| mw_tick -- the soft timer: repaints when the first track's state or step, or the scene indicator
| (its scenes and its position), changed.
mw_tick:
        tst.l   mw_win
        beq     mw_closed               | (gone without the callback: as NO, the timer and layer dropped)
        bsr     mw_first                | a0 = the first track's state, d0 = its index
        move.l  %d0,-(%sp)
        bsr     mw_sig                  | d0 = state << 16 | k
        cmp.l   mw_last,%d0
        bne     mw_t8
        move.l  (%sp)+,%d0
        bsr     mw_sc                   | d0 = the indicator's position << 16 | scene A << 8 | B
        cmp.l   mw_last2,%d0
        bne     mw_draw
        rts
mw_t8:  addq.l  #4,%sp
        bra     mw_draw

| mw_sig -- d0 = track d0's state << 16 | k (k < 6400). Clobbers d1, a0, a1.
mw_sig:
        lea     mp_state,%a0
        mvz.b   (%a0,%d0.l),%d1
        lsl.l   #2,%d0
        lea     mp_k,%a1
        move.l  (%a1,%d0.l),%d0
        swap    %d1
        clr.w   %d1
        or.l    %d1,%d0
        rts

| mw_sc -- d0 = track d0's scene indicator: its position (0..4, stock's formula) << 16 | scene A
| << 8 | scene B (from 0; 0 0 without a bank). Clobbers d1, a0, a1.
mw_sc:
        lea     mp_state,%a0
        mvz.b   (%a0,%d0.l),%d1
        cmp.l   #S_HELDP,%d1
        bhi     msc_m                   | 7..9 (STAY: on B, on the way back): its own
        subq.l  #S_RUN,%d1
        beq     msc_m
        subq.l  #S_STOP-S_RUN,%d1
        beq     msc_m
        subq.l  #S_PARK-S_STOP,%d1
        beq     msc_a
        subq.l  #S_HELDP-S_PARK,%d1
        beq     msc_a
        move.l  XF,%d1                  | the fader's
        bra     msc_x
msc_a:  moveq   #127,%d1                | parked: A
        bra     msc_x
msc_m:  lea     mp_xf,%a0               | morphing: its own
        mvz.b   (%a0,%d0.l),%d1
msc_x:  moveq   #16,%d0                 | 4 - ((xf + 16) >> 5), 0..4 (0x400357cc)
        add.l   %d0,%d1
        asr.l   #5,%d1
        moveq   #4,%d0
        sub.l   %d1,%d0
        bpl     msc_1
        moveq   #0,%d0
msc_1:  moveq   #4,%d1
        cmp.l   %d1,%d0
        ble     msc_2
        move.l  %d1,%d0
msc_2:  move.l  %d0,%a1                 | the position
        moveq   #0,%d0
        move.l  BANK_PTR,%d1
        beq     msc_9
        move.l  %d1,%a0
        mvz.b   PART,%d0
        and.l   #3,%d0
        move.l  #PART_STRIDE,%d1
        muls.l  %d1,%d0
        add.l   %d0,%a0
        add.l   #SCENES,%a0
        mvz.w   (%a0),%d0               | scene A << 8 | scene B
        and.l   #0x0f0f,%d0             | 16 scenes
msc_9:  move.l  %a1,%d1
        swap    %d1
        clr.w   %d1
        or.l    %d1,%d0
        rts

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
mw_yes:                                 | YES: close; the held tracks start on the next step
        moveq   #1,%d0
        cmp.l   8(%sp),%d0
        bne     mw_k9
        move.l  %d0,mw_go
        bra     mw_close

mw_no:                                  | NO, UP: close; nothing starts
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

| mw_enc -- encoder (index @4, delta @8): A STEPS 0..64, B x 1..100, C MODE 0..1 (any turn to the
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
        bne     mw_e_ext                | D..F: RET, CURV, END (v1.2)
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
        add.l   %d1,%d0
        moveq   #1,%d1
        cmp.l   %d1,%d0
        bge     mw_e_m1
        move.l  %d1,%d0
mw_e_m1: moveq  #XMAX,%d1
        cmp.l   %d1,%d0
        ble     mw_e_m2
        move.l  %d1,%d0
mw_e_m2: moveq  #1,%d1
        bra     mw_e_set
mw_e_ext:                               | D RET 0..8, E CURV 0..3, F END 0..2, by one a click
        subq.l  #1,%d0                  | 0 RET, 1 CURV, 2 END
        moveq   #2,%d1
        cmp.l   %d1,%d0
        bhi     mw_k9
        bsr     mw_first                | d0 = the first track (d1 clobbered)
        lsl.l   #2,%d0
        lea     mp_ext,%a1
        add.l   %d0,%a1
        move.l  4(%sp),%d0
        subq.l  #3,%d0
        add.l   %d0,%a1                 | a1 = the first track's byte
        lea     MW_XMAX,%a0
        add.l   %d0,%a0                 | a0 = its largest value
        moveq   #1,%d1                  | one value a click, whatever the speed
        tst.l   8(%sp)
        bpl     mw_x0
        moveq   #-1,%d1
mw_x0:  mvz.b   (%a1),%d0
        add.l   %d1,%d0
        bpl     mw_x1
        moveq   #0,%d0
mw_x1:  mvz.b   (%a0),%d1
        cmp.l   %d1,%d0
        ble     mw_x2
        move.l  %d1,%d0
mw_x2:  move.l  4(%sp),%d1
        subq.l  #3,%d1                  | the byte: 0 RET, 1 CURV, 2 END
        lea     mp_ext,%a0
        bra     mw_e_setx
| d0 = the value, d1 = the byte (0 STEPS, 1 x, 2 MODE): set on every window track
mw_e_set:
        lea     mp_set,%a0
mw_e_setx:                              | (a0 = mp_ext: 0 RET, 1 CURV, 2 END)
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
| MORPH  T1                         (the window tracks)
| ──────────────────────
| MORPH  T1                 ON      (the window tracks; OFF / ARM / WAIT / ON / STOP / PARK /
|                                    TOP / RET)
|  STEP 12/128      [01]-[09]       (CYCLE 128 when not morphing, BACK 2/4 on the way back;
|                                    the stock scene indicator)
|  STEPS (A)            16          (TRK = the track's length)
|  x (B)                 8
|  MODE (C)         SMOOTH          (SMOOTH / HOLD)
|  RET (D)            SAME          (SAME 1/2 1/4 1/8 1/16 BAR BEAT STEP CUT)
|  CURV (E)            LIN          (LIN HAND RISE BOTH)
|  END (F)            LOOP          (LOOP ONCE STAY)
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
        moveq   #X_TRK,%d0
        moveq   #Y_TITLE,%d1
        lea     mw_buf,%a0
        bsr     mw_text
        bsr     mw_first                | d0 = track, a0 = state, a1 = settings
        move.l  %d0,%d6
        move.l  %a1,%a3
        mvz.b   (%a0),%d7               | the state
        move.l  %d6,%d0                 | a4 = its v1.2 settings (mp_cycle, mp_tlen)
        lsl.l   #2,%d0
        lea     mp_ext,%a4
        add.l   %d0,%a4
| the state, on the right of the title
        lea     V_STATE,%a0             | 5 bytes a name: OFF ON STOP PARK WAIT ARM ARM TOP RET RET
        move.l  %d7,%d0
        mulu.w  #5,%d0
        add.l   %d0,%a0
        moveq   #X_VAL,%d0
        moveq   #Y_TITLE,%d1
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
        bsr     mw_num
        moveq   #X_VAL,%d0
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
| RET, CURV, END rows (v1.2)
        moveq   #X_LAB,%d0
        moveq   #Y_RET,%d1
        lea     L_RET,%a0
        bsr     mw_text
        lea     V_RET,%a0
        mvz.b   (%a4),%d0
        moveq   #RETMAX,%d1
        bsr     mw_name
        moveq   #X_VAL,%d0
        moveq   #Y_RET,%d1
        bsr     mw_rtext
        moveq   #X_LAB,%d0
        moveq   #Y_CURV,%d1
        lea     L_CURV,%a0
        bsr     mw_text
        lea     V_CURV,%a0
        mvz.b   1(%a4),%d0
        moveq   #CURVMAX,%d1
        bsr     mw_name
        moveq   #X_VAL,%d0
        moveq   #Y_CURV,%d1
        bsr     mw_rtext
        moveq   #X_LAB,%d0
        moveq   #Y_END,%d1
        lea     L_END,%a0
        bsr     mw_text
        lea     V_END,%a0
        mvz.b   2(%a4),%d0
        moveq   #ENDMAX,%d1
        bsr     mw_name
        moveq   #X_VAL,%d0
        moveq   #Y_END,%d1
        bsr     mw_rtext
| the step, while morphing: STEP k/C; on the way back after STAY: BACK k/R; else CYCLE C
        move.l  %d6,%d4                 | mp_cycle: d4 = the track, a3, a4 its settings
        bsr     mp_cycle                | d0 = C, d3 = N
        move.l  %d0,%d3                 | d3 = C
        moveq   #S_RUN,%d0
        cmp.l   %d0,%d7
        beq     mw_d3
        moveq   #S_STOP,%d0
        cmp.l   %d0,%d7
        beq     mw_d3
        moveq   #S_RET,%d0
        cmp.l   %d0,%d7
        beq     mw_d3r
        move.l  %d3,-(%sp)              | not morphing: the cycle the settings make
        pea     F_CYC
        pea     mw_buf
        jsr     SPRINTF
        lea     12(%sp),%sp
        bra     mw_d5
mw_d3r: bsr     mp_len                  | d3 = N again
        bsr     mp_tlen                 | d0 = T
        add.l   #255,%d0
        lsr.l   #8,%d0
        bne     mw_d3q
        moveq   #1,%d0                  | CUT: one step
mw_d3q: move.l  %d0,%d3                 | d3 = R, the way back in steps
        lea     F_BACK,%a0
        bra     mw_d3k
mw_d3:  lea     F_POS,%a0
mw_d3k: move.l  %d6,%d0
        lsl.l   #2,%d0
        lea     mp_k,%a1
        move.l  (%a1,%d0.l),%d5         | k
        cmp.l   %d3,%d5                 | C just shrank under k (an encoder): the frame puts
        bcs     mw_d3b                  | k back in range; until then 0
        moveq   #0,%d5
mw_d3b: move.l  %d3,-(%sp)
        addq.l  #1,%d5
        move.l  %d5,-(%sp)              | the step, from 1
        move.l  %a0,-(%sp)
        pea     mw_buf
        jsr     SPRINTF
        lea     16(%sp),%sp
mw_d5:  moveq   #X_LAB,%d0
        moveq   #Y_MORPH,%d1
        lea     mw_buf,%a0
        bsr     mw_text
| the scene indicator, stock's
        move.l  %d6,%d0
        bsr     mw_sc
        move.l  %d0,mw_last2
        move.l  %d0,%d5                 | d5 = position << 16 | A << 8 | B
        moveq   #X_SC,%d0               | scene A's box and number
        moveq   #Y_SC,%d1
        moveq   #X_SC+8,%d2
        moveq   #Y_SC+6,%d3
        moveq   #1,%d4
        bsr     mw_box
        move.l  %d5,%d2
        lsr.l   #8,%d2
        and.l   #15,%d2
        moveq   #X_SC+1,%d0
        bsr     mw_scnum
        moveq   #X_SC+14,%d0            | scene B's
        moveq   #Y_SC,%d1
        moveq   #X_SC+22,%d2
        moveq   #Y_SC+6,%d3
        moveq   #1,%d4
        bsr     mw_box
        move.l  %d5,%d2
        and.l   #15,%d2
        moveq   #X_SC+15,%d0
        bsr     mw_scnum
        moveq   #X_SC+9,%d0             | the position between them
        moveq   #Y_SC,%d1
        moveq   #X_SC+13,%d2
        moveq   #Y_SC+6,%d3
        moveq   #1,%d4
        bsr     mw_box
        moveq   #X_SC+9,%d0
        moveq   #Y_SC+2,%d1
        moveq   #X_SC+13,%d2
        moveq   #Y_SC+4,%d3
        moveq   #0,%d4
        bsr     mw_box
        pea     Y_SC+2
        pea     X_SC+9
        move.l  %a5,-(%sp)
        swap    %d5
        and.l   #7,%d5
        lsl.l   #2,%d5
        lea     SC_SPR,%a0
        move.l  (%a0,%d5.l),%d0         | (ColdFire: no indexed source to -(sp))
        move.l  %d0,-(%sp)
        jsr     SPRITE
        lea     16(%sp),%sp
mw_d4:
| what this paint showed, for mw_tick
        move.l  %d6,%d0
        bsr     mw_sig
        move.l  %d0,mw_last
        moveq   #1,%d0
        move.l  %d0,SCRDIRTY
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     44(%sp),%sp
mw_d99: rts

| mw_name -- a0 = the name d0 of the 5-byte table a0 (d1 = the largest; a stray value: the
| first). Clobbers d0.
mw_name:
        cmp.l   %d1,%d0
        bls     mwn_1
        moveq   #0,%d0
mwn_1:  mulu.w  #5,%d0
        add.l   %d0,%a0
        rts

| mw_box -- INVERT(a5, d0, d1, d2, d3, d4): 1 set, 0 clear. Clobbers d0, d1, a0, a1.
mw_box:
        move.l  %d4,-(%sp)
        move.l  %d3,-(%sp)
        move.l  %d2,-(%sp)
        move.l  %d1,-(%sp)
        move.l  %d0,-(%sp)
        move.l  %a5,-(%sp)
        jsr     INVERT
        lea     24(%sp),%sp
        rts

| mw_scnum -- scene d2 (from 0) as "%02d" from 1, at x = d0, y = Y_SC + 1, inverted: stock's
| 0x40013904 call. Clobbers d0, d1, a0, a1.
mw_scnum:
        move.l  %d2,%d1
        addq.l  #1,%d1
        move.l  %d1,-(%sp)
        pea     SC_FMT
        pea     SC_W
        pea     1
        clr.l   -(%sp)
        pea     Y_SC+1
        move.l  %d0,-(%sp)
        move.l  %a5,-(%sp)
        pea     FONT
        jsr     NUMTEXT
        lea     36(%sp),%sp
        rts

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

| ---------------------------------------------------------------- the long press
| A track key held ~1 s alone (as TRACK MENU v1 measured it on the owner's MKI, 24 Oct 2026): the
| PRESS field of the eight track records of the MKI key table 0x400bfc10 and the MKII one
| 0x400c01f4 (press = release = repeat = 0x40040250) points at lp_tpress, which calls the stock
| handler first, then counts with a soft timer while that track key stays the only key down (HELD
| 0x460fab40 = 1 << t, the panel rows 0x46100b18 show no key that was not down at the press).
| FUNC or CUE down at the press (mute, cue), MIDI mode, our window open, another key, another
| track or the release: nothing. At ~1 s, on an ARMED track (mp_prime: it has been in the window):
| on the fader or parked -> it starts on the next step (from A); morphing -> it stops at the end
| of its cycle, on A, then parks there (as [TRACK]+[DOWN]); stopping -> it carries on; waiting for
| its step -> back to the fader. A toast says which: T2 MORPH ON / T2 MORPH OFF.
| d0/d1/a0/a1 only (d2-d7 are the caller's).
lp_tpress:
        move.l  8(%sp),-(%sp)           | event
        move.l  8(%sp),-(%sp)           | code (4(sp) before the first push)
        jsr     STOCK_TKEY
        addq.l  #8,%sp
        moveq   #1,%d0
        cmp.l   8(%sp),%d0
        bne     lp_rel                  | release, repeat
        tst.l   mw_win
        bne     lp_9                    | our window is open
        mvz.b   MIDIMODE,%d0
        bne     lp_9
        move.l  4(%sp),%d0
        sub.l   #0x10,%d0
        moveq   #7,%d1
        cmp.l   %d1,%d0
        bhi     lp_9                    | not a track key
        move.l  ROWS+4,%d1              | FUNC or CUE down: mute / cue
        and.l   #T_MASKS,%d1
        bne     lp_x
        move.l  %d0,lp_cand
        clr.l   lp_count
        addq.l  #8,%d0                  | row 2 is the third byte of the first long
        moveq   #1,%d1
        lsl.l   %d0,%d1
        not.l   %d1
        and.l   ROWS,%d1
        move.l  %d1,lp_snap0
        move.l  ROWS+4,%d1
        move.l  %d1,lp_snap1
        tst.l   lp_timer
        bpl     lp_9
        pea     lp_tick
        pea     TICK
        jsr     TIMER
        addq.l  #8,%sp
        move.l  %d0,lp_timer
lp_9:   rts
lp_rel: move.l  lp_ut,%d0               | the key of the last long press let go: no undo now
        bmi     lp_9
        moveq   #1,%d1
        lsl.l   %d0,%d1
        and.l   HELD,%d1                | (stock has just updated HELD)
        bne     lp_9
        moveq   #-1,%d0
        move.l  %d0,lp_ut
        rts
| lp_undo -- the long press fired while its key is still down, and that key turns out to be the
| first of a combination ([TRACK] + [UP] / [DOWN]): its track back to the state it had. Clobbers
| d0, d1, a0.
lp_undo:
        move.l  lp_ut,%d0
        bmi     lu_9
        moveq   #-1,%d1
        move.l  %d1,lp_ut
        moveq   #1,%d1
        lsl.l   %d0,%d1
        and.l   HELD,%d1
        beq     lu_9                    | let go meanwhile: it stands
        lea     mp_state,%a0
        move.l  lp_us,%d1
        move.b  %d1,(%a0,%d0.l)
lu_9:   rts
lp_x:   moveq   #-1,%d0
        move.l  %d0,lp_cand
        rts

| lp_tick -- the long press's soft timer. d0/d1/a0/a1 only.
lp_tick:
        move.l  lp_cand,%d0
        bmi     lp_untimer
        tst.l   mw_win
        bne     lp_cancel               | our window came (TRACK + UP)
        moveq   #1,%d1
        lsl.l   %d0,%d1
        cmp.l   HELD,%d1
        bne     lp_cancel               | released, or another track too
        addq.l  #8,%d0
        moveq   #1,%d1
        lsl.l   %d0,%d1
        or.l    lp_snap0,%d1
        not.l   %d1
        and.l   ROWS,%d1
        bne     lp_cancel               | a key that was not down at the press
        move.l  lp_snap1,%d1
        not.l   %d1
        and.l   ROWS+4,%d1
        bne     lp_cancel
        addq.l  #1,lp_count
        move.l  lp_count,%d0
        moveq   #LONG,%d1
        cmp.l   %d1,%d0
        blt     lp_t9
lp_long:                                | the time is up (a label for the port's --watch-pc)
        move.l  lp_cand,%d0
        move.l  %d0,lp_t
        moveq   #-1,%d0
        move.l  %d0,lp_cand
        bsr     lp_untimer
        move.l  lp_t,%d0
        lea     mp_state,%a0
        add.l   %d0,%a0
        mvz.b   (%a0),%d1
        move.l  %d1,lp_us               | (for lp_undo)
        beq     lp_a0                   | the fader's
        subq.l  #S_RUN,%d1
        beq     lp_off                  | morphing: stop at the cycle's end
        subq.l  #S_STOP-S_RUN,%d1
        beq     lp_on_r                 | stopping: carry on
        subq.l  #S_PARK-S_STOP,%d1
        beq     lp_a0                   | parked
        subq.l  #S_ARMED-S_PARK,%d1
        bne     lp_top
        clr.b   (%a0)                   | waiting for its step: back to the fader
        lea     V_TOFF,%a1
        bra     lp_toast
lp_top: subq.l  #S_TOP-S_ARMED,%d1
        bne     lp_t9                   | held (the window's), or already on the way back
        moveq   #S_RETW,%d1             | on B (END STAY): the way back, from the next step
        move.b  %d1,(%a0)
        lea     V_TOFF,%a1
        bra     lp_toast
lp_a0:  move.l  mp_prime,%d1            | not ARMED: nothing
        btst    %d0,%d1
        beq     lp_t9
        moveq   #S_ARMED,%d1
        move.b  %d1,(%a0)
        lea     V_TON,%a1
        bra     lp_toast
lp_on_r: moveq  #S_RUN,%d1
        move.b  %d1,(%a0)
        lea     V_TON,%a1
        bra     lp_toast
lp_off: moveq   #S_STOP,%d1
        move.b  %d1,(%a0)
        lea     V_TOFF,%a1
lp_toast:                               | "T2 MORPH ON": NOTIFY(text, 0x30), as stock's toasts
        move.l  lp_t,%d0                | done while the key is down: lp_undo can take it back
        move.l  %d0,lp_ut
        move.l  %a1,-(%sp)
        move.l  lp_t,%d0
        addq.l  #1,%d0
        move.l  %d0,-(%sp)
        pea     F_TOAST
        pea     lp_tbuf
        jsr     SPRINTF
        lea     16(%sp),%sp
        pea     0x30
        pea     lp_tbuf
        jsr     NOTIFY
        addq.l  #8,%sp
        rts
lp_cancel:
        moveq   #-1,%d0
        move.l  %d0,lp_cand
lp_untimer:
        move.l  lp_timer,%d0
        bmi     lp_t9
        move.l  %d0,-(%sp)
        jsr     UNTIMER
        addq.l  #4,%sp
        moveq   #-1,%d0
        move.l  %d0,lp_timer
lp_t9:  rts

S_STOP_T: .asciz "MORPH STOP"
T_TITLE: .asciz "MORPH"
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
        .asciz  "ARM"
        .byte   0
        .asciz  "TOP"                   | v1.2: 7 on B (END STAY), 8 and 9 on the way back
        .byte   0
        .asciz  "RET"
        .byte   0
        .asciz  "RET"
        .byte   0
L_RET:  .asciz  "RET (D)"
L_CURV: .asciz  "CURV (E)"
L_END:  .asciz  "END (F)"
V_RET:  .asciz  "SAME"                  | 5 bytes a name
        .asciz  "1/2"
        .byte   0
        .asciz  "1/4"
        .byte   0
        .asciz  "1/8"
        .byte   0
        .asciz  "1/16"
        .asciz  "BAR"
        .byte   0
        .asciz  "BEAT"
        .asciz  "STEP"
        .asciz  "CUT"
        .byte   0
V_CURV: .asciz  "LIN"
        .byte   0
        .asciz  "HAND"
        .asciz  "RISE"
        .asciz  "BOTH"
V_END:  .asciz  "LOOP"
        .asciz  "ONCE"
        .asciz  "STAY"
MW_XMAX: .byte  RETMAX, CURVMAX, ENDMAX
V_TRK:  .asciz  "TRK"
V_SMOOTH: .asciz "SMOOTH"
V_HOLD: .asciz  "HOLD"
V_TON:  .asciz  "ON"
V_TOFF: .asciz  "OFF"
F_NUM:  .asciz  "%d"
F_POS:  .asciz  "STEP %d/%d"
F_CYC:  .asciz  "CYCLE %d"
F_BACK: .asciz  "BACK %d/%d"
F_TOAST: .asciz "T%d MORPH %s"

| ---- the window's layer (pushed while it is open): {next, keys, encoders, +12, +16, -1, -1}
        .balign 4
MW_LAYER:
        .long   0, MW_KEYS, MW_ENCS, 0, 0, -1, -1
MW_KEYS:
        KEYREC  0x31, mw_yes, 0                     | YES:  close, the held tracks start
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
        .byte   3, 0                                | D: RET (v1.2)
        .long   mw_enc, 0, 0, 0, 0
        .byte   4, 0                                | E: CURV
        .long   mw_enc, 0, 0, 0, 0
        .byte   5, 0                                | F: END
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
| v1.2: version 3, length 72: the same 40 bytes, then mp_ext (8 tracks x RET, CURV, END, pad);
| written only when one of those is not 0, else version 2 as before (a v1.1 image still reads
| what a v1.2 one wrote unless the new settings are used). Versions 1, 2 and 3 are read.
| STORE's handlers may clobber every register (modules/store/README.md).
        .globl  mrp_st_loadall_post, mrp_st_loadmask_post, mrp_st_newproj, mrp_st_bankw_post
        .globl  mrp_st_pstore_pre, mrp_st_pstore_post, mrp_st_preload_post, mrp_st_answer
| store_path, store_fopen, store_fread, store_fwrite, store_fclose, store_crc32 and store_refuse
| are STORE's (undefined here: the link resolves them).
        .set    MP_MAGIC, 0x4d525057     | 'MRPW'
        .set    MP_LEN,   40             | versions 1 and 2 (v1, v1.1)
        .set    MP_LEN3,  72             | version 3 (v1.2): + RET, CURV, END, pad of the 8 tracks
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
        subq.l  #S_TOP-S_ARMED,%d2      | on B (STAY): morphing too
        bne     mb_3
mb_on:  moveq   #1,%d2
        lsl.l   %d1,%d2
        or.l    %d2,%d0
mb_3:   subq.l  #1,%d1
        bpl     mb_2
        move.l  %d0,%d1
        lsl.l   #8,%d1
        move.l  mp_prime,%d0            | the ARMED tracks (v1.1; v1 wrote 0)
        and.l   #0xff,%d0
        or.l    %d0,%d1
        lsl.l   #8,%d1
        lsl.l   #8,%d1                  | the two masks in the first bytes, two zero bytes
        move.l  %d1,(%a1)+
        clr.l   (%a1)+
        lea     mp_ext,%a0              | v1.2: bytes 40..71
        moveq   #8,%d1
mb_4:   move.l  (%a0)+,(%a1)+
        subq.l  #1,%d1
        bne     mb_4
        rts

| mp_save -- write morph.work when the payload differs from mp_saved. Clobbers everything.
mp_save:
        tst.l   mp_nowrite
        bne     mps_9
        bsr     mp_build
        lea     mp_buf,%a0
        lea     mp_saved,%a1
        moveq   #MP_LEN3/4,%d1
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
mps_3:  moveq   #2,%d0                  | version 2 (v1.1: x to 100, the ARMED byte), 40 bytes,
        moveq   #MP_LEN,%d1             | unless a v1.2 setting is used: version 3, 72
        lea     mp_buf+MP_LEN,%a0
        moveq   #8,%d2
mps_3a: tst.l   (%a0)+
        bne     mps_3b
        subq.l  #1,%d2
        bne     mps_3a
        bra     mps_3c
mps_3b: moveq   #3,%d0
        moveq   #MP_LEN3,%d1
mps_3c: move.l  %d0,mp_wver
        move.l  %d1,mp_wlen
        lea     mp_buf,%a0
        move.l  mp_wlen,%d0
        moveq   #0,%d1
        jsr     store_crc32
        lea     mp_hdr,%a0
        move.l  %d0,12(%a0)
        move.l  #MP_MAGIC,%d0
        move.l  %d0,(%a0)
        move.l  mp_wver,%d0
        move.l  %d0,4(%a0)
        move.l  mp_wlen,%d0
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
        move.l  mp_wlen,%d0
        jsr     store_fwrite
        move.l  %d0,%d3
        jsr     store_fclose
        subq.l  #1,%d2
        bne     mps_8
        subq.l  #1,%d3
        bne     mps_8
        lea     mp_buf,%a0              | written: the payload on the card
        lea     mp_saved,%a1
        moveq   #MP_LEN3/4,%d1
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
        move.l  4(%a0),%d0              | version 1 (v1), 2 (v1.1): 40 bytes; 3 (v1.2): 72
        move.l  %d0,mp_ver
        moveq   #MP_LEN,%d1
        subq.l  #1,%d0
        moveq   #1,%d2
        cmp.l   %d2,%d0
        bls     mpl_1
        moveq   #MP_LEN3,%d1
        subq.l  #2,%d0
        bne     mpl_bad
mpl_1:  cmp.l   8(%a0),%d1
        bne     mpl_bad
        move.l  %d1,mp_wlen
        lea     mp_buf+MP_LEN,%a0       | a 40-byte payload: the v1.2 settings 0 (as v1.1)
        moveq   #8,%d1
mpl_2:  clr.l   (%a0)+
        subq.l  #1,%d1
        bne     mpl_2
        lea     mp_buf,%a0
        move.l  mp_wlen,%d0
        jsr     store_fread
        subq.l  #1,%d0
        bne     mpl_bad
        jsr     store_fclose
        lea     mp_buf,%a0
        move.l  mp_wlen,%d0
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
        moveq   #2,%d0
        move.l  %d0,mp_ver
        lea     mp_buf,%a0
        moveq   #8,%d1
        move.l  #0x10080000,%d0         | 16, 8, SMOOTH, pad
mpd_1:  move.l  %d0,(%a0)+
        subq.l  #1,%d1
        bne     mpd_1
        moveq   #10,%d1                 | the masks, and the v1.2 settings: SAME LIN LOOP
mpd_2:  clr.l   (%a0)+
        subq.l  #1,%d1
        bne     mpd_2
| mp_apply -- mp_buf (a payload) into mp_set and the states, each value clamped; mp_saved = it.
| The tracks that morphed are armed: they start from A on the first step after PLAY. The others
| go to the fader, a track that was not on the fader by way of PARK (held on A until the fader
| is at A, as after a stop: its weight is not left where its morph was).
mp_apply:
        addq.l  #1,mp_gen               | a new project's settings: a window open now is the old one's
        lea     mp_buf,%a0
        lea     mp_set,%a1
        moveq   #0,%d1                  | t
mpa_1:  mvz.b   (%a0),%d0               | STEPS 0..64
        cmp.l   #64,%d0
        bls     mpa_2
        moveq   #16,%d0
mpa_2:  move.b  %d0,(%a1)
        mvz.b   1(%a0),%d0              | x 1..100
        moveq   #17,%d2                 | version 1's 17 was 41.625: 42 now
        cmp.l   %d2,%d0
        bne     mpa_2x
        moveq   #1,%d2
        cmp.l   mp_ver,%d2
        bne     mpa_2x
        moveq   #42,%d0
mpa_2x: cmp.l   #XMAX,%d0
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
        mvz.b   1(%a0),%d0              | the ARMED tracks (v1.1)
        move.l  %d0,mp_prime
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
        lea     mp_buf+MP_LEN,%a0       | v1.2: RET, CURV, END, each clamped (a stray value: 0)
        lea     mp_ext,%a1
        moveq   #8,%d1
mpa_11: lea     MW_XMAX,%a2
        moveq   #3,%d3
mpa_12: mvz.b   (%a0)+,%d0
        mvz.b   (%a2)+,%d2
        cmp.l   %d2,%d0
        bls     mpa_13
        moveq   #0,%d0
mpa_13: move.b  %d0,(%a1)+
        subq.l  #1,%d3
        bne     mpa_12
        addq.l  #1,%a0                  | the pad: 0
        clr.b   (%a1)+
        subq.l  #1,%d1
        bne     mpa_11
        bsr     mp_build                | what is on the card (clamped values: a rewrite if any was)
        lea     mp_buf,%a0
        lea     mp_saved,%a1
        moveq   #MP_LEN3/4,%d1
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
| per track, v1.2: RET (0 SAME .. 8 CUT), CURV (0 LIN 1 HAND 2 RISE 3 BOTH), END (0 LOOP 1 ONCE
| 2 STAY), pad; all 0 = v1.1
        .balign 4
mp_ext:    .long 0, 0, 0, 0, 0, 0, 0, 0
mp_cyc:    .long 0                          | the frame's scratch: C, L, T of the track at hand
mp_lup:    .long 0
mp_ldn:    .long 0
mw_win:    .long 0                          | the window, 0 = closed
mw_timer:  .long -1                         | its soft timer slot
mw_pushed: .long 0                          | the layer is pushed
mw_targets: .long 0                         | the window's tracks (bits)
mw_last:   .long -1                         | state << 16 | k the last paint showed
mw_last2:  .long -1                         | the scene indicator the last paint showed
mw_go:     .long 0                          | YES: the held tracks start when the window closes
mp_prime:  .long 0                          | ARMED: the tracks the long press starts and stops
lp_cand:   .long -1                         | the long press: the track key down, or -1
lp_count:  .long 0
lp_snap0:  .long 0
lp_snap1:  .long 0
lp_timer:  .long -1
lp_t:      .long 0
lp_ut:     .long -1                         | the track the last long press acted on while held
lp_us:     .long 0                          | its state before
mp_gen:    .long 0                          | loads so far (mp_apply)
mw_gen:    .long 0                          | mp_gen when the window opened, -1 without a window
mp_ver:    .long 2                          | the version of the file read
mp_xf:     .byte 127, 127, 127, 127, 127, 127, 127, 127   | each track's xf, the frame's
lp_tbuf:   .space 24
        .balign 4
mw_rx:     .long 0
mw_ry:     .long 0
mw_rstr:   .long 0
mw_buf:    .space 24
        .balign 4
| saving (morph.work)
mp_saved:  .byte 16, 8, 0, 0, 16, 8, 0, 0, 16, 8, 0, 0, 16, 8, 0, 0     | the payload on the card
           .byte 16, 8, 0, 0, 16, 8, 0, 0, 16, 8, 0, 0, 16, 8, 0, 0     | (no file: the defaults)
           .long 0, 0
           .long 0, 0, 0, 0, 0, 0, 0, 0     | (v1.2: SAME LIN LOOP)
mp_buf:    .space 72
mp_wver:   .long 2                          | the version and length mp_save writes (mp_load: read)
mp_wlen:   .long 40
mp_hdr:    .space 16
mp_nowrite: .long 0                         | morph.work refused: never written over
mp_backup: .long 0                          | the next write first copies it to morph.bak
mp_bad:    .long 0                          | morph.work refused (count)
mp_ioerr:  .long 0                          | morph.work not written (count)
mp_ctx:    .space 4120                      | STORE_CTX: the file object and its 4 KB buffer
mp_path:   .space 260
mp_psrc:   .space 260
