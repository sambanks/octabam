; ---------------------------------------------------------------------------
; Ripple -- a Mutable-Instruments-Ripples-flavoured resonant SVF insert.
;
; Same contract as modules/warpfold/warp_fold.asm: a per-track INSERT that
; reads x:(r0)/x:(r0+n0) and writes back in place; no bus, no absolute Y,
; all state in this instance's own r7 block.
;
; The filter is the Chamberlin state-variable form, per channel:
;       lp += f * bp
;       hp  = x - lp - damp * bp
;       bp += f * hp
; with a drive stage in front (gain 1..4x, hard-clipped by the store limiter)
; and the HP node passing through a limited register move each sample -- both
; clips are deliberate: they are what tames the resonance and they are the
; character, the way Ripples' OTA stage is.
;
; ---- knobs ----------------------------------------------------------------
;   p0 FREQ  f = FREQ^2 * 0.984 + 0.0034      (~24 Hz .. ~7.2 kHz; the SVF's
;            stable region at 44.1k -- f = 2sin(pi*fc/fs), capped below 1.0)
;   p1 RES   damp = 0.992 - RES * 0.969       (RES=127 -> damp ~ 0.031, Q~30)
;   p2 DRV   gain = 1 + 3*DRV/128, clip at the rail
;   p3 MIX   out = dry + MIX*(wet - dry); MIX=0 is an exact passthrough
;   p7 MODE  0 LP, 1 BP, 2 HP (ChonVerb's slot-7 decode; unexpected -> LP)
;
; ---- r7 slots -------------------------------------------------------------
;   r7+$20  f     (per block)          r7+$24  lp state L (PERSISTENT)
;   r7+$21  damp  (per block)          r7+$25  bp state L (PERSISTENT)
;   r7+$22  g4 = gain/4 (per block)    r7+$26  lp state R (PERSISTENT)
;   r7+$23  m = MIX (per block)        r7+$27  bp state R (PERSISTENT)
; States are bounded by the limited stores; boot garbage is a legal state
; and decays. Nothing here ever becomes an address.
;
; Every mpy is `mpy x0,y1` (the known-signed encoding); audited by
; disassembly like warp_fold.asm's.
; ---------------------------------------------------------------------------

init:
        rts

proc:
; ---- per-block knob decode ------------------------------------------------
; f = FREQ^2 * 0.984 + 0.0034
        move    x:(r6+$0),x0
        move    x:(r6+$0),y1
        mpy     x0,y1,a
        move    a,x0
        move    #>$7e0000,y1            ; 0.984
        mpy     x0,y1,a
        add     #>$7000,a               ; + 0.0034
        move    a,x:(r7+$20)

; damp = 0.992 - RES * 0.969
        move    x:(r6+$1),x0
        move    #>$7c0000,y1            ; 0.969
        mpy     x0,y1,a
        neg     a
        add     #>$7f0000,a             ; 0.992 - res*0.969
        move    a,x:(r7+$21)

; g4 = 0.25 + DRV * 0.75   (gain/4; the loop shifts it back up by 2)
        move    x:(r6+$2),x0
        move    #>$600000,y1            ; 0.75
        mpy     x0,y1,a
        add     #>$200000,a             ; + 0.25
        move    a,x:(r7+$22)

; m = MIX
        move    x:(r6+$3),x0
        move    x0,x:(r7+$23)

; ---- MODE: page-2 slot 7 companion, bits 8-15 -----------------------------
        move    x:(r6+$c),a
        and     #>$ff00,a
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        move    #>$10000,x0
        cmp     x0,a
        beq     rp_dobp
        move    #>$20000,x0
        cmp     x0,a
        beq     rp_dohp
                                        ; 0, and anything unexpected: LP

; ===========================================================================
; MODE 0 -- LOWPASS. The per-channel body below is the template the other
; two modes copy; only the WET TAP line differs.
; ===========================================================================
        move    #>$1,n0
        do      n7,>rp_endlp
; L drive
        move    x:(r0),x0
        move    x:(r7+$22),y1           ; g4
        mpy     x0,y1,a
        asl     #$2,a,a                 ; x*gain, in acc up to +/-4
        move    a,x1                    ; x_d -- the limiter IS the drive clip
; lp += f*bp
        move    x:(r7+$25),x0           ; bp
        move    x:(r7+$20),y1           ; f
        mpy     x0,y1,a
        move    x:(r7+$24),b
        add     b,a
        move    a,x:(r7+$24)            ; lp'
        move    a,b                     ; b = lp'
; hp = x_d - lp' - damp*bp
        move    x:(r7+$21),y1           ; damp
        mpy     x0,y1,a                 ; damp*bp (x0 still bp)
        neg     a
        sub     b,a
        add     x1,a                    ; hp
; bp += f*hp
        move    a,x0                    ; hp, limited -- the resonance clamp
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        move    x:(r7+$25),b
        add     b,a
        move    a,x:(r7+$25)            ; bp'
; wet tap: LP
        move    x:(r7+$24),a
; mix
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$23),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
; R channel, states $26/$27
        move    x:(r0+n0),x0
        move    x:(r7+$22),y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x1
        move    x:(r7+$27),x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        move    x:(r7+$26),b
        add     b,a
        move    a,x:(r7+$26)
        move    a,b
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        neg     a
        sub     b,a
        add     x1,a
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        move    x:(r7+$27),b
        add     b,a
        move    a,x:(r7+$27)
        move    x:(r7+$26),a
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$23),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
rp_endlp:
        nop
        rts

; ===========================================================================
; MODE 1 -- BANDPASS: identical spine, wet = bp' (already in a at the tap).
; ===========================================================================
rp_dobp:
        move    #>$1,n0
        do      n7,>rp_endbp
        move    x:(r0),x0
        move    x:(r7+$22),y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x1
        move    x:(r7+$25),x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        move    x:(r7+$24),b
        add     b,a
        move    a,x:(r7+$24)
        move    a,b
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        neg     a
        sub     b,a
        add     x1,a
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        move    x:(r7+$25),b
        add     b,a
        move    a,x:(r7+$25)            ; bp' -- and a still holds it: the tap
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$23),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        move    x:(r0+n0),x0
        move    x:(r7+$22),y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x1
        move    x:(r7+$27),x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        move    x:(r7+$26),b
        add     b,a
        move    a,x:(r7+$26)
        move    a,b
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        neg     a
        sub     b,a
        add     x1,a
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        move    x:(r7+$27),b
        add     b,a
        move    a,x:(r7+$27)
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$23),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
rp_endbp:
        nop
        rts

; ===========================================================================
; MODE 2 -- HIGHPASS: identical spine, wet = hp (parked in y0 at the clamp,
; because bp's update consumes the accumulator).
; ===========================================================================
rp_dohp:
        move    #>$1,n0
        do      n7,>rp_endhp
        move    x:(r0),x0
        move    x:(r7+$22),y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x1
        move    x:(r7+$25),x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        move    x:(r7+$24),b
        add     b,a
        move    a,x:(r7+$24)
        move    a,b
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        neg     a
        sub     b,a
        add     x1,a
        move    a,x0                    ; hp, limited
        move    a,y0                    ; parked: the wet tap
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        move    x:(r7+$25),b
        add     b,a
        move    a,x:(r7+$25)
        move    y0,a                    ; wet = hp
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$23),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        move    x:(r0+n0),x0
        move    x:(r7+$22),y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x1
        move    x:(r7+$27),x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        move    x:(r7+$26),b
        add     b,a
        move    a,x:(r7+$26)
        move    a,b
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        neg     a
        sub     b,a
        add     x1,a
        move    a,x0
        move    a,y0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        move    x:(r7+$27),b
        add     b,a
        move    a,x:(r7+$27)
        move    y0,a
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$23),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
rp_endhp:
        nop
        rts
