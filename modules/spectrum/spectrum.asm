; ---------------------------------------------------------------------------
; SPECTRUM -- two filters, four routings, one modulation, two sends.
;
; Insert contract (modules/ripple/ripple_svf.asm): frames in place at
; x:(r0)/x:(r0+n0), knobs from r6, state in this instance's r7 block. PLUS
; the bus-client contract from modules/send/send_client.asm: the PROCESSED
; frames are summed to mono and added into the REVERB and DELAY accumulators
; at this block's write offset, and the instance registers in the per-block
; client count -- ONLY when its send knob is non-zero.
;
; ---- signal ---------------------------------------------------------------
;   x_d  = clip(x * gain)                                  DRV
;   A    = SVF(x_d, f, damp): lp / bp / hp taps            FREQ RES MODE
;   wetA = kLP*lp + kBP*bp + kHP*hp                        (MODE, per block)
;   yB   = sel ? wetA : x                                  (ROUT, per block)
;   B    = LP2_wdth( HP2_base( yB ) )                      BASE WDTH
;   out  = kA*wetA + kB*B + kR*(2*wetA*B)                  (ROUT, per block)
;   f    = fA + kFM*B_prev  (clamped)                      (FM only)
;   fA   = law( FREQ + (DPTH-64)/64 * mod )                mod: ENV/LFO/BOTH
; NOTCH is kLP = kHP = 1 (lp + hp = x - damp*bp). VOWEL is BP at F1 with B
; a band at F2, routing forced PAR, F1/F2 morphed across five formants.
;
; ---- NO HOUSEKEEPING, by design ------------------------------------------
; The election (SEND's bus_dohk) is for FX2 participants. An FX1 instance on
; track 5 runs BEFORE that track's FX2 instance, and position 0 (r7 = 0x6200)
; housekeeps unconditionally -- so an FX1 participant that also elected would
; flip the rotation TWICE in the first block, which leaves core 1's private
; tracking one step behind forever (the R25 metallic). This station reads the
; rotation and writes; it never flips. On core 0 its contribution therefore
; lands in the buffer written LAST block (it runs before the flip), which is
; read one block sooner than everyone else's -- 16 samples less bus latency
; and nothing lost: that buffer was cleared two blocks ago and is read next.
;
; ---- r7 slots -------------------------------------------------------------
;   $20 fA (per block, post-modulation)   $21 damp          $22 g4 (gain/4)
;   $23 kLP  $24 kBP  $25 kHP              $26 kA  $27 kB  $28 kR  $29 sel
;   $2a cHP  $2b cLP  $2c kFM              $2d bypass flag
;   $30 FX2-slot flag (set at init: 1 = this instance is on FX2, dry)
;   $31 LFO phase (PERSISTENT, masked)     $32 env (PERSISTENT, clamped)
;   $34/$35 SVF lp/bp L   $36/$37 SVF lp/bp R                 (PERSISTENT)
;   $38..$3b B poles L: hp1 hp2 lp1 lp2    $3c..$3f R         (PERSISTENT)
;   $19/$1a B_out previous sample L/R (the FM source)         (PERSISTENT)
;   $1b wetA  $1c f this sample  $1d x / yB park  $1e peak (this block, so
;   at decode time LAST block's)  $1f f ceiling (per block)
;   $46 fall  $47 lfo inc  $49 lfo / frac park  $4a..$4d VOWEL picks
;   ⚠️ EVERY SLOT THE SAMPLE LOOP TOUCHES IS BELOW $40: an r7-indexed move
;   with a displacement past 63 takes the two-word long form, and the loop
;   priced 30 words dearer with these at $40..$4f (3 Sep 2026). Per-block
;   slots may sit high; per-sample ones may not.
; Persistent states are bounded by the limited stores or masked on use;
; nothing here ever becomes an address except the bus pointers, which come
; masked exactly as SEND's are.
;
; Every mpy is `mpy x0,y1` (the known-signed encoding) except the send taps,
; which are SEND's `mpy x1,y1` / `mpy x1,y0` with a non-negative level in the
; second operand -- the one condition under which that order is safe. The FM
; clamp and the env max are cmp + ONE Tcc with nothing between (the flag
; trap).
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
        move    b,x:(r7+$30)          ; 1 = dry pass
        rts

proc:
        move    x:(r7+$30),a           ; an FX2 slot: dry, nothing written
        tst     a
        bne     fs_end
; (the bus section -- split-aware frame offset, the rotation latch, the registration
; and the r1/r2 accumulator pointers -- left with the sends, 12 Sep 2026: the
; stations have carried no send since the one-aux rig of 7 Sep, and the ~70
; words and ~10 cycles a block it cost bought nothing. The station is no
; longer a bus client: Harness(bus_client=False).)
; ===========================================================================
; PER-BLOCK KNOB DECODE
; ===========================================================================
; damp = (0.998 - RES * 0.587)^4   -- base linear in RES, then squared twice,
; so the resonant PEAK is close to linear in dB across the dial: ~0.8 / 5.5 /
; 12 / 20 / 30 dB at RES 0 / 32 / 64 / 96 / 127. Ripple's linear damp
; (0.992 - RES * 0.969, the law until 12 Sep 2026) measured 0.8 / 2.7 / 5.7 /
; 11.3 / 29.5 dB on noise: 18 of the 29 dB lived in the top quarter of the
; dial (tools/harness/station_laws.py). RES 0 is unchanged (0.998^4 = 0.992).
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
        mpy     x0,y1,a                 ; base^4
        move    a,x:(r7+$21)
; g4 = 0.25 + DRV * 0.75  (page-2 slot 6 KNOB field of r6+$c)
        move    x:(r6+$c),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        move    a,x0
        move    #>$600000,y1
        mpy     x0,y1,a
        add     #>$200000,a
        move    a,x:(r7+$22)
; cHP = BASE^2 * 0.5 ;  cLP = WDTH^2 * 1.0 + 0.002  (one-pole coefficients)
; cLP's scale was 0.75 until 12 Sep 2026: WDTH 127 then sat at 0.74 (about
; 7 kHz per pole, 12 dB/oct above it), so "open" lost 5 dB at 10 kHz and 8 dB
; at 15 kHz in EVERY live setting -- measured on noise, station_laws.py --
; and only the all-defaults bypass was flat. At 1.0 WDTH 127 is 0.986: a
; corner near 30 kHz per pole, flat within 0.15 dB at 10 kHz.
        move    x:(r6+$2),x0
        move    x:(r6+$2),y1
        mpy     x0,y1,a
        move    a,x0
        move    #>$400000,y1
        mpy     x0,y1,a
        move    a,x:(r7+$2a)
        move    x:(r6+$3),x0
        move    x:(r6+$3),y1
        mpy     x0,y1,a
        move    a,x0
        move    #>$7fffff,y1            ; x 1.0
        mpy     x0,y1,a
        add     #>$4189,a
        move    a,x:(r7+$2b)
; RATE (slot 10 KNOB of r6+$e): lfo inc = RATE^2 * $7000 + $100 per block
; (~0.08..9 Hz); fall = $7fe000 - RATE * $1e00 (~370 ms .. ~3 ms release)
        move    x:(r6+$e),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    a,x0
        move    #>$7000,y1
        mpy     x0,y1,a
        add     #>$100,a
        move    a,x:(r7+$47)            ; lfo inc
        move    x:(r6+$e),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        move    a,x0
        move    #>$f0000,y1
        mpy     x0,y1,a                 ; RATE * $1e00 in Q23
        neg     a
        add     #>$7fe000,a
        move    a,x:(r7+$46)            ; fall

; ---- LFO: phase += inc, triangle -> bipolar Q23 ---------------------------
        move    x:(r7+$31),a
        move    x:(r7+$47),x0
        add     x0,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$31)
        move    #>$400000,x0
        sub     x0,a
        abs     a                       ; 0 .. $400000
        move    #>$200000,x0
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

; ---- SRC (slot 11 select of r6+$e): mod = env | lfo | (env+lfo)/2 ---------
        move    x:(r6+$e),a
        and     #>$ff00,a
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        move    #>$10000,x0
        cmp     x0,a
        beq     fs_slfo
        move    #>$20000,x0
        cmp     x0,a
        beq     fs_sboth
        move    x:(r7+$32),a            ; ENV (and anything unexpected)
        bra     fs_smod
fs_slfo:
        move    x:(r7+$49),a
        bra     fs_smod
fs_sboth:
        move    x:(r7+$32),a
        move    x:(r7+$49),x0
        add     x0,a
        asr     #$1,a,a
fs_smod:
; ---- DPTH (slot 8 KNOB of r6+$d): depth = (DPTH - 64)/64, bipolar ---------
        move    a,x1                    ; mod
        move    x:(r6+$d),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        move    #>$400000,x0
        sub     x0,a                    ; (DPTH-64)/128
        asl     #$1,a,a                 ; (DPTH-64)/64, -1 .. +1
        move    a,x0
        move    x1,y1
        mpy     x0,y1,a                 ; depth * mod  (x0 signed, y1 signed)
        move    x:(r6+$0),x0            ; FREQ
        add     x0,a                    ; FREQm
        move    #>$0,x0
        tmi     x0,a                    ; clamp below at 0
        move    #>$7f0000,x0
        cmp     x0,a
        tgt     x0,a                    ; clamp above at 127/128
; fA = table(FREQm): an EXPONENTIAL taper, 24 Hz..7.2 kHz, one octave per
; ~15.5 detents, read from the 33-word P table the manifest declares
; (DspSection.ptable; the build places it before this code and rewrites the
; literal below) and interpolated linearly: idx = FREQm >> 18 (0..31),
; frac = the 18 bits under it as Q23. Until 12 Sep 2026 the law was
; 0.984 * FREQm^2 + 0.0034 -- half the dial above 2 kHz on noise, and the
; loop's centroid on the drum loop barely moved from FREQ 24 to 56.
; AGU settle: r5/n5 are written two instructions before they address.
        move    a,x1                    ; FREQm, kept
        move    #>$fab1e0,r5            ; FREQ_TABLE -- rewritten by build_bus.py
        move    #>$ffffff,m5
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
        move    a,x:(r7+$20)            ; fA

; ---- ROUT (slot 9 select of r6+$d): sel, kA, kB, kR, kFM -------------------
        clr     a
        move    a,x:(r7+$29)            ; sel = 0
        move    a,x:(r7+$26)            ; kA
        move    a,x:(r7+$27)            ; kB
        move    a,x:(r7+$28)            ; kR
        move    a,x:(r7+$2c)            ; kFM
        move    x:(r6+$d),a
        and     #>$ff00,a
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        move    #>$10000,x0
        cmp     x0,a
        beq     fs_rpar
        move    #>$20000,x0
        cmp     x0,a
        beq     fs_rring
        move    #>$30000,x0
        cmp     x0,a
        beq     fs_rfm
        move    #>$1,x0                 ; SER (and anything unexpected):
        move    x0,x:(r7+$29)           ; B is fed A, out = B
        move    #>$7fffff,x0
        move    x0,x:(r7+$27)
        bra     fs_rdone
fs_rpar:
        move    #>$400000,x0            ; PAR: out = (A + B) / 2
        move    x0,x:(r7+$26)
        move    x0,x:(r7+$27)
        bra     fs_rdone
fs_rring:
        move    #>$7fffff,x0            ; RING: out = 2 * A * B
        move    x0,x:(r7+$28)
        bra     fs_rdone
fs_rfm:
        move    #>$7fffff,x0            ; FM: out = A, f modulated by B
        move    x0,x:(r7+$26)
        move    #>$200000,x0            ; kFM = 0.25
        move    x0,x:(r7+$2c)
fs_rdone:

; ---- MODE (slot 7 select of r6+$c): tap coefficients; VOWEL overrides -----
        clr     a
        move    a,x:(r7+$23)
        move    a,x:(r7+$24)
        move    a,x:(r7+$25)
        move    #>$7fffff,x0
        move    x:(r6+$c),a
        and     #>$ff00,a
        move    a1,x1
        move    x1,a
        asl     #$8,a,a                 ; mode << 16
        move    #>$10000,x1
        cmp     x1,a
        beq     fs_mbp
        move    #>$20000,x1
        cmp     x1,a
        beq     fs_mhp
        move    #>$30000,x1
        cmp     x1,a
        beq     fs_mntch
        move    #>$40000,x1
        cmp     x1,a
        beq     fs_mvowl
        move    x0,x:(r7+$23)           ; LP, and anything unexpected
        bra     fs_mdone
fs_mbp:
        move    x0,x:(r7+$24)
        bra     fs_mdone
fs_mhp:
        move    x0,x:(r7+$25)
        bra     fs_mdone
fs_mntch:
        move    x0,x:(r7+$23)
        move    x0,x:(r7+$25)
        bra     fs_mdone
fs_mvowl:
; ---- VOWEL: A = band-pass at F1, B = a band at F2, routing forced PAR; ----
; F1 (an SVF f) and F2 (a one-pole c) morph across A E I O U with FREQ:
; idx = FREQ >> 5 (0..3) picks the pair, frac = (FREQ & 31)/32 interpolates.
; Constants are 2*sin(pi*F/44100) and 1-exp(-2*pi*F/44100) in Q23 for
; A 730/1090, E 530/1840, I 270/2290, O 570/840, U 300/870 Hz.
        move    x0,x:(r7+$24)           ; kBP = 1
        clr     a
        move    a,x:(r7+$29)            ; sel = 0
        move    a,x:(r7+$28)
        move    a,x:(r7+$2c)
        move    #>$400000,x0            ; PAR
        move    x0,x:(r7+$26)
        move    x0,x:(r7+$27)
        move    x:(r6+$0),a
        asr     #$10,a,a
        and     #>$1f,a                 ; FREQ & 31
        asl     #$12,a,a                ; -> frac, Q23
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$49)            ; frac (the lfo park is dead by now)
        move    x:(r6+$0),a
        asr     #$15,a,a                ; idx = FREQ >> 5, 0..3
        move    a1,x0
        move    x0,a
        move    #>$1,x0
        cmp     x0,a
        blt     fs_v0
        beq     fs_v1
        move    #>$2,x0
        cmp     x0,a
        beq     fs_v2
        move    #>$0a6466,x0            ; idx 3: O -> U
        move    x0,x:(r7+$4a)
        move    #>$05787d,x0
        move    x0,x:(r7+$4b)
        move    #>$0e7015,x0
        move    x0,x:(r7+$4c)
        move    #>$0eec14,x0
        move    x0,x:(r7+$4d)
        bra     fs_vint
fs_v2:
        move    #>$04ec75,x0            ; idx 2: I -> O
        move    x0,x:(r7+$4a)
        move    #>$0a6466,x0
        move    x0,x:(r7+$4b)
        move    #>$23a244,x0
        move    x0,x:(r7+$4c)
        move    #>$0e7015,x0
        move    x0,x:(r7+$4d)
        bra     fs_vint
fs_v1:
        move    #>$09a9cc,x0            ; idx 1: E -> I
        move    x0,x:(r7+$4a)
        move    #>$04ec75,x0
        move    x0,x:(r7+$4b)
        move    #>$1d8496,x0
        move    x0,x:(r7+$4c)
        move    #>$23a244,x0
        move    x0,x:(r7+$4d)
        bra     fs_vint
fs_v0:
        move    #>$0d4e94,x0            ; idx 0: A -> E
        move    x0,x:(r7+$4a)
        move    #>$09a9cc,x0
        move    x0,x:(r7+$4b)
        move    #>$12695e,x0
        move    x0,x:(r7+$4c)
        move    #>$1d8496,x0
        move    x0,x:(r7+$4d)
fs_vint:
; v = a + frac * (b - a), both tables
        move    x:(r7+$4b),a
        move    x:(r7+$4a),x0
        sub     x0,a
        move    a,x0                    ; b - a (signed)
        move    x:(r7+$49),y1           ; frac
        mpy     x0,y1,a
        move    x:(r7+$4a),x0
        add     x0,a
        move    a,x:(r7+$20)            ; fA = F1 (no modulation in VOWEL)
        move    x:(r7+$4d),a
        move    x:(r7+$4c),x0
        sub     x0,a
        move    a,x0
        move    x:(r7+$49),y1
        mpy     x0,y1,a
        move    x:(r7+$4c),x0
        add     x0,a
        move    a,x:(r7+$2a)            ; cHP = F2
        move    a,x:(r7+$2b)            ; cLP = F2: a band around F2
fs_mdone:

        move    #>$7d0e56,x0            ; the SVF's stable f ceiling, staged for
        move    x0,x:(r7+$1f)           ; the loop's FM clamp (1-word loads there)

; ---- BYPASS: the defaults are a bit-exact passthrough ---------------------
; FREQ 127, RES 0, BASE 0, WDTH 127, DRV 0, DPTH 64, MODE LP, ROUT SER. Every
; part that ever chose stock FILTER runs this on FX1 after the flash, so the
; neutral block copies nothing and only does the sends.
        clr     b
        move    b,x:(r7+$2d)
        move    x:(r6+$0),a
        move    #>$7f0000,x0
        cmp     x0,a
        bne     fs_live
        move    x:(r6+$1),a
        tst     a
        bne     fs_live
        move    x:(r6+$2),a
        tst     a
        bne     fs_live
        move    x:(r6+$3),a
        cmp     x0,a
        bne     fs_live
        move    x:(r6+$c),a             ; DRV knob field AND the MODE select
        and     #>$7fff00,a
        move    a1,x0
        move    x0,a
        tst     a
        bne     fs_live
        move    x:(r6+$d),a             ; DPTH knob field AND the ROUT select
        and     #>$7fff00,a
        move    a1,x0
        move    x0,a
        move    #>$400000,x0
        cmp     x0,a
        bne     fs_live
        bra     fs_bypass
fs_live:

; ===========================================================================
; THE SAMPLE LOOP
; ===========================================================================
        move    #>$1,n0
        do      n7,>fs_end
; ---- input peak for the envelope follower (mono, pre-filter) --------------
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        abs     a
        move    x:(r7+$1e),x0
        cmp     x0,a
        tlt     x0,a
        move    a,x:(r7+$1e)
; ===================== channel L =====================
        move    x:(r0),x0
        move    x0,x:(r7+$1d)           ; park x
; FM: f = clamp(fA + kFM * B_prev)
        move    x:(r7+$19),x0           ; B_prev L
        move    x:(r7+$2c),y1           ; kFM (0 unless ROUT = FM)
        mpy     x0,y1,a                 ; kFM * B, +-0.25
        move    a,x0
        move    x:(r7+$20),y1           ; fA
        mpy     x0,y1,a                 ; fA * kFM * B: MULTIPLICATIVE FM,
        move    x:(r7+$20),x0           ; so f stays positive by construction
        add     x0,a                    ; f = fA * (1 + kFM * B)
        move    x:(r7+$1f),x0           ; 0.977, the SVF's stable ceiling
        cmp     x0,a
        tgt     x0,a
        move    a,x:(r7+$1c)            ; f this sample
; drive
        move    x:(r7+$1d),x0
        move    x:(r7+$22),y1           ; g4
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x1                    ; x_d, the limiter IS the drive clip
; SVF A: lp += f*bp
        move    x:(r7+$35),x0           ; bp
        move    x:(r7+$1c),y1           ; f
        mpy     x0,y1,a
        move    x:(r7+$34),b
        add     b,a
        move    a,x:(r7+$34)            ; lp'
        move    a,b
; hp = x_d - lp' - damp*bp
        move    x:(r7+$21),y1           ; damp
        mpy     x0,y1,a                 ; damp*bp (x0 still bp)
        neg     a
        sub     b,a
        add     x1,a                    ; hp
        move    a,x0                    ; hp, limited -- the resonance clamp
        move    a,y0                    ; park hp
; bp += f*hp
        move    x:(r7+$1c),y1
        mpy     x0,y1,a
        move    x:(r7+$35),b
        add     b,a
        move    a,x:(r7+$35)            ; bp'
; wetA = kBP*bp' + kHP*hp + kLP*lp'
        move    a,x0
        move    x:(r7+$24),y1
        mpy     x0,y1,a
        move    y0,x0
        move    x:(r7+$25),y1
        mpy     x0,y1,b
        add     b,a
        move    x:(r7+$34),x0
        move    x:(r7+$23),y1
        mpy     x0,y1,b
        add     b,a
        move    a,x:(r7+$1b)            ; wetA
        move    a,x1
; yB = sel ? wetA : x
        move    x:(r7+$29),b
        tst     b
        move    x:(r7+$1d),a
        tne     x1,a
        move    a,x:(r7+$1d)            ; yB
; B: two HP poles (HP = in - LP2(in)) at cHP
        move    x:(r7+$38),b            ; h1
        sub     b,a                     ; yB - h1
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$2a),y1           ; cHP
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a                     ; h1'
        move    a,x:(r7+$38)
        move    x:(r7+$39),b            ; h2
        sub     b,a                     ; h1' - h2
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a                     ; h2'
        move    a,x:(r7+$39)
        move    a,x0
        move    x:(r7+$1d),a
        sub     x0,a                    ; hp2 = yB - h2'
        move    a,x:(r7+$1d)            ; park hp2
; two LP poles at cLP
        move    x:(r7+$3a),b            ; l1
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$2b),y1           ; cLP
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$3a)
        move    x:(r7+$3b),b            ; l2
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$3b)            ; B_out = l2'
        move    a,x:(r7+$19)            ; B_prev for next sample's FM
; out = kA*wetA + kB*B + kR*(2*wetA*B)
        move    a,x0                    ; B_out
        move    x:(r7+$27),y1           ; kB
        mpy     x0,y1,a
        move    x:(r7+$1b),y1           ; wetA (signed x signed: the known-
        mpy     x0,y1,b                 ; signed order)
        asl     #$1,b,b
        move    b,x0
        move    x:(r7+$28),y1           ; kR
        mpy     x0,y1,b
        add     b,a
        move    x:(r7+$1b),x0           ; wetA
        move    x:(r7+$26),y1           ; kA
        mpy     x0,y1,b
        add     b,a
        move    a,x:(r0)                ; out L (limited)
; ===================== channel R =====================
        move    x:(r0+n0),x0
        move    x0,x:(r7+$1d)
        move    x:(r7+$1a),x0           ; B_prev R
        move    x:(r7+$2c),y1           ; kFM (0 unless ROUT = FM)
        mpy     x0,y1,a                 ; kFM * B, +-0.25
        move    a,x0
        move    x:(r7+$20),y1           ; fA
        mpy     x0,y1,a                 ; fA * kFM * B: MULTIPLICATIVE FM,
        move    x:(r7+$20),x0           ; so f stays positive by construction
        add     x0,a                    ; f = fA * (1 + kFM * B)
        move    x:(r7+$1f),x0           ; 0.977, the SVF's stable ceiling
        cmp     x0,a
        tgt     x0,a
        move    a,x:(r7+$1c)            ; f this sample
        move    x:(r7+$1d),x0
        move    x:(r7+$22),y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x1
        move    x:(r7+$37),x0           ; bp R
        move    x:(r7+$1c),y1
        mpy     x0,y1,a
        move    x:(r7+$36),b
        add     b,a
        move    a,x:(r7+$36)
        move    a,b
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        neg     a
        sub     b,a
        add     x1,a
        move    a,x0
        move    a,y0
        move    x:(r7+$1c),y1
        mpy     x0,y1,a
        move    x:(r7+$37),b
        add     b,a
        move    a,x:(r7+$37)
        move    a,x0
        move    x:(r7+$24),y1
        mpy     x0,y1,a
        move    y0,x0
        move    x:(r7+$25),y1
        mpy     x0,y1,b
        add     b,a
        move    x:(r7+$36),x0
        move    x:(r7+$23),y1
        mpy     x0,y1,b
        add     b,a
        move    a,x:(r7+$1b)
        move    a,x1
        move    x:(r7+$29),b
        tst     b
        move    x:(r7+$1d),a
        tne     x1,a
        move    a,x:(r7+$1d)
        move    x:(r7+$3c),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$2a),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$3c)
        move    x:(r7+$3d),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$3d)
        move    a,x0
        move    x:(r7+$1d),a
        sub     x0,a
        move    a,x:(r7+$1d)
        move    x:(r7+$3e),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$2b),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$3e)
        move    x:(r7+$3f),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$3f)
        move    a,x:(r7+$1a)
        move    a,x0
        move    x:(r7+$27),y1
        mpy     x0,y1,a
        move    x:(r7+$1b),y1
        mpy     x0,y1,b
        asl     #$1,b,b
        move    b,x0
        move    x:(r7+$28),y1
        mpy     x0,y1,b
        add     b,a
        move    x:(r7+$1b),x0
        move    x:(r7+$26),y1
        mpy     x0,y1,b
        add     b,a
        move    a,x:(r0+n0)             ; out R
        move    #>$2,n0                 ; LONG immediates, deliberately: the
        move    (r0)+n0                 ; short form `move #2,n0` assembled and
        move    #>$1,n0                 ; stepped ONE word per frame (3 Sep 2026)
fs_end:
        nop
        rts

; ===========================================================================
; BYPASS: frames untouched -- with no sends there is nothing to do at all
; ===========================================================================
fs_bypass:
        rts
