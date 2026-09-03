; ---------------------------------------------------------------------------
; BodeShift -- a Warps-flavoured BODE FREQUENCY SHIFTER.
;
; Not a pitch shifter and not a ring modulator: every partial moves by the
; SAME number of Hz, so harmonic relationships are destroyed rather than
; preserved. Small shifts give slow metallic phasing and detune; large ones
; give clangorous, bell-like inharmonic material. A ring modulator produces
; BOTH sidebands (f-fc and f+fc); a Bode shifter cancels one of them, which
; is the whole difference and the whole difficulty.
;
; The insert contract, no buffer: frames in place from r0, knobs from r6,
; state in this instance's own r7 block. Stacks with the other inserts.
;
; ---- how the sideband is cancelled ----------------------------------------
; Two allpass chains (Niemitalo's 8-pole Hilbert pair) whose phase responses
; differ by 90 degrees across the audio band turn the input into an analytic
; pair I,Q. Then
;       out = I*cos(wt) + Q*sin(wt)      is the UPPER sideband alone
;       out = I*cos(wt) - Q*sin(wt)      is the LOWER
; and the unwanted one cancels to the extent that the pair really is 90
; degrees apart. MEASURED in the float model this was derived from, and the
; sign convention is NOT a matter of taste -- the first form written here
; produced the wrong sideband, which is why the model came first:
;       100 Hz  40.8 dB      1 kHz  29.2 dB
;       440 Hz  41.1 dB      5 kHz  18.6 dB      9 kHz  24.8 dB
; So the residual opposite sideband is real and audible at the top of the
; band. That is the honest cost of an 8-pole pair; it is a character, not a
; defect, and doubling the sections would be the fix if it ever matters.
;
; ⚠️ The extra z^-1 belongs on chain A ONLY (I = z^-1 A(x), Q = B(x)). Both
; chains without it, or the delay on B, still assemble, still sound like a
; frequency shifter, and simply stop cancelling -- a ring modulator wearing
; this module's name. The gate that catches it is a sideband measurement.
;
; ---- knobs ----------------------------------------------------------------
;   p0 FREQ  shift, 0..1000 Hz on a squared taper (fine control down low,
;            where the musical detune and phasing settings live)
;   p1 FINE  0..20 Hz, added linearly -- at 1 Hz the two sidebands of a
;            stereo pair beat against each other, the classic slow swirl
;   p2 FDBK  0..0.45, the shifted output back into the input: each pass
;            shifts again, so partials walk up (or down) the spectrum in a
;            spiral. Capped where the loop provably cannot run away.
;   p3 MIX   out = dry + MIX*(wet - dry); MIX=0 is an exact passthrough
;   p7 MODE  0 UP, 1 DOWN, 2 WIDE (up on L and down on R -- the two
;            directions beat against each other across the stereo field)
;
; ---- r7 slots -------------------------------------------------------------
;   $20 m      $21 step    $22 fdbk    $23 sL   $24 sR
;   $25 phase      (PERSISTENT, wrapped by a1 extraction every sample)
;   $26 lastwet    (PERSISTENT, the feedback tap)
;   $27 aPrev      (PERSISTENT, chain A's z^-1)
;   $28 in   $29 sin   $2a cos   $2b I*cos   $2c Q*sin   $2d Q
;   $30..$3f  chain A state, 4 sections x (x[n-1], x[n-2], y[n-1], y[n-2])
;   $40..$4f  chain B state, the same
;
; Every mpy/mac is `mpy x0,y1` / `mac x0,y1` -- the encodings proven signed,
; and both operands here routinely go negative, so this is not optional.
; Audited by disassembly.
; ---------------------------------------------------------------------------

init:
        rts

proc:
; ---- per-block knob decode ------------------------------------------------
        move    x:(r6+$3),x0            ; m = MIX
        move    x0,x:(r7+$20)
; step = FREQ^2 * K + FINE * kfine, in phase units (a full wrap = one cycle,
; so a step of 2f/fs advances f Hz per sample)
        move    x:(r6+$0),x0
        move    x:(r6+$0),y1
        mpy     x0,y1,a                 ; FREQ^2
        move    a,x0
        move    #>$05e592,y1            ; -> 1000 Hz at full knob
        mpy     x0,y1,a
        move    a,x1                    ; the coarse part
        move    x:(r6+$1),x0
        move    #>$001df5,y1            ; FINE -> 20 Hz at full knob
        mpy     x0,y1,a
        add     x1,a
        move    a,x:(r7+$21)
; fdbk = FDBK * 0.45. The cap is arithmetic, not taste: the loop is
; in = 0.5*x + fdbk*wet and |wet| ~ |in|, so |in| settles at 0.5/(1-fdbk),
; which stays under 1.0 for fdbk < 0.5.
        move    x:(r6+$2),x0
        move    #>$39999a,y1
        mpy     x0,y1,a
        move    a,x:(r7+$22)

; ---- MODE: page-2 slot 7 companion (BusVerb's decode) --------------------
; The direction is a per-block SIGN on Q rather than three copies of the
; sample loop: wetL = I*cos + sL*(Q*sin), wetR the same with sR. UP is
; (+1,+1), DOWN (-1,-1), WIDE (+1,-1).
        move    x:(r6+$c),a
        and     #>$ff00,a
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        move    #>$10000,x0
        cmp     x0,a
        beq     sb_down
        move    #>$20000,x0
        cmp     x0,a
        beq     sb_wide
        move    #>$7fffff,x0            ; UP: both channels +1
        move    x0,x:(r7+$23)
        move    x0,x:(r7+$24)
        bra     sb_go
sb_down:
        move    #>$800000,x0            ; DOWN: both -1
        move    x0,x:(r7+$23)
        move    x0,x:(r7+$24)
        bra     sb_go
sb_wide:
        move    #>$7fffff,x0            ; WIDE: L up, R down
        move    x0,x:(r7+$23)
        move    #>$800000,x0
        move    x0,x:(r7+$24)
sb_go:

; ---- per-sample -----------------------------------------------------------
        move    #>$1,n0
        do      n7,>sb_end
; in = 0.5 * mono + fdbk * lastwet
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$2,a,a                 ; (L+R)/4 == 0.5 * the mono sum
        move    x:(r7+$26),x0           ; lastwet
        move    x:(r7+$22),y1           ; fdbk
        mac     x0,y1,a
        move    a,x:(r7+$28)
        move    a,x1                    ; chain A's input

; ---- chain A section 0: allpass, c = 0.6923877778065 -----------------------------
        move    #>$58a02a,y1
        move    x1,x0                   ; this section's input
        mpy     x0,y1,a                 ; c*in
        move    x:(r7+$33),x0          ; y[n-2]
        mac     x0,y1,a                 ; + c*y[n-2]
        move    x:(r7+$31),b           ; x[n-2]
        sub     b,a                     ; - x[n-2]   = y[n]
        move    x:(r7+$30),b           ; shift the state, oldest first
        move    b,x:(r7+$31)           ; x[n-2] <- x[n-1]
        move    x1,x:(r7+$30)          ; x[n-1] <- in
        move    x:(r7+$32),b
        move    b,x:(r7+$33)           ; y[n-2] <- y[n-1]
        move    a,x:(r7+$32)           ; y[n-1] <- y[n]
        move    a,x1                    ; -> the next section's input
; ---- chain A section 1: allpass, c = 0.9360654322959 -----------------------------
        move    #>$77d0fe,y1
        move    x1,x0                   ; this section's input
        mpy     x0,y1,a                 ; c*in
        move    x:(r7+$37),x0          ; y[n-2]
        mac     x0,y1,a                 ; + c*y[n-2]
        move    x:(r7+$35),b           ; x[n-2]
        sub     b,a                     ; - x[n-2]   = y[n]
        move    x:(r7+$34),b           ; shift the state, oldest first
        move    b,x:(r7+$35)           ; x[n-2] <- x[n-1]
        move    x1,x:(r7+$34)          ; x[n-1] <- in
        move    x:(r7+$36),b
        move    b,x:(r7+$37)           ; y[n-2] <- y[n-1]
        move    a,x:(r7+$36)           ; y[n-1] <- y[n]
        move    a,x1                    ; -> the next section's input
; ---- chain A section 2: allpass, c = 0.9882295226860 -----------------------------
        move    #>$7e7e4e,y1
        move    x1,x0                   ; this section's input
        mpy     x0,y1,a                 ; c*in
        move    x:(r7+$3b),x0          ; y[n-2]
        mac     x0,y1,a                 ; + c*y[n-2]
        move    x:(r7+$39),b           ; x[n-2]
        sub     b,a                     ; - x[n-2]   = y[n]
        move    x:(r7+$38),b           ; shift the state, oldest first
        move    b,x:(r7+$39)           ; x[n-2] <- x[n-1]
        move    x1,x:(r7+$38)          ; x[n-1] <- in
        move    x:(r7+$3a),b
        move    b,x:(r7+$3b)           ; y[n-2] <- y[n-1]
        move    a,x:(r7+$3a)           ; y[n-1] <- y[n]
        move    a,x1                    ; -> the next section's input
; ---- chain A section 3: allpass, c = 0.9987488452737 -----------------------------
        move    #>$7fd701,y1
        move    x1,x0                   ; this section's input
        mpy     x0,y1,a                 ; c*in
        move    x:(r7+$3f),x0          ; y[n-2]
        mac     x0,y1,a                 ; + c*y[n-2]
        move    x:(r7+$3d),b           ; x[n-2]
        sub     b,a                     ; - x[n-2]   = y[n]
        move    x:(r7+$3c),b           ; shift the state, oldest first
        move    b,x:(r7+$3d)           ; x[n-2] <- x[n-1]
        move    x1,x:(r7+$3c)          ; x[n-1] <- in
        move    x:(r7+$3e),b
        move    b,x:(r7+$3f)           ; y[n-2] <- y[n-1]
        move    a,x:(r7+$3e)           ; y[n-1] <- y[n]
        move    a,x1                    ; -> the next section's input
; I is chain A's output delayed one sample; the CURRENT output becomes
; next sample's I.
        move    x:(r7+$27),b            ; I = aPrev
        move    x1,x:(r7+$27)           ; aPrev <- this sample's A output
        move    b,x1                    ; park I in x1 while chain B runs...
        move    x1,x:(r7+$2e)           ; ...in a slot, since B needs x1
        move    x:(r7+$28),x1           ; chain B takes the same input

; ---- chain B section 0: allpass, c = 0.4021921162426 -----------------------------
        move    #>$337b08,y1
        move    x1,x0                   ; this section's input
        mpy     x0,y1,a                 ; c*in
        move    x:(r7+$43),x0          ; y[n-2]
        mac     x0,y1,a                 ; + c*y[n-2]
        move    x:(r7+$41),b           ; x[n-2]
        sub     b,a                     ; - x[n-2]   = y[n]
        move    x:(r7+$40),b           ; shift the state, oldest first
        move    b,x:(r7+$41)           ; x[n-2] <- x[n-1]
        move    x1,x:(r7+$40)          ; x[n-1] <- in
        move    x:(r7+$42),b
        move    b,x:(r7+$43)           ; y[n-2] <- y[n-1]
        move    a,x:(r7+$42)           ; y[n-1] <- y[n]
        move    a,x1                    ; -> the next section's input
; ---- chain B section 1: allpass, c = 0.8561710882420 -----------------------------
        move    #>$6d9704,y1
        move    x1,x0                   ; this section's input
        mpy     x0,y1,a                 ; c*in
        move    x:(r7+$47),x0          ; y[n-2]
        mac     x0,y1,a                 ; + c*y[n-2]
        move    x:(r7+$45),b           ; x[n-2]
        sub     b,a                     ; - x[n-2]   = y[n]
        move    x:(r7+$44),b           ; shift the state, oldest first
        move    b,x:(r7+$45)           ; x[n-2] <- x[n-1]
        move    x1,x:(r7+$44)          ; x[n-1] <- in
        move    x:(r7+$46),b
        move    b,x:(r7+$47)           ; y[n-2] <- y[n-1]
        move    a,x:(r7+$46)           ; y[n-1] <- y[n]
        move    a,x1                    ; -> the next section's input
; ---- chain B section 2: allpass, c = 0.9722909545651 -----------------------------
        move    #>$7c7408,y1
        move    x1,x0                   ; this section's input
        mpy     x0,y1,a                 ; c*in
        move    x:(r7+$4b),x0          ; y[n-2]
        mac     x0,y1,a                 ; + c*y[n-2]
        move    x:(r7+$49),b           ; x[n-2]
        sub     b,a                     ; - x[n-2]   = y[n]
        move    x:(r7+$48),b           ; shift the state, oldest first
        move    b,x:(r7+$49)           ; x[n-2] <- x[n-1]
        move    x1,x:(r7+$48)          ; x[n-1] <- in
        move    x:(r7+$4a),b
        move    b,x:(r7+$4b)           ; y[n-2] <- y[n-1]
        move    a,x:(r7+$4a)           ; y[n-1] <- y[n]
        move    a,x1                    ; -> the next section's input
; ---- chain B section 3: allpass, c = 0.9952884791278 -----------------------------
        move    #>$7f659d,y1
        move    x1,x0                   ; this section's input
        mpy     x0,y1,a                 ; c*in
        move    x:(r7+$4f),x0          ; y[n-2]
        mac     x0,y1,a                 ; + c*y[n-2]
        move    x:(r7+$4d),b           ; x[n-2]
        sub     b,a                     ; - x[n-2]   = y[n]
        move    x:(r7+$4c),b           ; shift the state, oldest first
        move    b,x:(r7+$4d)           ; x[n-2] <- x[n-1]
        move    x1,x:(r7+$4c)          ; x[n-1] <- in
        move    x:(r7+$4e),b
        move    b,x:(r7+$4f)           ; y[n-2] <- y[n-1]
        move    a,x:(r7+$4e)           ; y[n-1] <- y[n]
        move    a,x1                    ; -> the next section's input
        move    x1,x:(r7+$2d)           ; Q = chain B's output

; ---- oscillator: phase accumulator, then a refined parabolic sine ---------
; Drift-free BY CONSTRUCTION -- the phase is an exact wrapping integer, so
; unlike a resonator oscillator the amplitude cannot creep over minutes.
        move    x:(r7+$25),a
        move    x:(r7+$21),x0
        add     x0,a
        move    a1,x0                   ; wrap: a1 IS the modulo
        move    x0,a                    ; sign-extended, so A2 is clean
        move    a,x:(r7+$25)
        bsr     sb_sin
        move    a,x:(r7+$29)            ; sin(pi*p)
        move    x:(r7+$25),a
        move    #>$400000,x0
        add     x0,a                    ; + a quarter turn
        move    a1,x0
        move    x0,a
        bsr     sb_sin
        move    a,x:(r7+$2a)            ; cos(pi*p)

; ---- the two sidebands, and the mix --------------------------------------
        move    x:(r7+$2e),x0           ; I
        move    x:(r7+$2a),y1           ; cos
        mpy     x0,y1,a
        move    a,x:(r7+$2b)            ; I*cos
        move    x:(r7+$2d),x0           ; Q
        move    x:(r7+$29),y1           ; sin
        mpy     x0,y1,a
        move    a,x:(r7+$2c)            ; Q*sin
; wetL = 2 * (I*cos + sL*(Q*sin))   -- the x2 undoes the input's 0.5
        move    x:(r7+$2c),x0
        move    x:(r7+$23),y1           ; sL
        mpy     x0,y1,a
        move    x:(r7+$2b),b
        add     b,a
        asl     #$1,a,a
        move    a,x:(r7+$26)            ; lastwet, for the feedback tap
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
; wetR
        move    x:(r7+$2c),x0
        move    x:(r7+$24),y1           ; sR
        mpy     x0,y1,a
        move    x:(r7+$2b),b
        add     b,a
        asl     #$1,a,a
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
sb_end:
        nop
        rts

; ---------------------------------------------------------------------------
; sb_sin -- sin(pi*p) for p in [-1,1), to about 0.1% .
;   y = 4p(1-|p|)                 the parabola
;   y = 0.775y + 0.225y|y|        the standard refinement
; Without the refinement the parabola's 3rd harmonic sits near -28 dB, which
; would put a spurious shifted copy ABOVE the Hilbert pair's own residual --
; the oscillator would become the limiting error, for two multiplies.
; In: a = p.  Out: a = sin(pi*p).  Clobbers x0, x1, y1, b.
; ---------------------------------------------------------------------------
sb_sin:
        move    a,x1                    ; keep p
        abs     a
        move    #>$800000,x0
        add     x0,a                    ; |p| - 1
        neg     a                       ; t = 1 - |p|
        move    a,y1
        move    x1,x0
        mpy     x0,y1,a                 ; p*t
        asl     #$2,a,a                 ; y = 4p(1-|p|)
        move    a,x1                    ; keep y
        move    a,x0
        abs     a
        move    a,y1                    ; |y|
        mpy     x0,y1,a                 ; y*|y|
        move    a,x0
        move    #>$1ccccd,y1            ; 0.225
        mpy     x0,y1,a
        move    x1,x0
        move    #>$633333,y1            ; 0.775
        mac     x0,y1,a
        rts
