; ---------------------------------------------------------------------------
; stageprobe5 -- the axes are eliminated; now stage the reverb's SHAPES.
;
; stageprobe4, two tracks, hardware: BOTH instances climbed the ladder audibly
; and nothing froze. That eliminates, for two simultaneous instances: audio
; buffer access, parameter reads, Y traffic to 36 a sample each (72 across the
; pair, double v50's need), and ~450 instructions a sample across the pair.
; The freeze is not a rate. It is a SHAPE -- something the reverb does that
; raw traffic does not. Only four candidates remain, and this build stages
; them onto the scaffold v4 proved, one every ~3 s:
;
;   stage 0   the v4 baseline: 8 Y accesses a sample, nothing audible
;   stage 1   + audio buzz + params (both proven by v4; the ladder readout)
;   stage 2   + 4 READS at v50's tap offsets -- scattered reads at distances
;             481/799/1071/1315 behind the write phase, across the full
;             2048-word lines. v4's traffic was sequential; v50's is not.
;   stage 3   + 4 WRITES at the write phase: the full tank traffic pattern
;   stage 4   + 2 allpass READ-MODIFY-WRITES at v50's offsets (117, 351 in
;             the 1024-word diffuser buffers) with the mpy chain between
;   stage 5   + 2 interpolated DOUBLE-READS (adjacent words, mpy blend) --
;             the modulated-line read shape, fixed offset
;   stage 6   + the offset MODULATED by a block-rate LFO: full v50-style
;             modulated addressing. The LFO phase persists in the Y state
;             block at base+0x3800, which v4 already loads and saves.
;   stage 7+  everything, forever. The count recycles; the buzz never stops.
;
; The Y ramp and the instruction burn from v4 are DROPPED: those axes are
; closed, and dropping them pays for the new stages -- this build runs ~270
; instructions a sample per instance at full load, ~540 across the pair,
; near what v4 proved survivable.
;
; Readout unchanged from v4: buzz from bit 1 of the count, ADDED to the dry,
; -12 dB at stage 1 and 6 dB down per stage to the floor; a click on any tag
; failure. IF TWO TRACKS FREEZE, THE LEVEL YOU LAST HEARD NAMES THE FEATURE:
;
;   -12 dB (loudest)  froze before the shapes: scaffold regression, tell me
;   -18 dB            tap-pattern reads
;   -24 dB            tank writes
;   -30 dB            allpass read-modify-write
;   -36 dB            interpolated double-reads
;   -42 dB / floor    LFO modulation
;   runs forever      none of them individually -- the fault needs the full
;                     engine, and the next bisect is combination, not part
;
; Known readout behaviour, measured with v4: the pitch is the call rate
; (~690 Hz one call a block, ~1.4 kHz two), sequencer trigs re-pitch the buzz
; by setting the split (the trig's landing offset inside the block -- BPM
; dependent, verified 80->2 tones, 100->1, 114->4, 120->1), and the ladder
; replays only after the slot is scrambled (power cycle, effect switch).
; ---------------------------------------------------------------------------

init:
; Identical to stageprobe's init. Reading X:$213 is only valid here, so the base
; is stashed at an address unique to this instance.
        move    x:>$213,r4
        move    r7,a
        asr     #$8,a,a                 ; r7 >> 8; also fills the AGU slot
        move    x:(r4),x0               ; this instance's base
        move    #>$800,y0
        add     y0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m0            ; both fill the AGU slot
        move    x0,y:(r5)
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        rts

proc:
; The A accumulator is the dispatcher's mode flag; stored so the audio stage
; can refuse to write through r0 on a call where r0 is not an audio pointer.
        move    a,x:(r7+$16)

; ---- the counter: tag and count in the one slot, plus the click flag ----
; word = tag | count.  tag = bits 23..17 = $2c0000 (bit 23 clear -- a set sign
; bit would poison A2 through every mask and compare below). count = bits
; 16..0. A wrong tag means the slot was scrambled: restart at zero AND raise
; the click flag. v4 measured zero unprompted clicks on hardware, so a click
; in this build still means what it meant there.
        clr     a
        move    a,x:(r7+$19)            ; click flag, default clear
        move    x:(r7+$83),a
        move    #>$fe0000,x0
        and     x0,a
        move    #>$2c0000,x0
        cmp     x0,a
        beq     tagok
        move    #>$2c0000,a             ; wrong tag: count = 0
        move    a,x:(r7+$83)
        move    #>$1,a
        move    a,x:(r7+$19)            ; and CLICK: the counter was scrambled
tagok:
        move    x:(r7+$83),a
        move    #>$01ffff,x0
        and     x0,a                    ; count
        cmp     x0,a                    ; count == max?
        bne     notmax
        move    #>$1bfff,a              ; recycle inside the top stage: stage
notmax:                                 ; stays 14..15 and bit 1 keeps toggling,
        move    #>$1,x0                 ; so the floor buzz never freezes to DC
        add     x0,a
        move    a,x1                    ; keep the count for the stage and phase
        move    #>$2c0000,x0
        add     x0,a                    ; tag | count
        move    a,x:(r7+$83)
        move    x1,a
        asr     #$d,a,a                 ; stage = count >> 13, 0..15
        move    a,x:(r7+$15)            ; every stage test reads it from here

; ---- the tank phase, derived from the count -----------------------------
; v50 keeps its write phase in $83; here $83 is the counter, so the phase is
; DERIVED: p0 = (count << 4) & $7ff -- 16 a block, the frame count, so the
; access pattern walks the lines the way the reverb's does.
        move    x1,a
        asl     #$4,a,a
        move    #>$7ff,x0
        and     x0,a
        move    a,x:(r7+$1a)

        move    #>$ffffff,m0
        move    #>$ffffff,m5

; ---- recover the base, derive the line and allpass bases ----------------
        move    r7,a
        asr     #$8,a,a
        move    #>$800,y0
        add     y0,a
        move    a,r5
        move    #>$ffffff,m1            ; two instructions before r5 is used
        move    #>$ffffff,m2
        move    y:(r5),x0               ; base
        move    x0,x:(r7+$10)
        move    #>$800,a
        add     x0,a
        move    a,x:(r7+$11)
        move    #>$1000,a
        add     x0,a
        move    a,x:(r7+$12)
        move    #>$1800,a
        add     x0,a
        move    a,x:(r7+$13)
        move    #>$2000,a
        add     x0,a
        move    a,x:(r7+$2c)            ; allpass 0 base (v50's layout)
        move    #>$2400,a
        add     x0,a
        move    a,x:(r7+$2d)            ; allpass 1 base

; ---- the tap offsets, folded with the phase once per block --------------
; q_i = (p0 + (2048 - tap_i)) & $7ff for v50's taps 1567 1249 977 733.
; In the loop each read is then just (q_i + frame) & $7ff + base_i.
        move    x:(r7+$1a),a
        move    #>481,x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    a,x:(r7+$28)
        move    x:(r7+$1a),a
        move    #>799,x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    a,x:(r7+$29)
        move    x:(r7+$1a),a
        move    #>1071,x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    a,x:(r7+$2a)
        move    x:(r7+$1a),a
        move    #>1315,x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    a,x:(r7+$2b)

; ---- the state block, one Y read and one Y write per block --------------
; The loaded word doubles as the LFO phase from stage 6; the save happens
; after the LFO update so the phase persists in OUR Y memory, not in r7.
        move    x:(r7+$10),a
        move    #>$3800,x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    y:(r5),a
        move    a,x:(r7+$14)

; ---- stage 1: the parameter reads, once per block -----------------------
        move    x:(r7+$15),a
        move    #>$1,x0
        cmp     x0,a
        blt     noparm
        move    x:(r6),x0
        move    x0,x:(r7+$20)
        move    x:(r6+$1),x0
        move    x0,x:(r7+$21)
        move    x:(r6+$2),x0
        move    x0,x:(r7+$22)
        move    x:(r6+$4),x0
        move    x0,x:(r7+$23)
        move    x:(r6+$5),x0
        move    x0,x:(r7+$24)
        move    x:(r6+$b),x0
        move    x0,x:(r7+$25)
        move    x:(r6+$d),x0
        move    x0,x:(r7+$26)
        move    x:(r6+$e),x0
        move    x0,x:(r7+$27)
noparm:

; ---- the readout gain: 6 dB down per stage ------------------------------
; A fall-through chain, not a variable-count shift: `do`/`rep` with a zero
; count runs 65536 times on this core.
        move    #>$7fffff,a
        move    x:(r7+$15),b
        move    #>$2,x0
        cmp     x0,b
        blt     gdone
        asr     #$1,a,a
        move    #>$3,x0
        cmp     x0,b
        blt     gdone
        asr     #$1,a,a
        move    #>$4,x0
        cmp     x0,b
        blt     gdone
        asr     #$1,a,a
        move    #>$5,x0
        cmp     x0,b
        blt     gdone
        asr     #$1,a,a
        move    #>$6,x0
        cmp     x0,b
        blt     gdone
        asr     #$1,a,a
        move    #>$7,x0
        cmp     x0,b
        blt     gdone
        asr     #$1,a,a
gdone:
        move    a,x:(r7+$17)            ; ladder gain

; ---- the buzz sample, once per call -------------------------------------
; A square from bit 1 of the count at ladder gain - 12 dB, synthesized, never
; read from input. Also the allpass stage's excitation signal.
        move    x:(r7+$17),a
        asr     #$2,a,a
        move    x:(r7+$83),b
        move    #>$2,x0
        and     x0,b                    ; bit 1 of the count
        tst     b
        beq     bpos
        neg     a
bpos:
        move    a,x:(r7+$18)
        move    x:(r7+$19),b            ; tag-fail click: override the buzz
        tst     b                       ; with one loud block, whatever the
        beq     noclick                 ; stage -- the ladder may be at 0
        move    #>$3fffff,a
        move    a,x:(r7+$18)
noclick:

; ---- the interpolation offsets, and stage 6's LFO -----------------------
; Defaults first: line 1 reads 799 behind, line 2 reads 1071 behind, no
; fraction. Stage 6 overwrites line 1's pair from a triangle LFO whose phase
; is the state word -- v50's modulated-read shape, cut to its essentials.
        move    #>799,a
        move    a,x:(r7+$30)            ; line 1 offset (integer)
        clr     a
        move    a,x:(r7+$31)            ; line 1 fraction
        move    #>1071,a
        move    a,x:(r7+$32)            ; line 2 offset, always fixed
        move    x:(r7+$15),a
        move    #>$6,x0
        cmp     x0,a
        blt     nolfo
        move    x:(r7+$14),a            ; the persistent word IS the phase
        move    #>$2000,x0              ; ~2.7 Hz at one call a block
        add     x0,a
        move    #>$7fffff,x0
        and     x0,a
        move    a1,x0                   ; extract without saturating on A2
        move    x0,x:(r7+$14)           ; persists via the state-block save
        move    x0,a
        move    #>$400000,x0
        sub     x0,a
        abs     a                       ; triangle T, 0 .. $400000
        move    a,x1                    ; T
        asr     #$13,a,a                ; integer offset, 0..8
        move    a,x0
        move    #>799,a
        sub     x0,a
        move    a,x:(r7+$30)            ; 799 - lfo: the modulated offset
        move    x1,a                    ; T again, A2 = 0 because T is positive
        move    #>$07ffff,x0
        and     x0,a
        asl     #$4,a,a                 ; fraction, at most $7ffff0 -> positive
        move    a,x0
        move    x0,x:(r7+$31)
nolfo:

; ---- the state save -----------------------------------------------------
        move    x:(r7+$10),a
        move    #>$3800,x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    x:(r7+$14),a
        move    a,y:(r5)

; ---- the sample loop -----------------------------------------------------
; b restarts at 0 every block; the block phase p0 carries the continuity, so
; every address below advances the way the reverb's do.
        clr     b                       ; b = phase, and nothing below clobbers b
        do      n7,>pend

; ---- stage 0: read all four lines (the v4 baseline) ---------------------
        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$10),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5            ; two instructions before r5 is used
        move    #>$ffffff,m1
        move    y:(r5),a

        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$11),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    y:(r5),a

        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$12),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    y:(r5),a

        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$13),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    y:(r5),a

; ---- stage 0: write all four lines --------------------------------------
        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$10),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    b,a
        move    a,y:(r5)

        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$11),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    b,a
        move    a,y:(r5)

        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$12),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    b,a
        move    a,y:(r5)

        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$13),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    b,a
        move    a,y:(r5)

; ---- stage 1: the audio buzz --------------------------------------------
; v4's audio stage verbatim: buzz ADDED in place, r0 walked with v50's
; idiom. A click forces the write on so a reset is audible at any stage.
        move    x:(r7+$19),a
        tst     a
        bne     doaud                   ; click: force the write on
        move    x:(r7+$15),a
        move    #>$1,x0
        cmp     x0,a
        blt     noaud
doaud:
        move    x:(r7+$16),a
        tst     a
        beq     noaud                   ; r0 is not an audio pointer on this call
        move    #>$1,n0
        move    x:(r7+$18),x0           ; the buzz sample
        move    x:(r0),a
        add     x0,a
        move    a,x:(r0)                ; L + buzz, in place
        move    x:(r0+n0),a
        add     x0,a
        move    a,x:(r0+n0)             ; R + buzz, in place
        move    #>$2,n0
        move    (r0)+n0                 ; advance one stereo frame -- v50 verbatim
noaud:

; ---- stage 2: four reads at the tap offsets -----------------------------
; The tank's READ pattern: four scattered addresses per sample, hundreds of
; words apart, sweeping the full 2048-word lines. v4 never did this; v50
; does it every sample of its life.
        move    x:(r7+$15),a
        move    #>$2,x0
        cmp     x0,a
        blt     ntr
        move    b,a
        move    x:(r7+$28),x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$10),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    y:(r5),a

        move    b,a
        move    x:(r7+$29),x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$11),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    y:(r5),a

        move    b,a
        move    x:(r7+$2a),x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$12),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    y:(r5),a

        move    b,a
        move    x:(r7+$2b),x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$13),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    y:(r5),a
ntr:

; ---- stage 3: four writes at the write phase ----------------------------
; With stage 2 this is the tank's complete traffic: reads far behind, writes
; at the head, every sample, both lines' extremes touched.
        move    x:(r7+$15),a
        move    #>$3,x0
        cmp     x0,a
        blt     ntw
        move    b,a
        move    x:(r7+$1a),x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$10),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    b,a
        move    a,y:(r5)

        move    b,a
        move    x:(r7+$1a),x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$11),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    b,a
        move    a,y:(r5)

        move    b,a
        move    x:(r7+$1a),x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$12),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    b,a
        move    a,y:(r5)

        move    b,a
        move    x:(r7+$1a),x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$13),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    b,a
        move    a,y:(r5)
ntw:

; ---- stage 4: two allpass read-modify-writes ----------------------------
; The diffuser's shape: read d at (phase + offset) mod 1024, v = x + g*d
; through the multiplier, write v back at phase. The excitation x is the
; buzz sample; the output is discarded -- the MEMORY pattern is the test.
        move    x:(r7+$15),a
        move    #>$4,x0
        cmp     x0,a
        blt     nap
        move    b,a
        move    x:(r7+$1a),x0
        add     x0,a
        move    #>117,x0
        add     x0,a
        move    #>$3ff,x0
        and     x0,a
        move    x:(r7+$2c),x0
        add     x0,a
        move    a,r5
        move    #>$400000,y0            ; coefficient, and fills the AGU slot
        move    #>$ffffff,m5
        move    y:(r5),a                ; d
        move    a,x0
        mpy     x0,y0,a
        move    x:(r7+$18),x0
        add     x0,a                    ; v = x + g*d
        move    a,x:(r7+$1c)
        move    b,a
        move    x:(r7+$1a),x0
        add     x0,a
        move    #>$3ff,x0
        and     x0,a
        move    x:(r7+$2c),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$1c),a            ; reload v, fills the AGU slot
        move    #>$ffffff,m5
        move    a,y:(r5)

        move    b,a
        move    x:(r7+$1a),x0
        add     x0,a
        move    #>351,x0
        add     x0,a
        move    #>$3ff,x0
        and     x0,a
        move    x:(r7+$2d),x0
        add     x0,a
        move    a,r5
        move    #>$400000,y0
        move    #>$ffffff,m5
        move    y:(r5),a                ; d
        move    a,x0
        mpy     x0,y0,a
        move    x:(r7+$18),x0
        add     x0,a                    ; v = x + g*d
        move    a,x:(r7+$1c)
        move    b,a
        move    x:(r7+$1a),x0
        add     x0,a
        move    #>$3ff,x0
        and     x0,a
        move    x:(r7+$2d),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$1c),a
        move    #>$ffffff,m5
        move    a,y:(r5)
nap:

; ---- stage 5 (+6): two interpolated double-reads ------------------------
; The modulated line's shape: two reads one word apart, blended by a
; fraction through the multiplier. At stage 5 the offset is fixed; at stage
; 6 line 1's offset and fraction come from the LFO, which is the full v50
; modulated-read pattern. The second read at address-1 may step one word
; below the line base -- that is the previous line's last word, still inside
; this instance's allocation.
        move    x:(r7+$15),a
        move    #>$5,x0
        cmp     x0,a
        blt     nin
        move    b,a
        move    x:(r7+$1a),x0
        add     x0,a
        move    x:(r7+$30),x0           ; line 1 offset, LFO'd at stage 6
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$11),x0
        add     x0,a
        move    a,r5
        move    a,x1                    ; hold the address, fills the AGU slot
        move    #>$ffffff,m5
        move    y:(r5),a                ; d0
        move    a,x:(r7+$1d)
        move    x1,a
        move    #>$1,x0
        sub     x0,a                    ; the adjacent word
        move    a,r5
        move    x:(r7+$31),y1           ; fraction, fills the AGU slot
        move    x:(r7+$1d),x0           ; d0, second fill
        move    y:(r5),a                ; d1
        sub     x0,a
        move    a,x1
        mpy     x1,y1,a                 ; f*(d1-d0)
        move    x:(r7+$1d),x0
        add     x0,a                    ; the interpolated tap, discarded

        move    b,a
        move    x:(r7+$1a),x0
        add     x0,a
        move    x:(r7+$32),x0           ; line 2 offset, always fixed
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$12),x0
        add     x0,a
        move    a,r5
        move    a,x1
        move    #>$ffffff,m5
        move    y:(r5),a                ; d0
        move    a,x:(r7+$1d)
        move    x1,a
        move    #>$1,x0
        sub     x0,a
        move    a,r5
        move    x:(r7+$31),y1
        move    x:(r7+$1d),x0
        move    y:(r5),a                ; d1
        sub     x0,a
        move    a,x1
        mpy     x1,y1,a
        move    x:(r7+$1d),x0
        add     x0,a
nin:

        move    #>$1,x0
        add     x0,b                    ; advance the phase
pend:

out:
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts
