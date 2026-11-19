; ---------------------------------------------------------------------------
; SPECTRUM -- a filter pedal: LADR (the zero-delay Moog ladder), SEM (the
; zero-delay SEM SVF, LP -> BP -> HP by SHPE), ISO (an isolator, Airwindows Capacitor2), VOWL (three
; constant-peak-gain formant resonators morphed by FREQ); ENV and LFO onto
; the cutoff; mid/side WDTH. Insert
; contract: frames in place at
; x:(r0)/x:(r0+n0), knobs from r6, state in this instance's r7 block. FX1
; only: init reads the allocator base and an FX2 instance runs as a dry pass.
; Defaults are a bit-exact passthrough. Every mpy is `mpy x0,y1` (fs_qs's
; `mpy y0,x0` is the other audited-signed order) but the
; VOWL decode's `mpy x1,y1,b` (audited: R' > 0; build_bus.MPYSU_AUDITED);
; every clip is the store limiter; every Tcc reads the one compare above it
; with nothing but moves between.
;
; r7 block (raw slots; init zeroes $00..$3f, a MODE change $00..$17 + $26/$27):
;   $00..$17  the mode's states: SVF none here (its s0/s1 pairs are at $34);
;             VOWL x1 x2 (y1 y2)x3 per channel, L $00 R $08; LADR s0..s3
;             halved, L $00 R $04; CAP hp A..F, lp A..F per channel, L $00
;             R $0c. One mode per block, cleared on a MODE change.
;   $10..$18  the per-block coefficients the decode writes and the prologues
;             copy into the streams: VOWL m1 $10..$12, a2 $13..$15, b0
;             $16..$18; LADR G $10, G(1-G) $11, G^2(1-G) $12, k/4 $13, d/2
;             $14, dG $15, Grun $16 (persistent), G^3(1-G) $17, 1-G $18
;             (LADR's overlap VOWL's: one mode per block)
;   $1e       the block's input peak (the follower's; written after the loop)
;   $1f $20 $21  c4, g2 (this block's target), R
;   $22       CAP's rotation count (persistent)
;   $23 $24 $25  kLP kBP kHP (SHPE's crossfade, per block)
;   $26       CAP lpBase (persistent chase)
;   $27       no reader; the MODE-change clear stores 0 here beside $26
;   $2c       WDTH's side gain / 2
;   $2d       the mode flag: 0 SVF 1 VOWL 2 LADR 3 CAP
;   $2e $2f   g2run (the cutoff ramp, persistent) and dg
;   $30       the FX2 flag (1 = dry pass)
;   $31 $32 $33  LFO phase (persistent), env (persistent), d
;   $34..$37  the SVF's states s0L s1L s0R s1R (persistent)
;   $38       the MODE latch (the mode-change clear)
;   $40..$45  CAP's rotation table 3 4 5 3 4 5 (init)
;   $46 $47   ENV fall, LFO inc; $48 vg/8 (VOWL); $49 lfo, then VOWL's frac
;   $4e $4f   the P table's base, FREQm
;   $50..$56  the SVF stream (dg, c4 d kLP kHP kBP, WDTH); its steps $76..$7a
;   $5c..$5f  CAP's constants ring (gn/16 hpBase lpBase trim/2; m2 = 3)
;   $60..$69  the LADR stream (G' dG G^3(1-G) G^2(1-G) G(1-G) 1-G k/4 d/2 M/4 WDTH)
;   $68..$75  the VOWL stream (b0 m1 a2 gain x3, vg/8, WDTH; overlaps LADR's:
;             each is rebuilt by its own mode's prologue every block)
;   $7c..$7f  CAP's amounts ring (m1 = 3)
;   $2b       1 once this mode's ramped stream words started at their
;             targets (0 at init and on a MODE change; fs_rset)
;   $39..$3b  CAP's per-sample steps (gn/16 lpBase trim/2); $76..$7f the
;             other modes' per-sample steps (per block, fs_rbase), CAP's
;             gn/16 and trim/2 targets at $76/$77
;   free: $19..$1d, $27 (written 0 on a MODE change, never read), $28..$2a, $3c..$3f, $4a..$4d
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
; ---- EVERY PERSISTENT SLOT IS ZEROED HERE -------------------
        clr     a
        move    r7,r5
        move    #>$ffffff,m5
        do      #>64,>fs_iz            ; $00..$3f
        move    a,x:(r5)+
fs_iz:
        nop
        move    b,x:(r7+$30)            ; the FX2 flag (1 = dry pass), after the clear
        move    a,x:(r7+$2e)            ; g2run and dg: the ramp starts from 0
        move    a,x:(r7+$2f)
        move    #>$3,x0                 ; CAP's rotation: the third pole of each
        move    x0,x:(r7+$40)           ; sample by count (3 4 5 3 4 5), read
        move    x0,x:(r7+$43)           ; per sample at $40 + count
        move    #>$4,x0
        move    x0,x:(r7+$41)
        move    x0,x:(r7+$44)
        move    #>$5,x0
        move    x0,x:(r7+$42)
        move    x0,x:(r7+$45)
        rts

proc:
        move    x:(r7+$30),a           ; an FX2 slot: dry, nothing written
        tst     a
        bne     fs_end
; ===========================================================================
; PER-BLOCK KNOB DECODE
        move    x:(r6+$4),a             ; a knob word: bit 23 clear, a2 = 0
        and     #>$7f0000,a
        move    a1,x0                   ; (no clean reload: the input was positive)
        move    a1,y1
        move    a1,x1                   ; LSP, kept for the fall below
        mpy     x0,y1,a                 ; LSP^2
        move    a,x0
        move    #>$7000,y1              ; $7000 * LSP^2 + $100: the LFO's phase
        mpy     x0,y1,a                 ; step per block, $100 (0.09 Hz) ..
        add     #>$100,a                ; $7100 (10 Hz), square-law
        move    a,x:(r7+$47)            ; lfo inc
        move    x1,x0                   ; LSP again (decoded once, above)
        move    #$0f,y1
        mpy     x0,y1,a                 ; LSP * $1e00 in Q23
        neg     a
        add     #>$7fe000,a             ; fall = 1 - $2000/2^23 - LSP*$1e00: the
        move    a,x:(r7+$46)            ; envelope's per-block release, 0.999 .. 0.99

; ---- LFO: phase += inc, triangle -> bipolar Q23 ---------------------------
        move    x:(r7+$31),a
        move    x:(r7+$47),x0
        add     x0,a                    ; phase <= $7fffff + inc <= $7100 < 2^24:
        and     #>$7fffff,a             ; no carry into a2, which stays 0
        move    a,x:(r7+$31)
        move    #$40,x0                 ; 0.5
        sub     x0,a
        abs     a                       ; 0 .. $400000
        move    #$20,x0                 ; 0.25
        sub     x0,a
        asl     #$1,a,a                 ; -0.5 .. +0.5 -> -1 .. +1
        move    a,x:(r7+$49)            ; lfo, bipolar

; ---- ENV: env = max(last block's peak, env * fall) ------------------------
        move    x:(r7+$1e),x1           ; last block's peak
        move    x:(r7+$32),x0
        move    x:(r7+$46),y1
        mpy     x0,y1,a                 ; env * fall
        cmp     x1,a                    ; nothing between this and the Tcc
        tlt     x1,a                    ; env = max(peak, release)
        move    a,x:(r7+$32)
        clr     a
        move    a,x:(r7+$1e)            ; this block's peak starts at 0

; ---- ENV (slot 2, bipolar) and LDP (slot 3, 0..127): two depths onto the cutoff
        move    x:(r6+$2),a             ; ENV, a knob word (bit 23 clear, a2 = 0)
        and     #>$7f0000,a
        move    #$40,x0
        sub     x0,a
        asl     #$1,a,a                 ; (ENV-64)/64, -1 .. +1
        move    a,x0
        move    x:(r7+$32),y1           ; env (>= 0)
        mpy     x0,y1,a
        move    a,x1                    ; the envelope's term
        move    x:(r6+$3),a             ; LDP
        and     #>$7f0000,a
        move    a,x0                    ; LDP/128
        move    x:(r7+$49),y1           ; lfo, bipolar
        mpy     x0,y1,a                 ; (x0 signed, y1 signed: the audited order)
        add     x1,a
        move    x:(r6+$0),x0            ; FREQ
        add     x0,a                    ; FREQm
        move    #$0,x0
        tmi     x0,a                    ; clamp below at 0
        move    #$7f,x0
        cmp     x0,a
        tgt     x0,a                    ; clamp above at 127/128
        move    a,x1                    ; FREQm, kept
        move    #>$fab1e0,r5            ; the P table -- rewritten by build_bus.py
        move    #>$ffffff,m5
        move    r5,x:(r7+$4e)           ; its base, for VOWL's cosine lookup (the
                                        ; build allows the literal once per module)
        asr     #$12,a,a                ; idx
        move    a1,n5
        move    x1,a
        and     #>$3ffff,a              ; FREQm & (2^18 - 1)   (a2 = 0: FREQm >= 0)
        asl     #$5,a,a                 ; frac, Q23
        move    (r5)+n5
        move    a,x0                    ; frac
        move    p:(r5)+,y0              ; T[idx]
        move    p:(r5),b                ; T[idx+1]
        move    y0,a
        sub     a,b                     ; T[idx+1] - T[idx]  (>= 0: the table rises)
        move    b,y1
        mpy     x0,y1,a                 ; frac * diff
        add     y0,a
        move    a,x:(r7+$20)            ; g2 = tan(pi fc/fs)/2, this block's target
        move    x1,x:(r7+$4f)           ; FREQm, kept for VOWL's morph
; ---- the cutoff RAMP: dg = (g2 - g2run)/128 per block, added
; once per sample in the loop, so a fast FREQ sweep or LFO has no block-rate
; step (the ~2.8 kHz comb of a per-block jump). A 15-sample block covers
; 15/128 of the way and the next block starts from where it got to (1/16
; until 26 Sep 2026: a FREQ jump was a one-block ramp,
; tools/verify/verify_knob_clicks.py). The first block after init or a MODE
; change ($2b = 0) starts g2run AT g2.
        move    a,y1                    ; g2: g2run ($2e) steps toward it by
        lua     (r7+$2e),r1             ; dg ($2f), fs_rset's law (the post-
        lua     (r7+$2f),r3             ; increments' results are not used, so
        bsr     fs_rset                 ; m1/m3 do not matter here)
; ---- SEM-only coefficients. Other MODEs never read R, c4 or d; keep their
; per-block work off the LADR/ISO/VOWL paths. Unknown mode bytes still take
; the existing SEM fallback below.
        move    x:(r6+$c),a
        and     #>$ff0000,a
        move    a1,x0
        move    x0,a                    ; clean A2 after the mask before signed branches
        cmp     #>$30000,a
        bgt     fs_sem_coeffs
        cmp     #>$10000,a
        bne     fs_skip_sem_coeffs
fs_sem_coeffs:
        move    x:(r6+$1),x0
        move    #>$4b2350,y1            ; 0.587
        mpy     x0,y1,a
        neg     a
        add     #>$7fbe77,a             ; base = 0.998 - RES * 0.587  (>= 0.416)
        move    a,x0
        move    a,y1
        mpy     x0,y1,a                 ; base^2
        move    a,x0
        move    a,y1
        mpy     x0,y1,a                 ; base^4 = damp, the Chamberlin form's 1/Q
        asr     #$1,a,a                 ; R = damp/2: the SEM core's damping is 2R
        move    a,x:(r7+$21)
; c4 = (R + g2)/2 (so 4*c4 = 2R + g), d = 1/(1 + 2Rg + g^2) =
; (1/8) / (1/8 + R*g2/2 + g2^2/2) -- the one real division per block;
; den/8 <= 0.86 at every knob, d <= 1. Both are frozen for the block.
        move    x:(r7+$20),a
        move    x:(r7+$21),x0           ; R
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$1f)            ; c4
        move    x:(r7+$20),x0           ; g2
        move    x:(r7+$20),y1
        mpy     x0,y1,a                 ; g2^2
        move    x:(r7+$21),y1           ; R
        mac     x0,y1,a                 ; + R*g2
        add     #>$200000,a             ; + 1/4
        asr     #$1,a,a                 ; den/8
        move    a,x0
        move    #$10,y1                 ; 1/8
        move    y1,a                    ; a clean load: a0 = 0 for the divide
        andi    #$fe,ccr                ; carry clear
        do      #$18,>norep_sp_01
        div     x0,a                    ; 24 quotient bits land in a0
norep_sp_01:
        move    a0,x0
        move    x0,x:(r7+$33)           ; d
fs_skip_sem_coeffs:

; ---- MODE (slot 6 select of r6+$c, the knob field): tap coefficients; VOWL runs the bank ---
        move    x:(r6+$c),a
        and     #>$ff0000,a
        move    x:(r7+$38),x0
        move    a1,x:(r7+$38)
        sub     x0,a                    ; (a2 = 0: both positive)
        beq     fs_msame
        clr     a
        move    r7,r5
        move    #>$ffffff,m5
        do      #>24,>fs_mclr
        move    a,x:(r5)+
fs_mclr:
        nop
        move    a,x:(r7+$26)
        move    a,x:(r7+$27)
        move    a,x:(r7+$2b)            ; the new mode's stream at its targets
fs_msame:
        clr     a
        move    a,x:(r7+$2d)            ; the SVF alternative unless VOWL says so
        move    a,x:(r7+$23)
        move    a,x:(r7+$24)
        move    a,x:(r7+$25)
        move    #>$7fffff,x0
        move    x:(r6+$c),a             ; MODE, slot 6 = $c's knob field
        and     #>$ff0000,a             ; 0 LADR, 1 SEM, 2 ISO, 3 VOWL
        beq     fs_mladr
        cmp     #>$20000,a
        beq     fs_mcap
        cmp     #>$30000,a
        beq     fs_mvowl
; SEM (and anything unexpected): SHPE, slot 7 in $c's companion field,
; sweeps LP -> BP -> HP (27 Sep 2026; 0 LP, 64 notch, 127 HP from 23 Sep):
; d = (k - 64)/64 below 64, (k - 64)/63 above, and an equal-power crossfade
; between neighbours, kHP = max(0, s(d)), kLP = max(0, -s(d)),
; kBP = s(1 - |d|), s ~ sin(pi x/2) (fs_qs). Each is exactly 1 at its own
; stop and exactly 0 at the others: s(1) > 1 and the stores limit it; 127's
; d rounds up past 1, and kBP's argument is 3 LSB short of 1 - |d|, so it
; floors to 0 at both ends. At the cutoff the three taps are equal in size
; and LP/BP, BP/HP in quadrature, so the sum keeps its level across a fade.
        move    x:(r6+$c),a
        and     #>$7f00,a               ; k<<8
        move    a1,x0
        move    x0,a                    ; A2-clean (AND cleans A1 only)
        move    #>$4000,x0
        sub     x0,a                    ; (k - 64)<<8: its sign picks the half
        move    #$40,b                   ; below 64: x 1/2, x 4 below = 1/64 (short immediate: bits 23-16)
        move    #>$410411,y0            ; above: (128/63)/4, rounded up
        tgt     y0,b                    ; nothing but moves since the sub
        move    b,y1
        asl     #$8,a,a                 ; (k - 64)/128
        move    a,x0
        mpy     x0,y1,a
        asl     #$2,a,a                 ; d, -1 .. 1.0000002
        move    a,x0                    ; limited: 127's d lands on 1 - 2^-23
        move    x0,x1                   ; d, kept (fs_qs leaves x1)
        bsr     fs_qs                   ; a = s(d), odd
        move    a,b
        move    #$0,x0
        tst     a
        tmi     x0,a                    ; kHP = max(0, s(d))
        move    a,x:(r7+$25)
        neg     b
        tmi     x0,b                    ; kLP = max(0, -s(d))
        move    b,x:(r7+$23)
        move    x1,a
        abs     a
        neg     a
        add     #>$7ffffd,a             ; 1 - |d| - 3 LSB
        tmi     x0,a                    ; floored at 0: the ends
        move    a,x0
        bsr     fs_qs
        move    a,x:(r7+$24)            ; kBP = s(1 - |d|)
        bra     fs_mdone
fs_mcap:
; ---- ISO: Airwindows Capacitor2 (Chris Johnson, MIT), the
; isolator with a dielectric: a lowpass and a highpass (LOW = FREQ, HIGH =
; RES here, the knobs renamed by the mode) whose one-pole amounts are the
; knob squared, chased 1/16 per block, and per sample scaled by the signal
; itself -- |1 - x/nl|, nl = 1 + 6 (1 - NLIN/128) -- six poles per channel
; rotated three-at-a-time (modules/spectrum/capacitor2_ref.py). Per block:
; $26 lpBase (the persistent chase) and the loop's four-word constants ring
; at $5c: gn/16, hpBase, lpBase, trim/2 = 0.75/cbrt(nl) fitted in COLR.
        move    #>$3,x0
        move    x0,x:(r7+$2d)           ; the loop runs the capacitor
        move    x:(r7+$4f),x0           ; FREQm
        move    x:(r7+$4f),y1
        mpy     x0,y1,a                 ; (FREQm)^2
        move    a,x0
        move    #>$7f7cee,y1            ; 0.996
        mpy     x0,y1,a
        add     #>$008312,a             ; + 0.004
        move    x:(r7+$26),x0
        sub     x0,a
        asr     #$4,a,a
        add     x0,a
        move    a,x:(r7+$26)            ; lpBase += (target - lpBase)/16, the
                                        ; ramp's target for ring 2 (fs_cap)
; the high-pass side is a fixed 2^-12 (a ~2 Hz corner: a DC block, never a
; frozen pole); RES is the dielectric's colour (COLR).
        move    #>$000800,x0
        move    x0,x:(r7+$5d)           ; ring 1: hpBase
        move    x:(r6+$1),x0            ; C = RES/128, drawn COLR in ISO
        move    #$60,y1                 ; 6/8
        mpy     x0,y1,a
        neg     a
        add     #>$700000,a             ; nl/8 = 7/8 - 6C/8, 1/8 .. 7/8
        move    a,x1                    ; the denominator
        move    #$0f,y1                  ; 15/128 (short immediate: bits 23-16)
        mpy     x0,y1,a
        add     #>$010000,a             ; (1 + 15C)/128, < nl/8 always
        move    x1,x0
        andi    #$fe,ccr
        do      #$18,>norep_sp_02
        div     x0,a
norep_sp_02:
        move    a0,x0
        move    x0,x:(r7+$76)           ; gn/16 = (1 + 15C)/(16 nl), <= 0.993:
                                        ; ring 0's target
        move    x:(r6+$1),x0
        move    x:(r6+$1),y1
        mpy     x0,y1,a                 ; C^2
        move    a,x0
        move    #>$326e98,y1            ; 0.394
        mpy     x0,y1,a
        move    x:(r6+$1),x0
        move    #>$fb6db7,y1            ; -0.036
        mac     x0,y1,a
        add     #>$322d0e,a             ; + 0.392: trim/2 = 0.75/cbrt(nl), fitted
        move    a,x:(r7+$77)            ; trim/2: ring 3's target
        bra     fs_mdone
fs_mvowl:
        move    x:(r6+$1),a             ; RES/128
        asr     #$1,a,a
        add     #>$400000,a
        move    a,x:(r7+$48)            ; vg/8
; ---- VOWL: three parallel constant-peak-gain resonators
; (audiojs formant / resonator, JOS's two-zero form, MIT) replace the
; two-peak trick. Per formant y = b0*(x - x2) + 2*m1*y1 - a2*y2 with
; R = exp(-pi*bw/fs), m1 = R*cos(w0), a2 = R^2, b0 = (1-R^2)/2; gains
; 1 / 0.5 / 0.3. FREQm (post-modulation, so DPTH and the LFO sweep the
; vowels) morphs A E I O U: idx = FREQm >> 21 (0..3) picks the pair, frac =
; the 21 bits under it. RES narrows the bandwidths: R' = R + 0.9(1-R)*RES.
        move    #>$1,x0
        move    x0,x:(r7+$2d)           ; the loop runs the bank, not the SVF
        move    x:(r7+$4f),a            ; FREQm
        and     #>$1fffff,a
        asl     #$2,a,a                 ; (FREQm >= 0, so a2 = 0 throughout)
        move    a1,x:(r7+$49)           ; frac, all 21 bits (the lfo park is
                                        ; dead by now; 5 bits until 26 Sep
                                        ; 2026: a turn stepped the formants)
        move    x:(r7+$4f),a
        asr     #$15,a,a                ; idx 0..3 (FREQm >= 0: a2 clean)
        move    a1,x0
        move    x0,a
        move    a,b
        add     x0,b
        add     x0,b                    ; 3*idx
        move    b1,n5
        move    x:(r7+$4e),r5           ; the P table's base (saved at the g2 lookup)
        move    #>$ffffff,m5
        move    (r5)+n5
        move    #$21,n5                 ; 33
        move    (r5)+n5                 ; r5 = COS_TABLE[idx][0] (33 words past G2)
        move    #$3,n5
; One loop over the three formants. The coefficient slots are stride-1 per
; formant -- m1 at $10..$12, a2 at $13..$15, b0 at $16..$18 -- so r3 = r7 +
; $10 + k and the stores are r3-relative; the per-formant constants e_k and
; R_k sit in the P table after the COS table (manifest VOWL_ER), walked by
; r2.
        move    x:(r7+$4e),r2           ; the P table's base ...
        move    #>$ffffff,m2
        move    #$30,n2
        move    (r2)+n2                 ; ... + 48: the (e_k, R_k) pairs
        move    r7,r3
        move    #$10,n3
        move    (r3)+n3                 ; r3 = r7 + $10, formant 0's m1
        do      #3,>fs_vfz
; formant k: cw = CW[idx][k] + frac*(CW[idx+1][k] - CW[idx][k]) (p:(r5)+n5
; reads the first and steps to the next vowel, p:(r5)-n5 reads it and steps
; back; (r5)+ moves to the next formant); R' = R_k + e_k*RES narrows the band
; with RES; m1 = R'*cw = -a1/2, a2 = R'^2, b0 = (1 - a2)/2.
        move    p:(r5)+n5,y0            ; CW[idx][k]
        move    p:(r5)-n5,b             ; CW[idx+1][k]
        move    (r5)+
        move    y0,a
        sub     a,b                     ; diff
        move    b,x0
        move    x:(r7+$49),y1           ; frac
        mpy     x0,y1,a
        add     y0,a                    ; cw
        move    a,x1
        move    x:(r6+$1),x0            ; RES/128
        move    p:(r2)+,y1              ; e_k = 0.9*(1 - R_k)
        mpy     x0,y1,a
        move    p:(r2)+,y0              ; R_k = exp(-pi*bw_k/fs)
        add     y0,a                    ; R'
        move    a,y1                    ; R' > 0: safe as mpysu's second operand
        mpy     x1,y1,b                 ; m1 = cw*R' (encodes mpysu; audited)
        move    b,x:(r3)                ; $10 + k
        move    a,x0
        mpy     x0,y1,b                 ; a2 = R'^2
        move    b,x:(r3+$3)             ; $13 + k
        asr     #$1,b,b
        neg     b
        add     #>$400000,b             ; b0 = 1/2 - a2/2
        move    b,x:(r3+$6)             ; $16 + k
        move    (r3)+
fs_vfz:
        nop
        bra     fs_mdone
fs_mladr:
; ---- LADR: the Moog transistor ladder, the LINEAR zero-delay
; 4-pole (audiojs/filter moogLadder without its tanh; Zavalishin ch. 6): per
; block G = g/(1+g) = (g2/2)/(1/4 + g2/2) by the second real division, its
; powers, k/4 = 0.975*RES/128 (the linear ladder oscillates at k = 4; 3.9
; rings hard and the limiting stores bound it), d/2 = (1/4)/(1/2 + 2*(k/4)*G^4)
; by a third. Per sample (the loop's third alternative): S/8 from the four
; states stored HALVED (s/2 in $00..$03 L, $08..$0b R -- VOWL's slots, the
; two modes never run in one block), u = (x - k*S)*d, four trapezoidal
; stages y = G'(v - s) + s, s' = 2y - s, out = y4. G ramps per sample as g2
; does (Grun += dG, G' = Grun) with the block's powers frozen (the same
; approximation as the SEM's frozen d). Slots: $10 G  $11 G(1-G)  $12
; G^2(1-G)  $17 G^3(1-G)  $18 1-G  $13 k/4  $14 d/2  $15 dG  $16 Grun.
        move    #>$2,x0
        move    x0,x:(r7+$2d)           ; the loop runs the ladder
        move    x:(r6+$1),x0            ; RES/128
        move    #>$7ccccd,y1            ; 0.975
        mpy     x0,y1,a
        move    a,x:(r7+$13)            ; k/4
        move    x:(r7+$20),a            ; g2, this block's target
        asr     #$1,a,a                 ; g2/2, the numerator
        move    a,x1
        add     #>$200000,a             ; den = 1/4 + g2/2  (<= 0.71)
        move    a,x0
        move    x1,a                    ; a clean load: a0 = 0, num < den
        andi    #$fe,ccr
        do      #$18,>norep_sp_03
        div     x0,a
norep_sp_03:
        move    a0,x0                   ; G = g/(1+g), <= 0.65
        move    x0,x:(r7+$10)           ; G, the ramp's target
        move    x0,y1
        mpy     x0,y1,a                 ; G^2
        move    a,x0
        move    a,y1
        mpy     x0,y1,a                 ; G^4
        move    a,x0
        move    x:(r7+$13),y1           ; k/4
        mpy     x0,y1,a                 ; (k/4) G^4
        asl     #$1,a,a                 ; 2 (k/4) G^4 = k G^4 / 2  (<= 0.34)
        add     #>$400000,a             ; den = 1/2 + k G^4 / 2
        move    a,x0
        move    #$20,a                  ; num = 1/4 (a2 = a0 = 0): d/2 = (1/4)/den, <= 1/2
        andi    #$fe,ccr
        do      #$18,>norep_sp_04
        div     x0,a
norep_sp_04:
        move    a0,x0
        move    x0,x:(r7+$14)           ; d/2
        move    x:(r7+$10),y1           ; G
        move    #>$7fffff,a
        sub     y1,a
        move    a,x:(r7+$18)            ; 1-G
        move    a,x0
        mpy     x0,y1,a
        move    a,x:(r7+$11)            ; G(1-G)
        move    a,x0
        mpy     x0,y1,a
        move    a,x:(r7+$12)            ; G^2(1-G)
        move    a,x0
        mpy     x0,y1,a
        move    a,x:(r7+$17)            ; G^3(1-G)
        move    x:(r7+$10),a            ; G
        move    a,y1                    ; G: Grun ($16) steps toward it by dG
        lua     (r7+$16),r1             ; ($15), fs_rset's law
        lua     (r7+$15),r3
        bsr     fs_rset
fs_mdone:
; ---- WDTH (slot 5): stereo width of the output, Character's mid/side,
; drawn -64..+63; the knob word IS WDTH/128 = the side gain HALVED (64 ->
; 0.5, doubled back per sample: 0 = mono, 127 = double sides).
        move    x:(r6+$5),a
        and     #>$7f0000,a
        move    a,x:(r7+$2c)

; ---- BYPASS: the defaults are a bit-exact passthrough ---------------------
; FREQ 127, RES 0, ENV 64, LDP 0, WDTH 64, MODE 0 (LSP is inert at LDP 0 / ENV 64; slot 6 is blank).
; Every part that ever chose stock FILTER runs this on FX1 after the flash,
; so the neutral block copies nothing at all.
        move    x:(r6+$0),a
        move    #$7f,x0
        cmp     x0,a
        bne     fs_live
        move    x:(r6+$1),a
        tst     a
        bne     fs_live
        move    #$40,x0
        move    x:(r6+$2),a
        cmp     x0,a
        bne     fs_live
        move    x:(r6+$3),a
        tst     a
        bne     fs_live
        move    x:(r6+$5),a
        cmp     x0,a
        bne     fs_live
        move    x:(r6+$c),a             ; the MODE select (slot 6, the knob field
        and     #>$ff0000,a             ; since 16 Sep 2026)
        bne     fs_live                 ; AND sets Z from A1 (a2 = a0 = 0 here)
        rts                             ; BYPASS: frames untouched
fs_live:
; ===========================================================================
; THE SAMPLE LOOPS -- one `do n7` per MODE, dispatched once per block on $2d
; (0 SVF, 1 VOWL, 2 LADR, 3 CAP); each builds its own coefficient stream,
; sets its pointers, runs its loop and stores its register-held state. The
; input peak (the envelope follower's) is kept in an address register for
; the loop and stored to $1e at fs_done; the WDTH block ends every loop.
; The pricer prices the worst loop (cycle_count.py: mutually exclusive by
; construction).
; ===========================================================================
        move    #$1,n0                  ; (short immediate, stock's own form)
        move    x:(r7+$2d),a
        tst     a
        beq     fs_svf
        cmp     #$1,a                   ; (6-bit immediate)
        beq     fs_vowl
        cmp     #$2,a                   ; (6-bit immediate)
        beq     fs_ladr
        bra     fs_cap

; ---------------------------------------------------------------------------
; SVF: the SEM zero-delay SVF, LP -> BP -> HP by SHPE
; ---------------------------------------------------------------------------
fs_svf:
; the stream at $50 on r4 (r1 walks a copy per sample): dg, then c4 d kLP
; kHP kBP for L and again for R, then WDTH's side gain; r6 -> the states
; s0L s1L s0R s1R at $34 (r2 walks a copy). The cutoff ramp g2run += dg runs
; once per sample here (the other modes step g2run per block by n7 dg, the
; same end value: fs_gramp).
        move    r7,r4
        move    #$50,n4
        move    (r4)+n4
        move    #>$ffffff,m4
        move    r4,r1
        move    #>$ffffff,m1
        move    x:(r7+$2f),x0           ; dg
        move    x0,x:(r1)+
        bsr     fs_rbase                ; r3 -> the steps at $76
        move    x:(r7+$1f),y1           ; c4
        bsr     fs_rset
        move    x:(r7+$33),y1           ; d
        bsr     fs_rset
        move    x:(r7+$23),y1           ; kLP
        bsr     fs_rset
        move    x:(r7+$25),y1           ; kHP
        bsr     fs_rset
        move    x:(r7+$24),y1           ; kBP
        bsr     fs_rset
        move    x:(r7+$2c),x0           ; WDTH's side gain / 2
        move    x0,x:(r1)+
        move    #>$1,x0
        move    x0,x:(r7+$2b)           ; primed
        move    r7,r6
        move    #$34,n6
        move    (r6)+n6
        move    #>$ffffff,m2
        move    #$0,r5                  ; the input peak
        do      n7,>fs_sz
        move    r4,r1                   ; the stream (first: the input peak below
        move    r6,r2                   ; the states  covers the AGU's wait)
; ---- input peak for the envelope follower (mono, pre-filter) --------------
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        abs     a
        move    r5,b
        max     a,b                     ; peak = max(peak, |mono|)
        move    b1,r5
; ---- the cutoff ramp: g2run += dg, once per sample for both channels -------
        move    x:(r1)+,x0              ; dg
        move    x:(r7+$2e),a
        add     x0,a
        move    a,x:(r7+$2e)            ; g2run (never past the rail: the
                                        ; target is <= 0.91 and the ramp
                                        ; stops at it)
; ---- the stream's ramps: c4 d kLP kHP kBP, one step each (r3 walks the steps)
        move    n3,r3
        bsr     fs_r3                   ; c4 d kLP
        move    x:(r3)+,x0
        move    x:(r1),a
        add     x0,a    x:(r3)+,x0
        move    a,x:(r1)+               ; kHP
        move    x:(r1),a
        add     x0,a
        move    a,x:(r1)+               ; kBP
; ---- channels L then R: one body (27 Sep 2026; two copies before), the same
; five stream words for both, the states walked on by r2; r3 (spent by the
; ramps above) walks the frame. It paid for SHPE's crossfade in words; the
; SVF loop is Spectrum's cheapest, and ISO's prices the station.
        move    r0,r3
        do      #2,>fs_sch
        move    r4,r1
        move    (r1)+                   ; on c4
        move    x:(r3),x1               ; x
        move    x:(r2)+,x0              ; s0
        move    x0,y0                   ; s0, kept for bp
        move    x:(r1)+,y1              ; c4 = (R + g2)/2
        mpy     x0,y1,a
        asl     #$2,a,a                 ; (2R + g) * s0
        move    x:(r2)-,x0              ; s1 (r2 back on s0)
        add     x0,a  x1,b              ; b = x
        sub     a,b                     ; t
        asr     #$3,b,b
        move    b,x0                    ; t8, |t8| <= 0.63
        move    x:(r1)+,y1              ; d
        mpy     x0,y1,a
        asl     #$3,a,a
        move    a,x0                    ; hp, limited -- the resonance clamp
        move    a,x1                    ; hp, kept for the tap (x is spent)
        move    x:(r7+$2e),y1           ; g2 = g2run this sample
        mpy     x0,y1,b
        asl     b  y0,a                 ; p = g*hp; a = s0
        add     b,a                     ; bp
        add     b,a  a,y0               ; s0'; y0 = bp, limited, kept for the tap
        move    a,x:(r2)+               ; s0' (r2 -> s1)
        move    y0,x0
        mpy     x0,y1,b                 ; y1 is still g2
        asl     #$1,b,b                 ; q = g*bp
        move    x:(r2),a                ; s1
        add     b,a                     ; lp
        add     b,a  a,x0               ; s1'; x0 = lp, limited, for the tap
        move    a,x:(r2)+               ; s1' (r2 -> the next channel's s0)
; wetA = kLP*lp + kHP*hp + kBP*bp (exact in the accumulator, any order)
        move    x:(r1)+,y1              ; kLP
        mpy     x0,y1,a     x1,x0       ; hp
        move    x:(r1)+,y1              ; kHP
        mac     x0,y1,a     y0,x0       ; bp
        move    x:(r1)+,y1              ; kBP
        mac     x0,y1,a
        move    a,x:(r3)+               ; out (limited)
fs_sch:
        nop
; WIDTH
        move    x:(r0),a                ; L
        move    x:(r0+n0),x0            ; R
        add     x0,a
        asr     #$1,a,a
        sub     x0,a        a,x1        ; mid ; mid - R = (L - R)/2, floor
        move    a,x0                    ; side
        move    x:(r1)+,y1              ; side gain / 2
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,y0                    ; scaled side
        move    x1,a
        add     y0,a
        move    a,x:(r0)+
        move    x1,a
        sub     y0,a
        move    a,x:(r0)+               ; the frame advance
fs_sz:
        nop
        bra     fs_done

; ---------------------------------------------------------------------------
; VOWL: the three-formant bank
; ---------------------------------------------------------------------------
fs_vowl:
; the stream at $68 on r5 (r1 walks a copy per channel): b0 m1 a2 gain/2 per
; formant, vg/8, WDTH's side gain; r3 -> the eight states per channel (x1
; x2, then y1 y2 per formant), L at $00, R at $08 -- the L pass leaves r3 on
; R's; n3 = 2 steps a pair.
        bsr     fs_gramp
        move    r7,r5
        move    #$68,n5
        move    (r5)+n5
        move    #>$ffffff,m5
        move    r5,r1
        move    #>$ffffff,m1
        bsr     fs_rbase                ; r3 -> the steps at $76
        move    r7,r2
        move    #$10,n2
        move    (r2)+n2                 ; r2 -> formant 0's m1 at $10
        move    #>$ffffff,m2
        do      #3,>fs_vbz
        move    x:(r2+$6),y1            ; b0 ($16 + k)
        bsr     fs_rset
        move    x:(r2),y1               ; m1 ($10 + k)
        bsr     fs_rset
        move    x:(r2+$3),y1            ; a2 ($13 + k)
        bsr     fs_rset
        move    (r1)+                   ; the formant's gain (below)
        move    (r2)+
fs_vbz:
        nop
        move    #$40,x0                 ; the gains 1, 0.5, 0.3, halved
        move    x0,x:(r7+$6b)
        move    #$20,x0
        move    x0,x:(r7+$6f)
        move    #>$133333,x0
        move    x0,x:(r7+$73)
        move    x:(r7+$48),y1           ; vg/8
        bsr     fs_rset
        move    x:(r7+$2c),x0           ; WDTH's side gain / 2
        move    x0,x:(r1)+
        move    #>$1,x0
        move    x0,x:(r7+$2b)           ; primed
        move    n3,n4                   ; the loop walks the steps on r4
        move    #$2,n3
        move    #$0,r6                  ; the input peak
        do      n7,>fs_vz
; ---- input peak for the envelope follower (mono, pre-filter) --------------
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        abs     a
        move    r6,b
        max     a,b
        move    b1,r6
; ---- the stream's ramps: b0 m1 a2 per formant and vg/8, one step each (r3
; walks the steps from n4; r1 the stream, reloaded by the L pass)
        move    r5,r1
        move    n4,r3
        bsr     fs_r3                   ; formant 0
        move    (r1)+                   ; its gain
        bsr     fs_r3                   ; formant 1
        move    (r1)+
        bsr     fs_r3                   ; formant 2
        move    (r1)+
        move    x:(r3)+,x0
        move    x:(r1),a
        add     x0,a
        move    a,x:(r1)+               ; vg/8
; ===================== channel L =====================
        move    x:(r0),x1               ; x
        move    r7,r3                   ; states at $00
        move    r5,r1                   ; the stream
; dx/2 = (x - x2)/2, shared by the three resonators; then x2 <- x1 <- x
        move    x:(r3),y0               ; x1
        move    x1,x:(r3)+              ; x1 <- x
        move    x:(r3),x0               ; x2
        move    y0,x:(r3)+              ; x2 <- x1; r3 -> formant 0's y1
        move    x1,a
        sub     x0,a
        asr     #$1,a,a
        move    a,x1                    ; dx/2 (|.| <= 1)
; formant 0: y = 2*b0*(dx/2) + 2*m1*y1 - a2*y2; then y2 <- y1 <- y
        move    x1,x0                   ; dx/2
        move    x:(r1)+,y1              ; b0
        mpy     x0,y1,a  x:(r3)+,x0     ; x0 = y1
        asl     #$1,a,a
        move    x:(r1)+,y1              ; m1 = -a1/2
        mpy     x0,y1,b
        asl     #$1,b,b
        add     b,a  x0,b               ; b = y1, for the shift
        move    x:(r3),x0               ; y2
        move    b,x:(r3)-               ; y2 <- y1
        move    x:(r1)+,y1              ; a2
        mpy     x0,y1,b
        sub     b,a                     ; y
        move    a,x:(r3)+n3             ; y1 <- y (limited); on to the next pair
        move    a,x0                    ; y, limited
        move    x:(r1)+,y1              ; the formant's gain, halved
        mpy     x0,y1,a
        move    a,y0                    ; the sum so far (halved)
; formant 1
        move    x1,x0                   ; dx/2
        move    x:(r1)+,y1              ; b0
        mpy     x0,y1,a  x:(r3)+,x0     ; x0 = y1
        asl     #$1,a,a
        move    x:(r1)+,y1              ; m1
        mpy     x0,y1,b
        asl     #$1,b,b
        add     b,a  x0,b
        move    x:(r3),x0               ; y2
        move    b,x:(r3)-
        move    x:(r1)+,y1              ; a2
        mpy     x0,y1,b
        sub     b,a
        move    a,x:(r3)+n3
        move    a,x0
        move    x:(r1)+,y1              ; gain
        mpy     x0,y1,a
        add     y0,a
        move    a,y0
; formant 2
        move    x1,x0
        move    x:(r1)+,y1
        mpy     x0,y1,a  x:(r3)+,x0
        asl     #$1,a,a
        move    x:(r1)+,y1
        mpy     x0,y1,b
        asl     #$1,b,b
        add     b,a  x0,b
        move    x:(r3),x0
        move    b,x:(r3)-
        move    x:(r1)+,y1
        mpy     x0,y1,b
        sub     b,a
        move    a,x:(r3)+n3             ; r3 -> R's states
        move    a,x0
        move    x:(r1)+,y1
        mpy     x0,y1,a
        add     y0,a
        move    a,y0
; wetA = 2 * the halved sum (= y0 + 0.5*y1 + 0.3*y2), limited -- as sum + sum,
; NOT an asl: a0 still holds the last product's low bits and a shift would
; carry its top bit into a1; the add leaves a2:a1 exactly as the shift of the
; reloaded sum did
        add     y0,a
        move    a,x0                    ; wetA (limited)
        move    x:(r1)+,y1              ; vg/8
        mpy     x0,y1,a
        asl     #$3,a,a                 ; wetA * vg, the store limits
        move    a,x:(r0)                ; out (limited)
; ===================== channel R =====================
        move    x:(r0+n0),x1            ; x
        move    r5,r1                   ; the stream (r3 is on R's states)
        move    x:(r3),y0               ; x1
        move    x1,x:(r3)+
        move    x:(r3),x0               ; x2
        move    y0,x:(r3)+
        move    x1,a
        sub     x0,a
        asr     #$1,a,a
        move    a,x1                    ; dx/2
; formant 0
        move    x1,x0
        move    x:(r1)+,y1
        mpy     x0,y1,a  x:(r3)+,x0
        asl     #$1,a,a
        move    x:(r1)+,y1
        mpy     x0,y1,b
        asl     #$1,b,b
        add     b,a  x0,b
        move    x:(r3),x0
        move    b,x:(r3)-
        move    x:(r1)+,y1
        mpy     x0,y1,b
        sub     b,a
        move    a,x:(r3)+n3
        move    a,x0
        move    x:(r1)+,y1
        mpy     x0,y1,a
        move    a,y0
; formant 1
        move    x1,x0
        move    x:(r1)+,y1
        mpy     x0,y1,a  x:(r3)+,x0
        asl     #$1,a,a
        move    x:(r1)+,y1
        mpy     x0,y1,b
        asl     #$1,b,b
        add     b,a  x0,b
        move    x:(r3),x0
        move    b,x:(r3)-
        move    x:(r1)+,y1
        mpy     x0,y1,b
        sub     b,a
        move    a,x:(r3)+n3
        move    a,x0
        move    x:(r1)+,y1
        mpy     x0,y1,a
        add     y0,a
        move    a,y0
; formant 2
        move    x1,x0
        move    x:(r1)+,y1
        mpy     x0,y1,a  x:(r3)+,x0
        asl     #$1,a,a
        move    x:(r1)+,y1
        mpy     x0,y1,b
        asl     #$1,b,b
        add     b,a  x0,b
        move    x:(r3),x0
        move    b,x:(r3)-
        move    x:(r1)+,y1
        mpy     x0,y1,b
        sub     b,a
        move    a,x:(r3)+n3
        move    a,x0
        move    x:(r1)+,y1
        mpy     x0,y1,a
        add     y0,a
        move    a,y0
        add     y0,a
        move    a,x0                    ; wetA (limited)
        move    x:(r1)+,y1              ; vg/8
        mpy     x0,y1,a
        asl     #$3,a,a
        move    a,x:(r0+n0)             ; out (limited)
; WIDTH
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        sub     x0,a        a,x1        ; mid
        move    a,x0                    ; side
        move    x:(r1)+,y1              ; side gain / 2
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,y0
        move    x1,a
        add     y0,a
        move    a,x:(r0)+
        move    x1,a
        sub     y0,a
        move    a,x:(r0)+
fs_vz:
        nop
        move    r6,a
        move    a,x:(r7+$1e)            ; the block's peak
        bra     fs_end

; ---------------------------------------------------------------------------
; LADR: the linear zero-delay Moog ladder
; ---------------------------------------------------------------------------
fs_ladr:
; the stream at $60 on r2 (r1 walks a copy per channel; r6 = r2 + 2 is R's
; start): G' (written per sample), dG, then G^3(1-G) G^2(1-G) G(1-G) 1-G k/4
; d/2 M/4 for both channels, WDTH's side gain. The per-sample ramp Grun +=
; dG runs in n4 and goes back to $16 after the loop; G' = Grun (the ramp
; never passes G, and G = g/(1+g) <= 0.65 at the table's top, so the old
; clamp at $7f0000 never fired). r3 -> the states s0..s3 at $00 (L) and
; $04 (R): the L pass leaves r3 on R's. M = min(1 + k/2, 2.3) is the RES
; makeup on the ladder's output (README).
        bsr     fs_gramp
        move    x:(r7+$13),x0           ; k/4
        move    #$40,y1                  ; 0.5 (short immediate: bits 23-16)
        mpy     x0,y1,a
        add     #>$200000,a             ; M/4 = (1 + k/2)/4
        move    #>$499999,x0            ; 2.3/4
        cmp     x0,a
        tgt     x0,a                    ; M <= 2.3
        move    a,y0                    ; (fs_rset clobbers x1)
        move    r7,r2
        move    #$60,n2
        move    (r2)+n2
        move    #>$ffffff,m2
        move    r2,r1
        move    #>$ffffff,m1
        move    (r1)+                   ; slot 0: G', per sample
        move    x:(r7+$15),x0           ; dG
        move    x0,x:(r1)+
        move    r1,r6                   ; R's start
        move    x:(r7+$17),x0
        move    x0,x:(r1)+
        move    x:(r7+$12),x0
        move    x0,x:(r1)+
        move    x:(r7+$11),x0
        move    x0,x:(r1)+
        move    x:(r7+$18),x0
        move    x0,x:(r1)+
        bsr     fs_rbase                ; r3 -> the steps at $76
        move    x:(r7+$13),y1           ; k/4
        bsr     fs_rset
        move    x:(r7+$14),y1           ; d/2
        bsr     fs_rset
        move    y0,y1                   ; M/4
        bsr     fs_rset
        move    x:(r7+$2c),x0           ; WDTH's side gain / 2
        move    x0,x:(r1)+
        move    #>$1,x0
        move    x0,x:(r7+$2b)           ; primed
        move    #$4,n1                  ; the loop's hop from G^3(1-G) to k/4
        move    x:(r7+$16),a            ; Grun, where the last block ended
        move    a1,n4
        move    #$0,r4                  ; the input peak
        do      n7,>fs_lz
; ---- input peak for the envelope follower (mono, pre-filter) --------------
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        abs     a
        move    r4,b
        max     a,b
        move    b1,r4
; ---- the ramp: Grun += dG; G' = Grun into the stream ----------------------
        move    r2,r1
        move    (r1)+
        move    x:(r1)+,x0              ; dG (r1 -> G^3(1-G))
        move    n4,a
        add     x0,a
        move    a1,n4
        move    a,x:(r2)                ; G' (slot 0)
; ---- the stream's ramps: k/4 d/2 M/4, one step each (r3 walks the steps)
        move    (r1)+n1                 ; r1 -> k/4
        move    n3,r3
        bsr     fs_r3                   ; k/4 d/2 M/4
        move    r6,r1                   ; back on G^3(1-G)
; ===================== channel L =====================
        move    x:(r0),b                ; x
        move    r7,r3                   ; states s0..s3 at $00
        bsr     fs_lcore
        move    a,x0                    ; wetA (limited)
        move    x:(r1)+,y1              ; M/4, the RES makeup
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x:(r0)                ; out (limited)
; ===================== channel R =====================
        move    x:(r0+n0),b
        move    r6,r1                   ; the same stream (r3 is on R's states)
        bsr     fs_lcore
        move    a,x0
        move    x:(r1)+,y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x:(r0+n0)
; WIDTH
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        sub     x0,a        a,x1        ; mid
        move    a,x0                    ; side
        move    x:(r1)+,y1              ; side gain / 2
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,y0
        move    x1,a
        add     y0,a
        move    a,x:(r0)+
        move    x1,a
        sub     y0,a
        move    a,x:(r0)+
fs_lz:
        nop
        move    n4,a
        move    a,x:(r7+$16)            ; Grun for the next block
        move    r4,a
        move    a,x:(r7+$1e)            ; the block's peak
        bra     fs_end

; ---------------------------------------------------------------------------
; CAP: Airwindows Capacitor2 (Chris Johnson, MIT), the isolator
; ---------------------------------------------------------------------------
fs_cap:
; ring 0, 2 and 3 (gn/16 lpBase trim/2) are run values stepped once per
; sample toward the decode's targets (fs_rset, steps at $39..$3b); hpBase
; is fixed
        move    r7,r1
        move    #$5c,n1
        move    (r1)+n1
        move    #>$ffffff,m1
        move    r7,r3
        move    #$39,n3
        move    (r3)+n3
        move    #>$ffffff,m3
        move    x:(r7+$76),y1           ; gn/16
        bsr     fs_rset
        move    (r1)+                   ; hpBase
        move    x:(r7+$26),y1           ; lpBase
        bsr     fs_rset
        move    x:(r7+$77),y1           ; trim/2
        bsr     fs_rset
        move    #>$1,x0
        move    x0,x:(r7+$2b)           ; primed
; r1 -> the four-word amounts ring at $7c (m1 = 3: fs_ccore writes and reads
; it round once per pole pair), r2 -> the four-word constants ring at $5c
; (m2 = 3: gn/16 hpBase lpBase trim/2, written by the MODE decode, read once
; per channel), r6 -> the six-word rotation table at $40, r4 the input
; peak, n2 the rotation count (back to $22 after the loop). m1/m2 go back
; to linear at fs_end.
        bsr     fs_gramp
        move    r7,r1
        move    #$7c,n1
        move    (r1)+n1
        move    #$3,m1
        move    r7,r2
        move    #$5c,n2
        move    (r2)+n2
        move    #$3,m2
        move    r7,r6
        move    #$40,n6
        move    (r6)+n6
        move    x:(r7+$22),a
        move    a1,n2                   ; the rotation count
        move    #$0,r4                  ; the input peak
        do      n7,>fs_cz
; ---- the ring's ramps: r2 walks it once (m2 = 3) --------------------------
        move    x:(r7+$39),x0
        move    x:(r2),a
        add     x0,a
        move    a,x:(r2)+               ; gn/16
        move    (r2)+                   ; hpBase
        move    x:(r7+$3a),x0
        move    x:(r2),a
        add     x0,a
        move    a,x:(r2)+               ; lpBase
        move    x:(r7+$3b),x0
        move    x:(r2),a
        add     x0,a
        move    a,x:(r2)+               ; trim/2, and r2 is back on gn/16
; ---- input peak for the envelope follower (mono, pre-filter) --------------
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        abs     a
        move    r4,b
        max     a,b
        move    b1,r4
; the rotation: count = (count + 1) mod 6 picks which two of the five moving
; pole pairs join pole A this sample (B or C, then D, E or F); o1 -> n4,
; o2 -> n6 from the table.
        move    n2,a
        add     #$1,a                   ; (6-bit immediate)
        cmp     #$6,a                   ; (6-bit immediate)
        move    #$0,x1
        tge     x1,a
        move    a1,n6                   ; n6 first: one move between it and the read
        move    a1,n2
        move    x:(r6+n6),a             ; o2 = 3, 4 or 5
        move    a1,n6
        move    n2,a
        and     #$1,a                   ; (6-bit immediate)
        add     #$1,a                   ; o1 = 1 or 2 (6-bit immediate)
        move    a1,n4
; ===================== channel L =====================
        move    x:(r0),a
        move    r7,r3                   ; L states: hp A..F at $00, lp A..F at $06
        bsr     fs_ccore
        move    a,x:(r0)                ; out (limited)
; ===================== channel R =====================
        move    x:(r0+n0),a
        lua     (r7+$c),r3              ; R states at $0c / $12 (fs_ccore writes n3 before it reads it)
        bsr     fs_ccore
        move    a,x:(r0+n0)
; WIDTH
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        sub     x0,a        a,x1        ; mid
        move    a,x0                    ; side
        move    x:(r7+$2c),y1           ; side gain / 2
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,y0
        move    x1,a
        add     y0,a
        move    a,x:(r0)+
        move    x1,a
        sub     y0,a
        move    a,x:(r0)+
fs_cz:
        nop
        move    n2,a
        move    a,x:(r7+$22)            ; the rotation count for the next block
        move    r4,a
        move    a,x:(r7+$1e)            ; the block's peak
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        bra     fs_end
fs_done:
        move    r5,a
        move    a,x:(r7+$1e)            ; the block's peak (SVF)
fs_end:
        nop
        rts

; ---------------------------------------------------------------------------
; fs_rbase -- r3 and n3 -> the ramps' steps at $76 (per block; the loops
; walk them from n3 once per sample). Clobbers x0 and r3's modifier.
; ---------------------------------------------------------------------------
fs_rbase:
        move    r7,r3
        move    #$76,n3
        move    (r3)+n3
        move    #>$ffffff,m3
        move    r3,n3
        rts

; ---------------------------------------------------------------------------
; fs_r3 -- the loop's step for three ramped stream words: each += its step.
; In: r1 -> the words, r3 -> their steps. Out: r1 and r3 three on.
; Straight-line (cycle_count.py's rule for a loop callee); clobbers a, x0.
; ---------------------------------------------------------------------------
fs_r3:
        move    x:(r3)+,x0
        move    x:(r1),a
        add     x0,a    x:(r3)+,x0
        move    a,x:(r1)+
        move    x:(r1),a
        add     x0,a    x:(r3)+,x0
        move    a,x:(r1)+
        move    x:(r1),a
        add     x0,a
        move    a,x:(r1)+
        rts

; ---------------------------------------------------------------------------
; fs_rset -- one ramped stream word, per block (26 Sep 2026). The word is a
; RUN value the loop steps once per sample; its step is 1/128 of the way
; from where the last block ended to this block's target, so a 15-sample
; block covers 15/128 of the way and the next block carries on from it (the
; cutoff ramp's form, g2run/dg): linear inside a block, a glide across them. A step that rounds to 0 puts the word on
; the target. The first block of a mode ($2b = 0) starts the word AT the
; target, so a knob at rest renders exactly as the rebuilt stream did.
; In: y1 = the target, r1 -> the word, r3 -> its step. Out: r1, r3 each one
; on. Clobbers a, b, x0, x1.
; ---------------------------------------------------------------------------
fs_rset:
        move    x:(r7+$2b),b
        tst     b
        move    x:(r1),b                ; the run value (moves keep the flags)
        teq     y1,b                    ; a new mode: at the target
        move    b,x0
        move    y1,a
        sub     x0,a
        asr     #$7,a,a                 ; the step per sample
        move    a,x1                    ; a0 holds the shifted-out bits: a
        move    x1,a                    ; clean reload, so Z reads a1 alone
        tst     a
        teq     y1,b                    ; a step of 0: at the target
        move    a,x:(r3)+
        move    b,x:(r1)+
        rts

; ---------------------------------------------------------------------------
; fs_qs -- s(x) = x (A - B x^2), a quarter sine (sin(pi x/2) within 0.006,
; s(x)^2 + s(1 - x)^2 within 0.05 dB of 1 on 0..1), odd; A - B = 1.00001, so
; s(1) lands past 1 and a store limits it onto 1. The SHPE crossfade's law.
; In: x0 = x. Out: a = s(x), unlimited. Clobbers x0, y0, y1 (x1 is kept).
; ---------------------------------------------------------------------------
fs_qs:
        move    x0,y1
        mpy     x0,y1,a                 ; x^2
        move    a,x0
        move    #>$22c3a0,y0            ; B/2 = 0.271595
        mpy     y0,x0,a                 ; B/2 x^2 (y0,x0: the signed order)
        neg     a
        add     #>$62c3ca,a             ; A/2 = 0.7716
        move    a,x0
        mpy     x0,y1,a                 ; s/2 (x0,y1: x may be negative)
        asl     #$1,a,a
        rts

; ---------------------------------------------------------------------------
; fs_gramp -- the cutoff ramp's end value for a block that does not run the
; SVF: g2run += n7 * dg, the same additions the SVF loop makes per sample,
; so a MODE change into SEM/BP starts its ramp from where the loop would
; have left it.
; ---------------------------------------------------------------------------
fs_gramp:
        move    x:(r7+$2e),a
        move    x:(r7+$2f),x0
        move    n7,b
        move    b,y0
        do      y0,>fs_gz
        add     x0,a
fs_gz:
        nop
        move    a,x:(r7+$2e)
        rts

; ---------------------------------------------------------------------------
; fs_ccore -- Capacitor2 for one channel (Airwindows, MIT).
; In: a = x, r3 -> the channel's twelve states (hp A..F at +0..5, lp A..F at
; +6..11), n4 = o1 (1/2), n6 = o2 (3/4/5) this sample, r1 -> the amounts
; ring (m1 = 3), r2 -> the constants ring (m2 = 3: gn/16 hpBase lpBase
; trim/2; one turn per call).
; Out: a = x through pole A, the o1 pair and the o2 pair, times trim.
; scale/2 = |1/2 - x/(2 nl)|; amt/2 = base * scale/2; each pole is
; s' = x amt/2 + x amt/2 + s (1 - amt) (exact in the accumulator, any
; order), a highpass takes x - s', a lowpass takes s'. STRAIGHT-LINE.
; r5 = r3 + 6 is the lowpass states (n3 = n5 = the pair's offset), x1 the
; running x. Clobbers x0, x1, y0, y1, b, r1, r2, r5, n3, n5.
; ---------------------------------------------------------------------------
fs_ccore:
        move    r3,r5
        move    #$6,n5
        move    a,x1                    ; x (the dry drives the dielectric)
        move    a,x0
        move    x:(r2)+,y1              ; gn/16
        move    (r5)+n5                 ; -> the lowpass states (n5 loaded three back: no wait)
        mpy     x0,y1,a                 ; g x / (16 nl)
        asl     #$3,a,a                 ; g x / (2 nl)
        neg     a
        add     #>$400000,a             ; 1/2 - g x/(2 nl)
        abs     a
        move    a,x0                    ; scale/2, 0 .. 1 (clipped: the plugin's own bound)
        move    x:(r2)+,y1              ; hpBase
        mpy     x0,y1,a
        move    a,x:(r1)+               ; ring 0: hpAmt/2
        asl     #$1,a,a
        neg     a
        add     #>$7fffff,a
        move    a,x:(r1)+               ; ring 1: 1 - hpAmt
        move    x:(r2)+,y1              ; lpBase
        mpy     x0,y1,a
        move    a,x:(r1)+               ; ring 2: lpAmt/2
        asl     #$1,a,a
        neg     a
        add     #>$7fffff,a
        move    a,x:(r1)+               ; ring 3: 1 - lpAmt (-1 .. 1); r1 round to ring 0
; pole A (offset 0 / 6)
        move    x1,x0                   ; x
        move    x:(r1)+,y1              ; hpAmt/2
        mpy     x0,y1,a
        mac     x0,y1,a  x:(r3),x0      ; x0 = hp state
        move    x:(r1)+,y1              ; 1 - hpAmt
        mac     x0,y1,a                 ; s'
        move    a,x:(r3)
        move    x1,b
        sub     a,b                     ; x - s'
        move    b,x1
        move    x:(r1)+,x0  b,y1        ; lpAmt/2 ; x (mpy x0,y1: the signed order)
        mpy     x0,y1,a
        mac     x0,y1,a  x:(r5),x0      ; x0 = lp state
        move    x:(r1)+,y1              ; 1 - lpAmt
        mac     x0,y1,a
        move    a,x:(r5)
        move    a,x1                    ; x = s'
; the o1 pair (B or C)
        move    n4,n3
        move    n4,n5
        move    x:(r1)+,x0  a,y1        ; hpAmt/2 ; x (= s', still in a)
        mpy     x0,y1,a
        mac     x0,y1,a
        move    x:(r3+n3),x0            ; hp state
        move    x:(r1)+,y1              ; 1 - hpAmt
        mac     x0,y1,a
        move    a,x:(r3+n3)
        move    x1,b
        sub     a,b
        move    b,x1
        move    x:(r1)+,x0  b,y1        ; lpAmt/2 ; x
        mpy     x0,y1,a
        mac     x0,y1,a
        move    x:(r5+n5),x0            ; lp state
        move    x:(r1)+,y1              ; 1 - lpAmt
        mac     x0,y1,a
        move    a,x:(r5+n5)
        move    a,x1
; the o2 pair (D, E or F)
        move    n6,n3
        move    n6,n5
        move    x:(r1)+,x0  a,y1        ; hpAmt/2 ; x
        mpy     x0,y1,a
        mac     x0,y1,a
        move    x:(r3+n3),x0
        move    x:(r1)+,y1
        mac     x0,y1,a
        move    a,x:(r3+n3)
        move    x1,b
        sub     a,b
        move    b,x1
        move    x:(r1)+,x0  b,y1        ; lpAmt/2 ; x
        mpy     x0,y1,a
        mac     x0,y1,a
        move    x:(r5+n5),x0
        move    x:(r1)+,y1
        mac     x0,y1,a
        move    a,x:(r5+n5)
        move    a,x0                    ; x = s'
        move    x:(r2)+,y1              ; trim/2
        mpy     x0,y1,a
        asl     #$1,a,a                 ; out = x trim
        rts

; ---- fs_lcore: the ladder's per-channel core (LADR) ----------
; In: b = x, r1 -> this channel's stream after dG (G^3(1-G) G^2(1-G) G(1-G)
; 1-G k/4 d/2, then M/4 for the caller), r2 -> G' (the stream's slot 0),
; r3 -> the channel's four halved states. Out: wetA = y4 in a, r3 on the
; next channel's states. Straight-line, no control transfer (cycle_count.py's
; rule for a loop callee); clobbers x0 x1 y0 y1 a b r1 r3 r5.
fs_lcore:
; S/8 = (1-G)(G^3 s0 + G^2 s1 + G s2 + s3)/8 with the states at s/2: sum/4
        move    r3,r5                   ; the stages write through r5
        move    x:(r3)+,x0              ; s0/2
        move    x:(r1)+,y1              ; G^3(1-G)
        mpy     x0,y1,a  x:(r3)+,x0     ; x0 = s1/2
        move    x:(r1)+,y1              ; G^2(1-G)
        mac     x0,y1,a  x:(r3)+,x0     ; x0 = s2/2
        move    x:(r1)+,y1              ; G(1-G)
        mac     x0,y1,a  x:(r3)+,x0     ; x0 = s3/2; r3 -> the next channel
        move    x:(r1)+,y1              ; 1-G
        mac     x0,y1,a                 ; S/2
        asr     #$2,a,a                 ; S/8, <= 0.6
        move    a,x0
; u = (x - k S) d: k S = 32 (k/4)(S/8); the accumulator holds the sum
        move    x:(r1)+,y1              ; k/4
        mpy     x0,y1,a                 ; (k/4)(S/8)
        asl     #$5,a,a                 ; k S
        sub     a,b                     ; x - k S (b = x from the caller)
        asr     #$5,b,b                 ; /32, <= 0.6
        move    b,x0
        move    x:(r1)+,y1              ; d/2
        mpy     x0,y1,a                 ; (x - k S) d / 64
        asl     #$5,a,a                 ; u/2
        move    a,x1                    ; v/2 (limited: u within +-2)
        move    x:(r2),y1               ; G' for the four stages
; stage 0: y/2 = G'(v-s)/2 + s/2 ; s'/2 = y - s/2  (x1 = v/2 in, y/2 out)
        tfr     x1,a  x:(r5),y0         ; v/2 ; s/2
        sub     y0,a                    ; (v - s)/2
        asr     #$1,a,a                 ; (v - s)/4
        move    a,x0
        mpy     x0,y1,a                 ; G'(v - s)/4
        asl     #$1,a,a                 ; G'(v - s)/2
        add     y0,a                    ; y/2
        asl     a  a,x1                 ; y; x1 = the next stage's v/2 (limited)
        sub     y0,a                    ; s'/2 = y - s/2
        move    a,x:(r5)+               ; limited: s' within +-2
; stage 1
        tfr     x1,a  x:(r5),y0
        sub     y0,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     y0,a
        asl     a  a,x1
        sub     y0,a
        move    a,x:(r5)+
; stage 2
        tfr     x1,a  x:(r5),y0
        sub     y0,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     y0,a
        asl     a  a,x1
        sub     y0,a
        move    a,x:(r5)+
; stage 3
        tfr     x1,a  x:(r5),y0
        sub     y0,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     y0,a
        asl     a  a,x1
        sub     y0,a
        move    a,x:(r5)+
; wetA = y4 = 2 * (y/2), in a for the caller's limiting store
        move    x1,a
        asl     #$1,a,a
        rts
