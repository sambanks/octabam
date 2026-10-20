; ---------------------------------------------------------------------------
; VOID -- SCRAPE insert (FEED start: one-sample sat loop).
;
; Insert: x:(r0)/x:(r0+n0) in place, knobs r6, state r7. No bus, no buffers.
; Stages: vd_src -> vd_am -> vd_body -> vd_fdbk -> vd_sat -> out (always wet)
; Law: modules/void/void_ref.py
;
; P table (ptable literal): RATE +0, HPF +129, COLOR +258 (129 words each).
;
; r7: $00 phase $01 noise LCG
;     $02..$05 body filter state
;     $06 fbL   $07 fbR   (one-sample last after sat)
;     $08..$0a pink b0/b1/b2   $0b brown
;     $0c dcL   $0d dcR   (feedback DC tracker — high FDBK+DRV otherwise rails)
;     $10..$19 block knobs/flags ($16 = BAL, $1a = NTYP)
;     $20 wetL  $21 wetR  $22 dryL  $23 dryR
;     $24 scratch (u / pre-HP / osc)
;     $25 noise sample / sqr osc (reused after src)
;     $26 sin osc  $27 saw osc  $28 pink  $29 brown (scratch)
;     $40..$4f RESERVED for FEED delay (kept zero)
;
; CYCLES_FORWARD_BRANCHES
; ---------------------------------------------------------------------------

init:
        move    r7,r5
        clr     a
        do      #$50,>norep_vd_zi
        move    a,x:(r5)+
norep_vd_zi:
        move    #>$2a5f31,x0
        move    x0,x:(r7+$01)
        rts

proc:
        move    #>$ffffff,m5
        move    #>$fab1e0,r4
        move    x:(r6+$0),a
        and     #>$7fffff,a
        move    a,x:(r7+$16)            ; BAL: 0 = full input, 127 = full noise
        move    r4,r5
        move    x:(r6+$1),a
        and     #>$7fffff,a
        asr     #$10,a,a
        move    a1,n5
        move    (r5)+n5
        move    p:(r5),x0
        move    x0,x:(r7+$10)
        move    x:(r6+$2),a
        and     #>$7f0000,a
        asr     #$10,a,a
        move    #>$000002,x0
        cmp     x0,a
        move    #0,y0
        tgt     y0,a
        move    a,x:(r7+$17)
        move    x:(r6+$3),a
        and     #>$7fffff,a
        move    a,x:(r7+$11)
        move    x:(r6+$4),a
        and     #>$7fffff,a
        move    a,x:(r7+$13)
        move    x:(r6+$5),a
        and     #>$7fffff,a
        move    a,x:(r7+$12)
        move    x:(r6+$c),a
        and     #>$7f0000,a
        asr     #$10,a,a
; clr after cmp would set Z and make teq always fire (COLR always "open")
        move    #0,b
        move    #>$00007f,x0
        cmp     x0,a
        move    #>$000001,y0
        teq     y0,b
        move    b,x:(r7+$18)
        move    r4,r5
        move    #>$000102,n5
        move    (r5)+n5
        move    a1,n5
        move    (r5)+n5
        move    p:(r5),x0
        move    x0,x:(r7+$15)
; HPF = companion of $c (slot 7, top row)
        move    x:(r6+$c),a
        and     #>$007f00,a
        asr     #$8,a,a
        move    #0,b
        tst     a
        move    #>$000001,y0
        tne     y0,b
        move    b,x:(r7+$19)
        move    r4,r5
        move    #>$000081,n5
        move    (r5)+n5
        move    a1,n5
        move    (r5)+n5
        move    p:(r5),x0
        move    x0,x:(r7+$14)
        move    x:(r6+$d),a
        and     #>$7f0000,a
        asr     #$10,a,a
        move    #>$000002,x0
        cmp     x0,a
        move    #0,y0
        tgt     y0,a
        move    a,x:(r7+$1a)
        move    #$1,n0

        do      n7,>vd_end
        move    x:(r0),a
        move    a,x:(r7+$22)
        move    x:(r0+n0),a
        move    a,x:(r7+$23)
; white LCG -> $25 at -6 dB, then colour by NTYP (WHT/PINK/BRWN)
        move    x:(r7+$01),x0
        move    #>$19660d,y1
        mpy     x0,y1,b
        asr     b
        move    b0,x0
        move    x0,b
        add     #>$6ef35f,b
        move    b1,x:(r7+$01)
        move    b1,a
        asr     #$1,a,a                 ; × 1/2
        move    a,x0
        move    x0,x:(r7+$25)
; pink (Paul Kellet economy): b0..b2 in $08..$0a, out $28
        move    x0,x1
        move    #>$0cad8a,y0            ; 0.099046
        mpy     x1,y0,a
        move    x:(r7+$08),y1
        move    #>$7fb2ff,y0            ; 0.99765
        mpy     y1,y0,b
        add     b,a
        move    a,x:(r7+$08)
        asr     #$2,a,a                 ; sum ¼·b0 first (full sum saturates Q23)
        move    a,x:(r7+$28)
        move    #>$25f440,y0            ; 0.2965164
        mpy     x1,y0,a
        move    x:(r7+$09),y1
        move    #>$7b4396,y0            ; 0.96300
        mpy     y1,y0,b
        add     b,a
        move    a,x:(r7+$09)
        asr     #$2,a,a
        move    x:(r7+$28),b
        add     b,a
        move    a,x:(r7+$28)            ; ¼·(b0+b1)
        move    #>$06be97,y0            ; 0.0526913
        mpy     x1,y0,a
        add     x1,a                    ; white * 1.0526913
        move    x:(r7+$0a),y1
        move    #>$48f5c3,y0            ; 0.57000
        mpy     y1,y0,b
        add     b,a
        move    a,x:(r7+$0a)
        asr     #$2,a,a
        move    x:(r7+$28),b
        add     b,a
        move    a,x:(r7+$28)            ; ¼·(b0+b1+b2)
        move    #>$17a787,y0            ; 0.1848
        mpy     x1,y0,a
        asr     #$2,a,a
        move    x:(r7+$28),b
        add     b,a                     ; ¼·(b0+b1+b2+0.1848·w)
        move    a,x:(r7+$28)
; brown: br = 0.996*br + 0.08*w → $29
        move    #>$0a3d71,y0            ; 0.08
        mpy     x1,y0,a
        move    x:(r7+$0b),y1
        move    #>$7f7cee,y0            ; 0.996
        mpy     y1,y0,b
        add     b,a
        move    #>$7fffff,x0
        cmp     x0,a
        tgt     x0,a
        move    #>$800000,x0
        cmp     x0,a
        tlt     x0,a
        move    a,x:(r7+$0b)
        asr     #$1,a,a                 ; × 1/2
        move    a,x:(r7+$29)
; pick WHT / PINK / BRWN → $25
        move    x:(r7+$25),a
        move    x:(r7+$1a),b
        move    #>$000001,x1
        cmp     x1,b
        move    x:(r7+$28),x0
        teq     x0,a
        move    #>$000002,x1
        cmp     x1,b
        move    x:(r7+$29),x0
        teq     x0,a
        move    a,x:(r7+$25)
; BAL crossfade: wet = in + BAL*(noise - in); 0 = full input
        move    x:(r7+$22),a
        move    x:(r7+$25),b
        sub     a,b
        move    b,x0
        move    x:(r7+$16),y1           ; BAL (y1: signed mpy order, not mpysu)
        mpy     x0,y1,a
        move    x:(r7+$22),b
        add     b,a
        move    a,x:(r7+$20)
        move    x:(r7+$23),a
        move    x:(r7+$25),b
        sub     a,b
        move    b,x0
        move    x:(r7+$16),y1
        mpy     x0,y1,a
        move    x:(r7+$23),b
        add     b,a
        move    a,x:(r7+$21)
; phase
        move    x:(r7+$00),a
        move    x:(r7+$10),x0
        add     x0,a
        move    a1,x:(r7+$00)
        move    a1,x0
; SAW $27
        move    x0,x:(r7+$27)
; SQR $25 (reuse)
        move    x0,a
        tst     a
        move    #>$7fffff,a
        move    #>$800000,b
        tlt     b,a
        move    a,x:(r7+$25)
; SIN $26
        move    x0,a
        abs     a
        move    #>$800000,b
        add     b,a
        neg     a
        move    a,y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x:(r7+$26)
; osc select -> a
        move    x:(r7+$27),a
        move    x:(r7+$17),b
        tst     b
        move    x:(r7+$26),x0
        teq     x0,a
        move    #>$000001,x1
        cmp     x1,b
        move    x:(r7+$25),x0
        teq     x0,a
; env
        asr     #$1,a,a
        add     #>$400000,a
        move    a,b
        move    x:(r7+$11),x0
        move    #>$7fffff,a
        sub     x0,a
        move    b,y0
        mpy     y0,x0,b
        add     b,a
        move    a,y0
        move    x:(r7+$20),x1
        mpy     x1,y0,a
        move    a,x:(r7+$20)
        move    x:(r7+$21),x1
        mpy     x1,y0,a
        move    a,x:(r7+$21)
; HP L
        move    x:(r7+$20),x1
        move    x1,x:(r7+$24)
        move    x:(r7+$14),y0
        move    x:(r7+$02),b
        move    x1,a
        sub     b,a
        move    a,x0
        mpy     y0,x0,a
        add     b,a
        move    a,x:(r7+$02)
        move    x1,b
        sub     a,b
        move    b,a
        move    x:(r7+$19),b
        tst     b
        move    x:(r7+$24),x0
        teq     x0,a
        move    a,x:(r7+$20)
; HP R
        move    x:(r7+$21),x1
        move    x1,x:(r7+$24)
        move    x:(r7+$14),y0
        move    x:(r7+$03),b
        move    x1,a
        sub     b,a
        move    a,x0
        mpy     y0,x0,a
        add     b,a
        move    a,x:(r7+$03)
        move    x1,b
        sub     a,b
        move    b,a
        move    x:(r7+$19),b
        tst     b
        move    x:(r7+$24),x0
        teq     x0,a
        move    a,x:(r7+$21)
; LP (forward skip when COLOR open)
        move    x:(r7+$18),a
        tst     a
        bne     vd_open
        move    x:(r7+$15),y0
        move    x:(r7+$20),x1
        move    x:(r7+$04),b
        move    x1,a
        sub     b,a
        move    a,x0
        mpy     y0,x0,a
        add     b,a
        move    a,x:(r7+$04)
        move    a,x:(r7+$20)
        move    x:(r7+$21),x1
        move    x:(r7+$05),b
        move    x1,a
        sub     b,a
        move    a,x0
        mpy     y0,x0,a
        add     b,a
        move    a,x:(r7+$05)
        move    a,x:(r7+$21)
vd_open:
        move    x:(r7+$18),a
        tst     a
        beq     vd_do_sat
        move    x:(r7+$20),x0
        move    x0,x:(r7+$04)
        move    x:(r7+$21),x0
        move    x0,x:(r7+$05)
vd_do_sat:
; one-sample AC feedback into the drive: wet += FDBK * (last - dc)
; (without the DC strip, FDBK≳50 + DRV rails soft-clip to ±2/3 = silence on AC outs)
        move    x:(r7+$12),y0
        move    x:(r7+$06),a
        move    x:(r7+$0c),x1
        sub     x1,a
        move    a,x1
        mpy     x1,y0,a
        move    x:(r7+$20),b
        add     b,a
        move    a,x:(r7+$20)
        move    x:(r7+$07),a
        move    x:(r7+$0d),x1
        sub     x1,a
        move    a,x1
        mpy     x1,y0,a
        move    x:(r7+$21),b
        add     b,a
        move    a,x:(r7+$21)
        move    x:(r7+$20),a
        move    x:(r7+$13),b
        tst     b
        beq     vd_sL
; u = x + 3*(d*x) — not 3x first (Q23 saturates); then clamp; y = u - u^3/3
        move    b,x0
        move    a,x1
        mpy     x1,x0,a
        move    a,y1
        asl     #$1,a,a
        add     y1,a
        add     x1,a
        move    #>$7fffff,x0
        cmp     x0,a
        tgt     x0,a
        move    #>$800000,x0
        cmp     x0,a
        tlt     x0,a
        move    a,x0
        move    x0,x:(r7+$24)
        move    x0,y1
        mpy     x0,y1,a
        move    a,y1
        mpy     x0,y1,a
        move    a,y1
        move    #>$2aaaaa,x0
        mpy     x0,y1,a
        move    x:(r7+$24),b
        sub     a,b
        move    b,a
vd_sL:
        move    a,x:(r7+$20)
        move    a,x:(r7+$06)
; dc += 0.02 * (y - dc)
        move    x:(r7+$0c),b
        sub     b,a
        move    a,x0
        move    #>$028f5c,y1            ; ≈0.02 (y1: signed mpy, not mpysu)
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$0c)
        move    x:(r7+$20),a
        move    a,x:(r0)
        move    x:(r7+$21),a
        move    x:(r7+$13),b
        tst     b
        beq     vd_sR
        move    b,x0
        move    a,x1
        mpy     x1,x0,a
        move    a,y1
        asl     #$1,a,a
        add     y1,a
        add     x1,a
        move    #>$7fffff,x0
        cmp     x0,a
        tgt     x0,a
        move    #>$800000,x0
        cmp     x0,a
        tlt     x0,a
        move    a,x0
        move    x0,x:(r7+$24)
        move    x0,y1
        mpy     x0,y1,a
        move    a,y1
        mpy     x0,y1,a
        move    a,y1
        move    #>$2aaaaa,x0
        mpy     x0,y1,a
        move    x:(r7+$24),b
        sub     a,b
        move    b,a
vd_sR:
        move    a,x:(r7+$21)
        move    a,x:(r7+$07)
        move    x:(r7+$0d),b
        sub     b,a
        move    a,x0
        move    #>$028f5c,y1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$0d)
        move    x:(r7+$21),a
        move    a,x:(r0+n0)
        move    #>$2,n0                 ; stereo frame = 2 words (lofi2)
        move    (r0)+n0
        move    #>$1,n0
vd_end:
        rts
