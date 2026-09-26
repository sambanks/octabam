; ---------------------------------------------------------------------------
; MODULATION -- a modulation pedal: JUNO, DIM, FLNG, COMB, PHSR, each a
; transcription of the source modules/modulation/modulation_ref.py names
; (docs/effects/PORTS.md), proven against that float reference. Three sample
; loops, one chosen per block: LINE (JUNO, DIM and FLNG differ only in five
; per-block mix weights bl bd ff kc kb), PHSR, COMB. Insert contract
; (modules/ripple/ripple_svf.asm). FX1 only: init reads the allocator base
; (X:0x213 -> this instance's entry, valid at init and nowhere else); a base
; >= 0x4000 is an FX2 slot and proc runs the dry path, which writes nothing
; to Y. Two 1,024-word lines (L, R) out of the FX1 slot's 3,072; the read
; offset is masked, not the address. MIX 0 is an exact passthrough; a
; change of MODE clears the walk, $23..$3f ($20, $21, $41 and the lines
; persist).
;
; The r7 block:
;   $00..$0b   per block: MIX, LFO inc, DLY centre, DPTH, FDBK, TONE c, WDTH,
;              bl bd ff kc kb (the LINE weights)
;   $0c        the mode 0..4; $0d the FX2 flag (init); $0e the line base
;              (init); $0f the P table base
;   $10..$1e   PHSR per block: u, bm/dbm/bf/dbf L and R, v L, fb, w2 w4 w6 w8;
;              COMB per block: gain $1a, h0 $1b, h1 $1c, polarity $1d,
;              period $1e; PHSR's v R at $1f
;   $20        the line write phase (persistent)
;   $21        the LFO phase (persistent)
;   $23..$3f   the per-sample walk on r3, cleared on a MODE change: LINE
;              $23..$2d, PHSR $25..$3f (y previous L/R at $23/$24, the ramps'
;              block copies at $25/$26 and $33/$34), COMB $23..$39
;   $40        the last block's MODE select word
;   $41        the LOFI hold counter (persistent)
;   $42        the LOFI hold length; $45 its mask; $46 the TONE knob word;
;              $47 mo_para's park (per block)
;   $48..$69   the block's constant stream on r4/r1: LINE 34 words, PHSR 18,
;              COMB 16 (each loop's header lists the order)
;   $22, $43, $44, $6a..$83 free
; init zeroes $11..$46 and, on FX1, the lines.
; ---------------------------------------------------------------------------

init:
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
        move    b,x:(r7+$0d)
        tst     b
        bne     monoclr                 ; FX2: never touch the buffer at all
; ---- clear both lines, once, at instantiation ----------------------------
        move    x:(r7+$0e),a
        move    a,r5
        move    #>$ffffff,m5
        clr    a
        do      #2048,>moclrz
        move    a,y:(r5)+
moclrz:
        nop
monoclr:
; ---- every persistent slot to zero (verify_dirtystate) -------------------
        clr     a
        move    r7,r5
        move    #>$ffffff,m5
        move    #$11,n5
        move    (r5)+n5                 ; $11 .. $46
        do      #54,>moiclz
        move    a,x:(r5)+
moiclz:
        nop
        rts

; ===========================================================================
proc:
; ===========================================================================
; PER-BLOCK KNOB DECODE
; ===========================================================================
        move    #>$ffffff,m5
; MIX (page-1 slot 5, bottom right on every effect); 127 = 1.0, the wet
; outright (the through-zero null is exact)
        move    x:(r6+$5),a
        move    #>$7f0000,x0
        cmp     x0,a                    ; k - 127
        move    #>$7fffff,x0
        tge     x0,a
        move    a,x:(r7+$00)
; LFO increment: RATE^2 * $780 + $10 per sample (~0.08 .. 10 Hz)
        move    x:(r6+$0),x0
        move    x:(r6+$0),y1
        mpy     x0,y1,a
        move    a,x0
        move    #>$780,y1
        mpy     x0,y1,a
        add     #>$10,a
        move    a,x:(r7+$01)
; WDTH (page-2 slot 8, $d's knob field, bits 16-23) -> the right channel's
; LFO phase offset, 0 .. half a cycle
        move    x:(r6+$d),a             ; a knob word: bit 23 clear, so a2 = 0
        and     #>$7f0000,a             ; ... and stays 0 through the and
        asr     #$1,a,a
        move    a,x:(r7+$06)
; TONE (page-2 slot 7, $c's companion field, bits 8-15) -> the one-pole
; coefficient 0.25 + 0.75 * k/128; 127 = 1.0, an exact bypass (the
; flanger's through-zero null needs the blend and the wet alike). The knob
; word is parked in $46 (COMB's FIR reads it below).
; TONE GLIDES (26 Sep 2026): the parked word moves 1/32 of the way to the
; knob per block and snaps to it when the step rounds to nothing, so c
; and COMB's FIR glide with it (tools/verify/verify_knob_clicks.py); the
; first block after init ($43 = 0) starts it at the knob.
        move    x:(r7+$43),b            ; 0 until the first block is done
        move    x:(r6+$c),a
        and     #>$7f00,a
        asl     #$8,a,a
        move    a1,y1                   ; TONE << 16, the knob
        tst     b
        move    x:(r7+$46),a            ; the glide (moves keep the flags)
        teq     y1,a                    ; the first block: at the knob
        move    a,x0
        move    y1,a
        sub     x0,a
        asr     #$5,a,a
        add     x0,a
        cmp     x0,a                    ; no progress: at the knob
        teq     y1,a
        move    a,x:(r7+$46)            ; TONE << 16, glided
        move    a,x0
        move    #$60,y1                 ; 0.75 (short immediate: bits 23-16)
        mpy     x0,y1,a
        add     #>$200000,a             ; + 0.25
        move    x:(r7+$46),b
        move    #>$7f0000,x0
        cmp     x0,b                    ; k - 127
        move    #>$7fffff,x0
        tge     x0,a                    ; k >= 127: open
        move    a,x:(r7+$05)
; FDBK (page-1 slot 3) -> bipolar, (k - 64)/64: -1 .. +0.984, glided as
; TONE is, 1/128 per block ($04 is the glide)
        move    x:(r6+$3),a
        sub     #>$400000,a             ; k/128 - 0.5
        asl     #$1,a,a
        move    a,y1
        move    x:(r7+$43),b
        tst     b
        move    x:(r7+$04),a
        teq     y1,a
        move    a,x0
        move    y1,a
        sub     x0,a
        asr     #$7,a,a                 ; 1/128 per block
        add     x0,a
        cmp     x0,a
        teq     y1,a
        move    a,x:(r7+$04)
; DLY (page-1 slot 2) -> the centre delay in Q11.12 samples, 8 .. 1,000
        move    x:(r6+$2),a
        and     #>$7f0000,a
        move    a1,x0                   ; (a knob word, non-negative)
; $3e0000 IS 992*4096, so the product already lands in Q11.12 (no shift)
        move    #$3e,y1                 ; 992 samples, pre-scaled to Q11.12
        mpy     x0,y1,a
        add     #>$8000,a               ; + 8 samples of floor
        move    #>$3e8000,x0            ; 1,000 samples
        cmp     x0,a
        tgt     x0,a
        move    a,x:(r7+$02)
; DPTH -> the sweep depth in Q11.12 samples, clamped so the read stays inside
; the line: <= centre - 8 and <= 1,015 - centre
        move    a,b
        move    #>$8000,x0
        sub     x0,b                    ; centre - 8
        move    b,x1
        move    #>$3f7000,b             ; 1,015 samples
        sub     a,b                     ; 1,015 - centre
        move    x:(r6+$1),x0
        move    #$1e,y1                 ; 480 samples, pre-scaled to Q11.12
        mpy     x0,y1,a
        cmp     x1,a
        tgt     x1,a                    ; depth <= centre - 8
        move    b,x1
        cmp     x1,a                    ; nothing between: the flag trap
        tgt     x1,a                    ; depth <= 1,015 - centre
        move    a,x:(r7+$03)
; the P table base (rewritten by build_bus.py; the literal appears ONCE)
        move    #>$fab1e0,r5
        move    r5,x:(r7+$0f)
; LOFI (page-1 slot 4): the hold length 1 + 64 (k/128)^2
; samples (an integer in $42; 17 at 64, 64 at 127) and the bit mask from the
; 16-word table at P + 132 on k >> 3 ($45); k = 0 is hold 1 and a full
; mask: bit-exact (verify_modulation)
        move    x:(r6+$4),a
        and     #>$7f0000,a
        move    a1,x0
        move    a1,y1
        mpy     x0,y1,a                 ; (k/128)^2, Q23
        asr     #$11,a,a                ; x 64: an integer 0..63
        add     #>$1,a
        move    a1,x:(r7+$42)
        move    x:(r6+$4),a
        and     #>$7f0000,a
        asr     #$13,a,a                ; k >> 3: 0..15
        move    x:(r7+$0f),r5
        move    #$84,n5                 ; 4 x 33 words in front of the masks
        move    (r5)+n5
        move    a1,n5
        move    (r5)+n5
        move    p:(r5),x0
        move    x0,x:(r7+$45)
; ---- MODE (slot 6 select of r6+$c, the knob field) ------------------------
; A change of mode clears the walk $23..$3f: a state that meant something
; else in the last mode is garbage in this one.
        move    x:(r6+$c),a
        and     #>$ff0000,a
        move    x:(r7+$40),x0           ; the last block's select ($40: above
        move    a1,x:(r7+$40)           ; the loops' slots, per block only)
        sub     x0,a                    ; (a2 = 0: both positive)
        beq     mo_msame
        clr     a
        move    r7,r5
        move    #$23,n5
        move    (r5)+n5
        do      #29,>mo_mclr
        move    a,x:(r5)+
mo_mclr:
        nop
        move    a,x:(r7+$43)            ; the new mode's run words at their targets
mo_msame:
        move    x:(r7+$40),a
        asr     #$10,a,a
        move    a1,x0
        move    x0,a                    ; the mode, 0..4, clean
        move    a,x:(r7+$0c)
; ---- the dry path: an FX2 slot, or MIX at zero ---------------------------
        move    x:(r7+$0d),a            ; the FX2 flag from init
        tst     a
        bne     mo_dry
; MIX RAMPS (26 Sep 2026): the loops mix at a run value ($22) stepped once
; per sample 1/1024 of the way to MIX (mo_rset; the step is each stream's
; last word, parked in $44), so the dry path waits for the run to land on 0
        move    r7,r1
        move    #$22,n1
        move    (r1)+n1
        move    r7,r3
        move    #$44,n3
        move    (r3)+n3
        move    #>$ffffff,m1
        move    #>$ffffff,m3
        move    x:(r7+$00),y1           ; MIX
        bsr     mo_rset
        move    x:(r7+$00),a
        move    x:(r7+$22),x0
        or      x0,a                    ; MIX 0 and the run on it
        beq     mo_dry
; ---- dispatch, once per block ---------------------------------------------
        move    x:(r7+$0c),a
        cmp     #>$1,a
        beq     mo_bdim
        cmp     #>$2,a
        beq     mo_bflng
        cmp     #>$3,a
        beq     mo_bcomb
        cmp     #>$4,a
        beq     mo_bphsr
; JUNO (and any stored value past 4): bl 0, bd 0, ff 1, kc 0, kb 0
        clr     a
        move    #>$7fffff,x0
        move    a,x:(r7+$07)
        move    a,x:(r7+$08)
        move    x0,x:(r7+$09)
        move    a,x:(r7+$0a)
        move    a,x:(r7+$0b)
        bra     mo_line
mo_bdim:
; DIM: bl 0, bd 1, ff 0.25, kc -1, kb 0.5 (OURS: the SDD-320's amounts are
; unpublished; the highpass and the lift's lowpass are one-poles at 200 Hz),
; all x 0.398: the -8 dB trim that levels it with JUNO at the views
        clr     a
        move    a,x:(r7+$07)
        move    #>$32f52d,x0            ; 0.398
        move    x0,x:(r7+$08)
        move    #>$0cbd4b,x0            ; 0.0995
        move    x0,x:(r7+$09)
        move    #>$cd0ad3,x0            ; -0.398
        move    x0,x:(r7+$0a)
        move    #>$197a96,x0            ; 0.199
        move    x0,x:(r7+$0b)
        bra     mo_line
mo_bflng:
; FLNG: bl 0.7071, bd 0, ff -0.7071, kc 0, kb 0 (Dattorro Table 6); bl and
; ff x 0.447, the -7 dB trim (the feedback is FDBK's, untrimmed)
        clr     a
        move    #>$286dc6,x0            ; 0.7071 x 0.447
        move    x0,x:(r7+$07)
        move    a,x:(r7+$08)
        move    #>$d7923a,x0            ; -0.7071 x 0.447
        move    x0,x:(r7+$09)
        move    a,x:(r7+$0a)
        move    a,x:(r7+$0b)
        bra     mo_line

; ===========================================================================
; THE LINE LOOP -- JUNO, DIM, FLNG: two lines, one triangle LFO
;   wet_L = bl*fixed_L + bd*dry_L + ff*LPo(tap_L) + kc*HP(LPo(tap_R)) + kb*LPb(dry_L)
;   line_L <- LPi(dry_L) + fb*tap_L ; R mirrored.
; ===========================================================================
mo_line:
        move    #$1,n0                  ; (short immediate, stock's own form)
; Pointer-addressed (22 Sep 2026). The block's constants in a stream at $48
; (r4), in the order the sample reads them: inc wid | depth centre c fb hold
; mask c | depth centre c fb mask c | i f bl bd ff c200 kc c200 kb | the same
; for R | m. The states walk from $23 on r3: lpi L, latch L, lpo L, lpi R,
; latch R, lpo R, hp L, lpb L, wet L, hp R, lpb R. r2/r6 = the lines' bases,
; y0 = the write phase, n4 = the LFO phase, n1 = the LOFI counter, n2/n6 =
; the taps and then the LPo outputs. r6 (the page pointer) is not read past
; here: the dispatcher reloads it.
        move    r7,r4
        move    #$48,n4
        move    (r4)+n4
        move    #>$ffffff,m4
        move    r4,r1
        move    #>$ffffff,m1
        move    x:(r7+$01),x0
        move    x0,x:(r1)+              ; inc
; wid, depth and centre are RUN values stepped once per sample (the loop's
; head) 1/1024 of the way to this block's WDTH, DPTH and DLY (26 Sep 2026;
; steps at $10..$12); the R tap reads L's depth and centre, and both fixed
; taps read the centre and split it per sample (mo_tap), so no tap moves
; in one step at a block edge
        move    r7,r3
        move    #$10,n3
        move    (r3)+n3
        move    x:(r7+$06),y1
        bsr     mo_rset                 ; wid
        move    x:(r7+$03),y1
        bsr     mo_rset                 ; depth
        move    x:(r7+$02),y1
        bsr     mo_rset                 ; centre
        move    x:(r7+$05),x0
        move    x0,x:(r1)+
        move    x:(r7+$04),x0
        move    x0,x:(r1)+
        move    x:(r7+$42),x0
        move    x0,x:(r1)+
        move    x:(r7+$45),x0
        move    x0,x:(r1)+
        move    x:(r7+$05),x0
        move    x0,x:(r1)+
        move    x:(r7+$05),x0
        move    x0,x:(r1)+
        move    x:(r7+$04),x0
        move    x0,x:(r1)+
        move    x:(r7+$45),x0
        move    x0,x:(r1)+
        move    x:(r7+$05),x0
        move    x0,x:(r1)+
        move    #>$039912,y0            ; c200 = 0.0281
        move    x:(r7+$07),x0
        move    x0,x:(r1)+
        move    x:(r7+$08),x0
        move    x0,x:(r1)+
        move    x:(r7+$09),x0
        move    x0,x:(r1)+
        move    y0,x:(r1)+
        move    x:(r7+$0a),x0
        move    x0,x:(r1)+
        move    y0,x:(r1)+
        move    x:(r7+$0b),x0
        move    x0,x:(r1)+
        move    x:(r7+$07),x0
        move    x0,x:(r1)+
        move    x:(r7+$08),x0
        move    x0,x:(r1)+
        move    x:(r7+$09),x0
        move    x0,x:(r1)+
        move    y0,x:(r1)+
        move    x:(r7+$0a),x0
        move    x0,x:(r1)+
        move    y0,x:(r1)+
        move    x:(r7+$0b),x0
        move    x0,x:(r1)+
        move    x:(r7+$44),x0           ; MIX's step
        move    x0,x:(r1)+
        move    #>$1,x0
        move    x0,x:(r7+$43)           ; primed
        move    x:(r7+$0e),r2
        move    #>$ffffff,m2
        move    x:(r7+$0e),r6
        move    #>$400,n6
        move    (r6)+n6
        move    #>$ffffff,m6
        move    #>$ffffff,m3
        move    x:(r7+$20),y0
        move    x:(r7+$21),a
        move    a1,n4
        move    x:(r7+$41),a
        move    a1,n1
        do      n7,>molinz
        move    r4,r1
        move    (r1)+                   ; inc
        move    x:(r7+$10),x0
        move    x:(r1),a
        add     x0,a
        move    a,x:(r1)+               ; wid
        move    x:(r7+$11),x0
        move    x:(r1),a
        add     x0,a
        move    a,x:(r1)+               ; depth
        move    x:(r7+$12),x0
        move    x:(r1),a
        add     x0,a
        move    a,x:(r1)+               ; centre
        move    r4,r1
        move    r7,r3
        move    #$23,n3
        move    (r3)+n3
; ---- advance the write phase ----------------------------------------------
        move    y0,a                    ; 0..1023, so phase + 1 is 1..1024: a2 = 0
        add     #>$1,a
        and     #>$3ff,a
        move    a1,y0                   ; a1 straight over: no limiter
; ---- the two triangles: a = lfo L, x1 = lfo R ------------------------------
; The stream gives inc then wid; the phase (n4) advances once and the right
; channel reads it WID further round. tri = 4 |phase - 0.5| - 1.
        move    n4,a
        move    x:(r1)+,x0              ; inc
        add     x0,a                    ; phase <= $7fffff + inc <= $790: no carry
        and     #>$7fffff,a             ; into a2, which stays 0 through the and
        move    a1,n4
        move    x:(r1)+,x0              ; wid
        add     x0,a                    ; (< 2^24: a2 = 0 through the and)
        and     #>$7fffff,a
        move    #$40,y1                 ; 0.5 (short immediate: bits 23-16)
        sub     y1,a
        abs     a                       ; 0 .. 0.5
        asl     #$2,a,a                 ; 0 .. 2, in the guard bits
        move    #>$7fffff,x0
        sub     x0,a                    ; -1 .. 1
        move    a,x1                    ; LIMITING: lfo R
        move    n4,a
        sub     y1,a
        abs     a
        asl     #$2,a,a
        sub     x0,a                    ; lfo L
; ---- L: the swept tap ----------------------------------------------------
        move    a,x0                    ; lfo L
        move    x:(r1)+,y1              ; depth, Q11.12
        mpy     x0,y1,a x:(r1)+,x0      ; the sweep, Q11.12 signed; centre
        add     x0,a
        move    r2,r5                   ; line L
        bsr     mo_tap
        move    a,n2                    ; tap L
; ---- the line write L: LPi(dry) + fb*tap, a LIMITING store -----------------
        move    x:(r0),a           ; dry L
        move    x:(r3),b                ; lpi L
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r1)+,y1              ; c
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r3)+
        move    a,b                     ; (limited: an accumulator-to-accumulator
                                        ; MOVE goes through the limiter; TFR would not)
        move    n2,x0                   ; tap L
        move    x:(r1)+,y1              ; fb
        mpy     x0,y1,a
        add     b,a
        move    a,x0                    ; LIMITING: the loop cannot rail
        move    y0,a
        move    a1,n5
        move    r2,r5
        move    (r5)+n5                 ; line L at the write phase
        move    x0,a
; ---- mo_lofl, inline (23 Sep 2026; three sites each, FREE allows it) ----
        move    a,y1
        move    n1,a
        move    x:(r1)+,x0              ; the hold length
        add     #>$1,a
        cmp     x0,a
        move    #$0,x0                  ; (a plain immediate move keeps the flags)
        tge     x0,a
        move    a1,n1
        move    x:(r3),a
        tge     y1,a
        move    a,x:(r3)+
        move    x:(r1)+,x0              ; the mask
        and     x0,a
        move    a,y:(r5)                ; write line L
; ---- LPo L: wo L ---------------------------------------------------------
        move    n2,a                    ; tap L
        move    x:(r3),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r1)+,y1              ; c
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r3)+
        move    a,n2                    ; wo L
; ---- R: the swept tap ----------------------------------------------------
        move    x1,x0                   ; lfo R
        move    x:(r4+$2),y1            ; depth, Q11.12 (L's run value)
        mpy     x0,y1,a                 ; the sweep, Q11.12 signed
        move    x:(r4+$3),x0            ; centre (L's run value)
        add     x0,a
        move    r6,r5                   ; line R
        bsr     mo_tap
        move    a,n6                    ; tap R
; ---- the line write R: LPi(dry) + fb*tap, a LIMITING store -----------------
        move    x:(r0+n0),a        ; dry R
        move    x:(r3),b                ; lpi R
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r1)+,y1              ; c
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r3)+
        move    a,b                     ; (limited: an accumulator-to-accumulator
                                        ; MOVE goes through the limiter; TFR would not)
        move    n6,x0                   ; tap R
        move    x:(r1)+,y1              ; fb
        mpy     x0,y1,a
        add     b,a
        move    a,x0                    ; LIMITING: the loop cannot rail
        move    y0,a
        move    a1,n5
        move    r6,r5
        move    (r5)+n5                 ; line R at the write phase
        move    x0,a
; ---- mo_lofr, inline (23 Sep 2026; three sites each, FREE allows it) ----
        move    a,y1
        move    n1,a
        tst     a
        move    x:(r3),a
        teq     y1,a
        move    a,x:(r3)+
        move    x:(r1)+,x0
        and     x0,a
        move    a,y:(r5)                ; write line R
; ---- LPo R: wo R ---------------------------------------------------------
        move    n6,a                    ; tap R
        move    x:(r3),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r1)+,y1              ; c
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r3)+
        move    a,n6                    ; wo R
; ---- wet L = bl*fixed + bd*dry + ff*wo + kc*HP(wo of the other side) + kb*LPb(dry)
        move    x:(r4+$3),a             ; the fixed tap at the centre's run
        move    r2,r5                   ; value (read after this sample's
        bsr     mo_tap                  ; write: a delay >= 8 never sees it)
        move    a,x0                    ; fixed L
        move    x:(r1)+,y1              ; bl
        mpy     x0,y1,a x:(r0),x0       ; dry L
        move    x:(r1)+,y1              ; bd
        mac     x0,y1,a
        move    n2,x0                   ; wo L
        move    x:(r1)+,y1              ; ff
        mac     x0,y1,a
        move    a,x1                    ; the sum so far (limited)
; HP(wo of the other side): s += c200*(x - s); hp = x - s
        move    n6,a
        move    x:(r3),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r1)+,y1              ; c200 = 0.0281
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r3)+
        move    n6,b
        sub     a,b                     ; hp
        move    b,x0
        move    x:(r1)+,y1              ; kc
        mpy     x0,y1,a
        add     x1,a
        move    a,x1
; LPb(dry)
        move    x:(r0),a
        move    x:(r3),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r1)+,y1              ; c200
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r3)+
        move    a,x0
        move    x:(r1)+,y1              ; kb
        mpy     x0,y1,a
        add     x1,a
        move    a,x:(r3)+               ; wet L (limited)
; ---- wet R = bl*fixed + bd*dry + ff*wo + kc*HP(wo of the other side) + kb*LPb(dry)
        move    x:(r4+$3),a             ; the fixed tap at the centre
        move    r6,r5
        bsr     mo_tap
        move    a,x0                    ; fixed R
        move    x:(r1)+,y1              ; bl
        mpy     x0,y1,a x:(r0+n0),x0    ; dry R
        move    x:(r1)+,y1              ; bd
        mac     x0,y1,a
        move    n6,x0                   ; wo R
        move    x:(r1)+,y1              ; ff
        mac     x0,y1,a
        move    a,x1                    ; the sum so far (limited)
; HP(wo of the other side): s += c200*(x - s); hp = x - s
        move    n2,a
        move    x:(r3),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r1)+,y1              ; c200 = 0.0281
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r3)+
        move    n2,b
        sub     a,b                     ; hp
        move    b,x0
        move    x:(r1)+,y1              ; kc
        mpy     x0,y1,a
        add     x1,a
        move    a,x1
; LPb(dry)
        move    x:(r0+n0),a
        move    x:(r3),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r1)+,y1              ; c200
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r3)+
        move    a,x0
        move    x:(r1)+,y1              ; kb
        mpy     x0,y1,a
        add     x1,a
        move    #$3,n3                  ; wet L is three back from the cursor
; ---- momixs, inline (23 Sep 2026; three sites each, FREE allows it) ----
        move    a,x1                    ; wet R (limited)
        move    (r3)-n3
        move    x:(r3),a                ; wet L
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$22),a            ; m, the run value
        move    x:(r1)+,y1              ; its step
        add     y1,a
        move    a,x:(r7+$22)
        move    a,y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        move    x1,a
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a                 ; (y1 = m still)
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    (r0)+n0                 ; the frame advance: n0 is 1 for the
        move    (r0)+n0                 ; whole loop, so two steps, no reload
molinz:
        nop
        move    y0,a
        move    a1,x:(r7+$20)           ; the write phase
        move    n4,a
        move    a1,x:(r7+$21)           ; the LFO phase
        move    n1,a
        move    a1,x:(r7+$41)           ; the LOFI counter
        rts

; ===========================================================================
; PHSR -- ChowPhaser: the per-block LFO and tables, then the loop
; ===========================================================================
mo_bphsr:
; the LFO advances a block at a time here (15 inc); L and R from the
; parabola; v = DPTH * lfo (-1..1) is the LDR's input
        move    x:(r7+$21),a
        move    x:(r7+$01),x0
        do      #15,>mo_padv
        add     x0,a
mo_padv:
        nop
        and     #>$7fffff,a
        move    a1,x:(r7+$21)
        bsr     mo_para
        move    a,x0
        move    x:(r6+$1),y1            ; DPTH
        mpy     x0,y1,a
        move    a,x:(r7+$19)            ; v L
        move    x:(r7+$21),a
        move    x:(r7+$06),x0
        add     x0,a
        and     #>$7fffff,a
        bsr     mo_para
        move    a,x0
        move    x:(r6+$1),y1
        mpy     x0,y1,a
        move    a,x:(r7+$1f)            ; v R
; L: u = (v + 1)/2 -> the two tables -> the ramps toward them
        move    x:(r7+$19),a
        asr     #$1,a,a
        add     #>$400000,a
        move    a,x:(r7+$10)
        move    #$0,n5                  ; the mod table
        bsr     mo_tab
        move    x:(r7+$11),x0           ; bm run L
        sub     x0,a
        asr     #$4,a,a
        move    a,x:(r7+$12)            ; dbm L
        move    x:(r7+$10),a
        move    #$21,n5                 ; the feedback table
        bsr     mo_tab
        move    x:(r7+$13),x0
        sub     x0,a
        asr     #$4,a,a
        move    a,x:(r7+$14)            ; dbf L
; R
        move    x:(r7+$1f),a
        asr     #$1,a,a
        add     #>$400000,a
        move    a,x:(r7+$10)
        move    #$0,n5
        bsr     mo_tab
        move    x:(r7+$15),x0
        sub     x0,a
        asr     #$4,a,a
        move    a,x:(r7+$16)            ; dbm R
        move    x:(r7+$10),a
        move    #$21,n5
        bsr     mo_tab
        move    x:(r7+$17),x0
        sub     x0,a
        asr     #$4,a,a
        move    a,x:(r7+$18)            ; dbf R
; the feedback, clamped to +-0.95
        move    x:(r7+$04),a
        move    #>$79999a,x0            ; 0.95
        cmp     x0,a
        tgt     x0,a
        move    #>$866666,x0            ; -0.95
        cmp     x0,a
        tlt     x0,a
        move    a,x:(r7+$1a)
; STGS on DLY: the tap weights for 2 / 4 / 6 / 8 stages by quarters. Only one
; is set (0.794, the trim); the loop sums all four (branch-free). $1b w2  $1c w4  $1d w6  $1e w8
        clr     a
        move    a,x:(r7+$1b)
        move    a,x:(r7+$1c)
        move    a,x:(r7+$1d)
        move    a,x:(r7+$1e)
        move    x:(r6+$2),a             ; DLY (page-1 slot 2)
        and    #>$7f0000,a
        asr     #$15,a,a                ; DLY >> 5: 0..3
        move    a1,n5
        move    r7,r5
        move    (r5)+n5
        move    #$1b,n5
        move    (r5)+n5
        move    #>$65ac8c,x0            ; 0.794: the -2 dB trim
        move    x0,x:(r5)
; ---- the loop --------------------------------------------------------------
; Pointer-addressed (22 Sep 2026). The stream at $48 (r4): dbm dbf fb w2 w4
; w6 w8 hold mask | dbm dbf fb w2 w4 w6 w8 mask | m. The walk from $25 on
; r3, per channel: bm bf, the two feedback stages, the eight mod stages, the
; LOFI latch, then (L only) the wet. The ramps' states are copied into the
; walk for the block and back after it; y previous in n2/n6 (their slots
; $23/$24), the LOFI counter in n1.
        move    #$1,n0
        move    r7,r4
        move    #$48,n4
        move    (r4)+n4
        move    #>$ffffff,m4
        move    r4,r1
        move    #>$ffffff,m1
        move    x:(r7+$12),x0
        move    x0,x:(r1)+
        move    x:(r7+$14),x0
        move    x0,x:(r1)+
        move    x:(r7+$1a),x0
        move    x0,x:(r1)+
        move    x:(r7+$1b),x0
        move    x0,x:(r1)+
        move    x:(r7+$1c),x0
        move    x0,x:(r1)+
        move    x:(r7+$1d),x0
        move    x0,x:(r1)+
        move    x:(r7+$1e),x0
        move    x0,x:(r1)+
        move    x:(r7+$42),x0
        move    x0,x:(r1)+
        move    x:(r7+$45),x0
        move    x0,x:(r1)+
        move    x:(r7+$16),x0
        move    x0,x:(r1)+
        move    x:(r7+$18),x0
        move    x0,x:(r1)+
        move    x:(r7+$1a),x0
        move    x0,x:(r1)+
        move    x:(r7+$1b),x0
        move    x0,x:(r1)+
        move    x:(r7+$1c),x0
        move    x0,x:(r1)+
        move    x:(r7+$1d),x0
        move    x0,x:(r1)+
        move    x:(r7+$1e),x0
        move    x0,x:(r1)+
        move    x:(r7+$45),x0
        move    x0,x:(r1)+
        move    x:(r7+$44),x0           ; MIX's step
        move    x0,x:(r1)+
        move    #>$1,x0
        move    x0,x:(r7+$43)           ; primed
        move    #>$ffffff,m3
        move    x:(r7+$11),x0           ; bm L
        move    x0,x:(r7+$25)
        move    x:(r7+$13),x0           ; bf L
        move    x0,x:(r7+$26)
        move    x:(r7+$15),x0           ; bm R
        move    x0,x:(r7+$33)
        move    x:(r7+$17),x0           ; bf R
        move    x0,x:(r7+$34)
        move    x:(r7+$23),a
        move    a1,n2
        move    x:(r7+$24),a
        move    a1,n6
        move    x:(r7+$41),a
        move    a1,n1
        do      n7,>mophsz
        move    r4,r1
        move    r7,r3
        move    #$25,n3
        move    (r3)+n3
; ===== channel L =====
        move    x:(r3),a                ; the ramps
        move    x:(r1)+,x0              ; dbm
        add     x0,a
        move    a,x:(r3)+
        move    a,y0                    ; bm (limited)
        move    x:(r3),a
        move    x:(r1)+,x0              ; dbf
        add     x0,a
        move    a,x:(r3)+
        move    a,x1                    ; bf (limited)
        move    n2,x0                   ; y previous (halved, as the chain runs)
        move    x:(r1)+,y1              ; fb
        mpy     x0,y1,a
        move    x:(r0),b           
        asr     #$1,b,b
        add     b,a                     ; u = x/2 + fb * yprev: the chain runs at
        move    a,x0                    ; HALF scale (an allpass cascade peaks
                                        ; above its input; the stores clamp at 1)
        move    x1,y1                   ; bf
        bsr     mo_apst                 ; the feedback stages
        bsr     mo_apst
        move    x0,n2                   ; the feedback section's output
        move    y0,y1                   ; bm
        clr     b                       ; the tap sum
        bsr     mo_apst                 ; the mod stages
        bsr     mo_apst
        move    x:(r1)+,y1              ; w2
        mac     x0,y1,b
        move    b,x1
        move    x1,b                    ; the sum, limited and clean
        move    y0,y1                   ; bm
        bsr     mo_apst
        bsr     mo_apst
        move    x:(r1)+,y1              ; w4
        mac     x0,y1,b
        move    b,x1
        move    x1,b                    ; the sum, limited and clean
        move    y0,y1                   ; bm
        bsr     mo_apst
        bsr     mo_apst
        move    x:(r1)+,y1              ; w6
        mac     x0,y1,b
        move    b,x1
        move    x1,b                    ; the sum, limited and clean
        move    y0,y1                   ; bm
        bsr     mo_apst
        bsr     mo_apst
        move    x:(r1)+,y1              ; w8
        mac     x0,y1,b
        asl     #$1,b,b                 ; back to full scale
        move    b,x1                    ; wet L (limited)
        move    x1,a
; ---- mo_lofl, inline (23 Sep 2026; three sites each, FREE allows it) ----
        move    a,y1
        move    n1,a
        move    x:(r1)+,x0              ; the hold length
        add     #>$1,a
        cmp     x0,a
        move    #$0,x0                  ; (a plain immediate move keeps the flags)
        tge     x0,a
        move    a1,n1
        move    x:(r3),a
        tge     y1,a
        move    a,x:(r3)+
        move    x:(r1)+,x0              ; the mask
        and     x0,a
        move    a,x:(r3)+               ; wet L
; ===== channel R =====
        move    x:(r3),a                ; the ramps
        move    x:(r1)+,x0              ; dbm
        add     x0,a
        move    a,x:(r3)+
        move    a,y0                    ; bm (limited)
        move    x:(r3),a
        move    x:(r1)+,x0              ; dbf
        add     x0,a
        move    a,x:(r3)+
        move    a,x1                    ; bf (limited)
        move    n6,x0                   ; y previous (halved, as the chain runs)
        move    x:(r1)+,y1              ; fb
        mpy     x0,y1,a
        move    x:(r0+n0),b        
        asr     #$1,b,b
        add     b,a                     ; u = x/2 + fb * yprev: the chain runs at
        move    a,x0                    ; HALF scale (an allpass cascade peaks
                                        ; above its input; the stores clamp at 1)
        move    x1,y1                   ; bf
        bsr     mo_apst                 ; the feedback stages
        bsr     mo_apst
        move    x0,n6                   ; the feedback section's output
        move    y0,y1                   ; bm
        clr     b                       ; the tap sum
        bsr     mo_apst                 ; the mod stages
        bsr     mo_apst
        move    x:(r1)+,y1              ; w2
        mac     x0,y1,b
        move    b,x1
        move    x1,b                    ; the sum, limited and clean
        move    y0,y1                   ; bm
        bsr     mo_apst
        bsr     mo_apst
        move    x:(r1)+,y1              ; w4
        mac     x0,y1,b
        move    b,x1
        move    x1,b                    ; the sum, limited and clean
        move    y0,y1                   ; bm
        bsr     mo_apst
        bsr     mo_apst
        move    x:(r1)+,y1              ; w6
        mac     x0,y1,b
        move    b,x1
        move    x1,b                    ; the sum, limited and clean
        move    y0,y1                   ; bm
        bsr     mo_apst
        bsr     mo_apst
        move    x:(r1)+,y1              ; w8
        mac     x0,y1,b
        asl     #$1,b,b                 ; back to full scale
        move    b,x1                    ; wet R (limited)
        move    x1,a
; ---- mo_lofr, inline (23 Sep 2026; three sites each, FREE allows it) ----
        move    a,y1
        move    n1,a
        tst     a
        move    x:(r3),a
        teq     y1,a
        move    a,x:(r3)+
        move    x:(r1)+,x0
        and     x0,a
        move    #$e,n3                  ; wet L is fourteen back from the cursor
; ---- momixs, inline (23 Sep 2026; three sites each, FREE allows it) ----
        move    a,x1                    ; wet R (limited)
        move    (r3)-n3
        move    x:(r3),a                ; wet L
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$22),a            ; m, the run value
        move    x:(r1)+,y1              ; its step
        add     y1,a
        move    a,x:(r7+$22)
        move    a,y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        move    x1,a
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a                 ; (y1 = m still)
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    (r0)+n0
        move    (r0)+n0
mophsz:
        nop
        move    x:(r7+$25),x0
        move    x0,x:(r7+$11)
        move    x:(r7+$26),x0
        move    x0,x:(r7+$13)
        move    x:(r7+$33),x0
        move    x0,x:(r7+$15)
        move    x:(r7+$34),x0
        move    x0,x:(r7+$17)
        move    n2,a
        move    a1,x:(r7+$23)
        move    n6,a
        move    a1,x:(r7+$24)
        move    n1,a
        move    a1,x:(r7+$41)
        rts

; ===========================================================================
; COMB -- Rings' string loop: the per-block tuning and decay, then the loop
; ===========================================================================
mo_bcomb:
; period from the table on DLY (page-1 slot 2; Q11.12 samples, 1,000 .. 8)
        move    x:(r6+$2),a
        and     #>$7f0000,a
        move    #$42,n5                 ; the period table
        bsr     mo_tab
        move    a,x:(r7+$1e)
; the polarity: FDBK's sign
        move    x:(r7+$04),a
        move    #>$7fffff,x0
        move    #>$800000,x1
        move    x0,b                    ; +1
        tst     a
        tmi     x1,b                    ; -1 when negative
        move    b,x:(r7+$1d)
; the decay: d = |fb|, lf = d(2 - d); T(u) = 2^(-8u): rt60 = 790,272 T(1 - lf)
; samples; q = 1.25 period / rt60 = (period_q * 0.0032394) / T(1 - lf), one
; division (q < 0.41 at every knob, so no clamp); gain = T(q)
        abs     a
        move    a,x0
        move    a,y1
        mpy     x0,y1,b                 ; d^2
        asl     #$1,a,a                 ; 2d
        sub     b,a                     ; lf  (<= 1)
        move    a,x0
        move    #>$7fffff,a
        sub     x0,a                    ; 1 - lf (>= 0)
        move    #$63,n5                 ; the 2^(-8u) table
        bsr     mo_tab
        move    a,x1                    ; T(1 - lf), 1/256 .. 1
        move    x:(r7+$1e),x0
        move    #>$006a27,y1            ; 0.0032394
        mpy     x0,y1,a
        move    a,x0
        move    x0,a                    ; a clean load: a0 = 0 for the divide
        move    x1,x0
        andi    #$fe,ccr                ; carry clear
        rep     #$18
        div     x0,a                    ; 24 quotient bits land in a0
        move    a0,x0
        move    x0,a
        move    #$63,n5
        bsr     mo_tab
        move    a,x:(r7+$1a)            ; the gain per pass
; the FIR: h0 = (1 + b)/2, h1 = (1 - b)/4, b = TONE/128 (parked in $46)
        move    x:(r7+$46),a
        asr     #$1,a,a
        add     #>$400000,a
        move    a,x:(r7+$1b)
        move    x:(r7+$46),a
        asr     #$2,a,a
        neg     a
        add     #>$200000,a
        move    a,x:(r7+$1c)
; ---- the loop --------------------------------------------------------------
; Pointer-addressed (22 Sep 2026). The stream at $48 (r4): period-1 polarity
; h1 h0 gain hold mask trim | period-1 polarity h1 h0 gain mask trim | m. The
; walk from
; $23 on r3, per channel: mo_herm's eight scratch words, x1, x2, the LOFI
; latch, then (L only) the wet. r2/r6 = the lines' bases, y0 = the write
; phase, n1 = the LOFI counter.
        move    #$1,n0
        move    r7,r4
        move    #$48,n4
        move    (r4)+n4
        move    #>$ffffff,m4
        move    r4,r1
        move    #>$ffffff,m1
; period - 1 and the gain are RUN values stepped once per sample (the loop's
; head) 1/1024 of the way to this block's (26 Sep 2026; steps at $10..$12);
; the R string reads L's
        move    r7,r3
        move    #$10,n3
        move    (r3)+n3
        move    x:(r7+$1e),a
        sub     #>$1000,a               ; period - 1 (the FIR's own delay)
        move    a,y1
        bsr     mo_rset                 ; period - 1
        move    x:(r7+$1d),y1
        bsr     mo_rset                 ; the polarity: through 0, not a flip
        move    #>$2026f3,y0            ; 0.251, the -12 dB output trim
        move    x:(r7+$1c),x0
        move    x0,x:(r1)+
        move    x:(r7+$1b),x0
        move    x0,x:(r1)+
        move    x:(r7+$1a),y1
        bsr     mo_rset                 ; the gain
        move    x:(r7+$42),x0
        move    x0,x:(r1)+
        move    x:(r7+$45),x0
        move    x0,x:(r1)+
        move    y0,x:(r1)+
        move    x:(r7+$1c),x0
        move    x0,x:(r1)+
        move    x:(r7+$1b),x0
        move    x0,x:(r1)+
        move    x:(r7+$45),x0
        move    x0,x:(r1)+
        move    y0,x:(r1)+
        move    x:(r7+$44),x0           ; MIX's step
        move    x0,x:(r1)+
        move    #>$1,x0
        move    x0,x:(r7+$43)           ; primed
        move    x:(r7+$0e),r2
        move    #>$ffffff,m2
        move    x:(r7+$0e),r6
        move    #>$400,n6
        move    (r6)+n6
        move    #>$ffffff,m6
        move    #>$ffffff,m3
        move    x:(r7+$20),y0
        move    x:(r7+$41),a
        move    a1,n1
        do      n7,>mocmbz
        move    r4,r1
        move    x:(r7+$10),x0
        move    x:(r1),a
        add     x0,a
        move    a,x:(r1)+               ; period - 1
        move    x:(r7+$11),x0
        move    x:(r1),a
        add     x0,a
        move    a,x:(r1)+               ; the polarity
        move    (r1)+
        move    (r1)+
        move    x:(r7+$12),x0
        move    x:(r1),a
        add     x0,a
        move    a,x:(r1)                ; the gain
        move    r4,r1
        move    r7,r3
        move    #$23,n3
        move    (r3)+n3
        move    y0,a
        add     #>$1,a
        and     #>$3ff,a
        move    a1,y0
; ===== channel L =====
        move    x:(r1)+,a               ; period - 1 (the FIR's own delay)
        move    r2,r5
        bsr     mo_herm                 ; r3 -> the third word of its scratch
        move    #$6,n3
        move    (r3)+n3                 ; -> x1 L
        move    a,x0
        move    x:(r1)+,y1              ; the polarity
        mpy     x0,y1,a x:(r0),x0
        add     x0,a                    ; s = +-read + x
        move    a,x1                    ; (limited)
        move    x1,a
        move    (r3)+
        move    x:(r3)-,x0              ; x2
        add     x0,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r1)+,y1              ; h1
        mpy     x0,y1,a x:(r3),x0       ; and x1
        asl     #$1,a,a
        move    x:(r1)+,y1              ; h0
        mac     x0,y1,a x1,x:(r3)+      ; x1 <- s
        move    x0,x:(r3)+              ; x2 <- x1
        move    a,x0                    ; the FIR's output (limited)
        move    x:(r1)+,y1              ; gain
        mpy     x0,y1,a
; ---- mo_lofl, inline (23 Sep 2026; three sites each, FREE allows it) ----
        move    a,y1
        move    n1,a
        move    x:(r1)+,x0              ; the hold length
        add     #>$1,a
        cmp     x0,a
        move    #$0,x0                  ; (a plain immediate move keeps the flags)
        tge     x0,a
        move    a1,n1
        move    x:(r3),a
        tge     y1,a
        move    a,x:(r3)+
        move    x:(r1)+,x0              ; the mask
        and     x0,a
        move    a,x1                    ; wet L = the sample written
        move    y0,a
        move    a1,n5
        move    r2,r5
        move    (r5)+n5
        move    x1,a
        move    a,y:(r5)                ; write line L
        move    x1,x0                   ; the -12 dB output trim, after the line
        move    x:(r1)+,y1              ; write so the ring is untouched: 0.251
        mpy     x0,y1,a
        move    a,x:(r3)+               ; wet L, trimmed
; ===== channel R =====
        move    x:(r4),a                ; period - 1 (L's run value)
        move    r6,r5
        bsr     mo_herm                 ; r3 -> the third word of its scratch
        move    #$6,n3
        move    (r3)+n3                 ; -> x1 R
        move    a,x0
        move    x:(r4+$1),y1            ; the polarity (L's run value)
        mpy     x0,y1,a x:(r0+n0),x0
        add     x0,a                    ; s = +-read + x
        move    a,x1                    ; (limited)
        move    x1,a
        move    (r3)+
        move    x:(r3)-,x0              ; x2
        add     x0,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r1)+,y1              ; h1
        mpy     x0,y1,a x:(r3),x0       ; and x1
        asl     #$1,a,a
        move    x:(r1)+,y1              ; h0
        mac     x0,y1,a x1,x:(r3)+      ; x1 <- s
        move    x0,x:(r3)+              ; x2 <- x1
        move    a,x0                    ; the FIR's output (limited)
        move    x:(r4+$4),y1            ; gain (L's run value)
        mpy     x0,y1,a
; ---- mo_lofr, inline (23 Sep 2026; three sites each, FREE allows it) ----
        move    a,y1
        move    n1,a
        tst     a
        move    x:(r3),a
        teq     y1,a
        move    a,x:(r3)+
        move    x:(r1)+,x0
        and     x0,a
        move    a,x1                    ; wet R = the sample written
        move    y0,a
        move    a1,n5
        move    r6,r5
        move    (r5)+n5
        move    x1,a
        move    a,y:(r5)                ; write line R
        move    x1,x0                   ; the -12 dB output trim, after the line
        move    x:(r1)+,y1              ; write so the ring is untouched: 0.251
        mpy     x0,y1,a
        move    #$c,n3                  ; wet L is twelve back from the cursor
; ---- momixs, inline (23 Sep 2026; three sites each, FREE allows it) ----
        move    a,x1                    ; wet R (limited)
        move    (r3)-n3
        move    x:(r3),a                ; wet L
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$22),a            ; m, the run value
        move    x:(r1)+,y1              ; its step
        add     y1,a
        move    a,x:(r7+$22)
        move    a,y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        move    x1,a
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a                 ; (y1 = m still)
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    (r0)+n0
        move    (r0)+n0
mocmbz:
        nop
        move    y0,a
        move    a1,x:(r7+$20)
        move    n1,a
        move    a1,x:(r7+$41)
        rts

; ===========================================================================
; THE DRY PATH: an FX2 slot, or MIX at zero. Frames untouched.
; ===========================================================================
mo_dry:
        rts

; ---------------------------------------------------------------------------
; mo_rset -- one ramped word, per block (26 Sep 2026). The word is a RUN
; value a loop steps once per sample, 1/1024 of the way from where the last
; block ended to this block's target (linear inside a block, a glide across
; them); a step that rounds to 0 puts the word on the target, and the first
; block after init or a MODE change ($43 = 0) starts it there.
; In: y1 = the target, r1 -> the word, r3 -> its step. Out: r1, r3 each one
; on. Clobbers a, b, x0.
; ---------------------------------------------------------------------------
mo_rset:
        move    x:(r7+$43),b
        tst     b
        move    x:(r1),b                ; the run value (moves keep the flags)
        teq     y1,b                    ; the first block: at the target
        move    b,x0
        move    y1,a
        sub     x0,a
        asr     #$a,a,a                 ; the step per sample
        teq     y1,b                    ; a step of 0: at the target
        move    a,x:(r3)+
        move    b,x:(r1)+
        rts

; ---------------------------------------------------------------------------
; mo_para -- a = a 0..1 phase -> a = the parabola 2t - t|t| of its triangle,
; -1..1 (the station's sine). Uses x0 x1 y1 b and $47 (per block; $3f is
; PHSR's walk). Straight-line.
; ---------------------------------------------------------------------------
mo_para:
        move    #$40,x0
        sub     x0,a
        abs     a
        asl     #$2,a,a
        move    #>$7fffff,x0
        sub     x0,a
        move    a,x:(r7+$47)            ; LIMITING: t
        move    x:(r7+$47),x1
        move    x1,a
        abs     a
        move    a,y1                    ; |t|
        move    x1,x0
        mpy     x0,y1,a                 ; t|t|
        neg     a
        move    x1,b
        asl     #$1,b,b                 ; 2t
        add     b,a
        rts

; ---------------------------------------------------------------------------
; mo_tap -- a = the delay in Q11.12 (8 .. 1,015), y0 = the write phase, r5 =
; the line's base -> a = the tap, the fraction blended toward the OLDER
; neighbour: a delay of i + f lies between the samples at i and i + 1
; (blended toward the newer one it reads i - f and clicks at every integer
; crossing). Uses x0 y1 b n5; x1 is kept. mo_itap enters with the split
; already done: x0 = i, y1 = f. Straight-line.
; ---------------------------------------------------------------------------
mo_tap:
        move    a,x0                    ; the total (positive, under 1: not limited)
        move    x0,a                    ; clean: a0 = 0
        and     #>$fff,a
        asl     #$b,a,a                 ; the fraction, Q23
        move    a1,y1
        move    x0,a
        asr     #$c,a,a
        move    a1,x0                   ; i
mo_itap:
; the fixed taps enter here, their split done per block: x0 = i, y1 = f
        move    y0,a                    ; the write phase
        sub     x0,a
        and     #>$3ff,a                ; (a2 may be stale: a1 is what is read)
        move    a1,x0
        move    a1,n5
        move    x0,a
        add     #>$3ff,a                ; i + 1, mod 1024 (positive throughout)
        and     #>$3ff,a
        move    (r5)+n5                 ; -> sample i
        move    y:(r5),b                ; t0
        move    (r5)-n5
        move    a1,n5
        move    (r5)+n5                 ; -> sample i + 1
        move    y:(r5),a                ; t1
        sub     b,a                     ; t1 - t0
        move    a,x0
        mpy     x0,y1,a                 ; f (t1 - t0)
        add     b,a
        rts

; ---------------------------------------------------------------------------
; mo_herm -- a = the delay in Q11.12 (>= 4), y0 = the write phase, r5 = the
; line's base, r3 -> eight words of scratch -> a = the 4-point Hermite read
; (stmlib's ReadHermite: xm1 one sample NEWER than i, x1 and x2 older),
; everything scaled by 1/16 so no intermediate leaves +-1:
;   c = (x1 - xm1)/2 ; v = x0 - x1 ; w = c + v ; a = w + v + (x2 - x0)/2 ;
;   b = w + a ; out = (((a f) - b) f + c) f + x0
; The scratch: xm1 c x0 x1 w x2 a; r3 leaves on its third word. Uses x0 x1
; y1 b n3 n5. Straight-line.
; ---------------------------------------------------------------------------
mo_herm:
        move    a,x0                    ; the total
        move    x0,a                    ; clean
        and     #>$fff,a
        asl     #$b,a,a
        move    a1,y1                   ; f, Q23
        move    x0,a
        asr     #$c,a,a
        move    a1,x1                   ; i
        move    y0,a
        sub     x1,a
        add     #>$1,a                  ; i - 1: xm1
        and     #>$3ff,a
        move    a1,n5
        move    (r5)+n5
        move    y:(r5),b                ; xm1
        move    (r5)-n5
        move    b,x:(r3)+
        move    (r3)+                   ; (c's word)
        add     #>$3ff,a                ; each next index is the last - 1 mod
        and     #>$3ff,a                ; 1024 (a1 only: a2 is stale)
        move    a1,n5
        move    (r5)+n5
        move    y:(r5),b                ; x0
        move    (r5)-n5
        move    b,x:(r3)+
        add     #>$3ff,a
        and     #>$3ff,a
        move    a1,n5
        move    (r5)+n5
        move    y:(r5),b                ; x1
        move    (r5)-n5
        move    b,x:(r3)+
        move    (r3)+                   ; (w's word)
        add     #>$3ff,a
        and     #>$3ff,a
        move    a1,n5
        move    (r5)+n5
        move    y:(r5),b                ; x2
        move    (r5)-n5
        move    b,x:(r3)
; the polynomial, /16
        move    #$2,n3
        move    (r3)-n3                 ; -> x1
        move    x:(r3)-,a               ; x1
        move    (r3)-
        move    (r3)-                   ; -> xm1
        move    x:(r3)+,x0              ; xm1
        sub     x0,a
        asr     #$5,a,a                 ; c/16
        move    a,x:(r3)+
        move    x:(r3)+,b               ; x0
        move    x:(r3)+,x0              ; x1
        sub     x0,b                    ; v
        asr     #$4,b,b                 ; v/16
        add     b,a                     ; w/16
        move    a,x:(r3)+
        add     b,a                     ; w + v
        move    x:(r3)+,b               ; x2
        move    #$4,n3
        move    (r3)-n3                 ; -> x0
        move    x:(r3)+n3,x0            ; x0
        sub     x0,b
        asr     #$5,b,b                 ; (x2 - x0)/32
        add     b,a                     ; a/16
        move    a,x:(r3)-               ; a; r3 -> x2
        move    (r3)-                   ; -> w
        move    x:(r3)+,b               ; w
        add     b,a                     ; b/16 = (w + a)/16
        move    a,x1
        move    (r3)+                   ; -> a
        move    x:(r3),x0               ; a/16
        mpy     x0,y1,a                 ; a f /16
        sub     x1,a                    ; - b/16
        move    a,x0
        mpy     x0,y1,a                 ; (..) f
        move    #$5,n3
        move    (r3)-n3                 ; -> c
        move    x:(r3)+,x0
        add     x0,a                    ; + c/16
        move    a,x0
        mpy     x0,y1,a                 ; (..) f
        asl     #$4,a,a                 ; x 16
        move    x:(r3),x0               ; x0
        add     x0,a                    ; + x0
        rts

; ---------------------------------------------------------------------------
; mo_apst -- one first-order allpass stage: x0 = x (limited), y1 = b0, r3
; -> its state; y = b0 x + z ; z' = b0 y - x ; returns x0 = y (limited), r3
; advanced, so a chain of stages passes x0 straight through. Uses a x1; b
; and y0 are kept. Straight-line.
; ---------------------------------------------------------------------------
mo_apst:
        mpy     x0,y1,a x:(r3),x1       ; b0 x, and z
        add     x1,a                    ; y
        move    x0,x1                   ; x
        move    a,x0                    ; y (LIMITING)
        mpy     x0,y1,a                 ; b0 y
        sub     x1,a                    ; - x
        move    a,x:(r3)+               ; z' (limited), next stage
        rts

; ---------------------------------------------------------------------------
; mo_tab -- a = u (0..1, Q23), n5 = the table's offset -> a = T(u), the
; 33-word table read at idx = u >> 18 and interpolated on the 18 bits under
; it (Spectrum's read). Per block only. Uses x0 x1 y0 y1 b r5 n5.
; ---------------------------------------------------------------------------
mo_tab:
        move    x:(r7+$0f),r5           ; the P table base
        move    a,x1
        asr     #$12,a,a                ; idx
        move    (r5)+n5                 ; + the table's offset
        move    a1,n5
        move    x1,a
        and     #>$3ffff,a
        asl     #$5,a,a                 ; frac, Q23
        move    (r5)+n5                 ; + idx
        move    a,x0
        move    p:(r5)+,y0              ; T[idx]
        move    p:(r5),b                ; T[idx + 1]
        move    y0,a
        sub     a,b                     ; the difference (either sign)
        move    b,y1
        mpy     x0,y1,a
        add     y0,a
        rts

; ---------------------------------------------------------------------------
; LOFI (mo_lofl / mo_lofr, inline at their three sites each): the value in a
; held and masked. One counter (n1) for both channels: L advances it and
; latches on the compare, R latches on the counter reading 0; each channel's
; latch is the walk word at r3 (advanced). The stream gives the hold length
; then the mask (L), the mask (R). The mask keeps bit 23, so a2 stays
; consistent through the and and the store does not saturate. Applied at the
; LINE WRITE in the line modes and COMB (the line is clocked coarse and the
; taps read through the stairs; COMB's ring recirculates it) and on the wet
; in PHSR, which has no line. Uses x0 y1; x1 is kept.
;
; MIX (momixs, inline at its three sites): the wet in a (R) and n3 words
; behind the walk cursor (L) against the dry still in the frame, written
; back: out = dry + m (wet - dry). The stream gives m, the last word.
; ---------------------------------------------------------------------------
