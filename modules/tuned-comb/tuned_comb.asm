; ---------------------------------------------------------------------------
; TUNED COMB -- a feedback comb with a one-pole lowpass in the loop, whose
; loop length is solved each block so the loop's pole sits on the sounding
; fundamental: PTCH stays in tune at any LP and FB. Proven against
; modules/tuned-comb/tuned_comb_ref.py (verify_tuned_comb.py).
;
; Insert contract (frames in place at x:(r0), L then R, n7 of them; knobs
; from r6; state in the r7 block). Init reads the allocator base (X:0x213 ->
; this instance's entry); a base >= 0x4000 is an FX2 slot and, unless SLOTS
; is FX1+FX2, proc returns at once, writing nothing. Two lines of 1,536
; words out of the FX1 slot's 3,072: L at the base, R at base + 1,536; each
; is N = 1,533 data words plus 3 guard words that mirror words 0..2, so the
; four Hermite taps never wrap (they read descending, from TM). FX1 bases are not
; all 2048-aligned, so the lines are linear: the write index wraps by
; compare.
;
; Per block: the pitch s = PTCH + (TUNE - 64)/64 semitones above A#0; P =
; SR/f0 (Q12.11) and phi0 = 1/P from E2 and the shift table SH; the sounding
; phase phis = phi0 (FB > 0) or phi0/2 (FB < 0); sin/cos of it from the
; stock sine at X:0x6c00; b = 1 - a from BLP; then three fixed-point steps
; of the pole solve (rho = a/r):
;   psi  = atan2(rho sin, 1 - rho cos) in cycles (one div, ATN)
;   1/L  = phi0 / (1 - k psi)               (one div; k = 1, or 2 for FB < 0)
;   lr   = min(0, (log2(|g| b) - log2|q|) / L)   (LG2, logs in 1/32)
;   rho  = a / 2^lr                          (SH, E2, one div)
; then lr = (lr3 + 0.1 lr2)/1.1 (the iteration converges oscillating), psi
; once more, L = P (1 - k psi), less the Hermite read's own phase-delay
; error at phis, clamped to 3 .. 1,530 samples. The delay walks to L in a
; straight line, a 16th of the way a sample.
;
; Per sample, each channel: v = herm(d), y += b (v - y), hp = x - dc
; (rounded) and dc += hp/1024 (the input's DC blocker, about 6.9 Hz: a
; positive loop's gain at DC is up to 500, and it sits outside the loop so
; the pitch solve is untouched), s = hp + g y, written at the advanced index
; (and its guard twin), out = x + m (s - x).
;
; The r7 block ($00..$3f, all zeroed at init):
;   $00 write index (persistent)    $01 delay d, Q11.12 (persistent)
;   $02 slope (per block)           $03/$04 L's input DC, high, low (persistent)
;   $05 b    $06 g                  $07 MIX run (persistent)  $08 MIX step
;   $09 primed                      $0a line base (init)      $0b FX2 flag (init)
;   $0c P table base                $0d P, Q12.11             $0e phi0
;   $0f phis                        $10 sin   $11 cos         $12 a = 1 - b
;   $13 log2(|g| b)/32              $14 k - 1 (0 or 1)        $15 rho
;   $16 psi   $18 lr (persistent)   $19 1/L
;   $1a L, Q12.11                   $1b f (the per-block Hermite's)
;   $1c..$24 scratch (per block)    $25/$26 R's input DC, high, low (persistent)

;   $27..$2a the last PTCH/TUNE/LP/FB words   $2b warm steps left   $2c steps this block
;   $2d iterating (LP closed)   $2e FB - 64 (2^-16)   $2f lr1 x 128
;   $30 scratch (per block; the frame count across the loop)
;   $31..$34 lowpass y L high, L low, R high, R low (persistent)
;   $35 PTCH, TUNE or FB moved this block   $36 warm change (per block)
;   $37 the steps pending   $38/$39 b, g pending   $3a..$3c b, g, L kept   $3d..$3f free
;
; Every mpy/mac is `x0,y1`, the order dsp_asm encodes signed (AGENTS.md).
; AND and ASL leave A2 stale: every value passing through one leaves via a1.
; ---------------------------------------------------------------------------

init:
; ---- every slot to zero (verify_dirty_state). r5, never r1: the FX1
; dispatcher keeps the effect id in r1 across this call (verify_init_regs).
        clr     a
        move    r7,r5
        move    #>$ffffff,m5
        do      #$40,>tq01z
        move    a,x:(r5)+
tq01z:
        nop
; ---- the allocator base, and the FX1/FX2 decision ------------------------
        move    x:>$213,r4
        move    #>$ffffff,m4
        move    x:(r4),x0
        move    x0,x:(r7+$0a)           ; the line base
; sub/tst rather than cmp: the cmp-encodes-as-max family (AGENTS.md).
        move    x0,a
        move    #>$4000,x0
        sub     x0,a                    ; base - 0x4000
        clr     b                       ; b = 0 BEFORE the tst (the flag trap)
        move    #>$1,x0
        tst     a
        tpl     x0,b                    ; base >= 0x4000: an FX2 slot
        move    b,x:(r7+$0b)
        tst     b
        bne     tq02z                   ; FX2: never touch the buffer at all
; ---- clear both lines, once, at instantiation ----------------------------
        move    x:(r7+$0a),a
        move    a,r5
        move    #>$ffffff,m5
        clr     a
        do      #3072,>tq03z
        move    a,y:(r5)+
tq03z:
        nop
tq02z:
        rts

; ===========================================================================
proc:
; ===========================================================================
        move    x:(r7+$0b),a
        tst     a
        bne     tq99_dry                ; an FX2 instance: the frames pass dry
        move    #>$ffffff,m5
        move    #>$ffffff,m4
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$fab1e0,r5            ; the ptable's base, placed by the build
        move    r5,x:(r7+$0c)           ; (the build wants the literal once)
; ---- has PTCH, TUNE, LP or FB moved? -----------------------------------------
; A change (or the first block): the closed form, or with LP closed the
; iteration: a small change (the knobs' moves, each over its limit -- PTCH 1
; semitone, TUNE 8, FB and LP 4 -- summing to at most 1) from a block that
; was iterating takes one warm step from the last lr; any other a cold start
; (lr = 0) and two steps. Then one warm step a block for six blocks; then the
; solve is frozen (b, g and L are kept) until the next change.
; With LP closed a change after the first block is split over two blocks,
; to halve the peak under a moving knob: this block the setup and the gain
; (b and g held back, the loop keeping last block's b, g and L), the next
; the steps and L, which apply b, g and L together; that block reads no
; knobs (a move then waits a block).
        move    x:(r7+$37),a
        tst     a
        bne     tq58_b                  ; the steps of last block's change
        clr     b                       ; the moves, over their limits
        move    x:(r6+$0),a
        and     #>$7f0000,a             ; PTCH (its integer only is read)
        move    a1,x0
        move    x:(r7+$27),a
        sub     x0,a
        move    x0,x:(r7+$27)
        abs     a                       ; (one semitone: 1)
        add     a,b
        move    x:(r6+$1),a
        and     #>$7fff00,a             ; TUNE, with its LFO fraction
        move    a1,x0
        move    x:(r7+$28),a
        sub     x0,a
        move    x0,x:(r7+$28)
        abs     a
        asr     #$3,a,a                 ; (8 units: 1)
        add     a,b
        move    x:(r6+$3),a
        and     #>$7fff00,a             ; FB
        move    a1,x0
        move    x:(r7+$2a),a
        sub     x0,a
        move    x0,x:(r7+$2a)
        abs     a
        asr     #$2,a,a                 ; (4 units: 1)
        add     a,b
        move    b,x:(r7+$35)            ; PTCH, TUNE or FB: the pitch's setup too
        move    x:(r6+$2),a
        and     #>$7fff00,a             ; LP
        move    a1,x0
        move    x:(r7+$29),a
        sub     x0,a
        move    x0,x:(r7+$29)
        abs     a
        asr     #$2,a,a                 ; (4 units: 1)
        add     a,b
        move    x:(r7+$09),a
        tst     a
        bne     tq45z
        move    #>$7fffff,b             ; unprimed: a cold change
        move    b,x:(r7+$35)
tq45z:
        tst     b
        beq     tq40_same
        move    #>$010000,x0
        tfr     b,a
        clr     b
        cmp     x0,a                    ; the moves - 1
        move    x:(r7+$2d),x1           ; iterating last block (moves keep the flags)
        tle     x1,b                    ; small: warm if it was iterating
        move    b,x:(r7+$36)            ; warm
        move    #>$2,a
        sub     b,a                     ; steps: 2 cold, 1 warm ...
        move    x:(r7+$35),b
        tst     b
        move    #>$2,x0
        tne     x0,a                    ; ... 2 if PTCH, TUNE or FB moved (the split's B block)
        move    a1,x:(r7+$2c)
        bra     tq41_solve
tq40_same:
        move    x:(r7+$2b),a
        tst     a
        beq     tq42_kept               ; settled: the solve is frozen
        sub     #$1,a                   ; (6-bit immediate)
        move    a1,x:(r7+$2b)
        move    #>$1,x0
        move    x0,x:(r7+$2c)
        move    r5,a                    ; the table pointers, for the solve:
        move    a1,r1                   ;   E2 (+0)
        add     #>$41,a
        move    a1,r3                   ;   LG2 (+65)
        add     #>$21,a
        move    a1,r2                   ;   ATN (+98)
        add     #>$42,a
        move    a1,n0                   ;   SH (+164)
        bra     tq50_iter               ; a warm step: nothing it reads has moved
tq58_b:
        clr     a
        move    a,x:(r7+$37)
        move    x:(r7+$38),x0
        move    x0,x:(r7+$05)           ; b and g, held back a block
        move    x:(r7+$39),x0
        move    x0,x:(r7+$06)
        move    r5,a                    ; the table pointers, for the solve:
        move    a1,r1                   ;   E2 (+0)
        add     #>$41,a
        move    a1,r3                   ;   LG2 (+65)
        add     #>$21,a
        move    a1,r2                   ;   ATN (+98)
        add     #>$42,a
        move    a1,n0                   ;   SH (+164)
        bra     tq50_iter
tq41_solve:
        move    r5,a                    ; the table pointers, for the solve:
        move    a1,r1                   ;   E2 (+0)
        add     #>$41,a
        move    a1,r3                   ;   LG2 (+65)
        add     #>$21,a
        move    a1,r2                   ;   ATN (+98)
        add     #>$42,a
        move    a1,n0                   ;   SH (+164)
        move    x:(r7+$05),x0           ; the loop's b, g and L, kept for a split
        move    x0,x:(r7+$3a)
        move    x:(r7+$06),x0
        move    x0,x:(r7+$3b)
        move    x:(r7+$1a),x0
        move    x0,x:(r7+$3c)
; ---- LP: b from BLP (127 is exactly 1: the loop unfiltered), a = 1 - b ----
        move    x:(r7+$0c),a
        add     #>$83,a                 ; BLP at +131
        move    a1,r5
        move    x:(r6+$2),a
        bsr     tq11_k33
        move    a,x0
        move    x:(r6+$2),a
        and     #>$7f0000,a
        move    a1,b
        move    #>$7f0000,x1
        move    #>$7fffff,y1
        move    x0,a
        cmp     x1,b                    ; LP - 127
        tge     y1,a                    ; 127: b = 1
        move    a,x:(r7+$05)            ; b
        move    a,x0
        move    #>$7fffff,a
        sub     x0,a
        move    a,x:(r7+$12)            ; a = 1 - b (0 at LP 127)
        move    x:(r7+$35),a
        tst     a
        beq     tq44z                   ; only LP moved: P, phis, sin, cos kept
; ---- the pitch: S = PTCH << 16 + (TUNE - 64) << 10, in 2^-16 semitones ----
        move    x:(r6+$0),a             ; PTCH
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a                    ; clean
        move    #>$5f0000,x0            ; at most 95 (A8)
        cmp     x0,a
        tgt     x0,a
        move    a1,y0                   ; PTCH << 16
        move    x:(r6+$1),a             ; TUNE, with its LFO fraction
        and     #>$7fff00,a
        move    a1,x0
        move    x0,a                    ; clean
        move    #>$400000,x0
        sub     x0,a                    ; (TUNE - 64) << 16
        asr     #$6,a,a                 ; ... / 64 semitones, in 2^-16
        move    a1,x0
        move    y0,a
        add     x0,a                    ; S (-65536 .. 95 << 16 + 63 << 10)
        move    a1,x0
        move    #>$0aaaab,y1            ; 1/12
        mpy     x0,y1,a                 ; U = S/12, in 2^-16 octaves (a1)
        move    a1,x1                   ; U
; oct = U >> 16 (-1 .. 7), fr = (U & $ffff) << 7, Q23
        move    x1,a
        asr     #$10,a,a
        move    a1,x:(r7+$1e)           ; oct
        move    x1,a
        and     #>$00ffff,a
        asl     #$7,a,a
        move    a1,x:(r7+$1c)           ; fr
; P = 2 P0 E2(fr) SH[oct + 1]
        move    r1,r5                   ; E2 at +0
        move    x:(r7+$1c),a
        bsr     tq10_t64                ; E2(fr), 0.5 .. 1
        move    a,x0
        move    #>$5e9a1a,y1            ; 2 P0, Q12.11 (2 x 3,099,917)
        mpy     x0,y1,a                 ; 2 P0 E2(fr), an integer in a1
        move    a1,x:(r7+$1d)
        move    x:(r7+$1e),a
        add     #$1,a                   ; oct + 1, 0 .. 8 (6-bit immediate)
        move    a1,n5
        move    n0,r5                   ; SH at +164
        move    (r5)+n5
        move    p:(r5),y1               ; 2^-(oct + 1)
        move    x:(r7+$1d),x0
        mpy     x0,y1,a
        move    a1,x:(r7+$0d)           ; P, Q12.11
; phi0 = CPHI E2(1 - fr) SH[7 - oct]
        move    #>$7fffff,a
        move    x:(r7+$1c),x0
        sub     x0,a                    ; 1 - fr
        move    r1,r5
        bsr     tq10_t64                ; E2(1 - fr)
        move    a,x0
        move    #>$15a60b,y1            ; 2^8 / P0
        mpy     x0,y1,a
        move    a,x:(r7+$1d)
        move    x:(r7+$1e),x0
        move    #>$7,a
        sub     x0,a                    ; 7 - oct, 0 .. 8
        move    a1,n5
        move    n0,r5
        move    (r5)+n5
        move    p:(r5),y1
        move    x:(r7+$1d),x0
        mpy     x0,y1,a
        move    a,x:(r7+$0e)            ; phi0 = 1/P, cycles a sample
; ---- FB: the polarity (below 64: k = 2, the octave down) and FB - 64 ------
        move    x:(r6+$3),a
        and     #>$7fff00,a
        move    a1,x0
        move    x0,a                    ; clean
        move    #>$400000,x0
        sub     x0,a                    ; FB - 64, in 2^-16 (signed)
        move    a1,x:(r7+$2e)
        clr     b
        move    #>$1,x0
        move    a1,x1
        move    x1,a                    ; clean
        tst     a
        tlt     x0,b                    ; FB < 0: k = 2 (the octave down)
        move    x:(r7+$14),a
        sub     b,a
        beq     tq46z                   ; k as it was
        clr     a                       ; the octave flips: cold
        move    a,x:(r7+$36)
        move    #>$2,x0
        move    x0,x:(r7+$2c)
tq46z:
        move    b,x:(r7+$14)
        move    x:(r7+$0e),a
        tst     b
        beq     tq04z
        asr     #$1,a,a                 ; phis = phi0/2
tq04z:
        move    a1,x:(r7+$0f)           ; phis
; ---- sin and cos of the sounding phase -------------------------------------
        move    x:(r7+$0f),x1
        bsr     tq12_sin
        move    a,x:(r7+$10)            ; sin
        move    x:(r7+$0f),a
        add     #>$200000,a
        move    a1,x1
        bsr     tq12_sin
        move    a,x:(r7+$11)            ; cos
tq44z:
; ---- the solve ---------------------------------------------------------------
; FB is a decay time: T60 = 0.05 s x 600^d, d = |FB - 64|/63 (at most 1), the
; pole's radius r a sample (log2 r = lr1). The gain is the law's with LP open,
; at most G_MAX (0.998: a positive loop near 1 rings at DC); LP closed
; shortens the decay. With LP open the solve is closed-form; with LP closed
; the pitch is the iteration's at that gain (two steps cold, then one warm
; step a block for six blocks). FB 64: no feedback.
        move    x:(r7+$36),a
        tst     a
        bne     tq47z                   ; warm: lr kept
        move    a,x:(r7+$18)            ; lr = 0 (the cold start, if capped)
tq47z:
        clr     a
        move    a,x:(r7+$2d)            ; not capped
        move    a,x:(r7+$2b)            ; no warm steps
        move    x:(r7+$2e),a
        tst     a
        bne     tq51_dec
        clr     a
        move    a,x:(r7+$06)            ; FB 64: g = 0
        bsr     tq15_rho                ; lr = 0: rho = a (L on the circle)
        bra     tq52_len
tq51_dec:
; y = LOG2_SPAN d, as y/16 = 1.172 |FB - 64|; lr1 x 128 = -LRS0 2^-y
        abs     a
        move    #>$3f0000,x0
        cmp     x0,a
        tgt     x0,a                    ; d at most 1 (FB 0 is -63)
        move    a,x0
        move    #>$160143,y1
        mpy     x0,y1,a                 ; 0.172 m
        add     x0,a                    ; y/16
        move    a1,x1
        move    x1,a
        asr     #$13,a,a                ; n = floor(y), 0 .. 9
        move    a1,x:(r7+$1f)
        move    x1,a
        and     #>$07ffff,a
        asl     #$4,a,a                 ; frac, Q23
        move    r1,r5                   ; E2
        bsr     tq10_t64
        bsr     tq60_shn                ; x 2^-n: 2^-y
        move    a,x0
        move    #>$4a0cb4,y1            ; LRS0 = 128 x 3 log2(10) / (SR x 0.05 s)
        mpy     x0,y1,a
        neg     a
        move    a,x:(r7+$2f)            ; lr1 x 128 (< 0)
; the gain from the law as if LP were open: |g| = 2^(L0 lr1) / |S|, L0 the
; loop on the lowpass's circle (rho = a), S the Hermite read's response at w
; (its loss a pass). LP closed then shortens the decay, so the comb's DC mode
; (which LP leaves alone) never rings longer than the note's T60.
        clr     a
        bsr     tq15_rho                ; lr = 0: rho = a
        bsr     tq16_psi
        bsr     tq53_L                  ; L0 at $1a
        move    x:(r7+$2f),x0           ; lr1 x 128
        move    x:(r7+$1a),y1           ; L0, Q12.11: L0/4096 as a fraction
        mpy     x0,y1,a                 ; L0 lr1 / 32
        move    a,x:(r7+$30)
        bsr     tq17_herm               ; the read's phase error out of L (LP open: the final L)
        bsr     tq61_S                  ; ... and S where the read now is: its loss a pass
        move    x:(r7+$23),x0           ; re/2
        move    x0,y1
        mpy     x0,y1,a
        move    x:(r7+$24),x0           ; im/2
        move    x0,y1
        mac     x0,y1,a                 ; |S|^2 / 4
        bsr     tq13_log2
        add     #>$080000,a             ; + 2/32: log2|S|^2 / 32
        asr     #$1,a,a                 ; log2|S| / 32
        move    a1,x0
        move    x:(r7+$30),a
        sub     x0,a                    ; log2|g| / 32
        move    #>$fffd0b,x0            ; log2(G_MAX) / 32
        cmp     x0,a
        bgt     tq54_cap
; |g| = 2^lgg: -lgg = n + frac, SH[n] E2(frac); n over 10 is 0
        neg     a
        move    a,x1
        move    x1,a
        asr     #$12,a,a
        move    a1,b
        move    a1,x:(r7+$1f)
        move    #>$b,x0
        cmp     x0,b
        bge     tq55_zero
        move    x1,a
        and     #>$03ffff,a
        asl     #$5,a,a
        move    r1,r5
        bsr     tq10_t64
        bsr     tq60_shn                ; |g|
        bra     tq56_sign
tq54_cap:
        move    #>$7fbe77,a             ; at most G_MAX
        bra     tq56_sign
tq55_zero:
        clr     a
tq56_sign:
        move    a,y1
        neg     a
        move    x:(r7+$2e),b
        tst     b
        tgt     y1,a                    ; FB above 64: +|g|; below: -|g|
        move    a,x:(r7+$06)            ; g
; LP open: the closed form is exact (no lowpass lag), L at $1a is final
        move    x:(r7+$12),a            ; a = 1 - b
        tst     a
        beq     tq42_kept
; LP closed: the pitch by the iteration at this g (two steps cold, then one
; warm step a block for six blocks)
        move    #>$1,x0
        move    x0,x:(r7+$2d)           ; iterating
        move    #>$6,x0
        move    x0,x:(r7+$2b)           ; warm steps to come
        move    x:(r7+$36),a
        tst     a
        bne     tq59z                   ; warm: one step from the last lr
        move    a,x:(r7+$18)            ; lr = 0: the cold start
tq59z:
        move    x:(r7+$09),a
        tst     a
        beq     tq50_iter               ; the first block: all of it now
        move    x:(r7+$05),x0
        move    x0,x:(r7+$38)           ; b and g wait for the steps
        move    x:(r7+$06),x0
        move    x0,x:(r7+$39)
        move    x:(r7+$3a),x0
        move    x0,x:(r7+$05)
        move    x:(r7+$3b),x0
        move    x0,x:(r7+$06)
        move    x:(r7+$3c),x0
        move    x0,x:(r7+$1a)           ; the loop keeps last block's b, g and L
        move    #>$1,x0
        move    x0,x:(r7+$37)           ; the steps next block
        bra     tq42_kept
tq50_iter:
        move    x:(r7+$06),a
        abs     a
        move    #>$010000,x0
        cmp     x0,a
        tlt     x0,a                    ; |g| at least 1/128 for the log
        move    a,x0
        move    x:(r7+$05),y1
        mpy     x0,y1,a                 ; |g| b
        bsr     tq13_log2
        move    a,x:(r7+$13)            ; log2(|g| b) / 32
        bsr     tq14_step               ; lr at $18, rho at $15
        move    x:(r7+$2c),a
        move    #>$2,x0
        cmp     x0,a
        blt     tq43z                   ; one step: a warm step or a warm change
        bsr     tq14_step               ; the second step of a change block
tq43z:
        nop
tq52_len:
        bsr     tq16_psi
        bsr     tq53_L                  ; L = P (1 - k psi), at $1a
tq57_herm:
; ---- the Hermite read's own phase-delay error at phis -----------------------
        bsr     tq17_herm
; ---- clamp to 3 .. 1,530 samples, to Q11.12 --------------------------------
tq42_kept:
        move    x:(r7+$1a),a
        move    #>$001800,x0            ; 3, Q12.11
        cmp     x0,a
        tlt     x0,a
        move    #>$2fd000,x0            ; 1,530, Q12.11
        cmp     x0,a
        tgt     x0,a
        asl     #$1,a,a
        move    a1,b                    ; the knot, Q11.12
        move    x:(r7+$09),a
        tst     a
        move    x:(r7+$01),a            ; the delay now (moves keep the flags)
        teq     b,a                     ; the first block: on the knot
        move    a,x:(r7+$01)
        sub     a,b
        add     #$8,b                   ; rounded (6-bit immediate)
        asr     #$4,b,b                 ; a 16th of the way a sample
        move    b,x:(r7+$02)
; ---- MIX: VIBRATO's run, without the duck ----------------------------------
        move    x:(r6+$5),a
        and     #>$7fff00,a
        move    #$7f,x0                 ; (short immediate: bits 23-16)
        cmp     x0,a                    ; k - 127
        move    #>$7fffff,x0
        tge     x0,a                    ; 127: the wet outright
        move    a1,x1                   ; the target m
        move    x1,a
        move    x:(r7+$07),b            ; the run
        sub     b,a
        move    a,y1                    ; target - run
        abs     a
        cmp     #>$80,a                 ; under 128 LSBs: snap
        bge     tq07_mg
        move    x1,x:(r7+$07)
        clr     a
        move    a,x:(r7+$08)
        bra     tq08z
tq07_mg:
        move    y1,a
        asr     #$7,a,a
        move    a,x:(r7+$08)
tq08z:
        move    #>$1,x0
        move    x0,x:(r7+$09)           ; primed
; ---- the sample loop -------------------------------------------------------
; Loop-carried values live in address registers, so the loop reads none of
; them back: r3 = d (n3 its slope, stepped by the AGU), r2 = the MIX run (n2
; its step), n0 = b, n7 = g and n1 = f (both per sample). r1 walks the lowpass state,
; $31..$34 = y L (high, low), y R (high, low); r5 reads L's four taps then
; R's ($600 - 3 on), r4 and r6 write L's s and its twin then R's ($600 on).
; Each sample: i and f from d, j = w - i - 1 (wrapped), the next write index
; w' and its twin; then each channel inline. Bit-identical to the loop it
; replaced (one channel routine, state at r7 offsets); README "Load".
        move    x:(r7+$01),r3           ; d
        move    x:(r7+$02),n3           ; its slope
        move    x:(r7+$07),r2           ; the MIX run
        move    x:(r7+$08),n2           ; its step
        move    x:(r7+$05),n0           ; b
        move    #>$600,n4
        move    #>$600,n6
        move    #>$603,n5               ; $600 + 3: L's T2 to R's TM
        lua     (r7+$33),r1             ; (two steps back each sample)
        move    n7,x:(r7+$30)           ; the frame count, restored below
        move    (r3)+n3                 ; d for the first sample
        do      n7,>tq09z               ; (n7 then holds g, reloaded each sample)
; ---- shared: i, f, j, w' and the twin ------------------------------------
        move    r3,a                    ; d, Q11.12
        asr     #$c,a,a                 ; i; d's 12 fraction bits atop a0
        move    x:(r7+$00),x1           ; w, the last index written
        move    x:(r7+$06),n7           ; g (do has its count)
        move    a0,b
        lsr     b       (r2)+n2         ; f, Q23 (b1); the MIX run steps
        move    a1,y0                   ; i
        tfr     x1,a    (r1)-
        sub     y0,a    (r1)-           ; w - i
        move    b1,n1                   ; f (after r1's steps: the AGU set)
        move    #>$5fd,x0               ; N
        add     #$2,a                   ; j + 3, j = w - i - 1
        move    x:(r7+$0a),y1           ; the line base
        tfr     a,b
        add     x0,b                    ; + N
        cmp     #$3,a
        tlt     b,a                     ; j < 0: wrapped
        add     y1,a                    ; L's TM (the taps read down)
        clr     b
        move    a1,r5
        tfr     x1,a
        add     #$1,a
        cmp     x0,a
        tge     b,a                     ; w' (N -> 0)
        tfr     a,b
        move    a1,x:(r7+$00)
        add     x0,b                    ; w' + N
        cmp     #$3,a
        tge     a,b                     ; under 3: the twin at + N; else itself
        add     y1,a    y:(r5)-,x0      ; TM
        add     y1,b    y:(r5)-,y0      ; T0
        move    a1,r4                   ; L's s here
        move    b1,r6                   ; ... and here
; ---- channel L -----------------------------------------------------------
; Taps T2 T1 T0 TM, oldest first; the Hermite in eighths (Niemitalo's form):
;   c1 = (T1 - TM)/2,  c3 = 3(T0 - T1)/2 + (T2 - TM)/2,  c2 = TM - T0 + c1 - c3
;   v  = ((c3 f + c2) f + c1) f + T0
; C1 = c1/8 and C3 = c3/8 rounded (their floors bias v, and the loop holds a
; bias as DC); y += b (v - y) in 48 bits; hp = x - dc rounded, dc += hp/1024
; in 48 bits; s = hp + g y truncated toward zero (a rounded loop holds a limit
; cycle); out = x + m (s - x), the dry as it came.
        move    y:(r5)-,y1              ; T1
        tfr     y1,a    y:(r5)+n5,b     ; T2; r5 -> R's TM
        sub     x0,b                    ; T2 - TM
        sub     x0,a                    ; T1 - TM
        asr     #$4,a,a
        rnd     a                       ; C1
        asr     #$4,b,b                 ; (T2 - TM)/16
        tfr     y0,a    a,x1            ; x1 = C1
        sub     y1,a                    ; T0 - T1
        asr     #$4,a,a
        rnd     a                       ; u = (T0 - T1)/16
        add     a,b
        add     a,b
        add     a,b
        rnd     b                       ; C3
        tfr     x0,a
        sub     y0,a                    ; TM - T0
        asr     #$3,a,a
        add     x1,a                    ; + C1
        sub     b,a     b,x0            ; C2; x0 = C3
        move    n1,y1                   ; f
        mpy     x0,y1,b                 ; C3 f
        add     a,b                     ; + C2
        move    b,x0
        mpy     x0,y1,a x:(r1)+,b       ; y, high word
        add     x1,a    x:(r1)-,b0      ; + C1; y, low word
        move    x:(r0),x1               ; the dry x
        move    a,x0
        mpy     x0,y1,a
        asl     #$3,a,a
        add     y0,a                    ; + T0 (x 8 first: the same sum)
        rnd     a
        move    n0,y1                   ; b
        move    a,x0                    ; v (limited)
        tfr     x0,a
        sub     b,a                     ; v - y (|.| < 2)
        asr     #$1,a,a
        rnd     a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a                     ; y + b (v - y), 48 bits
        move    n7,y1                   ; g
        move    a1,x:(r1)+
        move    a0,x:(r1)+
        move    a,x0                    ; y (limited)
        move    x:(r7+$03),a            ; the input's DC, high
        move    x:(r7+$04),a0           ; ... and low
        tfr     x1,b                    ; the dry x
        sub     a,b                     ; x - dc
        rnd     b                       ; hp (a floor is a DC the loop holds)
        move    b,y0                    ; hp (limited)
        asr     #$a,b,b                 ; hp/1024, exact
        add     b,a                     ; dc += hp/1024, 48 bits
        move    a1,x:(r7+$03)
        move    a0,x:(r7+$04)
        mpy     x0,y1,a
        add     y0,a                    ; s = hp + g y, 56 bits
        tfr     a,b                     ; its sign
        abs     a
        move    r2,y1                   ; m
        move    a,x1                    ; |s|, floored (and limited)
        tfr     x1,a
        neg     a
        tst     b
        tge     x1,a                    ; s >= 0: +|s|
        move    x:(r0),b                ; the dry
        move    a,x1                    ; s
        tfr     x1,a    x1,y:(r4)+n4    ; at the next index; r4 -> R
        sub     b,a
        asr     #$1,a,a
        move    x1,y:(r6)+n6            ; ... and its twin; r6 -> R
        move    a,x0                    ; (s - x)/2
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a     y:(r5)-,x0      ; R's TM
        move    y:(r5)-,y0              ; R's T0
        move    a,x:(r0)+ y:(r5)-,y1    ; out L; R's T1
; ---- channel R: the same -------------------------------------------------
        tfr     y1,a    y:(r5),b        ; T2
        sub     x0,b
        sub     x0,a
        asr     #$4,a,a
        rnd     a
        asr     #$4,b,b
        tfr     y0,a    a,x1
        sub     y1,a
        asr     #$4,a,a
        rnd     a
        add     a,b
        add     a,b
        add     a,b
        rnd     b
        tfr     x0,a
        sub     y0,a
        asr     #$3,a,a
        add     x1,a
        sub     b,a     b,x0
        move    n1,y1
        mpy     x0,y1,b
        add     a,b
        move    b,x0
        mpy     x0,y1,a x:(r1)+,b
        add     x1,a    x:(r1)-,b0
        move    x:(r0),x1
        move    a,x0
        mpy     x0,y1,a
        asl     #$3,a,a
        add     y0,a
        rnd     a
        move    n0,y1
        move    a,x0
        tfr     x0,a
        sub     b,a
        asr     #$1,a,a
        rnd     a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    n7,y1
        move    a1,x:(r1)+
        move    a0,x:(r1)-              ; (r1 back to y R; L's two steps below)
        move    a,x0
        move    x:(r7+$25),a            ; R's input DC
        move    x:(r7+$26),a0
        tfr     x1,b
        sub     a,b
        rnd     b
        move    b,y0
        asr     #$a,b,b
        add     b,a
        move    a1,x:(r7+$25)
        move    a0,x:(r7+$26)
        mpy     x0,y1,a
        add     y0,a
        tfr     a,b
        abs     a
        move    r2,y1
        move    a,x1
        tfr     x1,a
        neg     a
        tst     b
        tge     x1,a
        move    x:(r0),b
        move    a,x1
        tfr     x1,a    x1,y:(r4)
        sub     b,a
        asr     #$1,a,a
        move    x1,y:(r6)
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    (r3)+n3                 ; d for the next sample
        move    a,x:(r0)+               ; out R
tq09z:
        move    (r3)-n3                 ; (one step past)
        move    r3,x:(r7+$01)
        move    r2,x:(r7+$07)
        move    x:(r7+$30),n7           ; the frame count back
        move    #>$ffffff,m5
tq99_dry:
        rts

; ---------------------------------------------------------------------------
; tq14_step -- one damped step of the pole iteration: rho from lr (at $18),
; psi(rho), 1/L, F = min(0, (log2(|g| b) - log2|q|) / L), then lr = (F + 0.1
; lr)/1.1 and rho from it (at $15).
; ---------------------------------------------------------------------------
tq14_step:
        move    x:(r7+$18),a
        bsr     tq15_rho                ; rho from the last block's lr
        bsr     tq16_psi                ; a = psi; X at $1d, Y at $1e
        move    x:(r7+$14),b
        tst     b
        beq     tq20z
        asl     #$1,a,a                 ; k psi
tq20z:
        move    a1,x0
        move    #>$7fffff,a
        sub     x0,a
        move    a,x0                    ; 1 - k psi
        move    x:(r7+$0e),a            ; phi0 (clean: a0 = 0)
        bsr     tq19_div                ; 1/L = phi0 / (1 - k psi)
        move    x0,x:(r7+$19)
        bsr     tq59_lq                 ; log2|q| / 32
        move    a1,x0
        move    x:(r7+$13),a            ; log2(|g| b)/32
        sub     x0,a                    ; the difference
        move    a,x0
        move    x:(r7+$19),y1           ; 1/L
        mpy     x0,y1,a                 ; F/32
        clr     b
        tst     a
        tgt     b,a                     ; at most 0: r <= 1
; lr = (F + 0.1 lr)/1.1
        move    a,x0
        move    #>$745d17,y1            ; 1/1.1
        mpy     x0,y1,a
        move    x:(r7+$18),x0
        move    #>$0ba2e9,y1            ; 0.1/1.1
        mac     x0,y1,a
        move    a,x:(r7+$18)            ; lr
        bsr     tq15_rho                ; rho from it
        rts

; ---------------------------------------------------------------------------
; tq59_lq -- a = log2|q| / 32 from X ($1d) and Y ($1e): (log2(Q/2) + 1)/2,
; Q = X^2 + Y^2 (< 2, in the guard bits).
; ---------------------------------------------------------------------------
tq59_lq:
        move    x:(r7+$1d),x0
        move    x0,y1
        mpy     x0,y1,a                 ; X^2
        move    x:(r7+$1e),x0
        move    x0,y1
        mac     x0,y1,a                 ; + Y^2
        asr     #$1,a,a                 ; Q/2
        bsr     tq13_log2               ; log2(Q/2)/32
        add     #>$040000,a             ; + 1/32
        asr     #$1,a,a
        rts

; ---------------------------------------------------------------------------
; tq53_L -- a = psi (cycles) -> L = P (1 - k psi) at $1a (Q12.11).
; ---------------------------------------------------------------------------
tq53_L:
        move    x:(r7+$14),b
        tst     b
        beq     tq58z
        asl     #$1,a,a                 ; k psi
tq58z:
        move    a1,x0
        move    #>$7fffff,a
        sub     x0,a                    ; 1 - k psi (0.5 .. 1)
        move    a,x0
        move    x:(r7+$0d),y1           ; P (an integer)
        mpy     x0,y1,a
        move    a1,x:(r7+$1a)
        rts

; ---------------------------------------------------------------------------
; tq60_shn -- a = a value, n at $1f (0 .. 10) -> a x 2^-n (SH[n]).
; ---------------------------------------------------------------------------
tq60_shn:
        move    a,x0
        move    x:(r7+$1f),n5
        move    n0,r5                   ; SH at +164
        move    (r5)+n5
        move    p:(r5),y1
        mpy     x0,y1,a
        rts

; ---------------------------------------------------------------------------
; tq15_rho -- a = lr/32 (<= 0) -> rho = a 2^y at $15, y = -lr = n + fr:
; a E2(1 - fr) 2^(n + 1), shifted into the guard bits and limited to RHO_MAX;
; n >= 3 saturates. A note that rings has r >= 0.79 (y < 1).
; ---------------------------------------------------------------------------
tq15_rho:
        neg     a                       ; y/32 >= 0
        move    a,x1
        move    x1,a
        asr     #$12,a,a                ; n
        move    #>$3,x0
        move    a1,b
        cmp     x0,b
        bge     tq21_sat
        not     b                       ; -(n + 1) (b1; b2 is not read)
        move    #>$03ffff,a
        move    x1,x0
        and     x0,a                    ; fr / 32
        asl     #$5,a,a
        move    b1,n1
        move    a1,x0
        move    #>$7fffff,a
        sub     x0,a                    ; 1 - fr
        move    r1,r5                   ; E2
        bsr     tq10_t64
        move    a,x0                    ; E2(1 - fr)
        move    x:(r7+$12),y1           ; a
        mpy     x0,y1,a                 ; a E2(1 - fr) < 1
        move    n1,y0
        normf   y0,a                    ; x 2^(n + 1), into the guard bits
        move    #>$7ff000,x0
        cmp     x0,a                    ; 56 bits: the guard bits count
        tgt     x0,a                    ; at most RHO_MAX
        move    a,x:(r7+$15)
        rts
tq21_sat:
        move    #>$7ff000,x0
        move    x:(r7+$12),a
        tst     a
        tne     x0,a                    ; (a = 0, LP 127: rho = 0)
        move    a,x:(r7+$15)
        rts

; ---------------------------------------------------------------------------
; tq16_psi -- a = psi(rho) in cycles: X = 1 - rho cos (to $1d), Y = rho sin
; (to $1e), psi = atan2(Y, X), X > 0, Y >= 0.
; ---------------------------------------------------------------------------
tq16_psi:
        move    x:(r7+$15),x0           ; rho
        move    x:(r7+$11),y1
        mpy     x0,y1,a                 ; rho cos
        move    x:(r7+$10),y1
        move    a,x1
        mpy     x0,y1,b                 ; rho sin
        move    #>$7fffff,a
        sub     x1,a
        move    b,x:(r7+$1e)            ; Y
        move    a,x:(r7+$1d)            ; X
        bra     tq22_atan               ; a = X, b = Y (its rts returns)

; ---------------------------------------------------------------------------
; tq17_herm -- L at $1a (Q12.11) less the Hermite read's phase-delay error
; at phis: f = frac L; the Catmull-Rom weights at f, halved; S = sum w_k
; e^{-jwk}, k = -1..2; tau = -arg S / w samples; L -= tau - f.
; ---------------------------------------------------------------------------
tq17_herm:
        bsr     tq61_S                  ; S at w for the read at $1a's fraction
        move    x:(r7+$24),a            ; im/2
; tau = -arg S / w = -sign(im) atan2(|im|, re) / phis (cycles over cycles)
        abs     a
        move    a,b                     ; |im|/2
        move    x:(r7+$23),a            ; re/2
        bsr     tq22_atan               ; cycles
        move    a,x1
        move    x:(r7+$0f),a            ; phis
        asl     #$1,a,a
        move    a1,x0                   ; 2 phis
        move    x1,a
        cmp     x0,a
        bge     tq28z                   ; no read: tau would be 2 or more
        bsr     tq19_div                ; q = psi_h / (2 phis)
        move    x0,a                    ; tau/2 = -sign(im) q
        move    x:(r7+$24),b
        tst     b
        ble     tq29z
        neg     a                       ; im > 0: a lead, tau negative
tq29z:
        move    a,x1                    ; tau/2
; err = tau - f, in Q12.11: (tau/2 - f/2) * 4096
        move    x:(r7+$1b),a
        asr     #$1,a,a                 ; f/2
        move    a1,x0
        move    x1,a
        sub     x0,a                    ; (tau - f)/2, Q23
        move    a,x0
        move    #>$001000,y1            ; x 4096 / 2^23 ... an integer in a1
        mpy     x0,y1,a                 ; (tau - f) x 2048, integer
        move    a1,x0
        move    x:(r7+$1a),a
        sub     x0,a
        move    a1,x:(r7+$1a)
tq28z:
        rts

; ---------------------------------------------------------------------------
; tq61_S -- the Hermite read's response S at phis, for a read at $1a's
; fraction f: the Catmull-Rom weights at f, halved; re/2 at $23, im/2 at $24.
; ---------------------------------------------------------------------------
tq61_S:
        move    x:(r7+$1a),a
        and     #>$0007ff,a
        asl     #$c,a,a                 ; f, Q23
        lua     (r7+$1e),r4             ; the weights' scratch, walked
        move    a1,x:(r7+$1b)           ; f (herm reads it)
        move    a1,x0
        move    a1,y1
        mpy     x0,y1,a                 ; f^2
        move    a,x0                    ; (limited, as the stored word was)
        mpy     x0,y1,a x0,x1           ; f^3; x1 = f^2
        move    a,y0
; (wm + w1)/2 = 3f^2/2 - f^3, (wm - w1)/2 = -f/2 - f^2/2 + f^3/2
; w0/2 = 1/2 - 5f^2/4 + 3f^3/4, w2/2 = -f^2/4 + f^3/4
        tfr     y1,a
        add     x1,a
        sub     y0,a                    ; f + f^2 - f^3
        asr     #$1,a,a
        neg     a                       ; (wm - w1)/2
        move    #>$600000,y1            ; 3/4
        mpy     x0,y1,b a,x:(r4)+       ; to $1e
        asl     #$1,b,b
        sub     y0,b                    ; (wm + w1)/2 (0 .. 1/2)
        move    #>$b00000,y1            ; -5/8
        mpy     x0,y1,a b,x:(r4)+       ; to $1f
        asl     #$1,a,a                 ; -5f^2/4
        move    y0,x0
        move    #>$600000,y1
        mac     x0,y1,a                 ; + 3f^3/4
        add     #>$400000,a             ; + 1/2: w0/2
        tfr     y0,b
        sub     x1,b    a,x:(r4)+       ; f^3 - f^2; w0/2 to $20
        asr     #$2,b,b                 ; w2/2
; re/2 = (wm + w1)/2 cos + w0/2 + w2/2 c2,  c2 = 2 cos^2 - 1
; im/2 = (wm - w1)/2 sin - w2/2 s2,       s2 = 2 sin cos
        move    x:(r7+$11),x0           ; cos
        move    x0,y1
        mpy     x0,y1,a b,x:(r4)+       ; w2/2 to $21
        asl     #$1,a,a
        sub     #>$400000,a
        sub     #>$400000,a             ; c2
        move    x:(r7+$10),x0           ; sin (y1 is cos)
        mpy     x0,y1,b
        move    a,y0                    ; c2
        asl     #$1,b,b                 ; s2
        move    x:(r7+$1f),x0
        mpy     x0,y1,a
        move    x:(r7+$21),x0
        move    y0,y1
        mac     x0,y1,a
        move    x:(r7+$20),x0
        add     x0,a                    ; re/2 (> 0)
        move    x:(r7+$1e),x0
        move    x:(r7+$10),y1
        move    a,x:(r7+$23)
        mpy     x0,y1,a
        move    x:(r7+$21),x0
        move    b,y1                    ; s2 (limited, as the stored word was)
        mpy     x0,y1,b
        sub     b,a                     ; im/2
        move    a,x:(r7+$24)
        rts

; ---------------------------------------------------------------------------
; tq22_atan -- a = x (> 0), b = y (>= 0), both under 1 -> a = atan2(y, x) in
; cycles (0 .. 1/4): one div, ATN, the octant swap. Uses a b x0 x1 y0 y1 r5
; n5.
; ---------------------------------------------------------------------------
tq22_atan:
        move    a,x0                    ; x
        move    b,x1                    ; y
        move    x1,a
        cmp     x0,a                    ; y - x
        bge     tq23z                   ; y >= x: the octant swap
        bsr     tq19_div                ; t = y/x, in x0
        move    x0,a
        move    r2,r5                   ; ATN at +98
        bsr     tq25_t32                ; 4 atan(t) / (2 pi)
        asr     #$2,a,a                 ; atan(t), cycles
        move    a1,x0
        move    x0,a
        rts
tq23z:
        move    x0,a
        move    x1,x0
        cmp     x0,a                    ; x - y: equal is t = 1
        blt     tq24z
        move    #>$7fffff,x0
        bra     tq26z
tq24z:
        bsr     tq19_div                ; t = x/y
tq26z:
        move    x0,a
        move    r2,r5
        bsr     tq25_t32
        asr     #$2,a,a
        move    a1,x0
        move    #>$200000,a             ; 1/4 - atan(t)
        sub     x0,a
        move    a1,x0
        move    x0,a
        rts

; ---------------------------------------------------------------------------
; tq19_div -- x0 = a / x0, a and x0 positive, a < x0, a clean (a2 = a0 = 0):
; VIBRATO's 24-step div. Uses a.
; ---------------------------------------------------------------------------
tq19_div:
        andi    #$fe,ccr
        do      #$18,>tq27z             ; do, not rep: stock never holds interrupts off
        div     x0,a
tq27z:
        move    a0,x0
        rts

; ---------------------------------------------------------------------------
; tq13_log2 -- a = v (0 < v < 1, in a1) -> a = log2(v)/32: v normalised into
; [1/2, 1) by clb/normf (n left shifts: the pair stock's own log runs), then
; log2 v = log2(1 + x) - 1 - n, x = 2v - 1, LG2 = log2(1 + x)/2. v is never 0
; here (|g| b >= 2^-7 x 0.011; Q/2 and |S|^2/4 far above 2^-23). Bit-identical
; to the five conditional shifts it replaced. Uses a b x0 x1 y0 y1 r5 n5.
; ---------------------------------------------------------------------------
tq13_log2:
        move    a1,b                    ; v (its low word dropped)
        clb     b,a                     ; -n
        normf   a1,b                    ; v 2^n, in [1/2, 1)
        neg     a
        move    #>$400000,y1
        asl     #$12,a,a                ; n/32
        sub     y1,b                    ; v - 1/2
        move    a1,x:(r7+$21)           ; n/32
        asl     b                       ; x = 2v - 1
        move    r3,r5                   ; LG2 at +65
        tfr     b,a                     ; x
        bsr     tq25_t32                ; log2(1 + x)/2
        asr     #$4,a,a                 ; log2(1 + x)/32
        move    x:(r7+$21),x0
        sub     x0,a                    ; - n/32
        sub     #>$040000,a             ; - 1/32
        rts

; ---------------------------------------------------------------------------
; tq12_sin -- x1 = phase (Q23 cycles, 0 .. 1) -> a = sin, from the stock
; 1,024-point sine at X:0x6c00, linearly interpolated (VIBRATO's vbs_sin).
; ---------------------------------------------------------------------------
tq12_sin:
        move    #>$3ff,m4
        move    x1,a
        and     #>$7fffff,a
        move    a1,x1
        move    x1,a
        asr     #$d,a,a
        move    a1,n4                   ; i = phi >> 13
        move    x1,a
        and     #>$001fff,a
        asl     #$a,a,a
        move    a1,x0                   ; f, Q23
        move    #>$6c00,r4
        nop
        nop
        move    (r4)+n4
        move    x:(r4)+,b               ; s[i]
        move    x:(r4),a                ; s[i+1] (the modulo wraps 1023 -> 0)
        sub     b,a
        move    a,y1
        mpy     x0,y1,a
        add     b,a
        move    #>$ffffff,m4
        rts

; ---------------------------------------------------------------------------
; tq11_k33 -- VIBRATO's vb_tab: a = a knob word, r5 = a 33-entry table at k
; = 0, 4, .. 128 -> a = T[k >> 2] interpolated by the rest of k (bits 17-8).
; ---------------------------------------------------------------------------
tq11_k33:
        and     #>$7fff00,a
        move    a1,x1                   ; u
        move    x1,a
        asr     #$12,a,a
        move    a1,n5                   ; i
        move    x1,a
        and     #>$03ff00,a
        asl     #$5,a,a
        move    a1,x0                   ; f
        move    (r5)+n5
        move    p:(r5)+,y0              ; T[i]
        move    p:(r5),b                ; T[i+1]
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a                 ; f (T[i+1] - T[i])
        add     y0,a
        rts

; ---------------------------------------------------------------------------
; tq25_t32 / tq10_t64 -- a1 = x (Q23, 0 .. 1), r5 = a table of 33 / 65
; entries over [0, 1] -> a = T(x), interpolated. Uses a b x0 x1 y0 y1 n5.
; ---------------------------------------------------------------------------
tq25_t32:
        move    a1,x1
        move    x1,a                    ; x (clean)
        asr     #$12,a,a               ; i; the fraction's bits atop a0
        move    a1,n5
        move    a0,b
        lsr     b                       ; f (b1): a0 >> 1
        move    (r5)+n5
        move    b1,x0
        move    p:(r5)+,y0
        move    p:(r5),b
        sub     y0,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a
        rts

tq10_t64:
        move    a1,x1
        move    x1,a                    ; x (clean)
        asr     #$11,a,a               ; i; the fraction's bits atop a0
        move    a1,n5
        move    a0,b
        lsr     b                       ; f (b1): a0 >> 1
        move    (r5)+n5
        move    b1,x0
        move    p:(r5)+,y0
        move    p:(r5),b
        sub     y0,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a
        rts
