; ---------------------------------------------------------------------------
; CHARACTER STATION -- crush, fold, ring, saturate, compress, width, sends.
;
; Insert contract (modules/ripple/ripple_svf.asm): frames in place at
; x:(r0)/x:(r0+n0), knobs from r6, state in this instance's r7 block. PLUS
; the bus-client contract from modules/send/send_client.asm, exactly as
; modules/filterstation/ carries it: the PROCESSED mono goes into both
; accumulators, registration is gated on each send knob, and the station
; NEVER HOUSEKEEPS (an FX1 instance runs before its track's FX2 one, so an
; electing station would double-flip the rotation -- see filterstation's
; header for the full argument).
;
; ---- the chain, fixed order ----------------------------------------------
;   held  = SRR ? (hold each sample 2/4/8) : x          SRR
;   q     = quantise(held, bits)                        CRSH
;   f     = fold(q * (1 + 7*FOLD/128))                  FOLD
;   r     = f * carrier                                 RING (0 = skip)
;   s     = saturate(r * (1 + 3*DRV/128))               DRV, SAT
;   c     = s * gain(env)                                COMP, CMOD
;   w     = width(c)                                     WDTH
;   out   = x + MIX*(w - x)                              MIX
; Distortion BEFORE dynamics: a compressor after the dirt is a tool, before
; it is a fader for the dirt.
;
; ---- the compressor ------------------------------------------------------
; A feedforward peak detector on the mono sum, one-pole attack and release,
; then a gain curve applied to both channels -- so it cannot pump the image.
;   env  = max(|key| , env*rel) with attack smoothing on the way up
;   over  = env - thr, positive part only            (thr per CMOD)
;   gr/2  = 0.5 - over*slope*COMP/2                  (linear-in-amplitude,
;                                                     which IS a soft knee in
;                                                     dB and needs no log)
;   TRNS  = fast - slow followers: gr rides ABOVE 1 on transients, so the
;           knob adds attack. Its gr is 1 + (fast-slow)*COMP, and BOTH
;           gains are stored HALVED: a y1 operand is a fraction, so a gain
;           above 1 would wrap. Doubled back in the accumulator's guard bits.
; ⚠️ THE DETECTOR READS x:(r7+$32), the KEY. Today the station writes its own
; input there; the ->KEY bus send on the backlog writes another track's, and
; nothing else changes.
;
; ---- r7 slots -------------------------------------------------------------
;   $14 $65..$69   bus bookkeeping, SEND's layout ($69 = this block's offset)
;   per block:
;   $20 m (MIX)   $21 fold gain/8   $22 drive gain/4   $23 crush mask
;   $24 carrier step  $25 srr mask  $26 comp amount    $27 thr
;   $28 slope     $29 sat mode      $2a cmod           $2b width side gain
;   $2c width mid gain  $2d attack coeff   $2e release coeff  $2f bypass
;   $30 ->DEL level     $31 ->VRB level
;   $3e RVRB return level  $3f DLY return level   (BUS mode only, else 0)
;   per sample / persistent (ALL BELOW $40 -- an r7 displacement past 63
;   assembles to the two-word long form, which cost the filter station 30
;   words before it was found):
;   $19 held L (PERSISTENT)      $1a held R (PERSISTENT)
;   $1b srr counter (PERSISTENT) $1c carrier phase (PERSISTENT)
;   $1d env fast (PERSISTENT)    $1e env slow (PERSISTENT, TRNS only)
;   $1f gr this sample           $32 key    $33 dry L park   $34 dry R park
;   $35 scratch (wet L)          $36 scratch (wet R)
;   r4 / r5: the REVERB / DELAY wet read pointers (BUS mode), linear, per
;   block from the rotation -- two buffers back, like every bus read.
;
; ---- BUS mode: the returns (3 Sep 2026) -----------------------------------
; With SAT = BUS the station is the master's glue chain, and on a master
; chain CRSH and RING are knobs nobody turns -- so BUS repurposes them as
; the RVRB and DLY RETURN levels (the panel prints those names: ModeView in
; the manifest). Each sample, AFTER the send taps, the two shared wet buffers
; (stereo, four deep, docs/BUS.md "The returns") are read two buffers back
; and added at those levels; and each block the station STAMPS the bus's
; liveness word (y:$9d8 / y:$9d9) while a return level is up, which is what
; tells that engine to stop printing its wet on its own host. Added after
; the taps, never before: a return inside the tap would feed the wet back
; into the bus and the reverb would run away.
;
; CYCLES_FORWARD_BRANCHES -- the SRR hold and the RING gate are the only
; branches left in the sample loop, both forward and both skipping work, so
; the word span is the worst-case cycle count (tools/cycle_count.py). The
; saturation character and the compressor mode are per-block COEFFICIENTS
; for exactly this reason: a dispatch inside the loop cannot be priced.
;
; Every mpy is `mpy x0,y1` (the audited-signed encoding) except the send
; taps, which are SEND's `mpy x1,y1` / `mpy x1,y0` with a non-negative level
; second. Every Tcc reads the ONE compare above it with nothing but moves
; between (the flag-clobber trap).
; ---------------------------------------------------------------------------

init:
; ROTINIT
        rts

proc:
; ===========================================================================
; BUS: split-aware frame offset, verbatim from modules/send/send_client.asm
; ===========================================================================
        move    a,x:(r7+$14)
        clr     a
        move    a,x:(r7+$67)
        move    x:(r7+$14),a
        tst     a
        bne     ch_a1
        move    #>$1,a
        move    a,x:(r7+$65)
        move    n7,a
        and     #>$f,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$66)
        bra     ch_offok
ch_a1:
        move    x:(r7+$65),a
        and     #>$ff,a
        move    a1,x0
        move    x0,a
        move    #>$1,x0
        cmp     x0,a
        bne     ch_offok
        clr     a
        move    a,x:(r7+$65)
        move    x:(r7+$66),a
        and     #>$f,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$67)
ch_offok:
; ---- resolve this block's write offset (per payload) -> r7+$69, r1, r2 ---
; ROTLATCH
        move    a,x0
        move    #>$901,a
        add     x0,a
        move    x:(r7+$67),b
        add     b,a
        move    a,r1                    ; REVERB ACC[write] + frame offset
        move    #>$961,a
        add     x0,a
        add     b,a
        move    a,r2                    ; DELAY  ACC[write] + frame offset
        move    #>$ffffff,m1
        move    #>$ffffff,m2
; ---- register, once per block, per bus, ONLY IF SENDING (r6+4 / r6+5) ----
        move    x:(r7+$67),a
        tst     a
        bne     ch_cntz
        move    x:(r7+$69),a
        asr     #$4,a,a
        move    a1,x0
        move    x0,a
        move    #>$9c3,x0
        add     x0,a
        move    a,r3
        move    #>$ffffff,m3
        move    #>$1,x0
        clr     b
        move    x:(r6+$5),a             ; ->VRB level
        tst     a
        tne     x0,b
        move    y:(r3),a
        add     b,a
        move    a,y:(r3)
        move    #4,n3
        move    (r3)+n3
        clr     b
        move    x:(r6+$4),a             ; ->DEL level
        tst     a
        tne     x0,b
        move    y:(r3),a
        add     b,a
        move    a,y:(r3)
ch_cntz:
        move    x:(r6+$4),x0
        move    x0,x:(r7+$30)           ; ->DEL
        move    x:(r6+$5),x0
        move    x0,x:(r7+$31)           ; ->VRB

; ===========================================================================
; PER-BLOCK KNOB DECODE
; ===========================================================================
; MIX: page-2 slot 6, the KNOB field of r6+$c (the word SAT's select shares)
        move    x:(r6+$c),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$20)            ; m
; fold gain/8 = (1 + 7*FOLD/128)/8 = 1/8 + FOLD*(7/1024)   -- WarpFold's law,
; pre-divided by 8 so the fold's (v+1)/2 arithmetic keeps its guard bits.
        move    x:(r6+$1),x0            ; the knob word IS FOLD/128 in Q23
        move    #>$700000,y1            ; 7/8
        mpy     x0,y1,a                 ; (7/8)*(FOLD/128)
        add     #>$100000,a             ; + 1/8 -> gain/8, 0.125 .. 0.992
        move    a,x:(r7+$21)            ; gq
; drive gain/4 = (1 + 3*DRV/128)/4 = 1/4 + DRV*(3/512)
        move    x:(r6+$0),x0            ; the knob word IS DRV/128 in Q23
        move    #>$600000,y1            ; 3/4
        mpy     x0,y1,a                 ; (3/4)*(DRV/128)
        add     #>$200000,a             ; + 1/4 -> gain/4, 0.25 .. 0.992
        move    a,x:(r7+$22)            ; gd
; CRSH -> a bit MASK, built ONCE PER BLOCK (the per-sample cost is then one
; AND). The knob picks how many low bits are cleared, 0..21; the mask is
; $ffffff shifted left that many times, and the shift runs in a `do` loop
; here rather than a `rep` per sample.
; bits = 21 * knob / 128. The knob word IS knob/128 in Q23, so the product
; with 21/128 is 21*knob/2^14 as a fraction; one asr #16 of the accumulator
; leaves the plain integer.
        move    x:(r6+$2),x0
        move    #>$150000,y1            ; 21/128
        mpy     x0,y1,a
        asr     #$10,a,a                ; -> the integer, 0..20
        move    a1,x0
        move    x0,a
        move    #>21,x0
        cmp     x0,a
        tgt     x0,a                    ; belt and braces: never past 21
        move    a,y0                    ; bits to drop, 0..21 -- the do count
        tst     a                       ; (tst takes an ACCUMULATOR, never a
        move    #>$ffffff,a             ; register; a move does not disturb it)
        beq     ch_mskz                 ; knob 0: the all-ones mask, unshifted
        do      y0,>ch_mskl
        asl     #$1,a,a
        move    a1,x0                   ; asl leaves A2 stale every trip
        move    x0,a
ch_mskl:
        nop
ch_mskz:
        move    a,x:(r7+$23)            ; the mask: AND clears the low bits
; RING: carrier step, WarpFold's squared taper; 0 = OFF (a step of 0 leaves
; the phase still, and the per-sample gate below skips the multiply)
        move    x:(r6+$d),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a                 ; RING^2
        move    a,x0
        move    #>$5a0000,y1            ; ~2.95 kHz at full knob
        mpy     x0,y1,a
        move    a,x:(r7+$24)            ; carrier step
; SRR (slot 11 select of r6+$e): hold mask 0 / 1 / 3 / 7
        move    x:(r6+$e),a
        and     #>$ff00,a
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        move    #>$10000,x0
        cmp     x0,a
        beq     ch_srr2
        move    #>$20000,x0
        cmp     x0,a
        beq     ch_srr4
        move    #>$30000,x0
        cmp     x0,a
        beq     ch_srr8
        clr     a                       ; OFF, and anything unexpected
        bra     ch_srrz
ch_srr2:
        move    #>$1,a
        bra     ch_srrz
ch_srr4:
        move    #>$3,a
        bra     ch_srrz
ch_srr8:
        move    #>$7,a
ch_srrz:
        move    a,x:(r7+$25)            ; srr mask
; COMP amount, straight from the knob
        move    x:(r6+$3),x0
        move    x0,x:(r7+$26)
; CMOD (slot 9 select of r6+$d): threshold, slope, attack and release
        move    x:(r6+$d),a
        and     #>$ff00,a
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        move    #>$10000,x0
        cmp     x0,a
        beq     ch_cglue
        move    #>$20000,x0
        cmp     x0,a
        beq     chcmtr
        clr     a                       ; COMP: fast 4:1
        move    a,x:(r7+$2a)            ; trns flag = 0
        move    #>$199999,x0            ; thr 0.2
        move    x0,x:(r7+$27)
        move    #>$600000,x0            ; slope 0.75 (4:1-ish in amplitude)
        move    x0,x:(r7+$28)
        move    #>$100000,x0            ; attack ~0.5 ms
        move    x0,x:(r7+$2d)
        move    #>$008000,x0            ; release ~90 ms
        move    x0,x:(r7+$2e)
        bra     ch_cdone
ch_cglue:
        clr     a                       ; GLUE: slow, soft, 2:1
        move    a,x:(r7+$2a)            ; trns flag = 0
        move    #>$0ccccd,x0            ; thr 0.1 -- it works earlier
        move    x0,x:(r7+$27)
        move    #>$400000,x0            ; slope 0.5
        move    x0,x:(r7+$28)
        move    #>$020000,x0            ; attack ~8 ms: lets transients through
        move    x0,x:(r7+$2d)
        move    #>$002000,x0            ; release ~350 ms
        move    x0,x:(r7+$2e)
        bra     ch_cdone
chcmtr:
        move    #>$7fffff,a             ; TRNS: the two-follower difference
        move    a,x:(r7+$2a)            ; trns flag = 1
        move    a,x:(r7+$27)            ; threshold 1.0: the compressor half of
                                        ; the expression below can never fire,
                                        ; which is what makes it branchless
        clr     a
        move    a,x:(r7+$28)            ; slope 0
        move    #>$200000,x0            ; fast follower
        move    x0,x:(r7+$2d)
        move    #>$004000,x0            ; slow follower
        move    x0,x:(r7+$2e)
ch_cdone:
; SAT character (slot 7 select of r6+$c) -> FOUR COEFFICIENTS, so the sample
; loop has no branch in it at all: neg (what the negative half is scaled by
; before the curve -- TUBE's asymmetry), pre and post around the curve (BUS
; drives it half and doubles back, the gentlest knee) and a symmetric clip
; (FUZZ's hard half; 1.0 elsewhere never bites, since |sat(w)| <= 2/3).
; neg / pre / post are stored HALVED and doubled back in the accumulator's
; guard bits, the same discipline as the width and compressor gains: a y1
; operand is a fraction and post reaches 2.0.
        move    #>$400000,x0            ; the defaults: neg 1, pre 1, post 1
        move    x0,x:(r7+$37)
        move    x0,x:(r7+$38)
        move    x0,x:(r7+$39)
        move    #>$7fffff,x0            ; clip 1.0 -- never bites
        move    x0,x:(r7+$3a)
        move    #>$800000,x0            ; -1.0
        move    x0,x:(r7+$3b)
        clr     a
        move    a,x:(r7+$3e)            ; return levels: 0 outside BUS mode
        move    a,x:(r7+$3f)
        move    x:(r6+$c),a
        and     #>$ff00,a
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        move    #>$10000,x0
        cmp     x0,a
        beq     ch_stube
        move    #>$20000,x0
        cmp     x0,a
        beq     ch_sfuzz
        move    #>$30000,x0
        cmp     x0,a
        beq     ch_sbus
        bra     ch_sdone                ; TAPE: the curve alone
ch_stube:
        move    #>$300000,x0            ; neg = 0.75: the positive half is
        move    x0,x:(r7+$37)           ; driven harder, so even harmonics
        bra     ch_sdone
ch_sfuzz:
        move    #>$266666,x0            ; clip +0.6
        move    x0,x:(r7+$3a)
        move    #>$d9999a,x0            ; clip -0.6
        move    x0,x:(r7+$3b)
        bra     ch_sdone
ch_sbus:
        move    #>$200000,x0            ; pre = 0.5 ...
        move    x0,x:(r7+$38)
        move    #>$7fffff,x0            ; ... post = 2.0
        move    x0,x:(r7+$39)
; BUS: CRSH and RING are the RETURN levels. The crush mask goes all-ones and
; the carrier step 0, so the stages those knobs used to drive are neutral.
        move    #>$ffffff,x0
        move    x0,x:(r7+$23)           ; crush: identity
        clr     a
        move    a,x:(r7+$24)            ; ring: no carrier
        move    x:(r6+$2),x0
        move    x0,x:(r7+$3e)           ; RVRB return level (the CRSH knob)
        move    x:(r6+$d),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,x:(r7+$3f)           ; DLY return level (the RING knob)
ch_sdone:
; WDTH -> mid and side gains. 64 = (1, 1); 0 = (1, 0) mono; 127 = (1, ~2).
; side gain = WDTH/64, mid stays 1 -- widening only touches the difference,
; so a mono source is untouched at every setting.
        move    x:(r6+$e),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
; ⚠️ STORED HALVED. A y1 operand is a FRACTION, and a side gain of WDTH/64
; tops out near 2.0, which would wrap the word. The knob's own value IS
; WDTH/128, so it is stored as-is and the product is doubled back in the
; accumulator's guard bits. 64 -> 0.5 -> x2 = exactly 1.0, i.e. untouched.
        move    a,x:(r7+$2b)            ; side gain / 2
; ---- the return read pointers, and the liveness stamps -------------------
; Two buffers back, like every bus read (an idle block each side of the
; reader on both cores); x2 throughout because the wet buffers are stereo,
; 32 words each. The delay's page is the reverb's + $80 (spelled as base +
; offset, so the XBUS relocation of `$9xx` literals catches the base).
        move    x:(r7+$69),a            ; this block's write offset
        add     #>$20,a
        and     #>$30,a                 ; two back, mod 4
        move    a1,x0
        move    x0,a                    ; A2-clean after the and
        add     x0,a                    ; x2
        move    x:(r7+$67),b            ; split-aware frame offset
        add     b,a
        add     b,a                     ; + frame x2
        add     #>$9da,a
        move    a,r4                    ; REVERB wet [read]
        add     #>$80,a
        move    a,r5                    ; DELAY wet [read]
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        move    x:(r7+$3e),a            ; RVRB up: stamp the reverb's word
        tst     a
        beq     ch_nrv
        move    #>$1,x0
        move    x0,y:>$9d8
ch_nrv:
        move    x:(r7+$3f),a            ; DLY up: stamp the delay's word
        tst     a
        beq     ch_ndl
        move    #>$1,x0
        move    x0,y:>$9d9
ch_ndl:
; ---- BYPASS: the defaults are a bit-exact passthrough ---------------------
; DRV 0, FOLD 0, CRSH 0, COMP 0, MIX 127, RING 0, WDTH 64, SRR OFF. Every
; part that ever chose LO-FI runs this after the flash, so the neutral block
; copies nothing and only does the sends.
        clr     b
        move    b,x:(r7+$2f)
        move    x:(r6+$0),a             ; DRV
        tst     a
        bne     ch_live
        move    x:(r6+$1),a             ; FOLD
        tst     a
        bne     ch_live
        move    x:(r7+$23),a            ; crush MASK (not the knob: in BUS
        move    #>$ffffff,x0            ; mode the knob is RVRB and the mask
        cmp     x0,a                    ; is identity)
        bne     ch_live
        move    x:(r7+$3e),a            ; a return level up needs the loop
        move    x:(r7+$3f),b
        add     b,a
        bne     ch_live
        move    x:(r6+$3),a             ; COMP
        tst     a
        bne     ch_live
        move    x:(r7+$24),a            ; carrier step (RING)
        tst     a
        bne     ch_live
        move    x:(r7+$25),a            ; srr mask
        tst     a
        bne     ch_live
        move    x:(r7+$2b),a            ; side gain/2: 64 -> exactly 0.5
        move    #>$400000,x0
        cmp     x0,a
        bne     ch_live
        bra     ch_bypass
ch_live:

; ===========================================================================
; THE SAMPLE LOOP
; ===========================================================================
        move    #>$1,n0
        do      n7,>ch_end
; ---- park the dry, and take the key (the mono sum) ------------------------
        move    x:(r0),a
        move    a,x:(r7+$33)
        move    x:(r0+n0),x0
        move    x0,x:(r7+$34)
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$32)            ; key = mono in (the ->KEY hook)
; ---- SRR: hold the pair for 2/4/8 samples ---------------------------------
        move    x:(r7+$25),a            ; mask
        tst     a
        beq     ch_nosrr
        move    x:(r7+$1b),b            ; counter
        add     #>$1,b
        move    b1,x0
        move    x0,b
        move    b,x:(r7+$1b)
        and     x0,a                    ; counter & mask
        move    a1,x0
        move    x0,a
        tst     a
        bne     ch_hold                 ; not a fresh sample: reuse the held
        move    x:(r0),x0               ; fresh: latch this pair
        move    x0,x:(r7+$19)
        move    x:(r0+n0),x0
        move    x0,x:(r7+$1a)
ch_hold:
        move    x:(r7+$19),x0           ; the held pair drives the chain
        move    x0,x:(r7+$33)
        move    x:(r7+$1a),x0
        move    x0,x:(r7+$34)
ch_nosrr:
; ---- CRSH: one AND per channel with the per-block mask -------------------
; ⚠️ AND leaves A2 STALE and the next store would saturate (CLAUDE.md), so
; each value leaves through a1 into a clean register first.
        move    x:(r7+$23),x0           ; mask
        move    x:(r7+$33),a
        and     x0,a
        move    a1,x1
        move    x1,x:(r7+$33)
        move    x:(r7+$34),a
        and     x0,a
        move    a1,x1
        move    x1,x:(r7+$34)
; ---- FOLD: WarpFold's wrap-and-reflect, both channels --------------------
        move    x:(r7+$33),x0
        move    x:(r7+$21),y1           ; gq = gain/8
        mpy     x0,y1,a                 ; v/8
        asl     #$2,a,a                 ; v/2
        move    #>$400000,x1
        add     x1,a                    ; (v+1)/2
        move    a1,x1                   ; s = wrap(...), raw A1: the fold
        move    x1,a                    ; clean re-load, A2 consistent
        abs     a
        move    #>$400000,b
        sub     b,a                     ; |s| - 0.5
        asl     #$1,a,a                 ; fold in [-1,1)
        move    a,x:(r7+$35)            ; wet L
        move    x:(r7+$34),x0
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    #>$400000,x1
        add     x1,a
        move    a1,x1
        move    x1,a
        abs     a
        move    #>$400000,b
        sub     b,a
        asl     #$1,a,a
        move    a,x:(r7+$36)            ; wet R
; ---- RING: one carrier, both channels ------------------------------------
        move    x:(r7+$24),a            ; step
        tst     a
        beq     ch_noring
        move    x:(r7+$1c),b            ; phase
        move    a,x0
        move    b,a
        add     x0,a
        move    a1,x0                   ; p = wrapped phase
        move    x0,x:(r7+$1c)
        move    x0,a
        abs     a
        move    #>$800000,y1            ; -1.0
        add     y1,a                    ; |p| - 1
        neg     a                       ; t = 1 - |p|
        move    a,y1
        mpy     x0,y1,a                 ; p*t
        asl     #$2,a,a                 ; carrier = 4*p*t
        move    a,y0                    ; held for both channels
        move    x:(r7+$35),x0
        mpy     y0,x0,a                 ; wet * carrier (signed order)
        move    a,x:(r7+$35)
        move    x:(r7+$36),x0
        mpy     y0,x0,a
        move    a,x:(r7+$36)
ch_noring:
; ---- SATURATE: drive, the curve, the character -- BRANCHLESS ------------
; Both channels take the identical path: scale the negative half by `neg`
; (one tst + one Tcc, nothing between them), apply `pre`, run the cubic,
; apply `post`, clamp to +-clip. The character lives in those four per-block
; words, so `make cycles` can price this loop -- a branch in a sample loop
; makes words != cycles and the counter refuses the module outright.
        move    x:(r7+$35),x0           ; L, post-fold/ring ($33 is the PRE-fold
                                        ; park -- reading it here threw the fold
                                        ; and the ring away, 3 Sep 2026)
        move    x:(r7+$22),y1           ; gd = gain/4
        mpy     x0,y1,a
        asl     #$2,a,a                 ; driven
        move    a,x:(r7+$35)            ; LIMITING store: the clip IS the drive
        move    x:(r7+$35),x0
        move    x:(r7+$37),y1           ; neg / 2
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,x1                    ; the softened form
        move    x:(r7+$35),a
        tst     a                       ; sign of w -- nothing between this
        tmi     x1,a                    ; and the Tcc (the flag trap)
        move    a,x0
        move    x:(r7+$38),y1           ; pre / 2
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,x:(r7+$35)
        bsr     chsatur
        move    a,x0
        move    x:(r7+$39),y1           ; post / 2
        mpy     x0,y1,a
        asl     #$1,a,a
        move    x:(r7+$3a),x0           ; +clip
        cmp     x0,a
        tgt     x0,a
        move    x:(r7+$3b),x0           ; -clip
        cmp     x0,a
        tlt     x0,a
        move    a,x:(r7+$35)            ; saturated L
        move    x:(r7+$36),x0           ; R, the identical path
        move    x:(r7+$22),y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x:(r7+$36)
        move    x:(r7+$36),x0
        move    x:(r7+$37),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,x1
        move    x:(r7+$36),a
        tst     a
        tmi     x1,a
        move    a,x0
        move    x:(r7+$38),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        move    x:(r7+$35),x1           ; park L across chsatur's use of $35
        move    a,x:(r7+$35)
        bsr     chsatur
        move    a,x0
        move    x:(r7+$39),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        move    x:(r7+$3a),x0
        cmp     x0,a
        tgt     x0,a
        move    x:(r7+$3b),x0
        cmp     x0,a
        tlt     x0,a
        move    a,x:(r7+$36)            ; saturated R
        move    x1,x:(r7+$35)           ; L back from its park
; ---- COMPRESS: one detector, one gain, both channels ---------------------
; env_fast: attack toward |key|, release by the coefficient.
        move    x:(r7+$32),a            ; key
        abs     a
        move    a,x1                    ; |key|
        move    x:(r7+$1d),x0           ; env fast
        move    x:(r7+$2e),y1           ; release
        mpy     x0,y1,a                 ; decayed
        cmp     x1,a                    ; nothing between this and the Tcc
        tlt     x1,a                    ; env = max(|key|, decayed)
        move    a,x:(r7+$1d)
; gr/2 = 0.5 - (compress - boost)/2, where ONE of the two terms is always
; zero by construction: the compressor half needs env above the threshold,
; and TRNS sets that threshold to 1.0; the boost half is multiplied by the
; trns flag, which is 0 in the other two modes. No branch, so the loop stays
; priceable.
        move    x:(r7+$27),x0           ; thr
        sub     x0,a                    ; env - thr
        move    #>$0,x0
        tmi     x0,a                    ; below it: nothing
        move    a,x0
        move    x:(r7+$28),y1           ; slope
        mpy     x0,y1,a                 ; the compression term
        move    a,x1
; the slow follower, and the boost term (fast - slow) * trns flag
        move    x:(r7+$1d),a            ; fast env
        move    x:(r7+$1e),b            ; slow env
        sub     b,a                     ; fast - slow, either sign
        asr     #$1,a,a
        move    a,x0
        move    #>$004000,y1            ; k ~ 1/512: ~12 ms, slow enough that
                                        ; a transient is 12 ms of headroom
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a                     ; slow'
        move    a,x:(r7+$1e)
        move    x:(r7+$1d),a
        move    x:(r7+$1e),x0
        sub     x0,a                    ; fast - slow, >= 0 while it lags
        move    #>$0,x0
        tmi     x0,a                    ; never negative
        move    a,x0
        move    x:(r7+$2a),y1           ; trns flag: 1 in TRNS, 0 elsewhere
        mpy     x0,y1,a                 ; the boost term
        move    a,x0
        move    x1,a                    ; compression - boost
        sub     x0,a
        move    a,x0
        move    x:(r7+$26),y1           ; COMP amount
        mpy     x0,y1,a
        asr     #$1,a,a                 ; halved: gr is a y1 fraction and TRNS
        neg     a                       ; drives it above 1
        add     #>$400000,a             ; gr/2
        move    #>$0,x0
        tmi     x0,a                    ; never invert
ch_grz:
        move    a,x:(r7+$1f)            ; gr / 2
        move    x:(r7+$35),x0
        move    x:(r7+$1f),y1           ; gr / 2
        mpy     x0,y1,a
        asl     #$1,a,a                 ; ... doubled back in the guard bits
        move    a,x:(r7+$35)
        move    x:(r7+$36),x0
        move    x:(r7+$1f),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,x:(r7+$36)
; ---- WIDTH: mid stays, side scales ---------------------------------------
        move    x:(r7+$35),a            ; L
        move    x:(r7+$36),x0           ; R
        add     x0,a
        asr     #$1,a,a
        move    a,x1                    ; mid
        move    x:(r7+$35),a
        sub     x0,a
        asr     #$1,a,a
        move    a,x0                    ; side
        move    x:(r7+$2b),y1           ; side gain / 2
        mpy     x0,y1,a
        asl     #$1,a,a                 ; the halving undone in the guard bits
        move    a,y0                    ; scaled side
        move    x1,a
        add     y0,a                    ; mid + side
        move    a,x:(r7+$35)
        move    x1,a
        sub     y0,a                    ; mid - side
        move    a,x:(r7+$36)
; ---- MIX and write back --------------------------------------------------
        move    x:(r7+$35),a
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$20),y1           ; m
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        move    x:(r7+$36),a
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
; ---- the sends: the PROCESSED mono, 3 bits of bus headroom ---------------
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x1
        move    x:(r7+$30),y1           ; ->DEL
        mpy     x1,y1,a                 ; SEND's order: the level is >= 0
        asr     #$3,a,a
        move    y:(r2),b
        add     b,a
        move    a,y:(r2)+
        move    x:(r7+$31),y0           ; ->VRB
        mpy     x1,y0,a
        asr     #$3,a,a
        move    y:(r1),b
        add     b,a
        move    a,y:(r1)+
; ---- the returns (BUS mode): added LAST, after the send taps -------------
; Skipped per sample when both levels are 0 -- a forward skip, the class
; CYCLES_FORWARD_BRANCHES admits. The wet in x0 goes negative, so the mpy is
; the audited-signed x0,y1 order; the level is the knob word (val/128, >= 0).
        move    x:(r7+$3e),a
        move    x:(r7+$3f),b
        add     b,a
        beq     ch_noret
        move    x:(r0),a
        move    y:(r4)+,x0              ; reverb wet L
        move    x:(r7+$3e),y1           ; RVRB
        mpy     x0,y1,b
        add     b,a
        move    y:(r5)+,x0              ; delay wet L
        move    x:(r7+$3f),y1           ; DLY
        mpy     x0,y1,b
        add     b,a
        move    a,x:(r0)
        move    x:(r0+n0),a
        move    y:(r4)+,x0              ; reverb wet R
        move    x:(r7+$3e),y1
        mpy     x0,y1,b
        add     b,a
        move    y:(r5)+,x0              ; delay wet R
        move    x:(r7+$3f),y1
        mpy     x0,y1,b
        add     b,a
        move    a,x:(r0+n0)
ch_noret:
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
ch_end:
        nop
        rts

; ===========================================================================
; BYPASS LOOP: frames untouched, sends only
; ===========================================================================
ch_bypass:
        move    x:(r7+$31),y0
        move    x:(r7+$30),y1
        move    #>$1,n0
        do      n7,>ch_byz
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x1
        mpy     x1,y1,a
        asr     #$3,a,a
        move    y:(r2),b
        add     b,a
        move    a,y:(r2)+
        mpy     x1,y0,a
        asr     #$3,a,a
        move    y:(r1),b
        add     b,a
        move    a,y:(r1)+
; ---- the returns (BUS mode): added LAST, after the send taps -------------
; Skipped per sample when both levels are 0 -- a forward skip, the class
; CYCLES_FORWARD_BRANCHES admits. The wet in x0 goes negative, so the mpy is
; the audited-signed x0,y1 order; the level is the knob word (val/128, >= 0).
        move    x:(r7+$3e),a
        move    x:(r7+$3f),b
        add     b,a
        beq     ch_bynor
        move    x:(r0),a
        move    y:(r4)+,x0              ; reverb wet L
        move    x:(r7+$3e),y1           ; RVRB
        mpy     x0,y1,b
        add     b,a
        move    y:(r5)+,x0              ; delay wet L
        move    x:(r7+$3f),y1           ; DLY
        mpy     x0,y1,b
        add     b,a
        move    a,x:(r0)
        move    x:(r0+n0),a
        move    y:(r4)+,x0              ; reverb wet R
        move    x:(r7+$3e),y1
        mpy     x0,y1,b
        add     b,a
        move    y:(r5)+,x0              ; delay wet R
        move    x:(r7+$3f),y1
        mpy     x0,y1,b
        add     b,a
        move    a,x:(r0+n0)
        move    x:(r7+$30),y1           ; ->DEL level back in y1
ch_bynor:
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
ch_byz:
        nop
        rts

; ---------------------------------------------------------------------------
; chsatur -- BongDelay's loop-saturation curve, sat = w - w^3/3.
; In:  x:(r7+$35) = w (already limited by its store).  Out: a = sat.
; Unity small-signal by construction, monotonic, |out| bounded -- the same
; argument modules/bongdelay/delay_server.asm's satdrv makes, which is why
; this can sit in front of a compressor without adding gain.
; bsr, not jsr: dsp_asm implements only the relative b-forms.
; ---------------------------------------------------------------------------
chsatur:
        move    x:(r7+$35),x0           ; w
        move    x0,y1
        mpy     x0,y1,b                 ; w^2
        move    b,y1                    ; limiting move: w^2 <= 1
        mpy     x0,y1,b                 ; w^3
        move    b,x0
        move    #>$2aaaab,y1            ; 1/3
        mpy     x0,y1,b                 ; w^3/3
        move    x:(r7+$35),a            ; w
        move    b,x0
        sub     x0,a                    ; sat
        rts
