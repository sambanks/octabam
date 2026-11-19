; ---------------------------------------------------------------------------
; VOCODER -- a ten-band channel vocoder after the Roland VP-330
; (modules/vocoder/DESIGN.md; float reference vocoder_ref.py, which holds the
; law in this form).
;
; Insert contract: frames in place at x:(r0)/x:(r0+n0), knobs from r6,
; state in this instance's r7 block. No bus, no buffers, no shared window.
; Uses r3, r4, r5 (m3, m4, m5 linear); r1 is left alone. One allocator slot
; (stock DELAY's mechanism): 20 words of Y for GEND's analysis coefficients.
; Runs on FX2 of tracks 2, 4, 6 and 8 only (r7 0x6500 or 0x6b00): at most two
; per DSP core, which the MKII carries; a dry pass on every other slot, T1 and T5
; included (a core's position 0: see proc).
;
;; ---- the law ------------------------------------------------------------------
;   m = (L + R)/2 (INT) or L (EXT)
;   c = 0.3 saw(pitch) + 0.2 saw(pitch + 12), the two sawtooths on one 24-bit phase (the
;       4' is the phase doubled), polyBLEP, branch-free; WHSP blends it to white noise at
;       the same RMS: c + w (G noise - c). Or R/2 (EXT)
;   pitch: P = q(NOTE) + 12 + 2 B (BEND - 1/2) semitones above C0 (x 2^16), q the scale
;       snap (SCAL, KEY: the scale note at or below), B = 12, 6 or 24 (RANG), P held to
;       C0 .. just under C8, glided per call
;       (GLIDE: P_s += n7 K (P - P_s), 48 bits); inc = OCT[o] 2^r / 2 from x = 4/3 P_s,
;       o = floor(8x), r = frac(8x), 2^r a quintic; 1/(du 2^12) by one division per call.
;       Every step truncates, so vocoder_ref.py reproduces the increment bit for bit
;   each band k: two Chamberlin band-pass sections (f1, then f2, Q 7), each input scaled
;       by q = 1/7 so a section peaks at its input's level. On c they run at the table's
;       f1, f2; on m at f1 A, f2 A, A = 2^-t (t = GEND - 1/2, halved below the centre): the
;       voice is analysed x1.19 .. x0.71 off the synthesis, so every formant comes out scaled by
;       1/A, x0.84 .. x1.41 (GEND)
;   v = (W_k/2) |band_k(m)|;  e = max(v, e (1 - 0.00227)): a peak detector,
;       instant attack and 10 ms release, as the VP-330's diodes; e in 48 bits
;   out = limit(2^8 sum_k e_k band_k(c) + 4 CONS hp6(m/2) + DRY m): the level is the
;       track's AMP
;   de-zipper: GEND, WHSP, DRY and CONS follow their knobs by s += n7 K (T - s) per call,
;       rounded, K for 8 ms, so a scene jump or a fast crossfader lands over a few ms
;   hp6: three Chamberlin high-pass sections at 4 kHz (Q 0.518, 0.707, 1.932),
;       q/2 stored and applied twice (q is above 1)
;
; ---- the P table (the manifest's ptable, 166 words) --------------------------
;   +0   BAND[10] x {W/2, f1, f2}: the synthesis side, as the band loop reads it
;   +30  OCT[8]   the increment of C(o), x 2 (a cycle is 2^24)
;   +38  GLD[5]   GLIDE's K per sample: 8 (OFF), 30, 80, 200, 500 ms
;   +43  RNG[3]   BEND's R: 3/16 (+-12 semitones), 3/32 (+-6), 3/8 (+-24)
;   +46  DOWN[10][12] per scale and degree above KEY, the semitones to the scale note at
;                 or below, x 2^16 (CHRO all 0)
; ---- the Y slot: this instance's allocator base (read at init), 20 words ------
;   per band k: f1 A, f2 A, written every call before the band loop
;
; ---- r7 slots ---------------------------------------------------------------
; per sample: $00 q m   $01 q c   $02 the band sum   $04 m
;             $17 this band's envelope
; persistent: $05 the carrier phase   $06..$0b hp6: three sections of (low, band)
;             $1b..$7e ten band blocks of 10, band k at $1b + 10k:
;               +0 +1 m section 1 (low, band)   +2 +3 m section 2
;               +4 +5 the envelope (high, low)  +6 +7 c section 1   +8 +9 c section 2
;             $7f WHSP's generator   $80 $81 P_s (high, low)
;             $15 0 before the first call; 1 the last call did the per-call work, 2 it skipped it
;             $10 the Y slot: the allocator base + 256 (position 1 Y:0x8100; position 3
;                 Y:0x34100 on core 0, 0x3c100 on core 1, in the shared window)
;             $82 GEND, smoothed: the word last written to the Y slot   $83 the P_s inc was
;             last made for (both -1 after init: the first call computes)
;             $03 WHSP   $0e CONS   $0f DRY: smoothed per call (0 after init)
;             $17 the de-zipper's k between the knob reads (the band loop's scratch after)
; per block:  $0c inc   $0d 1/(du 2^12)   $11 MODE
;             $12 the table base   $13 1/(du 2^12)/2   $14 0.00227   $16 q
;             $18 $19 $1a hp6's q/2
; Scratch sits low so its moves take one word; the band blocks are walked
; with (r5)+, so the section arithmetic carries its loads and stores as
; parallel moves.
;
; Every multiply is one of the valid signed pairs (x0,y1  y0,x0  x1,x0  y1,x1
; x1,y0  x0,x0). Every Tcc reads the arithmetic directly above it, with only
; moves between.
; ---------------------------------------------------------------------------

init:
        move    #>$ffffff,m5
        move    r7,r5
        clr     a
        do      #$82,>norep_vc_01  ; every slot, $00..$81
        move    a,x:(r5)+
norep_vc_01:
        move    #>$2a5f31,x0            ; WHSP's generator: its seed
        move    x0,x:(r7+$7f)
        move    #>$ffffff,x0            ; nothing cached yet: no GEND or P_s can be -1
        move    x0,x:(r7+$82)
        move    x0,x:(r7+$83)
        move    x:>$213,r4              ; this instance's base-table entry (valid at init only)
        move    x:(r4),a
        add     #>$000100,a             ; 256 words in: clear of the slot's first word (a probe
        move    a,x:(r7+$10)            ; at 0x30000 itself buzzed, docs/firmware/DSP.md)
        rts

proc:
; ---- TWO PER CORE, BUILT IN: FX2 positions 1 and 3 only --------------------------
; Three VOCODERs on one DSP core overran Ignorato's MKII (a glitch, then a stall
; until a reboot; two ran safely), so it runs at two positions per core and is an
; exact dry pass everywhere else. Not position 0 (T1, T5). Measured: on Ignorato's
; MKII VOCODER on T1 put left-only click bursts into the main out at one phase of
; the pattern, worst at trigs; on T2 and T3 it ran clean (5 Oct 2026). Inferred:
; at position 0 the ColdFire's pull of the previous frame's read-back must finish
; before T1's FX2 output is copied over it (docs/contributing/FAILURE_MODES.md,
; "Junk on main R ... T1 with BusDelay"; that was main R, 16-24 samples). T5 is
; excluded by analogy, unmeasured.
; So it runs at r7 = 0x6500 and 0x6b00 (T2, T4 on core 1; T6, T8 on core 0): the even
; tracks, so a NEIGHBOR machine there hands it the odd track's audio before it. Position
; 2 (T3, T7) is now dry, though VOCODER ran clean there on the unit (5 Oct 2026); position
; 3 is checked in the emulator only. r7 per slot measured under the port: modules/send/README.md, "An FX1 slot is not
; a client".
        move    r7,a
        move    #>$6500,x0
        cmp     x0,a
        beq     vc_run
        move    #>$6b00,x0
        cmp     x0,a
        bne     vc_end                  ; not T2/T4/T6/T8's FX2: dry, nothing written
vc_run:
; ---- per block: the knobs ---------------------------------------------------------
        move    #>$ffffff,m5
        move    #>$ffffff,m4            ; the (r4)+ table walk: linear, whatever ran before
        move    #>$fab1e0,r4            ; the table base
        move    r4,x:(r7+$12)
        move    #>$ffffff,m3
; ---- pitch: P = (q(NOTE) + 12) 2^16 + R y, y = BEND - 1/2: semitones above C0, x 2^16 ---
;      q(n) = n - DOWN[SCAL][(n + 12 - KEY) mod 12]: the nearest note of the scale at or
;      below n (CHRO: n itself); R = 3/16, 3/32 or 3/8 (RANG: +-12, +-6, +-24 semitones).
;      P is held to [0, 96 x 2^16): C0 (16.35 Hz, 1/du's Q23 floor) up to just under C8
        move    x:(r6+$0),a             ; NOTE: the step in bits 16 and up
        and     #>$7f0000,a
        move    #>$3c0000,x0            ; 60, C6
        cmp     x0,a
        tgt     x0,a
        move    a1,y1                   ; n
        move    x:(r6+$e),b             ; KEY, slot 10: the knob field of $e
        and     #>$7f0000,b
        move    #>$0b0000,x0            ; 11, B
        cmp     x0,b
        tgt     x0,b
        move    b1,x0
        add     #>$0c0000,a
        sub     x0,a                    ; d = n + 12 - KEY: 1 .. 72
        move    #>$300000,x0            ; d mod 12: less 48, 24 and 12 where they go
        move    a,b
        sub     x0,b
        tpl     b,a
        move    #>$180000,x0
        move    a,b
        sub     x0,b
        tpl     b,a
        move    #>$0c0000,x0
        move    a,b
        sub     x0,b
        tpl     b,a                     ; the degree above KEY, 0 .. 11
        move    a1,x1
        move    x:(r6+$c),b             ; SCAL, slot 7: the companion field of $c (bits 8-15)
        and     #>$007f00,b
        move    #>$000900,x0            ; 9, BLUE
        cmp     x0,b
        tgt     x0,b
        asl     #$8,b,b                 ; s
        move    b1,x0
        asl     b
        add     x0,b                    ; 3 s
        asl     #$2,b,b                 ; 12 s
        add     x1,b
        asr     #$10,b,b
        add     #>$00002e,b             ; + 46, DOWN
        move    b1,n4
        move    p:(r4+n4),x0            ; DOWN[s][degree]: 0 .. 2 semitones, x 2^16
        move    y1,a
        sub     x0,a                    ; q(n): -2 .. 60
        add     #>$0c0000,a             ; + 12: C1 is 12 semitones above C0
        move    a1,x1
        move    x:(r6+$d),b             ; RANG, slot 9: the companion field of $d (bits 8-15)
        and     #>$007f00,b
        move    #>$000200,x0            ; 2, +-24
        cmp     x0,b
        tgt     x0,b
        asr     #$8,b,b
        add     #>$00002b,b             ; + 43, RNG
        move    b1,n4
        move    x:(r6+$1),a             ; BEND: bipolar
        and     #>$7f0000,a
        sub     #>$400000,a
        move    a,y0                    ; y
        move    p:(r4+n4),x0            ; R: 3/16, 3/32 or 3/8
        mpy     y0,x0,a                 ; floor(R y)
        add     x1,a
        clr     b
        tst     a
        tmi     b,a                     ; under C0: C0
        move    #>$5fffff,x0            ; just under C8 (BEND +63 at C6 is 95.6 semitones)
        cmp     x0,a
        tgt     x0,a
        move    a1,y1                   ; P
; ---- GLIDE: P_s += (n7 K) (P - P_s), 48 bits; the first call takes P as it is -------------
        move    x:(r7+$15),a            ; primed?
        tst     a
        bne     vc_glide
        move    y1,x:(r7+$80)           ; P_s = P
        clr     a
        move    a,x:(r7+$81)
        move    #>$000002,x0            ; 2: the next call does the per-call work
        move    x0,x:(r7+$15)
vc_glide:
        move    x:(r6+$d),a             ; GLIDE, slot 8: OFF (8 ms), 30, 80, 200, 500 ms
        and     #>$7f0000,a
        asr     #$10,a,a
        move    #>$000004,x0
        cmp     x0,a
        tgt     x0,a
        add     #>$000026,a             ; + 38, GLD
        move    a1,n4
        move    n7,y0                   ; the call's frame count
        move    p:(r4+n4),x0            ; K
        mpy     y0,x0,a
        asr     a
        move    a0,x0                   ; k = n7 K
        move    x:(r7+$80),a            ; P_s, high
        move    x:(r7+$81),a0           ; low
        move    y1,b                    ; P
        move    a1,y0
        sub     y0,b                    ; d = P - P_s
        move    b,y0
        mac     y0,x0,a                 ; P_s += 2 d k
        move    a1,x:(r7+$80)
        move    a0,x:(r7+$81)
; ---- the de-zipper's k = n7 K, K for 8 ms (GLDE OFF's): GEND, WHSP, DRY and CONS follow
;      their knobs by s += k (T - s), rounded, once a call (vocoder_law.dz_step)
        move    a1,y1                   ; (P_s, for below)
        move    n7,y0
        move    #>$005ce1,x0            ; K, 2^23 / (FS 8 ms)
        mpy     y0,x0,b
        asr     b
        move    b0,x:(r7+$17)           ; k (the slot is the band loop's scratch: free here)
        move    y1,a
; ---- inc and 1/du only when P_s has moved: the per-call work stays small on a settled pitch
;      (T1 is called twice a frame; on the unit the per-call cost of OCTABAM13 clicked there)
        move    a1,y0                   ; P_s
; ---- a 1-sample call does none of the per-call work below if the call before did it: T1 is
;      run as a 1-sample call then a 15-sample one each frame, and on the unit T1 glitched at
;      every NOTE change while that short call ran long (OCTABAM18; T2 was clean). Never twice
;      in a row, so a run of 1-sample calls still updates every other call. $15: 1 worked last
;      call, 2 skipped it (or primed): work now.
        move    x:(r7+$15),b
        move    #>$000001,x0
        cmp     x0,b
        bne     vc_long
        move    n7,b
        cmp     x0,b
        bne     vc_long
        move    #>$000002,x1
        move    x1,x:(r7+$15)
        bra     vc_gdone                ; inc, 1/du and the Y slot stand as they are
vc_long:
        move    x0,x:(r7+$15)
        move    x:(r7+$83),b
        cmp     y0,b
        beq     vc_pdone
        move    y0,x:(r7+$83)
; ---- inc = OCT[o] 2^r / 2, x = 4/3 P_s (octaves / 8), o = floor(8x), r = frac(8x) -------------
        move    #>$2aaaab,x0            ; 1/3
        mpy     y0,x0,a
        add     y0,a                    ; x
        move    a1,x1
        move    x1,b
        asr     #$14,b,b                ; o
        move    x1,a                    ; (a0 cleared)
        asl     #$3,a,a
        and     #>$7fffff,a
        move    a1,y0                   ; r
        move    #>$001f0d,x0            ; 2^r / 2: Horner, each step truncated
        move    #>$009293,a
        mac     y0,x0,a
        move    a,x0
        move    #>$039344,a
        mac     y0,x0,a
        move    a,x0
        move    #>$0f5e77,a
        mac     y0,x0,a
        move    a,x0
        move    #>$2c5ca5,a
        mac     y0,x0,a
        move    a,x0
        move    #>$400000,a
        mac     y0,x0,a
        move    a,x0                    ; 2^r / 2
        add     #>$00001e,b             ; + 30, OCT
        move    b1,n4
        move    p:(r4+n4),y0            ; OCT[o]: the increment of C(o), x 2
        mpy     y0,x0,a
        move    a1,x:(r7+$c)            ; inc
; ---- 1/(du 2^12) = floor(2^35 / inc): a 48-by-24 division, undoubled ----------------------------
        move    a1,x0
        clr     a
        move    #>$001000,a1            ; 2^36 (a2 stays 0)
        andi    #$fe,ccr
        do      #24,>norep_vc_02
        div     x0,a
norep_vc_02:
        move    a0,x:(r7+$d)            ; idt
        move    a0,b
        asr     b
        move    b1,x:(r7+$13)           ; idt / 2, for the 4'
vc_pdone:
; ---- GEND: the analysis pairs at f x A, A = 2^-t, t = y (y >= 0) or y/2 (y < 0): formants
;      x0.84 (-64, -3 semitones) .. x1 .. x1.41 (+63, +6), into this instance's Y slot.
;      GEND is smoothed first; the coefficients are rewritten only when the smoothed word moved
        move    x:(r6+$2),a             ; GEND: bipolar
        and     #>$7f0000,a             ; T
        move    a1,y1
        move    x:(r7+$82),b            ; s: the word the Y slot was last written for (-1 after init)
        sub     b,a
        move    a,y0                    ; T - s
        move    x:(r7+$17),x1           ; k
        move    b,a
        macr    x1,y0,a                 ; s + k (T - s), rounded
        tst     b
        tmi     y1,a                    ; the first call (s = -1) takes T as it is
        cmp     b,a
        beq     vc_gdone                ; unmoved: the 20 coefficients stand
        move    a1,x:(r7+$82)
        sub     #>$400000,a
        move    a,x0                    ; y
        asr     a                       ; y/2: below the centre each step is half as large
        tpl     x0,a                    ; y >= 0: y itself
        move    a,y0                    ; t
        move    #>$fcba91,x0            ; A/2: a cubic, Horner, truncated
        move    #>$0f679c,a
        mac     y0,x0,a
        move    a,x0
        move    #>$d39f80,a
        mac     y0,x0,a
        move    a,x0
        move    #>$400000,a
        mac     y0,x0,a
        move    a,y1                    ; A/2
        move    x:(r7+$10),r3           ; the Y slot
        move    x:(r7+$12),r4           ; BAND {W/2, f1, f2}
        do      #10,>vc_gend
        move    (r4)+                   ; (W/2)
        move    p:(r4)+,x0              ; f1
        mpy     x0,y1,a
        asl     a                       ; f1 A (limited at the top: the 6 kHz pair at x1.19)
        move    a,y:(r3)+
        move    p:(r4)+,x0              ; f2
        mpy     x0,y1,a
        asl     a
        move    a,y:(r3)+
vc_gend:
vc_gdone:
        move    x:(r7+$17),x1           ; k
        move    x:(r6+$5),a             ; CONS, slot 5: value/128
        and     #>$7f0000,a
        move    x:(r7+$e),b             ; s
        sub     b,a
        move    a,y0
        move    b,a
        macr    x1,y0,a
        move    a1,x:(r7+$e)
        move    x:(r6+$4),a             ; DRY, slot 4: value/128
        and     #>$7f0000,a
        move    x:(r7+$f),b
        sub     b,a
        move    a,y0
        move    b,a
        macr    x1,y0,a
        move    a1,x:(r7+$f)
        move    x:(r6+$3),a             ; WHSP, slot 3: value/128
        and     #>$7f0000,a
        move    x:(r7+$3),b
        sub     b,a
        move    a,y0
        move    b,a
        macr    x1,y0,a
        move    a1,x:(r7+$3)
        move    x:(r6+$c),a             ; MODE, slot 6: 0 INT, 1 EXT
        and     #>$7f0000,a
        asr     #$10,a,a
        move    a1,x:(r7+$11)
        move    #>$004a38,x0            ; 0.00227: the 10 ms release
        move    x0,x:(r7+$14)
        move    #>$124925,x0            ; q = 1/7
        move    x0,x:(r7+$16)
        move    #>$7ba5c9,x0            ; hp6's q/2: Q 0.518, 0.707, 1.932
        move    x0,x:(r7+$18)
        move    #>$5a82b2,x0
        move    x0,x:(r7+$19)
        move    #>$2120c5,x0
        move    x0,x:(r7+$1a)
        move    #$1,n0

        do      n7,>vc_end
; ---- the modulator: (L + R)/2, or L with MODE EXT -----------------------------------
        move    x:(r0),a                ; L
        move    x:(r0+n0),b             ; R
        add     a,b       a,x1          ; L + R;  x1 = L
        asr     b                       ; (L + R)/2
        move    x:(r7+$11),a
        tst     a
        tne     x1,b                    ; EXT -> L
        move    b,x:(r7+$4)             ; m
        move    b,y0
        move    x:(r7+$16),x1           ; q
        mpyr    x1,y0,a
        move    a,x:(r7)                ; q m
; ---- the carrier: two polyBLEP sawtooths on one phase, or R/2 ----------------------
        move    #>$000800,y0            ; 2^-12, the cap, for both calls
        move    x:(r7+$5),b             ; s, the 8' phase
        move    x:(r7+$d),y1            ; 1/(du 2^12)
        bsr     vc_blep                 ; x0 = the 8' sawtooth
        move    #>$266666,y1            ; 0.3
        mpy     x0,y1,a
        move    a,x:(r7+$1)             ; (the 8' part, for a moment)
        move    x:(r7+$5),b
        asl     #$1,b,b
        move    b1,x0                   ; the 4' phase: doubled, wrapped
        move    x0,b
        move    x:(r7+$13),y1           ; du is twice as large: 1/(du 2^12) halved
        bsr     vc_blep                 ; x0 = the 4' sawtooth
        move    #>$19999a,y1            ; 0.2
        move    x:(r7+$1),a
        mac     x0,y1,a                 ; 0.3 saw8 + 0.2 saw4
; WHSP: c = mix + w (G noise - mix); noise: x' = A x + C mod 2^24, the sample x signed
        move    x:(r7+$7f),x0
        move    #>$19660d,y1            ; A
        mpy     x0,y1,b
        asr     b                       ; x A exactly: its low 24 bits in b0
        move    b0,y0
        move    y0,b
        add     #>$6ef35f,b             ; + C (b1 wraps when stored unlimited)
        move    b1,x:(r7+$7f)
        move    b1,x0                   ; the noise sample
        move    #>$287a27,y1            ; G: the sawtooth mix's RMS over uniform noise's
        mpy     x0,y1,b
        sub     a,b
        move    b,x0
        move    x:(r7+$3),y1            ; w
        mac     x0,y1,a
        move    x:(r0+n0),b             ; R
        asr     #$1,b,b
        move    b,x1                    ; R/2
        move    x:(r7+$11),b
        tst     b
        tne     x1,a                    ; EXT -> R/2
        move    a,y0
        move    x:(r7+$16),x1           ; q
        mpyr    x1,y0,a
        move    a,x:(r7+$1)             ; q c
        move    x:(r7+$5),a             ; the phase advances
        move    x:(r7+$c),x0
        add     x0,a
        move    a1,x:(r7+$5)            ; (a1 is not limited: it wraps)
; ---- the ten bands ---------------------------------------------------------------------
        clr     a
        move    a,x:(r7+$2)
        move    x:(r7+$12),r4           ; BAND {W/2, f1, f2}: the synthesis side
        move    x:(r7+$10),r3           ; the analysis f1 A, f2 A, written this block
        lua     (r7+$1b),r5             ; $1b, band 0
        do      #10,>vc_bend
; m, section 1 (f1 A); x1 = q in every section
        move    y:(r3)+,x0              ; f1 A
        move    x:(r5)+,a               ; low
        move    x:(r5)-,y1              ; band
        macr    x0,y1,a   x:(r7),b      ; low += f band;  b = q m
        sub     a,b       a,x:(r5)+     ; q m - low
        macr    -y1,x1,b                ; hp = q m - low - q band
        tfr     y1,a      b,y0
        macr    y0,x0,a                 ; band += f hp
        move    a,y0
        mpy     x1,y0,b   a,x:(r5)+     ; section 2's input, q band
; m, section 2 (f2 A)
        move    y:(r3)+,x0              ; f2 A
        move    x:(r5)+,a
        move    x:(r5)-,y1
        macr    x0,y1,a
        sub     a,b       a,x:(r5)+
        macr    -y1,x1,b
        tfr     y1,a      b,y0
        macr    y0,x0,a                 ; the m band
        abs     a         a,x:(r5)+     ; |m band| (the signed band is stored)
; the envelope: e = max((W/2) |m band|, e (1 - 0.00227)), 48 bits
        move    a,y0
        move    p:(r4)+,x0              ; W/2
        mpy     y0,x0,b                 ; v
        move    x:(r5)+,a               ; e, high word
        move    x:(r5)-,a0              ; e, low word
        move    a1,x0
        move    x:(r7+$14),y1           ; 0.00227
        mac     -x0,y1,a                ; e (1 - 0.00227)
        cmp     b,a
        tlt     b,a                     ; below v -> v (the instant attack)
        move    a1,x:(r5)+
        move    a0,x:(r5)+
        move    a,x:(r7+$17)            ; e, for the VCA
; c, section 1 (f1)
        move    p:(r4)+,x0              ; f1
        move    x:(r5)+,a
        move    x:(r5)-,y1
        move    x:(r7+$1),b             ; q c
        macr    x0,y1,a
        sub     a,b       a,x:(r5)+
        macr    -y1,x1,b
        tfr     y1,a      b,y0
        macr    y0,x0,a
        move    a,y0
        mpy     x1,y0,b   a,x:(r5)+
; c, section 2 (f2)
        move    p:(r4)+,x0              ; f2
        move    x:(r5)+,a
        move    x:(r5)-,y1
        macr    x0,y1,a
        sub     a,b       a,x:(r5)+
        macr    -y1,x1,b
        tfr     y1,a      b,y0
        macr    y0,x0,a                 ; the c band
        move    a,x:(r5)+               ; (r5 -> the next band)
; the VCA: the band sum += e (c band), rounded to 24 bits (about 62 dB under
; the vocoded signal, README and DESIGN; two moves a band fewer than 48)
        move    a,y0
        move    x:(r7+$17),x0           ; e
        move    x:(r7+$2),b
        macr    y0,x0,b
        move    b,x:(r7+$2)
vc_bend:
; ---- hp6: m/2 through three high-pass sections at 4 kHz, states walked by r5 -------------
        lua     (r7+$6),r5              ; $06 (first: its wait overlaps the next three)
        move    x:(r7+$4),b
        asr     #$1,b,b                 ; m/2
        move    #>$47f6e6,x0            ; f, 4 kHz
        move    x:(r5)+,a               ; section 1: low
        move    x:(r5)-,y1              ; band
        macr    x0,y1,a
        sub     a,b       a,x:(r5)+
        move    x:(r7+$18),x1           ; q/2, Q 0.518
        macr    -y1,x1,b
        macr    -y1,x1,b
        tfr     y1,a      b,y0
        macr    y0,x0,a
        move    a,x:(r5)+
        move    x:(r5)+,a               ; section 2
        move    x:(r5)-,y1
        macr    x0,y1,a
        sub     a,b       a,x:(r5)+
        move    x:(r7+$19),x1           ; q/2, Q 0.707
        macr    -y1,x1,b
        macr    -y1,x1,b
        tfr     y1,a      b,y0
        macr    y0,x0,a
        move    a,x:(r5)+
        move    x:(r5)+,a               ; section 3
        move    x:(r5)-,y1
        macr    x0,y1,a
        sub     a,b       a,x:(r5)+
        move    x:(r7+$1a),x1           ; q/2, Q 1.932
        macr    -y1,x1,b
        macr    -y1,x1,b
        tfr     y1,a      b,y0
        macr    y0,x0,a
        move    a,x:(r5)+
; ---- out = limit(2^8 sum + 4 CONS hp + DRY m) -------------------------------------
        move    x:(r7+$e),x0            ; CONS
        mpy     y0,x0,b                 ; hp CONS
        asl     #$2,b,b
        move    x:(r7+$4),x0            ; m
        move    x:(r7+$f),y1            ; DRY
        mac     x0,y1,b
        move    x:(r7+$2),a
        asl     #$8,a,a                 ; 2^8, the make-up gain
        add     a,b
        move    b,x:(r0)+               ; (limited; the level is the track's AMP)
        move    b,x:(r0)+
vc_end:
        nop
        rts

; ---- x0 = the polyBLEP sawtooth at phase b; y1 = 1/(du 2^12), y0 = 2^-12; uses a, b, x0, x1 --
; corr = (1 - min(u/du, 1))^2 - (1 - min((1 - u)/du, 1))^2, u = s/2 + 1/2
vc_blep:
        move    b,x1                    ; s
        asr     #$1,b,b
        add     #>$400000,b             ; u
        move    #>$7fffff,a
        sub     b,a                     ; 1 - u
        move    a,x0
        mpy     x0,y1,a                 ; (1 - u)/(du 2^11)
        cmp     y0,a
        tgt     y0,a                    ; min(., 2^-12)
        asl     #$c,a,a
        move    a,x0                    ; t_b (1.0 limited)
        move    #>$7fffff,a
        sub     x0,a
        move    a,x0
        mpyr    x0,x0,a                 ; (1 - t_b)^2
        move    a,x0
        move    x1,a
        sub     x0,a                    ; s - (1 - t_b)^2
        move    a,x1
        move    b,x0                    ; u
        mpy     x0,y1,a                 ; u/(du 2^11)
        cmp     y0,a
        tgt     y0,a
        asl     #$c,a,a
        move    a,x0                    ; t_a
        move    #>$7fffff,a
        sub     x0,a
        move    a,x0
        mpyr    x0,x0,a                 ; (1 - t_a)^2
        add     x1,a
        move    a,x0                    ; (limited)
        rts
