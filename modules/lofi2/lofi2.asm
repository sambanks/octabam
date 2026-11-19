; ---------------------------------------------------------------------------
; LOFI2 -- one modulator, then sample-rate and bit reduction.
;
; Ring mod OR stereo frequency shifter, then SRR and BRR, then a high-shelf
; cut. All three are our own code, measured against stock LO-FI where it has
; the same control. The chain is
;   dry -> modulator -> MIX -> SRR -> BRR -> LPF -> out:
; the hold and the crush see the MODULATED signal, so the reduction aliases
; the ring output rather than the dry. MIX is the MODULATOR's depth and sits
; before the reduction pair, so SRR and BRR are live at MIX=0 -- see the MIX
; block below.
;
; All three MODE positions are implemented: 0 runs the ring block, 1 and 2 run
; the shifter, DOWN with the carrier running backwards. The two modulators are mutually
; exclusive and each is skipped by a forward branch.
;
; Same contract as ripple_svf.asm / warp_fold.asm / character.asm: a per-track
; INSERT reading x:(r0) / x:(r0+n0) and writing back in place, n7 frames, no
; bus, no absolute Y, all state in this instance's r7 block.
;
; ---- knobs ----------------------------------------------------------------
;   p0 FREQ   carrier frequency, EXPONENTIAL, six octaves from RANGE's base
;   p1 MIX    modulator depth only: crossfades ring/shift against dry.
;             SRR and BRR run after it and are LIVE AT MIX=0.
;   p2 FDBK   SHIFT: feedback, the f/f+d/f+2d ladder
;        GAIN   RING: makeup gain on the ring product, 2^(k/64): 0 dB at 0,
;             +6 dB at 64, +11.9 dB at 127 (the panel renames the slot per
;             MODE; one knob word, read per mode)
;   p3 SRR    sample-rate reduction, a fractional hold at stock LO-FI's
;             measured rates: 44,100 Hz at 0 down to 3,564 Hz at 127
;   p4 BRR    bit depth: our own round-to-nearest quantiser, a continuous
;             step exponent from our own table, gliding per sample
;   p5 LPF    high-shelf cut, LAST in the chain: our own first-order shelf,
;             -12 dB above a corner swept exponentially from 100 Hz (0)
;             to 16 kHz (126); 127 takes it out of circuit, bit for bit
;   p6 RANGE  MODE-DEPENDENT base: RING 2 Hz / 60 Hz (MF-102), SHIFT 2 Hz /
;             31.25 Hz (Bode 1630) -- knob field of r6+$c
;   p8 MODE   0 RING, 1 SHIFT DOWN, 2 SHIFT UP -- knob field of r6+$d
;   p10 AMPH  ring carrier L/R phase offset, BIPOLAR: -90..+88.6 deg, 0 at
;             the knob's centre (64); + puts R ahead, - puts L ahead. Knob
;             field of r6+$e
;
; ---- r7 slots -------------------------------------------------------------
; All below $40 (one-word displacements, about 2/3 the cost of the two-word
; form on the chip: CHIP.md section 2, probe 57) except the Hilbert state.
;   the glides lf_gset steps, in use then step, walked by r4/r3 each sample:
;     $00/$01 MIX   $02/$03 GAIN/4   $04/$05 fdbk   $06/$07 amph offset
;     $08/$09 LPF c   $0a/$0b LPF kd   $0c/$0d carrier step
;   (per block, before the glide setup, the step slots hold the targets)
;   the MODE duck:
;     $10 running mode (PERSISTENT: the mode actually playing)
;     $11 duck depth e, 0 = none .. $7fffff = wet fully out (PERSISTENT)
;     $13 duck step, signed (per block)   $15 MODE as the knob has it (per block)
;   persistent:
;     $19 held L      $1a held R      $1b srr phase      $1c carrier phase
;     $17 SRR rate in use (glided per sample toward $16, its per-block step)
;     $29 BRR E in use (the one per-sample one-pole, toward $28, the target)
;     $0e/$0f the shelf allpass's dropped bits, L/R
;     $20/$12 the shelf's ap[n-1] and x[n-1], L    $38/$26 the same, R
;     $39/$3a aPrev L/R (chain A delayed)   $3b/$3c lastwet L/R (the feedback tap)
;     $37 the Hilbert chains' parity half, $40 or $60
;   per block:
;     $21 range   $22 mode   $25 ptable base   $27 ring flag   $32 shift flag
;   per sample:
;     $2a m, $2b 1/(2m) -- BRR's step pair   $2c sin  $2d cos
;     $33 dry L   $34 dry R   $35 v L   $36 v R   $3d/$3e chain inputs L/R
;   free: $14 $18 $1d-$1f $23 $24 $2e-$31 $3f $80-$83
;   the four Hilbert chains: each section is an allpass in z^-2, so even and
;   odd samples run independent state. $40-$5f is one parity's half, $60-$7f
;   the other's, toggled each sample ($37); within a half, 16 sections x
;   [y[n-2], x[n-2]] in chain order A-L, B-L, A-R, B-R. r1 reads each pair;
;   r2 writes x[n-2] <- in in the sub's parallel slot, then y[n-2] <- y[n]
;   and on to the next section's X slot (n2 = 3). Do not reorder.
;   $84..$8a is host-owned: nothing there survives across calls, and
;   LOFI2 uses none of it (CHIP.md section 5).
; ---- boot garbage --------------------------------------------------------
; `init` zeroes $00..$83 from r7, as stock LO-FI's own init does
; (verify_dirty_state). Beyond that, the state tolerates garbage:
;   * carrier phase: any value is a legal phase, and A1 extraction wraps it.
;   * held pair: at worst one wrong sample before the first latch.
;   * SRR phase: init zeroes it, and it stays in 0 .. 1.0 by construction.
;
; CYCLES_FORWARD_BRANCHES
; Every conditional branch in the sample loop jumps FORWARD and can only
; SKIP code, so the word span remains a ceiling: the two modulator gates
; (the SRR latch is branch-free, with Tccs). A backward one would be a loop
; the span counts once, which that declaration must never be used to hide.
;
; Every mpy is `mpy x0,y1`, `mpy y0,x0` or `mpy y1,x1` -- the operand orders
; dsp_asm encodes SIGNED (y1,x1 checked in the listing: 0x..f0, QQQ=111,
; not 01278f mpysu; it is the Hilbert sections' only form). AND and ASL leave A2 STALE and a store would
; then saturate, so every value passing through one leaves via a1 into a
; clean register first.
; ---------------------------------------------------------------------------

init:
; ---- every slot to zero (verify_dirty_state; AGENTS.md "a persistent slot
; that init does not clear"). r5, never r1: the FX1 dispatcher keeps the
; effect id in r1 across this call (verify_init_regs). $00..$83 is the whole
; block, so no per-slot census can go stale. The smoothed shelf coefficient
; at $08 starts at 0 and glides to its target over the first few hundred
; samples, which on silence produces nothing.
        clr     a
        move    r7,r5
        move    #>$ffffff,m5
        do      #$84,>lfiniz
        move    a,x:(r5)+
lfiniz:
        nop
; start fully ducked: the first block takes the knob's MODE and fades the
; wet in over the duck's 5 ms instead of starting it with a step
        move    #>$7fffff,x0
        move    x0,x:(r7+$11)
; SRR's rate starts at 1.0 (a latch every sample) and glides to the knob's
        move    #$40,x0                  ; (short immediate: bits 23-16)
        move    x0,x:(r7+$17)
; the Hilbert chains start on the even half
        move    #>$40,x0
        move    x0,x:(r7+$37)
        rts

proc:
; ---- per-block knob decode ------------------------------------------------
        move    x:(r6+$1),a             ; m = MIX, value<<16
        and     #>$7fff00,a             ; the knob AND its LFO fraction (bits 15-8)
        move    a1,x0
        move    x0,x:(r7+$01)

        move    x:(r6+$c),a             ; RANGE, slot 6, knob field
        and     #>$7f0000,a
        move    a1,x0
        move    x0,x:(r7+$21)

        move    x:(r6+$d),a             ; MODE, slot 8, knob field
        and     #>$7f0000,a
        move    a1,x0
        move    x0,x:(r7+$15)           ; MODE as the knob has it

; ---- the MODE duck --------------------------------------------------------
; A MODE change swaps one modulator for an unrelated one (or reverses the
; carrier, UP <-> DOWN),
; a step in the output. So the wet is ducked to dry over 5 ms, the running
; mode switches only once it is fully out, and the wet comes back over 5 ms.
; Only the running mode ($10) reaches the flags below, never the knob. The
; switch waits for a block boundary, so the wet may sit out for up to one
; block (16 samples) longer. MIX then runs at m*(1-e), exactly m when e = 0.
        move    x:(r7+$11),a            ; e
        move    #>$7fff00,x1
        sub     x1,a                    ; >= 0: fully ducked
        move    x:(r7+$10),b            ; the running mode
        tpl     x0,b                    ; fully ducked: take the knob's
        move    b,x:(r7+$10)
        move    b,x:(r7+$22)            ; every flag below reads THIS
        move    x:(r7+$15),a
        sub     b,a                     ; knob - running; Z when they agree
        move    #>$949c,b               ; +1/220.5 a sample: duck
        move    #>$ff6b64,y1            ; -1/220.5 a sample: recover
        teq     y1,b
        move    b,x:(r7+$13)

; shift flag: 1 in MODE 1 and 2. Resolved at block setup with the ring flag.
        move    x:(r7+$22),a
        tst     a
        beq     lf_noshf
        move    #>$1,a
        bra     lf_shf
lf_noshf:
        clr     a
lf_shf:
        move    a,x:(r7+$32)

; The direction (DOWN vs UP) is the carrier's: see "the shifter's
; direction" below, after the step is known. Selector order is RING / DOWN /
; UP, so the encoder walks the sidebands in pitch order with RING at one end.

; fdbk = FDBK * 0.40. Inactive in RING by design: ring feedback is a
; harmonic-order generator, not a ladder, and was not wanted. The cap was
; 0.45 (BodeShift's) until sambanks/octabam#825: see the loop gain below.
        move    x:(r6+$2),a
        and     #>$7fff00,a             ; the knob AND its LFO fraction
        move    a1,x0
        move    #>$333333,y1            ; 0.40
        mpy     x0,y1,a
        move    a,x:(r7+$05)

; GAIN = 2^(k/64) on the same knob word, read only by the RING block. Stored
; as GAIN/4 (it reaches 3.96) and restored there with asl #2. k/64 = n + f:
; n is bit 23 of the doubled knob word, f the 23 bits below it, and
; 2^f = 1 + 0.66023 f + 0.33977 f^2 (exact at 0 and 1, within 0.023 dB
; between). h = 2^f / 2; GAIN/4 = h at n = 1, h/2 at n = 0. GAIN 0 is
; therefore exactly 0.25 * 4: unity, bit-exact.
        move    x:(r6+$2),a
        and     #>$7fff00,a             ; the knob AND its LFO fraction
        asl     #$1,a,a                 ; k/64: bit 23 = n, bits 22-0 = f
        move    a1,x1
        move    x1,a
        and     #>$7fffff,a
        move    a1,x0                   ; f
        move    #>$2a4135,a             ; 0.66023/2
        move    #>$15becb,y1            ; 0.33977/2
        mac     x0,y1,a                 ; 0.33012 + 0.16989 f
        move    a,y1
        move    #$40,a                   ; 0.5 (short immediate: bits 23-16)
        mac     x0,y1,a                 ; h = 2^f / 2
        move    a,x0
        asr     #$1,a,a
        move    a,y0                    ; h/2
        move    x1,b
        tst     b                       ; N: n = 1
        move    y0,a
        tmi     x0,a
        move    a,x:(r7+$03)            ; GAIN/4

; ring flag: 1 only in MODE 0. Resolved HERE, at block setup -- a dispatch
; inside the sample loop could not be priced by tools/cycle_count.py.
        move    x:(r7+$22),a
        tst     a
        bne     lf_noring
        move    #>$1,a
        bra     lf_ringf
lf_noring:
        clr     a
lf_ringf:
        move    a,x:(r7+$27)

; ---- BRR -> the quantiser's step exponent, from our own table ------------
; Our own quantiser (the loop below): y = round(x * 2^-E) * 2^E, E the step
; above the LSB in bits. The target E comes from the module's own table
; (manifest.py, BRR_E, 129 words after SRR_INC), indexed by the knob and
; interpolated by the knob word's LFO fraction; the loop glides to it.
; E is held as bits * 2^17: the whole bits in 22..17, the fraction below.
        move    #>$ffffff,m5
        move    #>$fab1e0,r5            ; the ptable's base, placed by the build
        move    r5,x:(r7+$25)           ; kept for SRR and the loop: the build
                                        ; wants the base literal exactly once
        move    x:(r6+$4),a
        and     #>$7fff00,a             ; the knob AND its fraction (bits 15-8)
        move    a1,x1
        asr     #$10,a,a
        add     #>$81,a                 ; k + 129
        move    a1,n5
        move    x1,a
        and     #>$00ff00,a
        asl     #$7,a,a
        move    a1,x0                   ; the fraction, Q23
        move    (r5)+n5
        move    p:(r5)+,y0              ; E[k]
        move    p:(r5),b                ; E[k+1]
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a
        move    a,x:(r7+$28)            ; the target; $29 glides to it

; ---- LPF -> the shelf's corner and depth, from our own table ------------
; A first-order high shelf of our own (the loop below): unity at DC, 1/4
; (-12.04 dB) at Nyquist, no resonance, so its gain never exceeds 1 at any
; frequency -- safe inside a feedback loop. The corner is the allpass
; coefficient c from the module's own table (manifest.py, LPF_C, 129 words
; at +387), an exponential sweep of the allpass break frequency from 100 Hz
; at 0 to 16 kHz at 126, indexed by the knob and interpolated by its LFO
; fraction. The depth kd is 3/4 at 0..126 and 0 at 127, where the shelf is
; out of circuit bit for bit. The loop glides both.
        move    x:(r6+$5),a
        and     #>$7fff00,a             ; the knob AND its fraction (bits 15-8)
        move    a1,x1
        asr     #$10,a,a
        move    a1,y0                   ; k
        add     #>$183,a                ; k + 387
        move    a1,n5
        move    #$60,b                   ; kd = 3/4: the shelf in (short immediate: bits 23-16)
        move    #$00,x0                  ; (short immediate: bits 23-16)
        move    y0,a
        sub     #>$7f,a
        teq     x0,b                    ; k = 127: out
        move    b,x:(r7+$0b)            ; kd target; $0a glides to it
        move    x1,a
        and     #>$00ff00,a
        asl     #$7,a,a
        move    a1,x0                   ; the fraction, Q23
        move    x:(r7+$25),r5           ; the ptable's base (m5 set above)
        move    (r5)+n5
        move    p:(r5)+,y0              ; c[k]
        move    p:(r5),b                ; c[k+1]
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a
        move    a,x:(r7+$09)            ; c target; $08 glides to it

; ---- SRR -> the hold's rate, from our own table -------------------------
; A fractional sample-and-hold: a phase advances by `inc` a sample and the
; held pair is re-latched on each wrap, so the hold lasts 1/inc samples on
; average. inc comes from the module's own 129-word table (manifest.py,
; SRR_INC), indexed by the knob and interpolated by the knob word's bits
; 15-8 -- the fraction an LFO leaves there, which is what lets a modulated
; SRR sweep smoothly instead of in 128 steps.
;
; The curve is stock LO-FI's as MEASURED ON THE UNIT (10 Oct 2026, a 1 kHz
; tone over USB, the rate read from the image positions): 8,018 Hz at 64,
; 3,564 Hz at 127. As a hold length L(k) = (k+128)^2/4096 - 3.5 samples,
; floored at 1: 1 at 0, 5.50 at 64, 12.37 at 127.
;
; Phase units: 1.0 = $400000, so inc runs up to exactly 1.0 (a latch every
; sample, no reduction) without leaving Q23.
        move    #>$ffffff,m5
        move    x:(r7+$25),r5           ; the ptable's base: SRR_INC
        move    x:(r6+$3),a
        and     #>$7fff00,a             ; the knob AND its fraction (bits 15-8)
        move    a1,x1
        asr     #$10,a,a
        move    a1,n5                   ; k, 0..127
        move    x1,a
        and     #>$00ff00,a
        asl     #$7,a,a
        move    a1,x0                   ; the fraction, Q23
        move    (r5)+n5
        move    p:(r5)+,y0              ; inc[k]
        move    p:(r5),b                ; inc[k+1]
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a                 ; frac * (inc[k+1] - inc[k])
        add     y0,a
        move    a,x:(r7+$16)            ; the rate's target; $17 glides to it

; ---- FREQ -> carrier step, SIX OCTAVES, EXPONENTIAL ----------------------
; The MF-102's ranges are 2-130 Hz and 60-4000 Hz, both six octaves, so the
; taper is exponential -- constant cents per degree of rotation. Neither
; BodeShift nor Character has this; both use squared tapers, which cramp the
; bottom of a carrier knob and coarsen the top.
;
; step is WarpFold's convention: the phase spans the full 24 bits as one
; cycle, so a Q23 value of 1.0 is half a cycle and step = 2*f/fs.
;   base step, f=0:  LOW  2 Hz -> $0002f9      HIGH 60 Hz -> $00593d
;
; ⚠️ NO ZERO. FREQ=0 is the base frequency, not silence. Character's
; "skip the multiply at step 0" gate does not apply and the cycle count must
; assume the carrier always runs.
; The base depends on MODE as well as RANGE, because the two effects have
; different ancestors. RING follows the MF-102: 2-130 Hz and 60-4000 Hz.
; SHIFT follows the Bode 1630, whose exponential scale is 2 Hz to 2 kHz --
; so LOW keeps the same 2 Hz floor and HIGH starts at 31.25 Hz, six octaves
; from which is exactly 2000 Hz. The 1630's four LINEAR scales are
; deliberately not offered: MODE already picks the direction they exist for.
        move    x:(r7+$32),a            ; shift?
        tst     a
        bne     lf_sbase
        move    x:(r7+$21),a            ; RING bases
        tst     a
        beq     lf_rlow
        move    #>$00593d,x0            ; HIGH: 60 Hz
        bra     lf_rdone
lf_rlow:
        move    #>$0002f9,x0            ; LOW: 2 Hz
        bra     lf_rdone
lf_sbase:
        move    x:(r7+$21),a            ; SHIFT bases
        tst     a
        beq     lf_slow
        move    #>$002e71,x0            ; HIGH: 31.25 Hz -> 2 kHz at the top
        bra     lf_rdone
lf_slow:
        move    #>$0002f9,x0            ; LOW: 2 Hz
lf_rdone:
        move    x0,x:(r7+$0d)           ; park the base step

; t = 0.75 * knob, so the six octaves land in bits 22..20 (integer) and the
; rest is the fraction. The knob word IS knob/128, so t = 6*knob/128 / 8.
; The knob's LFO fraction (bits 15-8) is KEPT: one knob step is 6/128 of an
; octave, 56 cents, so an LFO on FREQ needs the bits between the steps.
        move    x:(r6+$0),a
        and     #>$7fff00,a             ; the knob AND its fraction
        move    a1,x0
        move    #$60,y1                  ; 0.75 (short immediate: bits 23-16)
        mpy     x0,y1,a
        move    a1,x1                   ; t

        move    x1,a                    ; n = whole octaves, 0..5
        and     #>$700000,a
        move    a1,x0
        move    x0,a
        asr     #$14,a,a
        move    a1,y0                   ; the octave shift count

        move    x1,a                    ; f = fractional octave, back to [0,1)
        and     #>$0fffff,a
        move    a1,x0
        move    x0,a
        asl     #$3,a,a
        move    a1,x1                   ; f

; h = 2^f / 2, quadratic: 0.5 + f*(0.328125 + f*0.171875). Halved because
; 2^f reaches 2.0, which Q23 cannot hold; the octave shift below puts it
; back. The coefficients sum to exactly 1.0 so h(1) = 1.0 exactly and the
; octave boundaries are seamless. Worst-case error is about 5 cents near
; f = 0.25 -- inaudible on a carrier, and the alternative is a cubic.
        move    x1,x0
        move    #$16,y1                  ; 0.171875 (short immediate: bits 23-16)
        mpy     x0,y1,a
        add     #>$2a0000,a             ; + 0.328125
        move    a,y1
        move    x1,x0                   ; f
        mpy     x0,y1,a
        add     #>$400000,a             ; + 0.5
        move    a,y1                    ; h, in [0.5, 1.0)

; step = base * h, then shifted up (n+1) times: the +1 undoes h's halving.
        move    x:(r7+$0d),x0
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$0d)
        move    y0,b                    ; ⚠️ a `do` with a count of 0 runs
        tst     b                       ;  65536 times, so guard it
        beq     lf_noct
        move    x:(r7+$0d),a
        do      y0,>lf_octl
        asl     #$1,a,a
        move    a1,x0
        move    x0,a
lf_octl:
        nop
        move    a,x:(r7+$0d)
lf_noct:

; ---- AMPH -> the L/R carrier phase offset --------------------------------
; BIPOLAR: the phase word spans one
; cycle over 24 bits, so the knob word less $400000 (knob 64) is exactly
; -1/4..+1/4 cycle: -90..+88.6 degrees, 1.4 a step, 0 at the centre. Every
; distinct stereo motion of a ring mod lives inside +-90 (theta and
; 180-theta give the same envelope, lead and lag swapped); the sign says
; which channel leads. Wraps in A1 exactly as the phase itself does.
        move    x:(r6+$e),a
        and     #>$7fff00,a             ; the knob AND its LFO fraction
        sub     #>$400000,a
        move    a1,x0
        move    x0,x:(r7+$07)

; ---- the shifter's direction -------------------------------------------
; DOWN runs the carrier backwards: sin(-t) = -sin(t) while cos is even, so
; I*cos + Q*sin(-t) is I*cos - Q*sin(t), the lower sideband, with no sign
; multiply in the sample loop. The target step is negated for DOWN, and the
; step in use is given the same sign here, so a MODE change (made only once
; the wet is fully ducked) never glides the carrier through 0 Hz. RING and
; UP run forwards.
        move    x:(r7+$0c),a
        abs     a
        move    a,x:(r7+$0c)
        move    x:(r7+$22),a
        move    #>$10000,x0
        cmp     x0,a                    ; MODE 1 = DOWN?
        bne     lf_fwd
        move    x:(r7+$0d),a
        neg     a
        move    a,x:(r7+$0d)
        move    x:(r7+$0c),a
        neg     a
        move    a,x:(r7+$0c)
lf_fwd:

; ---- the glides' per-block steps -----------------------------------------
; Each continuous knob but BRR's E (which keeps the per-sample one-pole, in
; the loop) glides toward its target as a one-pole at the block
; rate (63/64 a sample over 16 samples, the per-sample glide's own rate),
; spread over the block as a linear ramp: lf_gset works out the step once
; per block and the loop only adds it (4 words a glide, no call). When the
; step rounds to nothing the value snaps onto the target, so 0, unity and
; the LPF bypass are still exact, as with the per-sample glide. The step is parked in the TARGET's slot: every
; target is recomputed above at each block and read nowhere else.
        move    x:(r7+$0d),y0
        move    x:(r7+$0c),x0
        bsr     lf_gset
        move    x0,x:(r7+$0c)
        move    x1,x:(r7+$0d)
        move    x:(r7+$01),y0
        move    x:(r7+$00),x0
        bsr     lf_gset
        move    x0,x:(r7+$00)
        move    x1,x:(r7+$01)
        move    x:(r7+$03),y0
        move    x:(r7+$02),x0
        bsr     lf_gset
        move    x0,x:(r7+$02)
        move    x1,x:(r7+$03)
        move    x:(r7+$05),y0
        move    x:(r7+$04),x0
        bsr     lf_gset
        move    x0,x:(r7+$04)
        move    x1,x:(r7+$05)
        move    x:(r7+$07),y0
        move    x:(r7+$06),x0
        bsr     lf_gset
        move    x0,x:(r7+$06)
        move    x1,x:(r7+$07)
        move    x:(r7+$09),y0
        move    x:(r7+$08),x0
        bsr     lf_gset
        move    x0,x:(r7+$08)
        move    x1,x:(r7+$09)
        move    x:(r7+$0b),y0
        move    x:(r7+$0a),x0
        bsr     lf_gset
        move    x0,x:(r7+$0a)
        move    x1,x:(r7+$0b)
        move    x:(r7+$16),y0
        move    x:(r7+$17),x0
        bsr     lf_gset
        move    x0,x:(r7+$17)
        move    x1,x:(r7+$16)

; ---- sample loop ----------------------------------------------------------
        move    #>$1,n0
        move    x:(r7+$37),n1           ; the Hilbert chains' parity half, $40 or $60
        move    #>$3,n2                 ; r2's stride: a section's Y slot to the next X slot
        move    #>$ffffff,m1            ; r1/r2 walk linearly, whatever the
        move    #>$ffffff,m2            ;  effect before us left in m1/m2
        move    #>$2,n3                 ; r3: in-use slot to in-use slot
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        do      n7,>lf_end

; park the dry pair (v, the modulated signal, is written by whichever
; modulator runs: the ring and shift flags are exact complements)
        move    x:(r0),x1
        move    x1,x:(r7+$33)
        move    x:(r0+n0),x1
        move    x1,x:(r7+$34)

; The continuous page-1 knobs glide to the block's values (lf_gset's
; per-block step, added here each sample; about 1.5 ms), so a turned knob or
; an LFO sweeps instead of stepping at the block rate: FREQ's carrier step, MIX, GAIN, FDBK and
; AMPH's offset. Here, before the fork, because both modulators read them.
; The seven glides lf_gset steps (MIX, GAIN, FDBK, AMPH, LPF c and kd, the
; carrier step) sit in pairs, in use then step, at $00..$0d: r4 walks the
; pairs reading, r3 trails writing each new in-use value (n3 = 2), and every
; store rides an add as a parallel move, alternating a and b.
        move    r7,r4
        move    r7,r3
        move    x:(r4)+,b               ; MIX in use
        move    x:(r4)+,x0              ; its step
        add     x0,b      x:(r4)+,a     ; MIX'       ; a = GAIN in use
        move    x:(r4)+,x0
        add     x0,a      b,x:(r3)+n3   ; GAIN'      ; MIX' stored
        move    x:(r4)+,b               ; FDBK in use
        move    x:(r4)+,x0
        add     x0,b      a,x:(r3)+n3   ; FDBK'      ; GAIN' stored
        move    x:(r4)+,a               ; AMPH in use
        move    x:(r4)+,x0
        add     x0,a      b,x:(r3)+n3   ; AMPH'      ; FDBK' stored
        move    x:(r4)+,b               ; LPF c in use
        move    x:(r4)+,x0
        add     x0,b      a,x:(r3)+n3   ; c'         ; AMPH' stored
        move    x:(r4)+,a               ; LPF kd in use
        move    x:(r4)+,x0
        add     x0,a      b,x:(r3)+n3   ; kd'        ; c' stored
        move    x:(r4)+,b               ; carrier step in use
        move    x:(r4)+,x0
        add     x0,b      a,x:(r3)+n3   ; carrier'   ; kd' stored
        move    b,x:(r3)+n3             ; carrier' stored
        move    b,y0                    ; the step in use, for whichever modulator

; MODEFORK_BEGIN -- cycle_count.py: RING and SHIFT are MUTUALLY EXCLUSIVE.
; Without these markers the tool sums both and prices a whole engine that
; can never run on the same sample. BEGIN..first MID is the dispatch.
        nop
; MODEFORK_MID -- alternative 1: RING
; ---- MODULATOR: ring mod, MODE 0 only ------------------------------------
; Forward branch, and it SKIPS work, so the word span is still the worst-case
; cycle count. In MODE 1/2 the carrier does not advance either -- there is no
; continuity to preserve when nothing reads it, and the shifter has its own
; oscillator.
        move    x:(r7+$27),a            ; ring flag
        tst     a
        beq     lf_nomod

; carrier: WarpFold's parabolic sine 4*p*(1-|p|) on a phase wrapped by A1
; extraction -- continuous at the wrap, exact +/-1 peaks.
        move    x:(r7+$1c),a            ; phase; y0 = the step, glided
        add     y0,a
        move    a1,x0                   ; p, wrapped
        move    x0,x:(r7+$1c)
        move    x0,a                    ; clean
        abs     a
        move    #$80,y1                  ; -1.0 (short immediate: bits 23-16)
        add     y1,a                    ; |p| - 1
        neg     a                       ; t = 1 - |p|
        move    a,y1
        mpy     x0,y1,a                 ; p*t
        asl     #$2,a,a                 ; carrier L = 4*p*t
        move    a,y1
        move    x:(r7+$33),x0           ; dry L
        mpy     x0,y1,a
        move    a,x0
        move    x:(r7+$02),y1           ; GAIN/4, glided
        mpy     x0,y1,a
        asl     #$2,a,a                 ; x GAIN; the store limits
        move    a,x:(r7+$35)            ; v L

; the R carrier is the same shape read at p + AMPH; at AMPH=0 the offset is
; zero and the two are identical, so this costs cycles rather than a branch
        move    x:(r7+$1c),a
        move    x:(r7+$06),x0           ; amph offset, glided
        add     x0,a
        move    a1,x0                   ; pR, wrapped
        move    x0,a
        abs     a
        move    #$80,y1                  ; (short immediate: bits 23-16)
        add     y1,a
        neg     a
        move    a,y1
        mpy     x0,y1,a
        asl     #$2,a,a                 ; carrier R
        move    a,y1
        move    x:(r7+$34),x0           ; dry R
        mpy     x0,y1,a
        move    a,x0
        move    x:(r7+$02),y1           ; GAIN/4, glided
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x:(r7+$36)            ; v R
lf_nomod:


; MODEFORK_MID -- alternative 2: SHIFT (the expensive one: 16 allpass
; sections and two sines, against the ring's single carrier)
; ---- MODULATOR: frequency shifter, MODE 1 (DOWN) and 2 (UP) --------------
; STEREO: two independent Hilbert pairs, one shared oscillator. BodeShift
; computes its analytic pair on (L+R)/4 and gets away with it because WIDE
; derives its stereo from the two DIRECTIONS; with WIDE dropped a mono wet
; would put every shifted partial dead centre and collapse the image
; entirely at MIX=127. So each channel gets its own chain A and chain B.
; Ring mod needs none of this -- one carrier multiplies both channels and
; the image survives untouched.
        move    x:(r7+$32),a            ; shift flag
        tst     a
        beq     lf_noshift

; in = 0.5*dry + fdbk*lastwet, per channel. The x2 that forms the wet is
; INSIDE the loop, so the loop gain is 2*fdbk, not fdbk: 0.8 at the cap.
; The Hilbert pair cannot shift DC or Nyquist (every section is -1 at
; z = +-1, so I/Q collapses to 0 degrees there and DC comes back as a
; carrier-rate tone with sqrt(2) the amplitude, and back again), so the
; worst two-pass gain is (2 fdbk)^2 sqrt(2): 0.905 at 0.40. At the old 0.45
; it was 1.15, and FDBK 124-127 at FREQ about 56-72 in HIGH self-oscillated
; up to the limiter (#825).
        move    x:(r7+$33),a            ; dry L
        asr     #$1,a,a
        move    x:(r7+$3b),x0           ; lastwet L
        move    x:(r7+$04),y1           ; fdbk, glided
        mac     x0,y1,a
        move    a,x:(r7+$3d)
        move    x:(r7+$34),a            ; dry R
        asr     #$1,a,a
        move    x:(r7+$3c),x0           ; lastwet R
        mac     x0,y1,a                 ; y1 = fdbk still
        move    a,x:(r7+$3e)

; ---- the oscillator, ONCE for both channels ------------------------------
        move    x:(r7+$1c),a            ; phase (shared with the ring mod --
        add     y0,a                    ;  the two modes are exclusive)
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$1c)
        move    x0,b                    ; the phase, kept across the sine (a, x0, x1, y1)
; ---- sin(pi*p) for p in [-1,1), inline: BodeShift's, from WarpFold's carrier,
; the parabola 4p(1-|p|) refined by the 0.775/0.225 correction; p and the
; result in A
        move    a,x1
        abs     a
        move    #$80,x0                  ; (short immediate: bits 23-16)
        add     x0,a                    ; |p| - 1
        neg     a                       ; t = 1 - |p|
        move    a,y1
        move    x1,x0
        mpy     x0,y1,a                 ; p*t
        asl     #$2,a,a                 ; y = 4p(1-|p|)
        move    a,x1
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
        move    a,x:(r7+$2c)            ; sin
        move    #$40,x0                  ; (short immediate: bits 23-16)
        add     x0,b                    ; + a quarter turn
        move    b1,x0
        move    x0,a
; ---- the same sine, a quarter turn on: cos ----
        move    a,x1
        abs     a
        move    #$80,x0                  ; (short immediate: bits 23-16)
        add     x0,a                    ; |p| - 1
        neg     a                       ; t = 1 - |p|
        move    a,y1
        move    x1,x0
        mpy     x0,y1,a                 ; p*t
        asl     #$2,a,a                 ; y = 4p(1-|p|)
        move    a,x1
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
        move    a,x:(r7+$2d)            ; cos

; ---- the four Hilbert chains ---------------------------------------------
; POINTER-WALKED, not displacement-addressed: an ALU op can carry a memory
; move in the same word, but only with (rn) addressing -- never with
; r7+displacement. That is the whole reason BodeShift's sections cost what
; they do (21 words against 6 here).
;
; PARITY-SPLIT STATE. Each section is H(z) = (c - z^-2)/(1 - c z^-2):
;   y[n] = c*(x[n] + y[n-2]) - x[n-2]
; Olli Niemitalo's 90-degree allpass section, so c = a^2. His published
; values are the a's (chain A 0.6923877778065, 0.9360654322959,
; 0.9882295226860, 0.9987488452737; chain B 0.4021921162426,
; 0.8561710882420, 0.9722909545651, 0.9952884791278); loading a unsquared
; bends the I/Q difference off 90 degrees and costs some 30 dB of image
; rejection at 3-5 kHz. verify_lofi2 gates the image across the band.
; Only the n-2 values are read, so even and odd samples are two independent
; recursions. Each parity keeps its own [y[n-2], x[n-2]] per section, and a
; sample overwrites its own pair with [y[n], x[n]], which are exactly what
; the same parity reads two samples later. Half the state traffic of a
; single shifting set, and the same arithmetic in the same order: the
; output is bit-identical to the four-word layout it replaced (12 Oct 2026).
; The halves are $40-$5f and $60-$7f; n1 holds this sample's ($37 across
; blocks, since a block can be split to an odd length).
;
; ONE setup covers all four chains: they sit contiguously within the half in
; the order they run, so the pointers walk the half once per sample.
; ⚠️ Anything inserted between the chains must therefore leave r1 and r2
; alone.
; $40 is past lua's -64..63 displacement (`lua (r7+$40)` assembles to
; r7-$40; AGENTS.md), so the base is r7 + n1.
        move    r7,r1
        move    n1,a                    ; the other half next sample: $40 <-> $60
        move    #>$20,x0                ; (these two fill r1's wait before the step)
        move    (r1)+n1                 ; this sample's parity half (n1 not flipped yet)
        move    r1,r2
        eor     x0,a                    ; EOR in the register form (stock uses eor x0,b /
                                        ; x1,b; stock has no EOR #imm site, #704 review)
        move    (r2)+                   ; r2 writes from section 0's X slot
        move    a1,n1                   ; the flip, for the next sample

        move    x:(r7+$3d),x1          ; chain A-L input
; ---- chain A-L section 0: allpass, c = a^2 = 0.4794008348558 ----
        move    #>$3d5d02,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
; ---- chain A-L section 1: allpass, c = a^2 = 0.8762184935393 ----
        move    #>$7027ed,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
; ---- chain A-L section 2: allpass, c = a^2 = 0.9765975895082 ----
        move    #>$7d0126,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
; ---- chain A-L section 3: allpass, c = a^2 = 0.9974992559355 ----
        move    #>$7fae0e,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
; I is chain A's output delayed one sample
        move    x:(r7+$39),x0           ; I_L = aPrev L
        move    x1,x:(r7+$39)
        move    x:(r7+$2d),y1           ; cos
        mpy     x0,y1,b                 ; I*cos: b is free while the chains run,
        move    b,y0                    ;  and y0 is untouched by them (limited, as
        move    x:(r7+$3d),x1          ;  the old park was); chain B-L input
; ---- chain B-L section 0: allpass, c = a^2 = 0.1617584983677 ----
        move    #>$14b481,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
; ---- chain B-L section 1: allpass, c = a^2 = 0.7330289323415 ----
        move    #>$5dd3e4,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
; ---- chain B-L section 2: allpass, c = a^2 = 0.9453497003291 ----
        move    #>$790138,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
; ---- chain B-L section 3: allpass, c = a^2 = 0.9905991566845 ----
        move    #>$7ecbf4,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
        move    x1,x0                   ; Q_L
        move    x:(r7+$2c),y1           ; sin
        mpy     x0,y1,a                 ; Q*sin, the direction already in sin
        add     y0,a                    ; + I*cos
        asl     #$1,a,a                 ; the x2 undoing the input halving
        move    a,x:(r7+$3b)            ; lastwet L, the feedback tap
        move    a,x:(r7+$35)            ; v L

        move    x:(r7+$3e),x1          ; chain A-R input
; ---- chain A-R section 0: allpass, c = a^2 = 0.4794008348558 ----
        move    #>$3d5d02,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
; ---- chain A-R section 1: allpass, c = a^2 = 0.8762184935393 ----
        move    #>$7027ed,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
; ---- chain A-R section 2: allpass, c = a^2 = 0.9765975895082 ----
        move    #>$7d0126,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
; ---- chain A-R section 3: allpass, c = a^2 = 0.9974992559355 ----
        move    #>$7fae0e,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
        move    x:(r7+$3a),x0           ; I_R = aPrev R
        move    x1,x:(r7+$3a)
        move    x:(r7+$2d),y1           ; cos
        mpy     x0,y1,b
        move    b,y0
        move    x:(r7+$3e),x1          ; chain B-R input
; ---- chain B-R section 0: allpass, c = a^2 = 0.1617584983677 ----
        move    #>$14b481,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
; ---- chain B-R section 1: allpass, c = a^2 = 0.7330289323415 ----
        move    #>$5dd3e4,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
; ---- chain B-R section 2: allpass, c = a^2 = 0.9453497003291 ----
        move    #>$790138,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
; ---- chain B-R section 3: allpass, c = a^2 = 0.9905991566845 ----
        move    #>$7ecbf4,y1
        mpy     y1,x1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = x[n-2]
        sub     x0,a      x1,x:(r2)-    ; a = y[n]       ; x[n-2] slot <- in
        move    a,x:(r2)+n2             ; y[n-2] slot <- y[n]; r2 to the next X slot
        move    a,x1
        move    x1,x0                   ; Q_R
        move    x:(r7+$2c),y1
        mpy     x0,y1,a
        add     y0,a
        asl     #$1,a,a
        move    a,x:(r7+$3c)            ; lastwet R
        move    a,x:(r7+$36)            ; v R

; (the sidebands, wet = 2*(I*cos + Q*sin), are formed right after each
; channel's B chain above)
lf_noshift:
; MODEFORK_END

; (LPF c and kd glide with the others, in the walk before the fork; kd still
; lands on exactly 0 at LPF 127, lf_gset's snap)

; ---- the MODE duck, per sample: e moves one step toward its target -------
; Floored at 0 by tmi, capped near 1 by the store's limiter.
        move    x:(r7+$11),a            ; e
        move    x:(r7+$13),x0           ; the step, signed
        add     x0,a
        move    #$00,x0                  ; (short immediate: bits 23-16)
        tmi     x0,a
        move    a,x:(r7+$11)
        move    a,x0                    ; e as stored (the same limiting)
        move    x:(r7+$00),y1           ; m, glided
        mpy     x0,y1,b                 ; m*e
        move    y1,a
        sub     b,a                     ; m*(1-e): exactly m at e = 0
        move    a,y1                    ; held in y1 for both channels (limited,
                                        ;  as the old park in $14 was)

; ---- MIX: crossfade the MODULATOR against the dry, HERE ------------------
; MIX is the modulator's depth, NOT a global wet/dry -- it sits between the
; ring/shift stage and the reduction stage, so SRR and BRR run on the result
; UNCONDITIONALLY and stay live at MIX=0. That is how stock LO-FI works: AMD
; crossfades the ring mod while SRR and BRR are always in circuit.
;   out = dry + m*(v - dry), the halve/double straddle keeping the difference
;   inside the accumulator when v and dry have opposite signs.
; ⚠️ There is therefore NO single-knob bypass. A passthrough is MIX 0 AND
; SRR 0 AND BRR 0 -- still the default state, so a freshly selected LOFI2 is
; transparent, but the null test needs all three at zero.
        move    x:(r7+$35),a            ; v L
        move    x:(r7+$33),b            ; dry L
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a                 ; y1 = m*(1-e)
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$35)

        move    x:(r7+$36),a            ; v R
        move    x:(r7+$34),b            ; dry R
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a                 ; y1 = m*(1-e) still
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$36)

; ---- SRR: glide the rate, advance the phase, latch the MODULATED pair ---
; The rate glides by lf_gset's per-block step, added every sample (about
; 1.5 ms), so a turned knob never steps at the block rate.
        move    x:(r7+$17),b           ; the rate in use
        move    x:(r7+$16),x0           ; this block's step (target)
        add     x0,b
        move    b,x:(r7+$17)
        move    b,x0                    ; inc (the same limiting as the store)
        move    x:(r7+$1b),b            ; phase, 0 .. < $400000
        add     x0,b                    ; phase + inc
        move    #$40,x1                  ; (short immediate: bits 23-16)
        move    b,a
        sub     x1,a                    ; >= 0: it wrapped
        move    a,y0
        tge     y0,b                    ; wrapped: phase - 1.0
        move    b,x:(r7+$1b)
; The latch, branch-free: the one compare above drives all three Tccs, and
; only moves sit between them (AGENTS.md, the shared-compare trap).
        move    x:(r7+$19),b
        move    x:(r7+$35),y1           ; latch v, not the dry
        tge     y1,b
        move    b,x:(r7+$19)
        move    x:(r7+$1a),b
        move    x:(r7+$36),y1
        tge     y1,b
        move    b,x:(r7+$1a)

; ---- BRR: glide E, then the shift and the mantissa pair, once a sample ---
; E moves 1/64 of the way to its target each sample and snaps to it when
; that step rounds to nothing (Modulation's mo_glide). The step is reloaded
; through a register before the test: `asr` leaves a remainder in a0 and Z
; needs all 56 bits clear (AGENTS.md).
; Inline, and the one glide NOT on lf_gset's per-block ramp: E is the
; exponent of a step that is mostly noise, so its trajectory is kept exactly
; as it was (verify_lofi2's BRR turn is measured against it).
        move    x:(r7+$28),y0           ; E target
        move    x:(r7+$29),x0           ; E in use
        move    y0,a
        sub     x0,a
        asr     #$6,a,a
        move    a,x1
        move    x0,b
        add     x1,b
        move    x1,a                    ; reloaded: Z needs all 56 bits clear
        tst     a
        teq     y0,b
        move    b,x:(r7+$29)
; n = whole bits (a variable shift), j = the fraction to 1/128 bit
        move    b,a
        asr     #$a,a,a
        and     #>$7f,a
        move    a1,x1                   ; j
        move    x:(r7+$25),a            ; the ptable's base: BRR_M at +258
        add     #>$102,a
        add     x1,a
        move    a1,r5
        move    p:(r5),y0               ; m = M[j] = 2^-(j/128), (0.5, 1]
        move    y0,x:(r7+$2a)
        move    x:(r7+$25),a
        add     #>$182,a
        sub     x1,a
        move    a1,r5
        move    p:(r5),y0               ; r = M[128-j] = 2^(j/128)/2 = 1/(2m)
        move    y0,x:(r7+$2b)
        move    b,a                     ; b = E still
        asr     #$11,a,a
        move    a1,y0                   ; n, in y0 for both channels

; ---- L: quantise the held sample and write it out ------------------------
; out = dry + m*(wet - dry). The halve/double straddle keeps the difference
; inside the accumulator when wet and dry have opposite signs.
        move    x:(r7+$19),x0           ; held L
        move    x0,x1                   ; kept for the E = 0 path
        move    x:(r7+$2a),y1           ; m
        mpy     x0,y1,a                 ; x * 2^-frac
        asr     y0,a,a                  ; * 2^-n (y0 = n)
        rnd     a                       ; to the nearest step
        asl     y0,a,a
        move    a,x0
        move    x:(r7+$2b),y1           ; 1/(2m)
        mpy     x0,y1,b
        asl     #$1,b,b                 ; back by 2^frac: exactly unity gain
                                        ; E = 0: the held sample (x1), untouched
        move    x:(r7+$29),a
        tst     a
        teq     x1,b

; ---- L: the shelf, LAST in the chain -------------------------------------
;   ap[n] = c*ap[n-1] + x[n-1] - c*x[n]      a first-order allpass
;   y     = x - kd*(x - ap)/2                 = (5/8)x + (3/8)ap at kd = 3/4
; At DC ap = x (y = x); at Nyquist ap = -x (y = x/4). kd = 0 is y = x exactly.
; The allpass keeps the bits its store drops (a0) and adds them back the
; next sample: first-order error feedback, so the rounding error is
; high-passed and cannot pile up into a dead band when c is near 1.
        move    b,x1                    ; x[n], the BRR output (limited)
        clr     a
        move    x:(r7+$0e),a0           ; last sample's dropped bits
        move    x:(r7+$08),y1           ; c, smoothed
        move    x1,x0
        mac     -x0,y1,a                ; - c*x[n]
        move    x:(r7+$12),x0           ; x[n-1]
        add     x0,a
        move    x:(r7+$20),x0           ; ap[n-1]
        mac     x0,y1,a                 ; ap[n], 48 bits
        move    a0,x:(r7+$0e)
        move    x1,x:(r7+$12)           ; x[n-1] <- x[n]
        move    a,x:(r7+$20)            ; ap[n-1] <- ap[n] (limited)
        move    a,x0
        move    x1,a
        sub     x0,a                    ; x - ap
        asr     a                       ; /2
        move    a,x0
        move    x:(r7+$0a),y1           ; kd, smoothed
        move    x1,a
        mac     -x0,y1,a
        move    a,x:(r0)

; ---- R: the same ---------------------------------------------------------
        move    x:(r7+$1a),x0           ; held R
        move    x0,x1
        move    x:(r7+$2a),y1
        mpy     x0,y1,a
        asr     y0,a,a
        rnd     a
        asl     y0,a,a
        move    a,x0
        move    x:(r7+$2b),y1
        mpy     x0,y1,b
        asl     #$1,b,b
        move    x:(r7+$29),a
        tst     a
        teq     x1,b

; ---- R: the same shelf, its own state ----------------------------------
        move    b,x1
        clr     a
        move    x:(r7+$0f),a0
        move    x:(r7+$08),y1
        move    x1,x0
        mac     -x0,y1,a
        move    x:(r7+$26),x0
        add     x0,a
        move    x:(r7+$38),x0
        mac     x0,y1,a
        move    a0,x:(r7+$0f)
        move    x1,x:(r7+$26)
        move    a,x:(r7+$38)
        move    a,x0
        move    x1,a
        sub     x0,a
        asr     a
        move    a,x0
        move    x:(r7+$0a),y1
        move    x1,a
        mac     -x0,y1,a
        move    a,x:(r0+n0)

        lua     (r0+$2),r0              ; the frame advance: one stereo frame, n0 stays 1
lf_end:
        nop
        move    n1,x:(r7+$37)           ; the parity carries into the next block
        rts

; ---------------------------------------------------------------------------
; lf_gset: one glide's step for this block. In: y0 = target, x0 = the value
; in use. Out: x1 = the per-sample step, (target - in use) * K with
; K = (1 - (63/64)^16) / 16, so a full block moves it as far as sixteen
; samples of the 1/64 one-pole would; x0 = the value in use, snapped onto
; the target when the step rounds to nothing (within about 72 LSB below it;
; from above the step is at least -1, so it walks down and snaps once it
; lands under). Uses a, b, x0, x1, y1.
; ---------------------------------------------------------------------------
lf_gset:
        move    x0,b                    ; in use
        move    y0,a
        sub     x0,a                    ; target - in use: up to +-2 (c is
        asr     a                       ;  signed), so halved, and K doubled
        move    a,x0
        move    #>$39052,y1             ; 2K
        mpy     x0,y1,a
        move    a,x1                    ; the step
        move    x1,a                    ; reloaded: Z needs all 56 bits clear
        tst     a
        bne     lf_gdone
        move    y0,b                    ; the step rounds to nothing: snap
lf_gdone:
        move    b,x0
        rts
