; ---------------------------------------------------------------------------
; CHARACTER -- fold, saturate, tilt, compress, width.
;
; Insert contract (modules/ripple/ripple_svf.asm): frames in place at
; x:(r0)/x:(r0+n0), knobs from r6, state in this instance's r7 block. The
; station never touches the bus.
;
; ---- the chain, fixed order ----------------------------------------------
;   f     = fold(x * gain) / gain                       FOLD (held level)
;   s     = TAPE: TapeHead(f; DRV) | TUBE | INFL          DRV, SAT (held level)
;   t     = tilt(s; TONE)                                TONE (64 = flat)
;   c     = t * gain(env)                                COMP (GLUE on the master)
;   w     = width(c)                                     WDTH
;   out   = x + MIX*(w - x)                              MIX
; Distortion before dynamics.
;
; ---- the compressor (JClones AC1, MIT) -------------------------------------
; AC1's console channel law for both flavours: |key| smoothed by attack /
; release, Lv = K * level_s, gr = (Lv^2/2 - 1)^2 + a*Lv clamped at 1 -- a
; dip around Lv = 1 whose depth is a = 0.75 - 0.675*COMP/128 -- and a
; makeup 1/(1 - 0.3375*COMP/128). GLUE: 0.5 / 500 ms, K = 3. COMP: 0.5 /
; 63 ms, K = 4 (release coefficient $bd0 = 3024/2^23 per sample, tau = 62.9
; ms). COMP 0 skips the stage, bit-exact. The key is the mono input, read
; from the frame (untouched until the write-back).
;
; ---- r7 slots -------------------------------------------------------------
; per block, read into the rings before the loop:
;   $1d fold trim/2 (1/128)/gq   $20 m (MIX)   $21 fold gain/64 (gq)
;   $22 K/4   $24 tilt t/2   $26 COMP amount   $27 makeup/4   $28 the dip's a
;   $29 sat mode (0 TAPE = TapeHead, 1 TUBE = DaTube, 2 INFL = OInflator)
;   $2a TAPE trim (1/11)/d8 + 0.023   $2b width side gain/2
;   $2d attack coeff   $2e release coeff
;   $30 k2   $31 k3mag   $48 d/8 (TAPE)
;   $32 G/8   $33 the output scale after the curve (1, (1+d)/G, 1/G by mode)
;   $37 d/2   $38 d   $39 comp/2   $4c (0.5+d)/2 (TUBE)   $3a e/2   $3b 1-e (INFL)
;   $4d DRV == 0: skip the saturator
;   $25 master flag (1 = position 3 on A: GLUE), $23 FX2-slot flag (set at
;     init: 1 = this instance is on FX2, dry)
; persistent, zeroed at init:
;   $3e/$3f R y1/y2, $40/$41 L y1/y2: TapeHead's SVF states (/4)
;   $42/$43 L x1/y1, $44/$45 R x1/y1: TUBE's DC blockers
;   $5a tilt lp L, $5b tilt lp R, $5c level_s
; per sample:
;   $19 wet L, $1a wet R (r4 -> $19)
;   $60..$6f the main ring (r5, m5 = 15), in the order the sample reads
;     them: gq trim/2 gq trim/2 $4d $29 t/2 t/2 $26 $2d $2e $22 $28 $27 $2b
;     $20 -- COMP off steps over its five words (n5 = 5, else 0)
;   $70..$7f the SAT ring (r6, m6 = 15 in every mode -- the chip has only
;     ever run power-of-two modulos): G/8 then TAPE k2 k3mag d8 d8 trim,
;     TUBE (0.5+d)/2 d d/2 comp/2 R, INFL e/2 1-e, then the scale; x2; the
;     remainder to 16 is stepped once per sample by (r6)+n6 (n6 = 2 / 2 / 8)
; The loop's state pointers all go through n3 = $41: TapeHead's L y2 at
; r7 + n3, TUBE's L pair at r7 + n3 + 1, the tilt block at r4 + n3 (an
; address register steps only by its own N).
; knob glides and ramps (26 Sep 2026):
;   $4e..$53 page-1 slots 0..5 glided; $54 1 once they started at the
;   knobs, $55 1 once the ring's run values started at their targets (both
;   zeroed at init); $15..$17, $34..$36 the per-sample steps of gq trim t,
;   a makeup m (per block), whose run values are their main-ring words
; free: $18, $1b, $1c, $2c, $3c/$3d, $46/$47, $49..$4b, $56..$59, $5d..$5f
;
; ---- the master, by position ---------------------------------------------
; On the master (dispatch position 3 on payload A, track 8) COMP runs the
; GLUE law; everywhere else the channel law. SAT is TAPE / TUBE / INFL on
; every track; no knob changes meaning by mode.
;
; CYCLES_FORWARD_BRANCHES -- the branches in the sample loop are forward and
; skip work, so the word span is the worst-case cycle count
; (tools/build/cycle_count.py). The saturation character and the
; compressor mode are per-block coefficients for that reason: a dispatch
; inside the loop cannot be priced.
;
; Every mpy is `mpy x0,y1` or `mpy y0,x0` (the signed encodings) except
; chtube's `mpy x1,y1` (mpysu; its second operand is the constant 1.0,
; commented at its site). Every Tcc reads the one compare above it with
; nothing but moves between (the flag-clobber trap).
; ---------------------------------------------------------------------------

init:
; ROTINIT
; ---- FX1 ONLY: the allocator base decides, at init --------
; Modulation's idiom (modules/modulation/modulation.asm): X:0x213 points at
; this instance's entry in the base table, valid HERE and nowhere else. FX1
; slots are below 0x4000, FX2 slots at or above it. An FX2 instance runs as
; a dry pass -- proc returns before it touches a frame or the bus -- so a
; part that names this id on FX2 (the stock id both menus share) costs its
; core nothing: the rig's cycle envelope is priced with the stations on FX1
; only (tools/harness/pressure.py), and the FX2 chooser hides them.
; sub/tst rather than cmp: the cmp-encodes-as-max family (AGENTS.md).
        move    x:>$213,r4
        move    #>$ffffff,m4
        move    x:(r4),x0
        move    x0,a
        move    #>$4000,x0
        sub     x0,a                    ; base - 0x4000
        clr     b                       ; b = 0 BEFORE the tst (the flag trap)
        move    #>$1,x0
        tst     a
        tpl     x0,b                    ; base >= 0x4000: an FX2 slot
        move    b,x:(r7+$23)            ; 1 = dry pass
        clr     a
        move    a,x:(r7+$3e)            ; TapeHead's SVF states, R then L
        move    a,x:(r7+$3f)
        move    a,x:(r7+$40)
        move    a,x:(r7+$41)
        move    a,x:(r7+$42)            ; the DC blocker's states, L then R
        move    a,x:(r7+$43)
        move    a,x:(r7+$44)
        move    a,x:(r7+$45)
        move    a,x:(r7+$5a)            ; the tilt's two low-pass states, the
        move    a,x:(r7+$5b)            ; compressor's level_s, the master flag:
        move    a,x:(r7+$5c)            ; every slot read before written
        move    a,x:(r7+$25)            ; (verify_dirtystate)
        move    a,x:(r7+$54)            ; the glides start at the knobs,
        move    a,x:(r7+$55)            ; the ramps at their targets
        rts

proc:
        move    x:(r7+$23),a            ; an FX2 slot: dry, nothing written
        tst     a
        bne     ch_end
; ---- KNOB GLIDES (26 Sep 2026): page-1 slots 0..5 (DRV FOLD WDTH COMP
; TONE MIX) move 1/128 of the way to the knob per block into $4e..$53 and
; snap to it when the step rounds to nothing; the decode reads those. The
; first block after init ($54 = 0) starts them AT the knobs, so a knob at
; rest renders as before (tools/verify/verify_knob_clicks.py).
        move    r6,r4
        move    #>$ffffff,m4
        move    r7,r5
        move    #$4e,n5
        move    (r5)+n5
        move    #>$ffffff,m5
        move    x:(r7+$54),b
        do      #6,>ch_glz
        move    x:(r4)+,y1              ; the knob
        tst     b
        move    x:(r5),a                ; the glide (moves keep the flags)
        teq     y1,a                    ; the first block: at the knob
        move    a,x0
        move    y1,a
        sub     x0,a
        asr     #$7,a,a
        move    a,x1                    ; a0 holds the shifted-out bits: a
        move    x1,a                    ; clean reload, so Z reads a1 alone
        add     x0,a
        cmp     x0,a                    ; no progress: at the knob
        teq     y1,a
        move    a,x:(r5)+
ch_glz:
        nop
        move    #>$1,x0
        move    x0,x:(r7+$54)
; ===========================================================================
; PER-BLOCK KNOB DECODE
; ===========================================================================
; MIX: page-1 slot 5 since 16 Sep 2026; TONE page-1 slot 4 since 20 Sep
        move    x:(r7+$53),a             ; a knob word: bit 23 clear, a2 = 0
        move    a1,x:(r7+$20)           ; m (a1 straight to memory)
        move    x:(r7+$4f),x0            ; the knob word IS FOLD/128 in Q23
        move    #$5e,y1                 ; 47/64 (short immediate: bits 23-16)
        mpy     x0,y1,a                 ; (47/64)*(FOLD/128)
        add     #>$020000,a             ; + 1/64 -> gain/64, 0.016 .. 0.75
        move    a,x:(r7+$21)            ; gq
        move    a,x0                    ; gq = the denominator, >= 1/64
        move    #>$010000,a             ; 1/128 (a clean load: a0 = 0)
        andi    #$fe,ccr
        rep     #$18
        div     x0,a
        move    a0,x0
        move    x0,x:(r7+$1d)           ; fold trim/2
; DRV 0 skips the saturation stage (a per-block flag, $4d; a forward skip
; per sample), so DRV 0 is bit-exact in every mode. The saturators' states
; are not cleared while skipped: a later DRV resumes from them.
        move    x:(r7+$4e),a             ; DRV
        clr     b                       ; b = 0 BEFORE the tst (the flag trap)
        move    #>$1,x0
        tst     a
        teq     x0,b                    ; DRV == 0 -> skip flag 1
        move    b,x:(r7+$4d)
        move    x:(r7+$52),a             ; TONE, page-1 slot 4
        and     #>$7f0000,a             ; a knob word, TONE << 16
        sub     #>$400000,a
        move    a,x:(r7+$24)            ; t/2, -0.5 .. +0.49
; COMP amount, straight from the knob
        move    x:(r7+$51),x0
        move    x0,x:(r7+$26)
        move    x:(r7+$25),a
        tst     a
        bne     ch_cglue
        move    #>$7fffff,x0            ; COMP: K/4 = 1.0 (4x), release 63 ms
        move    x0,x:(r7+$22)
        move    #>$000bd0,x0
        move    x0,x:(r7+$2e)
        bra     ch_cset
ch_cglue:
        move    #$60,x0                 ; GLUE: K/4 = 0.75 (3x), release 500 ms
        move    x0,x:(r7+$22)
        move    #>$00017c,x0
        move    x0,x:(r7+$2e)
ch_cset:
        move    #>$05ce1b,x0            ; attack 0.5 ms: 1/(fs*t), both
        move    x0,x:(r7+$2d)
        move    x:(r7+$26),x0           ; COMP/128
        move    #>$566666,y1            ; 0.675
        mpy     x0,y1,a
        neg     a
        add     #>$600000,a             ; a = 0.75 - 0.675*COMP/128
        move    a,x:(r7+$28)
        move    #>$2b3333,y1            ; 0.3375
        mpy     x0,y1,a
        neg     a
        add     #>$7fffff,a             ; den = 1 - 0.3375*COMP/128 (0.66..1)
        move    a,x0
        move    #$20,a                  ; num = 0.25 (a1), a2 = a0 = 0 (short: bits 23-16)
        andi    #$fe,ccr
        rep     #$18
        div     x0,a
        move    a0,x0
        move    x0,x:(r7+$27)           ; m/4 = 0.25/den: makeup/4
; SAT (slot 6, r6+$c's knob field) -> the mode flag $29 and per-mode words,
; so the sample loop's SAT stage is a MODEFORK: TAPE (0) = TapeHead, TUBE (1)
; = DaTube, INFL (2) = OInflator (JClones, MIT). A stored 3 lands on TAPE.
; Per-mode words, all from DRV = d (0..0.992):
;   TUBE  $37 = d/2 (the positive half's scale)  $38 = d (the negative half's)
;         ($4c = (0.5 + d)/2 input gain and $39 = comp/2 below, every mode)
;   INFL  $3a = e/2 with e = d            $3b = 1 - e
        clr     a
        move    a,x:(r7+$29)            ; sat mode: 0 = TAPE
        move    x:(r6+$c),a             ; SAT, slot 6 = $c's knob field
        and     #>$ff0000,a
        cmp     #>$10000,a
        beq     ch_stube
        cmp     #>$20000,a
        beq     ch_sinfd
        bra     ch_sdone                ; TAPE (a stored 3 too)
ch_stube:
        move    #>$1,x0
        move    x0,x:(r7+$29)           ; sat mode 1: TUBE
        move    x:(r7+$4e),a             ; d = DRV/128
        move    a,x:(r7+$38)            ; the negative half: d
        asr     #$1,a,a
        move    a,x:(r7+$37)            ; the positive half: d/2
                                        ; (TUBE's asymmetry leaves DC; the DC
                                        ; blocker in chtube, R = 0.999 ~7 Hz,
                                        ; removes it)
        bra     ch_sdone
ch_sinfd:
        move    #>$2,x0
        move    x0,x:(r7+$29)           ; sat mode 2: INFL
        move    x:(r7+$4e),a             ; e = DRV/128
        move    a,x0
        asr     #$1,a,a
        move    a,x:(r7+$3a)            ; e/2
        move    #>$7fffff,a
        sub     x0,a
        move    a,x:(r7+$3b)            ; 1 - e (DRV 0 never gets here: the skip)
ch_sdone:
; ---- the master flag, BY POSITION ($45: GLUE) ---------------------------
; Track 8 is dispatch position 3 on PAYLOAD A; the mirror position on core 1
; is track 4. An insert carries no per-payload literal (an FX1 module may own
; no buffers, so the build refuses it a base), so the core is read off the
; DISPATCH TABLE: in the specialized image BusVerb (id 0x07) is real on
; payload A and ALIASED TO SEND (id 0x09) on payload B -- X:$215+7 ==
; X:$215+9 there. Under the DEV hatch everything is payload A and the test
; allows. A remix WITHOUT BusVerb has no master anywhere (its id aliases on
; both cores).
        move    x:>$21c,a               ; INIT_TABLE[REVERB SERVER]
        move    x:>$21e,x0              ; INIT_TABLE[SEND]
        cmp     x0,a
        beq     ch_nopos                ; the alias: payload B
        move    r7,a
        and     #>$ff00,a
        move    #>$6a00,x0
        cmp     x0,a
        beq     ch_master
ch_nopos:
        clr     a
        move    a,x:(r7+$25)            ; not track 8: the channel law
        bra     ch_pos3
ch_master:
        move    #>$1,x0
        move    x0,x:(r7+$25)           ; the master: GLUE
ch_pos3:
        move    x:(r7+$4e),a             ; d = DRV/128
        move    a,x1                    ; (x1 = DRV/128 for TapeHead's words below)
        move    a,x0
        move    #>$37445f,y1            ; 0.43175 = 1.727/4
        mpy     x0,y1,a
        add     #>$200000,a             ; (1 + 1.727 d)/4
        move    a,x0
        move    x1,a
        asr     #$1,a,a
        add     #>$200000,a             ; (0.5 + d)/2
        move    a,x:(r7+$4c)            ; TUBE's input gain, halved
        move    a,y1
        mpy     x0,y1,a                 ; D8
        move    a,x0                    ; den
        move    #$08,y1                 ; 1/16
        move    y1,a                    ; a clean load: a0 = 0 for the divide
        andi    #$fe,ccr                ; carry clear
        rep     #$18
        div     x0,a                    ; 24 quotient bits land in a0
        move    a0,x0
        move    x0,x:(r7+$39)           ; comp/2
; the P table: TUBE_UP (17 pairs, DaTube's curve) then TAPE_D8 (9 words).
        move    #>$fab1e0,r1            ; TUBE_UP -- rewritten by build_bus.py
        move    #>$ffffff,m1
        move    r1,r2
        move    (r2)+                   ; r2 = its slopes
; ---- TapeHead's per-block words (TAPE only reads them; computed always) --
; d8 = d/8 from TAPE_D8 (the 17 words after TUBE_UP's 34), interpolated over
; DRV/128 (idx = DRV >> 19, frac = the 19 bits under it); k2 linear in
; TONE/128 (2.1 -> 5 kHz);
; k3mag = 1.4*k2 = (0.7*k2)*2. The table sits in the manifest after DaTube's
; curve, so the one P-table literal above still finds everything.
        move    r1,r3
        move    #$22,n3                 ; 34 (short immediate: an integer)
        move    #>$ffffff,m3
        move    x1,a                    ; DRV/128
        asr     #$13,a,a
        move    (r3)+n3                 ; r3 = TAPE_D8
        move    a1,n3
        move    x1,a
        and     #>$7ffff,a
        asl     #$4,a,a
        move    a,x0                    ; frac
        move    (r3)+n3
        move    p:(r3)+,y0              ; D8[idx]
        move    p:(r3),b                ; D8[idx+1]
        move    y0,a
        sub     a,b                     ; diff (> 0: the table rises)
        move    b,y1
        mpy     x0,y1,a
        add     y0,a
        move    a,x:(r7+$48)            ; d8 = d/8, 0.1 .. 0.98
        move    a,x0                    ; d8 = the denominator
        move    #>$0ba2e9,a             ; 1/11 (a clean load: a0 = 0)
        andi    #$fe,ccr                ; carry clear
        rep     #$18
        div     x0,a                    ; 24 quotient bits land in a0
        move    a0,x0                   ; (1/11)/d8, flat unity
        move    x0,a
        add     #>$02fb7f,a             ; 0.0233
        move    a,x:(r7+$2a)            ; TAPE trim
        move    #>$3fb89c,a             ; k2 = 0.4978: the split at its middle
        move    a,x:(r7+$30)            ; (3.7 kHz; TONE is the tilt since 14 Sep 2026)
        move    a,x0
        move    #>$59999a,y1            ; 0.7: k3mag = 1.4 * k2, halved
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,x:(r7+$31)            ; k3mag (< 0.98)
; WDTH -> mid and side gains. 64 = (1, 1); 0 = (1, 0) mono; 127 = (1, ~2).
; side gain = WDTH/64, mid stays 1 -- widening only touches the difference,
; so a mono source is untouched at every setting.
        move    x:(r7+$50),a             ; WDTH, page-1 slot 2 -> WDTH << 16
; ⚠️ STORED HALVED. A y1 operand is a FRACTION, and a side gain of WDTH/64
; tops out near 2.0, which would wrap the word. The knob's own value IS
; WDTH/128, so it is stored as-is and the product is doubled back in the
; accumulator's guard bits. 64 -> 0.5 -> x2 = exactly 1.0, i.e. untouched.
        move    a1,x:(r7+$2b)           ; side gain / 2 (a1 straight to memory)
; ---- BYPASS: the defaults are a bit-exact passthrough ---------------------
; DRV 0, FOLD 0, TONE 64, COMP 0, MIX 127, WDTH 64. Every part that
; ever chose LO-FI runs this after the flash, so the neutral block does
; nothing at all.
        move    x:(r7+$4e),a             ; DRV
        tst     a
        bne     ch_live
        move    x:(r7+$4f),a             ; FOLD
        tst     a
        bne     ch_live
        move    x:(r7+$24),a            ; the tilt's t/2 (TONE 64 = 0)
        tst     a
        bne     ch_live
        move    x:(r7+$51),a             ; COMP
        tst     a
        bne     ch_live
        move    x:(r7+$2b),a            ; side gain/2: 64 -> exactly 0.5
        move    #$40,x0
        cmp     x0,a
        beq     ch_bypass
ch_live:

; ===========================================================================
; THE SAMPLE LOOP
; ===========================================================================
        move    #$1,n0                  ; (short immediate, stock's own form)
        move    #>$ffffff,m3            ; the SAT callees own r3
; ---- the rings (22 Sep 2026): the block's coefficients, in the order the
; sample reads them, walked by post-increment; modulo brings each pointer
; back to its base every sample (one turn per sample), so nothing is reset
; inside the loop. r4 -> the per-sample scratch (wet L, wet R, key).
        move    r7,r4
        move    #$19,n4
        move    (r4)+n4
        move    #>$ffffff,m4
        move    r7,r5
        move    #$60,n5
        move    (r5)+n5
        move    #>$ffffff,m5
; ---- THE RAMPS (26 Sep 2026): gq trim t a makeup m are RUN values in the
; ring, stepped once per sample by the loop's head (ch_rset), steps at
; $15..$17 and $34..$36
        move    r5,r3
        move    r7,r6                   ; (the page is read: r6 is free)
        move    #$15,n6
        move    (r6)+n6
        move    x:(r7+$21),y1           ; gq (FOLD L)
        bsr     ch_rset
        move    b,x1
        move    x:(r7+$1d),y1           ; trim/2
        bsr     ch_rset
        move    x1,x:(r3)+              ; gq (FOLD R), the same run
        move    b,x:(r3)+               ; trim/2 (R)
        move    x:(r7+$4d),x0           ; DRV 0: skip the saturator
        move    x0,x:(r3)+
        move    x:(r7+$29),x0           ; sat mode
        move    x0,x:(r3)+
        move    x:(r7+$24),y1           ; t/2 (TONE L)
        bsr     ch_rset
        move    b,x:(r3)+               ; t/2 (TONE R), the same run
        move    #$0f,m5                 ; sixteen words, one turn per sample
        move    x:(r7+$26),a            ; COMP; off: the sample steps over its
        move    a,x:(r3)+               ; five words (n5 = 5 at ch_capd)
        clr     b
        move    #>$5,x0
        tst     a
        teq     x0,b
        move    b1,n5
        move    x:(r7+$2d),x0           ; attack
        move    x0,x:(r3)+
        move    x:(r7+$2e),x0           ; release
        move    x0,x:(r3)+
        move    x:(r7+$22),x0           ; K/4
        move    x0,x:(r3)+
        move    r7,r6
        move    #$34,n6
        move    (r6)+n6
        move    x:(r7+$28),y1           ; the dip's a
        bsr     ch_rset
        move    x:(r7+$27),y1           ; makeup/4
        bsr     ch_rset
        move    x:(r7+$2b),x0           ; side gain / 2
        move    x0,x:(r3)+
        move    x:(r7+$20),y1           ; m
        bsr     ch_rset
        move    #>$1,x0
        move    x0,x:(r7+$55)
; DRV's drive into the curve: the saturator's input is x*G with G = 1 + 3d
; (DRV 127 = +12 dB) and its output is scaled back per mode -- INFL by 1/G
; (unity small signal), TUBE by (1+d)/G, TAPE by 1 (TapeHead's own trim
; holds its small signal at unity and its smoothstep compresses the rest;
; with 1/G on top a loop sat 18 dB under dry at DRV 127). G/8 at $32, the
; output scale at $33 (the ring words around each callee).
        move    x:(r7+$4e),a             ; d = DRV/128
        move    a,x0
        move    #>$300000,y1            ; 0.375
        mpy     x0,y1,a
        add     #>$100000,a             ; G/8 = 0.125 + 0.375 d
        move    a,x:(r7+$32)
        move    a,x0
        move    #$08,y1                 ; 1/16
        move    y1,a                    ; a clean load: a0 = 0 for the divide
        andi    #$fe,ccr
        rep     #$18
        div     x0,a                    ; (1/16)/(G/8) = 1/(2G) in a0
        move    a0,x0
        move    x0,a
        asl     #$1,a,a                 ; 1/G, 1.0 at DRV 0 (the store limits)
        move    x:(r7+$29),b            ; sat mode
        tst     b
        beq     ch_gtape
        cmp     #>$1,b
        bne     ch_gdone                ; INFL: 1/G
        move    a,x0                    ; TUBE: (1/G)(1+d)
        move    x:(r7+$4e),a
        asr     #$1,a,a
        add     #>$400000,a             ; (1 + d)/2
        move    a,y1
        mpy     x0,y1,a
        asl     #$1,a,a
        bra     ch_gdone
ch_gtape:
        move    #>$7fffff,a             ; TAPE: 1
ch_gdone:
        move    a,x:(r7+$33)
; the SAT ring: the active mode's words, both channels, each between G/8
; and the output scale. n3 = $41 for the sample loop's state pointers:
; TapeHead's L y2 at r7 + n3, TUBE's L pair one past it, the tilt block at
; r4 + n3.
        move    #$41,n3
        move    r7,r6
        move    #$70,n6
        move    (r6)+n6
        move    #$0f,m6                 ; sixteen words in every mode: the
        move    r6,r3                   ; chip has only ever run power-of-two
                                        ; modulos (stock m = $3ff, $7f, $1f);
                                        ; the remainder is stepped by n6
        move    x:(r7+$29),a
        tst     a
        bne     ch_r12
        move    x:(r7+$32),x0           ; TAPE: G/8 k2 k3mag d8 d8 trim scale
        move    x0,x:(r3)+
        move    x:(r7+$30),x0
        move    x0,x:(r3)+
        move    x:(r7+$31),x0
        move    x0,x:(r3)+
        move    x:(r7+$48),x0
        move    x0,x:(r3)+
        move    x0,x:(r3)+
        move    x:(r7+$2a),x0
        move    x0,x:(r3)+
        move    x:(r7+$33),x0
        move    x0,x:(r3)+
        move    x:(r7+$32),x0
        move    x0,x:(r3)+
        move    x:(r7+$30),x0
        move    x0,x:(r3)+
        move    x:(r7+$31),x0
        move    x0,x:(r3)+
        move    x:(r7+$48),x0
        move    x0,x:(r3)+
        move    x0,x:(r3)+
        move    x:(r7+$2a),x0
        move    x0,x:(r3)+
        move    x:(r7+$33),x0
        move    x0,x:(r3)+
        move    #$2,n6                  ; 16 - 14
        bra     ch_rdone
ch_r12:
        cmp     #>$1,a
        bne     ch_rinfl
        move    x:(r7+$32),x0           ; TUBE: G/8 (0.5+d)/2 d d/2 comp/2 R scale
        move    x0,x:(r3)+
        move    x:(r7+$4c),x0
        move    x0,x:(r3)+
        move    x:(r7+$38),x0
        move    x0,x:(r3)+
        move    x:(r7+$37),x0
        move    x0,x:(r3)+
        move    x:(r7+$39),x0
        move    x0,x:(r3)+
        move    #>$7fdf3b,x0            ; the DC blocker's R = 0.999
        move    x0,x:(r3)+
        move    x:(r7+$33),x0
        move    x0,x:(r3)+
        move    x:(r7+$32),x0
        move    x0,x:(r3)+
        move    x:(r7+$4c),x0
        move    x0,x:(r3)+
        move    x:(r7+$38),x0
        move    x0,x:(r3)+
        move    x:(r7+$37),x0
        move    x0,x:(r3)+
        move    x:(r7+$39),x0
        move    x0,x:(r3)+
        move    #>$7fdf3b,x0            ; the DC blocker's R = 0.999
        move    x0,x:(r3)+
        move    x:(r7+$33),x0
        move    x0,x:(r3)+
        move    #$2,n6                  ; 16 - 14
        bra     ch_rdone
ch_rinfl:
        move    x:(r7+$32),x0           ; INFL: G/8 e/2 1-e scale
        move    x0,x:(r3)+
        move    x:(r7+$3a),x0
        move    x0,x:(r3)+
        move    x:(r7+$3b),x0
        move    x0,x:(r3)+
        move    x:(r7+$33),x0
        move    x0,x:(r3)+
        move    x:(r7+$32),x0
        move    x0,x:(r3)+
        move    x:(r7+$3a),x0
        move    x0,x:(r3)+
        move    x:(r7+$3b),x0
        move    x0,x:(r3)+
        move    x:(r7+$33),x0
        move    x0,x:(r3)+
        move    #$8,n6                  ; 16 - 8
ch_rdone:
        do      n7,>ch_end
; ---- the ramps' step: r5 walks the ring once (one turn per sample), r3
; the steps ($15..$17, then $34..$36)
        lua     (r7+$15),r3
        move    x:(r3)+,x0
        move    x:(r5),a
        add     x0,a    x:(r3)+,x0
        move    a,x:(r5)+               ; gq L
        move    x:(r5),b
        add     x0,b    x:(r3)+,x0
        move    b,x:(r5)+               ; trim/2 L
        move    a,x:(r5)+               ; gq R
        move    b,x:(r5)+               ; trim/2 R
        move    (r5)+
        move    (r5)+
        move    x:(r5),a
        add     x0,a
        move    a,x:(r5)+               ; t/2 L
        move    a,x:(r5)+               ; t/2 R
        lua     (r7+$34),r3
        move    (r5)+
        move    (r5)+
        move    (r5)+
        move    (r5)+
        move    x:(r3)+,x0
        move    x:(r5),a
        add     x0,a    x:(r3)+,x0
        move    a,x:(r5)+               ; the dip's a
        move    x:(r5),a
        add     x0,a    x:(r3)+,x0
        move    a,x:(r5)+               ; makeup/4
        move    (r5)+
        move    x:(r5),a
        add     x0,a
        move    a,x:(r5)+               ; m, and r5 is back at the ring's head
; ---- FOLD: WarpFold's wrap-and-reflect, both channels --------------------
        move    x:(r0),x0
        move    x:(r5)+,y1              ; gq = gain/64
        mpy     x0,y1,a                 ; v/64
        asl     #$5,a,a                 ; v/2
        move    #$40,x1                 ; 0.5 (short immediate: bits 23-16)
        add     x1,a                    ; (v+1)/2
        move    a1,x1                   ; s = wrap(...), raw A1: the fold
        move    x1,a                    ; clean re-load, A2 consistent
        abs     a
        move    #$40,b                  ; 0.5, b2 = b0 = 0
        sub     b,a                     ; |s| - 0.5
        asl     #$1,a,a                 ; fold in [-1,1)
        move    a,x0
        move    x:(r5)+,y1              ; trim/2
        mpy     x0,y1,a
        asl     #$1,a,a                 ; the fold at a held level
        move    a,x:(r4)+               ; wet L
        move    x:(r0+n0),x0
        move    x:(r5)+,y1
        mpy     x0,y1,a
        asl     #$5,a,a
        move    #$40,x1
        add     x1,a
        move    a1,x1
        move    x1,a
        abs     a
        move    #$40,b
        sub     b,a
        asl     #$1,a,a
        move    a,x0
        move    x:(r5)+,y1
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,x:(r4)-               ; wet R
; ---- SATURATE: the character. TAPE is
; TapeHead, TUBE is DaTube, INFL is OInflator: one straight-line callee per
; mode per channel (a = the sample in, b = out; the caller's store is the
; hard clip). Skipped whole when DRV is 0 (per block). The three
; alternatives are a MODEFORK so the pricer charges the worst, not all.
        move    x:(r5)+,b               ; DRV 0: skip the saturator
        move    x:(r5)+,a               ; sat mode (both ring words consumed)
        tst     b
        bne     ch_nosat
; MODEFORK_BEGIN -- cycle_count.py: the dispatch, one flag test
        tst     a
        bne     ch_s12
; MODEFORK_MID -- alternative 1: TAPE = TapeHead
; r3 -> the channel's y2 (y1 the word below): L at r7 + n3 = $41, R two
; below (chtape leaves r3 where it entered). r6 its ring. y0 = the
; smoothstep's 0.7 for both calls (chtape reads it, never writes it).
        move    r7,r3
        move    x:(r4),x0               ; L in (post fold)
        move    x:(r6)+,y1              ; G/8
        mpy     x0,y1,a
        asl     #$3,a,a                 ; x*G, up to 4 in the accumulator
        move    #>$59999a,y0            ; 0.7
        move    (r3)+n3                 ; r3 = r7+$41: L y2
        bsr     chtape
        move    b,x0                    ; LIMITING: the hard clip
        move    x:(r6)+,y1              ; the output scale
        mpy     x0,y1,b
        move    b,x:(r4)+
        move    x:(r4),x0               ; R in
        move    x:(r6)+,y1              ; G/8
        mpy     x0,y1,a
        asl     #$3,a,a                 ; x*G, up to 4 in the accumulator
        move    (r3)-
        move    (r3)-                   ; r3 = r7+$3f: R y2
        bsr     chtape
        move    b,x0                    ; LIMITING: the hard clip
        move    x:(r6)+,y1              ; the output scale
        mpy     x0,y1,b
        move    b,x:(r4)-
        move    (r6)+n6                 ; the ring's remainder: one turn per sample
        bra     ch_nosat
; MODEFORK_MID -- alternative 2: TUBE = DaTube (one compare more: 1 or 2)
ch_s12:
        cmp     #>$1,a
        bne     ch_sinfl
; r3 -> the channel's DC-blocker pair (x1, y1): L at r7 + n3 + 1 = $42, R
; the pair above (chtube leaves r3 on y1).
        move    r7,r3
        move    x:(r4),x0               ; L in (post fold)
        move    x:(r6)+,y1              ; G/8
        mpy     x0,y1,a
        move    (r3)+n3
        asl     #$3,a,a                 ; x*G, up to 4 in the accumulator
        move    (r3)+                   ; r3 = r7+$42: L x1, y1
        bsr     chtube
        move    b,x0                    ; LIMITING: the hard clip
        move    x:(r6)+,y1              ; the output scale
        mpy     x0,y1,b
        move    b,x:(r4)+
        move    x:(r4),x0               ; R in
        move    x:(r6)+,y1              ; G/8
        mpy     x0,y1,a
        asl     #$3,a,a                 ; x*G, up to 4 in the accumulator
        move    (r3)+                   ; r3 = r7+$44: R x1, y1
        bsr     chtube
        move    b,x0                    ; LIMITING: the hard clip
        move    x:(r6)+,y1              ; the output scale
        mpy     x0,y1,b
        move    b,x:(r4)-
        move    (r6)+n6
        bra     ch_nosat
; MODEFORK_MID -- alternative 3: INFL = OInflator (stateless, inlined per
; channel: its 30 words twice against a bsr/rts per call)
ch_sinfl:
        move    x:(r4),x0               ; L in (post fold)
        move    x:(r6)+,y1              ; G/8
        mpy     x0,y1,a
        asl     #$3,a,a                 ; x*G, up to 4 in the accumulator
; ---- OInflator inline (JClones_OInflator.jsfx, MIT), single band, Curve 0
; (c = 0.25), Clip on: x2 = x/2; g = 0.75 + 0.5|x2|; gx = g x2;
; y = 2e gx (1 - |gx|) + (1 - e) x2; out = 2y. e = DRV/128; g and t = 1 - |gx|
; live halved. Stateless; the ring holds e/2, 1 - e. Clobbers x0, x1, y1, a, b.
        asr     #$1,a,a                 ; x2
        move    a,x1
        abs     a
        move    a,x0                    ; |x2|
        move    #$20,y1                 ; 0.25
        mpy     x0,y1,a
        add     #>$300000,a             ; g/2 = 0.375 + 0.25*|x2|
        move    a,y1
        move    x1,x0                   ; x2
        mpy     x0,y1,a
        asl     #$1,a,a                 ; gx = g*x2
        move    a,x0                    ; gx
        abs     a
        asr     #$1,a,a
        neg     a
        add     #>$400000,a             ; t/2 = 0.5 - |gx|/2, in [0.25, 0.5]
        move    a,y1
        mpy     x0,y1,a                 ; gx * t/2
        move    a,x0
        move    x:(r6)+,y1              ; e/2
        mpy     x0,y1,a                 ; gx * t/2 * e/2
        asl     #$3,a,a                 ; 2e * gx * t
        move    x1,x0                   ; x2
        move    x:(r6)+,y1              ; 1 - e
        mac     x0,y1,a                 ; + (1 - e)*x2 = y
        asl     #$1,a,a                 ; out = 2y
        move    a,b
        move    b,x0                    ; LIMITING: the hard clip
        move    x:(r6)+,y1              ; the output scale
        mpy     x0,y1,b
        move    b,x:(r4)+
        move    x:(r4),x0               ; R in           
        move    x:(r6)+,y1              ; G/8
        mpy     x0,y1,a
        asl     #$3,a,a                 ; x*G, up to 4 in the accumulator
        asr     #$1,a,a                 ; x2
        move    a,x1
        abs     a
        move    a,x0                    ; |x2|
        move    #$20,y1                 ; 0.25
        mpy     x0,y1,a
        add     #>$300000,a             ; g/2 = 0.375 + 0.25*|x2|
        move    a,y1
        move    x1,x0                   ; x2
        mpy     x0,y1,a
        asl     #$1,a,a                 ; gx = g*x2
        move    a,x0                    ; gx
        abs     a
        asr     #$1,a,a
        neg     a
        add     #>$400000,a             ; t/2 = 0.5 - |gx|/2, in [0.25, 0.5]
        move    a,y1
        mpy     x0,y1,a                 ; gx * t/2
        move    a,x0
        move    x:(r6)+,y1              ; e/2
        mpy     x0,y1,a                 ; gx * t/2 * e/2
        asl     #$3,a,a                 ; 2e * gx * t
        move    x1,x0                   ; x2
        move    x:(r6)+,y1              ; 1 - e
        mac     x0,y1,a                 ; + (1 - e)*x2 = y
        asl     #$1,a,a                 ; out = 2y
        move    a,b
        move    b,x0                    ; LIMITING: the hard clip
        move    x:(r6)+,y1              ; the output scale
        mpy     x0,y1,b
        move    b,x:(r4)-
        move    (r6)+n6
; MODEFORK_END
ch_nosat:
; ---- TONE: a tilt after the saturator, every mode ----------
; One-pole low-pass at 1.2 kHz per channel (k = 0.157), y = x + (t/2)(x - 2lp):
; TONE 127 = +3.5 dB above / -6 dB below, 0 the mirror, 64 bit-exact.
; r3 -> the state block at r4 + n3 = $5a: lp L, lp R, level_s. y0 = k.
        move    r4,r3
        move    #>$141893,y0            ; k = 0.157: one pole at 1.2 kHz
        move    (r3)+n3
        move    x:(r4),a                ; L
        move    x:(r3),x0               ; lp
        sub     x0,a
        move    a,x0                    ; x - lp
        mpy     y0,x0,a         x:(r3),b
        add     b,a                     ; lp' = lp + k (x - lp)
        move    a,x:(r3)+
        move    a,x0
        move    x:(r4),a
        sub     x0,a
        sub     x0,a                    ; x - 2 lp'
        move    a,x0
        move    x:(r5)+,y1              ; t/2
        mpy     x0,y1,a
        move    x:(r4),b
        add     b,a
        move    a,x:(r4)+
        move    x:(r4),a                ; R
        move    x:(r3),x0
        sub     x0,a
        move    a,x0
        mpy     y0,x0,a         x:(r3),b
        add     b,a
        move    a,x:(r3)+
        move    a,x0
        move    x:(r4),a
        sub     x0,a
        sub     x0,a
        move    a,x0
        move    x:(r5)+,y1
        mpy     x0,y1,a
        move    x:(r4),b
        add     b,a
        move    a,x:(r4)-
; ---- COMPRESS: COMP 0 skips the stage
; (bit-exact); else |key| smoothed by the flavour's attack / release, Lv =
; K * level_s, gr = (Lv^2/2 - 1)^2 + a*Lv, <= 1 by the limiting move --
; a dip around Lv = 1 -- then x *= gr * makeup on both channels. Lv is
; carried halved (Lv/2, so Lv up to 2 fits a word; the dip is over by 1.5).
; r3 -> level_s after the tilt's two states. The key is the mono input,
; still untouched in the frame (the write-back is the last stage).
        move    x:(r5)+,a               ; COMP
        tst     a
        beq     ch_capd                 ; COMP 0: the stage is skipped
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a                 ; key = mono in
        abs     a
        move    a,x0                    ; level
        move    x:(r3),b                ; level_s
        move    x0,a
        sub     b,a             x:(r5)+,x1      ; d = level - level_s; attack
        move    x:(r5)+,b               ; release
        tst     a                       ; nothing between this and the Tcc
        tpl     x1,b                    ; rising: attack
        move    b,y1
        move    a,x0
        mpy     x0,y1,a         x:(r3),b        ; k*d; level_s
        add     b,a
        move    a,x:(r3)                ; level_s
        move    a,x0
        move    x:(r5)+,y1              ; K/4
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,x0                    ; Lv/2 (the limiting move: Lv <= 2)
        move    x0,y1
        mpy     x0,y1,a                 ; (Lv/2)^2
        asl     #$1,a,a                 ; Lv^2/2
        add     #>$800000,a             ; t = Lv^2/2 - 1  (-1 .. 1)
        move    a,x1                    ; t (clean)
        move    x:(r5)+,y1              ; a
        mpy     x0,y1,b                 ; a*Lv/2  (x0 = Lv/2 >= 0)
        asl     #$1,b,b                 ; a*Lv
        move    x1,x0                   ; t goes negative below the dip: the
        move    x1,y1                   ; square must be the audited x0,y1
        mpy     x0,y1,a                 ; t^2   (mpy x1,y1 encodes as mpysu)
        add     b,a                     ; gr = t^2 + a*Lv
        move    a,x0                    ; gr (the limiting move: <= 1)
        move    x:(r5)+,y1              ; makeup/4
        mpy     x0,y1,a         x:(r4),x0
        move    a,y1                    ; gr*makeup/4
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x:(r4)+
        move    x:(r4),x0
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x:(r4)-
ch_capd:
        move    (r5)+n5                 ; COMP off: past its five ring words
; ---- WIDTH: mid stays, side scales ---------------------------------------
        move    x:(r4)+,a               ; L
        move    x:(r4)-,x0              ; R
        add     x0,a
        asr     #$1,a,a
        move    a,x1                    ; mid
        move    x:(r4),a
        sub     x0,a
        asr     #$1,a,a
        move    a,x0                    ; side
        move    x:(r5)+,y1              ; side gain / 2
        mpy     x0,y1,a
        asl     #$1,a,a                 ; the halving undone in the guard bits
        move    a,y0                    ; scaled side
        move    x1,a
        add     y0,a                    ; mid + side
        tfr     x1,a            a,x:(r4)+
        sub     y0,a                    ; mid - side
        move    a,x:(r4)-
; ---- MIX and write back --------------------------------------------------
        move    x:(r4)+,a
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r5)+,y1              ; m (the ring's last word: r5 turns)
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        move    x:(r4)-,a
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a                 ; y1 still m
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    (r0)+n0                 ; the frame advance: n0 is 1 for the
        move    (r0)+n0                 ; whole loop, so two steps, no reload
ch_end:
        move    #>$ffffff,m5            ; the rings' modulo, back to linear
        move    #>$ffffff,m6
        rts

; ===========================================================================
; BYPASS: frames untouched -- nothing to do at all (Spectrum's shape)
; ===========================================================================
ch_bypass:
        rts

; ---------------------------------------------------------------------------
; ch_rset -- one ramped ring word, per block (26 Sep 2026). The word is a
; RUN value the loop's head steps once per sample, 1/16 of the way from
; where the last block ended to this block's target (Spectrum's cutoff
; ramp form); a step that rounds to 0 puts it on the target, and the first
; block after init ($55 = 0) starts it there.
; In: y1 = the target, r3 -> the word, r6 -> its step. Out: b = the run
; value, r3 and r6 each one on. Clobbers a, x0, y0.
; ---------------------------------------------------------------------------
ch_rset:
        move    x:(r7+$55),b
        tst     b
        move    x:(r3),b                ; the run value (moves keep the flags)
        teq     y1,b                    ; the first block: at the target
        move    b,x0
        move    y1,a
        sub     x0,a
        asr     #$4,a,a                 ; the step per sample
        move    a,y0                    ; a0 holds the shifted-out bits: a
        move    y0,a                    ; clean reload, so Z reads a1 alone
        tst     a
        teq     y1,b                    ; a step of 0: at the target
        move    a,x:(r6)+
        move    b,x:(r3)+
        rts

; ---------------------------------------------------------------------------
; chtube -- DaTube per channel (JClones_DaTube.jsfx, MIT).
; In: a = x, r3 -> the DC blocker's x1 (y1 the word above), r6 -> the ring
; ((0.5+d)/2, d, d/2, comp/2, R). Out: b.
;   xin = x*(0.5 + d)                           ((0.5+d)/2, halved)
;   u   = 1 - |xin|      (may go negative: the JSFX's linear extension past
;                         +-1 is exactly the curve with u^P dropped, so the
;                         table lookup clamps u to 0 and the rest is linear)
;   T   = u - u^P, P = ln(10) + 1 = 3.3026     (TUBE_UP: 17 pairs of u^P/2)
;   y   = xin + (d/2)*T for xin > 0, xin - d*T for xin < 0   (asymmetric: the
;                         negative half is driven twice as hard -- the tube)
;   out = 2 * y * comp(d), then the DC blocker (k = 1 an immediate, R =
;                         0.999 from the ring).
; Everything runs HALVED (xin/2 <= 0.75, u/2, T/2, y/2) and the post gain is
; comp/4 doubled back twice. STRAIGHT-LINE: no branch. Every mpy x0,y1 (the
; audited-signed order; the one Tcc reads the tst right before it). Clobbers
; x0, x1, y0, y1, a, b, n1, n2; y0 parks u/2 (P2[idx] rides in b).
chtube:
        move    a,x0                    ; x
        move    x:(r6)+,y1              ; (0.5 + d)/2
        mpy     x0,y1,a
        move    a,x1                    ; xin/2  (|.| <= 0.75)
        abs     a
        neg     a
        add     #>$400000,a             ; u/2 = 0.5 - |xin/2|, in [-0.25, 0.5]
        move    a,y0                    ; park u/2
        move    #$0,x0                  ; (a move does not disturb the flags)
        tst     a
        tmi     x0,a                    ; the lookup's argument: max(u, 0)/2
        move    a,b
        asr     #$11,b,b                ; u/2 >> 17 = 2*idx + bit 17 ...
        and     #>$fffffe,b             ; ... masked to 2*idx (17 pairs, 1/32 steps)
        move    b1,n1
        move    b1,n2
        move    a,b
        and     #>$3ffff,b              ; the 18 bits under the step (b2 = 0)
        asl     #$5,b,b                 ; frac, Q23
        move    b,x0                    ; AGU settle: n1 written 4 back
        move    p:(r1+n1),b             ; P2[idx] = u^P / 2
        move    p:(r2+n2),y1            ; P2[idx+1] - P2[idx]  (>= 0)
        mpy     x0,y1,a                 ; frac * slope
        add     b,a                     ; u^P / 2
        move    y0,b                    ; u/2
        sub     a,b                     ; T/2 = (u - u^P)/2
        move    b,x0                    ; T/2
        move    x:(r6)+,y1              ; d
        mpy     x0,y1,a                 ; d * T/2
        neg     a
        move    a,y0                    ; the negative half's term, parked
        move    x:(r6)+,y1              ; d/2
        mpy     x0,y1,a                 ; the positive half's term
        move    x1,b                    ; xin/2
        tst     b                       ; its sign -- nothing between this
        tmi     y0,a                    ; and the Tcc (the flag trap)
        add     x1,a                    ; y/2 = xin/2 + term
        move    a,x0
        move    x:(r6)+,y1              ; comp/2
        mpy     x0,y1,a                 ; (y/2)(comp/2) = y*comp/4
        asl     #$2,a,a                 ; *4 -> y*comp: the JSFX's -6 dB default
        move    a,x0                    ; x, the DC blocker's input (LIMITING)
        move    x:(r3),x1               ; x1
        move    x0,x:(r3)+              ; x1 <- x
        move    #>$7fffff,y1            ; k = 1.0 (an immediate: chtube is TUBE's)
        mpy     x1,y1,b                 ; k*x1 (mpysu: y1 is positive)
        move    x0,a
        sub     b,a             x:(r3),x0       ; x - x1; y1
        move    x:(r6)+,y1              ; R = 0.999
        mac     x0,y1,a                 ; + R*y1
        move    a,x:(r3)                ; y1 <- y
        move    a,b
        rts

; chtape -- TapeHead per channel (JClones_TapeHead.jsfx, MIT).
; In: a = x, r3 -> y2 (y1 the word below), both kept at /4 (the
; port's headroom: |y1| <= 1.46, |y2| <= 1.95 true), r6 -> the ring (k2,
; k3mag, d/8, d/8, trim), y0 = 0.7. Out: b = (g3*clip(y3)
; + ss(d*y1) + ss(d*y2)) * trim, up to 2.2, CLIPPED (the JSFX's own output
; clip) and then scaled by the block's unity trim (1/11)/d8. STRAIGHT-LINE:
; no branch of any kind
; (cycle_count.py charges the span at each call). Every mpy is x0,y1 or
; y0,x0 (the signed encodings); every clip is a LIMITING move into x0.
; Clobbers x0, x1, y1, a, b; reads y0.
;   y1 += k2*y2 ; y3 = k1*y1 + y2 - x ; y2 -= k3mag*y3      (k3 = -1.4 k2)
;   ss(v) = 1.5v - 0.5v^3 on v = clip(d*y1), clip(d*y2)      (v = 32*(y1/4*d/8))
chtape:
        asr     #$2,a,a                 ; Xs = x/4
        move    a,x1
        move    x:(r3)-,x0              ; y2
        move    x:(r6)+,y1              ; k2
        mpy     x0,y1,a         x:(r3),b
        add     b,a                     ; y1n = y1 + k2*y2
        move    a,x0
        move    #>$5b6db7,y1            ; k1 = 5/7
        mpy     x0,y1,a         a,x:(r3)+       ; (the store is y1n, limited)
        move    x:(r3),b
        add     b,a
        sub     x1,a                    ; y3 = k1*y1n + y2 - Xs
        move    a,x0
        move    x:(r6)+,y1              ; k3mag
        mpy     x0,y1,a         x:(r3),b
        sub     a,b                     ; y2n = y2 - k3mag*y3
        tfr     x0,a            b,x:(r3)-
        asl     #$2,a,a                 ; 4*y3
        move    a,x0                    ; LIMITING move: clip(y3)
        move    #>$33e5de,y1            ; |g3|*trim/2 (g3 = -0.81, trim 1.0)
        mpy     x0,y1,b
        asl     #$1,b,b
        neg     b                       ; b = g3*trim*clip(y3)   (g3 < 0)
        move    x:(r3)+,x0              ; y1n/4
        move    x:(r6)+,y1              ; d/8
        mpy     x0,y1,a
        asl     #$5,a,a                 ; v = d*y1n
        move    a,x0                    ; LIMITING move: clip(v)
        move    x0,y1
        mpy     x0,y1,a                 ; v^2
        move    a,y1
        mpy     x0,y1,a                 ; v^3
        neg     a
        add     x0,a                    ; v - v^3
        asr     #$1,a,a
        add     x0,a                    ; ss(v) = 1.5v - 0.5v^3
        move    a,x0
        mpy     y0,x0,a                 ; * 0.7 (y0, the caller's)
        add     a,b             x:(r3),x0       ; y2n/4
        move    x:(r6)+,y1
        mpy     x0,y1,a
        asl     #$5,a,a
        move    a,x0
        move    x0,y1
        mpy     x0,y1,a
        move    a,y1
        mpy     x0,y1,a
        neg     a
        add     x0,a
        asr     #$1,a,a
        add     x0,a
        move    a,x0
        mpy     y0,x0,a                 ; * 0.7
        add     a,b
        move    b,x0                    ; LIMITING move: the JSFX's output clip
        move    x:(r6)+,y1              ; then the trim (1/11)/d8 + 0.023
        mpy     x0,y1,b
        rts
