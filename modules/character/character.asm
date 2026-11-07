; ---------------------------------------------------------------------------
; CHARACTER -- fold, saturate, tilt, compress, width.
;
; Insert contract: frames in place at
; x:(r0)/x:(r0+n0), knobs from r6, state in this instance's r7 block. The
; station writes nothing to the bus; with KEY on T1 it reads two words of
; its scratch (y:$990/$991, BusDelay host's level and counter).
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
; from the frame (untouched until the write-back), or with KEY = T1 (page-2
; slot 7; never on the master) T1's peak |mono in| x KLVL/64, per block.
;
; ---- r7 slots -------------------------------------------------------------
; per block, read into the rings before the loop:
;   $18 fold trim/2 (1/128)/gq   $20 m (MIX)   $21 fold gain/64 (gq)
;   $22 K/4   $24 tilt t/2   $26 COMP amount   $27 makeup/4   $28 the dip's a
;   $29 sat mode (0 TAPE = TapeHead, 1 TUBE = DaTube, 2 INFL = OInflator)
;   $2a TAPE trim (1/11)/d8 + 0.023   $2b width side gain/2
;   $2d attack coeff   $2e release coeff
;   $30 k2   $31 k3mag   $48 d/8 (TAPE)
;   $32 G/8   $33 the output scale after the curve (1, (1+d)/G, 1/G by mode)
;   $37 d/2   $38 d   $39 comp/2 (TUBE)   $4c (0.5+d)/2 (TUBE)   $3a e/2   $3b 1-e (INFL)
;   $4d DRV == 0: skip the saturator
;   $25 master flag (1 = position 3 on A: GLUE), $23 FX2-slot flag (set at
;     init: 1 = this instance is on FX2, dry)
; persistent, zeroed at init:
;   $3e/$3f R y1/y2, $40/$41 L y1/y2: TapeHead's SVF states (/4)
;   $42/$43 L x1/y1, $44/$45 R x1/y1: TUBE's DC blockers
;   $1b tilt lp L, $1c tilt lp R, $1d level_s (r4 + 2)
; per sample:
;   $19 wet L, $1a wet R (r4 -> $19, n4 = 1)
;   $60..$6f the main ring (r5, m5 = 15), in the order the sample reads
;     them: gq trim/2, the SAT word (-1 = DRV 0 skips, else $29), k (the
;     tilt's 0.157), t/2, $26, the KEY word $17, $2d $2e $22, -1.0, $28 $27,
;     a spare, $2b $20. COMP off steps over its seven words and the spare
;     (n5 = 8, else 1)
;   $70..$7f the SAT ring (r6, m6 = 15 in every mode -- the chip has only
;     ever run power-of-two modulos), both channels, each between G/8 and
;     the output scale: TAPE (0.7 on L only) k2 k1 k3mag d8 trim, TUBE
;     (0.5+d)/2 d d/2 comp/2 k R, INFL e/2 1-e. TUBE fills all sixteen;
;     TAPE's and INFL's remainder is stepped once per sample by (r6)+n6
;     (n6 = 1 / 8)
; The SAT callees' state pointer is r7 + n3: TapeHead's L y2 (n3 = $41) or
; DaTube's L pair (n3 = $42), set per block by mode.
; knob glides and ramps (26 Sep 2026):
;   $4e..$53 page-1 slots 0..5 glided; $54 1 once they started at the
;   knobs, $55 1 once the ring's run values started at their targets (both
;   zeroed at init); $56..$5b (r4 + $3d) the per-sample steps of gq trim t,
;   a makeup m (per block), whose run values are their main-ring words
;   $15 T1's counter last seen, $16 blocks since it moved (both zeroed at
;     init), $17 the KEY word (per block: -1 SELF, else T1's level)
; free: $2c, $34..$36, $3c/$3d, $46/$47, $49..$4b, $5c..$5f
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
; Every mpy and mac is x0,y1, y0,x0, x0,x0 or x1,x0 (the signed encodings)
; except chtube's `mpy x1,y1` (mpysu; its second operand is the constant
; 1.0, commented at its site). Every Tcc reads the one compare above it with
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
        move    a,x:(r7+$1b)            ; the tilt's two low-pass states, the
        move    a,x:(r7+$1c)            ; compressor's level_s, the master flag:
        move    a,x:(r7+$1d)            ; every slot read before written
        move    a,x:(r7+$25)            ; (verify_dirty_state)
        move    a,x:(r7+$54)            ; the glides start at the knobs,
        move    a,x:(r7+$55)            ; the ramps at their targets
        move    a,x:(r7+$15)            ; KEY's counter last seen and the
        move    a,x:(r7+$16)            ; blocks since it moved
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
        do      #$18,>norep_ch_01
        div     x0,a
norep_ch_01:
        move    a0,x0
        move    x0,x:(r7+$18)           ; fold trim/2
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
        do      #$18,>norep_ch_02
        div     x0,a
norep_ch_02:
        move    a0,x0
        move    x0,x:(r7+$27)           ; m/4 = 0.25/den: makeup/4
; SAT (slot 6, r6+$c's knob field) -> the mode flag $29 and per-mode words,
; so the sample loop's SAT stage is a MODEFORK: TAPE (0) = TapeHead, TUBE (1)
; = DaTube, INFL (2) = OInflator (JClones, MIT). A stored 3 lands on TAPE.
; Per-mode words, all from DRV = d (0..0.992):
;   TUBE  $37 = d/2 (the positive half's scale)  $38 = d (the negative half's)
;         ($4c = (0.5 + d)/2 input gain and $39 = comp/2)
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
; ---- KEY (29 Sep 2026): page-2 slot 7 (r6+$c bits 8-15) 1 = T1, the
; BusDelay host's level at y:$990, x KLVL/64 (slot 8, r6+$d's knob field);
; anything else, and the master always, keys on its own input. $17 is the
; ring's KEY word: -1 = SELF, else the level the loop holds for the block.
; A T1 counter (y:$991) that has not moved for 4 blocks reads as silence:
; no host, or boot garbage. $15 the counter last seen, $16 blocks since it
; moved (held at 8).
        move    x:(r7+$16),b
        add     #>$1,b
        move    #>$8,x1
        cmp     x1,b
        tgt     x1,b
        move    y:>$991,a
        move    x:(r7+$15),x0
        move    a,x:(r7+$15)
        cmp     x0,a                    ; nothing but moves before the Tcc
        move    #0,x1
        tne     x1,b                    ; moved: 0
        move    b,x:(r7+$16)
        move    x:(r6+$c),a             ; KEY, the companion byte
        and     #>$00ff00,a
; KEYTAP_PRE
        cmp     #>$000100,a
        bne     ch_kself
; KEYTAP_BEGIN
; Track 1..8 from the keybus a side-chain tap publishes (the key track's 32
; input words per block, in Y): this core's tracks from their keybus slot,
; the other core's from the shared-window relay two generations behind this
; core's counter. a = the KEY byte << 8 on entry; the master and SELF were
; sent to ch_kself before this. The peak of |(L + R) / 2| over the 16 frames
; goes through KLVL as T1's host level does.
ch_kbus:
        cmp     #>$000800,a
        bgt     ch_kself                ; a KEY byte above 8 reads as SELF
        sub     #>$000100,a
        asr     #$8,a,a                 ; the key track, 0..7
        move    #>$ffffff,m1
        move    a1,r4
        move    r4,b
        and     #>4,b
        move    b1,a                    ; a clean 4-or-0
        tst     a
        @CK_FOREIGN@
        move    r4,a
        asl     #6,a,a
        move    a1,n1
        move    #>@KEYB@,r1
        lua     (r1)+n1,r1              ; the keybus slot, gen 0
        bra     ch_kscan
ch_kfor:
        move    r4,a
        sub     #>@FCOREBASE@,a         ; the track's index on its own core
        asl     #2,a,a
        move    a1,x1
        move    #>@GCNT@,r1
        move    y:(r1),b                ; this core's counter, +2 = -2 mod 4
        add     #>2,b
        and     #>3,b
        move    b1,a
        add     x1,a
        asl     #5,a,a
        move    a1,n1
        move    #>@FSBASE@,r1
        lua     (r1)+n1,r1              ; the other core's slot for that generation
ch_kscan:
        clr     b
        do      #<$10,>ch_kloop
        move    y:(r1)+,x0              ; L
        move    y:(r1)+,a               ; R
        add     x0,a
        asr     a
        abs     a                       ; |mono|
        move    a,x0                    ; the limiting move
        cmp     x0,b
        tlt     x0,b                    ; the peak so far
ch_kloop:
        move    b1,x0
        bra     ch_klvl
; KEYTAP_END
; NOBUS_KEY
        move    x:(r7+$25),a
        tst     a
        bne     ch_kself                ; the master keys on its own input
        move    x:(r7+$16),a
        cmp     #>$4,a
        bge     ch_kzero                ; stale: silence
        move    y:>$990,x0              ; T1's peak |mono in|
ch_klvl:
        move    x:(r6+$d),a             ; KLVL, the knob field
        and     #>$7f0000,a
        move    a,y1                    ; KLVL/128
        mpy     x0,y1,a
        asl     a                       ; x KLVL/64: 64 = unity
        move    #0,x1
        tst     a                       ; nothing but moves before the Tcc
        tmi     x1,a                    ; a garbage level floors at 0
        move    a,x1                    ; the limiting move
        bra     ch_kset
ch_kzero:
        move    #0,x1
        bra     ch_kset
ch_kself:
        move    #>$ffffff,x1
ch_kset:
        move    x1,x:(r7+$17)
        move    x:(r7+$4e),a             ; d = DRV/128
        move    a,x1                    ; shared by the selected saturator decode
        move    #>$fab1e0,r1            ; TUBE_UP -- also the base of TAPE_D8
        move    #>$ffffff,m1
        move    x:(r7+$29),b            ; mode: calculate only the active curve's words
        cmp     #>$1,b
        beq     onlysat_tube_decode_block
        tst     b
        beq     onlysat_tape_decode_block
        bra     onlysat_decode_finish   ; INFL's coefficients were set at ch_sinfd
onlysat_tube_decode_block:
        move    r1,r2
        move    #$11,n2
        move    (r2)+n2                 ; r2 = TUBE_UP's slopes
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
        do      #$18,>norep_ch_03
        div     x0,a                    ; 24 quotient bits land in a0
norep_ch_03:
        move    a0,x0
        move    x0,x:(r7+$39)           ; comp/2
        bra     onlysat_decode_finish
onlysat_tape_decode_block:
; the P table: TUBE_UP (DaTube's curve: 17 values, then their 17 slopes)
; then TAPE_D8 (17 words).
; ---- TapeHead's per-block words (used only by TAPE) ----------------------
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
        do      #$18,>norep_ch_04
        div     x0,a                    ; 24 quotient bits land in a0
norep_ch_04:
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
onlysat_decode_finish:
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
; inside the loop. r4 -> the per-sample scratch (wet L, wet R, then the
; tilt's two states and level_s at $1b..$1d); n4 = 1 reaches wet R.
        move    r7,r4
        move    #$19,n4
        move    (r4)+n4
        move    #>$ffffff,m4
        move    #$1,n4
        move    r7,r5
        move    #$60,n5
        move    (r5)+n5
        move    #>$ffffff,m5
; ---- THE RAMPS (26 Sep 2026): gq trim t a makeup m are RUN values in the
; ring, stepped once per sample by the loop's head, steps at $56..$5b
        move    r5,r3
        move    r7,r6                   ; (the page is read: r6 is free)
        move    #$56,n6
        move    (r6)+n6
        move    x:(r7+$21),y1           ; gq
        bsr     ch_rset
        move    x:(r7+$18),y1           ; trim/2
        bsr     ch_rset
        move    x:(r7+$4d),a            ; the SAT word: -1 when DRV 0 skips
        move    x:(r7+$29),b            ; the saturator, else the sat mode
        move    #>$ffffff,x0
        tst     a
        tne     x0,b
        move    b,x:(r3)+
        move    #>$141893,x0            ; the tilt's k = 0.157: one pole at 1.2 kHz
        move    x0,x:(r3)+
        move    x:(r7+$24),y1           ; t/2
        bsr     ch_rset
        move    #$0f,m5                 ; sixteen words, one turn per sample
        move    x:(r7+$26),a            ; COMP; off: the sample steps over its
        move    a,x:(r3)+               ; seven words and the spare (n5 = 8,
        move    #>$1,b                  ; else 1: the spare)
        move    #>$8,x0
        tst     a
        teq     x0,b
        move    b1,n5
        move    x:(r7+$17),x0           ; KEY: -1 = SELF, else T1's level
        move    x0,x:(r3)+
        move    x:(r7+$2d),x0           ; attack
        move    x0,x:(r3)+
        move    x:(r7+$2e),x0           ; release
        move    x0,x:(r3)+
        move    x:(r7+$22),x0           ; K/4
        move    x0,x:(r3)+
        move    #>$800000,x0            ; -1.0: the dip's t = Lv^2/2 - 1
        move    x0,x:(r3)+
        move    x:(r7+$28),y1           ; the dip's a
        bsr     ch_rset
        move    x:(r7+$27),y1           ; makeup/4
        bsr     ch_rset
        move    (r3)+                   ; the spare
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
        move    x:(r7+$29),b            ; TAPE's output scale is unity; skip the unused reciprocal
        tst     b
        beq     ch_gtape
        move    a,x0
        move    #$08,y1                 ; 1/16
        move    y1,a                    ; a clean load: a0 = 0 for the divide
        andi    #$fe,ccr
        do      #$18,>norep_ch_05
        div     x0,a                    ; (1/16)/(G/8) = 1/(2G) in a0
norep_ch_05:
        move    a0,x0
        move    x0,a
        asl     #$1,a,a                 ; 1/G, 1.0 at DRV 0 (the store limits)
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
; the SAT ring: the active mode's words in the order the sample reads them.
; n3 = the callees' state base, r7 + n3: TapeHead's L y2 ($41) or DaTube's
; L pair ($42).
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
        move    x:(r7+$32),x0           ; TAPE: G/8 0.7 k2 k1 k3mag d8 trim
        move    x0,x:(r3)+              ; scale, then R without the 0.7
        move    #>$59999a,x0            ; the smoothstep's 0.7 (y0, both calls)
        move    x0,x:(r3)+
        move    x:(r7+$30),x0
        move    x0,x:(r3)+
        move    #>$5b6db7,x0            ; k1 = 5/7
        move    x0,x:(r3)+
        move    x:(r7+$31),x0
        move    x0,x:(r3)+
        move    x:(r7+$48),x0
        move    x0,x:(r3)+
        move    x:(r7+$2a),x0
        move    x0,x:(r3)+
        move    x:(r7+$33),x0
        move    x0,x:(r3)+
        move    x:(r7+$32),x0
        move    x0,x:(r3)+
        move    x:(r7+$30),x0
        move    x0,x:(r3)+
        move    #>$5b6db7,x0
        move    x0,x:(r3)+
        move    x:(r7+$31),x0
        move    x0,x:(r3)+
        move    x:(r7+$48),x0
        move    x0,x:(r3)+
        move    x:(r7+$2a),x0
        move    x0,x:(r3)+
        move    x:(r7+$33),x0
        move    x0,x:(r3)+
        move    #$1,n6                  ; 16 - 15
        bra     ch_rdone
ch_r12:
        cmp     #>$1,a
        bne     ch_rinfl
        move    #$42,n3                 ; DaTube's L pair
        move    x:(r7+$32),x0           ; TUBE: G/8 (0.5+d)/2 d d/2 comp/2 k R scale
        move    x0,x:(r3)+
        move    x:(r7+$4c),x0
        move    x0,x:(r3)+
        move    x:(r7+$38),x0
        move    x0,x:(r3)+
        move    x:(r7+$37),x0
        move    x0,x:(r3)+
        move    x:(r7+$39),x0
        move    x0,x:(r3)+
        move    #>$7fffff,x0            ; the DC blocker's k = 1.0
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
        move    #>$7fffff,x0            ; the DC blocker's k = 1.0
        move    x0,x:(r3)+
        move    #>$7fdf3b,x0            ; the DC blocker's R = 0.999
        move    x0,x:(r3)+
        move    x:(r7+$33),x0
        move    x0,x:(r3)+
        bra     ch_rdone                ; sixteen words: n6 unused
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
; the steps ($56..$5b = r4 + $3d)
        lua     (r4+$3d),r3
        move    x:(r5),a
        move    x:(r3)+,x0
        add     x0,a    x:(r3)+,x0
        move    a,x:(r5)+               ; gq
        move    x:(r5),a
        add     x0,a    x:(r3)+,x0
        move    a,x:(r5)+               ; trim/2
        lua     (r5+$2),r5              ; past the SAT word and k
        move    x:(r5),a
        add     x0,a    x:(r3)+,x0
        move    a,x:(r5)+               ; t/2
        lua     (r5+$6),r5              ; past COMP, KEY, attack, release, K, -1
        move    x:(r5),a
        add     x0,a    x:(r3)+,x0
        move    a,x:(r5)+               ; the dip's a
        move    x:(r5),a
        add     x0,a    x:(r3)+,x0
        move    a,x:(r5)+               ; makeup/4
        lua     (r5+$2),r5              ; past the spare and the side gain
        move    x:(r5),a
        add     x0,a    x:(r0),x0       ; L in, for the fold
        move    a,x:(r5)+               ; m, and r5 is back at the ring's head
; ---- FOLD: WarpFold's wrap-and-reflect, both channels. y1 = gq and y0 =
; trim/2 serve both; b = 0.5, the wrap's offset and the reflect's.
        move    x:(r5)+,y1              ; gq = gain/64
        mpy     x0,y1,a     #$40,b      ; v/64 ; 0.5 (short immediate: bits 23-16)
        asl     #$5,a,a                 ; v/2
        add     b,a                     ; (v+1)/2
        move    a1,x1                   ; s = wrap(...), raw A1: the fold
        move    x1,a                    ; clean re-load, A2 consistent
        abs     a           r7,r3       ; (r3 -> the SAT callees' state, below)
        sub     b,a                     ; |s| - 0.5
        asl     a           x:(r5)+,y0  ; fold in [-1,1) ; trim/2
        move    a,x0
        mpy     y0,x0,a     x:(r0+n0),x0        ; R in
        asl     a                       ; the fold at a held level
        mpy     x0,y1,a     a,x:(r4)+   ; wet L ; v/64 (R)
        asl     #$5,a,a
        add     b,a
        move    a1,x1
        move    x1,a
        abs     a           (r3)+n3     ; r3 = r7 + n3
        sub     b,a
        asl     a
        move    a,x0
        mpy     y0,x0,a
        asl     a           x:(r5)+,b   ; the SAT word
; ---- SATURATE: the character. TAPE is
; TapeHead, TUBE is DaTube, INFL is OInflator: one straight-line callee per
; mode per channel (a = the sample in, the caller's LIMITING move the hard
; clip). Skipped whole when DRV is 0 (the SAT word is -1). The three
; alternatives are a MODEFORK so the pricer charges the worst, not all.
        tst     b           a,x:(r4)-   ; wet R
        blt     ch_nosat                ; DRV 0: skip the saturator
; MODEFORK_BEGIN -- cycle_count.py: the dispatch, the tst above's flags
        beq     ch_tape
; MODEFORK_MID -- alternative 1: TUBE = DaTube (one compare more: 1 or 2)
; r3 -> the channel's DC-blocker pair (x1, y1): L at r7 + n3 = $42, R the
; pair above (chtube leaves r3 on y1; the caller's store steps it on).
        cmp     #1,b
        bne     ch_sinfl
        move    x:(r4),x0               ; L in (post fold)
        move    x:(r6)+,y1              ; G/8
        mpy     x0,y1,a     x:(r6)+,y1  ; (0.5 + d)/2, chtube's
        asl     #$3,a,a                 ; x*G, up to 4 in the accumulator
        bsr     chtube
        move    a,x0                    ; LIMITING: the hard clip
        mpy     x0,y1,b     a,x:(r3)+   ; the output scale ; the blocker's y1
        move    b,x:(r4)+
        move    x:(r4),x0               ; R in
        move    x:(r6)+,y1              ; G/8
        mpy     x0,y1,a     x:(r6)+,y1
        asl     #$3,a,a                 ; x*G, up to 4 in the accumulator
        bsr     chtube
        move    a,x0                    ; LIMITING: the hard clip
        mpy     x0,y1,b     a,x:(r3)+
        move    b,x:(r4)-               ; (sixteen ring words: no remainder)
        bra     ch_nosat
; MODEFORK_MID -- alternative 2: INFL = OInflator (stateless, inlined per
; channel: its 30 words twice against a bsr/rts per call)
ch_sinfl:
        move    x:(r4),x0               ; L in (post fold)
        move    x:(r6)+,y1              ; G/8
        mpy     x0,y1,a
        asl     #$2,a,a                 ; x2 = x*G/2
; ---- OInflator inline (JClones_OInflator.jsfx, MIT), single band, Curve 0
; (c = 0.25), Clip on: x2 = x/2; g = 0.75 + 0.5|x2|; gx = g x2;
; y = 2e gx (1 - |gx|) + (1 - e) x2; out = 2y. e = DRV/128; g and t = 1 - |gx|
; live halved. Stateless; the ring holds e/2, 1 - e. Clobbers x0, x1, y1, a, b.
        abs     a           a,x1
        move    a,x0                    ; |x2|
        move    #$20,y1                 ; 0.25
        mpy     x0,y1,a
        add     #>$300000,a             ; g/2 = 0.375 + 0.25*|x2|
        move    a,y1
        move    x1,x0                   ; x2
        mpy     x0,y1,a
        asl     #$1,a,a                 ; gx = g*x2
        abs     a           a,x0        ; gx
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
        asl     a           x:(r6)+,y1  ; out = 2y ; the output scale
        move    a,x0                    ; LIMITING: the hard clip
        mpy     x0,y1,b
        move    b,x:(r4)+
        move    x:(r4),x0               ; R in
        move    x:(r6)+,y1              ; G/8
        mpy     x0,y1,a
        asl     #$2,a,a                 ; x2
        abs     a           a,x1
        move    a,x0                    ; |x2|
        move    #$20,y1                 ; 0.25
        mpy     x0,y1,a
        add     #>$300000,a             ; g/2 = 0.375 + 0.25*|x2|
        move    a,y1
        move    x1,x0                   ; x2
        mpy     x0,y1,a
        asl     #$1,a,a                 ; gx = g*x2
        abs     a           a,x0        ; gx
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
        asl     a           x:(r6)+,y1  ; out = 2y ; the output scale
        move    a,x0                    ; LIMITING: the hard clip
        mpy     x0,y1,b     (r6)+n6
        move    b,x:(r4)-
        bra     ch_nosat
; MODEFORK_MID -- alternative 3: TAPE = TapeHead
; r3 -> the channel's y2 (y1 the word below): L at r7 + n3 = $41, R two
; below (chtape leaves r3 where it entered). y0 = the smoothstep's 0.7 for
; both calls (chtape reads it, never writes it).
ch_tape:
        move    x:(r4),x0               ; L in (post fold)
        move    x:(r6)+,y1              ; G/8
        mpy     x0,y1,a     x:(r6)+,y0  ; 0.7
        asl     a           x:(r6)+,y1  ; x*G/4, TapeHead's Xs ; k2
        bsr     chtape
        move    b,x0                    ; LIMITING: the hard clip
        mpy     x0,y1,b     x:(r4+n4),x0        ; the output scale ; R in
        lua     (r3-$2),r3              ; r3 = r7+$3f: R y2
        move    x:(r6)+,y1              ; G/8
        mpy     x0,y1,a     b,x:(r4)+   ; wet L
        asl     a           x:(r6)+,y1  ; k2
        bsr     chtape
        move    b,x0                    ; LIMITING: the hard clip
        mpy     x0,y1,b     (r6)+n6     ; the ring's remainder: one turn per sample
        move    b,x:(r4)-
; MODEFORK_END
ch_nosat:
; ---- TONE: a tilt after the saturator, every mode ----------
; One-pole low-pass at 1.2 kHz per channel (k = 0.157), y = x + (t/2)(x - 2lp):
; TONE 127 = +3.5 dB above / -6 dB below, 0 the mirror, 64 bit-exact.
; r3 -> the state block at r4 + 2 = $1b: lp L, lp R, level_s. y0 = k, y1 =
; t/2 for both channels.
        lua     (r4+$2),r3
        move    x:(r4),a                ; L
        move    x:(r3),x0               ; lp
        sub     x0,a        x:(r5)+,y0  ; k
        move    a,x0                    ; x - lp
        mpy     y0,x0,a     x:(r3),b
        add     b,a         x:(r4),b    ; lp' = lp + k (x - lp) ; x
        move    a,x0
        sub     x0,b        a,x:(r3)+
        sub     x0,b        x:(r5)+,y1  ; x - 2 lp' ; t/2
        move    b,x0
        mpy     x0,y1,a     x:(r4),b
        add     b,a         x:(r4+n4),b ; R
        move    a,x:(r4)+
        tfr     b,a         x:(r3),x0
        sub     x0,a
        move    a,x0
        mpy     y0,x0,a     x:(r3),b
        add     b,a         x:(r4),b
        move    a,x0
        sub     x0,b        a,x:(r3)+
        sub     x0,b        x:(r0+n0),x1        ; the key's R, for COMP
        move    b,x0
        mpy     x0,y1,a     x:(r4),b
        add     b,a         x:(r5)+,b   ; COMP
; ---- COMPRESS: COMP 0 skips the stage
; (bit-exact); else |key| smoothed by the flavour's attack / release, Lv =
; K * level_s, gr = (Lv^2/2 - 1)^2 + a*Lv, <= 1 by the limiting move --
; a dip around Lv = 1 -- then x *= gr * makeup on both channels. Lv is
; carried halved (Lv/2, so Lv up to 2 fits a word; the dip is over by 1.5).
; r3 -> level_s after the tilt's two states. The key is the mono input,
; still untouched in the frame (the write-back is the last stage), or with
; KEY on T1 the ring's KEY word, held for the block.
        tst     b           a,x:(r4)-
        beq     ch_capd                 ; COMP 0: the stage is skipped
        move    x:(r0),a
        add     x1,a        x:(r5)+,b   ; L + R ; the KEY word
        asr     a                       ; mono in
        abs     a           b,x1        ; |mono| ; the KEY word
        tst     b                       ; nothing but moves before the Tcc
        tpl     x1,a                    ; T1: its level
        move    a,x0                    ; level
        move    x:(r3),b                ; level_s
        tfr     x0,a        x:(r5)+,x1  ; attack
        sub     b,a         x:(r5)+,b   ; d = level - level_s ; release
        tst     a           a,x0        ; nothing between this and the Tcc
        tpl     x1,b                    ; rising: attack
        move    b,y1
        mpy     x0,y1,a     x:(r3),b    ; k*d ; level_s
        add     b,a         x:(r5)+,x0  ; level_s ; K/4
        move    a,y1
        mpy     x0,y1,a     a,x:(r3)
        asl     a           x:(r5)+,y0  ; -1.0
        move    a,x0                    ; Lv/2 (the limiting move: Lv <= 2)
        mpy     x0,x0,a                 ; (Lv/2)^2
        asl     a           x:(r5)+,y1  ; Lv^2/2 ; the dip's a
        add     y0,a                    ; t = Lv^2/2 - 1  (-1 .. 1)
        mpy     x0,y1,b     a,x1        ; a*Lv/2  (x0 = Lv/2 >= 0) ; t (clean)
        asl     b           x1,x0       ; a*Lv
        mpy     x0,x0,a                 ; t^2
        add     b,a         x:(r5)+,y1  ; gr = t^2 + a*Lv ; makeup/4
        move    a,x0                    ; gr (the limiting move: <= 1)
        mpy     x0,y1,a     x:(r4),x0
        move    a,y1                    ; gr*makeup/4
        mpy     x0,y1,a     x:(r4+n4),x0
        asl     #$2,a,a
        mpy     x0,y1,a     a,x:(r4)+
        asl     #$2,a,a
        move    a,x:(r4)-
; ---- WIDTH: mid stays, side scales ---------------------------------------
ch_capd:
        move    x:(r4),b                ; L
        tfr     b,a         x:(r4+n4),x0        ; R
        add     x0,a        (r5)+n5     ; COMP off: past its ring words
        asr     a           x:(r5)+,y1  ; mid ; side gain / 2
        sub     x0,b        a,x1        ; mid
        asr     b                       ; side
        move    b,x0
        mpy     x0,y1,a     x1,b
        asl     a                       ; the halving undone in the guard bits
        move    a,y0                    ; scaled side
        add     y0,b                    ; mid + side
        tfr     x1,a        b,x1        ; wet L, limited as a store would
        sub     y0,a        x:(r0),b    ; mid - side = wet R ; dry L
; ---- MIX and write back --------------------------------------------------
        tfr     x1,a        a,y0        ; wet L ; wet R, limited
        sub     b,a
        asr     a           x:(r5)+,y1  ; m (the ring's last word: r5 turns)
        move    a,x0
        mpy     x0,y1,a
        asl     a
        add     b,a         x:(r0+n0),b ; dry R
        tfr     y0,a        a,x:(r0)
        sub     b,a         (r0)+n0
        asr     a
        move    a,x0
        mpy     x0,y1,a                 ; y1 still m
        asl     a
        add     b,a
        move    a,x:(r0)+n0             ; the frame advance: n0 = 1, two steps
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
; In: a = x, y1 = (0.5+d)/2, r3 -> the DC blocker's x1 (y1 the word above),
; r6 -> the ring (d, d/2, comp/2, k = 1.0, R, the output scale). Out: a (the caller
; clips it and stores it as the blocker's y1), y1 = the output scale.
;   xin = x*(0.5 + d)                           ((0.5+d)/2, halved)
;   u   = 1 - |xin|      (may go negative: the JSFX's linear extension past
;                         +-1 is exactly the curve with u^P dropped, so the
;                         table lookup clamps u to 0 and the rest is linear)
;   T   = u - u^P, P = ln(10) + 1 = 3.3026     (TUBE_UP: u^P/2 at 17 points)
;   y   = xin + (d/2)*T for xin > 0, xin - d*T for xin < 0   (asymmetric: the
;                         negative half is driven twice as hard -- the tube)
;   out = 2 * y * comp(d), then the DC blocker (k = 1.0, R = 0.999, both
;                         from the ring).
; Everything runs HALVED (xin/2 <= 0.75, u/2, T/2, y/2) and the post gain is
; comp/4 doubled back twice. STRAIGHT-LINE: no branch. Every mpy x0,y1 (the
; audited-signed order) except the blocker's k*x1; each Tcc reads the tst
; right before it. Clobbers x0, x1, y0, y1, a, b, n1, n2.
chtube:
        move    a,x0                    ; x (LIMITING: the input clip)
        mpy     x0,y1,a     #$40,b      ; xin/2  (|.| <= 0.75) ; 0.5
        abs     a           a,x1        ; x1 = xin/2
        sub     a,b         #$0,x0      ; u/2 = 0.5 - |xin/2|, in [-0.25, 0.5]
        tst     b           b,y0        ; park u/2 -- nothing between this
        tmi     x0,b                    ; and the Tcc: the lookup's max(u, 0)/2
        move    b,a                     ; the copy the fraction is cut from
        asr     #$12,b,b                ; u/2 >> 18 = idx (1/32 steps)
        move    b1,n1
        move    b1,n2
        and     #>$3ffff,a              ; the 18 bits under the step
        asl     #$5,a,a                 ; frac, Q23
        move    a,x0
        move    p:(r1+n1),b             ; UP[idx] = u^P / 2
        move    p:(r2+n2),y1            ; its slope, UP[idx+1] - UP[idx]  (>= 0)
        mac     x0,y1,b     y0,a        ; u^P / 2 = UP[idx] + frac * slope ; u/2
        sub     b,a         x:(r6)+,y1  ; T/2 = (u - u^P)/2 ; d
        move    a,x0                    ; T/2
        mpy     x0,y1,a     x1,b        ; d * T/2 ; xin/2
        neg     a           x:(r6)+,y1  ; the negative half's term ; d/2
        mpy     x0,y1,a     a,y0        ; the positive half's ; the negative's
        tst     b           x:(r6)+,y1  ; the sign of xin/2 -- nothing between
        tmi     y0,a                    ; this and the Tcc ; comp/2
        add     x1,a        x:(r3),x1   ; y/2 = xin/2 + term ; the blocker's x1
        move    a,x0
        mpy     x0,y1,a     x:(r6)+,y1  ; y*comp/4 ; k = 1.0
        asl     #$2,a,a                 ; *4 -> y*comp: the JSFX's -6 dB default
        move    a,x0                    ; x, the DC blocker's input (LIMITING)
        mpy     x1,y1,b                 ; k*x1 (mpysu: y1 is positive)
        tfr     x0,a        x0,x:(r3)+  ; x1 <- x
        sub     b,a         x:(r3),x0   ; x - k*x1 ; the blocker's y1
        move    x:(r6)+,y1              ; R = 0.999
        mac     x0,y1,a     x:(r6)+,y1  ; + R*y1 ; the output scale
        rts

; chtape -- TapeHead per channel (JClones_TapeHead.jsfx, MIT).
; In: a = Xs = x/4, y1 = k2, r3 -> y2 (y1 the word below), both kept at /4
; (the port's headroom: |y1| <= 1.46, |y2| <= 1.95 true), r6 -> the ring
; (k1, k3mag, d/8, trim, the output scale), y0 = 0.7. Out: b = (g3*clip(y3)
; + ss(d*y1) + ss(d*y2)) * trim, up to 2.2, CLIPPED (the JSFX's own output
; clip) and then scaled by the block's unity trim (1/11)/d8; y1 = the output
; scale. STRAIGHT-LINE: no branch of any kind (cycle_count.py charges the
; span at each call). Every mpy and mac is x0,y1, y0,x0, x0,x0 or x1,x0 (the
; signed encodings); every clip is a LIMITING move into x0. g3*trim is one
; coefficient: the product is exact, so it equals the halved coefficient's
; product doubled and negated. Clobbers x0, x1, y1,
; a, b; reads y0.
;   y1 += k2*y2 ; y3 = k1*y1 + y2 - x ; y2 -= k3mag*y3      (k3 = -1.4 k2)
;   ss(v) = 1.5v - 0.5v^3 on v = clip(d*y1), clip(d*y2)      (v = 32*(y1/4*d/8))
chtape:
        move    a,x1                    ; Xs
        move    x:(r3)-,x0              ; y2
        mpy     x0,y1,a     x:(r3),b
        add     b,a         x:(r6)+,y1  ; y1n = y1 + k2*y2 ; k1 = 5/7
        move    a,x0
        mpy     x0,y1,a     a,x:(r3)+   ; (the store is y1n, limited)
        move    x:(r3),b
        add     b,a         x:(r6)+,y1  ; k3mag
        sub     x1,a        #>$983444,x1        ; y3 = k1*y1n + y2 - Xs ; g3*trim = -0.81
        move    a,x0
        mpy     x0,y1,a     x:(r3),b
        sub     a,b         x:(r6)+,y1  ; y2n = y2 - k3mag*y3 ; d/8
        tfr     x0,a        b,x:(r3)-
        asl     #$2,a,a                 ; 4*y3
        move    a,x0                    ; LIMITING move: clip(y3)
        mpy     x1,x0,b     x:(r3)+,x0  ; b = g3*trim*clip(y3) ; y1n/4
        mpy     x0,y1,a
        asl     #$5,a,a                 ; v = d*y1n
        move    a,x0                    ; LIMITING move: clip(v)
        mpy     x0,x0,a                 ; v^2
        tfr     x0,a        a,x1
        mac     -x1,x0,a                ; v - v^3
        asr     a
        add     x0,a                    ; ss(v) = 1.5v - 0.5v^3
        move    a,x0
        mac     y0,x0,b     x:(r3),x0   ; + 0.7 ss (y0, the caller's) ; y2n/4
        mpy     x0,y1,a                 ; (y1 still d/8)
        asl     #$5,a,a
        move    a,x0
        mpy     x0,x0,a
        tfr     x0,a        a,x1
        mac     -x1,x0,a
        asr     a           x:(r6)+,y1  ; the trim (1/11)/d8 + 0.023
        add     x0,a
        move    a,x0
        mac     y0,x0,b                 ; + 0.7 ss
        move    b,x0                    ; LIMITING move: the JSFX's output clip
        mpy     x0,y1,b     x:(r6)+,y1  ; * the trim ; the output scale
        rts
