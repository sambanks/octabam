; ---------------------------------------------------------------------------
; VIBRATO -- a pitch vibrato: one modulated delay per channel, wet only, MIX
; blends. Proven against modules/vibrato/vibrato_ref.py (verify_vibrato.py).
;
; Insert contract (frames in place at x:(r0) / x:(r0+n0), knobs from r6,
; state in the r7 block). FX1 only: init reads the allocator base (X:0x213
; -> this instance's entry, valid at init only); a base >= 0x4000 is an FX2
; slot and proc returns at once, writing nothing. Two 1,024-word lines (L at
; the base, R at base + $400) out of the FX1 slot's 3,072; every FX1 base is
; 1024-aligned, so the lines are AGU modulo rings (m5 = $3ff).
;
; Every shape is a PITCH trajectory; the delay is its integral, normalised
; to +-1 and scaled by the swing H (Q11.12 samples):
;   SINE  delay sin(2 pi phi), from the stock sine at X:0x6c00 (1,024 words,
;         m = $3ff), linearly interpolated   H = dev per / (2 pi)
;   TRI   delay +-4u(1-u), u = 2 phi mod 1   H = dev per / 8
;   SQR   delay 1 - 4|v - 1/2|, v = phi + 1/4   H = dev per / 4
;   RND   a new pitch u each half cycle, steered: u = (x + n)/2, then x -= 4
;         u dphi per block, |x| <= 1          H = dev per / 4
; H = min(500 samples, 8dev * per/2^18 * FAC), FAC from the P table.
;
; Per block (the knob decode, the phase n7 on, the knot): each channel's
; delay walks to its knot in a straight line, a 16th of the way a sample
; (modulation's mo_knot). The sample loop is straight-line: no branch, one
; callee (vb_tap, straight-line).
;
; The r7 block ($00..$3f, all zeroed at init):
;   $00 LFO phase, Q23 cycles (persistent)    $01 line write phase (persistent)
;   $02 H (per block)                         $03/$04 slewed offset L/R (persistent)
;   $05/$06 delay L/R, Q11.12 (persistent)    $07/$08 slope L/R (per block)
;   $09/$0a RND x L/R (persistent)            $0b/$0c RND u L/R (persistent)
;   $0d LFSR state (seeded at init from the payload and r7)           $0e line base (init)
;   $0f FX2 flag (init)                       $10 running shape << 16 (persistent)
;   $11 duck e (persistent; $7fffff at init)  $12 MIX run (persistent)
;   $13 MIX step (per block)                  $14 primed: 1 after the first block
;   $15 P table base                          $16 inc   $17 dphi = n7 inc
;   $18 per/2^18   $19 8 dev per/2^18         $1a/$1b raw offset L/R
;   $1c SLEW coefficient c                    $1d n1   $1e the walk's limit S
;   $1f the phase at block start
;   $20..$3f free
;
; Every mpy is `mpy x0,y1`, the order dsp_asm encodes signed (AGENTS.md).
; AND and ASL leave A2 stale: every value passing through one leaves via a1.
; ---------------------------------------------------------------------------

init:
; ---- every slot to zero (verify_dirty_state). r5, never r1: the FX1
; dispatcher keeps the effect id in r1 across this call (verify_init_regs).
        clr     a
        move    r7,r5
        move    #>$ffffff,m5
        do      #$40,>vbinz
        move    a,x:(r5)+
vbinz:
        nop
; ---- the allocator base, and the FX1/FX2 decision ------------------------
        move    x:>$213,r4
        move    #>$ffffff,m4
        move    x:(r4),x0
        move    x0,x:(r7+$0e)           ; the line base
; sub/tst rather than cmp: the cmp-encodes-as-max family (AGENTS.md).
        move    x0,a
        move    #>$4000,x0
        sub     x0,a                    ; base - 0x4000
        clr     b                       ; b = 0 BEFORE the tst (the flag trap)
        move    #>$1,x0
        tst     a
        tpl     x0,b                    ; base >= 0x4000: an FX2 slot
        move    b,x:(r7+$0f)
        tst     b
        bne     vbnoclr                 ; FX2: never touch the buffer at all
; ---- clear both lines, once, at instantiation ----------------------------
        move    x:(r7+$0e),a
        move    a,r5
        move    #>$ffffff,m5
        clr     a
        do      #2048,>vbclrz
        move    a,y:(r5)+
vbclrz:
        nop
vbnoclr:
; ---- the LFSR's seed: the payload's own odd word, eor this instance's r7 <<
; 8 (low byte 0, so the seed stays odd and never zero): no two RND instances
; step in lockstep, on either core. Then the duck fully out (the wet fades in).
        move    r7,x0
        move    x0,a                    ; a clean load: r7 is positive
        asl     #$8,a,a
        move    a1,x0
        move    #>@SEED@,a
        eor     x0,a
        move    a1,x:(r7+$0d)
        move    #>$7fffff,x0
        move    x0,x:(r7+$11)
        rts

; ===========================================================================
proc:
; ===========================================================================
        move    x:(r7+$0f),a
        tst     a
        bne     vb_dry                  ; an FX2 instance: the frames pass dry
; ---- the P table ---------------------------------------------------------
        move    #>$ffffff,m5
        move    #>$ffffff,m4
        move    #>$ffffff,m1
        move    #>$ffffff,m3
        move    #>$fab1e0,r5            ; the ptable's base, placed by the build
        move    r5,x:(r7+$15)           ; (the build wants the literal once)
; ---- SPD -> inc (the floor: the phase accumulates it) and per ------------
        move    x:(r7+$15),r5
        move    x:(r6+$0),a
        bsr     vb_tab                  ; INC at +0
        move    a1,x:(r7+$16)
        move    x:(r7+$15),a
        add     #>$21,a
        move    a1,r5                   ; PERW at +33
        move    x:(r6+$0),a
        bsr     vb_tab
        move    a,x:(r7+$18)
; ---- DEP -> 8 dev, and the product p = 8 dev per / 2^18 ------------------
        move    x:(r7+$15),a
        add     #>$42,a
        move    a1,r5                   ; DEV8 at +66
        move    x:(r6+$1),a
        bsr     vb_tab
        move    a,x0                    ; 8 dev
        move    x:(r7+$18),y1           ; per / 2^18
        mpy     x0,y1,a
        move    a,x:(r7+$19)
; ---- the walk's speed limit: 1.5 dev a sample, at least 0.006 (10.4 cents) --
; A knob jump moves H, and with it the centre (2 + H), by tens of samples in
; a block; unlimited, the walk to the new knot is a pitch spike (61 % at an
; SPD 80 -> 120 step). No shape's own slope exceeds dev, so in steady state
; the limit never engages; in a jump the delay chases its knot at 1.5 dev.
        move    #>$180000,y1            ; 1.5/8 (x0 is still 8 dev)
        mpy     x0,y1,a                 ; 1.5 dev
        move    #>$00c49c,x0            ; the floor, 0.006
        cmp     x0,a
        tlt     x0,a
        asr     #$b,a,a                 ; samples a sample -> Q11.12 (/2048)
        move    a1,x:(r7+$1e)
; ---- the SHP duck (LOFI2's MODE duck) --------------------------------------
; A shape change would step the delay. The wet fades to dry over 16 blocks,
; the running shape switches only once it is fully out (e full AND the MIX
; run snapped to 0: the run lags e), the delay snaps to the new shape's knot
; on that block (unprimed, as at init), and the wet fades back.
        move    x:(r6+$c),a             ; SHP, slot 6, the knob field
        and     #>$7f0000,a
        move    a1,x0                   ; the knob's shape << 16
        move    x:(r7+$10),b            ; the running shape << 16
        move    x0,a
        sub     b,a
        beq     vb_same
        move    x:(r7+$11),a            ; e
        move    #>$7fffff,x1
        cmp     x1,a                    ; e - full
        blt     vb_rise
        move    x:(r7+$12),b            ; ... and the MIX run on 0: the wet
        tst     b                       ; is out only once the run has
        bne     vb_rise                 ; glided down and snapped
        move    x0,x:(r7+$10)           ; fully out: switch
        clr     b                       ; ... and unprime, so this block's knots
        move    b,x:(r7+$14)            ; snap: the delay moves while the wet is
        bra     vb_duckd                ; out, not after (the walk's limit would chase)
vb_rise:
        add     #>$080000,a             ; + 1/16
        cmp     x1,a
        tgt     x1,a                    ; at most full
        move    a,x:(r7+$11)
        bra     vb_duckd
vb_same:
        move    x:(r7+$11),a
        clr     b
        sub     #>$080000,a             ; - 1/16
        tlt     b,a                     ; at least 0
        move    a,x:(r7+$11)
vb_duckd:
; ---- the swing: H = min(LIM, 4 p FAC') ------------------------------------
        move    x:(r7+$10),a
        asr     #$10,a,a
        move    a1,n5                   ; the running shape, 0..3
        move    x:(r7+$15),a
        add     #>$63,a
        move    a1,r5                   ; FACW at +99
        move    x:(r7+$19),x0           ; p
        nop
        move    (r5)+n5
        move    p:(r5),y1               ; FAC' = 16 FAC / 4
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x0                    ; Ht (LIMITED: saturates at $7fffff)
        move    #>$1f4000,a             ; LIM: 500 samples, Q11.12
        cmp     x0,a                    ; LIM - Ht
        tgt     x0,a                    ; Ht < LIM: Ht
        move    a,x:(r7+$02)            ; H, at once: the walk's limit smooths it
; ---- the phase, n7 on -----------------------------------------------------
        move    x:(r7+$16),a            ; inc
        asl     #$8,a,a
        move    a,x0                    ; inc << 8
        move    n7,a
        asl     #$f,a,a
        move    a,y1                    ; n7 << 15
        mpy     x0,y1,a                 ; inc n7, an integer in a1
        move    a1,x:(r7+$17)           ; dphi
        move    x:(r7+$00),b
        move    b,x:(r7+$1f)            ; the phase at the block's start
        add     b,a
        and     #>$7fffff,a
        move    a1,x:(r7+$00)           ; the phase n7 on
; ---- the raw offsets: H F(phi), or H x for RND -----------------------------
        move    x:(r7+$10),a
        asr     #$10,a,a
        move    a1,b
        cmp     #>$3,b
        beq     vb_rnd
        move    x:(r7+$00),a            ; L: phi
        bsr     vb_shape
        move    a,x0
        move    x:(r7+$02),y1
        mpy     x0,y1,a                 ; H F
        move    a,x:(r7+$1a)
        move    x:(r6+$3),a             ; WID: R's lead, (k/128)/2 of a cycle
        and     #>$7fff00,a
        asr     #$1,a,a
        move    a1,x0
        move    x:(r7+$00),a
        add     x0,a
        and     #>$7fffff,a             ; R: phi + wid
        bsr     vb_shape
        move    a,x0
        move    x:(r7+$02),y1
        mpy     x0,y1,a
        move    a,x:(r7+$1b)
        bra     vb_slew
vb_rnd:
; a half-cycle boundary in this block: draw n1, n2 and the new pitches
        move    x:(r7+$1f),a
        move    x:(r7+$00),x0
        eor     x0,a
        and     #>$400000,a
        beq     vb_nodraw
        bsr     vb_lfsr
        move    x0,x:(r7+$1d)           ; n1
        bsr     vb_lfsr                 ; x0 = n2
        move    x0,a
        move    x:(r7+$1d),b            ; n1
        sub     b,a
        asr     #$1,a,a                 ; (n2 - n1)/2
        move    a,x0
        move    x:(r6+$3),a             ; WID: w = k/128
        and     #>$7fff00,a
        move    a1,y1
        mpy     x0,y1,a                 ; w (n2 - n1)/2
        asl     #$1,a,a
        add     b,a
        move    a,x1                    ; nR = n1 + w (n2 - n1)
        move    x:(r7+$09),a
        add     b,a
        asr     #$1,a,a
        move    a,x:(r7+$0b)            ; uL = (xL + n1)/2
        move    x:(r7+$0a),a
        add     x1,a
        asr     #$1,a,a
        move    a,x:(r7+$0c)            ; uR = (xR + nR)/2
vb_nodraw:
        move    x:(r7+$17),y1           ; dphi
        move    x:(r7+$0b),x0
        mpy     x0,y1,a                 ; uL dphi
        asl     #$2,a,a
        move    x:(r7+$09),b
        sub     a,b
        move    b,x:(r7+$09)            ; xL -= 4 uL dphi (LIMITED: |x| <= 1)
        move    x:(r7+$0c),x0
        mpy     x0,y1,a
        asl     #$2,a,a
        move    x:(r7+$0a),b
        sub     a,b
        move    b,x:(r7+$0a)
        move    x:(r7+$02),y1           ; H
        move    x:(r7+$09),x0
        mpy     x0,y1,a
        move    a,x:(r7+$1a)            ; H xL
        move    x:(r7+$0a),x0
        mpy     x0,y1,a
        move    a,x:(r7+$1b)            ; H xR
vb_slew:
; ---- SLEW: c = min(1, dphi / q), q = (k/128)/4 -----------------------------
        move    x:(r6+$2),a
        and     #>$7fff00,a
        asr     #$2,a,a
        move    a1,x0                   ; q
        move    x:(r7+$17),a            ; dphi (a clean load: a0 = 0)
        cmp     x0,a                    ; dphi - q
        bge     vb_c1
        andi    #$fe,ccr
        do      #$18,>vbdivz            ; do, not rep: stock never holds interrupts off
        div     x0,a
vbdivz:
        move    a0,x:(r7+$1c)           ; c = dphi / q
        bra     vb_cd
vb_c1:
        move    #>$7fffff,x0
        move    x0,x:(r7+$1c)           ; c = 1 (SLEW 0 always lands here)
vb_cd:
; ---- the knots: off += c (raw - off); knot = 2 + H + off -----------------
        lua     (r7+$03),r1             ; off L, off R
        lua     (r7+$1a),r3             ; raw L, raw R
        lua     (r7+$05),r4             ; delay L, delay R
        nop
        bsr     vb_knot                 ; L
        bsr     vb_knot                 ; R
; ---- MIX: the run glides 1/8 of the way to m (1 - e) a block, straight
; within it, and snaps once the distance is under 128 LSBs (MIX 0 stays exact)
        move    x:(r6+$5),a
        and     #>$7fff00,a
        move    #>$7f0000,x0
        cmp     x0,a                    ; k - 127
        move    #>$7fffff,x0
        tge     x0,a                    ; 127: the wet outright
        move    a1,x0                   ; m
        move    #>$7fffff,a
        move    x:(r7+$11),y1
        sub     y1,a
        move    a,y1                    ; 1 - e
        mpy     x0,y1,a                 ; m (1 - e)
        move    a,x1                    ; the target
        move    x:(r7+$12),b            ; the run
        sub     b,a
        move    a,y1                    ; target - run
        abs     a
        cmp     #>$80,a                 ; under 128 LSBs: snap
        bge     vb_mglide
        move    x1,x:(r7+$12)           ; the run on the target
        clr     a
        move    a,x:(r7+$13)            ; no step
        bra     vb_mixd
vb_mglide:
        move    y1,a
        asr     #$7,a,a                 ; 1/8 a block, a 16th of that a sample
        move    a,x:(r7+$13)
vb_mixd:
        move    #>$1,x0
        move    x0,x:(r7+$14)           ; primed
; ---- the sample loop -------------------------------------------------------
        move    #$1,n0                  ; (short immediate, stock's own form)
        move    x:(r7+$0e),r2           ; line L
        move    x:(r7+$0e),r6
        move    #>$400,n6
        move    (r6)+n6                 ; line R (r6, the page pointer, is not
        move    #>$3ff,m5               ; read past here: the dispatcher reloads it)
        move    x:(r7+$01),y0           ; the write phase
        do      n7,>vbloopz
; ---- advance the write phase and the MIX run -------------------------------
        move    y0,a                    ; 0..1023, so phase + 1 is 1..1024: a2 = 0
        add     #>$1,a
        and     #>$3ff,a
        move    a1,y0
        move    x:(r7+$13),x0
        move    x:(r7+$12),a
        add     x0,a
        move    a,x:(r7+$12)
; ---- L: the tap, the line write, the blend ---------------------------------
        move    x:(r7+$07),x0
        move    x:(r7+$05),a
        add     x0,a
        move    a,x:(r7+$05)            ; delay L, Q11.12
        move    r2,r5
        bsr     vb_tap
        move    a,x1                    ; tap L
        move    y0,a
        move    a1,n5
        move    r2,r5
        move    (r5)+n5                 ; line L at the write phase
        move    x:(r0),b                ; dry L
        move    b,y:(r5)                ; write line L
        move    x1,a
        sub     b,a
        asr     #$1,a,a
        move    a,x0                    ; (tap - dry)/2
        move    x:(r7+$12),y1           ; m
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)                ; dry + m (tap - dry)
; ---- R ---------------------------------------------------------------------
        move    x:(r7+$08),x0
        move    x:(r7+$06),a
        add     x0,a
        move    a,x:(r7+$06)            ; delay R
        move    r6,r5
        bsr     vb_tap
        move    a,x1                    ; tap R
        move    y0,a
        move    a1,n5
        move    r6,r5
        move    (r5)+n5                 ; line R at the write phase
        move    x:(r0+n0),b             ; dry R
        move    b,y:(r5)                ; write line R
        move    x1,a
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$12),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    (r0)+n0                 ; the frame advance: n0 is 1 for the
        move    (r0)+n0                 ; whole loop, so two steps, no reload
vbloopz:
        nop
        move    #>$ffffff,m5
        move    y0,a
        move    a1,x:(r7+$01)           ; the write phase
vb_dry:
        rts

; ---------------------------------------------------------------------------
; vb_tab -- a = a knob word, r5 -> a 33-word P table -> a = T[i] + f (T[i+1]
; - T[i]), i = bits 22-18 of the word (k >> 2), f = bits 17-8 (k & 3 and the
; LFO's fraction), Q23; a1 is the floor. Uses x0 x1 y0 y1 b n5; r5 moves.
; ---------------------------------------------------------------------------
vb_tab:
        and     #>$7fff00,a
        move    a1,x1                   ; u
        move    x1,a
        asr     #$12,a,a
        move    a1,n5                   ; i
        move    x1,a
        and     #>$03ff00,a
        asl     #$5,a,a
        move    a1,x0                   ; f
        move    (r5)+n5
        move    p:(r5)+,y0              ; T[i]
        move    p:(r5),b                ; T[i+1]
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a                 ; f (T[i+1] - T[i])
        add     y0,a
        rts

; ---------------------------------------------------------------------------
; vb_shape -- a = a phase (Q23 cycles, clean) -> a = the running periodic shape's
; normalised delay offset, -1..1 (LIMITED). Uses x0 x1 y1 b r4 n4 m4.
; ---------------------------------------------------------------------------
vb_shape:
        move    a1,x1                   ; phi
        move    x:(r7+$10),b
        tst     b
        beq     vbs_sin
        cmp     #>$10000,b
        beq     vbs_tri
; SQR: 1 - 4|v - 1/2|, v = phi + 1/4
        move    x1,a
        add     #>$200000,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a                    ; clean
        sub     #>$400000,a             ; v - 1/2
        abs     a
        asl     #$2,a,a                 ; 0 .. 2, in the guard bits
        move    #>$7fffff,b
        sub     a,b                     ; 1 - 4|v - 1/2|
        move    b,a                     ; (limited: -1 at the bottom)
        rts
vbs_tri:
; TRI: +-4u(1-u), u = 2 phi mod 1, + in the first half
        move    x1,a
        asl     #$1,a,a
        and     #>$7fffff,a
        move    a1,x0                   ; u
        move    #>$7fffff,a
        sub     x0,a
        move    a,y1                    ; 1 - u
        mpy     x0,y1,a                 ; u (1 - u), <= 1/4
        asl     #$2,a,a
        move    a,y1                    ; g = 4u(1-u) (limited)
        move    y1,a
        neg     a                       ; -g
        move    x1,b
        and     #>$400000,b             ; phi >= 1/2 ?
        teq     y1,a                    ; first half: +g
        rts
vbs_sin:
; SINE: the stock 1,024-point sine at X:0x6c00, linearly interpolated
        move    #>$3ff,m4
        move    x1,a
        asr     #$d,a,a
        move    a1,n4                   ; i = phi >> 13
        move    x1,a
        and     #>$001fff,a
        asl     #$a,a,a
        move    a1,x0                   ; f, Q23
        move    #>$6c00,r4
        nop
        nop
        move    (r4)+n4
        move    x:(r4)+,b               ; s[i]
        move    x:(r4),a                ; s[i+1] (the modulo wraps 1023 -> 0)
        sub     b,a
        move    a,y1
        mpy     x0,y1,a
        add     b,a
        move    #>$ffffff,m4
        rts

; ---------------------------------------------------------------------------
; vb_lfsr -- one draw: the 24-bit Galois LFSR (mask $e10000, maximal) stepped
; 16 times -> x0 = the state as a signed Q23, n in [-1, 1). Bit 0 is tested
; with and/tne (no carry-conditional Tcc: not a form the modules use). Uses a
; b x0 y0.
; ---------------------------------------------------------------------------
vb_lfsr:
        move    x:(r7+$0d),a
        move    #>$e10000,y0
        do      #$10,>vblfz
        move    a1,b                    ; a1, not a: A2 is stale after lsr
        and     #>$1,b                  ; Z: bit 0 clear
        move    #$0,b                   ; (a plain immediate move keeps the flags)
        tne     y0,b                    ; bit 0 set: the mask
        lsr     #$1,a
        move    b1,x0
        eor     x0,a
vblfz:
        nop
        move    a1,x:(r7+$0d)
        move    a1,x0
        rts

; ---------------------------------------------------------------------------
; vb_knot -- one channel: r1 -> its slewed offset, r3 -> its raw offset, r4
; -> its delay; the slope is at r4 + 2. off += c (raw - off) (the first
; block: off = raw); knot = 2 + H + off; the delay walks to it in 16 equal
; steps from where it is (the first block starts on it), the step limited to
; +-S. r1 r3 r4 step one.
; ---------------------------------------------------------------------------
vb_knot:
        move    x:(r7+$1c),y1           ; c
        move    x:(r3),a                ; raw
        move    x:(r1),b                ; off
        sub     b,a                     ; raw - off (|.| <= 2H < 1/2)
        move    a,x0
        mpy     x0,y1,a
        add     b,a                     ; off + c (raw - off)
        move    x:(r7+$14),b
        tst     b
        move    x:(r3)+,b
        teq     b,a                     ; the first block: off = raw
        move    a,x:(r1)+
        move    x:(r7+$02),b            ; H
        add     #>$2000,b               ; + 2 samples
        add     a,b                     ; the knot
        move    #>$2000,x0              ; never under 2 samples (a shrinking H
        cmp     x0,b                    ; under a slewed offset could reach it)
        tlt     x0,b
        move    #>$3f8000,x0            ; never over 1,016
        cmp     x0,b
        tgt     x0,b
        move    x:(r7+$14),a
        tst     a
        move    x:(r4),a                ; the delay now (moves keep the flags)
        teq     b,a                     ; the first block: on the knot
        move    a,x:(r4)
        sub     a,b
        add     #>$8,b                  ; rounded: a floor leaves the walk 8 LSB short
        asr     #$4,b,b                 ; the slope per sample
        move    x:(r7+$1e),x0           ; ... limited to +-S
        cmp     x0,b
        tgt     x0,b
        move    x:(r7+$1e),a
        neg     a
        move    a,x0
        cmp     x0,b
        tlt     x0,b
        move    b,x:(r4+$2)
        move    (r4)+
        rts

; ---------------------------------------------------------------------------
; vb_tap -- modulation's mo_tap: a = the delay in Q11.12, y0 = the write
; phase, r5 = the line's base (m5 = $3ff) -> a = the tap, the fraction
; blended toward the OLDER neighbour. Uses x0 y1 b n5. Straight-line.
; ---------------------------------------------------------------------------
vb_tap:
        move    a,x0                    ; the total (positive, under 1: not limited)
        move    x0,a                    ; clean: a0 = 0
        and     #>$fff,a
        asl     #$b,a,a                 ; the fraction, Q23
        move    a1,y1
        move    x0,a
        asr     #$c,a,a
        move    a1,x0                   ; i
        move    y0,a                    ; the write phase
        sub     x0,a
        and     #>$3ff,a                ; (a2 may be stale: a1 is what is read)
        move    a1,n5
        move    (r5)+n5                 ; -> delay i
        move    y:(r5)-,b               ; t0; the modulo steps r5 to delay i + 1
        move    y:(r5),a                ; t1
        sub     b,a                     ; t1 - t0
        move    a,x0
        mpy     x0,y1,a                 ; f (t1 - t0)
        add     b,a
        rts
