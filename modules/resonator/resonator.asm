; CYCLES_SEQUENTIAL_LOOPS
; ---------------------------------------------------------------------------
; RESONATOR -- 4-band Chamberlin SVF filter bank (FX1 station).
;
; S-4 RING style: wet = live input through four bandpasses. NOT a modal body.
;
; Per band (Chamberlin):
;   low  += f * band
;   high  = x - low - damp * band
;   band += f * high
;   y     = g_i * band
;
; P table (build rewrites the one table-base literal below), 66 words:
;   +0  F   33  Chamberlin f = 2*sin(pi*fc/fs), fc 40..4000
;   +33 DAMP 33  damp; index 0 = most resonant, 32 = widest
;
; Knobs: r6+0..3 = GN1..GN4, r6+4 = DECY, r6+5 = MIX
;        page 2: r6+$c/$d = PIT1|PIT2, PIT3|PIT4; r6+$e = SCAL|LIM
; REPLACE: out = lim(dry + MIX*(wet-dry)); MIX 127 forces wet only.
; wet = sum(g*band)*4. g = (GN/128)*(SCALE/128)*32.
;   SCALE 8 → tame (GN 64 = 0dB); SCALE 127 → build-TN smash (~×16 at GN64).
; DECY high → low damp.
;
; LIM: shared current-block stereo peak limiter, one div outside sample DO.
; Ceiling = 0.75 - LIM*0.5/128 (LIM 0 bypass), near -2.5..-12 dBFS.
; Unity below ceiling, no makeup gain; approximately 63 ms block release.
; The second pass controls the first transient without nested DO/div.
;
; r7: $00..$0f L 4*(low,band), $10..$1f R same,
;     $20 fx2-dry  $21 MIX  $22 damp  $23 exc
;     $25/$26 prev L/R  $27 drive  $28 edge scratch
;     $29 lim thresh (0 = off)  $2a lim level_s  $2b lim gain
;     $2c mixed L  $2d mixed R  $2e block peak  $2f block start
;     $30..$33 f0..f3  $34..$37 g0..g3  $38 SCALE  $40..$43 pit<<16
;     $4b i  $58 wet-acc  $5a P-base
;
; CYCLES_FORWARD_BRANCHES -- LIM 0 skips the envelope/GR path after MIX
; ---------------------------------------------------------------------------

init:
        move    x:>$213,r4
        move    #>$ffffff,m4
        move    x:(r4),x0
        move    x0,a
        move    #>$4000,x0
        sub     x0,a
        clr     b
        move    #>$1,x0
        tst     a
        tpl     x0,b
        move    b,x:(r7+$20)
        clr     a
        move    r7,r4
        move    #>$ffffff,m4
        do      #<$20,>rs_iz
        move    a,x:(r4)+
rs_iz:
        move    a,x:(r7+$25)
        move    a,x:(r7+$26)
        move    a,x:(r7+$27)
        move    a,x:(r7+$28)
        move    a,x:(r7+$29)            ; lim thresh (0 = off)
        move    a,x:(r7+$2a)            ; lim level_s
        move    a,x:(r7+$2b)            ; lim gain
        move    a,x:(r7+$2c)            ; mixed L
        move    a,x:(r7+$2d)            ; mixed R
        move    a,x:(r7+$38)
        rts

proc:
        move    x:(r7+$20),a
        tst     a
        bne     rs_end
        move    #>$fab1e0,r5
        move    r5,x:(r7+$5a)
; MIX
        move    x:(r6+$5),a
        and     #>$7f0000,a
        move    #>$7f0000,x0
        cmp     x0,a
        move    #>$7fffff,x0
        teq     x0,a
        move    a,x:(r7+$21)
; DECY -> damp (high DECY = low damp index) + exc gain
        move    x:(r6+$4),a
        and     #>$7f0000,a
        move    a,x:(r7+$4c)
        move    #>$7f0000,x0
        move    x0,b
        sub     a,b
        move    b,a
        move    x:(r7+$5a),r5
        move    #$21,n5
        move    (r5)+n5
        move    a,x1
        and     #>$7fffff,a
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
        move    a,x:(r7+$22)
; exc = 1 - u; DECY 127 → force 0 (less dry feed into the BPs)
        move    x:(r7+$4c),a
        move    #>$7fffff,x0
        move    x0,b
        sub     a,b
        move    #>$7f0000,x0
        move    x:(r7+$4c),a
        cmp     x0,a
        move    #>$0,a
        teq     a,b
        move    b,x:(r7+$23)
; GN1..GN4 → $34..$37 as kn/128
        move    x:(r6),a
        and     #>$7f0000,a
        move    a,x:(r7+$34)
        move    x:(r6+$1),a
        and     #>$7f0000,a
        move    a,x:(r7+$35)
        move    x:(r6+$2),a
        and     #>$7f0000,a
        move    a,x:(r7+$36)
        move    x:(r6+$3),a
        and     #>$7f0000,a
        move    a,x:(r7+$37)
; page-2 PIT1..4 → $40..$43 as <<16; SCALE → $38
        move    x:(r6+$c),a
        and     #>$7f0000,a
        move    a,x:(r7+$40)
        move    x:(r6+$c),a
        and     #>$00ff00,a
        asl     #$8,a,a
        move    a,x:(r7+$41)
        move    x:(r6+$d),a
        and     #>$7f0000,a
        move    a,x:(r7+$42)
        move    x:(r6+$d),a
        and     #>$00ff00,a
        asl     #$8,a,a
        move    a,x:(r7+$43)
        move    x:(r6+$e),a
        and     #>$7f0000,a
        move    a,x:(r7+$38)
; LIMIT_THRESHOLD
; f0..f3 from parked pits
        clr     a
        move    a,x:(r7+$4b)
        move    r7,r1
        move    #$30,n1
        move    (r1)+n1
        do      #4,>rs_fbd
        bsr     rs_flook
        move    x:(r7+$4b),a
        add     #>$1,a
        move    a,x:(r7+$4b)
rs_fbd:
; samples
        move    #>$1,n0
; LIMIT_PREPARE
        do      n7,>rs_sz
        move    x:(r0),x1
        move    x:(r7+$25),y1
        move    x1,x0
        move    x:(r7+$23),y0
        mpy     y0,x0,b                 ; exc*x (y0,x0 encodes as mpy, not mpysu)
        move    b,x:(r7+$27)
        move    y1,a
        abs     a
        move    #>$066666,x0
        cmp     x0,a
        move    #>$0,a
        move    #>$7fffff,x0
        tmi     x0,a
        move    a,x:(r7+$28)
        move    x1,a
        abs     a
        move    #>$028f5c,x0
        cmp     x0,a
        move    #>$0,a
        move    #>$7fffff,x0
        tgt     x0,a
        move    x:(r7+$28),x0
        move    a,y0
        mpy     y0,x0,b
        move    x:(r7+$27),a
        tst     b
        move    x1,y0
        tne     y0,a
        move    a,x:(r7+$27)
        move    x1,x:(r7+$25)
        move    r7,r4
        move    r7,r3
        move    #$30,n3
        move    (r3)+n3
        move    r7,r2
        move    #$34,n2
        move    (r2)+n2
        clr     a
        move    a,x:(r7+$58)
        bsr     rs_one
        bsr     rs_one
        bsr     rs_one
        bsr     rs_one
        move    x:(r7+$58),a
        asl     #$2,a,a
        move    a,y0
        move    y0,x1
        move    x:(r0),a
        move    x1,b
        sub     a,b
        move    b,x0
        move    x:(r7+$21),y0
        mpy     y0,x0,b                 ; MIX*(wet-dry)
        add     b,a
        move    #>$7fffff,x0
        move    x:(r7+$21),b
        cmp     x0,b
        move    x1,y0
        teq     y0,a
        move    a,x:(r7+$2c)            ; stash L; advance to R without write
        move    (r0)+
        move    x:(r0),x1
        move    x:(r7+$26),y1
        move    x1,x0
        move    x:(r7+$23),y0
        mpy     y0,x0,b
        move    b,x:(r7+$27)
        move    y1,a
        abs     a
        move    #>$066666,x0
        cmp     x0,a
        move    #>$0,a
        move    #>$7fffff,x0
        tmi     x0,a
        move    a,x:(r7+$28)
        move    x1,a
        abs     a
        move    #>$028f5c,x0
        cmp     x0,a
        move    #>$0,a
        move    #>$7fffff,x0
        tgt     x0,a
        move    x:(r7+$28),x0
        move    a,y0
        mpy     y0,x0,b
        move    x:(r7+$27),a
        tst     b
        move    x1,y0
        tne     y0,a
        move    a,x:(r7+$27)
        move    x1,x:(r7+$26)
        move    r7,r4
        move    #$10,n4
        move    (r4)+n4
        move    r7,r3
        move    #$30,n3
        move    (r3)+n3
        move    r7,r2
        move    #$34,n2
        move    (r2)+n2
        clr     a
        move    a,x:(r7+$58)
        bsr     rs_one
        bsr     rs_one
        bsr     rs_one
        bsr     rs_one
        move    x:(r7+$58),a
        asl     #$2,a,a
        move    a,y0
        move    y0,x1
        move    x:(r0),a
        move    x1,b
        sub     a,b
        move    b,x0
        move    x:(r7+$21),y0
        mpy     y0,x0,b                 ; MIX*(wet-dry)
        add     b,a
        move    #>$7fffff,x0
        move    x:(r7+$21),b
        cmp     x0,b
        move    x1,y0
        teq     y0,a
        move    a,x:(r7+$2d)            ; stash R (r0 still on R)
; LIMIT_COLLECT
        ; r0 on R: write R, back to L, write L, step past R (no n0 #>)
        move    x:(r7+$2d),a
        move    a,x:(r0)-               ; write R, r0 → L
        move    x:(r7+$2c),a
        move    a,x:(r0)+               ; write L, r0 → R
        lua     (r0+1),r0               ; past R for next frame
rs_sz:
        nop
; LIMIT_FINISH
rs_end:
        rts

; one Chamberlin BP: state at r4, f at r3+, gain at r2+, drive $27, damp $22
; f stays in y0 (signed mpy y0,x0); no $59 spill; 2 words x 8 calls.
rs_one:
        move    x:(r3)+,y0              ; f
        move    x:(r4)+,a               ; low
        move    x:(r4)-,x0              ; band
        mpy     y0,x0,b                 ; f*band (signed)
        add     b,a
        move    a,x:(r4)+               ; store low, r4 → band
        move    a,x0                    ; low
        move    x:(r7+$27),a            ; drive/exc
        move    x0,b
        sub     b,a                     ; high = exc - low
        move    x:(r7+$22),x0
        move    x:(r4),y1
        mpy     x0,y1,b                 ; damp*band (x0,y1 encodes as mpy)
        sub     b,a
        move    a,x0                    ; high
        move    x:(r4),a                ; band
        mpy     y0,x0,b                 ; f*high (signed; y0 still f)
        add     b,a
        move    a,x:(r4)+
        move    a,x0
        move    x:(r2)+,y1              ; GN kn/128
        mpy     x0,y1,a                 ; band*(GN/128)
        move    a,x0
        move    x:(r7+$38),y1           ; SCALE kn/128
        mpy     x0,y1,a                 ; *(SCALE/128)
        asl     #$5,a,a                 ; ×32 → g=(GN/128)*(SCALE/128)*32
        move    x:(r7+$58),b            ; SCALE 8 → ×2 (tame); 127 → TN smash
        add     a,b
        move    b,x:(r7+$58)
        rts

; Look up f for pit word at $40+$4b into (r1)+
rs_flook:
        move    r7,r5
        move    #$40,n5
        move    (r5)+n5
        move    x:(r7+$4b),a
        move    a1,n5
        move    (r5)+n5
        move    x:(r5),a
        and     #>$7f0000,a
        move    a,x1
        move    x:(r7+$5a),r5
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
        move    a,x:(r1)+
        rts
