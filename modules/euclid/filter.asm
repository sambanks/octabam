; Euclid stereo two-pole TPT state-variable filter / amplitude modulator.
; The ColdFire control engine publishes the modulated cutoff or gain as FREQ.
; No shared buffers. All state is private to r7, in $00..$3f.
; $20 g2 target, $21 R, $22 previous TYPE, $1f c4, $33 inverse denominator
; $2e running g2, $2f ramp, $34/$35 L states, $36/$37 R states
; $23/$24/$25/$26 LP/BP/HP/AMP weights, $28 MIX, $1d dry, $1b wet
; Every product uses the audited signed x0,y1 encoding.
; CYCLES_FORWARD_BRANCHES
init:
        clr     a
        move    r7,r5
        move    #>$ffffff,m5
        do      #>64,>eu_zeroend
        move    a,x:(r5)+
eu_zeroend:
        nop
        rts

proc:
; TYPE, slot 8. AMP keeps value 3 for saved-project compatibility; NOTCH is
; appended at 4. Invalid saved bytes fall back to LP.
        move    x:(r6+$d),a
        and     #>$7f0000,a
        asr     #$10,a,a
        move    #>$4,x0
        cmp     x0,a
        ble     eu_type_valid
        clr     a
eu_type_valid:
        move    x:(r7+$22),y0           ; previous TYPE
        move    a1,x:(r7+$22)
        move    #>$3,x0
        cmp     x0,a
        beq     eu_amp_setup
; The filter did not run while AMP was selected. Clear its four integrators
; when returning so stale history cannot make the first filtered block click.
        move    y0,a
        cmp     x0,a
        bne     eu_filter_setup
        clr     a
        move    a,x:(r7+$34)
        move    a,x:(r7+$35)
        move    a,x:(r7+$36)
        move    a,x:(r7+$37)
eu_filter_setup:
; RES -> R, same law as Spectrum.
        move    x:(r6+$1),x0
        move    #>$4b2350,y1
        mpy     x0,y1,a
        neg     a
        add     #>$7fbe77,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        asr     #$1,a,a
        move    a,x:(r7+$21)
; Logarithmic cutoff table, retaining the ColdFire's fractional knob byte.
        move    x:(r6+$0),a
        and     #>$7fffff,a
        move    a1,x1
        move    #>$fab1e0,r5
        move    #>$ffffff,m5
        asr     #$12,a,a
        move    a1,n5
        move    x1,a
        and     #>$3ffff,a
        asl     #$5,a,a
        move    (r5)+n5
        move    a,x0
        move    p:(r5)+,y0
        move    p:(r5),b
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a
        move    a,x:(r7+$20)
        move    x:(r7+$20),a
; ---- the cutoff RAMP: dg = (g2 - g2run)/16 per block, added
; once per sample in the loop, so a fast FREQ sweep or LFO has no block-rate
; step (the ~2.8 kHz comb of a per-block jump). A 15-sample block reaches
; 15/16 of the way and the next block starts from where it got to.
        move    x:(r7+$2e),x0           ; g2run, where the last block ended
        sub     x0,a
        asr     #$4,a,a
        move    a,x:(r7+$2f)            ; dg
; Seed the reciprocal once per block. This covers the first block and RES
; edits even when cutoff is stationary; the sample loop updates it only
; while g is actually ramping.
        bsr     eu_denominator
; Select the wet tap. NOTCH is LP + HP; the existing accumulator saturates
; the sum safely. AMP branched around the entire SVF above.
        clr     a
        move    a,x:(r7+$23)
        move    a,x:(r7+$24)
        move    a,x:(r7+$25)
        move    x:(r7+$22),a
        move    #>$4,x0
        cmp     x0,a
        beq     eu_notch_taps
        move    r7,r5
        move    #>$23,n5
        move    (r5)+n5
        move    a1,n5
        move    (r5)+n5
        move    #>$7fffff,x0
        move    x0,x:(r5)
        bra     eu_type_done
eu_notch_taps:
        move    #>$7fffff,x0
        move    x0,x:(r7+$23)
        move    x0,x:(r7+$25)
eu_type_done:
; MIX, slot 11: companion field of r6+$e; pin full wet to unity.
        move    x:(r6+$e),a
        and     #>$7f00,a
        asl     #$8,a,a
        move    #$7f,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        move    #>$7fffff,x0
        teq     x0,a
        move    a,x:(r7+$28)
        move    #>$1,n0
        do      n7,>eu_loopend
        move    x:(r7+$2e),a
        move    x:(r7+$2f),x0
        add     x0,a
        move    a,x:(r7+$2e)
; A denominator frozen while g moves produces large overshoots when a gate
; closes from maximum cutoff. Follow the ramp, but retain the exact block
; value in x:$33 when dg is zero (the normal held-knob case).
        move    x:(r7+$2f),a
        tst     a
        beq     eu_den_held
        bsr     eu_denominator
eu_den_held:

        move    x:(r0),x0
        move    x0,x:(r7+$1d)           ; park x
        move    x:(r7+$2e),a            ; running g2
        move    x0,x1                   ; input: x is still in x0 (fills a's gap)
        move    a,x:(r7+$1c)            ; g2 this sample
; t8 = (x - (2R+g)*s0 - s1)/8, pre-scaled so nothing clamps before hp
        move    x:(r7+$34),x0           ; s0
        move    x:(r7+$1f),y1           ; c4 = (R + g2)/2
        mpy     x0,y1,a
        asl     #$2,a,a                 ; (2R + g) * s0
        move    x:(r7+$35),x0           ; s1
        add     x0,a
        move    x1,b
        sub     a,b                     ; t
        asr     #$3,b,b
        move    b,x0                    ; t8, |t8| <= 0.63
; hp = 8 * d * t8  (the ZDF's implicit solve)
        move    x:(r7+$33),y1           ; d
        mpy     x0,y1,a
        asl     #$3,a,a
        move    a,x0                    ; hp, limited -- the resonance clamp
        move    a,y0                    ; hp for the taps
; p = 2*g*hp ; bp = s0 + p ; s0' = bp + p  (trapezoidal integrator)
        move    x:(r7+$1c),y1           ; g2
        mpy     x0,y1,b
        asl     #$1,b,b                 ; p = g*hp
        move    x:(r7+$34),a
        add     b,a                     ; bp
        move    a,x1                    ; bp, limited
        add     b,a
        move    a,x:(r7+$34)            ; s0'
; q = 2*g*bp ; lp = s1 + q ; s1' = lp + q
        move    x1,x0
        move    x:(r7+$1c),y1           ; g2
        mpy     x0,y1,b
        asl     #$1,b,b                 ; q = g*bp
        move    x:(r7+$35),a
        add     b,a                     ; lp
        move    a,x:(r7+$1b)            ; lp parked (limited)
        add     b,a
        move    a,x:(r7+$35)            ; s1'
; Select the active LP, BP, HP or amplitude-modulated dry tap.
        move    x1,x0
        move    x:(r7+$24),y1
        mpy     x0,y1,a
        move    y0,x0
        move    x:(r7+$25),y1
        mpy     x0,y1,b
        add     b,a
        move    x:(r7+$1b),x0
        move    x:(r7+$23),y1
        mpy     x0,y1,b
        add     b,a
        move    x:(r7+$1d),x0
        move    x:(r7+$26),y1
        mpy     x0,y1,b
        add     b,a
        move    a,x:(r7+$1b)            ; wet
; dry + MIX * (wet - dry), half-scaled difference avoids saturation.
        move    x:(r7+$1d),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$28),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        move    x:(r0+n0),x0
        move    x0,x:(r7+$1d)           ; park x
        move    x:(r7+$2e),a            ; running g2
        move    x0,x1                   ; input: x is still in x0 (fills a's gap)
        move    a,x:(r7+$1c)            ; g2 this sample
; t8 = (x - (2R+g)*s0 - s1)/8, pre-scaled so nothing clamps before hp
        move    x:(r7+$36),x0           ; s0
        move    x:(r7+$1f),y1           ; c4 = (R + g2)/2
        mpy     x0,y1,a
        asl     #$2,a,a                 ; (2R + g) * s0
        move    x:(r7+$37),x0           ; s1
        add     x0,a
        move    x1,b
        sub     a,b                     ; t
        asr     #$3,b,b
        move    b,x0                    ; t8, |t8| <= 0.63
; hp = 8 * d * t8  (the ZDF's implicit solve)
        move    x:(r7+$33),y1           ; d
        mpy     x0,y1,a
        asl     #$3,a,a
        move    a,x0                    ; hp, limited -- the resonance clamp
        move    a,y0                    ; hp for the taps
; p = 2*g*hp ; bp = s0 + p ; s0' = bp + p  (trapezoidal integrator)
        move    x:(r7+$1c),y1           ; g2
        mpy     x0,y1,b
        asl     #$1,b,b                 ; p = g*hp
        move    x:(r7+$36),a
        add     b,a                     ; bp
        move    a,x1                    ; bp, limited
        add     b,a
        move    a,x:(r7+$36)            ; s0'
; q = 2*g*bp ; lp = s1 + q ; s1' = lp + q
        move    x1,x0
        move    x:(r7+$1c),y1           ; g2
        mpy     x0,y1,b
        asl     #$1,b,b                 ; q = g*bp
        move    x:(r7+$37),a
        add     b,a                     ; lp
        move    a,x:(r7+$1b)            ; lp parked (limited)
        add     b,a
        move    a,x:(r7+$37)            ; s1'
; Select the active LP, BP, HP or amplitude-modulated dry tap.
        move    x1,x0
        move    x:(r7+$24),y1
        mpy     x0,y1,a
        move    y0,x0
        move    x:(r7+$25),y1
        mpy     x0,y1,b
        add     b,a
        move    x:(r7+$1b),x0
        move    x:(r7+$23),y1
        mpy     x0,y1,b
        add     b,a
        move    x:(r7+$1d),x0
        move    x:(r7+$26),y1
        mpy     x0,y1,b
        add     b,a
        move    a,x:(r7+$1b)            ; wet
; dry + MIX * (wet - dry), half-scaled difference avoids saturation.
        move    x:(r7+$1d),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$28),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        lua     (r0+$2),r0              ; the frame advance: one stereo frame, n0 stays 1
eu_loopend:
        nop
        rts

; AMP fast path. It reproduces the old gain and dry/wet arithmetic exactly,
; but skips coefficient lookup, the reciprocal divide and both stereo SVFs.
eu_amp_setup:
        move    x:(r6+$0),a
        and     #>$7fffff,a
        move    #$7f,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        move    #>$7fffff,x0
        teq     x0,a
        move    a,x:(r7+$26)           ; gain
        move    x:(r6+$e),a
        and     #>$7f00,a
        asl     #$8,a,a
        move    #$7f,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        move    #>$7fffff,x0
        teq     x0,a
        move    a,x:(r7+$28)           ; MIX
        move    #>$1,n0
        do      n7,>eu_amp_loopend
        move    x:(r0),x0
        move    x:(r7+$26),y1
        mpy     x0,y1,a                ; wet = dry * LEVEL
        move    x0,b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$28),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        move    x:(r0+n0),x0
        move    x:(r7+$26),y1
        mpy     x0,y1,a
        move    x0,b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$28),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        lua     (r0+$2),r0              ; the frame advance: one stereo frame, n0 stays 1
eu_amp_loopend:
        nop
        rts

; d = 1 / (1 + 2*R*g + g^2), plus the coefficient used by both channels.
; Straight-line so cycle_count can price the conditional call above exactly.
eu_denominator:
        move    x:(r7+$2e),a
        move    x:(r7+$21),x0           ; R
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$1f)            ; c4
        move    x:(r7+$2e),x0           ; g2
        move    x:(r7+$2e),y1
        mpy     x0,y1,a                 ; g2^2
        move    x:(r7+$21),y1           ; R
        mac     x0,y1,a                 ; + R*g2
        add     #>$200000,a             ; + 1/4
        asr     #$1,a,a                 ; den/8
        move    a,x0
        move    #$10,y1                 ; 1/8
        move    y1,a                    ; a clean load: a0 = 0 for the divide
        andi    #$fe,ccr                ; carry clear
; 24 divide steps, unrolled so static cycle pricing sees every cycle.
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a
        div     x0,a                    ; 24 quotient bits land in a0
        move    a0,x0
        move    x0,x:(r7+$33)           ; d
        rts
