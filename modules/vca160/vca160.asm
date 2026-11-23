; ---------------------------------------------------------------------------
; VCA160 -- the dbx 160 compressor/limiter (1976), a per-track insert.
;
; GENERATED (do not edit) from vca160.tmpl.asm by generate_asm.py (constants from
; manifest.py). Edit the template, then: python3 modules/vca160/generate_asm.py
;
; Insert contract: frames in place at x:(r0)/x:(r0+n0), knobs from r6,
; state in this instance's r7 block. In the shared window it reads one word,
; KEYBUS's mean square of the track its KEY names (X:$037f68 + track).
;
; ---- the 160 (schematic + manual; modules/vca160/README.md) -----------------
;   ms   = (L^2 + R^2)/2, or KEY's block mean square from KEYBUS
;   S   += alpha (ms - S)            the RMS 208: tau = 34.7 ms (125 dB/s)
;   L    = log2 S / 32               clb + normf + LOG (transient's form)
;   over = L - T                     THRESHOLD, in mean-square bits / 32
;   oe   = max(over, 0)              HARD; OVER: (over + W/2)^2/(2W) inside the knee
;   g    = -oe k/2 + OUT             COMPRESSION k (ratio 1/(1 - k)); amplitude
;                                    bits / 32, clamped to -16 .. +4 bits
;   wet  = x 2^g                     the VCA: EXP mantissa, normf by the exponent
;   out  = dry + MIX (wet - dry)
; Below threshold at OUT 0 dB, g = 0 exactly and the wet path is bit-exact.
;
; ---- r7 slots ---------------------------------------------------------------
; per block: $00 T/32  $01 k/2  $02 OUT bits/32  $03 OverEasy flag  $04 KEY flag
;   $05 KEY's mean square (KEYBUS's word)  $06 MIX
; persistent, zeroed at init: $07 S high  $08 S low (48 bits)
; per sample scratch: $09 the shift count  $0a wet L  $0b wet R
;
; Every mpy and mac is x0,y1 / -x0,y1 / x0,x0 (the signed encodings). Every
; Tcc reads the tst or cmp directly above it with only moves between. No
; branch in the sample loop.
; ---------------------------------------------------------------------------

init:
        clr     a
        move    a,x:(r7+$07)            ; the detector, empty
        move    a,x:(r7+$08)
        rts

proc:
        move    #>$ffffff,m5
        move    #>$fab1e0,r4            ; the P table: LOG, EXP
; ===========================================================================
; PER BLOCK
; ===========================================================================
; ---- THRS: T/32 = THLO + x THSPAN (x = knob * 128/127, below 1.0) ------------
        move    x:(r6+$0),a
        and     #>$7fffff,a
        move    a,x0
        move    #>$010204,y1
        mac     x0,y1,a
        move    a,x0                    ; x
        move    #>$427046,y1
        move    #>$bd8fba,a
        mac     x0,y1,a
        move    a,x:(r7+$00)            ; T/32
; ---- RATI: k/2, 0 .. 0.496 over 0..100, then 0.5 .. 1.0 over 101..127 -------
        move    x:(r6+$1),a
        and     #>$7fffff,a
        move    a,x0                    ; w = knob/128
        move    #>$5143bf,y1
        mpy     x0,y1,b                 ; the 160: k/2 = w K1
        move    b,y0
        move    #>$640000,y1
        sub     y1,a                    ; w - 100/128
        move    a,x0
        move    #>$4bda13,y1
        mpy     x0,y1,a                 ; (w - 100/128) K2/4
        asl     #$2,a,a
        add     #>$400000,a             ; the 160A: 1/2 + (w - 100/128) K2
        move    a,x1
        move    x:(r6+$1),a
        and     #>$7fffff,a
        move    #>$640000,y1
        cmp     y1,a                    ; w - 100/128
        move    x1,a                    ; (moves keep the flags)
        tle     y0,a                    ; w <= 100/128: the 160's k
        move    a,x:(r7+$01)            ; k/2 (limited below 1.0)
; ---- OUT: amplitude bits/32 = (w - 1/2) OUTK ---------------------------------
        move    x:(r6+$2),a
        and     #>$7fffff,a
        sub     #>$400000,a
        move    a,x0
        move    #>$1ac8e1,y1
        mpy     x0,y1,a
        move    a,x:(r7+$02)
; ---- KNEE (page 2, slot 6: x:(r6+$c) bits 16-23): 1 = OverEasy ---------------
        move    x:(r6+$c),a
        and     #>$7f0000,a
        move    a1,x:(r7+$03)           ; 0 = HARD, anything else = OVER
; ---- MIX: value/128, 127 pinned to full scale ----------------------------------
        move    x:(r6+$4),a
        and     #>$7f0000,a
        move    #$7f,x0                 ; (short immediate: bits 23-16)
        cmp     x0,a
        move    #>$7fffff,x0
        teq     x0,a
        move    a,x:(r7+$06)
; ---- KEY: OFF, or T1..T8 -> that track's mean-square word on KEYBUS ------------
; t = KEY - 1; KEYBUS rewrites X:$037f68 + t every block with track t's block
; mean square, on either core, and both cores read all eight. A KEY of 0 or
; above 8 is OFF (a Part saved with another effect here can hold any byte).
        move    x:(r6+$3),a
        and     #>$7f0000,a
        asr     #$10,a,a                ; KEY 0..127
        move    a1,x1
        clr     b                       ; b = 0 BEFORE the compares
        move    x1,a
        sub     #$1,a                   ; KEY - 1
        move    #>$000001,x0
        tge     x0,b                    ; KEY >= 1: on
        move    x1,a
        sub     #$9,a                   ; KEY - 9
        move    #0,x0
        tge     x0,b                    ; KEY >= 9: off
        move    b1,x:(r7+$04)
        move    x1,a
        sub     #$1,a
        and     #$7,a                   ; t, 0..7 (when off, any word)
        move    a1,x1                   ; a1 straight out: the and left a2 stale
        move    x1,a
        add     #>$037f68,a             ; KEYBUS's mean-square word for track t
        move    a1,r1
        nop                             ; two moves between writing r1 and using it
        nop
        move    x:(r1),x0               ; the key's mean square
        move    x0,x:(r7+$05)
        move    #$1,n0                  ; (short immediate, stock's own form)
; ===========================================================================
; THE SAMPLE LOOP
; ===========================================================================
        do      n7,>dbc_end
; ---- ms: (L^2 + R^2)/2, or KEY's word ----------------------------------------------
        move    x:(r0),x0
        mpy     x0,x0,a
        move    x:(r0+n0),x0
        mac     x0,x0,a
        asr     #$1,a,a
        move    a,x1                    ; ms, limited below 1.0
        move    x:(r7+$04),b
        move    x:(r7+$05),x0
        tst     b
        move    x1,a
        tne     x0,a                    ; KEY on: the bus word
; ---- the RMS detector: S += alpha (ms - S), 48 bits ------------------------------
        move    x:(r7+$07),y0
        sub     y0,a                    ; ms - S
        move    a,x0
        move    #>$001561,y1
        mpy     x0,y1,b
        move    y0,a                    ; S, still in y0 (a0 = 0, as the load)
        move    x:(r7+$08),a0
        add     b,a                     ; S'
        move    #>$000001,x0            ; the floor: one LSB of the high word
        cmp     x0,a                    ; (-69 dB, under every threshold)
        tlt     x0,a
        move    a1,x:(r7+$07)
        move    a0,x:(r7+$08)
; ---- L = log2 S / 32 ------------------------------------------------------------------
        clb     a,b
        normf   b1,a                    ; the mantissa m in [0.5, 1)
        move    b1,x:(r7+$09)           ; the exponent, parked
        move    r4,r5
        sub     #>$400000,a
        asl     #$1,a,a                 ; u = 2 (m - 1/2)
        move    a1,x1
        asr     #$12,a,a                ; idx = bits 22..18
        move    a1,n5
        move    x1,a
        and     #>$3ffff,a
        asl     #$5,a,a                 ; frac
        move    (r5)+n5
        move    a,x0
        move    p:(r5)+,y0              ; LOG[i]
        move    p:(r5),b                ; LOG[i+1]
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a                    ; log2(m)/32
        move    x:(r7+$09),b
        asl     #$12,b,b                ; e/32
        add     b,a                     ; L
; ---- over, the knee -----------------------------------------------------------------
        move    x:(r7+$00),x0
        sub     x0,a                    ; over = L - T
        move    a,x1                    ; over
; OverEasy: d = over + W/2 clamped to [0, W], soft = d^2/(2W)
        move    #>$06a4d4,x0
        add     x0,a
        move    #0,x0
        tmi     x0,a                    ; d < 0: 0
        move    #>$0d49a8,x0
        cmp     x0,a
        tgt     x0,a                    ; d > W: W
        move    a,x0
        mpy     x0,x0,a                 ; d^2
        move    a,x0
        move    #>$4d104d,y1
        mpy     x0,y1,a
        asl     #$3,a,a                 ; d^2 / (2W)
        move    a,y0
        move    x1,a
        move    #>$06a4d4,x0
        cmp     x0,a                    ; over - W/2
        move    y0,a                    ; inside or below the knee: the curve
        tgt     x1,a                    ; above it: over itself
        move    a,y0                    ; OverEasy's oe
; HARD: max(over, 0)
        move    x1,b
        move    #0,x0
        tst     b
        tmi     x0,b
        move    b,x0                    ; HARD's oe
        move    x:(r7+$03),a
        tst     a
        move    x0,a
        tne     y0,a                    ; KNEE OVER: OverEasy's
; ---- g = -oe k/2 + OUT, clamped -------------------------------------------------------
        move    a,x0
        move    x:(r7+$01),y1
        mpy     -x0,y1,a
        move    x:(r7+$02),x0
        add     x0,a
        move    #>$c00000,x0
        cmp     x0,a
        tlt     x0,a
        move    #>$100000,x0
        cmp     x0,a
        tgt     x0,a
        move    a,x1                    ; g, amplitude bits / 32
; ---- 2^g: n = floor(32 g), the EXP mantissa 2^f / 2 -----------------------------------
        move    r4,r5
        asr     #$12,a,a                ; n
        move    a1,b
        add     #$1,b
        neg     b                       ; -(n + 1): normf's count
        move    b1,x:(r7+$09)
        move    x1,a
        and     #>$3ffff,a              ; 32 g - n, as 18 bits
        move    a1,x1
        move    x1,a
        asr     #$d,a,a                 ; idx = top 5 bits
        add     #>$000021,a
        move    a1,n5
        move    x1,a
        and     #>$1fff,a
        asl     #$a,a,a                 ; frac
        move    (r5)+n5
        move    a,x0
        move    p:(r5)+,y0              ; EXP[i]
        move    p:(r5),b                ; EXP[i+1]
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a                    ; 2^f / 2, in [0.5, 1]
        move    a,y1                    ; the VCA's gain mantissa
; ---- the VCA, both channels -------------------------------------------------------------
        move    x:(r7+$09),b            ; the count, a clean load
        move    x:(r0),x0
        mpy     x0,y1,a
        normf   b1,a                    ; x 2^(n+1)
        move    a,x:(r7+$0a)            ; wet L, limited
        move    x:(r0+n0),x0
        mpy     x0,y1,a
        normf   b1,a
        move    a,x:(r7+$0b)            ; wet R
; ---- MIX, per channel ---------------------------------------------------------------------
        move    x:(r7+$06),y1
        move    x:(r0),b                ; dry L
        move    x:(r7+$0a),a
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)+
        move    x:(r0),b                ; dry R
        move    x:(r7+$0b),a
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)+
dbc_end:
        nop
        rts
