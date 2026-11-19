; CYCLES_FORWARD_BRANCHES
; ---------------------------------------------------------------------------
; STUTTR -- chance-engaged grain repeater.
;
; Y ring from the stock allocator. Stereo interleaved. Write always dry.
; RATE ticks roll CHNC to grab SIZE; HOLD keeps looping; MODE FWD/HALF/
; QUART/RND sets rate; REV is per-repeat reverse probability.
; Engage/release: ~64-sample linear dry<->wet crossfade (declick).
;
; r7 $20 base $21 write $22 clear $23 maxlen $24 size $25 rate
;    $26 chnc $27 mix $28 mode $29 clock $2a offset $2b active
;    $2c hold_left $2d dir $2e play_div $2f wetL $30 wetR
;    $31 hold_reload $32 rev_kn $33 slice start $34 lfsr $35 play_cnt
;    $36 armed $37 xfade $38 xf_step $39 xf_dir (+1 up / 0 hold / -1 down)
; Labels st00.. only. mpy x0,y1 / y0,x0 / x0,x0 only. init keeps r1. No rep.
; SIZE words: (kn+1)^2, min 8, even, clamp maxlen (FX2 max 15862, #785).
; HOLD reload: (kn+1)^2 << 4 samples, at least one grain (size/2 frames).
; ---------------------------------------------------------------------------

init:
        move    #>$ffffff,m4
        move    r7,r4
        move    #>$20,n4
        move    (r4)+n4
        clr     a
        do      #26,>st00
        move    a,x:(r4)+
st00:
        nop
        move    x:>$213,r4
        move    x:(r4),a
        move    a,x:(r7+$20)
        move    a,x:(r7+$21)
        move    a,x:(r7+$33)
        move    #>$80,a
        move    a,x:(r7+$22)
        move    #>$4000,x0
        move    x:(r7+$20),a
        sub     x0,a
        move    #>$0c00,b
        move    #>$3df6,x0
        tst     a
        tpl     x0,b
        move    b,x:(r7+$23)
        move    #>$1,x0
        move    x0,x:(r7+$2d)
        move    x0,x:(r7+$2e)
        move    #>$5a5a5a,x0
        move    x0,x:(r7+$34)
        move    #>$1ffff,x0             ; $7fffff/64 ≈ 64-sample fade
        move    x0,x:(r7+$38)
        rts

proc:
        move    x:(r7+$22),a
        tst     a
        beq     st01
        sub     #$1,a                    ; (6-bit immediate)
        move    a,x:(r7+$22)
        asl     #$7,a,a
        move    x:(r7+$20),x0
        add     x0,a
        move    a,r4
        move    #>$ffffff,m4
        clr     a
        do      #128,>st02
        move    a,y:(r4)+
st02:
        nop
        rts
st01:
        move    x:(r6+$0),a
        and     #>$7f0000,a
        asr     #$10,a,a
        add     #$1,a                    ; (6-bit immediate)
        move    a1,x0
        clr     b
        do      x0,>st48
        add     x0,b
st48:
        move    b,a
        move    #>$8,x0
        cmp     x0,a
        tlt     x0,a
        move    x:(r7+$23),x0
        cmp     x0,a
        tgt     x0,a
        and     #>$fffffe,a
        move    a,x:(r7+$24)
        move    x:(r6+$1),a
        and     #>$7f0000,a
        asr     #$10,a,a
        asl     #$5,a,a
        add     #>$80,a
; SYNC is page-2 companion of MODE at r6+$c (bits 8-15), not r6+$7
        move    x:(r6+$c),b
        and     #>$7f00,b
        asr     #$8,b,b
        move    #>$1,x0
        cmp     x0,b
        bne     st14
        asr     #$4,a,a
        bra     st17
st14:
        move    #>$2,x0
        cmp     x0,b
        bne     st15
        asr     #$3,a,a
        bra     st17
st15:
        move    #>$3,x0
        cmp     x0,b
        bne     st17
        asr     #$2,a,a
st17:
        move    a,x:(r7+$25)
        move    x:(r6+$2),a
        and     #>$7f0000,a
        asr     #$10,a,a
        move    a,x:(r7+$26)
        move    x:(r6+$3),a
        and     #>$7f0000,a
        asr     #$10,a,a
        add     #$1,a                    ; (6-bit immediate)
        move    a1,x0
        clr     b
        do      x0,>st50
        add     x0,b
st50:
        move    b,a
        asl     #$4,a,a
        move    x:(r7+$24),b
        asr     #$1,b,b
        cmp     b,a
        tlt     b,a
        move    a,x:(r7+$31)
        move    x:(r6+$4),a
        and     #>$7f0000,a
        asr     #$10,a,a
        move    a,x:(r7+$32)
        move    x:(r6+$5),a
        and     #>$7f0000,a
        move    #$7f,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        move    #>$7fffff,x0
        teq     x0,a
        move    a,x:(r7+$27)
; MODE is page-2 knob at r6+$c bits 16-23 (PARAM_PAGES.md)
        move    x:(r6+$c),a
        and     #>$7f0000,a
        asr     #$10,a,a
        move    a,x:(r7+$28)
        move    #$1,n0
        move    #>$ffffff,m4            ; r4 linear for the whole loop: once a call,
                                        ; not every sample (nothing below changes m4)
        do      n7,>st19
; write dry
        move    x:(r7+$21),r4
        move    x:(r0),a
        move    a,y:(r4)+
        move    x:(r0+n0),a
        move    a,y:(r4)+
        move    r4,a
        move    x:(r7+$20),x0
        sub     x0,a
        move    x:(r7+$23),x0
        cmp     x0,a
        blt     st03
        move    x:(r7+$20),r4
st03:
        move    r4,x:(r7+$21)
; HOLD countdown while active and not releasing (xf_dir >= 0)
        move    x:(r7+$2b),a
        tst     a
        beq     st40
        move    x:(r7+$39),a            ; xf_dir
        tst     a
        bmi     st04                    ; releasing: keep grain, no new HOLD math
        move    x:(r7+$2c),a
        sub     #$1,a                    ; (6-bit immediate)
        move    a,x:(r7+$2c)
        tst     a
        bgt     st04
; HOLD done -> start release fade (stay active)
        move    #$80,a                   ; (short immediate: bits 23-16)
        move    a,x:(r7+$39)
        move    #>$1,b
        tst     b
        bne     st04
st40:
; RATE clock; attempt = RATE overflow | first-fill edge
        move    x:(r7+$29),a
        move    x:(r7+$25),x0
        add     x0,a
        move    a,x:(r7+$29)
        clr     b                       ; attempt flag
        move    a1,a
        tst     a
        bpl     st41
        clr     a
        move    a,x:(r7+$29)            ; clear clock on overflow
        move    #>$1,b
st41:
        move    x:(r7+$21),a
        move    x:(r7+$20),x0
        sub     x0,a
        move    x:(r7+$24),x0
        cmp     x0,a
        blt     st04                    ; ring not full
        move    x:(r7+$36),a            ; armed?
        tst     a
        bne     st42
        move    #>$1,x0
        move    x0,x:(r7+$36)
        move    #>$1,b                  ; first fill forces attempt
st42:
        tst     b
        beq     st04
        move    x:(r7+$26),b            ; CHNC
        tst     b
        beq     st04
        move    #>$7f,x0
        cmp     x0,b
        beq     st26
        move    x:(r7+$34),a
        move    a,x0
        asl     #$1,a,a
        add     x0,a
        add     #$3d,a                   ; (6-bit immediate)
        and     #>$00ffff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$34)
        and     #>$7f,a
        move    a1,x0
        move    x:(r7+$26),a
        cmp     x0,a
        ble     st04
st26:
        move    x:(r7+$31),a
        move    a,x:(r7+$2c)
        move    #>$1,x0
        move    x0,x:(r7+$2b)
        move    x0,x:(r7+$39)           ; xf_dir = +1 (fade in)
        move    x:(r7+$21),a
        move    x:(r7+$24),x0
        sub     x0,a
        move    x:(r7+$20),x0
        cmp     x0,a
        bge     st05
        move    x:(r7+$23),x0
        add     x0,a
st05:
        move    a,x:(r7+$33)
        clr     a
        move    a,x:(r7+$2a)
        move    a,x:(r7+$35)
; play_div from MODE: 0->1, 1->2, 2->4; 3=RND among those
        move    x:(r7+$28),b
        move    #>$3,x0
        cmp     x0,b
        bne     stm0
; RND: LFSR -> 0..2 then map like MODE
        move    x:(r7+$34),a
        move    a,x0
        asl     #$1,a,a
        add     x0,a
        add     #$3d,a                   ; (6-bit immediate)
        and     #>$00ffff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$34)
        and     #$3,a                    ; (6-bit immediate)
        move    a1,b
        move    #>$2,x0
        cmp     x0,b
        tgt     x0,b                    ; clamp roll to 0..2
stm0:
; b = 0/1/2 -> div 1/2/4 via shifts
        move    #>$1,a
        tst     b
        beq     stm1
        asl     #$1,a,a                 ; 2
        move    #>$1,x0
        cmp     x0,b
        beq     stm1
        asl     #$1,a,a                 ; 4
stm1:
        move    a,x:(r7+$2e)
; REV roll -> dir
        move    #>$1,a
        move    x:(r7+$32),b
        tst     b
        beq     stm4
        move    #>$7f,x0
        cmp     x0,b
        beq     stm5
        move    x:(r7+$34),a
        move    a,x0
        asl     #$1,a,a
        add     x0,a
        add     #$3d,a                   ; (6-bit immediate)
        and     #>$00ffff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$34)
        and     #>$7f,a
        move    a1,x0
        move    x:(r7+$32),a
        cmp     x0,a
        ble     stm6
stm5:
        move    #$80,a                   ; (short immediate: bits 23-16)
        move    #>$1,b
        tst     b
        bne     stm4
stm6:
        move    #>$1,a
stm4:
        move    a,x:(r7+$2d)
st04:
        move    x:(r7+$2b),a
        tst     a
        bne     st28
        move    x:(r0),a
        move    a,x:(r7+$2f)
        move    x:(r0+n0),a
        move    a,x:(r7+$30)
        move    #>$1,b
        tst     b
        bne     st10
st28:
        move    x:(r7+$35),a
        tst     a
        beq     st27
        sub     #$1,a                    ; (6-bit immediate)
        move    a,x:(r7+$35)
        move    #>$1,b
        tst     b
        bne     st10
st27:
        move    x:(r7+$33),a
        move    x:(r7+$2a),x0
        add     x0,a
        move    x:(r7+$20),x0
        cmp     x0,a
        bge     st24
        move    x:(r7+$23),x0
        add     x0,a
st24:
        move    x:(r7+$20),x0
        move    x:(r7+$23),b
        add     x0,b
        cmp     b,a
        blt     st25
        move    x:(r7+$23),x0
        sub     x0,a
st25:
        move    a,r4
        move    y:(r4)+,a
        move    a,x:(r7+$2f)
        move    y:(r4)+,a
        move    a,x:(r7+$30)
        move    x:(r7+$2e),a
        sub     #$1,a                    ; (6-bit immediate)
        move    a,x:(r7+$35)
        move    x:(r7+$2a),a
        add     #$2,a                    ; (6-bit immediate)
        move    a,x1
        move    x:(r7+$2a),a
        sub     #$2,a                    ; (6-bit immediate)
        move    x:(r7+$2d),b
        tst     b
        tpl     x1,a
        move    #$00,x0                  ; (short immediate: bits 23-16)
        move    #$00,b                   ; (short immediate: bits 23-16)
        cmp     x0,a
        bge     st12
        move    x:(r7+$24),a
        sub     #$2,a                    ; (6-bit immediate)
        move    #>$1,b
st12:
        move    x:(r7+$24),x0
        cmp     x0,a
        blt     st13
        move    #$00,a                   ; (short immediate: bits 23-16)
        move    #>$1,b
st13:
        move    a,x:(r7+$2a)
        tst     b
        beq     st10
; wrap: REV roll
        move    #>$1,a
        move    x:(r7+$32),b
        tst     b
        beq     stm7
        move    #>$7f,x0
        cmp     x0,b
        beq     stm8
        move    x:(r7+$34),a
        move    a,x0
        asl     #$1,a,a
        add     x0,a
        add     #$3d,a                   ; (6-bit immediate)
        and     #>$00ffff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$34)
        and     #>$7f,a
        move    a1,x0
        move    x:(r7+$32),a
        cmp     x0,a
        ble     stm9
stm8:
        move    #$80,a                   ; (short immediate: bits 23-16)
        move    #>$1,b
        tst     b
        bne     stm7
stm9:
        move    #>$1,a
stm7:
        move    a,x:(r7+$2d)
; wrap: RND re-pick div
        move    x:(r7+$28),a
        move    #>$3,x0
        cmp     x0,a
        bne     st10
        move    x:(r7+$34),a
        move    a,x0
        asl     #$1,a,a
        add     x0,a
        add     #$3d,a                   ; (6-bit immediate)
        and     #>$00ffff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$34)
        and     #$3,a                    ; (6-bit immediate)
        move    a1,b
        move    #>$2,x0
        cmp     x0,b
        tgt     x0,b
        move    #>$1,a
        tst     b
        beq     stmB
        asl     #$1,a,a
        move    #>$1,x0
        cmp     x0,b
        beq     stmB
        asl     #$1,a,a
stmB:
        move    a,x:(r7+$2e)
st10:
; if active: wet = dry + xfade*(grain-dry), then step xfade
        move    x:(r7+$2b),a
        tst     a
        beq     st11
        move    x:(r0),b
        move    x:(r7+$2f),a
        sub     b,a
        move    a,x0
        move    x:(r7+$37),y1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$2f)
        move    x:(r0+n0),b
        move    x:(r7+$30),a
        sub     b,a
        move    a,x0
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$30)
; step xfade by xf_dir
        move    x:(r7+$39),b
        tst     b
        beq     st11
        bmi     stx1
; fade up (leave xf_dir=+1; tgt keeps xfade at full)
        move    x:(r7+$37),a
        move    x:(r7+$38),x0
        add     x0,a
        move    #>$7fffff,x0
        cmp     x0,a
        tgt     x0,a
        move    a,x:(r7+$37)
        move    #>$1,b
        tst     b
        bne     st11
stx1:
; fade down
        move    x:(r7+$37),a
        move    x:(r7+$38),x0
        sub     x0,a
        move    #$00,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        tlt     x0,a
        move    a,x:(r7+$37)
        tst     a
        bne     st11
; release done
        clr     a
        move    a,x:(r7+$2b)
        move    a,x:(r7+$39)
st11:
; MIX
        move    x:(r0),b
        move    x:(r7+$2f),a
        sub     b,a
        move    a,x0
        move    x:(r7+$27),y1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r0)+n0
        move    x:(r0),b
        move    x:(r7+$30),a
        sub     b,a
        move    a,x0
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r0)+
st19:
        nop
        rts
