; ---------------------------------------------------------------------------
; MODULATION STATION -- one modulated line, seven modes, FX1 only.
;
; Insert contract (modules/ripple/ripple_svf.asm) plus the bus-client contract
; the other two stations carry (modules/filterstation/): the processed mono
; goes into both accumulators, registration is gated on each send knob, and
; the station NEVER HOUSEKEEPS -- an FX1 instance runs before its track's FX2
; one, so an electing station would double-flip the rotation.
;
; ---- FX1 ONLY, ENFORCED HERE ---------------------------------------------
; The base comes from the host's bump allocator, read in INIT and only there
; (docs/DSP.md section 10: X:0x213 is per-instance during init and garbage in
; proc). FX1 slots are 0x1000 0x1c00 0x2800 0x3400; FX2 slots are 0x4000 and
; up, and every one of those is a server's ground -- ChonVerb's tank on core
; 0, BongDelay's line on tracks 3-4. So a base >= 0x4000 sets a flag that
; sends proc down the DRY path, which writes NOTHING to Y. That promise is
; what Claims(fx1_only=True) declares to the ledger, and tools/
; verify_modstation.py is what proves it.
;
; Two lines of 1,024 words, L at base+0 and R at base+1024: 23 ms each, out
; of the 3,072 an FX1 slot gives. The read offset is MASKED (& $3ff), not the
; address, so nothing depends on where the allocator put us.
;
; ---- the modes -----------------------------------------------------------
; Three sample loops, chosen once per block (the Ripple pattern, which
; cycle_count prices as "worst of N mode loops" -- a dispatch INSIDE a sample
; loop cannot be priced at all):
;
;   LINE  CHOR FLNG COMB VIB -- one modulated tap with feedback. The modes
;         differ only in per-block coefficients: centre delay, sweep depth
;         and feedback. VIB is the same line with the dry left out by MIX.
;   PHSR  four one-pole allpass stages swept by the LFO, no line at all.
;         STGS taps the chain after 1, 2, 3 or 4 stages (2, 4, 6, 8 poles)
;         by weighting the four taps, which keeps the loop branchless.
;   AMP   TREM and PAN: the LFO on amplitude, the same in both channels or
;         opposite, which is one per-block polarity word.
;
; Every mode outputs the WET only; MIX does the blending, so MIX 0 is an
; exact passthrough in every mode and 127 is vibrato/tremolo outright.
;
; ---- the LFO -------------------------------------------------------------
; Per SAMPLE, not per block: at a 15-sample block a per-block LFO steps at
; 2.9 kHz, which a chorus hears as zipper. Two shaped copies, L and its
; WID-offset partner, from one phase accumulator. TRI is the basis; SIN is
; the parabola 2t - t|t| blended in; SQR is TRI multiplied up and clamped by
; a limiting store. All three are one code path with per-block weights.
;
; ---- r7 slots -------------------------------------------------------------
;   $14 $65..$69  bus bookkeeping, SEND's layout ($69 = this block's offset)
;   ⚠️ EVERY SLOT THE SAMPLE LOOPS TOUCH IS BELOW $40: an r7 displacement past
;   63 assembles to the two-word long form (it cost the filter station 30
;   words before that was found).
;   $19 line base (per instance)     $1a dry flag: 1 = FX2 slot or MIX 0
;   $1b write phase (PERSISTENT)     $1c LFO phase (PERSISTENT)
;   $1d lfo L this sample            $1e lfo R this sample
;   $1f R amplitude polarity (PAN)   $20 m (MIX)
;   $21 centre delay, Q11.12         $22 sweep depth, Q11.12
;   $23 feedback                     $24 tone coefficient
;   $25 WID phase offset             $26 LFO increment per sample
;   $27 sin blend weight             $28 square gain / 8
;   $29 engine class                 $2a scratch (shape)
;   $2b..$2e phaser tap weights      $2f phaser coefficient depth
;   $30 ->DEL level                  $31 ->VRB level
;   $32/$33 feedback tone state L/R      (PERSISTENT)
;   $34..$37 allpass state L, 4 stages   (PERSISTENT)
;   $38..$3b allpass state R, 4 stages   (PERSISTENT)
;   $3c tap L  $3d tap R  $3e scratch  $3f scratch
;
; Every mpy is `mpy x0,y1` (the audited-signed encoding) except the send
; taps, which are SEND's `mpy x1,y1` / `mpy x1,y0` with a non-negative level
; second. Every Tcc reads the ONE compare above it with nothing but moves
; between (the flag-clobber trap). No label here is a PREFIX of another --
; dsp_asm resolves by prefix, and `ch_sat` inside `ch_satr` cost the
; character station an afternoon.
; ---------------------------------------------------------------------------

init:
; ROTINIT
; ---- the allocator base, and the FX1/FX2 decision ------------------------
; Nimbus Lite's idiom (modules/nimbuslite/nimbus_lite.asm): X:0x213 points at
; this instance's entry in the base table. Valid HERE and nowhere else.
        move    x:>$213,r4
        move    #>$ffffff,m4
        move    x:(r4),x0
        move    x0,x:(r7+$19)           ; the line base
; sub/tst rather than cmp: the cmp-encodes-as-max family (CLAUDE.md).
        move    x0,a
        move    #>$4000,x0
        sub     x0,a                    ; base - 0x4000
        clr     b                       ; b = 0 BEFORE the tst (the flag trap)
        move    #>$1,x0
        tst     a
        tpl     x0,b                    ; base >= 0x4000: an FX2 slot
        move    b,x:(r7+$1a)
        tst     b
        bne     monoclr                 ; FX2: never touch the buffer at all
; ---- clear both lines, once, at instantiation ----------------------------
        move    x:(r7+$19),a
        move    a,r5
        move    #>$ffffff,m5
        clr     a
        do      #2048,>moclrz
        move    a,y:(r5)+
moclrz:
        nop
monoclr:
        clr     a
        move    a,x:(r7+$1b)            ; write phase
        move    a,x:(r7+$1c)            ; LFO phase
        move    a,x:(r7+$32)            ; feedback tone states
        move    a,x:(r7+$33)
        move    a,x:(r7+$34)            ; allpass states, both channels
        move    a,x:(r7+$35)
        move    a,x:(r7+$36)
        move    a,x:(r7+$37)
        move    a,x:(r7+$38)
        move    a,x:(r7+$39)
        move    a,x:(r7+$3a)
        move    a,x:(r7+$3b)
        rts

proc:
; ===========================================================================
; BUS: split-aware frame offset, verbatim from modules/send/send_client.asm
; ===========================================================================
        move    a,x:(r7+$14)
        clr     a
        move    a,x:(r7+$67)
        move    x:(r7+$14),a
        tst     a
        bne     moa1
        move    #>$1,a
        move    a,x:(r7+$65)
        move    n7,a
        and     #>$f,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$66)
        bra     mooffok
moa1:
        move    x:(r7+$65),a
        and     #>$ff,a
        move    a1,x0
        move    x0,a
        move    #>$1,x0
        cmp     x0,a
        bne     mooffok
        clr     a
        move    a,x:(r7+$65)
        move    x:(r7+$66),a
        and     #>$f,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$67)
mooffok:
; ---- resolve this block's write offset (per payload) -> r7+$69, r1, r2 ---
; ROTLATCH
        move    a,x0
        move    #>$901,a
        add     x0,a
        move    x:(r7+$67),b
        add     b,a
        move    a,r1                    ; REVERB ACC[write] + frame offset
        move    #>$961,a
        add     x0,a
        add     b,a
        move    a,r2                    ; DELAY  ACC[write] + frame offset
        move    #>$ffffff,m1
        move    #>$ffffff,m2
; ---- register, once per block, per bus, ONLY IF SENDING (r6+4 / r6+5) ----
        move    x:(r7+$67),a
        tst     a
        bne     mocntz
        move    x:(r7+$69),a
        asr     #$4,a,a
        move    a1,x0
        move    x0,a
        move    #>$9c3,x0
        add     x0,a
        move    a,r3
        move    #>$ffffff,m3
        move    #>$1,x0
        clr     b
        move    x:(r6+$5),a             ; ->VRB level
        tst     a
        tne     x0,b
        move    y:(r3),a
        add     b,a
        move    a,y:(r3)
        move    #4,n3
        move    (r3)+n3
        clr     b
        move    x:(r6+$4),a             ; ->DEL level
        tst     a
        tne     x0,b
        move    y:(r3),a
        add     b,a
        move    a,y:(r3)
mocntz:
        move    x:(r6+$4),x0
        move    x0,x:(r7+$30)           ; ->DEL
        move    x:(r6+$5),x0
        move    x0,x:(r7+$31)           ; ->VRB

; ===========================================================================
; PER-BLOCK KNOB DECODE
; ===========================================================================
; MIX
        move    x:(r6+$3),x0
        move    x0,x:(r7+$20)
; LFO increment: RATE^2 * $2600 + $30 per sample (~0.05 .. ~8 Hz)
        move    x:(r6+$0),x0
        move    x:(r6+$0),y1
        mpy     x0,y1,a
        move    a,x0
; ⚠️ $600, NOT $2600: the increment is a fraction of 2^23 per SAMPLE, so
; freq = inc * 44100 / 2^23. $2600 topped the knob out at 51 Hz -- audio
; rate, not an LFO, and a chorus swept that fast is just noise (measured
; 3 Sep 2026). $600 gives 0.06 Hz at the bottom and 7.9 Hz at the top.
        move    #>$600,y1
        mpy     x0,y1,a
        add     #>$10,a
        move    a,x:(r7+$26)
; WID -> the right channel's LFO phase offset, 0 .. half a cycle
        move    x:(r6+$e),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        asr     #$1,a,a                 ; 0 .. ~0.5 of a cycle
        move    a,x:(r7+$25)
; SHPE (slot 9 select of r6+$d): the sin blend and the square gain
        clr     a
        move    a,x:(r7+$27)            ; sin weight 0
        move    #>$100000,x0            ; square gain / 8 = 1/8, i.e. gain 1
        move    x0,x:(r7+$28)
        move    x:(r6+$d),a
        and     #>$ff00,a
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        move    #>$10000,x0
        cmp     x0,a
        beq     mo_shsin
        move    #>$20000,x0
        cmp     x0,a
        beq     mo_shsqr
        bra     mo_shdone               ; TRI, and anything unexpected
mo_shsin:
        move    #>$7fffff,x0            ; the parabola, all of it
        move    x0,x:(r7+$27)
        bra     mo_shdone
mo_shsqr:
        move    #>$7fffff,x0            ; gain 8, clamped by a limiting store
        move    x0,x:(r7+$28)
mo_shdone:
; TONE -> the one-pole coefficient inside the feedback path
        move    x:(r6+$d),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        move    a,x0
        move    #>$7c0000,y1
        mpy     x0,y1,a
        add     #>$040000,a
        move    a,x:(r7+$24)
; STGS (slot 11 select of r6+$e) -> the four phaser tap weights
        clr     a
        move    a,x:(r7+$2b)
        move    a,x:(r7+$2c)
        move    a,x:(r7+$2d)
        move    a,x:(r7+$2e)
        move    #>$7fffff,x1            ; the one that is 1.0
        move    x:(r6+$e),a
        and     #>$ff00,a
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        move    #>$10000,x0
        cmp     x0,a
        beq     mo_st4
        move    #>$20000,x0
        cmp     x0,a
        beq     mo_st6
        move    #>$30000,x0
        cmp     x0,a
        beq     mo_st8
        move    x1,x:(r7+$2b)           ; 2 poles: tap after stage 1
        bra     mo_stdone
mo_st4:
        move    x1,x:(r7+$2c)
        bra     mo_stdone
mo_st6:
        move    x1,x:(r7+$2d)
        bra     mo_stdone
mo_st8:
        move    x1,x:(r7+$2e)
mo_stdone:
; DLY -> the centre delay in Q11.12 samples, ~0.2 .. 23 ms (8 .. 1000)
        move    x:(r6+$c),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        move    a,x0
; ⚠️ NO SHIFT. $3e0000 IS 992*4096, so the product already lands in Q11.12:
; mpy(DLY/128, 992*4096/2^23) leaves (992*DLY/128)*4096 in a1. The `asr #11`
; that used to be here divided it by 2,048, which pinned every line mode at
; its 8-sample floor -- an 8-sample chorus, measured as an impulse coming
; back 7 samples late instead of 473 (3 Sep 2026).
        move    #>$3e0000,y1            ; 992 samples, pre-scaled to Q11.12
        mpy     x0,y1,a
        add     #>$8000,a               ; + 8 samples of floor
        move    a,x:(r7+$21)
; DPTH -> the sweep depth in Q11.12 samples
        move    x:(r6+$1),x0
        move    #>$1e0000,y1            ; 480 samples, pre-scaled to Q11.12
        mpy     x0,y1,a                 ; (no shift -- see the note above)
        move    a,x:(r7+$22)
; FDBK -> the feedback amount, and the phaser's sweep depth
        move    x:(r6+$2),x0
        move    x0,x:(r7+$23)
        move    #>$600000,x0            ; the phaser sweeps 0.75 of its range
        move    x0,x:(r7+$2f)
; ---- MODE (slot 7 select of r6+$c): the engine class, and the per-mode ----
; overrides of centre, depth and feedback. CHOR is the fall-through.
        clr     a
        move    a,x:(r7+$29)            ; class 0 = the LINE loop
        move    #>$400000,x0
        move    x0,x:(r7+$1f)           ; R polarity +1 (halved), for AMP
        move    x:(r6+$c),a
        and     #>$ff00,a
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        move    a,x:(r7+$2a)            ; park the mode
        move    #>$10000,x0
        cmp     x0,a
        beq     mo_mflng
        move    #>$20000,x0
        cmp     x0,a
        beq     mo_mphsr
        move    #>$30000,x0
        cmp     x0,a
        beq     mo_mcomb
        move    #>$40000,x0
        cmp     x0,a
        beq     mo_mtrem
        move    #>$50000,x0
        cmp     x0,a
        beq     mo_mvib
        move    #>$60000,x0
        cmp     x0,a
        beq     mo_mpan
; CHOR: a 10 ms centre, a gentle sweep, no feedback
        move    #>$28000,x0             ; 40 samples ~ 0.9 ms floor
        move    x:(r7+$21),a
        add     x0,a
        move    a,x:(r7+$21)
        clr     a
        move    a,x:(r7+$23)            ; no feedback
        bra     mo_mdone
mo_mflng:
        move    #>$4000,x0              ; 4 samples: the jet lives short
        move    x0,x:(r7+$21)
        move    x:(r7+$22),a
        asr     #$2,a,a                 ; a quarter of the sweep
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$22)
        bra     mo_mdone
mo_mphsr:
        move    #>$1,a
        move    a,x:(r7+$29)            ; class 1 = the PHASER loop
        bra     mo_mdone
mo_mcomb:
        move    x:(r7+$22),a
        asr     #$4,a,a                 ; barely swept: it is a resonator
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$22)
        bra     mo_mdone
mo_mtrem:
        move    #>$2,a
        move    a,x:(r7+$29)            ; class 2 = the AMP loop
        bra     mo_mdone
mo_mvib:
        clr     a
        move    a,x:(r7+$23)            ; no feedback; the dry goes with MIX
        bra     mo_mdone
mo_mpan:
        move    #>$2,a
        move    a,x:(r7+$29)            ; class 2 = the AMP loop ...
        move    #>$c00000,x0            ; ... with the right channel inverted
        move    x0,x:(r7+$1f)           ; (-0.5, halved like every y1 gain)
mo_mdone:
; ---- the dry path: an FX2 slot, or MIX at zero ---------------------------
        move    x:(r7+$1a),a            ; the FX2 flag from init
        tst     a
        bne     mo_dry
        move    x:(r7+$20),a            ; MIX
        tst     a
        beq     mo_dry
; ---- pick this block's engine -------------------------------------------
        move    x:(r7+$29),a
        move    #>$1,x0
        cmp     x0,a
        beq     mo_phsr
        move    #>$2,x0
        cmp     x0,a
        beq     mo_amp

; ===========================================================================
; THE LINE LOOP -- CHOR, FLNG, COMB, VIB
; ===========================================================================
        move    #>$1,n0
        do      n7,>molinz
        bsr     moshap                  ; both LFOs, into $1d and $1e
; ---- advance the write phase --------------------------------------------
        move    x:(r7+$1b),a
        add     #>$1,a
        and     #>$3ff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$1b)
; ---- L: the modulated tap ------------------------------------------------
        move    x:(r7+$1d),x0           ; lfo L
        move    x:(r7+$22),y1           ; depth, Q11.12
        mpy     x0,y1,a                 ; the sweep, Q11.12 signed
        move    x:(r7+$21),x0           ; centre
        add     x0,a
        move    a,x:(r7+$3e)            ; park the total
        asr     #$c,a,a                 ; integer samples
        move    a1,x0
        move    x:(r7+$1b),a            ; the write phase
        sub     x0,a                    ; ... minus the delay
        and     #>$3ff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$3f)            ; park the read phase
        move    x:(r7+$19),x0           ; the line base
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    y:(r5),a                ; t0
        move    a,x:(r7+$3c)
        move    x:(r7+$3f),a
        add     #>$1,a                  ; the neighbour, one sample newer
        and     #>$3ff,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$19),x0
        add     x0,a
        move    a,r5
        move    y:(r5),a                ; t1
        move    x:(r7+$3c),x0
        sub     x0,a                    ; t1 - t0
        move    a1,x0
        move    x:(r7+$3e),a            ; the total again, for its fraction
        and     #>$fff,a
        asl     #$b,a,a                 ; -> Q23
        move    a1,y1
        mpy     x0,y1,a                 ; frac * (t1 - t0)
        move    x:(r7+$3c),x0
        add     x0,a                    ; the interpolated tap
        move    a,x:(r7+$3c)            ; wet L
; ---- L: the feedback write ----------------------------------------------
; the one-pole INSIDE the feedback: s += c*(tap - s). It accumulated c*tap
; instead until 3 Sep 2026, which walks the state to the rail rather than
; damping the loop.
        move    x:(r7+$3c),a            ; the tap
        move    x:(r7+$32),b            ; the state
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$24),y1           ; the coefficient
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a                     ; s'
        move    a,x:(r7+$32)
        move    a,x0
        move    x:(r7+$23),y1           ; feedback
        mpy     x0,y1,a
        move    x:(r0),x0
        add     x0,a                    ; input + feedback
        move    a,x:(r7+$3e)            ; LIMITING store: the loop cannot rail
        move    x:(r7+$1b),a
        move    x:(r7+$19),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$3e),a
        move    a,y:(r5)                ; write the line
; ---- R: the same, on the second line ------------------------------------
        move    x:(r7+$1e),x0           ; lfo R
        move    x:(r7+$22),y1
        mpy     x0,y1,a
        move    x:(r7+$21),x0
        add     x0,a
        move    a,x:(r7+$3e)
        asr     #$c,a,a
        move    a1,x0
        move    x:(r7+$1b),a
        sub     x0,a
        and     #>$3ff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$3f)
        move    x:(r7+$19),x0
        add     x0,a
        add     #>$400,a                ; the right line, 1,024 words up
        move    a,r5
        move    y:(r5),a
        move    a,x:(r7+$3d)
        move    x:(r7+$3f),a
        add     #>$1,a
        and     #>$3ff,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$19),x0
        add     x0,a
        add     #>$400,a
        move    a,r5
        move    y:(r5),a
        move    x:(r7+$3d),x0
        sub     x0,a
        move    a1,x0
        move    x:(r7+$3e),a
        and     #>$fff,a
        asl     #$b,a,a
        move    a1,y1
        mpy     x0,y1,a
        move    x:(r7+$3d),x0
        add     x0,a
        move    a,x:(r7+$3d)            ; wet R
        move    x:(r7+$3d),a
        move    x:(r7+$33),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$24),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$33)
        move    a,x0
        move    x:(r7+$23),y1
        mpy     x0,y1,a
        move    x:(r0+n0),x0
        add     x0,a
        move    a,x:(r7+$3e)
        move    x:(r7+$1b),a
        move    x:(r7+$19),x0
        add     x0,a
        add     #>$400,a
        move    a,r5
        move    x:(r7+$3e),a
        move    a,y:(r5)
        bsr     momixs                  ; MIX from $3c/$3d, then the sends
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
molinz:
        nop
        rts

; ===========================================================================
; THE PHASER LOOP -- four allpass stages, tapped by STGS
; ===========================================================================
mo_phsr:
        move    #>$1,n0
        do      n7,>mophsz
        bsr     moshap
; the coefficient: c = lfo * depth, so it sweeps either side of centre
        move    x:(r7+$1d),x0
        move    x:(r7+$2f),y1
        mpy     x0,y1,a
        move    a,x:(r7+$3e)            ; c for this sample
        move    x:(r0),a
        move    a,x:(r7+$3c)
        bsr     moapch                  ; the L chain, state $34..$37
        move    x:(r7+$1e),x0           ; the right channel's own coefficient
        move    x:(r7+$2f),y1
        mpy     x0,y1,a
        move    a,x:(r7+$3e)
        move    x:(r0+n0),a
        move    a,x:(r7+$3d)
        bsr     moapcr                  ; the R chain, state $38..$3b
        bsr     momixs
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
mophsz:
        nop
        rts

; ===========================================================================
; THE AMP LOOP -- TREM and PAN
; ===========================================================================
mo_amp:
        move    #>$1,n0
        do      n7,>moampz
        bsr     moshap
; gain = 1 + depth*lfo, halved like every y1 gain and doubled back after
        move    x:(r7+$1d),x0
        move    x:(r6+$1),y1            ; DPTH straight from the knob
        mpy     x0,y1,a
        asr     #$1,a,a
        add     #>$400000,a             ; (1 + d*lfo) / 2
        move    a,y1
        move    x:(r0),x0
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,x:(r7+$3c)            ; wet L
        move    x:(r7+$1e),x0           ; the right channel's LFO ...
        move    x:(r7+$1f),y1           ; ... times its polarity (halved)
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,x0
        move    x:(r6+$1),y1
        mpy     x0,y1,a
        asr     #$1,a,a
        add     #>$400000,a
        move    a,y1
        move    x:(r0+n0),x0
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,x:(r7+$3d)            ; wet R
        bsr     momixs
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
moampz:
        nop
        rts

; ===========================================================================
; THE DRY PATH: an FX2 slot, or MIX at zero. Frames untouched, sends only.
; ===========================================================================
mo_dry:
        move    x:(r7+$31),y0
        move    x:(r7+$30),y1
        move    #>$1,n0
        do      n7,>mobypz
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x1
        mpy     x1,y1,a
        asr     #$3,a,a
        move    y:(r2),b
        add     b,a
        move    a,y:(r2)+
        mpy     x1,y0,a
        asr     #$3,a,a
        move    y:(r1),b
        add     b,a
        move    a,y:(r1)+
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
mobypz:
        nop
        rts

; ---------------------------------------------------------------------------
; moshap -- the two LFOs for this sample, into $1d (L) and $1e (R).
; The shaper is INLINED twice rather than called: cycle_count requires a bsr
; callee to be straight-line, and a callee that itself calls is refused --
; which costs the module its price, and an unpriced module cannot ship.
; The phase advances once; the right channel reads it WID further round.
; TRI is the basis, SIN is the parabola 2t - t|t| blended in by $27, and SQR
; is the whole thing multiplied by 8 and clamped by a limiting store -- so
; all three shapes are one code path with two per-block coefficients.
; ---------------------------------------------------------------------------
moshap:
        move    x:(r7+$1c),a            ; the phase
        move    x:(r7+$26),x0
        add     x0,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$1c)
        move    #>$400000,x0
        sub     x0,a                    ; phase - 0.5
        abs     a                       ; 0 .. 0.5
        asl     #$2,a,a                 ; 0 .. 2, in the guard bits
        move    #>$7fffff,x0
        sub     x0,a                    ; the triangle, -1 .. 1
        move    a,x:(r7+$2a)            ; LIMITING store, so |tri| <= 1
        move    x:(r7+$2a),x1           ; tri
        move    x1,a
        abs     a
        move    a,y1                    ; |tri|
        move    x1,x0
        mpy     x0,y1,a                 ; tri * |tri|
        neg     a
        move    x1,b
        asl     #$1,b,b                 ; 2 * tri
        add     b,a                     ; the parabola, -1 .. 1
        move    x1,x0
        sub     x0,a                    ; parabola - tri
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$27),y1           ; the sin blend
        mpy     x0,y1,a
        asl     #$1,a,a
        add     x1,a                    ; tri + w*(parabola - tri)
        move    a,x0
        move    x:(r7+$28),y1           ; the square gain / 8
        mpy     x0,y1,a
        asl     #$3,a,a
        move    a,x:(r7+$2a)            ; LIMITING store: this IS the square
        move    x:(r7+$2a),a
        move    a,x:(r7+$1d)            ; lfo L
        move    x:(r7+$1c),a
        move    x:(r7+$25),x0           ; ... WID further round
        add     x0,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a
        move    #>$400000,x0
        sub     x0,a                    ; phase - 0.5
        abs     a                       ; 0 .. 0.5
        asl     #$2,a,a                 ; 0 .. 2, in the guard bits
        move    #>$7fffff,x0
        sub     x0,a                    ; the triangle, -1 .. 1
        move    a,x:(r7+$2a)            ; LIMITING store, so |tri| <= 1
        move    x:(r7+$2a),x1           ; tri
        move    x1,a
        abs     a
        move    a,y1                    ; |tri|
        move    x1,x0
        mpy     x0,y1,a                 ; tri * |tri|
        neg     a
        move    x1,b
        asl     #$1,b,b                 ; 2 * tri
        add     b,a                     ; the parabola, -1 .. 1
        move    x1,x0
        sub     x0,a                    ; parabola - tri
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$27),y1           ; the sin blend
        mpy     x0,y1,a
        asl     #$1,a,a
        add     x1,a                    ; tri + w*(parabola - tri)
        move    a,x0
        move    x:(r7+$28),y1           ; the square gain / 8
        mpy     x0,y1,a
        asl     #$3,a,a
        move    a,x:(r7+$2a)            ; LIMITING store: this IS the square
        move    x:(r7+$2a),a
        move    a,x:(r7+$1e)            ; lfo R
        rts


; ---------------------------------------------------------------------------
; moapch / moapcr -- the four-stage allpass chain, L and R.
; In: $3c (or $3d) = the input, $3e = this sample's coefficient.
; Out: the same slot holds the weighted tap. Each stage is the one-pole
; allpass y = -c*x + s, s' = x + c*y, which is unity-magnitude at every
; frequency -- the phase is the whole point. The four taps are weighted
; rather than branched on, so STGS costs no branch in the loop. The stages
; are INLINED (cycle_count refuses a bsr callee that itself calls).
; ---------------------------------------------------------------------------
moapch:
        clr     b
        move    x:(r7+$3c),a
        move    a,x:(r7+$3f)
        move    x:(r7+$34),x0
        move    x:(r7+$3f),x1           ; x, the stage input
        move    x:(r7+$3e),y1           ; c
        mpy     x1,y1,a                 ; c * x
        neg     a                       ; -c * x
        move    x0,y0                   ; s
        add     y0,a                    ; y = -c*x + s
        move    a,x:(r7+$3f)            ; the stage output
        move    a,x0
        mpy     x0,y1,a                 ; c * y
        add     x1,a                    ; s' = x + c*y
        move    a,x:(r7+$34)
        move    x:(r7+$3e),y1
        move    x:(r7+$2b),y0
        move    x:(r7+$3f),x0
        move    y0,y1
        mpy     x0,y1,a
        add     a,b
        move    x:(r7+$35),x0
        move    x:(r7+$3f),x1           ; x, the stage input
        move    x:(r7+$3e),y1           ; c
        mpy     x1,y1,a                 ; c * x
        neg     a                       ; -c * x
        move    x0,y0                   ; s
        add     y0,a                    ; y = -c*x + s
        move    a,x:(r7+$3f)            ; the stage output
        move    a,x0
        mpy     x0,y1,a                 ; c * y
        add     x1,a                    ; s' = x + c*y
        move    a,x:(r7+$35)
        move    x:(r7+$2c),y0
        move    x:(r7+$3f),x0
        move    y0,y1
        mpy     x0,y1,a
        add     a,b
        move    x:(r7+$36),x0
        move    x:(r7+$3f),x1           ; x, the stage input
        move    x:(r7+$3e),y1           ; c
        mpy     x1,y1,a                 ; c * x
        neg     a                       ; -c * x
        move    x0,y0                   ; s
        add     y0,a                    ; y = -c*x + s
        move    a,x:(r7+$3f)            ; the stage output
        move    a,x0
        mpy     x0,y1,a                 ; c * y
        add     x1,a                    ; s' = x + c*y
        move    a,x:(r7+$36)
        move    x:(r7+$2d),y0
        move    x:(r7+$3f),x0
        move    y0,y1
        mpy     x0,y1,a
        add     a,b
        move    x:(r7+$37),x0
        move    x:(r7+$3f),x1           ; x, the stage input
        move    x:(r7+$3e),y1           ; c
        mpy     x1,y1,a                 ; c * x
        neg     a                       ; -c * x
        move    x0,y0                   ; s
        add     y0,a                    ; y = -c*x + s
        move    a,x:(r7+$3f)            ; the stage output
        move    a,x0
        mpy     x0,y1,a                 ; c * y
        add     x1,a                    ; s' = x + c*y
        move    a,x:(r7+$37)
        move    x:(r7+$2e),y0
        move    x:(r7+$3f),x0
        move    y0,y1
        mpy     x0,y1,a
        add     a,b
        move    b,x:(r7+$3c)
        rts
moapcr:
        clr     b
        move    x:(r7+$3d),a
        move    a,x:(r7+$3f)
        move    x:(r7+$38),x0
        move    x:(r7+$3f),x1           ; x, the stage input
        move    x:(r7+$3e),y1           ; c
        mpy     x1,y1,a                 ; c * x
        neg     a                       ; -c * x
        move    x0,y0                   ; s
        add     y0,a                    ; y = -c*x + s
        move    a,x:(r7+$3f)            ; the stage output
        move    a,x0
        mpy     x0,y1,a                 ; c * y
        add     x1,a                    ; s' = x + c*y
        move    a,x:(r7+$38)
        move    x:(r7+$3e),y1
        move    x:(r7+$2b),y0
        move    x:(r7+$3f),x0
        move    y0,y1
        mpy     x0,y1,a
        add     a,b
        move    x:(r7+$39),x0
        move    x:(r7+$3f),x1           ; x, the stage input
        move    x:(r7+$3e),y1           ; c
        mpy     x1,y1,a                 ; c * x
        neg     a                       ; -c * x
        move    x0,y0                   ; s
        add     y0,a                    ; y = -c*x + s
        move    a,x:(r7+$3f)            ; the stage output
        move    a,x0
        mpy     x0,y1,a                 ; c * y
        add     x1,a                    ; s' = x + c*y
        move    a,x:(r7+$39)
        move    x:(r7+$2c),y0
        move    x:(r7+$3f),x0
        move    y0,y1
        mpy     x0,y1,a
        add     a,b
        move    x:(r7+$3a),x0
        move    x:(r7+$3f),x1           ; x, the stage input
        move    x:(r7+$3e),y1           ; c
        mpy     x1,y1,a                 ; c * x
        neg     a                       ; -c * x
        move    x0,y0                   ; s
        add     y0,a                    ; y = -c*x + s
        move    a,x:(r7+$3f)            ; the stage output
        move    a,x0
        mpy     x0,y1,a                 ; c * y
        add     x1,a                    ; s' = x + c*y
        move    a,x:(r7+$3a)
        move    x:(r7+$2d),y0
        move    x:(r7+$3f),x0
        move    y0,y1
        mpy     x0,y1,a
        add     a,b
        move    x:(r7+$3b),x0
        move    x:(r7+$3f),x1           ; x, the stage input
        move    x:(r7+$3e),y1           ; c
        mpy     x1,y1,a                 ; c * x
        neg     a                       ; -c * x
        move    x0,y0                   ; s
        add     y0,a                    ; y = -c*x + s
        move    a,x:(r7+$3f)            ; the stage output
        move    a,x0
        mpy     x0,y1,a                 ; c * y
        add     x1,a                    ; s' = x + c*y
        move    a,x:(r7+$3b)
        move    x:(r7+$2e),y0
        move    x:(r7+$3f),x0
        move    y0,y1
        mpy     x0,y1,a
        add     a,b
        move    b,x:(r7+$3d)
        rts

; ---------------------------------------------------------------------------
; momixs -- MIX the wet in $3c/$3d against the dry still in the frame, write
; it back, and put the PROCESSED mono onto both buses. Shared by all three
; engines, so the mix law and the send have exactly one copy.
; ---------------------------------------------------------------------------
momixs:
        move    x:(r7+$3c),a
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$20),y1           ; m
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        move    x:(r7+$3d),a
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x1                    ; the processed mono
        move    x:(r7+$30),y1           ; ->DEL
        mpy     x1,y1,a
        asr     #$3,a,a
        move    y:(r2),b
        add     b,a
        move    a,y:(r2)+
        move    x:(r7+$31),y0           ; ->VRB
        mpy     x1,y0,a
        asr     #$3,a,a
        move    y:(r1),b
        add     b,a
        move    a,y:(r1)+
        rts
