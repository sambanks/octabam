; ---------------------------------------------------------------------------
; Streamz -- a Mutable-Instruments-Streams-flavoured lowpass gate.
;
; The insert contract, with no buffer at all: frames in place from r0, knobs
; from r6, state in this instance's own r7 block. Stacks with every other
; zero-footprint insert.
;
; ---- what it does ---------------------------------------------------------
; A peak follower watches the mono sum. Its envelope then opens a filter and
; an amplifier TOGETHER -- the vactrol coupling that makes a lowpass gate
; sound unlike a VCA: quiet is dark AND quiet, loud is bright AND loud.
;
;   env  = max(|x| * SENS, env * fall)      fast attack, knob-set release
;   c    = COLR + (1-COLR) * env            filter opening, 0..1
;   y    = two cascaded one-poles at c      12 dB/oct, no resonance
;   out  = y * env                          (LPG; VCF skips this, VCA skips
;                                            the filter)
;
; Two cascaded one-poles rather than an SVF: a lowpass gate wants a gentle,
; unresonant slope, and this costs 6 instructions a pole with no stability
; question at any coefficient the knobs can reach.
;
; ⚠️ ATTACK IS FIXED AND FAST, deliberately. `max` against the rectified
; input IS the attack, so it is instantaneous, and the release is the only
; time constant on a knob. An LPG whose attack you can slow down stops
; sounding like one -- it becomes a swell pedal.
;
; ---- knobs ----------------------------------------------------------------
;   p0 SENS  follower drive; gain = SENS/64, so 64 is unity (a full-scale
;            peak opens the gate fully) and 127 is ~2x for quiet material
;   p1 FALL  release, T60 20 ms .. 700 ms on a cubic-in-rate taper.
;            Short is plucky; long is a slow vactrol.
;   p2 COLR  how open the filter is when the gate is SHUT, 0 .. ~0.35.
;            0 is a true gate (shut is silent and black)
;   p3 MIX   out = dry + MIX*(wet - dry); MIX=0 is an exact passthrough
;   p7 MODE  0 LPG (filter+amp), 1 VCF (filter only), 2 VCA (amp only)
;
; ---- r7 slots -------------------------------------------------------------
;   $20 m (MIX)      $21 sens        $22 fall        $23 colr
;   $24 env          (PERSISTENT; bounded by construction -- it is a max of
;                     two things that are each <= full scale, and it decays)
;   $25 c            (per sample, the shared filter coefficient)
;   $26/$27 pole 1/2 state L   $28/$29 pole 1/2 state R   (PERSISTENT)
;
; Every mpy is `mpy x0,y1` (the known-signed encoding), and every value fed
; to one is non-negative except the audio itself, which is the FIRST operand
; throughout. Audited by disassembly.
; ---------------------------------------------------------------------------

init:
        rts

proc:
; ---- per-block knob decode ------------------------------------------------
        move    x:(r6+$3),x0            ; m = MIX
        move    x0,x:(r7+$20)
; sens: the knob STRAIGHT THROUGH (0..0.992), doubled later in the
; accumulator where there are guard bits.
; ⚠️ NOT `asl #$1` here: 127<<16 doubled is 0xfe0000, which exceeds the
; 24-bit signed range, so the STORE's limiter would clamp it to 1.0 and
; every SENS above 64 would behave identically. Legal, silent, and half the
; knob dead -- the store-limiter family from CLAUDE.md, in its quietest form.
        move    x:(r6+$0),x0
        move    x0,x:(r7+$21)
; fall: a release COEFFICIENT is hyperbolic in decay time (T60 ~ 6.9/(1-r)),
; so spending the knob linearly on r crams every useful value into the last
; few steps -- Rungs' DAMP has exactly that flaw, noted there as a voicing
; item. Here the knob is spent on the decay RATE with a cubic taper:
;   d = d1 + (d0-d1)*(1-knob)^3,  r = 1 - d
; which gives T60 20 / 46 / 134 / 458 / 700 ms at FALL 0 / 32 / 64 / 96 /
; 127 -- fine control where a lowpass gate lives and a real 700 ms at the
; top. Two multiplies for the cube.
        move    x:(r6+$1),a
        neg     a
        add     #>$7fffff,a             ; u = 1 - knob
        move    a,x0
        move    a,y1
        mpy     x0,y1,a                 ; u^2
        move    a,x0
        move    x:(r6+$1),a
        neg     a
        add     #>$7fffff,a
        move    a,y1                    ; u again
        mpy     x0,y1,a                 ; u^3
        move    a,x0
        move    #>$f84e,y1              ; d0 - d1
        mpy     x0,y1,a
        add     #>$755,a                ; + d1  = the decay rate
        neg     a
        add     #>$7fffff,a             ; r = 1 - d
        move    a,x:(r7+$22)
; colr = COLR * 0.35  (the filter's floor when the gate is shut)
        move    x:(r6+$2),x0
        move    #>$2ccccd,y1
        mpy     x0,y1,a
        move    a,x:(r7+$23)

; ---- MODE: page-2 slot 7 companion (BusVerb's decode) --------------------
        move    x:(r6+$c),a
        and     #>$ff00,a
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        move    #>$10000,x0
        cmp     x0,a
        beq     sz_vcf
        move    #>$20000,x0
        cmp     x0,a
        beq     sz_vca
                                        ; 0, and anything unexpected: LPG

; ===========================================================================
; MODE 0 -- LPG: the envelope opens the filter AND the amplifier.
; ===========================================================================
        move    #>$1,n0
        do      n7,>sz_endlpg
        bsr     sz_env                  ; env -> x:(r7+$24), c -> x:(r7+$25)
; ---- L: two poles, then the VCA -------------------------------------------
        move    x:(r0),x0
        bsr     sz_polel                ; filtered L in a
        move    a,x0
        move    x:(r7+$24),y1           ; env
        mpy     x0,y1,a                 ; the coupled amplifier
        bsr     sz_mixl
; ---- R --------------------------------------------------------------------
        move    x:(r0+n0),x0
        bsr     sz_poler
        move    a,x0
        move    x:(r7+$24),y1
        mpy     x0,y1,a
        bsr     sz_mixr
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
sz_endlpg:
        nop
        rts

; ===========================================================================
; MODE 1 -- VCF: the filter follows the envelope, the level is untouched.
; An envelope filter rather than a gate.
; ===========================================================================
sz_vcf:
        move    #>$1,n0
        do      n7,>sz_endvcf
        bsr     sz_env
        move    x:(r0),x0
        bsr     sz_polel
        bsr     sz_mixl
        move    x:(r0+n0),x0
        bsr     sz_poler
        bsr     sz_mixr
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
sz_endvcf:
        nop
        rts

; ===========================================================================
; MODE 2 -- VCA: the envelope drives the amplifier only. A dynamics gate,
; and the control for hearing what the filter coupling actually adds.
; ===========================================================================
sz_vca:
        move    #>$1,n0
        do      n7,>sz_endvca
        bsr     sz_env
        move    x:(r0),x0
        move    x:(r7+$24),y1
        mpy     x0,y1,a
        bsr     sz_mixl
        move    x:(r0+n0),x0
        move    x:(r7+$24),y1
        mpy     x0,y1,a
        bsr     sz_mixr
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
sz_endvca:
        nop
        rts

; ---------------------------------------------------------------------------
; sz_env -- advance the follower and derive this sample's filter coefficient.
;
; env = max(|mono| * sens, env * fall);  c = colr + (1-colr)*env
;
; The max is a cmp and ONE Tcc with nothing between them (the flag-clobber
; trap: `clr`, `and`, `abs` and every arithmetic op set the condition codes,
; and a Tcc that reads a stale flag is the GRAIN 5d noise wash). Tcc takes a
; REGISTER source, never an accumulator, so the candidate travels via x1.
; ---------------------------------------------------------------------------
sz_env:
        move    x:(r0),a                ; mono sum of this frame
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        abs     a                       ; |x|, and A2 stays consistent
        move    a,x0
        move    x:(r7+$21),y1           ; sens
        mpy     x0,y1,a                 ; the attack candidate
        asl     #$1,a,a                 ; x2 HERE, in the accumulator's guard
                                        ; bits, so SENS 64 is unity and 127 is
                                        ; ~2x -- see the decode's note on why
                                        ; this cannot be done at the store
        move    #>$7fffff,x0            ; and clamp: env > 1 would make the
        cmp     x0,a                    ; filter coefficient exceed 1 and the
        tgt     x0,a                    ; pole unstable
        move    a,x1                    ; -- into a REGISTER for the Tcc
        move    x:(r7+$24),x0           ; env
        move    x:(r7+$22),y1           ; fall
        mpy     x0,y1,a                 ; the release path
        cmp     x1,a                    ; nothing between this and the Tcc
        tlt     x1,a                    ; env = max(attack, release)
        move    a,x:(r7+$24)
; c = colr + (1-colr)*env  ==  colr + env - colr*env
        move    a,x0
        move    x:(r7+$23),y1           ; colr
        mpy     x0,y1,a                 ; colr*env
        neg     a
        move    x:(r7+$24),x0
        add     x0,a                    ; env - colr*env
        move    x:(r7+$23),x0
        add     x0,a                    ; + colr
        move    a,x:(r7+$25)
        rts

; ---------------------------------------------------------------------------
; sz_polel / sz_poler -- two cascaded one-poles at this sample's coefficient.
; In:  x0 = the sample.   Out: a = filtered.
; Each pole is y += c*(x-y); the difference spans (-2,2), so it is halved
; before the multiply and doubled after -- the same headroom idiom the other
; inserts use.
; ---------------------------------------------------------------------------
sz_polel:
        move    x:(r7+$26),b            ; pole 1 state
        move    x0,a
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$25),y1           ; c
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$26)
        move    x:(r7+$27),b            ; pole 2 state
        move    a,x0
        move    x0,a
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$25),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$27)
        rts
sz_poler:
        move    x:(r7+$28),b
        move    x0,a
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$25),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$28)
        move    x:(r7+$29),b
        move    a,x0
        move    x0,a
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$25),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$29)
        rts

; ---------------------------------------------------------------------------
; sz_mixl / sz_mixr -- out = dry + m*(wet - dry), written back in place.
; In: a = wet.
; ---------------------------------------------------------------------------
sz_mixl:
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        rts
sz_mixr:
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        rts
