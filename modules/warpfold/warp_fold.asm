; ---------------------------------------------------------------------------
; WarpFold -- a Mutable-Instruments-Warps-flavoured ring mod / wavefolder.
;
; A per-track INSERT, not a bus effect: it reads this track's stereo frames
; from x:(r0)/x:(r0+n0) and writes the processed frames back in place, the
; way the stock FX2 inserts do and the way BusVerb writes its dry+wet. It
; touches no bus scratch, no shared window and no absolute Y at all -- every
; word of state lives in this instance's own r7 block, which is per instance
; by construction (X:0x20a allocator, DSP.md section 10), so eight tracks can
; each run their own WarpFold.
;
; ---- knobs (page 1 val<<16; MODE is the page-2 slot-7 companion) ----------
;   p0 DRV   x:(r6+$0)  fold drive. gain = 1 + 7*DRV/128 (1x..7.9x). DRV=0
;            leaves the folder an identity to within 1 LSB -- the reflection
;            is never reached, so the only error is the wrap extraction's
;            truncation. The render harness nulls this against the input.
;   p1 FREQ  x:(r6+$1)  ring carrier, ~5 Hz..2.95 kHz on a squared taper:
;            step = FREQ^2 * 0.136 + 2^-12, carrier freq = SR*step/2.
;   p2 TONE  x:(r6+$2)  one-pole lowpass on the wet, c = 0.0078 + TONE*0.969.
;            127 is near-transparent (c ~ 0.98); it tames fold hash, it is
;            not meant to be a filter.
;   p3 MIX   x:(r6+$3)  dry/wet: out = dry + MIX*(wet - dry). MIX=0 is an
;            EXACT passthrough (the dry word is stored back untouched by
;            arithmetic that adds exactly zero).
;   p7 MODE  x:(r6+$c) bits 8-15 (BusVerb's exact decode): 0 FOLD, 1 RING,
;            2 BOTH (fold, then ring the folded signal). Anything unexpected
;            runs FOLD.
;
; ---- r7 slots (this instance's own block; nothing else runs on it) --------
;   r7+$20  carrier phase, 24-bit wrap (PERSISTENT; a garbage boot value is
;           a legal phase, and it never becomes an address, so no mask is
;           needed -- the two-track-freeze discipline is about AGU words)
;   r7+$21  TONE lowpass state L (PERSISTENT; bounded (-1,1) by construction
;           after the first block, boot garbage decays through the filter)
;   r7+$22  TONE lowpass state R (PERSISTENT, same)
;   r7+$23  gq   = gain/8, Q23        (per block, from DRV)
;   r7+$24  step = carrier phase inc  (per block, from FREQ)
;   r7+$25  c    = TONE coefficient   (per block)
;   r7+$26  m    = MIX, Q23           (per block)
;
; ---- arithmetic notes (the traps this file is written around) -------------
; * EVERY mpy is `mpy x0,y1` or `mpy y0,x0` -- the only two operand orders
;   dsp_asm is known to encode SIGNED (CLAUDE.md: anything it does not know
;   becomes mpysu, silently, and both operands here go negative). Audited by
;   disassembly, not by reading this source.
; * The fold is the wrap-and-reflect identity fold(v) = 2*|wrap((v+1)/2)|-1,
;   with wrap done by extracting A1 -- a plain register move, so no logical
;   op ever touches an accumulator whose extension byte then goes stale.
;   The one `and` in the file (the MODE field mask) is followed by BusVerb's
;   exact A1-clean dance before the value is compared.
; * 2|s|-1 is computed as (|s| - 0.5) << 1 so no intermediate needs +1.0,
;   which Q23 cannot represent.
; * mpy here is the emulator's PLAIN product (no <<1), confirmed on silicon
;   within 13% by the decay-vs-TIME capture (docs/CAPTURE.md).
; ---------------------------------------------------------------------------

init:
; Nothing to seed: r7 is NOT reliably set at init on hardware (the rotation
; seeding note in modules/send/send_client.asm), and every persistent word
; above is harmless as boot garbage.
        rts

proc:
; ---- per-block: decode the four knobs into r7 scratch ---------------------
; gq = 0.125 + DRV*0.875  (gain/8, so the fold stage's mpy cannot overflow)
        move    x:(r6+$0),x0            ; DRV, val<<16, positive
        move    #>$700000,y1            ; 0.875
        mpy     x0,y1,a
        add     #>$100000,a             ; + 0.125
        move    a,x:(r7+$23)

; step = FREQ^2 * 0.136 + 2^-12  (squared taper, ~5 Hz floor)
        move    x:(r6+$1),x0
        move    x:(r6+$1),y1
        mpy     x0,y1,a                 ; FREQ^2
        move    a,x0
        move    #>$116a00,y1            ; 0.136 -> ~2.95 kHz at full knob
        mpy     x0,y1,a
        add     #>$800,a                ; floor: never a frozen carrier
        move    a,x:(r7+$24)

; c = 0.0078 + TONE*0.969  (one-pole coefficient; 0 would freeze the wet)
        move    x:(r6+$2),x0
        move    #>$7c0000,y1            ; 0.969
        mpy     x0,y1,a
        add     #>$10000,a              ; + 0.0078
        move    a,x:(r7+$25)

; m = MIX, straight through
        move    x:(r6+$3),x0
        move    x0,x:(r7+$26)

; ---- MODE: page-2 slot 7 companion, bits 8-15 -- BusVerb's exact decode --
        move    x:(r6+$c),a
        and     #>$ff00,a               ; slot 7's field, NOT the knob field
        move    a1,x0                   ; AND cleans A1 only
        move    x0,a
        asl     #$8,a,a                 ; -> 0..2, MSB-ALIGNED ($010000 per
                                        ; step) to match the compares below
        move    #>$10000,x0
        cmp     x0,a
        beq     wf_doring
        move    #>$20000,x0
        cmp     x0,a
        beq     wf_doboth
                                        ; 0, and anything unexpected: FOLD

; ===========================================================================
; MODE 0 -- FOLD: wet = fold(dry * gain), tone, mix. No carrier.
; ===========================================================================
        move    #>$1,n0
        do      n7,>wf_endf
        move    x:(r0),x0               ; dry L
        move    x:(r7+$23),y1           ; gq
        mpy     x0,y1,a                 ; v/8       (signed encoding)
        asl     #$2,a,a                 ; v/2
        move    #>$400000,x1
        add     x1,a                    ; (v+1)/2, |.| <= 4.5 -- guard bits
        move    a1,x1                   ; s = wrap((v+1)/2), raw A1, no limiter
        move    x1,a                    ; clean re-load: A2 consistent again
        abs     a                       ; |s| in [0,1)
        move    #>$400000,b
        sub     b,a                     ; |s| - 0.5
        asl     #$1,a,a                 ; fold in [-1,1)
; tone L: y' = y + c*(x - y), the difference halved through the multiply
        move    x:(r7+$21),b            ; lp state L
        sub     b,a                     ; x - y, range (-2,2) -- stays in acc
        asr     #$1,a,a
        move    a,x0                    ; (x-y)/2, within +/-1
        move    x:(r7+$25),y1           ; c
        mpy     x0,y1,a
        asl     #$1,a,a                 ; c*(x-y)
        add     b,a                     ; y'
        move    a,x:(r7+$21)
; mix L: out = dry + m*(wet - dry)
        move    x:(r0),b                ; dry L, still in place
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$26),y1           ; m
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)                ; L in place
; R channel, identical, lp state $22
        move    x:(r0+n0),x0
        move    x:(r7+$23),y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    #>$400000,x1
        add     x1,a
        move    a1,x1
        move    x1,a
        abs     a
        move    #>$400000,b
        sub     b,a
        asl     #$1,a,a
        move    x:(r7+$22),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$25),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$22)
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$26),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0                 ; next stereo frame
        move    #>$1,n0
wf_endf:
        nop
        rts

; ===========================================================================
; MODE 1 -- RING: wet = dry * carrier, tone, mix. No fold.
; carrier: triangle phase wrapped in A1, shaped to a parabolic sine
;          4*p*(1-|p|) -- continuous at the wrap, exact +/-1 peaks (the
;          store's limiter turns the exact 1.0 into $7fffff, one LSB shy).
; ===========================================================================
wf_doring:
        move    #>$1,n0
        do      n7,>wf_endr
        move    x:(r7+$24),y0           ; step
        move    x:(r7+$20),a            ; phase
        add     y0,a
        move    a1,x0                   ; p = wrapped phase
        move    x0,x:(r7+$20)
        move    x0,a                    ; clean
        abs     a
        move    #>$800000,y1            ; -1.0
        add     y1,a                    ; |p| - 1, in [-1,0)
        neg     a                       ; t = 1 - |p|, in (0,1]
        move    a,y1                    ; (limiter: 1.0 -> $7fffff)
        mpy     x0,y1,a                 ; p*t      (signed encoding)
        asl     #$2,a,a                 ; carrier = 4*p*t
        move    a,y0                    ; carrier, held for both channels
; L
        move    x:(r0),x0
        mpy     y0,x0,a                 ; dry * carrier  (signed encoding)
        move    x:(r7+$21),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$25),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$21)
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$26),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
; R
        move    x:(r0+n0),x0
        mpy     y0,x0,a
        move    x:(r7+$22),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$25),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$22)
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$26),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
wf_endr:
        nop
        rts

; ===========================================================================
; MODE 2 -- BOTH: wet = fold(dry * gain) * carrier, tone, mix.
; ===========================================================================
wf_doboth:
        move    #>$1,n0
        do      n7,>wf_endb
        move    x:(r7+$24),y0           ; ---- carrier, as in RING ----
        move    x:(r7+$20),a
        add     y0,a
        move    a1,x0
        move    x0,x:(r7+$20)
        move    x0,a
        abs     a
        move    #>$800000,y1
        add     y1,a
        neg     a
        move    a,y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,y0                    ; carrier
; L: fold, then ring
        move    x:(r0),x0
        move    x:(r7+$23),y1           ; gq
        mpy     x0,y1,a
        asl     #$2,a,a
        move    #>$400000,x1
        add     x1,a
        move    a1,x1
        move    x1,a
        abs     a
        move    #>$400000,b
        sub     b,a
        asl     #$1,a,a                 ; fold
        move    a,x0
        mpy     y0,x0,a                 ; fold * carrier  (signed encoding)
        move    x:(r7+$21),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$25),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$21)
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$26),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
; R
        move    x:(r0+n0),x0
        move    x:(r7+$23),y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    #>$400000,x1
        add     x1,a
        move    a1,x1
        move    x1,a
        abs     a
        move    #>$400000,b
        sub     b,a
        asl     #$1,a,a
        move    a,x0
        mpy     y0,x0,a
        move    x:(r7+$22),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$25),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$22)
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$26),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
wf_endb:
        nop
        rts
