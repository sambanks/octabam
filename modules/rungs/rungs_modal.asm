; ---------------------------------------------------------------------------
; Rungs -- a Mutable-Instruments-Rings-flavoured 8-mode modal resonator.
;
; Same insert contract as warp_fold.asm / ripple_svf.asm: reads this track's
; frames from x:(r0)/x:(r0+n0), writes back in place, no bus, no absolute Y,
; all state in this instance's own r7 block.
;
; The mono sum of the input excites eight parallel two-pole resonators:
;       y_n' = 2*c1_n*y_n - r^2*y_n'' + g*x        c1_n = r*cos(w_n)
; The wet is their sum/8, mixed against the dry. Mode frequencies come from
; a per-block computation: w_n = w0 * ratio_n * (1 + STRC*stretch_n), with
; ratio_n from the MODE table (STRING harmonic 1..8, BELL, GLASS stretched)
; and cos via half-angle -- s = sin(w/4) ~ v - v^3/6, cos(w/2) = 1 - 2s^2,
; cos(w) = 2cos^2(w/2) - 1, every intermediate inside Q23. Tuning error
; ~0.2% at the top of the range 🟡 (checked in the render pass).
;
; ---- knobs ----------------------------------------------------------------
;   p0 FREQ  fundamental: w0/4 = 0.00196 + FREQ^2*0.04275  (~55 Hz..~1.25 kHz)
;   p1 STRC  stretches the partial series sharp, more per higher mode
;   p2 DAMP  r = 0.9985 + DAMP*0.0015    (ring T60 ~0.1 s .. ~9 s)
;   p3 MIX   out = dry + MIX*(wet - dry); MIX=0 is an exact passthrough
;   p7 MODE  0 STRING, 1 BELL, 2 GLASS (partial-ratio tables)
;
; ---- r7 slots -------------------------------------------------------------
;   $20 m          $21 r^2        $22 gx (per sample)   $23 wet sum (per sample)
;   $24..$2b c1_0..c1_7 (per block)
;   $2c sc = STRC*0.2   $2d v scratch   $2e r   $2f w0/4
;   $30..$3f mode states, y1_n at $30+2n, y2_n at $31+2n (PERSISTENT --
;            bounded by the limited stores, boot garbage rings once and
;            decays through r<1; nothing here ever becomes an address)
;   $50..$57 ratio_n/16, loaded from the MODE table each block
;
; Every mpy/mac is `mpy x0,y1` / `mac x0,y1` / `mpy y0,x0` -- the encodings
; proven signed (mac x0,y1 ships in the delay). Audited by disassembly.
; ---------------------------------------------------------------------------

init:
        rts

proc:
; ---- shared per-block decode ----------------------------------------------
        move    x:(r6+$3),x0            ; m = MIX
        move    x0,x:(r7+$20)
        move    x:(r6+$1),x0            ; sc = STRC * 0.2
        move    #>$19999a,y1
        mpy     x0,y1,a
        move    a,x:(r7+$2c)
        move    x:(r6+$2),x0            ; r = 0.9985 + DAMP * 0.0015
        move    #>$30fc,y1              ; T60 ~ 6.9/(1-r): ~0.1 s .. ~9 s.
        mpy     x0,y1,a                 ; (hyperbolic in the knob -- long
        add     #>$7fcf00,a             ; rings live in the top few steps;
        move    a,x:(r7+$2e)            ; a voicing item, noted in README)
        move    a,x0                    ; r^2
        move    a,y1
        mpy     x0,y1,a
        move    a,x:(r7+$21)
        move    x:(r6+$0),x0            ; w0/4 = 0.00196 + FREQ^2 * 0.04275
        move    x:(r6+$0),y1
        mpy     x0,y1,a
        move    a,x0
        move    #>$057900,y1
        mpy     x0,y1,a
        add     #>$4000,a
        move    a,x:(r7+$2f)

; ---- MODE: pick the partial-ratio table (ChonVerb's slot-7 decode) --------
        move    x:(r6+$c),a
        and     #>$ff00,a
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        move    #>$10000,x0
        cmp     x0,a
        beq     rg_tbel
        move    #>$20000,x0
        cmp     x0,a
        beq     rg_tgls
; STRING: harmonics 1..8 (ratio/16 in Q23)
        move    #>$080000,x0
        move    x0,x:(r7+$50)
        move    #>$100000,x0
        move    x0,x:(r7+$51)
        move    #>$180000,x0
        move    x0,x:(r7+$52)
        move    #>$200000,x0
        move    x0,x:(r7+$53)
        move    #>$280000,x0
        move    x0,x:(r7+$54)
        move    #>$300000,x0
        move    x0,x:(r7+$55)
        move    #>$380000,x0
        move    x0,x:(r7+$56)
        move    #>$400000,x0
        move    x0,x:(r7+$57)
        bra     rg_setup
rg_tbel:
; BELL: 0.5, 1, 1.2, 1.5, 2, 2.5, 3, 4 -- hum tone under the prime
        move    #>$040000,x0
        move    x0,x:(r7+$50)
        move    #>$080000,x0
        move    x0,x:(r7+$51)
        move    #>$09999a,x0
        move    x0,x:(r7+$52)
        move    #>$0c0000,x0
        move    x0,x:(r7+$53)
        move    #>$100000,x0
        move    x0,x:(r7+$54)
        move    #>$140000,x0
        move    x0,x:(r7+$55)
        move    #>$180000,x0
        move    x0,x:(r7+$56)
        move    #>$200000,x0
        move    x0,x:(r7+$57)
        bra     rg_setup
rg_tgls:
; GLASS: n*(1+0.08n) -- a stretched, gong-glass series
        move    #>$08a3d7,x0
        move    x0,x:(r7+$50)
        move    #>$128f5c,x0
        move    x0,x:(r7+$51)
        move    #>$1dc28f,x0
        move    x0,x:(r7+$52)
        move    #>$2a3d71,x0
        move    x0,x:(r7+$53)
        move    #>$380000,x0
        move    x0,x:(r7+$54)
        move    #>$470a3d,x0
        move    x0,x:(r7+$55)
        move    #>$575c29,x0
        move    x0,x:(r7+$56)
        move    #>$68f5c2,x0
        move    x0,x:(r7+$57)

rg_setup:
; ---- per-mode coefficient stanza, unrolled 8x. Only three things vary:
; the ratio slot, the stretch weight q_n = (n+1)/16, and the c1 slot.
; v = (w0/4)*ratio*16, stretched by v*sc*q_n, clamped at 0.62 (the sin
; approximation's accuracy bound), then the half-angle chain to c1 = r*cos w.
; ---- mode 0 ----
        move    x:(r7+$2f),x0
        move    x:(r7+$50),y1
        mpy     x0,y1,a
        asl     #$4,a,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    x:(r7+$2c),y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$080000,x0            ; q = 1/16
        mpy     y0,x0,a
        move    x:(r7+$2d),b
        add     b,a
        move    #>$4f5c28,x0            ; 0.62 clamp
        cmp     x0,a
        tge     x0,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    a,y1
        mpy     x0,y1,a                 ; v^2
        move    a,y0
        move    #>$155555,x0
        mpy     y0,x0,a                 ; v^2/6
        move    a,y1
        move    x:(r7+$2d),x0
        mpy     x0,y1,a                 ; v^3/6
        neg     a
        move    x:(r7+$2d),b
        add     b,a                     ; s = sin(w/4)
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        asl     #$1,a,a
        neg     a
        add     #>$7fffff,a             ; cos(w/2)
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    #>$400000,b
        sub     b,a
        asl     #$1,a,a                 ; cos(w)
        move    a,x0
        move    x:(r7+$2e),y1
        mpy     x0,y1,a
        move    a,x:(r7+$24)            ; c1_0
; ---- mode 1 ----
        move    x:(r7+$2f),x0
        move    x:(r7+$51),y1
        mpy     x0,y1,a
        asl     #$4,a,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    x:(r7+$2c),y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$100000,x0            ; q = 2/16
        mpy     y0,x0,a
        move    x:(r7+$2d),b
        add     b,a
        move    #>$4f5c28,x0
        cmp     x0,a
        tge     x0,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$155555,x0
        mpy     y0,x0,a
        move    a,y1
        move    x:(r7+$2d),x0
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$2d),b
        add     b,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        asl     #$1,a,a
        neg     a
        add     #>$7fffff,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    #>$400000,b
        sub     b,a
        asl     #$1,a,a
        move    a,x0
        move    x:(r7+$2e),y1
        mpy     x0,y1,a
        move    a,x:(r7+$25)            ; c1_1
; ---- mode 2 ----
        move    x:(r7+$2f),x0
        move    x:(r7+$52),y1
        mpy     x0,y1,a
        asl     #$4,a,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    x:(r7+$2c),y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$180000,x0            ; q = 3/16
        mpy     y0,x0,a
        move    x:(r7+$2d),b
        add     b,a
        move    #>$4f5c28,x0
        cmp     x0,a
        tge     x0,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$155555,x0
        mpy     y0,x0,a
        move    a,y1
        move    x:(r7+$2d),x0
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$2d),b
        add     b,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        asl     #$1,a,a
        neg     a
        add     #>$7fffff,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    #>$400000,b
        sub     b,a
        asl     #$1,a,a
        move    a,x0
        move    x:(r7+$2e),y1
        mpy     x0,y1,a
        move    a,x:(r7+$26)            ; c1_2
; ---- mode 3 ----
        move    x:(r7+$2f),x0
        move    x:(r7+$53),y1
        mpy     x0,y1,a
        asl     #$4,a,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    x:(r7+$2c),y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$200000,x0            ; q = 4/16
        mpy     y0,x0,a
        move    x:(r7+$2d),b
        add     b,a
        move    #>$4f5c28,x0
        cmp     x0,a
        tge     x0,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$155555,x0
        mpy     y0,x0,a
        move    a,y1
        move    x:(r7+$2d),x0
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$2d),b
        add     b,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        asl     #$1,a,a
        neg     a
        add     #>$7fffff,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    #>$400000,b
        sub     b,a
        asl     #$1,a,a
        move    a,x0
        move    x:(r7+$2e),y1
        mpy     x0,y1,a
        move    a,x:(r7+$27)            ; c1_3
; ---- mode 4 ----
        move    x:(r7+$2f),x0
        move    x:(r7+$54),y1
        mpy     x0,y1,a
        asl     #$4,a,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    x:(r7+$2c),y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$280000,x0            ; q = 5/16
        mpy     y0,x0,a
        move    x:(r7+$2d),b
        add     b,a
        move    #>$4f5c28,x0
        cmp     x0,a
        tge     x0,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$155555,x0
        mpy     y0,x0,a
        move    a,y1
        move    x:(r7+$2d),x0
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$2d),b
        add     b,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        asl     #$1,a,a
        neg     a
        add     #>$7fffff,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    #>$400000,b
        sub     b,a
        asl     #$1,a,a
        move    a,x0
        move    x:(r7+$2e),y1
        mpy     x0,y1,a
        move    a,x:(r7+$28)            ; c1_4
; ---- mode 5 ----
        move    x:(r7+$2f),x0
        move    x:(r7+$55),y1
        mpy     x0,y1,a
        asl     #$4,a,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    x:(r7+$2c),y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$300000,x0            ; q = 6/16
        mpy     y0,x0,a
        move    x:(r7+$2d),b
        add     b,a
        move    #>$4f5c28,x0
        cmp     x0,a
        tge     x0,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$155555,x0
        mpy     y0,x0,a
        move    a,y1
        move    x:(r7+$2d),x0
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$2d),b
        add     b,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        asl     #$1,a,a
        neg     a
        add     #>$7fffff,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    #>$400000,b
        sub     b,a
        asl     #$1,a,a
        move    a,x0
        move    x:(r7+$2e),y1
        mpy     x0,y1,a
        move    a,x:(r7+$29)            ; c1_5
; ---- mode 6 ----
        move    x:(r7+$2f),x0
        move    x:(r7+$56),y1
        mpy     x0,y1,a
        asl     #$4,a,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    x:(r7+$2c),y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$380000,x0            ; q = 7/16
        mpy     y0,x0,a
        move    x:(r7+$2d),b
        add     b,a
        move    #>$4f5c28,x0
        cmp     x0,a
        tge     x0,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$155555,x0
        mpy     y0,x0,a
        move    a,y1
        move    x:(r7+$2d),x0
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$2d),b
        add     b,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        asl     #$1,a,a
        neg     a
        add     #>$7fffff,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    #>$400000,b
        sub     b,a
        asl     #$1,a,a
        move    a,x0
        move    x:(r7+$2e),y1
        mpy     x0,y1,a
        move    a,x:(r7+$2a)            ; c1_6
; ---- mode 7 ----
        move    x:(r7+$2f),x0
        move    x:(r7+$57),y1
        mpy     x0,y1,a
        asl     #$4,a,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    x:(r7+$2c),y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$400000,x0            ; q = 8/16
        mpy     y0,x0,a
        move    x:(r7+$2d),b
        add     b,a
        move    #>$4f5c28,x0
        cmp     x0,a
        tge     x0,a
        move    a,x:(r7+$2d)
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    a,y0
        move    #>$155555,x0
        mpy     y0,x0,a
        move    a,y1
        move    x:(r7+$2d),x0
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$2d),b
        add     b,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        asl     #$1,a,a
        neg     a
        add     #>$7fffff,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    #>$400000,b
        sub     b,a
        asl     #$1,a,a
        move    a,x0
        move    x:(r7+$2e),y1
        mpy     x0,y1,a
        move    a,x:(r7+$2b)            ; c1_7

; ---- per-sample loop ------------------------------------------------------
        move    #>$1,n0
        do      n7,>rg_end
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$3,a,a                 ; gx = (L+R)/8
        move    a,x:(r7+$22)
        clr     a
        move    a,x:(r7+$23)            ; sum = 0
; mode 0
        move    x:(r7+$31),x0
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$22),b
        add     b,a
        move    x:(r7+$30),x0
        move    x:(r7+$24),y1
        mac     x0,y1,a
        mac     x0,y1,a
        move    x0,x:(r7+$31)
        move    a,x:(r7+$30)
        asr     #$3,a,a
        move    x:(r7+$23),b
        add     b,a
        move    a,x:(r7+$23)
; mode 1
        move    x:(r7+$33),x0
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$22),b
        add     b,a
        move    x:(r7+$32),x0
        move    x:(r7+$25),y1
        mac     x0,y1,a
        mac     x0,y1,a
        move    x0,x:(r7+$33)
        move    a,x:(r7+$32)
        asr     #$3,a,a
        move    x:(r7+$23),b
        add     b,a
        move    a,x:(r7+$23)
; mode 2
        move    x:(r7+$35),x0
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$22),b
        add     b,a
        move    x:(r7+$34),x0
        move    x:(r7+$26),y1
        mac     x0,y1,a
        mac     x0,y1,a
        move    x0,x:(r7+$35)
        move    a,x:(r7+$34)
        asr     #$3,a,a
        move    x:(r7+$23),b
        add     b,a
        move    a,x:(r7+$23)
; mode 3
        move    x:(r7+$37),x0
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$22),b
        add     b,a
        move    x:(r7+$36),x0
        move    x:(r7+$27),y1
        mac     x0,y1,a
        mac     x0,y1,a
        move    x0,x:(r7+$37)
        move    a,x:(r7+$36)
        asr     #$3,a,a
        move    x:(r7+$23),b
        add     b,a
        move    a,x:(r7+$23)
; mode 4
        move    x:(r7+$39),x0
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$22),b
        add     b,a
        move    x:(r7+$38),x0
        move    x:(r7+$28),y1
        mac     x0,y1,a
        mac     x0,y1,a
        move    x0,x:(r7+$39)
        move    a,x:(r7+$38)
        asr     #$3,a,a
        move    x:(r7+$23),b
        add     b,a
        move    a,x:(r7+$23)
; mode 5
        move    x:(r7+$3b),x0
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$22),b
        add     b,a
        move    x:(r7+$3a),x0
        move    x:(r7+$29),y1
        mac     x0,y1,a
        mac     x0,y1,a
        move    x0,x:(r7+$3b)
        move    a,x:(r7+$3a)
        asr     #$3,a,a
        move    x:(r7+$23),b
        add     b,a
        move    a,x:(r7+$23)
; mode 6
        move    x:(r7+$3d),x0
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$22),b
        add     b,a
        move    x:(r7+$3c),x0
        move    x:(r7+$2a),y1
        mac     x0,y1,a
        mac     x0,y1,a
        move    x0,x:(r7+$3d)
        move    a,x:(r7+$3c)
        asr     #$3,a,a
        move    x:(r7+$23),b
        add     b,a
        move    a,x:(r7+$23)
; mode 7
        move    x:(r7+$3f),x0
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        neg     a
        move    x:(r7+$22),b
        add     b,a
        move    x:(r7+$3e),x0
        move    x:(r7+$2b),y1
        mac     x0,y1,a
        mac     x0,y1,a
        move    x0,x:(r7+$3f)
        move    a,x:(r7+$3e)
        asr     #$3,a,a
        move    x:(r7+$23),b
        add     b,a
        move    a,x:(r7+$23)
; mix, wet = sum, both channels
        move    x:(r7+$23),a
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        move    x:(r7+$23),a
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
rg_end:
        nop
        rts
