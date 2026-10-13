; CYCLES_FORWARD_BRANCHES
; ---------------------------------------------------------------------------
; BBD -- a clocked bucket-brigade delay, one tap, as an FX2 insert.
;
; The chain, per sample (bbd_ref.py is the float model this is proven
; against; README.md has the design notes):
;   x    = (L+R)/2 + FDBK * tone(previous wet)          TONE: the tilt
;   q    = pade_tanh(x) / (LP10ms|q[n-1]| + 1e-5)       2:1 feedback compressor
;   v    = 8th-order Butterworth LP at clock/3 (q)      anti-alias
;   clock: every P samples (P = 2.15..8.61, TIME) the line shifts once:
;          the input sampled at the clock edge goes in, and the bucket that
;          went in stages-1 ticks ago comes out through the charge-transfer
;          polynomial plus white noise, and is HELD until the next tick
;   y    = 7th + 2nd order Butterworth LP at clock/3 (held)   reconstruction
;   wet  = dc_block(y) * LP10ms|dc_block(y)|             expander
;   out  = dry - k dry + g wet, both channels (MIX: g to 1 by 64, then k)
; The bucket path runs at half scale (the compressor clips at +-2).
;
; Knobs: TIME r6+0, FDBK r6+1, FRZ r6+2, TONE r6+3, FREQ r6+4, MIX r6+5,
; STGS r6+$c (page-2 slot 6, knob field), LIM r6+$c bits 8-15 (slot 7),
; PRE r6+$d bits 8-15 (slot 9), POST r6+$e (slot 10). A STGS change fades the
; wet out over 16 calls, clears the ring (256 words a call, dry) and fades back in.
;
; ---- r7 slots ($00..$5a; the OS allows $00..$83) --------------------------
;   $00 Y buffer base (allocator, FX2: 16,384 words)   $01 clear calls left
;   $02 fade calls left  $03 stage (knob word)  $04 ring modulo (stages-2)
;   $05 noise LCG        $06 ring write pointer
;   ---- zeroed by every reset ($07..$3f) ----
;   $07 P16 (clock period / 16, Q23)   $08 clock time / 16   $09 v[n-1]
;   $0a held bucket   $0b compressor average   $0c q[n-1]   $0d expander avg
;   $0e $0f DC blocker x1 y1   $10 tone 200 Hz LP   $11..$14 tone BP w1 w2 y1 y2
;   $15..$19 smoothed FDBK MIX (TONE: low-minus-high, high, peak) / 8
;   $1a..$1e their targets      $1f P16 target
;   $20..$29 AA boundaries (input, then after each of 4 sections; x1 x2)
;   $2a one-pole input x1      $2b..$34 recon boundaries (4 sections)
;   $35 wet/2   $36 snap P16 to its target   $37 K   $38 K^2
;   $39 FRZ hold   $3a FRZ 127   $3b rotation   $3c..$3e FREQ bandpass b0/2 -a1/2 -a2/2
;   $3f FDBK after LIM
;   ---- zeroed by init only ($40..$5a) ----
;   $40..$48 1/(2Q) table   $49..$4c PRE x1 x2 y1 y2   $4d..$50 POST x1 x2 y1 y2
;   $59 $5a PRE, POST on (0 = bypass)
; Y: ring at base..base+4094, coefficients at base+$2000 (5 per section),
; the fixed 150 Hz PRE/POST high-pass at base+$2030, and FREQ's bandpass at
; base+$2035 (b0 0 -b0 -a1 -a2, halved), copied from $3c..$3e each call.
;
; Multiplies use only the canonical operand pairs (dsp_asm encodes the
; others as mpysu/macsu): x0x0 y0y0 x1x0 y1y0 x0y1 y0x0 x1y0 y1x1.
; ---------------------------------------------------------------------------

init:
        move    #>$ffffff,m4
        move    r7,r4
        clr     a
        do      #$5b,>bbzero
        move    a,x:(r4)+
bbzero:
        nop
        move    x:>$213,r4
        move    x:(r4),a
        move    a,x:(r7+$00)
        move    #>$2030,x0
        add     x0,a
        move    a,r4                    ; the 150 Hz HPF, b0/2 b1/2 b2/2 -a1/2 -a2/2
        move    #>$3f0a45,a
        move    a,y:(r4)+
        move    #>$81eb76,a
        move    a,y:(r4)+
        move    #>$3f0a45,a
        move    a,y:(r4)+
        move    #>$7e10da,a
        move    a,y:(r4)+
        move    #>$c1e7c7,a
        move    a,y:(r4)+
        move    #>$10,a                 ; clear 16 x 256 words: the longest ring, 4,095
        move    a,x:(r7+$01)
        move    #>$5a5a5b,a
        move    a,x:(r7+$05)
        move    #>$7d8a5f,a             ; 1/(2Q), in section order, for the rotation
        move    a,x:(r7+$40)
        move    #>$6a6d99,a
        move    a,x:(r7+$41)
        move    #>$471ced,a
        move    a,x:(r7+$42)
        move    #>$18f8b8,a
        move    a,x:(r7+$43)
        move    #>$7352f3,a
        move    a,x:(r7+$45)
        move    #>$5a827a,a
        move    a,x:(r7+$46)
        move    #>$4fce84,a
        move    a,x:(r7+$47)
        move    #>$1c7b91,a
        move    a,x:(r7+$48)
        rts

proc:
        move    #>$ffffff,m1            ; r1, r4, r5 walk linearly until the loop
        move    #>$ffffff,m4
        move    #>$ffffff,m5
; ---- clearing: dry, 256 ring words a call; the last call resets ----------
        move    x:(r7+$01),a
        tst     a
        beq     bbrun
        sub     #>$1,a
        move    a,x:(r7+$01)
        move    a,b
        asl     #$8,a,a
        move    x:(r7+$00),x0
        add     x0,a
        move    a,r4
        move    #>$ffffff,m4
        clr     a
        do      #$100,>bbwipe           ; do, not rep: interrupts stay serviced
        move    a,y:(r4)+
bbwipe:
        tst     b
        bne     bbdry
        move    r7,r4
        move    #>$7,n4
        move    (r4)+n4
        do      #$39,>bbwipx
        move    a,x:(r4)+
bbwipx:
        nop
        move    #>$040000,a             ; poly(0): the DC every bucket carries, already
        move    a,x:(r7+$0a)            ; through the reconstruction and the DC blocker,
        move    a,x:(r7+$0e)            ; so a reset starts quiet
        move    r7,r4
        move    #>$2a,n4
        move    (r4)+n4
        do      #$b,>bbwipr
        move    a,x:(r4)+
bbwipr:
        nop
        move    #>$400000,a             ; warm start: the compressor's last output = 1
        move    a,x:(r7+$0b)
        move    a,x:(r7+$0c)
        move    #>$100000,a             ; TONE flat: high gain 1/8
        move    a,x:(r7+$18)
        move    a,x:(r7+$1d)
        move    #>$1,a
        move    a,x:(r7+$36)
        move    x:(r7+$00),a
        move    a,x:(r7+$06)
        move    x:(r6+$c),a
        and     #>$7f0000,a
        move    #>$010000,x0
        cmp     x0,a
        tgt     x0,a
        move    a,x:(r7+$03)
        move    a,b
        move    #>$3fe,a                ; 1024 stages: modulo 1022 (1023 buckets)
        tst     b
        move    #>$ffe,x0
        tne     x0,a                    ; 4096: modulo 4094
        move    a,x:(r7+$04)
bbdry:
        rts

bbrun:
; ---- STGS: a change fades out, then clears ---------------------------------
        move    x:(r6+$c),a
        and     #>$7f0000,a
        move    #>$010000,x0
        cmp     x0,a
        tgt     x0,a
        move    x:(r7+$03),x0
        cmp     x0,a
        beq     bbsame
        move    x:(r7+$02),b
        tst     b
        bne     bbsame
        move    #>$10,b
        move    b,x:(r7+$02)
bbsame:
        move    x:(r7+$02),b
        tst     b
        beq     bbnofade
        sub     #>$1,b
        move    b,x:(r7+$02)
        bne     bbfading
        move    #>$10,b
        move    b,x:(r7+$01)
bbfading:
        clr     a
        bra     bbmixdone
bbnofade:
; MIX: 127 is the wet alone, every other value value/128
        move    x:(r6+$5),a
        and     #>$7f0000,a
        move    #>$7f0000,x0
        cmp     x0,a
        bne     bbmixdone
        move    #>$7fffff,a
bbmixdone:
        move    a,x:(r7+$1b)
        move    x:(r6+$1),a
        and     #>$7f0000,a
        move    a,x:(r7+$1a)
; ---- TONE: u = |value-64|/64, gains / 8 from cubic fits of 10^(+-0.45u) ----
        move    x:(r6+$3),a
        and     #>$7f0000,a
        move    #>$400000,x0
        sub     x0,a
        move    a,b                     ; sign of value-64
        abs     a
        asl     a
        move    a,x0                    ; u (127 apart: 1.0 saturates)
        move    #>$04e6be,y0
        mpy     y0,x0,a
        add     #>$076111,a
        move    a,y0
        mpy     y0,x0,a
        add     #>$10ca1e,a
        move    a,y0
        mpy     y0,x0,a
        move    a,y1                    ; pg = (10^(0.45u) - 1) / 8
        move    #>$fe252d,y0
        mpy     y0,x0,a
        add     #>$0802ab,a
        move    a,y0
        mpy     y0,x0,a
        add     #>$ef836f,a
        move    a,y0
        mpy     y0,x0,a
        move    a,x1                    ; pc = (10^(-0.45u) - 1) / 8
        tst     b
        blt     bbtneg
        move    #>$100000,a             ; treble: high = 1 + pg, low = 1 + pc
        add     y1,a
        move    a,x:(r7+$1d)
        move    x1,a
        sub     y1,a
        move    a,x:(r7+$1c)
        clr     a
        move    a,x:(r7+$1e)
        bra     bbtdone
bbtneg:
        move    #>$100000,a             ; low-mid peak: flat plus pg * bandpass
        move    a,x:(r7+$1d)
        clr     a
        move    a,x:(r7+$1c)
        move    y1,x:(r7+$1e)
bbtdone:
; ---- FDBK and TONE glide 1/16 a call (~256 samples); MIX glides per sample
        move    x:(r7+$1a),a
        move    x:(r7+$15),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    a,x:(r7+$15)
        move    x:(r7+$1c),a
        move    x:(r7+$17),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    a,x:(r7+$17)
        move    x:(r7+$1d),a
        move    x:(r7+$18),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    a,x:(r7+$18)
        move    x:(r7+$1e),a
        move    x:(r7+$19),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    a,x:(r7+$19)
; ---- FRZ h = value/128: below 127 the input fades out of the line by h and
; FDBK goes h of the way up to sustain, (127/128) / TONE's peak gain, never
; down (an oscillating loop keeps its FDBK and LIM its level); into y1 for
; LIM. At 127 the line loops its own buckets exactly
        move    x:(r6+$2),a
        and     #>$7f0000,a
        move    a,x:(r7+$39)
        clr     b
        move    #>$1,x1
        move    #>$7f0000,x0
        cmp     x0,a
        teq     x1,b
        move    b,x:(r7+$3a)
        move    x:(r7+$17),a            ; (low - high) / 8
        move    x:(r7+$18),b            ; high / 8
        add     b,a                     ; low / 8
        cmp     b,a
        tlt     b,a
        move    x:(r7+$19),x0           ; peak / 8
        add     x0,a
        move    a,x0                    ; G / 8 = (max(low, high) + peak) / 8, 1/8..0.36
        move    #>$0fe000,a             ; (127/128) / 8
        andi    #$fe,ccr
        do      #$18,>bbfrzdv           ; do, not rep: stock never holds interrupts off
        div     x0,a
bbfrzdv:
        move    a0,y0                   ; sustain
        move    x:(r7+$15),b            ; FDBK
        move    y0,a
        sub     b,a
        move    #0,y0
        tst     a
        tlt     y0,a                    ; never down
        move    a,y0
        move    x:(r7+$39),x0           ; h
        mpy     y0,x0,a
        add     b,a
        move    a,y1                    ; FDBK + h max(0, sustain - FDBK)
; ---- LIM (page-2 slot 7, $c bits 8-15): the feedback governor. Above
; T = 2^(-3.5v/127) (0: 1, off; 127: 2^-3.5, BBD08's 96) the expander's
; envelope scales FDBK by (T/env)^2, so a self-oscillating loop settles near
; T, even dB a value.
; Halves: T/2 against $0d = env/2.
        move    x:(r6+$c),a
        and     #>$007f00,a
        asl     #$8,a,a
        move    a,x0                    ; v/128
        move    #>$386ffc,y0            ; 3.5 * 128 / (127 * 8)
        mpy     y0,x0,a                 ; e/8, e = 3.5v/127 = 0..3.5
        bsr     bbexp2                  ; T/2 = 2^-e / 2
        move    a,x0                    ; T/2
        move    x:(r7+$0d),b            ; env/2
        cmp     x0,b
        ble     bblimok
        move    b,x1
        move    x0,a                    ; a clean load: a0 = 0, T < env
        andi    #$fe,ccr
        do      #$18,>bblimdv           ; do, not rep: stock never holds interrupts off
        div     x1,a
bblimdv:
        move    a0,x0                   ; T / env
        mpy     x0,x0,a
        move    a,x0
        mpy     x0,y1,a
        move    a,y1                    ; FDBK (T/env)^2
bblimok:
        move    y1,x:(r7+$3f)
; ---- FREQ: the bandpass at 400 * 5^(v/127) Hz, Q 1.5, unity peak: b0/2, -a1/2,
; -a2/2 from polynomials in u = v/128, gliding 1/16 a call like TONE ----------
        move    x:(r6+$4),a
        and     #>$7f0000,a
        move    a,x0                    ; u
        move    #>$0135b9,y0
        mpy     y0,x0,a
        add     #>$013040,a
        move    a,y0
        mpy     y0,x0,a
        add     #>$01f499,a
        move    a,y0
        mpy     y0,x0,a
        add     #>$013094,a
        move    a,y1                    ; the target
        move    x:(r7+$3c),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    x:(r7+$36),b            ; snap: straight to the target
        tst     b
        tne     y1,a
        move    a,x:(r7+$3c)
        move    #>$fb82f5,y0
        mpy     y0,x0,a
        add     #>$00c49c,a
        move    a,y0
        mpy     y0,x0,a
        add     #>$faa62b,a
        move    a,y0
        mpy     y0,x0,a
        add     #>$fbc05d,a
        move    a,y0
        mpy     y0,x0,a
        add     #>$7d6790,a
        move    a,y1                    ; the target
        move    x:(r7+$3d),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    x:(r7+$36),b            ; snap: straight to the target
        tst     b
        tne     y1,a
        move    a,x:(r7+$3d)
        move    #>$026b6a,y0
        mpy     y0,x0,a
        add     #>$026080,a
        move    a,y0
        mpy     y0,x0,a
        add     #>$03e929,a
        move    a,y0
        mpy     y0,x0,a
        add     #>$c26131,a
        move    a,y1                    ; the target
        move    x:(r7+$3e),b
        sub     b,a
        asr     #$4,a,a
        add     b,a
        move    x:(r7+$36),b            ; snap: straight to the target
        tst     b
        tne     y1,a
        move    a,x:(r7+$3e)
; ---- PRE (slot 9, $d bits 8-15) and POST (slot 10, $e knob): OFF/ON for the
; fixed 150 Hz 2-pole HPFs (coefficients written by init)
        move    x:(r6+$d),a
        and     #>$007f00,a
        move    a,x:(r7+$59)            ; PRE on
        move    x:(r6+$e),a
        and     #>$7f0000,a
        move    a,x:(r7+$5a)            ; POST on
; ---- TIME: P16 = A + B * value / 128 ---------------------------------------
        move    x:(r6),a
        and     #>$7f0000,a
        move    a,x0
        move    #>$34162c,y1
        mpy     x0,y1,a
        move    #>$113a00,x0
        add     x0,a
        move    a,x:(r7+$1f)
        move    x:(r7+$36),b
        tst     b
        beq     bbsnapped
        move    a,x:(r7+$07)
bbsnapped:
; ---- coefficients for this call's clock: K = tan(pi / (3 P)) ---------------
        move    x:(r7+$07),x0
        move    #>$0860a9,a             ; pi / 48
        andi    #$fe,ccr
        do      #$18,>bbdivk            ; do, not rep: stock never holds interrupts off
        div     x0,a
bbdivk:
        move    a0,x0                   ; theta = pi / (48 P16)
        mpy     x0,x0,a
        move    a,y1                    ; theta^2
        move    #>$02cc9f,y0
        mpy     y1,y0,a
        add     #>$06e86f,a
        move    a,y0
        mpy     y1,y0,a
        add     #>$111111,a
        move    a,y0
        mpy     y1,y0,a
        add     #>$2aaaab,a
        move    a,y0
        mpy     y1,y0,a
        move    a,y0
        mpy     y0,x0,a
        add     x0,a                    ; K = tan(theta), series to theta^9
        move    a,x:(r7+$37)
        move    a,x0
        mpy     x0,x0,a
        move    a,x:(r7+$38)
        move    x:(r7+$00),a
        move    #>$2000,x0
        add     x0,a
        move    a,r2                    ; the coefficients, for the loop
        move    #>$1,x1                 ; one section a call ...
        move    x:(r7+$36),b
        tst     b
        beq     bbrot
        clr     b
        move    b,x:(r7+$36)
        move    b,x:(r7+$3b)
        move    #>$9,x1                 ; ... or all nine from 0 after a reset
; one of the nine sections follows the clock each call (all nine in 144
; samples); after a reset all nine at once
bbrot:
        do      x1,>bbrend
        move    x:(r7+$3b),b            ; section index 0..8
        move    b,a
        asl     #$2,a,a
        add     b,a                     ; 5 words a section ...
        move    a,y0
        move    #>$2,x0
        sub     x0,a
        move    a,x1
        move    y0,a
        move    #>$5,x0
        cmp     x0,b
        tge     x1,a                    ; ... less the real pole's 2 past it
        move    r2,x0
        add     x0,a
        move    a,r5
        move    r7,r4                   ; (r7+$40 is past lua's +-63)
        move    #>$40,n4
        move    (r4)+n4
        move    b,n4
        move    x:(r4+n4),y1            ; 1/(2Q)
        move    #>$4,x0
        cmp     x0,b
        beq     bbrpole
        bsr     bbsect
        bra     bbrjoin
bbrpole:
        bsr     bbpole
bbrjoin:
        move    x:(r7+$3b),b
        move    #>$1,x0
        add     x0,b
        move    #>$9,x0
        cmp     x0,b
        move    #>$0,x1
        tge     x1,b
        move    b,x:(r7+$3b)
bbrend:
bbcoefs:
        lua     (r2+$35),r5             ; the FREQ bandpass into Y for the loop:
        move    x:(r7+$3c),a            ; b0/2 0 -b0/2 -a1/2 -a2/2
        move    a,y:(r5)+
        clr     b
        move    b,y:(r5)+
        neg     a
        move    a,y:(r5)+
        move    x:(r7+$3d),a
        move    a,y:(r5)+
        move    x:(r7+$3e),a
        move    a,y:(r5)+
; ---- the sample loop -------------------------------------------------------
        move    x:(r7+$06),r4
        move    x:(r7+$04),m4
        move    #>$1,n0
        move    #>$ffffff,m3
        move    r7,b
        move    #>$49,x0
        add     x0,b
        move    b,r3                    ; r7 + $49: the HPF states, past lua's +63
        do      n7,>bbend
; glides: P (20 ms) and MIX (1/32)
        move    x:(r7+$1f),a
        move    x:(r7+$07),b
        sub     b,a
        move    a,x0
        move    #>$2522,y0
        mac     y0,x0,b
        move    b,x:(r7+$07)
        move    x:(r7+$1b),a
        move    x:(r7+$16),b
        sub     b,a
        asr     #$5,a,a
        add     b,a
        move    a,x:(r7+$16)
; mono / 8
        move    x:(r0),b
        move    x:(r0+n0),x0
        add     x0,b
        asr     #$4,b,b
        move    x:(r7+$59),a            ; PRE: the HPF on mono/8, skipped when OFF
        tst     a
        beq     bbpreoff
        move    b,x0
        move    r3,r1
        lua     (r2+$30),r5
        bsr     bbhsec
        move    x0,b
bbpreoff:
        move    b,x0
        move    x:(r7+$39),y0           ; FRZ h: the input fades out of the line
        mac     -y0,x0,b
; tone on the previous wet/2: the unity-peak FREQ bandpass (DF1 from Y, b1 = 0,
; b2 = -b0), then the 200 Hz split
        move    x:(r7+$35),x0
        lua     (r7+$11),r1
        lua     (r2+$35),r5
        move    x:(r1)+,x1      y:(r5)+,y0
        mpy     y0,x0,a         x:(r1)-,y1
        move    x0,x:(r1)+      y:(r5)+,y0
        mac     x1,y0,a         x1,x:(r1)+      y:(r5)+,y0
        mac     y1,y0,a         x:(r1)+,x1      y:(r5)+,y0
        mac     x1,y0,a         x:(r1)-,x1      y:(r5)+,y0
        mac     x1,y0,a
        asl     a
        move    x:(r1),x1
        move    a,x:(r1)+
        move    x1,x:(r1)+
        move    a,y1                    ; bp
        move    x:(r7+$10),x1
        move    x1,a
        move    #>$03988d,y0
        mac     y0,x0,a
        mac     -x1,y0,a
        move    a,x:(r7+$10)
        move    a,x1                    ; l
        move    x:(r7+$17),y0
        mpy     x1,y0,a                 ; (low - high) * l
        move    x:(r7+$18),y0
        mac     y0,x0,a                 ; + high * w
        move    x:(r7+$19),x0
        mac     x0,y1,a                 ; + peak * bp: T = tone / 16
        move    a,x0
        move    x:(r7+$3f),y0           ; FDBK after LIM
        mpy     y0,x0,a
        asl     a
        add     b,a                     ; x / 8
        move    #>$300000,x0            ; Pade range: |x| <= 3
        cmp     x0,a
        tgt     x0,a
        move    #>$d00000,x0
        cmp     x0,a
        tlt     x0,a
        asl     a
        move    a,x0                    ; xs = x / 4
; the compressor: q/2 = N / D, N = 27/128 xs + xs^3/8 (Pade numerator / 512),
; D = (27/128 + 9/8 xs^2) * (avg + 5e-6)
        mpy     x0,x0,a
        move    a,y1
        mpy     x0,y1,b
        asr     #$3,b,b
        move    #>$1b0000,y0
        mac     y0,x0,b                 ; N, full precision
        move    a,y0
        asr     #$3,a,a
        add     y0,a
        add     #>$1b0000,a
        move    a,x1                    ; 27/128 + 9/8 xs^2
        move    x:(r7+$0c),a
        abs     a
        move    x:(r7+$0b),y1
        sub     y1,a
        move    a,x0
        move    #>$004a23,y0
        move    y1,a
        mac     y0,x0,a
        move    a,x:(r7+$0b)            ; avg += (|q[n-1]| - avg) / 442
        add     #>$00002a,a
        move    a,y0
        mpy     x1,y0,a
        move    a,x0                    ; D
        move    b,y1                    ; N's sign
        abs     b
        move    x0,a
        sub     #>$1,a
        move    a,y0
        cmp     y0,b
        tgt     y0,b                    ; |N| >= D clips q at +-2
        andi    #$fe,ccr
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        div     x0,b
        move    b0,y0
        move    y0,a
        neg     a
        move    y1,b                    ; N's sign
        tst     b
        tpl     y0,a
        move    a,x:(r7+$0c)
        move    a,x0                    ; q / 2
; anti-alias: four DF1 sections, coefficients halved, from Y
        lua     (r7+$20),r1
        move    r2,r5
        move    x:(r1)+,x1      y:(r5)+,y0
        mpy     y0,x0,a         x:(r1)-,y1
        move    x0,x:(r1)+      y:(r5)+,y0
        mac     x1,y0,a         x1,x:(r1)+      y:(r5)+,y0
        mac     y1,y0,a         x:(r1)+,x1      y:(r5)+,y0
        mac     x1,y0,a         x:(r1)-,x1      y:(r5)+,y0
        mac     x1,y0,a
        asl     a
        move    a,x0
        move    x:(r1)+,x1      y:(r5)+,y0
        mpy     y0,x0,a         x:(r1)-,y1
        move    x0,x:(r1)+      y:(r5)+,y0
        mac     x1,y0,a         x1,x:(r1)+      y:(r5)+,y0
        mac     y1,y0,a         x:(r1)+,x1      y:(r5)+,y0
        mac     x1,y0,a         x:(r1)-,x1      y:(r5)+,y0
        mac     x1,y0,a
        asl     a
        move    a,x0
        move    x:(r1)+,x1      y:(r5)+,y0
        mpy     y0,x0,a         x:(r1)-,y1
        move    x0,x:(r1)+      y:(r5)+,y0
        mac     x1,y0,a         x1,x:(r1)+      y:(r5)+,y0
        mac     y1,y0,a         x:(r1)+,x1      y:(r5)+,y0
        mac     x1,y0,a         x:(r1)-,x1      y:(r5)+,y0
        mac     x1,y0,a
        asl     a
        move    a,x0
        move    x:(r1)+,x1      y:(r5)+,y0
        mpy     y0,x0,a         x:(r1)-,y1
        move    x0,x:(r1)+      y:(r5)+,y0
        mac     x1,y0,a         x1,x:(r1)+      y:(r5)+,y0
        mac     y1,y0,a         x:(r1)+,x1      y:(r5)+,y0
        mac     x1,y0,a         x:(r1)-,x1      y:(r5)+,y0
        mac     x1,y0,a
        asl     a
        move    a,x0                    ; v
        move    x:(r1),x1
        move    x0,x:(r1)+
        move    x1,x:(r1)+
; the bucket line: a tick when the clock time passes P
        move    x:(r7+$09),x1           ; v[n-1]
        move    x0,x:(r7+$09)
        move    x:(r7+$08),a
        move    x:(r7+$07),y1
        cmp     y1,a
        ble     bbnotick
        sub     y1,a
        move    a,x:(r7+$08)
        asl     #$4,a,a
        move    a,y0                    ; frac: samples past the clock edge
        mpy     y0,x0,b
        add     x1,b
        mac     -x1,y0,b                ; the input at the edge
        move    y:(r4),x0               ; the bucket that went in stages-1 ticks ago
        move    x:(r7+$3a),a
        tst     a
        tne     x0,b                    ; FRZ 127: the old bucket, exactly
        move    b,y:(r4)+
        move    x0,a
        mpy     x0,x0,b
        move    b,y1
        mpy     x0,y1,b
        asr     #$3,b,b
        sub     b,a
        move    #>$018acc,y0
        mac     -y1,y0,a
        add     #>$040000,a             ; v - v^2/83 - v^3/8 + 1/32 at half scale
        move    x:(r7+$05),x0
        move    #>$0cb306,y0
        mpy     y0,x0,b         #0,x1
        add     x,b             #>$6ef35f,y0
        move    #0,y1
        add     y,b
        move    b0,x0
        move    x0,x:(r7+$05)
        move    #>$000a5b,y0
        mac     y0,x0,a
        move    a,x:(r7+$0a)
bbnotick:
        move    x:(r7+$08),a
        add     #>$080000,a
        move    a,x:(r7+$08)
; reconstruction: the real pole, then four DF1 sections
        move    x:(r7+$0a),x0
        move    x:(r7+$2a),x1
        move    x0,x:(r7+$2a)
        move    y:(r5)+,y0
        mpy     y0,x0,a         y:(r5)+,y0
        mac     x1,y0,a         y:(r5)+,y0
        move    x:(r7+$2b),x1
        mac     x1,y0,a
        asl     a
        move    a,x0
        move    (r1)+
        move    x:(r1)+,x1      y:(r5)+,y0
        mpy     y0,x0,a         x:(r1)-,y1
        move    x0,x:(r1)+      y:(r5)+,y0
        mac     x1,y0,a         x1,x:(r1)+      y:(r5)+,y0
        mac     y1,y0,a         x:(r1)+,x1      y:(r5)+,y0
        mac     x1,y0,a         x:(r1)-,x1      y:(r5)+,y0
        mac     x1,y0,a
        asl     a
        move    a,x0
        move    x:(r1)+,x1      y:(r5)+,y0
        mpy     y0,x0,a         x:(r1)-,y1
        move    x0,x:(r1)+      y:(r5)+,y0
        mac     x1,y0,a         x1,x:(r1)+      y:(r5)+,y0
        mac     y1,y0,a         x:(r1)+,x1      y:(r5)+,y0
        mac     x1,y0,a         x:(r1)-,x1      y:(r5)+,y0
        mac     x1,y0,a
        asl     a
        move    a,x0
        move    x:(r1)+,x1      y:(r5)+,y0
        mpy     y0,x0,a         x:(r1)-,y1
        move    x0,x:(r1)+      y:(r5)+,y0
        mac     x1,y0,a         x1,x:(r1)+      y:(r5)+,y0
        mac     y1,y0,a         x:(r1)+,x1      y:(r5)+,y0
        mac     x1,y0,a         x:(r1)-,x1      y:(r5)+,y0
        mac     x1,y0,a
        asl     a
        move    a,x0
        move    x:(r1)+,x1      y:(r5)+,y0
        mpy     y0,x0,a         x:(r1)-,y1
        move    x0,x:(r1)+      y:(r5)+,y0
        mac     x1,y0,a         x1,x:(r1)+      y:(r5)+,y0
        mac     y1,y0,a         x:(r1)+,x1      y:(r5)+,y0
        mac     x1,y0,a         x:(r1)-,x1      y:(r5)+,y0
        mac     x1,y0,a
        asl     a
        move    a,x0
        move    x:(r1),x1
        move    x0,x:(r1)+
        move    x1,x:(r1)+
; 10 Hz DC blocker, then the expander: wet = y * LP10ms|y|
        move    x0,a
        move    x:(r7+$0e),x1
        sub     x1,a
        move    x:(r7+$0f),y1
        move    #>$7fd150,y0
        mac     y1,y0,a
        move    x0,x:(r7+$0e)
        move    a,x:(r7+$0f)
        move    a,x1                    ; y / 2
        abs     a
        move    x:(r7+$0d),y1
        sub     y1,a
        move    a,x0
        move    #>$004a23,y0
        move    y1,a
        mac     y0,x0,a
        move    a,x:(r7+$0d)
        move    a,y0
        mpy     x1,y0,a
        asl     a
        rnd     a                       ; a sub-LSB product of silence is 0, never -1
        move    a,x:(r7+$35)            ; wet / 2: FDBK reads it unlimited
        move    x:(r7+$5a),b            ; POST: the HPF on wet/2, after FDBK's tap
        tst     b
        beq     bbpstoff
        move    a,x0
        lua     (r3+$4),r1
        lua     (r2+$30),r5
        bsr     bbhsec
        move    x0,a
bbpstoff:
; the output stage: linear to half scale, then 0.25 + e - e^2 at half scale
; (e = |wet/2| - 0.25, at most 0.5): exactly full scale, flat, from 1.5
        move    a,y1
        abs     a
        move    a,x1                    ; |wet/2|
        sub     #>$200000,a
        move    #>$400000,x0
        cmp     x0,a
        tgt     x0,a
        move    a,x0                    ; e
        mpy     -x0,x0,a
        add     x0,a
        add     #>$200000,a
        move    a,x0                    ; 0.25 + e - e^2
        move    x1,a
        cmp     #>$200000,a
        tge     x0,a
        move    a,x0
        neg     a
        move    y1,b
        tst     b
        tpl     x0,a
        move    a,x1                    ; limited wet / 2
; MIX m: the wet rises to unity by 64 with the dry whole, then the dry fades
; out by 127. out = dry - k dry + g wet, g = min(1, 2m), k = max(0, 2m - 1);
; a sum past full scale saturates in the store
        move    x:(r7+$16),a
        asl     a
        move    a,y0                    ; g: the move limits 2m at 1
        move    #>$400000,x0
        sub     x0,a
        sub     x0,a                    ; 2m - 1
        move    #0,x0
        tst     a
        tlt     x0,a
        move    a,y1                    ; k
        move    x:(r0),x0
        move    x0,a
        mac     -x0,y1,a
        mac     x1,y0,a
        mac     x1,y0,a
        move    a,x:(r0)+
        move    x:(r0),x0
        move    x0,a
        mac     -x0,y1,a
        mac     x1,y0,a
        mac     x1,y0,a
        move    a,x:(r0)+
bbend:
        nop
        move    r4,x:(r7+$06)
        move    #>$ffffff,m4
        move    #>$ffffff,m3
        rts

; one DF1 section in the sample loop, no control transfer: x0 in and out,
; r1 -> x1 x2 y1 y2, r5 -> b0/2 b1/2 b2/2 -a1/2 -a2/2
bbhsec:
        move    x:(r1)+,x1      y:(r5)+,y0
        mpy     y0,x0,a         x:(r1)-,y1
        move    x0,x:(r1)+      y:(r5)+,y0
        mac     x1,y0,a         x1,x:(r1)+      y:(r5)+,y0
        mac     y1,y0,a         x:(r1)+,x1      y:(r5)+,y0
        mac     x1,y0,a         x:(r1)-,x1      y:(r5)+,y0
        mac     x1,y0,a
        asl     a
        rnd     a                       ; round, not truncate: the poles near DC
        move    a,x0                    ; amplify a truncation bias by ~2,500
        move    x:(r1),x1
        move    x0,x:(r1)+
        move    x1,x:(r1)+
        rts

; one Butterworth section's DF1 coefficients, halved, into y:(r5)+:
; y1 = 1/(2Q); K, K^2 in $37, $38
bbsect:
        move    x:(r7+$37),x0
        mpy     x0,y1,a
        move    a,x1                    ; K/(2Q)
        asr     a
        move    x:(r7+$38),b
        asr     #$2,b,b
        add     b,a
        move    #>$200000,y0
        add     y0,a
        move    a,x0                    ; d/4 = (1 + K/Q + K^2) / 4
        move    #>$100000,a
        andi    #$fe,ccr
        do      #$18,>bbdivs            ; do, not rep: stock never holds interrupts off
        div     x0,a
bbdivs:
        move    a0,y0                   ; 1 / (2d)
        move    x:(r7+$38),x0
        mpy     y0,x0,a
        move    a,y:(r5)+               ; b0/2
        move    a,b
        asl     b
        move    b,y:(r5)+               ; b1/2
        move    a,y:(r5)+               ; b2/2
        move    x:(r7+$38),a
        asr     a
        move    #>$400000,b
        sub     a,b
        asl     b
        move    b,x0                    ; 1 - K^2
        mpy     y0,x0,a
        asl     a
        move    a,y:(r5)+               ; -a1/2 = (1 - K^2) / d
        move    #>$400000,b
        sub     x1,b
        move    x:(r7+$38),a
        asr     a
        add     a,b
        move    b,x0                    ; (1 - K/Q + K^2) / 2: past 1 at high Q, fast clock
        mpy     -y0,x0,a
        asl     a
        move    a,y:(r5)+               ; -a2/2
        rts

; the real pole's DF1 coefficients, halved, into y:(r5)+: b0/2 b1/2 -a1/2
bbpole:
        move    x:(r7+$37),a
        asr     #$2,a,a
        move    #>$200000,y0
        add     y0,a
        move    a,x0                    ; (1 + K) / 4
        move    #>$100000,a
        andi    #$fe,ccr
        do      #$18,>bbdivp            ; do, not rep: stock never holds interrupts off
        div     x0,a
bbdivp:
        move    a0,y0                   ; 1 / (2 (1 + K))
        move    x:(r7+$37),x0
        mpy     y0,x0,a
        move    a,y:(r5)+
        move    a,y:(r5)+
        move    x:(r7+$37),a
        asr     a
        move    #>$400000,b
        sub     a,b
        asl     b
        move    b,x0                    ; 1 - K
        mpy     y0,x0,a
        move    a,y:(r5)+
        rts

; 2^-e / 2 for e/8 in a (e = 0..8): the fraction by a cubic, the integer by a shift
bbexp2:
        move    a1,b
        asr     #$14,b,b
        move    b1,x1                   ; n = the integer part of e
        asl     #$3,a,a
        and     #>$7fffff,a
        move    a1,x0                   ; f = the fraction of e
        move    #>$fd78ab,y0
        mpy     y0,x0,a
        add     #>$0ec20c,a
        move    a,y0
        mpy     y0,x0,a
        add     #>$d3c568,a
        move    a,y0
        mpy     y0,x0,a
        move    #>$3ffe57,y0
        add     y0,a                    ; 2^-f / 2
        asr     x1,a,a
        rts
