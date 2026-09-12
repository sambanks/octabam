; ---------------------------------------------------------------------------
; CHARACTER -- crush, fold, ring, saturate, compress, width, sends.
;
; Insert contract (modules/ripple/ripple_svf.asm): frames in place at
; x:(r0)/x:(r0+n0), knobs from r6, state in this instance's r7 block. PLUS
; the bus-client contract from modules/send/send_client.asm, exactly as
; modules/spectrum/ carries it: the PROCESSED mono goes into both
; accumulators, registration is gated on each send knob, and the station
; NEVER HOUSEKEEPS (an FX1 instance runs before its track's FX2 one, so an
; electing station would double-flip the rotation -- see spectrum's
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
;   $20 m (MIX)   $21 fold gain/32  $22 drive gain/16  $23 crush mask
;   $24 carrier step  $25 srr mask  $26 comp amount    $27 thr
;   $28 invR      $29 sat mode      $2a trns flag      $2b width side gain
;   $2c width mid gain  $2d attack coeff   $2e release coeff  $2f bypass
;   $30 ->DEL level     $31 ->VRB level
;   $3e RET return level   $3f 0 (was DLY; one return since 7 Sep 2026)
;   $40 FX2-slot flag (set at init: 1 = this instance is on FX2, dry; per block)
;   $41/$42 DC block x1 L/R, $43/$44 y1 L/R (PERSISTENT, zeroed at init; long-form slots)
;   $46 DC block k (1 or 0), $47 R (0.999 or 0): on in TUBE / FUZZ only (per block)
;   $49 post low-pass kl  $4a/$4b its state L/R (PERSISTENT)
;   $4c low-pass mode flag (1.0 in TAPE / TUBE, 0 in FUZZ / BUS; per block)
;   $3c/$3d reverb / delay liveness grace (BUS mode, per block)
;   per sample / persistent (ALL BELOW $40 -- an r7 displacement past 63
;   assembles to the two-word long form, which cost the Spectrum station 30
;   words before it was found):
;   $19 held L (PERSISTENT)      $1a held R (PERSISTENT)
;   $1b srr counter (PERSISTENT) $1c carrier phase (PERSISTENT)
;   $1d block max |key| (PERSISTENT across the block edge)  $1e slow follower (PERSISTENT, per block)
;   $1f gr/2 (PERSISTENT: slewed)  $45 gr/2 target (per block)
;   $32 key    $33 dry L park   $34 dry R park
;   $35 scratch (wet L)          $36 scratch (wet R)
;   r4 / r5: the REVERB / DELAY wet read pointers (BUS mode), linear, per
;   block from the rotation -- two buffers back, like every bus read.
;
; ---- BUS mode: the returns (3 Sep 2026) -----------------------------------
; With SAT = BUS the station is the master's glue chain, and on a master
; chain CRSH and RING are knobs nobody turns -- so BUS repurposes them as
; the RVRB and DLY RETURN levels (the panel prints those names: ModeView in
; the manifest). Each sample, AFTER the send taps, the two shared wet buffers
; (stereo, four deep, docs/effects/BUS.md "The returns") are read two buffers back
; and added at those levels; and each block the station STAMPS the bus's
; liveness word (y:$9d8 / y:$9d9) while a return level is up, which is what
; tells that engine to stop printing its wet on its own host. Added after
; the taps, never before: a return inside the tap would feed the wet back
; into the bus and the reverb would run away.
;
; CYCLES_FORWARD_BRANCHES -- the SRR hold and the RING gate are the only
; branches left in the sample loop, both forward and both skipping work, so
; the word span is the worst-case cycle count (tools/build/cycle_count.py). The
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
; ---- FX1 ONLY (12 Sep 2026): the allocator base decides, at init --------
; Modulation's idiom (modules/modulation/modulation.asm): X:0x213 points at
; this instance's entry in the base table, valid HERE and nowhere else. FX1
; slots are below 0x4000, FX2 slots at or above it. An FX2 instance runs as
; a dry pass -- proc returns before it touches a frame or the bus -- so a
; part that names this id on FX2 (the stock id both menus share) costs its
; core nothing: the rig's cycle envelope is priced with the stations on FX1
; only (tools/harness/pressure.py), and the FX2 chooser hides them.
; sub/tst rather than cmp: the cmp-encodes-as-max family (CLAUDE.md).
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
        move    b,x:(r7+$40)          ; 1 = dry pass
        clr     a
        move    a,x:(r7+$41)            ; the DC blocker's state, both channels
        move    a,x:(r7+$42)
        move    a,x:(r7+$43)
        move    a,x:(r7+$44)
        move    a,x:(r7+$1d)            ; the compressor: block max, slow follower
        move    a,x:(r7+$1e)
        move    #>$400000,x0
        move    x0,x:(r7+$1f)           ; gr/2 = unity
        move    x0,x:(r7+$45)
        rts

proc:
        move    x:(r7+$40),a           ; an FX2 slot: dry, nothing written
        tst     a
        bne     ch_end
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
; ---- resolve this block's rotation (per payload) -> r7+$69 -----------------
; ROTLATCH
; (the registration went with the sends, 12 Sep 2026; the rotation latch
; above stays: the returns read the engines' outputs by it)

; ===========================================================================
; PER-BLOCK KNOB DECODE
; ===========================================================================
; MIX: page-2 slot 6, the KNOB field of r6+$c (the word SAT's select shares)
        move    x:(r6+$c),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$20)            ; m
; fold gain/32 = (1 + 31*FOLD/128)/32 -- 1x .. 32x into the fold, pre-divided
; by 32 so the fold's (v+1)/2 arithmetic keeps its guard bits (the loop
; shifts by 4). WarpFold's 1x..8x law (until 12 Sep 2026) was sized for the
; old harness's 0.5 FS input; the unit hands the chain ~0.13 FS at AMP VOL
; 64 (the mixer model, COLDFIRE_PORT.md O14), where 8x reached the FIRST
; fold only at FOLD 127 -- +15 dB of gain and 12 % THD, a volume knob.
        move    x:(r6+$1),x0            ; the knob word IS FOLD/128 in Q23
        move    #>$7c0000,y1            ; 31/32
        mpy     x0,y1,a                 ; (31/32)*(FOLD/128)
        add     #>$040000,a             ; + 1/32 -> gain/32, 0.031 .. 0.992
        move    a,x:(r7+$21)            ; gq
; drive gain/16 = (1 + 15*DRV/128)/16 -- 1x .. 16x into the curve (the loop
; shifts by 4; the limiting store IS the clip). Was 1x..4x, same reason as
; the fold: at the unit's level TAPE 127 measured +11 dB and 2.4 % THD.
        move    x:(r6+$0),x0            ; the knob word IS DRV/128 in Q23
        move    #>$780000,y1            ; 15/16
        mpy     x0,y1,a                 ; (15/16)*(DRV/128)
        add     #>$080000,a             ; + 1/16 -> gain/16, 0.0625 .. 0.992
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
        move    #>$030000,x0            ; 3<<16 (zero-padded: not the base
        cmp     x0,a                    ; literal the build rewrites)
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
; The compressor (rebuilt 12 Sep 2026 -- the first one measured inert at the
; unit's level: thresholds of 0.2 / 0.1 FS against a chain that sees ~0.13
; at AMP VOL 64, a gain law linear in AMPLITUDE, a "release" coefficient of
; 0.004 that collapsed the envelope every sample and an attack that was
; never read). Now: a BLOCK-MAX detector (one cmp/Tcc a sample), a static
; curve computed once per block with a real division -- gr = (thr + over/R)
; / env above thr, 1 below -- COMP scaling the reduction and adding a
; proportional makeup, and attack / release as the GAIN's slew per sample
; (attack while it falls, release while it rises). Coefficients are
; 1 - exp(-1 / (t * fs)) in Q23. thr in FS at the chain; invR = 1/R.
        clr     a                       ; COMP: ~5:1 from -26 dBFS, 1 ms / 100 ms
        move    a,x:(r7+$2a)            ; trns flag = 0
        move    #>$066666,x0            ; thr 0.05
        move    x0,x:(r7+$27)
        move    #>$100000,x0            ; invR 0.125: the amplitude curve reads
        move    x0,x:(r7+$28)           ; ~5:1 in dB at +8 dB over
        move    #>$02deba,x0            ; attack 1 ms
        move    x0,x:(r7+$2d)
        move    #>$00076e,x0            ; release 100 ms
        move    x0,x:(r7+$2e)
        bra     ch_cdone
ch_cglue:
        clr     a                       ; GLUE: ~2.5:1 from -30 dBFS, 10 ms / 400 ms
        move    a,x:(r7+$2a)            ; trns flag = 0
        move    #>$03d70a,x0            ; thr 0.03
        move    x0,x:(r7+$27)
        move    #>$2ccccd,x0            ; invR 0.35: ~2.5:1 in dB
        move    x0,x:(r7+$28)
        move    #>$004a38,x0            ; attack 10 ms: lets transients through
        move    x0,x:(r7+$2d)
        move    #>$0001dc,x0            ; release 400 ms
        move    x0,x:(r7+$2e)
        bra     ch_cdone
chcmtr:
        move    #>$7fffff,a             ; TRNS: a boost above the slow follower
        move    a,x:(r7+$2a)            ; trns flag = 1
        move    a,x:(r7+$27)            ; threshold 1.0: the static curve never
                                        ; fires, only the boost term does
        clr     a
        move    a,x:(r7+$28)            ; invR 0
        move    #>$05ac58,x0            ; attack 0.5 ms
        move    x0,x:(r7+$2d)
        move    #>$0018c4,x0            ; release 30 ms
        move    x0,x:(r7+$2e)
        move    #>$200000,x0            ; fast follower
        move    x0,x:(r7+$2d)
        move    #>$004000,x0            ; slow follower
        move    x0,x:(r7+$2e)
ch_cdone:
; ---- the gain computer, once per block, on the LAST block's max |key| ----
        move    x:(r7+$1d),x1           ; env = the block max (persistent)
        clr     a
        move    a,x:(r7+$1d)            ; the max restarts each block
        move    x:(r7+$1e),b            ; slow follower, TRNS's reference
        move    x1,a
        sub     b,a                     ; env - slow
        move    a,x0
        move    #>$040000,y1            ; 1/32 a block: ~12 ms
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$1e)            ; slow'
        move    #>$400000,b             ; gr/2 = 0.5 (unity) unless over thr
        move    x1,a
        move    x:(r7+$27),x0           ; thr
        sub     x0,a                    ; over = env - thr
        ble     ch_gunity
        move    a,x0
        move    x:(r7+$28),y1           ; invR
        mpy     x0,y1,a                 ; over / R
        move    x:(r7+$27),x0
        add     x0,a                    ; num = thr + over/R  (< env: invR < 1)
        move    a,y1                    ; num, 24 bits
        move    y1,a                    ; a clean load: a0 = 0 for the divide
        move    x1,x0                   ; den = env
        andi    #$fe,ccr                ; carry clear
        rep     #$18
        div     x0,a                    ; 24 quotient bits land in a0
        move    a0,x0                   ; gr = num / env (a0 IS the quotient here)
        move    x0,a
        asr     #$1,a,a                 ; gr/2
        move    #>$400000,b
        sub     a,b                     ; 0.5 - gr/2 = the reduction, halved
        move    b,x0
        move    x:(r7+$26),y1           ; COMP
        mpy     x0,y1,b                 ; scaled by the knob
        move    #>$400000,a
        sub     b,a                     ; gr/2 = 0.5 - reduction*COMP
        move    a,b
ch_gunity:
; makeup = 1 + 0.5*COMP, on BOTH branches (a makeup applied only above the
; threshold cancels the reduction instead of lifting the whole signal) --
; and not in TRNS, which boosts on its own: the term is COMP * (1 - flag)
        move    b,x:(r7+$45)            ; park gr/2
        move    x:(r7+$26),a            ; COMP
        move    x:(r7+$2a),x0           ; trns flag
        move    x:(r7+$26),y1
        mpy     x0,y1,b                 ; COMP * flag
        sub     b,a                     ; COMP * (1 - flag)
        move    a,y1
        move    x:(r7+$45),x0           ; gr/2
        mpy     x0,y1,a                 ; gr/2 * COMP'
        asr     #$1,a,a
        move    x:(r7+$45),b
        add     a,b                     ; gr/2 * (1 + 0.5*COMP')
; TRNS: gr/2 += 4 * (env - slow)+ * COMP * flag, capped at 1.0 (gr 2.0)
        move    x1,a
        move    x:(r7+$1e),x0
        sub     x0,a                    ; env - slow
        move    #>$0,x0
        tmi     x0,a                    ; the rising side only
        move    a,x0
        move    x:(r7+$2a),y1           ; trns flag
        mpy     x0,y1,a
        move    a,x0
        move    x:(r7+$26),y1           ; COMP
        mpy     x0,y1,a
        asl     #$2,a,a                 ; x4
        add     a,b
        move    #>$7fffff,x0
        cmp     x0,b
        tgt     x0,b
        move    b,x:(r7+$45)            ; gr/2 target for this block
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
        move    a,x:(r7+$46)            ; the DC blocker off (k = R = 0): a
        move    a,x:(r7+$47)            ; symmetric curve leaves no DC
        move    #>$7fffff,x0            ; the post low-pass ON (TAPE, the
        move    x0,x:(r7+$4c)           ; fall-through; TUBE keeps it)
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
        move    #>$030000,x0            ; 3<<16 = BUS (zero-padded, see above)
        cmp     x0,a
        beq     ch_sbus
        bra     ch_sdone                ; TAPE: the curve alone
ch_stube:
        move    #>$0300000,x0           ; neg = 0.75: the positive half is
        move    x0,x:(r7+$37)           ; driven harder, so even harmonics
        move    #>$7fffff,x0            ; ... and DC: the blocker on
        move    x0,x:(r7+$46)
        move    #>$7fdf3b,x0            ; R = 0.999, ~7 Hz
        move    x0,x:(r7+$47)
        bra     ch_sdone
ch_sfuzz:
        move    #>$266666,x0            ; clip +0.6
        move    x0,x:(r7+$3a)
        move    #>$d9999a,x0            ; clip -0.6
        move    x0,x:(r7+$3b)
        move    #>$7fffff,x0            ; the blocker on (the crush and the
        move    x0,x:(r7+$46)           ; fold ahead of a hard clip are not
        move    #>$7fdf3b,x0            ; symmetric on real material)
        move    x0,x:(r7+$47)
        clr     a
        move    a,x:(r7+$4c)            ; FUZZ stays bright: no low-pass
        bra     ch_sdone
ch_sbus:
        move    #>$200000,x0            ; pre = 0.5 ...
        move    x0,x:(r7+$38)
        move    #>$7fffff,x0            ; ... post = 2.0
        move    x0,x:(r7+$39)
        clr     a
        move    a,x:(r7+$4c)            ; a return is clean: no low-pass
; BUS: CRSH and RING are the RETURN levels. The crush mask goes all-ones and
; the carrier step 0, so the stages those knobs used to drive are neutral.
        move    #>$ffffff,x0
        move    x0,x:(r7+$23)           ; crush: identity
        clr     a
        move    a,x:(r7+$24)            ; ring: no carrier
; ONE RETURN (the one-aux rig, 7 Sep 2026): RET (the CRSH knob) is the level
; of the LAST LIVE STAGE's output -- the reverb's if it is running, else the
; delay's, else nothing -- resolved below from the engines' liveness stamps.
; The RING knob is inert in BUS mode. And the return is PINNED to TRACK 8:
; dispatch position 3 on payload A only -- a BUS-mode
; station anywhere else, core 1's position 3 (track 4) included, returns
; nothing.
        move    x:(r6+$2),x0
        move    x0,x:(r7+$3e)           ; RET level (the CRSH knob)
; ... on PAYLOAD A ONLY: the mirror position on core 1 is track 4. An insert
; carries no per-payload literal (an FX1 module may own no buffers, so the
; build refuses it a base), so the core is read off the DISPATCH TABLE: in
; the specialized image BusVerb (id 0x07) is real on payload A and ALIASED
; TO SEND (id 0x09) on payload B -- X:$215+7 == X:$215+9 there. Under the
; DEV hatch everything is payload A and the test allows. Consequence: a
; remix WITHOUT BusVerb has no return anywhere (its id aliases on both
; cores); the rig always carries it on T5.
        move    x:>$21c,a               ; INIT_TABLE[REVERB SERVER]
        move    x:>$21e,x0              ; INIT_TABLE[SEND]
        cmp     x0,a
        beq     ch_nopos                ; the alias: payload B, never the return
        move    r7,a
        and     #>$ff00,a
; ⚠️ r7 is NOT 0x6100 + 0x100 * (2*pos + fx-1). The stock dispatcher bumps
; its r7 counter THREE times per track (FX1 at P:0x4ae, FX2 at P:0x4e4 and
; an unconditional third at P:0x51e after FX2), so a track's FX1 is at
; 0x6100 + 0x300*pos and its FX2 at 0x6200 + 0x300*pos -- measured 8 Sep
; 2026 on BOTH payloads with the firmware driving the DSP (the ColdFire port,
; COLDFIRE_PORT.md O11): position 3 is $6a00/$6b00. The old $6700/$6800 was
; the harness's two-per-track model (dsp_host's r7probe comment), matched
; ONLY in dsp_host -- which is why verify_onebus was green while the unit
; never returned (FAILURE_MODES "the one-aux return never reaches T8":
; the station ran with r7 = $6a00, took ch_nopos, cleared RET, stamped
; nothing, and both hosts kept printing -- reproduced under the port).
        move    #>$6a00,x0
        cmp     x0,a
        beq     ch_pos3
        move    #>$6b00,x0
        cmp     x0,a
        beq     ch_pos3
ch_nopos:
        clr     a
        move    a,x:(r7+$3e)            ; not track 8: no return
ch_pos3:
ch_sdone:
; post/2 *= 1/sqrt(1 + 15*DRV/128) (12 Sep 2026): the drive's 1x..16x
; pre-gain would otherwise read as a +16 dB fader at the unit's level. With
; the square root, a saturated signal (the curve caps at 2/3) comes out near
; unity at full drive and a quiet one gains ~+12 dB: drive densifies more
; than it turns up. A 17-word P table (the manifest's DspSection.ptable,
; DRIVE_COMP; the build rewrites the literal), interpolated: idx = DRV >> 19
; (0..15), frac = the 19 bits under it. r5 is free here (the BUS pointers
; load later). AGU settle: two instructions between the r5/n5 writes and use.
        move    x:(r6+$0),a             ; DRV/128, Q23
        move    a,x1
        move    #>$fab1e0,r5            ; DRIVE_COMP -- rewritten by build_bus.py
        move    #>$ffffff,m5
        asr     #$13,a,a                ; idx
        move    r5,r1                   ; ... and TANH_TD is the 17 words after
        move    #>17,n1                 ; it: r1 -> the curve's table, parked in
        move    #>$ffffff,m1            ; r2 = r1 + 1 for the sample loop (below)
        move    a1,n5
        move    x1,a
        and     #>$7ffff,a              ; DRV & (2^19 - 1)   (a2 = 0: DRV >= 0)
        asl     #$4,a,a                 ; frac, Q23
        move    (r5)+n5
        move    a,x0                    ; frac
        move    p:(r5)+,y0              ; T[idx]
        move    p:(r5),b                ; T[idx+1]
        move    y0,a
        sub     a,b                     ; T[idx+1] - T[idx]  (<= 0: the table falls)
        move    b,y1
        mpy     x0,y1,a                 ; frac * diff
        add     y0,a                    ; comp, 0.25 .. 1
        move    a,y1
        move    x:(r7+$39),x0           ; post/2 (1.0 or BUS's 2.0, halved)
        mpy     x0,y1,a
        move    a,x:(r7+$39)
        move    (r1)+n1                 ; r1 = TANH_TD (n1 written 12 back)
        move    r1,r2
        move    (r2)+                   ; r2 = its slopes
; kl = 0.6 * DRV/128 * the mode flag ($4c): the post low-pass, ~16 kHz at
; DRV 32, ~8 k at 64, ~3.6 k at 127 in TAPE / TUBE; 0 (bit-exact) elsewhere.
        move    x1,x0                   ; DRV/128
        move    #>$4ccccd,y1            ; 0.6
        mpy     x0,y1,a
        move    x:(r7+$4c),y1           ; 1.0 / 0
        move    a,x0
        mpy     x0,y1,a
        move    a,x:(r7+$49)            ; kl
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
        move    a,r4                    ; REVERB output [read]
        add     #>$80,a
        move    a,r5                    ; DELAY output [read]
        move    #>$ffffff,m4
        move    #>$ffffff,m5
; ---- ONLY THE RETURN READS THE STAMPS (9 Sep 2026, found under the port) --
; The engines' liveness words are clear-on-read, single reader by design. A
; BUS-mode station on any OTHER track (T4, T7 -- flash 6's claim vii only
; asked that it return nothing, and it does) was still running this block,
; stealing the stamps before T8's return read them: with such a station in
; the part the REAL return went silent from its first sample (the port,
; COLDFIRE_PORT.md O12; the local gate never tried both at once). A station
; whose RET level is 0 -- not track 8, or the knob down -- has no business
; here: skip the reads AND the RETV/RETD stamps below. (The engines then
; keep printing, which is what a return at 0 means.)
        move    x:(r7+$3e),a
        tst     a
        beq     ch_ndl                  ; no return level: touch nothing
; ---- which stage is live? (one-aux rig, 7 Sep 2026) ---------------------
; Each engine stamps its own word every block it processes (y:$9c4 reverb,
; y:$9c5 delay); this reads and clears them (single writer, single reader)
; and keeps 3 blocks of grace each in r7 $3c/$3d -- RETV's shape, for a
; stamp the other core's timing loses. Reverb live: read its output (r4).
; Delay live only: read the delay's (r4 := r5). Neither: the level is 0.
        move    x:(r7+$3c),a            ; reverb grace
        and     #>$3,a
        move    a1,x0
        move    x0,b
        move    #>$1,x0
        sub     x0,b
        move    #>$0,x0
        tmi     x0,b
        move    y:>$9c4,a
        move    x0,y:>$9c4              ; clear-on-read
        move    #>$3,x0
        tst     a
        tne     x0,b
        move    b,x:(r7+$3c)
        move    x:(r7+$3d),a            ; delay grace
        and     #>$3,a
        move    a1,x0
        move    x0,b
        move    #>$1,x0
        sub     x0,b
        move    #>$0,x0
        tmi     x0,b
        move    y:>$9c5,a
        move    x0,y:>$9c5              ; clear-on-read
        move    #>$3,x0
        tst     a
        tne     x0,b
        move    b,x:(r7+$3d)
        move    x:(r7+$3c),a
        tst     a
        bne     ch_rvlive               ; reverb live: r4 is right already
        move    x:(r7+$3d),a
        tst     a
        beq     ch_nolive
        move    r5,r4                   ; delay only: return the delay's output
        bra     ch_rvlive
ch_nolive:
        clr     a
        move    a,x:(r7+$3e)            ; nothing live: return nothing
ch_rvlive:
        move    x:(r7+$3e),a            ; RET up: tell BOTH hosts to go quiet
        tst     a
        beq     ch_ndl
        move    #>$1,x0
        move    x0,y:>$9d8
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
        move    x:(r7+$21),y1           ; gq = gain/32
        mpy     x0,y1,a                 ; v/32
        asl     #$4,a,a                 ; v/2
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
        asl     #$4,a,a
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
        move    x:(r7+$22),y1           ; gd = gain/16
        mpy     x0,y1,a
        asl     #$2,a,a                 ; driven/4: the curve's table spans 0..4
        move    a,x:(r7+$35)            ; LIMITING store at driven 4 = tanh 0.9993
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
; the clip (FUZZ's +-0.6) sits on the CURVE's output, before post: with post
; compensated for the drive (12 Sep 2026) a clip after it never bit -- FUZZ
; measured identical to TAPE across the dial.
        move    x:(r7+$3a),x0           ; +clip
        cmp     x0,a
        tgt     x0,a
        move    x:(r7+$3b),x0           ; -clip
        cmp     x0,a
        tlt     x0,a
        move    a,x0
        move    x:(r7+$39),y1           ; post / 2
        mpy     x0,y1,a
        asl     #$1,a,a
; DC block, y = x - x1 + R*y1, R = 0.999 (~7 Hz), 12 Sep 2026: TUBE's
; asymmetry left ~-30 dBFS of DC on a sine, which the compressor's detector
; and the bus would both have taken as signal. Every mode gets it (FUZZ and
; the crush are not symmetric either). State $41/$43 (L: x1, y1); long-form
; slots, per-block-cheap enough at ~10 words a channel. mac x0,y1 is the
; audited-signed order, and R is positive in any case.
        move    a,x0                    ; x
        move    x:(r7+$41),x1           ; x1
        move    x0,x:(r7+$41)           ; x1 <- x
        move    x:(r7+$46),y1           ; k: 1.0 in TUBE / FUZZ, 0 elsewhere
        mpy     x1,y1,b                 ; k*x1 (mpysu: y1 is positive)
        sub     b,a                     ; x - k*x1
        move    x:(r7+$43),x0           ; y1
        move    x:(r7+$47),y1           ; R: 0.999 in TUBE / FUZZ, 0 elsewhere
        mac     x0,y1,a                 ; + R*y1  -- k = R = 0 is y = x exactly,
        move    a,x:(r7+$43)            ; y1 <- y     so TAPE / BUS stay bit-exact
; Tape darkens as it drives (12 Sep 2026, by ear): one pole after the curve,
; y = x - kl*(x - y1), kl = 0.6*DRV/128 in TAPE / TUBE and 0 elsewhere --
; kl = 0 is y = x exactly, so FUZZ / BUS and DRV 0 stay bit-exact. State
; $4a/$4b (L/R), kl in $49.
        move    a,y0                    ; x
        move    x:(r7+$4a),x0           ; y1
        sub     x0,a                    ; x - y1
        move    a,x0
        move    x:(r7+$49),y1           ; kl
        mpy     x0,y1,a                 ; kl*(x - y1)  (signed order)
        neg     a
        add     y0,a                    ; y
        move    a,x:(r7+$4a)
        move    a,x:(r7+$35)            ; saturated L, DC-free, darkened
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
        move    x:(r7+$3a),x0           ; clip before post (as L)
        cmp     x0,a
        tgt     x0,a
        move    x:(r7+$3b),x0
        cmp     x0,a
        tlt     x0,a
        move    a,x0
        move    x:(r7+$39),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,x0                    ; the DC block, R side ($42/$44); x1
        move    x:(r7+$42),b            ; parks L across this, so b carries x1
        move    x0,x:(r7+$42)
        move    x:(r7+$46),y1           ; k
        move    b,x0
        mpy     x0,y1,b
        move    a,x0
        move    x0,a
        sub     b,a                     ; x - k*x1
        move    x:(r7+$44),x0
        move    x:(r7+$47),y1           ; R
        mac     x0,y1,a
        move    a,x:(r7+$44)
        move    a,y0                    ; the low-pass, R side ($4b); x1 still
        move    x:(r7+$4b),x0           ; parks L
        sub     x0,a
        move    a,x0
        move    x:(r7+$49),y1
        mpy     x0,y1,a
        neg     a
        add     y0,a
        move    a,x:(r7+$4b)
        move    a,x:(r7+$36)            ; saturated R, DC-free, darkened
        move    x1,x:(r7+$35)           ; L back from its park
; ---- COMPRESS: the block-max detector, and the gain slewed to the block's
; target -- attack while it falls, release while it rises (12 Sep 2026) ---
        move    x:(r7+$32),a            ; key
        abs     a
        move    x:(r7+$1d),x0           ; the block max so far
        cmp     x0,a                    ; nothing between this and the Tcc
        tlt     x0,a
        move    a,x:(r7+$1d)
        move    x:(r7+$45),a            ; gr/2 target
        move    x:(r7+$1f),x0           ; gr/2 now
        sub     x0,a                    ; d = target - now
        move    x:(r7+$2d),x1           ; attack coefficient
        move    x:(r7+$2e),b            ; release coefficient
        tst     a                       ; sign of d -- nothing between this
        tmi     x1,b                    ; and the Tcc: falling = attack
        move    b,y1
        move    a,x0
        mpy     x0,y1,a                 ; c * d
        move    x:(r7+$1f),b
        add     b,a                     ; gr/2 += c * d
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
; (the send taps left with the sends, 12 Sep 2026: the stations have had no
; send since the one-aux rig; the returns below still need the bus)
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
        move    #>$1,n0
        do      n7,>ch_byz
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
ch_bynor:
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
ch_byz:
        nop
        rts

; ---------------------------------------------------------------------------
; chsatur -- BusDelay's loop-saturation curve, sat = w - w^3/3.
; In:  x:(r7+$35) = w (already limited by its store).  Out: a = sat.
; Unity small-signal by construction, monotonic, |out| bounded -- the same
; argument modules/busdelay/delay_server.asm's satdrv makes, which is why
; this can sit in front of a compressor without adding gain.
; bsr, not jsr: dsp_asm implements only the relative b-forms.
; ---------------------------------------------------------------------------
; The curve is tanh(4w), w = driven/4 (12 Sep 2026, by ear: the cubic
; w - w^3/3 is a soft knee only up to |w| = 1 and a hard clip above it, and
; at DRV 96+ the whole top of a drum loop sat on that flat -- "digital,
; clippy"). tanh never goes flat: every extra dB in still changes the
; output. A 33-pair P table (TANH_TD in the manifest: value, slope-to-next,
; interleaved; the second half of the module's ptable after DRIVE_COMP),
; linear interpolation over [0, 4]: idx = |w| >> 18, frac = the 18 bits
; under it. r1 = the table and r2 = r1 + 1 (both per block; (Rn+Nn) reads
; leave them alone), n1 = 2*idx. Odd symmetry restored with one tst + one
; Tcc. Clobbers x0 y0 y1 b n1 n2 -- never x1 (the R pass parks L there).
chsatur:
        move    x:(r7+$35),b            ; w
        abs     b
        move    b,y1                    ; |w|
        asr     #$11,b,b                ; |w| >> 17 = 2*idx + bit 17 ...
        and     #>$fffffe,b             ; ... masked to 2*idx (an asl after the
        move    b1,n1                   ; asr would pull B0's top bit back in)
        move    b1,n2                   ; (Rn+Nn) wants its own N
        move    y1,b
        and     #>$3ffff,b              ; |w| & (2^18 - 1)   (b2 = 0: |w| >= 0)
        asl     #$5,b,b                 ; frac, Q23
        move    b,x0                    ; AGU settle: n1 written 4 back
        move    p:(r1+n1),y0            ; T[idx]
        move    p:(r2+n2),y1            ; T[idx+1] - T[idx]  (>= 0)
        mpy     x0,y1,a                 ; frac * slope  (signed order; both >= 0)
        add     y0,a                    ; |sat|
        move    a,x0
        neg     a                       ; -|sat|
        move    x:(r7+$35),b
        tst     b                       ; sign of w -- nothing between this
        tpl     x0,a                    ; and the Tcc
        rts
