; STUDIO VERB: the reverb of Mutable Instruments Clouds (clouds/dsp/fx/reverb.h,
; MIT, Copyright 2014 Emilie Gillet), a Griesinger/Dattorro plate: four input
; allpasses, then two halves of two allpasses and a delay, with a smeared first
; allpass and a modulated second delay. Port, not a copy: fixed point, the delay
; lengths scaled by 0.9682 (15,862 words in one ring, so the slot's last $202
; words, +$3DFE.., are never written: octabam's rule for an FX2 buffer (#785),
; SIDECHAIN_COMPRESSOR's window in T3's and T7's slot; the mailbox and LOAD METER
; sit in the top 256),
; 24-bit buffer words instead of Clouds' 12-bit (a value is held as value/8, so
; the buffer's range matches Clouds' +-8), parabolic LFOs updated once a block. A gate on the wet output
; (p5 GATE): hold 2048 + 256 k samples after the input falls under a threshold, then a
; desk gate's release (-60 dB in about 320 ms); once the gate is shut the tank's loop gain is 0,
; so the tank empties and the next hit starts from silence.
;
; Layout (cell k of line j is y:(r5 - base_j - k), r5 the write pointer, modulo 15862):
;   ap1    base     0 length  109
;   ap2    base   110 length  157
;   ap3    base   268 length  233
;   ap4    base   502 length  386
;   dap1a  base   889 length 1600
;   dap1b  base  2490 length 1973
;   del1   base  4464 length 3303
;   dap2a  base  7768 length 1852
;   dap2b  base  9621 length 1610
;   del2   base 11232 length 4630
;
; Scalars at x:(r7+n): $20 ring base, $21 write pointer, $22 clear calls left,
; $23 clear pointer, $24 AMT, $25 GC (input gain/4), $26 KRT, $27 KAP, $28 KLP
; (smoothed), $29 $2a LFO phases, $2c $2d the smear and delay fractions, $2e $2f
; the smear and delay offsets, $30 $31 the damping states, $32 apout, $33 input envelope,
; $34 hold counter, $35 gate gain, $36 hold length (0x7fffff = gate off), $37 $38 the loop gain
; and allpass coefficient in use (KRT and KAP, or 0 under a shut gate), $39 LCUT's coefficient,
; $3a $3b its states, $3c SIZE's f, $3d the long delay's swing, $3e $3f the LFO steps, $40..$44 the
; tank's read offsets, $45 the long delay's centre, $46 MOD's smoothed offset, $47 $48 the
; predelay's write and read offsets.
; Knobs: p0 AMNT amount, p1 GAIN input gain, p2 TIME reverb time, p3 DIFF
; diffusion, p4 TONE damping, p5 GATE hold (0 off); page 2: SIZE, LCUT, MOD, RATE
; (slots 6-9), PRE (slot 11).

init:
        move    #>$ffffff,m4
        move    r7,r4
        move    #>$20,n4
        move    (r4)+n4
        clr     a
        do      #41,>gv_zero
        move    a,x:(r4)+
gv_zero:
        nop
        move    x:>$213,r4
        move    x:(r4),a
        move    a,x:(r7+$20)
        move    a,x:(r7+$21)
        move    a,x:(r7+$23)
        move    #>77,a
        move    a,x:(r7+$22)
        rts

proc:
; Bounded clearing: 206 words a call, 77 calls, the output dry until the ring is clean.
        move    x:(r7+$22),a
        tst     a
        beq     gv_ready
        sub     #>$1,a
        move    a,x:(r7+$22)
        move    x:(r7+$23),r4
        move    #>$ffffff,m4
        clr     a
        do      #>206,>gv_clear
        move    a,y:(r4)+
gv_clear:
        nop
        move    r4,x:(r7+$23)
        rts
gv_ready:
; Knob words carry a non-zero low byte under an LFO: masked before any use.
        move    x:(r6+$0),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$24),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    a,x:(r7+$24)
        move    x:(r6+$1),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        asr     #$3,a,a
        move    x:(r7+$25),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    a,x:(r7+$25)
        move    x:(r6+$2),a
        and     #>$7f0000,a
        move    a1,x0
        move    #>$50a3d7,y1
        mpy     x0,y1,a
        move    #>$2ccccd,x1
        add     x1,a
        move    x:(r7+$26),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    a,x:(r7+$26)
        move    x:(r6+$3),a
        and     #>$7f0000,a
        move    a1,x0
        move    #>$666666,y1
        mpy     x0,y1,a
        move    x:(r7+$27),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    a,x:(r7+$27)
        move    x:(r6+$4),a
        and     #>$7f0000,a
        move    a1,x0
        move    #>$79999a,y1
        mpy     x0,y1,a
        move    #>$066666,x1
        add     x1,a
        move    x:(r7+$28),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    a,x:(r7+$28)
; Page 2 (5 Nov 2026). At their defaults (SIZE 127, LCUT 0, MOD 64, RATE 64) every value below is
; the one the code had as a constant before, exactly.
; Page 2 is three words of two controls (docs/firmware/PARAM_PAGES.md): slot 6 is x:(r6+$c)'s
; knob field (bits 16-23), slot 7 its companion (bits 8-15), slots 8 and 9 the same in x:(r6+$d).
; SIZE (slot 6): f = 0.8 (127 - SIZE)/127, smoothed; the tank's read taps move in by f of each length.
        move    x:(r6+$c),a
        and     #>$7f0000,a
        move    a1,x0
        move    #>$7f0000,a
        sub     x0,a
        move    a1,x0
        move    #>$6734ee,y1
        mpy     x0,y1,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$3c),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    a,x:(r7+$3c)
        move    x:(r7+$3c),y1
        move    #>1600,x0
        mpy     x0,y1,a
        move    #>$fff648,x1
        add     x1,a
        move    a1,x:(r7+$40)
        move    #>1973,x0
        mpy     x0,y1,a
        move    #>$ffee92,x1
        add     x1,a
        move    a1,x:(r7+$41)
        move    #>3303,x0
        mpy     x0,y1,a
        move    #>$ffe1aa,x1
        add     x1,a
        move    a1,x:(r7+$42)
        move    #>1852,x0
        mpy     x0,y1,a
        move    #>$ffda6d,x1
        add     x1,a
        move    a1,x:(r7+$43)
        move    #>1610,x0
        mpy     x0,y1,a
        move    #>$ffd422,x1
        add     x1,a
        move    a1,x:(r7+$44)
; MOD (slot 8): the long delay's swing, 2 dS m with dS its depth after SIZE and m = 1/2 + s, s smoothed
; from 0 toward MOD - 1/2.
        move    #>$061000,x0
        mpy     x0,y1,a
        move    a1,x1
        move    #>$061000,a
        sub     x1,a
        asl     #$1,a,a
        move    a1,x0
        move    x:(r6+$d),a
        and     #>$7f0000,a
        move    a1,x1
        move    x1,a
        move    #>$400000,x1
        sub     x1,a
        move    x:(r7+$46),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    a,x:(r7+$46)
        move    #>$400000,x1
        add     x1,a
        move    a1,y0
        mpy     y0,x0,a
        move    a1,x:(r7+$3d)
; the long delay's centre: its length after SIZE, less 2, less the swing, so the tap stays inside it
        move    #>4630,x0
        mpy     x0,y1,a
        move    a1,x1
        move    #>4628,a
        sub     x1,a
        move    x:(r7+$3d),b
        asr     #$c,b,b
        move    b1,x1
        sub     x1,a
        move    a1,x:(r7+$45)
; PRE (slot 11, x:(r6+$e)'s companion): a predelay of 32 PRE samples (0 to 92 ms) on the mono input,
; held in the far end of the long delay that SIZE leaves unread: m = 4630 f words past its tap, of
; which m - 2 are usable, written from the cell just past the tap. Clamped to that room, so none at
; SIZE 127. With no predelay both offsets are 0: ap1's write cell, which ap1 overwrites later in the
; sample, so the input passes untouched and the ring is not disturbed.
        move    #>4630,x0
        mpy     x0,y1,a
        move    a1,x1
        move    #>$ffc209,a
        add     x1,a
        move    a1,x:(r7+$47)
        move    x1,b
        move    #>2,x0
        sub     x0,b
        move    #0,x0
        tst     b
        tmi     x0,b
        move    x:(r6+$e),a
        and     #>$007f00,a
        asr     #$3,a,a
        move    a1,x0
        move    b1,x1
        move    x0,b
        sub     x1,a
        tgt     x1,b
        move    b1,x1
        move    x:(r7+$47),a
        sub     x1,a
        move    #0,x0
        tst     b
        teq     x0,a
        move    a1,x:(r7+$48)
        move    x:(r7+$47),a
        tst     b
        teq     x0,a
        move    a1,x:(r7+$47)
; RATE (slot 9, x:(r6+$d)'s companion): both LFOs' steps, 2 RATE times today's
        move    x:(r6+$d),a
        and     #>$007f00,a
        asl     #$8,a,a
        move    a1,y0
        move    #>380,x0
        mpy     y0,x0,a
        move    a1,x:(r7+$3e)
        move    #>228,x0
        mpy     y0,x0,a
        move    a1,x:(r7+$3f)
; LCUT (slot 7, x:(r6+$c)'s companion): a one-pole high-pass in each half of the tank, c = 0.1447 LCUT^2, smoothed (about
; 1 kHz at 127, 250 Hz at 64; 0 passes the tank untouched)
        move    x:(r6+$c),a
        and     #>$007f00,a
        asl     #$8,a,a
        move    a1,x0
        move    a1,y1
        mpy     x0,y1,a
        move    a1,x0
        move    #>$12866a,y1
        mpy     x0,y1,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$39),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    a,x:(r7+$39)
; GATE: 0 is off (hold length at maximum); k > 0 holds 2048 + 256 k samples.
        move    x:(r6+$5),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        asr     #$10,a,a
        tst     a
        bne     gv_gon
        move    #>$7fffff,a
        move    a1,x:(r7+$34)
        bra     gv_gdone
gv_gon:
        asl     #$8,a,a
        add     #>2048,a
gv_gdone:
        move    a1,x:(r7+$36)
; LFO phases advance a block at a time; the parabola 4x(1-|x|) stands for the cosine.
        move    x:(r7+$29),a
        move    x:(r7+$3e),x1
        do      n7,>gv_p29
        add     x1,a
gv_p29:
        nop
        move    a1,x:(r7+$29)
        move    x:(r7+$2a),a
        move    x:(r7+$3f),x1
        do      n7,>gv_p2a
        add     x1,a
gv_p2a:
        nop
        move    a1,x:(r7+$2a)
        move    x:(r7+$29),a
        abs     a
        move    a,x0
        move    #>$7fffff,b
        sub     x0,b
        move    b,x0
        move    x:(r7+$29),y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x0
; unipolar, as Clouds' LFO (0..1): (lfo1 + 1)/2. Bipolar, the reads reached 50 samples behind
; line 0 into the last tank line and fed it back to the input: the tail grew from TIME 94 up.
        move    x0,a
        asr     #$1,a,a
        add     #>$400000,a
        move    a,x0
; smear: offset 10 + 60 * lfo1 samples in Q12; whole part and fraction.
        move    #>$03c000,y1
        mpy     x0,y1,a
        add     #>$00a000,a
        move    a1,x0
        move    x0,a
        asr     #$c,a,b
        move    b1,x1
        and     #>$000fff,a
        asl     #$b,a,a
        move    a1,x:(r7+$2c)
        clr     a
        sub     x1,a
        move    a1,x:(r7+$2e)
        move    x:(r7+$2a),a
        abs     a
        move    a,x0
        move    #>$7fffff,b
        sub     x0,b
        move    b,x0
        move    x:(r7+$2a),y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x0
; delay 2: offset centre + swing * lfo2 samples (4531 + 97 at the defaults).
        move    x:(r7+$3d),y1
        mpy     x0,y1,a
        move    a1,x0
        move    x0,a
        asr     #$c,a,b
        move    b1,x1
        move    x:(r7+$45),b
        add     x1,b
        move    b1,x1
        and     #>$000fff,a
        asl     #$b,a,a
        move    a1,x:(r7+$2d)
        move    #>$ffd420,a
        sub     x1,a
        move    a1,x:(r7+$2f)
; the loop gain and the allpass coefficient this block: KRT and KAP, or 0 while the gate's gain
; is 0 (shut). With both 0 every line is a plain delay fed only by the (quiet) input, so the tank
; drains in one pass of its longest line and the next hit starts from silence.
        move    x:(r7+$26),a
        move    x:(r7+$35),b
        move    #0,x0
        tst     b
        teq     x0,a
        move    a1,x:(r7+$37)
        move    x:(r7+$27),a
        tst     b
        teq     x0,a
        move    a1,x:(r7+$38)
; block setup
        move    #>$1,n0
        move    #>15861,m4
        move    #>15861,m5
        move    x:(r7+$21),r5
        do      n7,>gv_end
; smear: the first allpass line read at 10 + 60 lfo1, written back at 100
        move    x:(r7+$2e),n5
        lua     (r5+n5),r4
        move    y:(r4)-,b
        move    y:(r4),a
        sub     b,a
        move    a,x0
        move    x:(r7+$2c),y0
        mpy     y0,x0,a
        add     b,a
        move    #>$ffff9c,n5
        move    a,y:(r5+n5)
; input: (L + R)/2 times the gain
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        move    a,y0
        abs     a
        move    a,x1
; gate: input envelope (instant attack, 1/512 release), hold counter, smoothed gain
        move    x:(r7+$33),a
        asr     #$9,a,b
        sub     b,a
        move    x1,b
        sub     a,b
        move    #0,x0
        tst     b
        tmi     x0,b
        add     b,a
        move    a1,x:(r7+$33)
        move    x:(r7+$34),b
        sub     #>$1,b
        move    #0,x0
        tst     b
        tmi     x0,b
        sub     #>$010000,a
        move    x:(r7+$36),x1
        tst     a
        tgt     x1,b
        move    b1,x:(r7+$34)
; a desk gate: open (hold left), the gain rises 1/32 of the way a sample (y1); shut, it falls
; 1/2048 a sample, a straight line in dB (-60 in about 320 ms), and below 2^-11 it is 0 (a); the
; hold picks one. Straight-line, for the pricer. A shut gate empties the tank: x:(r7+$37), $38.
        move    x:(r7+$35),x1
        move    #>$7fffff,a
        sub     x1,a
        asr     #$5,a,a
        add     x1,a
        move    a1,y1
        move    x1,a
        asr     #$b,a,a
        move    a1,x0
        move    x1,a
        sub     x0,a
        move    a,b
        move    #>$001000,x0
        sub     x0,b
        move    #0,x0
        tst     b
        tmi     x0,a
        move    x:(r7+$34),b
        tst     b
        tne     y1,a
        move    a,x:(r7+$35)
        move    x:(r7+$47),n5
        move    y0,y:(r5+n5)
        move    x:(r7+$48),n5
        move    y:(r5+n5),x0
        move    x:(r7+$25),y1
        mpy     x0,y1,a
; four input allpasses
        move    x:(r7+$38),y1
        move    #>$ffff94,n5
        move    y:(r5+n5),x0
        mac     x0,y1,a
        move    x0,b
        move    #>$000000,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     -x0,y1,a
        move    #>$fffef6,n5
        move    y:(r5+n5),x0
        mac     x0,y1,a
        move    x0,b
        move    #>$ffff92,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     -x0,y1,a
        move    #>$fffe0c,n5
        move    y:(r5+n5),x0
        mac     x0,y1,a
        move    x0,b
        move    #>$fffef4,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     -x0,y1,a
        move    #>$fffc89,n5
        move    y:(r5+n5),x0
        mac     x0,y1,a
        move    x0,b
        move    #>$fffe0a,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     -x0,y1,a
        move    a,x:(r7+$32)
; loop, first half: delay 2 (modulated) -> damping -> dap1a -> dap1b -> delay 1; left out
        move    x:(r7+$2f),n5
        lua     (r5+n5),r4
        move    y:(r4)-,b
        move    y:(r4),a
        sub     b,a
        move    a,x0
        move    x:(r7+$2d),y0
        mpy     y0,x0,a
        add     b,a
        move    a,x0
        move    x:(r7+$37),y1
        mpy     x0,y1,a
        move    x:(r7+$32),x0
        add     x0,a
        move    x:(r7+$30),b
        sub     b,a
        move    a,x0
        move    x:(r7+$28),y1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$30)
        move    x:(r7+$3a),b
        sub     b,a
        move    a,x0
        move    x:(r7+$39),y1
        mac     -x0,y1,a
        mac     x0,y1,b
        move    b,x:(r7+$3a)
        move    x:(r7+$38),y1
        move    x:(r7+$40),n5
        move    y:(r5+n5),x0
        mac     -x0,y1,a
        move    x0,b
        move    #>$fffc87,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     x0,y1,a
        move    x:(r7+$41),n5
        move    y:(r5+n5),x0
        mac     x0,y1,a
        move    x0,b
        move    #>$fff646,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     -x0,y1,a
        move    #>$ffee90,n5
        move    a,y:(r5+n5)
        asl     #$1,a,a
        move    a,x0
        move    x:(r7+$35),y1
        mpy     x0,y1,a
        move    a,x0
        move    x:(r7+$24),y1
        mpy     x0,y1,b
        asl     #$3,b,b
        move    x:(r0),x0
        move    x0,a
        add     b,a
        mac     -x0,y1,a
        move    a,x:(r0)+
; second half: delay 1 tail -> damping -> dap2a -> dap2b -> delay 2; right out
        move    x:(r7+$32),a
        move    x:(r7+$42),n5
        move    y:(r5+n5),x0
        move    x:(r7+$37),y1
        mac     x0,y1,a
        move    x:(r7+$31),b
        sub     b,a
        move    a,x0
        move    x:(r7+$28),y1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$31)
        move    x:(r7+$3b),b
        sub     b,a
        move    a,x0
        move    x:(r7+$39),y1
        mac     -x0,y1,a
        mac     x0,y1,b
        move    b,x:(r7+$3b)
        move    x:(r7+$38),y1
        move    x:(r7+$43),n5
        move    y:(r5+n5),x0
        mac     x0,y1,a
        move    x0,b
        move    #>$ffe1a8,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     -x0,y1,a
        move    x:(r7+$44),n5
        move    y:(r5+n5),x0
        mac     -x0,y1,a
        move    x0,b
        move    #>$ffda6b,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     x0,y1,a
        move    #>$ffd420,n5
        move    a,y:(r5+n5)
        asl     #$1,a,a
        move    a,x0
        move    x:(r7+$35),y1
        mpy     x0,y1,a
        move    a,x0
        move    x:(r7+$24),y1
        mpy     x0,y1,b
        asl     #$3,b,b
        move    x:(r0),x0
        move    x0,a
        add     b,a
        mac     -x0,y1,a
        move    a,x:(r0)+
        move    (r5)+
gv_end:
        nop
        move    r5,x:(r7+$21)
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts
