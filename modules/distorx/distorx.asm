; ---------------------------------------------------------------------------
; DISTORX -- the BOSS SD-1 (1981) and the Pro Co RAT (1978) in one insert.
;
; GENERATED (do not edit) from distorx.tmpl.asm by generate_asm.py (every constant comes
; from manifest.py, which computes it from the pedals' part values). Edit the
; template, then: python3 modules/distorx/generate_asm.py
;
; Insert contract: frames in place at x:(r0)/x:(r0+n0), knobs from r6,
; state in this instance's r7 block ($00..$3f, one-word displacements only).
; No bus, no buffers, no shared window.
;
; MODE (page 1, the sixth knob) picks the pedal: 0 OFF, 1 SD-1, 2 RAT, 3 TURBO.
; v8 (18 Oct 2026): OFF, the default, runs nothing (the frames pass untouched),
; so DISTORX can be put on a track live and faded in; the SD-1 at 1x like the
; RAT; a settled block (d = 0, MIX 127) writes the wet alone. All for core 1's
; budget on T1 (README "On the unit").
; The SD-1 path is the circuit of README "The SD-1" (manifest.py's constants).
; Shared callees carry its per-block decode (the knob stretch, the LN lookup,
; the TONE polynomials as a loop over a P table); the MODE fade multiplies MIX
; by (1 + d) and is MIX exactly when d = 0.
;
; ---- the MODE fade -----------------------------------------------------------
; d in [-1, 0] steps 1/128 a sample: towards -1 while the knob asks for
; another pedal, towards 0 otherwise. MIX x (1 + d) goes to the dry signal and
; back, 2.9 ms each way. At d = -1 with the knob on another pedal, the block
; zeroes every state slot ($12..$3c) and the new pedal starts from rest.
; $3b the pedal running (m << 16: 0 OFF, 1 SD-1, 2 RAT, 3 TURBO; init OFF)
; $30 v8: 1 = a settled block (d = 0, the knob's pedal on, MIX 127)   $3d d   $3e d's step this block   $3f the knob's
;
; ---- the SD-1's slots ------------------------------------------------------
; ($00..$3a, $3c; this file keeps every one of them)
;
; ---- the RAT, at the sample rate (twice it until 15 Oct 2026) ---------------
;   vp   = HP 7.2 Hz (in), 48-bit state         C1/R2, 1x
;   z    = 2x interpolation of vp               the SD-1's 11-tap halfband
;   the LM308 stage (dtx_rstage), volts/4; C4 left out (README):
;     c0 = c5 vh5 + c6 vh6                      so that v- = q vo + c0
;     vo = r vo1 + (1-th) r d1 + th W r (z - c0)  the integrator, implicit
;     vo within vo1 +- SRT (slew), then +-VSAT (the rails)
;     vm = q vo + c0;  d1 = W (z - vm) (a word: +-4 V, README)
;     vh5,6 += K5,6 (vm - vh5,6)                C5, C6 (48 bits)
;   the clipper node (dtx_rstage), volts/8:
;     vs = vo/2 - vh7                           C7's voltage out
;     u  = rho vs + s8 vh8 + s9 vh9             the node's drive (x Rp)
;     X/2 = |u| KX + C/2 = (U + 12)/256         U = u/N + k + ln k, -11..116
;     v  = u + sgn(u) (N k/8 - 16N omega(U)/128)   the diode law, exact
;     vh7 += K7 (vs - v);  vX = aD v + a8 vh8 + a9 vh9
;     vh8 = 2 vX - vh8;  g = GR8 (vX - vh9);  vh9 += K9 (vX - vh9)
;   out  = 2x decimation of g, HP 1.6 Hz (48-bit state), x LEVEL
;
; RAT r7 slots: per block
;   $00 Gi   $01 q   $02 c5 = (1-q) LAM   $03 c6 = (1-q)(1-LAM)   $04 r - 1
;   $05 (1-th) r   $06 th W r/64   $07 rho  $08 s8  $09 s9  $0a KX
;   $0b/$0c C/2 (48 bits)  $0d N k/8  $0e 8N  $0f aD  $10 LEVEL  $11 MIX
;   $12 a8   $13 a9
; per call scratch: $1b vm  $1c u, then v  $1d vs
; persistent: $1e vo  $1f d1  $28/$29 vh5  $2a/$2b vh6  $2c/$2d vh7  $2e vh8
;   $32/$33 vh9  $34 vin[n-1]  $35/$36 the input HP's 48-bit state
;   $37/$38 the output HP's 48-bit state  $3a g[n-1]
;   (v8: the halfbands are gone with the SD-1's 2x. Their slots: $20..$23 the
;   knob cache, $30 the settled-block flag; free $17..$1a $24..$27 $2f $31)
; per block parking: $14 $15 $1b $1c (the decode's own)
; registers through the RAT loop: r1 SRT/8  r2 -SRT/8  r3 VSAT  n3 -VSAT
;   (r1 and r2 the dispatcher reloads after proc; r3 and n3 the SD-1's too)
;   v10: n1 RK5  n2 RK6  n4 RK9 (a word a use), r4 on to OM + 6 x 16 (the loop's lookup);
;   the three loops (fading, calm d = 0, settled) share dtx_rstage: README "v10"
; ---------------------------------------------------------------------------

init:
        move    #>$ffffff,m3            ; linear: the clear walks r3
        move    r7,r3
        clr     a
        do      #$40,>dxzinit           ; do, not rep: interrupts stay serviced (tools/build/norep.py)
        move    a,x:(r3)+               ; every slot $00..$3f (verify_dirtystate)
dxzinit:
        move    #$80,x0                  ; d = -1, the pedal OFF ($3b = 0 from the clear): (short immediate: bits 23-16)
                                        ; a pedal chosen later switches in and fades in
        move    x0,x:(r7+$3d)
        rts

proc:
        move    #>$ffffff,m3            ; linear: the callees walk r3, the
        move    #>$ffffff,m4            ; tables r4/r5
        move    #>$ffffff,m5
        move    #>$fab1e0,r4            ; the P table: WF LN EXP TAPER TP OM MK
; ===========================================================================
; PER BLOCK, every MODE
; ===========================================================================
; ---- MODE: the knob's pedal, and the switch at the bottom of the fade ------
        move    x:(r6+$5),a
        and     #>$7f0000,a
        move    #$03,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        tgt     x0,a                    ; anything past TURB is TURB
        move    a1,x:(r7+$3f)           ; the knob's pedal
        move    x:(r7+$3d),a            ; d, a clean load
        move    #$80,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        bne     dtx_keep                ; still sounding: no switch
        move    x:(r7+$3b),a
        move    x:(r7+$3f),x0
        cmp     x0,a
        beq     dtx_keep                ; silent, and already that pedal
        move    r7,r3                   ; the switch: every state slot to zero
        move    #$12,n3
        move    (r3)+n3
        clr     a
        do      #$2b,>dxzswap           ; do, not rep
        move    a,x:(r3)+               ; $12..$3c
dxzswap:
        move    x:(r7+$3f),x0
        move    x0,x:(r7+$3b)           ; the new pedal
dtx_keep:
        move    x:(r7+$3b),a
        move    x:(r7+$3f),x0
        cmp     x0,a
        move    #$ff,a                   ; -1/128 a sample: fading out ... (short immediate: bits 23-16)
        move    #$01,x0                  ; ... +1/128: the knob's pedal is on (short immediate: bits 23-16)
        teq     x0,a
        move    a,x:(r7+$3e)
; ---- v8: OFF -- nothing runs, the frames (in place) pass untouched ----------
        move    x:(r7+$3b),a
        tst     a
        bne     dtx_on
        rts
dtx_on:
; ---- IN -> Gi = 2^(-2 + 4w)/4 (EXP, interpolated) ----------------------------
        move    x:(r6+$3),a
        and     #>$7fffff,a
        move    a,x0
        move    #>$000132,b
        bsr     dtx_tab
        move    a,x:(r7+$00)            ; Gi
; ---- MIX: value/128, 127 pinned to full scale (transient's) -------------------
        move    x:(r6+$4),a
        and     #>$7f0000,a
        move    #$7f,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        move    #>$7fffff,x0
        teq     x0,a
        move    a,x:(r7+$11)
; ---- v8: a settled block -- d = 0, the knob's pedal on, MIX 127: dtx_out
; writes the wet alone (MIX x (1 + d) would be 1 - 2^-23).
; A calm block (d = 0 and the step up: d stays 0 through the block) needs no fade
; arithmetic at all: $2f; settled is calm with MIX 127: $30.
        move    a1,y1                   ; MIX
        move    #$00,b                   ; (short immediate: bits 23-16)
        move    b1,x:(r7+$30)
        move    b1,x:(r7+$2f)
        move    x:(r7+$3d),a
        tst     a                       ; d = 0?
        bne     dtx_nofast
        move    x:(r7+$3e),a
        move    #$01,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a                    ; the step up (the knob's pedal on)?
        bne     dtx_nofast
        move    #>$000001,b
        move    b1,x:(r7+$2f)           ; calm
        move    y1,a
        move    #>$7fffff,x0
        cmp     x0,a                    ; MIX 127?
        bne     dtx_nofast
        move    b1,x:(r7+$30)           ; settled
dtx_nofast:
        move    #$1,n0                  ; (short immediate, stock's own form)
        move    x:(r7+$3b),a
        move    #$01,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        bne     dtx_rat
; ===========================================================================
; MODE 1: THE SD-1 (its per-block decode, then its loop)
; ===========================================================================
; ---- v8: the knobs as last decoded ($20 LEVL $21 TONE $22 DRIV, $23 = 1 when
; valid; the init and every switch clear it): the same three words, the same
; decode -- skip it. The words compared whole, LFO fractions included.
        move    x:(r7+$23),a
        tst     a
        beq     sod_dec
        move    x:(r6+$0),a
        move    x:(r7+$20),x0
        cmp     x0,a
        bne     sod_dec
        move    x:(r6+$1),a
        move    x:(r7+$21),x0
        cmp     x0,a
        bne     sod_dec
        move    x:(r6+$2),a
        move    x:(r7+$22),x0
        cmp     x0,a
        beq     sod_go
sod_dec:
        move    x:(r6+$0),x0
        move    x0,x:(r7+$20)
        move    x:(r6+$1),x0
        move    x0,x:(r7+$21)
        move    x:(r6+$2),x0
        move    x0,x:(r7+$22)
        move    #>$000001,x0
        move    x0,x:(r7+$23)
; ---- DRIV -> Rf/2^20 = R5 + x VR1 (x = knob * 128/127, capped at 1) ----------
        move    x:(r6+$2),a
        bsr     dtx_knob                ; x (limited below 1.0)
        move    #>$7a1200,y1
        move    #>$040740,a
        mac     x0,y1,a                 ; Rf_s
        move    a,x0
        move    x0,x:(r7+$39)
        move    #>$267b88,y1
        mpy     x0,y1,a                 ; G2 = Rf/R6 * 4/(N2 2^15)
        move    a,x:(r7+$01)
        asl     #$1,a,a
        move    a,x:(r7+$06)            ; G1 = 2 G2 (N1 = N2/2)
        move    #>$03bbdb,y1
        mpy     x0,y1,a                 ; k2 = Is Rf / N2
        move    a,x:(r7+$3a)
; ---- ln k2 / 16 = ln(Is/N2)/16 + ln(Rf)/16 (clb, normf, LN) ------------------
        move    x0,a                    ; Rf_s, a clean load
        clb     a,b                     ; b1 = floor(log2 Rf_s) + 1
        normf   b1,a                    ; m in [0.5, 1)
        move    b1,x:(r7+$37)           ; the exponent, parked
        bsr     dtx_ln                  ; ln(m)/16
        move    a,x1
        move    x:(r7+$37),b            ; the exponent, a clean load
        asl     #$12,b,b                ; e/32
        move    b,x0
        move    #>$58b90c,y1
        mpy     x0,y1,b                 ; e ln2/32
        asl     #$1,b,b                 ; e ln2/16
        add     x1,b
        add     #>$e3b923,b                ; + (ln(Is/N2) + 20 ln2)/16
        move    b,x:(r7+$37)            ; ln k2 / 16
        move    x:(r7+$37),b
        add     #>$058b91,b            ; k1 = 2 k2
        move    b,x:(r7+$38)            ; ln k1 / 16
; ---- C = (k + ln k + 8)/2^15, 48 bits, per side -------------------------------
        move    x:(r7+$37),a
        asr     #$b,a,a                 ; 16 (ln k2/16) / 2^15
        move    x:(r7+$3a),b
        asr     #$f,b,b                 ; k2 / 2^15
        add     b,a
        add     #>$000800,a             ; + 8/2^15
        move    a1,x:(r7+$02)
        move    a0,x:(r7+$03)
        move    x:(r7+$38),a
        asr     #$b,a,a
        move    x:(r7+$3a),b
        asr     #$e,b,b                 ; k1 / 2^15 = 2 k2 / 2^15
        add     b,a
        add     #>$000800,a
        move    a1,x:(r7+$07)
        move    a0,x:(r7+$08)
; ---- A = 4N, B = -A ln(k)/16, per side ---------------------------------------
        move    #>$2e6136,y1
        move    y1,x:(r7+$04)
        move    x:(r7+$37),x0
        mpy     -x0,y1,a
        move    a,x:(r7+$05)
        move    #>$17309b,y1
        move    y1,x:(r7+$09)
        move    x:(r7+$38),x0
        mpy     -x0,y1,a
        move    a,x:(r7+$0a)
; ---- TONE -> t (the W taper) -> the biquad, exact ------------------------------
        move    x:(r6+$1),a
        bsr     dtx_knob                ; x
        move    x0,a                    ; a clean load
        sub     #>$400000,a             ; d = x - 1/2
        move    a,x0
        mpy     x0,x0,b                 ; d^2
        move    b,y1
        move    #>$666666,x0
        mpy     x0,y1,b                 ; 0.8 d^2
        add     #>$266666,b              ; + 0.3
        move    b,y1
        move    a,x0                    ; d
        mpy     x0,y1,b                 ; d (0.3 + 0.8 d^2)
        add     #>$200000,b             ; t/2 = 1/4 + d (0.3 + 0.8 d^2)
        asl     #$1,b,b
        move    b,y1                    ; t, limited below 1.0
; the six coefficients as quadratics in t (manifest TONE_POLY, the TP table):
; B0 B1 B2 A1 A2 A0, each /8, to $32..$37
        move    #>$000174,n5
        move    r4,r5
        move    (r5)+n5
        move    r7,r3
        move    #$32,n3
        move    (r3)+n3
        do      #$6,>dtx_tpe
        move    p:(r5)+,x0              ; P2
        mpy     x0,y1,a
        move    p:(r5)+,x0              ; P1
        add     x0,a
        move    a,x0
        mpy     x0,y1,a
        move    p:(r5)+,x0              ; P0
        add     x0,a
        move    a,x:(r3)+
dtx_tpe:
        move    x:(r7+$37),x0           ; A0/8, in 0.018 .. 0.125
        move    #$02,a                   ; (short immediate: bits 23-16)
        bsr     dtx_div                 ; q = 1/(8 A0)
        move    x:(r7+$32),x0
        mpy     x0,y1,a
        asl     #$5,a,a                 ; (B0/8)(1/(8 A0)) 32 = b0/2
        move    a,x:(r7+$0b)
        move    x:(r7+$33),x0
        mpy     x0,y1,a
        asl     #$5,a,a
        move    a,x:(r7+$0c)            ; b1/2
        move    x:(r7+$34),x0
        mpy     x0,y1,a
        asl     #$5,a,a
        move    a,x:(r7+$0d)            ; b2/2
        move    x:(r7+$35),x0
        mpy     -x0,y1,a
        asl     #$5,a,a
        move    a,x:(r7+$0e)            ; -a1/2
        move    x:(r7+$36),x0
        mpy     -x0,y1,a
        asl     #$5,a,a
        move    a,x:(r7+$0f)            ; -a2/2
; ---- LEVL: linear, like VR2; x 0.68 (R10) x 1.41 (makeup) x 4 (V/4 -> 1 V) --
        move    x:(r6+$0),a
        bsr     dtx_knob
        move    #>$3d923a,y1
        mpy     x0,y1,a
        move    a,x:(r7+$10)            ; the output gain / 8
; ===========================================================================
; THE SD-1 SAMPLE LOOP
; ===========================================================================
sod_go:
        move    x:(r7+$30),a
        tst     a
        bne     sod_wet
        move    x:(r7+$2f),a
        tst     a
        bne     sod_calm
        do      n7,>sod_end
        bsr     sod_stage
        bsr     dtx_out                 ; the MODE fade, MIX, both channels
        nop                             ; LA: never a bsr (the chip decides the loop-back at LA;
                                        ; a call there ran one junk block now and then on the unit)
sod_end:
        move    #>$ffffff,m3
        rts
sod_calm:
        do      n7,>sod_cend
        bsr     sod_stage
        move    x:(r7+$11),y1           ; MIX x (1 + d) with d = 0 is MIX
        move    x:(r0),b                ; dry L
        move    y0,a
        sub     b,a
        asr     #$1,a,a                 ; (wet - dry)/2
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)+
        move    x:(r0),b                ; dry R
        move    y0,a
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)+
        nop
sod_cend:
        move    #>$ffffff,m3
        rts
sod_wet:
        do      n7,>sod_wend
        bsr     sod_stage
        move    y0,x:(r0)+
        move    y0,x:(r0)+
        nop
sod_wend:
        move    #>$ffffff,m3
        rts

; ---------------------------------------------------------------------------
; sod_stage -- one sample of the SD-1 up to the wet in y0: the input, its three
; HPs, the clipper (F, inline), TONE, the 1.59 kHz pole, the output HP, LEVEL.
; Straight-line. Uses a b x0 x1 y0 y1 r3 n3 r5 n5; reads r4 and r7.
; ---------------------------------------------------------------------------
sod_stage:
; ---- mono in, IN ----------------------------------------------------------
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a                 ; (L + R)/2
        move    a,x0
        move    x:(r7+$00),y1
        mpy     x0,y1,a                 ; vin
; ---- HP 7.2 Hz: y1 = c (vin - vin[n-1]) + p y1[n-1] ---------------------------
        move    a,x0
        move    #>$7fef31,y1
        mpy     x0,y1,a
        move    x0,x1                   ; vin
        move    x:(r7+$13),x0           ; vin[n-1]
        mac     -x0,y1,a
        move    x1,x:(r7+$13)
        move    x:(r7+$14),x0           ; y1[n-1]
        move    #>$7fde61,y1
        mac     x0,y1,a                 ; y1
; ---- HP 88 Hz: vp = c (y1 - y1[n-1]) + p vp[n-1] ------------------------------
        move    a,x1                    ; y1 (the word stored)
        move    x1,x:(r7+$14)
        move    #>$7f32e4,y1
        mpy     -x0,y1,a                ; x0 is still y1[n-1]
        move    x1,x0
        mac     x0,y1,a
        move    x:(r7+$1b),x0           ; vp[n-1]
        move    #>$7e65c9,y1
        mac     x0,y1,a                 ; vp
        move    a,x1                    ; vp (the word kept)
; ---- HP 720 Hz: h = c (vp - vp[n-1]) + p h[n-1] -------------------------------
        move    #>$79c044,y1
        mpy     -x0,y1,a                ; x0 is still vp[n-1]
        move    x1,x0
        mac     x0,y1,a
        move    x:(r7+$16),x0           ; h[n-1]
        move    #>$738087,y1
        mac     x0,y1,a                 ; h
; ---- v8: the SD-1 at 1x (2x through the halfbands, with vp delayed 5 to match
; them, until 18 Oct 2026): vf = F(h), o1 = clamp(vp + vf, rail) -----------------
        move    x1,x:(r7+$1b)           ; vp[n] (the HP 88 Hz's vp[n-1] next sample)
        move    a,x0                    ; h (the word kept)
        move    x0,x:(r7+$16)           ; h[n-1] next sample
; ---- sod_nl, inline: vf = F(h) ----
        move    x0,a
        move    x0,x:(r7+$12)           ; z, for the sign at the end
        tst     a
        move    #>$000001,b
        move    #>$000006,x0
        tmi     x0,b                    ; the side: r7+1 (D5+D6) or r7+6 (D4)
        abs     a
        move    b1,n3
        move    r7,r3
        move    a,x0                    ; |z|
        move    (r3)+n3                 ; r3 -> the side's five words
        move    x:(r3)+,y1              ; G
        move    x:(r3)+,a               ; C, high word (a0 cleared)
        move    x:(r3)+,a0              ; C, low word
        mac     x0,y1,a                 ; X = |z| G + C, 48 bits
        clb     a,b
        normf   b1,a                    ; m in [0.5, 1)
        move    b1,y0
        sub     #>$400000,a
        asl     #$1,a,a                 ; u = 2 (m - 1/2)
        move    a1,x1
        asr     #$13,a,a                ; seg = bits 22..19
        move    a1,x0
        move    y0,b                    ; the octave, a clean load
        asl     #$4,b,b
        add     #>$0000e0,b             ; + 14 x 16
        add     x0,b                    ; the point
        move    b1,n5
        move    x1,a
        and     #>$7ffff,a
        asl     #$4,a,a                 ; frac
        move    r4,r5
        move    a,x0
        move    (r5)+n5
        move    p:(r5)+,y0              ; WF[i]
        move    p:(r5),b                ; WF[i+1]
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a                    ; Wf/16
        move    a,x0
        move    x:(r3)+,y1              ; A
        move    x:(r3)+,a               ; B
        mac     x0,y1,a                 ; v
        move    a,x0
        neg     a
        move    a,y0                    ; -v
        move    x:(r7+$12),b
        tst     b
        move    x0,a
        tmi     y0,a                    ; z < 0: -v
; ---- o1 = clamp(vp + vf, rail): IC1a's output -----------------------------------
        move    x:(r7+$1b),x0           ; vp
        add     x0,a
        move    #>$69999a,x0
        cmp     x0,a
        tgt     x0,a
        move    #>$966666,x0
        cmp     x0,a
        tlt     x0,a
        move    a,x1                    ; o1
; ---- TONE: t = b0 o1 + b1 o1[n-1] + b2 o1[n-2] - a1 t[n-1] - a2 t[n-2] -----------
        move    x1,x0
        move    x:(r7+$0b),y1
        mpy     x0,y1,a
        move    x:(r7+$29),x0           ; o1[n-2]
        move    x:(r7+$0d),y1
        mac     x0,y1,a
        move    x:(r7+$28),x0           ; o1[n-1]
        move    x:(r7+$0c),y1
        mac     x0,y1,a
        move    x0,x:(r7+$29)
        move    x1,x:(r7+$28)
        move    x:(r7+$2b),x0           ; t[n-2]
        move    x:(r7+$0f),y1
        mac     x0,y1,a
        move    x:(r7+$2a),x0           ; t[n-1]
        move    x:(r7+$0e),y1
        mac     x0,y1,a
        move    x0,x:(r7+$2b)
        asl     #$1,a,a                 ; t (the coefficients are /2)
        move    a,x1                    ; t, limited
        move    x1,x:(r7+$2a)
; ---- R9 || C6: o2 = l (t + t[n-1]) + p o2[n-1], then the rail -------------------
        move    #>$0d08dd,y1
        mpy     x0,y1,a                 ; x0 is still t[n-1]
        move    x1,x0
        mac     x0,y1,a
        move    x:(r7+$2c),x0
        move    #>$65ee46,y1
        mac     x0,y1,a                 ; o2
        move    a,x:(r7+$2c)
        move    #>$69999a,x0
        cmp     x0,a
        tgt     x0,a
        move    #>$966666,x0
        cmp     x0,a
        tlt     x0,a
        move    a,x1                    ; o2, clamped
; ---- HP 10.8 Hz, the output DC blocker, with a 48-bit state ----------------
        move    x:(r7+$2e),a            ; S, high word (a0 cleared)
        move    x:(r7+$3c),a0           ; S, low word
        move    x:(r7+$2e),x0
        move    #>$003282,y1             ; 1 - p
        mac     -x0,y1,a
        move    x:(r7+$2d),x0           ; o2[n-1]
        move    x1,x:(r7+$2d)
        move    #>$3ff35f,y1             ; c/2
        mac     -x0,y1,a
        move    x1,x0
        mac     x0,y1,a                 ; S'
        move    a1,x:(r7+$2e)
        move    a0,x:(r7+$3c)
        move    a,x0                    ; o3/2, rounded
; ---- LEVEL --------------------------------------------------------------------------
        move    x:(r7+$10),y1
        mpy     x0,y1,a
        asl     #$4,a,a
        move    a,y0                    ; wet, limited to full scale
        rts

; ===========================================================================
; MODES 2 AND 3: THE RAT -- per block
; ===========================================================================
dtx_rat:
; ---- v8: the knobs as last decoded ($20 LEVL $21 TONE $22 DRIV, $23 = 1 when
; valid; the init and every switch clear it): the same three words, the same
; decode -- skip it. The words compared whole, LFO fractions included.
        move    x:(r7+$23),a
        tst     a
        beq     rat_dec
        move    x:(r6+$0),a
        move    x:(r7+$20),x0
        cmp     x0,a
        bne     rat_dec
        move    x:(r6+$1),a
        move    x:(r7+$21),x0
        cmp     x0,a
        bne     rat_dec
        move    x:(r6+$2),a
        move    x:(r7+$22),x0
        cmp     x0,a
        beq     dtx_rgo
rat_dec:
        move    x:(r6+$0),x0
        move    x0,x:(r7+$20)
        move    x:(r6+$1),x0
        move    x0,x:(r7+$21)
        move    x:(r6+$2),x0
        move    x0,x:(r7+$22)
        move    #>$000001,x0
        move    x0,x:(r7+$23)
; ---- the pedal's six words, MK + 6 (MODE - 1): KX 8N CK KK NK0 MAKEUP --------
        move    x:(r7+$3b),a
        move    #$03,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        move    #>$0001f7,a
        move    #>$0001fd,x0
        teq     x0,a                    ; TURBO: the LEDs' words
        move    a1,n5
        move    r4,r5
        move    (r5)+n5
        move    p:(r5)+,y0
        move    y0,x:(r7+$0a)           ; KX = 1/(32 N)
        move    p:(r5)+,y0
        move    y0,x:(r7+$0e)           ; 8N
        move    p:(r5)+,y0
        move    y0,x:(r7+$1b)           ; (ln k0 + 12)/256, parked
        move    p:(r5)+,y0
        move    y0,x:(r7+$1c)           ; k0/256, parked
        move    p:(r5)+,y0
        move    y0,x:(r7+$0d)           ; Is R6'/8 (x rho below: N k/8)
        move    p:(r5)+,y0
        move    y0,x:(r7+$10)           ; the make-up (x LEVEL below)
; ---- DISTORTION: Rd = 100k x A(x); P = 1 + Rd Gg, q = 1/P ----------------------
        move    x:(r6+$2),a
        bsr     dtx_knob                ; x
        move    #>$000153,b
        bsr     dtx_tab                 ; the A taper
        move    a,x0
        move    #>$4179c2,y1
        mpy     x0,y1,a
        add     #>$000800,a             ; P/4096
        move    a,x0
        move    x0,x:(r7+$14)           ; P/4096, parked
        move    #>$000400,a             ; 1/8192
        bsr     dtx_div                 ; q/2
        move    y1,x:(r7+$01)
        move    x:(r7+$01),a
        asl     #$1,a,a
        move    a,x:(r7+$01)            ; q (limited: 1 at DISTORTION 0)
        move    #>$7fffff,a
        move    x:(r7+$01),x0
        sub     x0,a
        move    a,x0                    ; 1 - q
        move    #>$75233a,y1
        mpy     x0,y1,a
        move    a,x:(r7+$02)            ; c5 = (1 - q) LAM
        move    #>$0adcc6,y1
        mpy     x0,y1,a
        move    a,x:(r7+$03)            ; c6 = (1 - q)(1 - LAM)
; ---- the integrator: theta = max(1/2, 1/1.3 - P/W), r = P/(P + theta W) -------
        move    x:(r7+$14),x0
        move    #>$23ef98,y1
        mpy     x0,y1,b
        asl     #$7,b,b                 ; P/W
        move    #>$627627,a
        sub     b,a
        move    #$40,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        tlt     x0,a                    ; theta
        move    a,x0
        move    x0,x:(r7+$15)           ; theta, parked
        move    #>$038fd8,y1
        mpy     x0,y1,a                 ; theta W/4096
        move    x:(r7+$14),x0
        add     x0,a                    ; (P + theta W)/4096
        move    a,x0                    ; the divisor
        move    x:(r7+$14),a            ; the dividend, P/4096
        bsr     dtx_div                 ; r
        move    y1,x:(r7+$04)           ; r, for now
        move    x:(r7+$15),x0           ; theta
        move    x:(r7+$04),a
        mac     -x0,y1,a
        move    a,x:(r7+$05)            ; (1 - theta) r
        move    #>$71fb0e,y1
        mpy     x0,y1,a                 ; theta W/128
        move    a,x0
        move    x:(r7+$04),y1
        mpy     x0,y1,a
        move    a,x:(r7+$06)            ; theta W r/128
        move    x:(r7+$04),a
        sub     #>$400000,a
        sub     #>$400000,a
        move    a,x:(r7+$04)            ; r - 1
; ---- FILTER: Rt' = R7 + 100k x A(1 - x); aD = 1/(1 + Rt' G8x) ------------------
        move    x:(r6+$1),a
        bsr     dtx_knob                ; x
        move    #>$7fffff,a
        sub     x0,a                    ; 1 - x: right is bright
        move    a,x0
        move    #>$000153,b
        bsr     dtx_tab
        move    a,x:(r7+$14)            ; the taper, parked
        move    x:(r7+$14),x0
        move    #>$3a6972,y1
        mpy     x0,y1,a
        add     #>$02e04d,a              ; (1 + Rt' G8x)/64
        move    a,x0
        move    #$02,a                   ; 1/64 (short immediate: bits 23-16)
        bsr     dtx_div
        move    y1,x:(r7+$0f)           ; aD
        move    x:(r7+$14),x0
        move    #>$0ccb1d,y1
        mpy     x0,y1,a
        add     #>$003120,a              ; Rt'/R89
        move    a,x0
        move    x:(r7+$0f),y1
        mpy     x0,y1,a
        move    a,x:(r7+$13)            ; a9
        move    x:(r7+$14),x0
        move    #>$3a3646,y1
        mpy     x0,y1,a
        add     #>$00df89,a              ; Rt'/(64 Rc8)
        move    a,x0
        move    x:(r7+$0f),y1
        mpy     x0,y1,a
        asl     #$6,a,a
        move    a,x:(r7+$12)            ; a8
; ---- rho = Rp/R6' = 1/(1 + R6' G8x aD) -----------------------------------------
        move    x:(r7+$0f),x0
        move    #>$12bca5,y1
        mpy     x0,y1,a
        add     #>$400000,a
        move    a,x0
        move    #$40,a                   ; (short immediate: bits 23-16)
        bsr     dtx_div
        move    y1,x:(r7+$07)           ; rho
        move    x:(r7+$0f),x0
        mpy     x0,y1,a                 ; rho aD
        move    a,x0
        move    #>$255876,y1
        mpy     x0,y1,a
        move    a,x:(r7+$08)            ; rho aD R6'/Rc8
        move    #>$0020d5,y1
        mpy     x0,y1,a
        move    a,x:(r7+$09)            ; rho aD R6'/R89
        move    x:(r7+$07),x0
        move    x:(r7+$0d),y1
        mpy     x0,y1,a
        move    a,x:(r7+$0d)            ; N k/8 = Is Rp/8
; ---- C/2 = (ln k + k + 12)/256, k = k0 rho, 48 bits ----------------------------
        move    x:(r7+$07),a
        bsr     dtx_ln                  ; ln(rho)/16
        move    a,x1
        move    x1,a                    ; a clean load
        asr     #$4,a,a                 ; ln(rho)/256
        move    x:(r7+$1b),x0
        add     x0,a                    ; + (ln k0 + 12)/256
        move    x:(r7+$07),x0
        move    x:(r7+$1c),y1
        mac     x0,y1,a                 ; + k0 rho/256
        move    a1,x:(r7+$0b)
        move    a0,x:(r7+$0c)
; ---- LEVEL: linear, x the pedal's make-up ---------------------------------------
        move    x:(r6+$0),a
        bsr     dtx_knob
        move    x:(r7+$10),y1
        mpy     x0,y1,a
        move    a,x:(r7+$10)            ; the output gain
; ---- the core's four limits, in registers through the loop ----------------------
dtx_rgo:
        move    #>$6cd7f2,r1
        move    #>$93280e,r2
        move    #>$700000,r3
        move    #>$900000,n3
        move    #>$0001e6,n4            ; the loop's OM lookup is from OM + 7 x 16, less the 16 of the 2m form: r4 on to there
        move    #>$194bf7,n1              ; three of the loop's constants, a word each to use
        move    #>$011919,n2
        move    (r4)+n4
        move    #>$0021c2,n4
        move    x:(r7+$30),a
        tst     a
        bne     dtx_rwet
        move    x:(r7+$2f),a
        tst     a
        bne     dtx_rcalm
; ===========================================================================
; THE RAT SAMPLE LOOPS: the fade (d moving), calm (d = 0), settled (wet alone)
; ===========================================================================
        do      n7,>dtx_rend
        bsr     dtx_rstage
        bsr     dtx_out                 ; the MODE fade, MIX, both channels
        nop                             ; LA: never a bsr (the chip decides the loop-back at LA;
                                        ; a call there ran one junk block now and then on the unit)
dtx_rend:
        move    #>$ffffff,m3
        rts
dtx_rcalm:
        do      n7,>dtx_rcend
        bsr     dtx_rstage
        move    x:(r7+$11),y1           ; MIX x (1 + d) with d = 0 is MIX
        move    x:(r0),b                ; dry L
        move    y0,a
        sub     b,a
        asr     #$1,a,a                 ; (wet - dry)/2
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)+
        move    x:(r0),b                ; dry R
        move    y0,a
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)+
        nop
dtx_rcend:
        move    #>$ffffff,m3
        rts
dtx_rwet:
        do      n7,>dtx_rwend
        bsr     dtx_rstage
        move    y0,x:(r0)+
        move    y0,x:(r0)+
        nop
dtx_rwend:
        move    #>$ffffff,m3
        rts

; ---------------------------------------------------------------------------
; dtx_rstage -- one sample of the RAT up to the wet in y0: the input, its HP,
; the LM308 stage and the clipper node, the output HP, LEVEL. Straight-line.
; Uses a b x0 x1 y0 y1 r5 n5; reads r0 n0 r1 r2 r3 n3 (the limits), n1 n2 n4 (RK5 RK6 RK9), r4 and r7.
; ---------------------------------------------------------------------------
dtx_rstage:
; ---- mono in, IN ----------------------------------------------------------
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a                 ; (L + R)/2
        move    a,x0
        move    x:(r7+$00),y1
        mpy     x0,y1,a                 ; vin
        move    a,x1
; ---- HP 7.2 Hz (C1, R2), a 48-bit state: S' = S - (1-p) hi(S) + c (vin - vin1) --
        move    x:(r7+$35),a            ; S, high word (a0 cleared)
        move    x:(r7+$36),a0           ; S, low word
        move    x:(r7+$35),x0
        move    #>$0021c2,y1             ; 1 - p
        mac     -x0,y1,a
        move    x:(r7+$34),x0           ; vin[n-1]
        move    x1,x:(r7+$34)
        move    #>$7fef1f,y0             ; c
        mac     -y0,x0,a
        mac     x1,y0,a                 ; S'
        move    a1,x:(r7+$35)
        move    a0,x:(r7+$36)
        move    a,y0                    ; vp = z, kept in y0 through the op-amp
; ---- the LM308 and the clipper, at 1x (2x until 15 Oct 2026: the cost on core 1) --
; ---- c0 = c5 vh5 + c6 vh6: v- = q vo + c0 ---------------------------------------
        move    x:(r7+$28),x0           ; vh5
        move    x:(r7+$02),y1           ; c5
        mpy     x0,y1,a
        move    x:(r7+$2a),x0           ; vh6
        move    x:(r7+$03),y1           ; c6
        mac     x0,y1,a
        move    a1,b                    ; c0 (|c0| < 1), kept in b
; ---- vo - vo1 = (r - 1) vo1 + (1 - th) r d1 + th W r (z - c0) ---------------------
        move    y0,a
        sub     b,a
        asr     #$1,a,a                 ; (z - c0)/2
        move    a,x0
        move    x:(r7+$06),y1           ; th W r/128
        mpy     x0,y1,a
        asl     #$8,a,a
        move    x:(r7+$1e),x1           ; vo1, kept in x1 to the add below (y1,x1: the signed form)
        move    x:(r7+$04),y1           ; r - 1
        mac     y1,x1,a
        move    x:(r7+$1f),x0           ; d1
        move    x:(r7+$05),y1           ; (1 - th) r
        mac     x0,y1,a                 ; the step
; ---- the slew: the step within +-SRT; then the rails -------------------------------
        asr     #$1,a,a                 ; the step at volts/8 (SRT/4 is past a word at 1x)
        move    r1,x0                   ; SRT/8
        cmp     x0,a
        tgt     x0,a
        move    r2,x0                   ; -SRT/8
        cmp     x0,a
        tlt     x0,a
        asl     #$1,a,a                 ; back to volts/4
        add     x1,a                    ; vo1 + the step
        move    r3,x0                   ; VSAT
        cmp     x0,a
        tgt     x0,a
        move    n3,x0                   ; -VSAT
        cmp     x0,a
        tlt     x0,a
        move    a,x1                    ; vo
        move    x1,x:(r7+$1e)
; ---- v- = q vo + c0;  d1 = W (z - v-) (a word: within +-4 V) ----------------------
        move    x:(r7+$01),y1           ; q
        mpy     y1,x1,a
        add     b,a
        move    a,b                     ; v-, kept in b (c0 is dead)
        move    y0,a
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    #>$71fb0e,y1
        mpy     x0,y1,a
        asl     #$8,a,a                 ; W (z - v-)
        move    a,x:(r7+$1f)            ; d1
; ---- C5, C6: vh += K (v- - vh), 48 bits -------------------------------------------
        move    b,a
        move    x:(r7+$28),x0
        sub     x0,a
        move    a,x0
        move    x:(r7+$28),a
        move    x:(r7+$29),a0
        move    n1,y1                   ; RK5
        mac     x0,y1,a
        move    a1,x:(r7+$28)
        move    a0,x:(r7+$29)
        move    x:(r7+$2a),a
        move    x:(r7+$2b),a0
        move    a1,x0
        sub     x0,b
        move    b,x0                    ; v- is dead after this: the difference is taken in b
        move    n2,y1                   ; RK6
        mac     x0,y1,a
        move    a1,x:(r7+$2a)
        move    a0,x:(r7+$2b)
; ---- the clipper node (volts/8): u = rho vs + s8 vh8 + s9 vh9 ---------------------
        move    x1,a
        asr     #$1,a,a                 ; vo, volts/8
        move    x:(r7+$2c),x0           ; vh7: C7
        sub     x0,a
        move    a,x0                    ; vs
        move    x0,x:(r7+$1d)
        move    x:(r7+$07),y1           ; rho
        mpy     x0,y1,a
        move    x:(r7+$2e),x0           ; vh8
        move    x:(r7+$08),y1
        mac     x0,y1,a
        move    x:(r7+$32),x0           ; vh9
        move    x:(r7+$09),y1
        mac     x0,y1,a                 ; u
        move    a,x:(r7+$1c)            ; u, for the sign at the end
; ---- the diode law: X/2 = |u| KX + C/2 = (U + 12)/256, U clamped to -11 .. 116 ---
        abs     a
        move    a,x0                    ; |u|
        move    x:(r7+$0a),y1           ; KX
        move    x:(r7+$0b),a            ; C/2, high word (a0 cleared)
        move    x:(r7+$0c),a0           ; C/2, low word
        mac     x0,y1,a
        move    #>$008000,x0
        cmp     x0,a
        tlt     x0,a
        move    #>$3fffff,x0
        cmp     x0,a
        tgt     x0,a
        clb     a,b
        normf   b1,a                    ; m in [0.5, 1)
        asl     #$1,a,a                 ; 2m, not 2 (m - 1/2): bit 23 is the 16 OMB16 takes off
        move    a1,x1
        asr     #$13,a,a                ; 16 + seg, seg = bits 22..19
        move    a1,x0
        asl     #$4,b,b                 ; the octave (-7..-1) x 16
        add     x0,b                    ; the point (r4 is at OM + 7 x 16)
        move    b1,n5
        move    x1,a                    ; (bit 23 set: A2 is stale from here, so a1 below, not a)
        lsl     #$5,a
        lsr     #$1,a                   ; frac = (u & $7ffff) << 4
        move    r4,r5
        move    a1,x0
        move    (r5)+n5
        move    p:(r5)+,y0              ; OM[i]
        move    p:(r5),b                ; OM[i+1]
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a                    ; omega/128
        move    a,x0
        move    x:(r7+$0e),y1           ; 8N
        mpy     x0,y1,b
        asl     #$1,b,b                 ; (N/8) omega
        move    x:(r7+$0d),a            ; N k/8
        sub     b,a                     ; D = N k/8 - (N/8) omega
        move    a,y0                    ; D
        neg     a                       ; -D
        move    x:(r7+$1c),b            ; u, a clean load
        tst     b
        tpl     y0,a                    ; sgn(u) D
        add     b,a                     ; v = u + sgn(u) D
        move    a,x0                    ; v
        move    x0,b                    ; kept in b
; ---- vX = aD v + a8 vh8 + a9 vh9; C8: vh8 = 2 vX - vh8 -----------------------------
        move    x:(r7+$0f),y1           ; aD
        mpy     x0,y1,a
        move    x:(r7+$32),x0
        move    x:(r7+$13),y1           ; a9
        mac     x0,y1,a
        move    x:(r7+$2e),x0
        move    x:(r7+$12),y1           ; a8 (last, so x0 is vh8 for the update below)
        mac     x0,y1,a
        move    a,x1                    ; vX
        asl     #$1,a,a
        sub     x0,a
        move    a,x:(r7+$2e)            ; vh8
; ---- C7: vh7 += K7 (vs - v), 48 bits ------------------------------------------------
        move    x:(r7+$1d),a
        sub     b,a
        asr     #$1,a,a
        move    a,x0                    ; (vs - v)/2
        move    x:(r7+$2c),a
        move    x:(r7+$2d),a0
        move    #>$013b6d,y1
        mac     x0,y1,a
        move    a1,x:(r7+$2c)
        move    a0,x:(r7+$2d)
; ---- C9 into R8: g = GR8 (vX - vh9); vh9 += K9 (vX - vh9) -------------------------
        move    x1,a
        move    x:(r7+$32),x0
        sub     x0,a
        move    a,x0                    ; vX - vh9
        move    x:(r7+$32),a
        move    x:(r7+$33),a0
        move    n4,y1                   ; RK9
        mac     x0,y1,a
        move    a1,x:(r7+$32)
        move    a0,x:(r7+$33)
        move    #>$7fef1f,y1
        mpy     x0,y1,a                 ; g
        move    a,x1                    ; g (volts/8)
; ---- HP 1.6 Hz (C10 into VOLUME), 48-bit state: S = o/2 + 1/2 LSB ----------------
        move    x:(r7+$37),a            ; S, high word (a0 cleared)
        move    x:(r7+$38),a0           ; S, low word
        move    x:(r7+$37),x0
        move    #>$00076e,y1             ; 1 - p
        mac     -x0,y1,a
        move    x:(r7+$3a),x0           ; g[n-1]
        move    x1,x:(r7+$3a)
        move    #>$3ffe25,y0             ; c/2
        mac     -y0,x0,a
        mac     x1,y0,a                 ; S'
        move    a1,x:(r7+$37)
        move    a0,x:(r7+$38)
        move    a,x0                    ; o/2 (volts/8), rounded
; ---- LEVEL: o (volts) x LEVEL x make-up ---------------------------------------
        move    x:(r7+$10),y1
        mpy     x0,y1,a
        asl     #$4,a,a
        move    a,y0                    ; wet, limited to full scale
        rts

; ---------------------------------------------------------------------------
; dtx_out -- the MODE fade, then MIX: wet in y0, the frame at x:(r0), r0 on
; past it. MIX x (1 + d) (d = 0: MIX exactly), d one step on within [-1, 0].
; Uses a b x0 y1.
; ---------------------------------------------------------------------------
; v9: branch-free (cycle_count prices a bsr callee as inlined, label..rts, straight-line).
dtx_out:
        move    x:(r7+$11),y1           ; MIX
        move    x:(r7+$3d),x0           ; d
        move    y1,a
        mac     x0,y1,a                 ; MIX + d MIX
        move    a,y1                    ; MIX x (1 + d)
        move    x:(r7+$3d),a
        move    x:(r7+$3e),x0
        add     x0,a                    ; d + step
        move    #0,x0
        cmp     x0,a
        tgt     x0,a                    ; not above 0
        move    #$80,x0                  ; (short immediate: bits 23-16)
        cmp     x0,a
        tlt     x0,a                    ; not below -1
        move    a,x:(r7+$3d)
        move    x:(r0),b                ; dry L
        move    y0,a
        sub     b,a
        asr     #$1,a,a                 ; (wet - dry)/2
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    x:(r7+$30),b            ; v8's settled block (d = 0, the pedal on, MIX 127):
        tst     b                       ; the wet alone, as v8's early return wrote it
        tne     y0,a                    ; (d's update above leaves 0 at 0 there)
        move    a,x:(r0)+
        move    x:(r0),b                ; dry R
        move    y0,a
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    x:(r7+$30),b
        tst     b
        tne     y0,a
        move    a,x:(r0)+
        rts

; ---------------------------------------------------------------------------
; dtx_knob -- a page-1 knob word in a -> x0 = knob x 128/127, limited below
; 1.0. Uses a x0 y1.
; ---------------------------------------------------------------------------
dtx_knob:
        and     #>$7fffff,a
        move    a,x0
        move    #>$010204,y1
        mac     x0,y1,a
        move    a,x0
        rts

; ---------------------------------------------------------------------------
; dtx_tab -- a 33-point P table at offset b, interpolated at x0 (0..1): a.
; (EXP for IN, TAPER for the pots.) Uses a b x0 x1 y0 y1 r5 n5.
; ---------------------------------------------------------------------------
dtx_tab:
        move    x0,a                    ; a clean load
        move    a1,x1
        asr     #$12,a,a                ; idx = bits 22..18
        add     b,a
        move    a1,n5
        move    x1,a
        and     #>$3ffff,a
        asl     #$5,a,a                 ; frac
        move    r4,r5
        move    (r5)+n5
        move    a,x0
        move    p:(r5)+,y0
        move    p:(r5),b
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a
        rts

; ---------------------------------------------------------------------------
; dtx_ln -- ln(m)/16 for m in [0.5, 1) in a (a clean load or a normf), from
; the LN table, interpolated. Uses a b x0 x1 y0 y1 r5 n5.
; ---------------------------------------------------------------------------
dtx_ln:
        sub     #>$400000,a
        asl     #$1,a,a                 ; u = 2 (m - 1/2)
        move    a1,x1
        asr     #$11,a,a                ; idx = bits 22..17
        add     #>$0000f1,a
        move    a1,n5
        move    x1,a
        and     #>$1ffff,a
        asl     #$6,a,a                 ; frac
        move    r4,r5
        move    (r5)+n5
        move    a,x0
        move    p:(r5)+,y0              ; LN[i]
        move    p:(r5),b                ; LN[i+1]
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a                    ; ln(m)/16
        rts

; ---------------------------------------------------------------------------
; dtx_div -- y1 = a1/x0 for 0 <= a1 < x0 (a0 clean), 24 quotient bits (the
; SD-1's TONE division).
; ---------------------------------------------------------------------------
dtx_div:
        andi    #$fe,ccr
        do      #$18,>dxdivlp           ; do, not rep
        div     x0,a
dxdivlp:
        move    a0,y1
        rts
