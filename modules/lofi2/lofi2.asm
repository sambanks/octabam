; ---------------------------------------------------------------------------
; LOFI2 -- one modulator, then sample-rate and bit reduction.
;
; STAGE 4 OF 4 -- COMPLETE. Ring mod OR stereo frequency shifter, then SRR
; and BRR, then a high-shelf cut. All three are our own code, measured
; against stock LO-FI where it has the same control. The chain is
;   dry -> modulator -> MIX -> SRR -> BRR -> LPF -> out,
; which is Bryan's stated order: the hold and the crush see the MODULATED
; signal, so the reduction aliases the ring output rather than the dry. MIX is
; the MODULATOR's depth and sits before the reduction pair, so SRR and BRR are
; live at MIX=0 -- see the MIX block below.
;
;   stage 1  spine + MIX                    done
;   stage 2  SRR + BRR                      done
;   stage 3  ring mod, RANGE and AMPH       done
;   stage 4  stereo frequency shifter, FDBK done
;
; All three MODE positions are implemented: 0 runs the ring block, 1 and 2 run
; the shifter with a per-block sign on Q. The two modulators are mutually
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
;   p10 AMPH  ring carrier L/R phase offset, BIPOLAR: -90..+90 deg, 0 at
;             the knob's centre (64); + puts R ahead, - puts L ahead. Knob
;             field of r6+$e
;
; ---- r7 slots -------------------------------------------------------------
;   the MODE duck:
;     $10 running mode (PERSISTENT: the mode actually playing)
;     $11 duck depth e, 0 = none .. $7fffff = wet fully out (PERSISTENT)
;     $12 ring GAIN / 4 (per block)   $13 duck step, signed (per block)
;     $14 m*(1-e), the MIX the crossfade uses (per sample)
;     $15 MODE as the knob has it (per block)
;   persistent (Character's slots for the same jobs, so the two read alike):
;     $19 held L      $1a held R      $1b srr phase      $1c carrier phase
;   per block:
;     $20 m = MIX     $21 range       $22 mode
;     $24 carrier step target   $25 ptable base   $26 amph offset  $27 ring flag
;     $16 SRR rate target (per block)   $17 SRR rate in use (PERSISTENT)
;     $28 BRR E target (per block)  $29 E in use (PERSISTENT)
;     $2a m, $2b 1/(2m), $18 n -- BRR's step, per sample
;     $1d LPF c target  $1e kd target (per block)
;     $23 carrier step in use, glided toward $24 (PERSISTENT)
;     $3f c in use  $1f kd in use -- glided per sample (PERSISTENT)
;     $01/$02 the shelf allpass's dropped bits, L/R (PERSISTENT)
;     $03 MIX  $04 GAIN/4  $05 fdbk  $06 amph offset -- in use, glided
;         toward $20 / $12 / $38 / $26 (PERSISTENT)
;     $2c sin  $2d cos  $2e I_L $2f Q_L $30 I_R $31 Q_R  $32 shift flag
;     $37 sign  $38 fdbk  $39/$3a aPrev L/R  $3b/$3c lastwet L/R
;     $3d/$3e chain inputs L/R
;   the four Hilbert chains, 16 words each -- ALL above $3f, so all in the
;   two-word long form, which is deliberate: they are the cold state and
;   the hot scalars keep the short encodings below:
;     $40 A-L   $50 B-L   $60 A-R   $70 B-R      (ends at $7f)
;   the LPF shelf's persistent state, two words per channel:
;     $80/$81 allpass ap[n-1] and x[n-1], L    $82/$83 the same, R
;   $84..$8a is host-owned for state ACROSS CALLS and per-call scratch there
;   is fine (CHIP.md, bisected; the blanket "$84+ hangs" was retracted
;   30 Aug 2026 and BusDelay ships using $84..$88).
;   Each section is y[n-2], y[n-1], x[n-2], x[n-1] IN THAT ORDER -- chosen so
;   r1's read walk and r2's write walk are both monotonic. Do not reorder.
;   per sample scratch:
;     $33 dry L       $34 dry R       $35 v L            $36 v R
; All below $40: a displacement past 63 assembles to the two-word long form.
; The four Hilbert chains are 16 words each, 64 in total, and go above that
; line for exactly that reason.
;
; ---- boot garbage --------------------------------------------------------
; Until the port to the October 2026 tree `init` was a bare `rts`, after
; WarpFold's note that r7 is not reliably set at init on hardware. Stock
; LO-FI's own init zeroes its block from r7, and so do this tree's modules
; under verify_dirtystate, so `init` now zeroes $00..$83. The tolerances
; below still hold and are kept:
;   * carrier phase: any value is a legal phase, and A1 extraction wraps it.
;   * held pair: at worst one wrong sample before the first latch.
;   * SRR phase: init zeroes it, and it stays in 0 .. 1.0 by construction.
;
; CYCLES_FORWARD_BRANCHES
; Every conditional branch in the sample loop jumps FORWARD and can only
; SKIP code, so the word span remains a ceiling: the two modulator gates
; (the SRR latch is branch-free, with Tccs). A backward one would be a loop the span counts
; once, which is the thing that declaration must never be used to hide.
;
; Every mpy is `mpy x0,y1` or `mpy y0,x0` -- the two operand orders dsp_asm
; is known to encode SIGNED. AND and ASL leave A2 STALE and a store would
; then saturate, so every value passing through one leaves via a1 into a
; clean register first.
; ---------------------------------------------------------------------------

init:
; ---- every slot to zero (verify_dirtystate; AGENTS.md "a persistent slot
; that init does not clear"). r5, never r1: the FX1 dispatcher keeps the
; effect id in r1 across this call (verify_initregs). $00..$83 is the whole
; block, so no per-slot census can go stale. The smoothed shelf coefficient
; at $3f starts at 0 and glides to its target over the first few hundred
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
        move    #>$400000,x0
        move    x0,x:(r7+$17)
        rts

proc:
; ---- per-block knob decode ------------------------------------------------
        move    x:(r6+$1),a             ; m = MIX, value<<16
        and     #>$7fff00,a             ; the knob AND its LFO fraction (bits 15-8)
        move    a1,x0
        move    x0,x:(r7+$20)

        move    x:(r6+$c),a             ; RANGE, slot 6, knob field
        and     #>$7f0000,a
        move    a1,x0
        move    x0,x:(r7+$21)

        move    x:(r6+$d),a             ; MODE, slot 8, knob field
        and     #>$7f0000,a
        move    a1,x0
        move    x0,x:(r7+$15)           ; MODE as the knob has it

; ---- the MODE duck --------------------------------------------------------
; A MODE change swaps one modulator for an unrelated one (or flips Q's sign),
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

; s: -1 for MODE 1 (DOWN), +1 for MODE 2 (UP). A per-block sign on Q, so
; the direction never costs a branch in the sample loop.
; Selector order is RING / DOWN / UP, so the encoder walks the sidebands in
; pitch order with RING at one end. Nothing else reads MODE's value: the ring
; flag tests it for zero and the shift flag for nonzero, so this compare is
; the only place the two shift positions are told apart.
        move    x:(r7+$22),a
        move    #>$20000,x0
        cmp     x0,a                    ; MODE 2?
        beq     lf_up
        move    #>$800000,x0            ; MODE 1 = DOWN
        bra     lf_sgn
lf_up:
        move    #>$7fffff,x0            ; MODE 2 = UP
lf_sgn:
        move    x0,x:(r7+$37)

; fdbk = FDBK * 0.45, BodeShift's cap. Inactive in RING by design: ring
; feedback is a harmonic-order generator, not a ladder, and was not wanted.
        move    x:(r6+$2),a
        and     #>$7fff00,a             ; the knob AND its LFO fraction
        move    a1,x0
        move    #>$39999a,y1
        mpy     x0,y1,a
        move    a,x:(r7+$38)

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
        move    #>$400000,a             ; 0.5
        mac     x0,y1,a                 ; h = 2^f / 2
        move    a,x0
        asr     #$1,a,a
        move    a,y0                    ; h/2
        move    x1,b
        tst     b                       ; N: n = 1
        move    y0,a
        tmi     x0,a
        move    a,x:(r7+$12)            ; GAIN/4

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
        move    #>$600000,b             ; kd = 3/4: the shelf in
        move    #>$0,x0
        move    y0,a
        sub     #>$7f,a
        teq     x0,b                    ; k = 127: out
        move    b,x:(r7+$1e)            ; kd target; $1f glides to it
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
        move    a,x:(r7+$1d)            ; c target; $3f glides to it

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
; floored at 1: 1 at 0, 5.50 at 64, 12.37 at 127. The September port held
; twice as long at every setting (11 at 64, 1,782 Hz at 127).
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
        move    x0,x:(r7+$24)           ; park the base step

; t = 0.75 * knob, so the six octaves land in bits 22..20 (integer) and the
; rest is the fraction. The knob word IS knob/128, so t = 6*knob/128 / 8.
; The knob's LFO fraction (bits 15-8) is KEPT: one knob step is 6/128 of an
; octave, 56 cents, so an LFO on FREQ needs the bits between the steps.
        move    x:(r6+$0),a
        and     #>$7fff00,a             ; the knob AND its fraction
        move    a1,x0
        move    #>$600000,y1            ; 0.75
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
        move    #>$160000,y1            ; 0.171875
        mpy     x0,y1,a
        add     #>$2a0000,a             ; + 0.328125
        move    a,y1
        move    x1,x0                   ; f
        mpy     x0,y1,a
        add     #>$400000,a             ; + 0.5
        move    a,y1                    ; h, in [0.5, 1.0)

; step = base * h, then shifted up (n+1) times: the +1 undoes h's halving.
        move    x:(r7+$24),x0
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$24)
        move    y0,b                    ; ⚠️ a `do` with a count of 0 runs
        tst     b                       ;  65536 times, so guard it exactly
        beq     lf_noct                 ;  as the mask loop above does
        move    x:(r7+$24),a
        do      y0,>lf_octl
        asl     #$1,a,a
        move    a1,x0
        move    x0,a
lf_octl:
        nop
        move    a,x:(r7+$24)
lf_noct:

; ---- AMPH -> the L/R carrier phase offset --------------------------------
; BIPOLAR (October 2026; 0..~357 degrees before): the phase word spans one
; cycle over 24 bits, so the knob word less $400000 (knob 64) is exactly
; -1/4..+1/4 cycle: -90..+88.6 degrees, 1.4 a step, 0 at the centre. Every
; distinct stereo motion of a ring mod lives inside +-90 (theta and
; 180-theta give the same envelope, lead and lag swapped); the sign says
; which channel leads. Wraps in A1 exactly as the phase itself does.
        move    x:(r6+$e),a
        and     #>$7fff00,a             ; the knob AND its LFO fraction
        sub     #>$400000,a
        move    a1,x0
        move    x0,x:(r7+$26)

; ---- sample loop ----------------------------------------------------------
        move    #>$1,n0
        move    #$40,n1                 ; the Hilbert chains' base offset
        do      n7,>lf_end

; park the dry pair, and default v (the modulated signal) to it
        move    x:(r0),x1
        move    x1,x:(r7+$33)
        move    x1,x:(r7+$35)
        move    x:(r0+n0),x1
        move    x1,x:(r7+$34)
        move    x1,x:(r7+$36)

; The continuous page-1 knobs glide to the block's values, 1/64 of the way a
; sample (about 1.5 ms, lf_glide), so a turned knob or an LFO sweeps instead
; of stepping at the block rate: FREQ's carrier step, MIX, GAIN, FDBK and
; AMPH's offset. Here, before the fork, because both modulators read them.
        move    x:(r7+$24),y0           ; carrier step target
        move    x:(r7+$23),x0           ; in use
        bsr     lf_glide
        move    b,x:(r7+$23)
        move    x:(r7+$20),y0           ; MIX
        move    x:(r7+$03),x0           ; in use
        bsr     lf_glide
        move    b,x:(r7+$03)
        move    x:(r7+$12),y0           ; GAIN/4
        move    x:(r7+$04),x0           ; in use
        bsr     lf_glide
        move    b,x:(r7+$04)
        move    x:(r7+$38),y0           ; fdbk
        move    x:(r7+$05),x0           ; in use
        bsr     lf_glide
        move    b,x:(r7+$05)
        move    x:(r7+$26),y0           ; amph offset
        move    x:(r7+$06),x0           ; in use
        bsr     lf_glide
        move    b,x:(r7+$06)

; MODEFORK_BEGIN -- cycle_count.py: RING and SHIFT are MUTUALLY EXCLUSIVE.
; Without these markers the tool sums both and prices a whole engine that
; can never run on the same sample. BEGIN..first MID is the dispatch.
        nop
; MODEFORK_MID -- alternative 1: RING
; ---- MODULATOR: ring mod, MODE 0 only ------------------------------------
; Forward branch, and it SKIPS work, so the word span is still the worst-case
; cycle count. In MODE 1/2 the carrier does not advance either -- there is no
; continuity to preserve when nothing reads it, and stage 4 gives the shifter
; its own oscillator.
        move    x:(r7+$27),a            ; ring flag
        tst     a
        beq     lf_nomod

; carrier: WarpFold's parabolic sine 4*p*(1-|p|) on a phase wrapped by A1
; extraction -- continuous at the wrap, exact +/-1 peaks.
        move    x:(r7+$23),y0           ; step, glided
        move    x:(r7+$1c),a            ; phase
        add     y0,a
        move    a1,x0                   ; p, wrapped
        move    x0,x:(r7+$1c)
        move    x0,a                    ; clean
        abs     a
        move    #>$800000,y1            ; -1.0
        add     y1,a                    ; |p| - 1
        neg     a                       ; t = 1 - |p|
        move    a,y1
        mpy     x0,y1,a                 ; p*t
        asl     #$2,a,a                 ; carrier L = 4*p*t
        move    a,y1
        move    x:(r7+$33),x0           ; dry L
        mpy     x0,y1,a
        move    a,x0
        move    x:(r7+$04),y1           ; GAIN/4, glided
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
        move    #>$800000,y1
        add     y1,a
        neg     a
        move    a,y1
        mpy     x0,y1,a
        asl     #$2,a,a                 ; carrier R
        move    a,y1
        move    x:(r7+$34),x0           ; dry R
        mpy     x0,y1,a
        move    a,x0
        move    x:(r7+$04),y1           ; GAIN/4, glided
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x:(r7+$36)            ; v R
lf_nomod:


; MODEFORK_MID -- alternative 2: SHIFT (the expensive one: 16 allpass
; sections and two calls into lf_sin, against the ring's single carrier)
; ---- MODULATOR: frequency shifter, MODE 1 (UP) and 2 (DOWN) --------------
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

; in = 0.5*dry + fdbk*lastwet, per channel. The halving is what keeps the
; feedback loop inside the rail: |in| settles at 0.5/(1-fdbk), so fdbk < 0.5
; is an ARITHMETIC cap, not a taste one. The x2 at the output undoes it.
        move    x:(r7+$33),a            ; dry L
        asr     #$1,a,a
        move    x:(r7+$3b),x0           ; lastwet L
        move    x:(r7+$05),y1           ; fdbk, glided
        mac     x0,y1,a
        move    a,x:(r7+$3d)
        move    x:(r7+$34),a            ; dry R
        asr     #$1,a,a
        move    x:(r7+$3c),x0           ; lastwet R
        move    x:(r7+$05),y1
        mac     x0,y1,a
        move    a,x:(r7+$3e)

; ---- the oscillator, ONCE for both channels ------------------------------
        move    x:(r7+$23),y0           ; step, glided
        move    x:(r7+$1c),a            ; phase (shared with the ring mod --
        add     y0,a                    ;  the two modes are exclusive)
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$1c)
        bsr     lf_sin
        move    a,x:(r7+$2c)            ; sin
        move    x:(r7+$1c),a
        move    #>$400000,x0
        add     x0,a                    ; + a quarter turn
        move    a1,x0
        move    x0,a
        bsr     lf_sin
        move    a,x:(r7+$2d)            ; cos

; ---- the four Hilbert chains ---------------------------------------------
; POINTER-WALKED, not displacement-addressed. Each section is 12 words where
; BodeShift's is 21, and the difference is PARALLEL MOVES: an ALU op can
; carry a memory move in the same word, but only with (rn) addressing --
; never with r7+displacement. That is the whole reason BodeShift's sections
; cost what they do.
;
; The state is laid out y[n-2], y[n-1], x[n-2], x[n-1] so that BOTH the read
; walk and the write walk are monotonic: r1 reads ascending, r2 writes
; ascending one step behind, and no value is overwritten before its last
; use. The old order could not do this -- y[n-1] had to be written before
; x[n-2] was read.
;
; ONE setup pair covers all four chains: they sit at $40/$50/$60/$70
; contiguously and run in that order, so the pointers walk $40 to $7f once
; per sample and land exactly at the end. ⚠️ Anything inserted between the
; chains must therefore leave r1 and r2 alone.
; $40 is past lua's -64..63 displacement: `lua (r7+$40)` assembled to
; r7-$40, so until the port to this tree all four chains walked the 64
; words BELOW this instance's block (AGENTS.md). n1 = $40, set before the loop.
        move    r7,r1
        move    (r1)+n1
        move    r1,r2

        move    x:(r7+$3d),x1          ; chain A-L input
; ---- chain A-L section 0: allpass, c = 0.6923877778065 ----
        move    #>$58a02a,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
; ---- chain A-L section 1: allpass, c = 0.9360654322959 ----
        move    #>$77d0fe,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
; ---- chain A-L section 2: allpass, c = 0.9882295226860 ----
        move    #>$7e7e4e,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
; ---- chain A-L section 3: allpass, c = 0.9987488452737 ----
        move    #>$7fd701,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
; I is chain A's output delayed one sample
        move    x:(r7+$39),b            ; I_L = aPrev L
        move    x1,x:(r7+$39)
        move    b,x:(r7+$2e)
        move    x:(r7+$3d),x1          ; chain B-L input
; ---- chain B-L section 0: allpass, c = 0.4021921162426 ----
        move    #>$337b08,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
; ---- chain B-L section 1: allpass, c = 0.8561710882420 ----
        move    #>$6d9704,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
; ---- chain B-L section 2: allpass, c = 0.9722909545651 ----
        move    #>$7c7408,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
; ---- chain B-L section 3: allpass, c = 0.9952884791278 ----
        move    #>$7f659d,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
        move    x1,x:(r7+$2f)           ; Q_L

        move    x:(r7+$3e),x1          ; chain A-R input
; ---- chain A-R section 0: allpass, c = 0.6923877778065 ----
        move    #>$58a02a,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
; ---- chain A-R section 1: allpass, c = 0.9360654322959 ----
        move    #>$77d0fe,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
; ---- chain A-R section 2: allpass, c = 0.9882295226860 ----
        move    #>$7e7e4e,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
; ---- chain A-R section 3: allpass, c = 0.9987488452737 ----
        move    #>$7fd701,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
        move    x:(r7+$3a),b            ; I_R = aPrev R
        move    x1,x:(r7+$3a)
        move    b,x:(r7+$30)
        move    x:(r7+$3e),x1          ; chain B-R input
; ---- chain B-R section 0: allpass, c = 0.4021921162426 ----
        move    #>$337b08,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
; ---- chain B-R section 1: allpass, c = 0.8561710882420 ----
        move    #>$6d9704,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
; ---- chain B-R section 2: allpass, c = 0.9722909545651 ----
        move    #>$7c7408,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
; ---- chain B-R section 3: allpass, c = 0.9952884791278 ----
        move    #>$7f659d,y1
        move    x1,x0
        mpy     x0,y1,a   x:(r1)+,x0    ; a = c*in       ; x0 = y[n-2]
        mac     x0,y1,a   x:(r1)+,x0    ; += c*y[n-2]    ; x0 = y[n-1]
        move    x0,x:(r2)+              ; y[n-2] <- y[n-1]
        move    x:(r1)+,x0              ; x0 = x[n-2]
        sub     x0,a      x:(r1)+,x0    ; a = y[n]       ; x0 = x[n-1]
        move    a,x:(r2)+               ; y[n-1] <- y[n]
        move    x0,x:(r2)+              ; x[n-2] <- x[n-1]
        move    x1,x:(r2)+              ; x[n-1] <- in
        move    a,x1
        move    x1,x:(r7+$31)           ; Q_R

; ---- the sidebands: wet = 2*(I*cos + s*(Q*sin)) --------------------------
; s is a per-block SIGN, +1 for UP and -1 for DOWN, so the direction costs
; no branch in the loop. Both channels share it: WIDE, which is where the
; two signs would differ, was dropped by design.
        move    x:(r7+$2e),x0           ; I_L
        move    x:(r7+$2d),y1           ; cos
        mpy     x0,y1,a
        move    a,x:(r7+$35)            ; park I*cos
        move    x:(r7+$2f),x0           ; Q_L
        move    x:(r7+$2c),y1           ; sin
        mpy     x0,y1,a
        move    a,x0
        move    x:(r7+$37),y1           ; s
        mpy     x0,y1,a
        move    x:(r7+$35),b
        add     b,a
        asl     #$1,a,a                 ; the x2 undoing the input halving
        move    a,x:(r7+$3b)            ; lastwet L, the feedback tap
        move    a,x:(r7+$35)            ; v L

        move    x:(r7+$30),x0           ; I_R
        move    x:(r7+$2d),y1
        mpy     x0,y1,a
        move    a,x:(r7+$36)
        move    x:(r7+$31),x0           ; Q_R
        move    x:(r7+$2c),y1
        mpy     x0,y1,a
        move    a,x0
        move    x:(r7+$37),y1
        mpy     x0,y1,a
        move    x:(r7+$36),b
        add     b,a
        asl     #$1,a,a
        move    a,x:(r7+$3c)            ; lastwet R
        move    a,x:(r7+$36)            ; v R
lf_noshift:
; MODEFORK_END

; ---- LPF: glide c and kd toward their targets, once per sample ----------
; 1/64 of the way a sample (about 1.5 ms), snapping to the target when the
; step rounds to nothing, so kd lands on exactly 0 at LPF 127. The step is
; reloaded through a register before the test (AGENTS.md: asr leaves a
; remainder in a0, and Z needs all 56 bits clear). HERE, after MODEFORK_END,
; so it runs in every mode; a, b, x0, x1 and y0 are all free at this point.
        move    x:(r7+$1d),y0           ; c target
        move    x:(r7+$3f),x0           ; c in use
        bsr     lf_glide
        move    b,x:(r7+$3f)
        move    x:(r7+$1e),y0           ; kd target
        move    x:(r7+$1f),x0           ; kd in use
        bsr     lf_glide
        move    b,x:(r7+$1f)

; ---- the MODE duck, per sample: e moves one step toward its target -------
; Floored at 0 by tmi, capped near 1 by the store's limiter.
        move    x:(r7+$11),a            ; e
        move    x:(r7+$13),x0           ; the step, signed
        add     x0,a
        move    #>$0,x0
        tmi     x0,a
        move    a,x:(r7+$11)
        move    x:(r7+$11),x0           ; e as stored
        move    x:(r7+$03),y1           ; m, glided
        mpy     x0,y1,b                 ; m*e
        move    x:(r7+$03),a
        sub     b,a                     ; m*(1-e): exactly m at e = 0
        move    a,x:(r7+$14)

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
        move    x:(r7+$14),y1           ; m*(1-e)
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$35)

        move    x:(r7+$36),a            ; v R
        move    x:(r7+$34),b            ; dry R
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$14),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$36)

; ---- SRR: glide the rate, advance the phase, latch the MODULATED pair ---
; The rate moves 1/64 of the way to its target every sample (a ~1.5 ms
; time constant), so a turned knob never steps at the block rate.
        move    x:(r7+$16),y0           ; target
        move    x:(r7+$17),x0           ; the rate in use
        bsr     lf_glide
        move    b,x:(r7+$17)
        move    x:(r7+$17),x0           ; inc
        move    x:(r7+$1b),b            ; phase, 0 .. < $400000
        add     x0,b                    ; phase + inc
        move    #>$400000,x1
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
        move    x:(r7+$28),y0           ; target
        move    x:(r7+$29),x0           ; E in use
        bsr     lf_glide
        move    b,x:(r7+$29)
; n = whole bits (a variable shift), j = the fraction to 1/128 bit
        move    b,a
        asr     #$11,a,a
        move    a1,x:(r7+$18)           ; n
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

; ---- L: quantise the held sample and write it out ------------------------
; out = dry + m*(wet - dry). The halve/double straddle keeps the difference
; inside the accumulator when wet and dry have opposite signs.
        move    x:(r7+$19),x0           ; held L
        move    x:(r7+$2a),y1           ; m
        mpy     x0,y1,a                 ; x * 2^-frac
        move    x:(r7+$18),y0           ; n
        asr     y0,a,a                  ; * 2^-n
        rnd     a                       ; to the nearest step
        asl     y0,a,a
        move    a,x0
        move    x:(r7+$2b),y1           ; 1/(2m)
        mpy     x0,y1,b
        asl     #$1,b,b                 ; back by 2^frac: exactly unity gain
        move    x:(r7+$19),x1           ; E = 0: the held sample, untouched
        move    x:(r7+$29),a
        tst     a
        teq     x1,b

; ---- L: the shelf, LAST in the chain -------------------------------------
;   ap[n] = c*ap[n-1] + x[n-1] - c*x[n]      a first-order allpass
;   y     = x - kd*(x - ap)/2                 = (5/8)x + (3/8)ap at kd = 3/4
; At DC ap = x (y = x); at Nyquist ap = -x (y = x/4). kd = 0 is y = x exactly.
; The allpass keeps the bits its store drops (a0) and adds them back the
; next sample: first-order error feedback, so the rounding error is
; high-passed and cannot pile up into a dead band when c is near 1 (the
; ported shelf lost an impulse's low-frequency tail to it).
        move    b,x1                    ; x[n], the BRR output (limited)
        clr     a
        move    x:(r7+$01),a0           ; last sample's dropped bits
        move    x:(r7+$3f),y1           ; c, smoothed
        move    x1,x0
        mac     -x0,y1,a                ; - c*x[n]
        move    x:(r7+$81),x0           ; x[n-1]
        add     x0,a
        move    x:(r7+$80),x0           ; ap[n-1]
        mac     x0,y1,a                 ; ap[n], 48 bits
        move    a0,x:(r7+$01)
        move    x1,x:(r7+$81)           ; x[n-1] <- x[n]
        move    a,x:(r7+$80)            ; ap[n-1] <- ap[n] (limited)
        move    a,x0
        move    x1,a
        sub     x0,a                    ; x - ap
        asr     a                       ; /2
        move    a,x0
        move    x:(r7+$1f),y1           ; kd, smoothed
        move    x1,a
        mac     -x0,y1,a
        move    a,x:(r0)

; ---- R: the same ---------------------------------------------------------
        move    x:(r7+$1a),x0           ; held R
        move    x:(r7+$2a),y1
        mpy     x0,y1,a
        move    x:(r7+$18),y0
        asr     y0,a,a
        rnd     a
        asl     y0,a,a
        move    a,x0
        move    x:(r7+$2b),y1
        mpy     x0,y1,b
        asl     #$1,b,b
        move    x:(r7+$1a),x1
        move    x:(r7+$29),a
        tst     a
        teq     x1,b

; ---- R: the same shelf, its own state ----------------------------------
        move    b,x1
        clr     a
        move    x:(r7+$02),a0
        move    x:(r7+$3f),y1
        move    x1,x0
        mac     -x0,y1,a
        move    x:(r7+$83),x0
        add     x0,a
        move    x:(r7+$82),x0
        mac     x0,y1,a
        move    a0,x:(r7+$02)
        move    x1,x:(r7+$83)
        move    a,x:(r7+$82)
        move    a,x0
        move    x1,a
        sub     x0,a
        asr     a
        move    a,x0
        move    x:(r7+$1f),y1
        move    x1,a
        mac     -x0,y1,a
        move    a,x:(r0+n0)

        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
lf_end:
        nop
        rts

; ---------------------------------------------------------------------------
; lf_sin -- sin(pi*p) for p in [-1,1), from BodeShift, which took it from
; WarpFold's carrier: the parabola 4p(1-|p|) refined by the standard
; 0.775/0.225 correction. Argument and result both in A.
; ---------------------------------------------------------------------------
; ---------------------------------------------------------------------------
; lf_glide: one step of every glide in the loop. In: y0 = target, x0 = the
; value in use. Out: b = in use + (target - in use)/64, or exactly the
; target when that step rounds to nothing (so a glide lands on 0, unity or
; a bypass exactly). The step is reloaded through x1 before the test:
; `asr` leaves a remainder in a0, and Z needs all 56 bits clear (AGENTS.md).
; Uses a, b, x1.
; ---------------------------------------------------------------------------
lf_glide:
        move    y0,a
        sub     x0,a
        asr     #$6,a,a
        move    a,x1
        move    x0,b
        add     x1,b
        move    x1,a
        tst     a
        teq     y0,b
        rts

; ---------------------------------------------------------------------------
lf_sin:
        move    a,x1
        abs     a
        move    #>$800000,x0
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
        rts

; ---------------------------------------------------------------------------
; RESOLVED: SHIFT gets its OWN pair of bases, not RING's. Opened 5 Sep 2026 --
; 60 Hz-4 kHz is well past where a shifter stays musical, BodeShift stopped at
; 1,000 Hz on purpose -- and settled by following the Bode 1630's own
; exponential scale of 2 Hz-2 kHz: LOW keeps the 2 Hz floor, HIGH starts at
; 31.25 Hz so six octaves lands on exactly 2,000 Hz. Both base constants are
; selected in the FREQ block above off the shift flag at r7+$32.
;
; STILL AN EAR DECISION, deferred: whether six exponential octaves feels right
; under the knob in either mode, and whether the SHIFT pair wants moving again
; once it has had real playing time.
; ---------------------------------------------------------------------------
