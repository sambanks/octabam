; ---------------------------------------------------------------------------
; stageprobe8 -- v7 with ONE constant changed: the engine starts IMMEDIATELY.
;
; v7's hardware result: v50's entire engine, verbatim, ran on two tracks and
; did not freeze -- knob-responsive, wet path verified in the emulator. The
; engine is innocent. But v7's ladder held the engine silent for the first
; ~6 seconds, which means it slept through the ENABLE TRANSITION -- and the
; original symptom was always "freezes THE MOMENT it is enabled on a second
; track". The moment. Every freezing build engaged instantly; every
; surviving probe started seconds late.
;
; So: the engine gate's stage threshold drops from 2 to 0. The engine runs
; from the very first proc call after enable, straight through whatever the
; host does while wiring the effect in -- the crossfade, the split churn,
; the init storm. Nothing else changes; the buzz still arrives at stage 1
; and drops at stage 2 as the liveness readout.
;
;   freezes the moment track 2 is enabled  ->  FOUND IT. The fault is
;       running the engine during the enable window, and the fix is a
;       warm-up guard: stay dry for the first ~64 blocks after init.
;       v9 is v50 plus that guard, no buzz, no ladder -- the reverb.
;   still no freeze  ->  the enable window is innocent too, and the
;       remaining deltas are the buzz input, the r0 stash/restore, the
;       derived-vs-persisted phase, and the entry head. One flash each.
;
; Below this line the file is stageprobe7 verbatim, one constant excepted.
; ---------------------------------------------------------------------------
;
; The ladder results, all on hardware, all this day: v4 eliminated the RATES
; (audio, params, Y bandwidth, cycles; two tracks). v5 eliminated the SHAPES
; (tap reads, tank write-behind, allpass RMW, modulated interpolated reads;
; eight tracks, combined). v6 eliminated the REGISTER IDIOMS (carried (r1)+
; pointer, dead n writes, X dataflow density, feedback at the carried phase;
; no freeze). Nothing the reverb is MADE OF freezes the machine.
;
; The one untested thing left is the reverb ITSELF: v50's exact instruction
; stream. This build carries it verbatim -- the whole engine, diffuser to
; width matrix -- on a minimal ladder scaffold:
;
;   stage 0   nothing. Silence for ~3 s proves the vehicle.
;   stage 1   the buzz, -12 dB. The scaffold's audio path, proven.
;   stage 2+  buzz drops to -18 dB and V50'S ENTIRE ENGINE SWITCHES ON.
;             The buzz feeds it, so its reverb tail becomes audible --
;             a ringing wash behind the tone means the engine is alive.
;
; Four surgical diffs from reverb50.asm, none inside the sample loop:
;   * the `tst a` head is replaced by the scaffold's gate (stage>=2 and the
;     stored mode flag), and `dry:` becomes the scaffold epilogue
;   * r0 is saved at entry and restored before the engine, because the
;     scaffold's buzz loop walks it first
;   * the engine's two reads of the phase in $83 read the DERIVED phase in
;     $1a instead ($83 is the ladder counter; the phase is count<<4 masked)
;   * the phase save at the end lands in scratch -- the phase is derived,
;     not stored
;
; The scaffold's control slots ($15..$1a, $32) are all inside the engine's
; scratch map and get freely clobbered by it -- BY DESIGN. Everything is
; re-derived from $83 and r7 at the top of every call; the engine runs
; strictly after the last scaffold read. Only $83 must persist, and only
; the engine's state block (base+0x3800, 5 words, its own) persists in Y.
;
; WHAT TWO TRACKS MEAN:
;   * freezes shortly after the second track's stage 2 (~3-6 s in): the
;     freeze is reproduced ON INSTRUMENT, inside a known-good vehicle, and
;     the difference between this and the surviving v6 is nothing but
;     v50's exact code. v8 bisects the engine body itself, on the ladder.
;   * runs, with a reverb tail on the buzz: the engine is INNOCENT in this
;     vehicle, and the freeze lives in what was AROUND it in the real
;     build -- v50's own entry/init/dispatch context. That would be the
;     first genuinely new place to look in fifty builds.
; ---------------------------------------------------------------------------

init:
; Identical to v50's init: stash the base at an address unique to this
; instance, readable later without X:$213.
        move    x:>$213,r4
        move    r7,a
        asr     #$8,a,a                 ; r7 >> 8; also fills the AGU slot
        move    x:(r4),x0               ; this instance's buffer base
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
; Save the mode flag, then r0 -- the buzz loop walks r0, the engine needs it
; back. $32 is engine scratch, but the engine restores r0 from it before its
; own first write to it.
        move    a,x:(r7+$16)
        move    r0,a
        move    a,x:(r7+$32)

; ---- the counter: tag and count in the one slot, plus the click flag ----
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
        move    #>$1bfff,a              ; recycle inside the top stage
notmax:
        move    #>$1,x0
        add     x0,a
        move    a,x1
        move    #>$2c0000,x0
        add     x0,a                    ; tag | count
        move    a,x:(r7+$83)
        move    x1,a
        asr     #$d,a,a                 ; stage = count >> 13
        move    a,x:(r7+$15)

; ---- the engine's phase, derived from the count -------------------------
        move    x1,a
        asl     #$4,a,a
        move    #>$7ff,x0
        and     x0,a
        move    a,x:(r7+$1a)

; ---- the readout gain: -12 dB at stage 1, -18 dB once the engine runs ---
        move    #>$200000,a             ; -12 dB
        move    x:(r7+$15),b
        move    #>$2,x0
        cmp     x0,b
        blt     gdone
        asr     #$1,a,a                 ; -18 dB from stage 2 on
gdone:
        move    x:(r7+$83),b
        move    #>$2,x0
        and     x0,b                    ; bit 1 of the count
        tst     b
        beq     bpos
        neg     a
bpos:
        move    a,x:(r7+$18)
        move    x:(r7+$19),b            ; tag-fail click overrides the buzz
        tst     b
        beq     noclick
        move    #>$3fffff,a
        move    a,x:(r7+$18)
noclick:

; ---- stage 1: the buzz, the scaffold's own loop -------------------------
        move    x:(r7+$19),a
        tst     a
        bne     dobz                    ; click: force the write on
        move    x:(r7+$15),a
        move    #>$1,x0
        cmp     x0,a
        blt     nobz
dobz:
        move    x:(r7+$16),a
        tst     a
        beq     nobz                    ; r0 is not an audio pointer on this call
        do      n7,>bzend
        move    #>$1,n0
        move    x:(r7+$18),x0           ; the buzz sample
        move    x:(r0),a
        add     x0,a
        move    a,x:(r0)                ; L + buzz, in place
        move    x:(r0+n0),a
        add     x0,a
        move    a,x:(r0+n0)             ; R + buzz, in place
        move    #>$2,n0
        move    (r0)+n0                 ; advance one stereo frame
bzend:
nobz:

; ---- THE ENGINE, from the FIRST call. reverb50.asm from here, verbatim --
; THE one change from v7: the threshold is 0, so blt never takes and the
; engine runs through the enable window instead of sleeping past it.
        move    x:(r7+$15),a
        move    #>$0,x0
        cmp     x0,a
        blt     engskip
        move    x:(r7+$16),a
        tst     a
        beq     engskip                 ; the engine only runs the audio call
        move    x:(r7+$32),r0           ; the block start again -- the buzz
                                        ; loop walked r0. No fill needed: its
                                        ; first use is the mono sum, hundreds
                                        ; of instructions away

; ---- this instance's buffer base ----------------------------------------
        move    r7,a
        move    #>$ffffff,m0
        asr     #$8,a,a
        move    #>$800,y0
        add     y0,a
        move    a,r5
        move    #>$ffffff,m1            ; both fill the AGU slot
        move    #>$ffffff,m5
        move    y:(r5),x0               ; the base init stashed for us
        move    x0,x:(r7+$31)

; ---- refuse to run on a slot that cannot hold the layout -----------------
        move    x:(r7+$31),b
        move    #>$4000,y0
        cmp     y0,b
        blt     engskip
        move    #>$8801,y0
        cmp     y0,b
        bge     engskip

; ---- every buffer base, derived once per block --------------------------
        move    #>$2000,a
        add     x0,a
        move    a,x:(r7+$32)
        move    #>$2400,a
        add     x0,a
        move    a,x:(r7+$33)
        move    #>$2800,a
        add     x0,a
        move    a,x:(r7+$34)
        move    #>$2c00,a
        add     x0,a
        move    a,x:(r7+$35)
        move    #>$800,a
        add     x0,a
        move    a,x:(r7+$36)
        move    #>$1000,a
        add     x0,a
        move    a,x:(r7+$37)
        move    #>$3000,a
        add     x0,a
        move    a,x:(r7+$38)
        move    #>$0,a
        add     x0,a
        move    a,x:(r7+$10)            ; line 0 base
        move    #>$800,a
        add     x0,a
        move    a,x:(r7+$11)            ; line 1 base
        move    #>$1000,a
        add     x0,a
        move    a,x:(r7+$12)            ; line 2 base
        move    #>$1800,a
        add     x0,a
        move    a,x:(r7+$13)            ; line 3 base

; ---- per-block: load the state that cannot be derived -------------------
        move    #>$3800,a
        add     x0,a
        move    a,x:(r7+$3f)            ; keep the address for the save
        move    a,r5
        move    #>$ffffff,m5            ; linear for the walk
        move    x:(r7+$31),x0           ; base again; fills the AGU slot
        move    y:(r5)+,a
        move    a,x:(r7+$3e)
        move    y:(r5)+,a
        move    a,x:(r7+$3a)
        move    y:(r5)+,a
        move    a,x:(r7+$3b)
        move    y:(r5)+,a
        move    a,x:(r7+$3c)
        move    y:(r5)+,a
        move    a,x:(r7+$3d)

; ---- rebuild the four delay pointers from the phase ----------------------
; DIFF: the phase is the scaffold's derived $1a, not $83.
        move    x:(r7+$1a),a
        move    #>$7ff,x0
        and     x0,a                    ; mask on LOAD, as v50 masks
        move    x:(r7+$31),x0
        add     x0,a                    ; base + LINE_OFF(0x0)
        move    a,r1                    ; line 0
        move    #>$800,x0
        add     x0,a
        move    a,r2                    ; line 1
        add     x0,a
        move    a,r3                    ; line 2
        add     x0,a
        move    a,r4                    ; line 3
        move    #>$ffffff,m1            ; linear
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4

; ---- SIZE: scale all four tap lengths -----------------------------------
        move    x:(r6+$2),x0
        move    #>$700000,y1
        mpy     x0,y1,a
        move    #>$100000,x0
        add     x0,a
        move    a,x1                    ; f = 0.125 .. 0.995
        move    #>$30f800,x0            ; 1567 as a fraction of 2048
        mpy     x0,x1,a
        asr     #$b,a,a
        neg     a
        move    a,n1                    ; -tap
        move    #>$270800,x0            ; 1249 as a fraction of 2048
        mpy     x0,x1,a
        asr     #$b,a,a
        move    #>$800,b
        sub     a,b
        move    b,x:(r7+$2a)
        move    #>$1e8800,x0            ; 977 as a fraction of 2048
        mpy     x0,x1,a
        asr     #$b,a,a
        move    #>$800,b
        sub     a,b
        move    b,x:(r7+$2b)
        move    #>$16e800,x0            ; 733 as a fraction of 2048
        mpy     x0,x1,a
        asr     #$b,a,a
        neg     a
        move    a,n4                    ; -tap
        move    #>$ffffff,m5

; ---- feedback gain from TIME --------------------------------------------
        move    x:(r6),x0
        move    #>$043000,y1
        mpy     x0,y1,a
        move    #>$3bd000,x0
        add     x0,a
        move    a,x:(r7+$1e)

; ---- HI: high cut --------------------------------------------------------
        move    x:(r6+$1),x0
        move    #>$700000,y1
        mpy     x0,y1,a
        move    #>$100000,x0
        add     x0,a
        move    a,x:(r7+$1f)

; ---- MIX -----------------------------------------------------------------
        move    x:(r6+$5),x0
        move    x0,x:(r7+$20)

; ---- MOD: modulation depth ----------------------------------------------
        move    x:(r6+$4),x0
        move    x0,x:(r7+$28)

; ---- WIDTH ---------------------------------------------------------------
        move    x:(r6+$b),x0
        move    x0,x:(r7+$2c)

; ---- RATE: LFO increment -------------------------------------------------
        move    x:(r6+$d),a
        asr     #$b,a,a
        move    #>$200,x0
        add     x0,a
        move    a,x:(r7+$2f)

; ---- PRE parameters (the delay itself is bypassed, as in v50) -----------
; DIFF: the phase read is $1a, not $83.
        move    x:(r6+$e),a
        asr     #$c,a,a
        move    a,x:(r7+$29)
        move    #>$1,x0
        add     x0,a
        neg     a
        move    a,n5
        move    x:(r7+$1a),a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$38),x0
        add     x0,a
        move    a,x:(r7+$30)

; ---- LFO: one triangle and its inverse ----------------------------------
        move    x:(r7+$3e),a            ; persistent phase, [0,$7fffff]
        move    x:(r7+$2f),x0           ; increment, from RATE
        add     x0,a
        move    #>$7fffff,x0
        and     x0,a
        move    a1,x0                   ; extract without saturating on A2
        move    x0,x:(r7+$3e)
        move    x0,a
        move    #>$400000,x0
        sub     x0,a
        abs     a                       ; triangle T
        move    a,x0
        move    x:(r7+$28),y1           ; MOD depth
        mpy     x0,y1,a
        move    a1,x0
        move    x0,x:(r7+$26)
        move    a1,x1
        asl     #$5,a,a
        move    a2,x0
        move    x0,x:(r7+$21)           ; line 1: integer offset
        move    x1,a
        move    #>$07ffff,x0
        and     x0,a
        asl     #$4,a,a
        move    a,x0
        move    x0,x:(r7+$22)
        move    #>$400000,a
        move    x:(r7+$26),x0
        sub     x0,a                    ; inverse triangle
        move    a1,x1
        asl     #$5,a,a
        move    a2,x0
        move    x0,x:(r7+$23)           ; line 2: integer offset
        move    x1,a
        move    #>$07ffff,x0
        and     x0,a
        asl     #$4,a,a
        move    a,x0
        move    x0,x:(r7+$24)

        do      n7,>rvend

; ---- input: mono sum -----------------------------------------------------
        move    #>$1,n0
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$1b)
        move    r1,a
        move    #>$3ff,x0
        and     x0,a
        move    a,x:(r7+$39)

; -- allpass 0: base+0x2000, tap 907 --
        move    x:(r7+$39),a
        move    #>117,x0
        add     x0,a
        move    #>$3ff,x0
        and     x0,a
        move    x:(r7+$32),x0
        add     x0,a
        move    a,r5
        move    #>$400000,y0
        move    y:(r5),b                ; d
        move    b,x0
        mpy     x0,y0,a
        move    x:(r7+$1b),x0
        add     x0,a                    ; v = x + g*d
        move    a,x:(r7+$1c)
        move    a,x1
        mpy     x1,y0,a
        sub     a,b                     ; out = d - g*v
        move    b,x:(r7+$1b)
        move    x:(r7+$39),a
        move    x:(r7+$32),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$1c),a
        move    a,y:(r5)

; -- allpass 1: base+0x2400, tap 673 --
        move    x:(r7+$39),a
        move    #>351,x0
        add     x0,a
        move    #>$3ff,x0
        and     x0,a
        move    x:(r7+$33),x0
        add     x0,a
        move    a,r5
        move    #>$400000,y0
        move    y:(r5),b
        move    b,x0
        mpy     x0,y0,a
        move    x:(r7+$1b),x0
        add     x0,a
        move    a,x:(r7+$1c)
        move    a,x1
        mpy     x1,y0,a
        sub     a,b
        move    b,x:(r7+$1b)
        move    x:(r7+$39),a
        move    x:(r7+$33),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$1c),a
        move    a,y:(r5)

; -- allpass 2: base+0x2800, tap 487 --
        move    x:(r7+$39),a
        move    #>537,x0
        add     x0,a
        move    #>$3ff,x0
        and     x0,a
        move    x:(r7+$34),x0
        add     x0,a
        move    a,r5
        move    #>$400000,y0
        move    y:(r5),b
        move    b,x0
        mpy     x0,y0,a
        move    x:(r7+$1b),x0
        add     x0,a
        move    a,x:(r7+$1c)
        move    a,x1
        mpy     x1,y0,a
        sub     a,b
        move    b,x:(r7+$1b)
        move    x:(r7+$39),a
        move    x:(r7+$34),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$1c),a
        move    a,y:(r5)

; -- allpass 3: base+0x2c00, tap 331 --
        move    x:(r7+$39),a
        move    #>693,x0
        add     x0,a
        move    #>$3ff,x0
        and     x0,a
        move    x:(r7+$35),x0
        add     x0,a
        move    a,r5
        move    #>$400000,y0
        move    y:(r5),b
        move    b,x0
        mpy     x0,y0,a
        move    x:(r7+$1b),x0
        add     x0,a
        move    a,x:(r7+$1c)
        move    a,x1
        mpy     x1,y0,a
        sub     a,b
        move    b,x:(r7+$1b)
        move    x:(r7+$39),a
        move    x:(r7+$35),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$1c),a
        move    a,y:(r5)

        move    x:(r7+$1b),a
        move    a,x:(r7+$15)            ; diffused input -> tank
        asr     #$1,a,a
        move    a,x:(r7+$27)            ; and at half, for the other three lines

; ---- four taps, damped inside the feedback path -------------------------
        move    x:(r7+$1f),y0           ; damping coefficient
        move    r1,a                    ; line 0 read, tap 1567
        move    #>$fff9e1,x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$10),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$3a),b            ; fills the AGU slot
        move    x:(r7+$1f),y0
        move    y:(r5),a
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,x:(r7+$3a)
        move    a,x:(r7+$16)

; -- line 1 modulated: tap 1249, interpolated --
        move    r1,b
        move    #>$7ff,x0
        and     x0,b
        move    x:(r7+$21),x0
        sub     x0,b
        move    x:(r7+$2a),x0
        add     x0,b
        move    #>$7ff,x0
        and     x0,b                    ; i0
        move    b,a
        add     x0,a
        and     x0,a                    ; i1 = (i0-1) mod 2048
        move    x:(r7+$36),x0
        add     x0,b
        add     x0,a
        move    a,x1
        move    b,r5
        move    x:(r7+$22),y1
        move    x1,a
        move    y:(r5),b                ; d0
        move    a,r5
        move    b,x:(r7+$25)
        move    b,x0
        move    y:(r5),a                ; d1
        sub     x0,a
        move    a,x0
        mpy     x0,y1,a
        move    x:(r7+$25),x0
        add     x0,a
        move    x:(r7+$3b),b
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,x:(r7+$3b)
        move    a,x:(r7+$17)

; -- line 2 modulated: tap 977, interpolated --
        move    r1,b
        move    #>$7ff,x0
        and     x0,b
        move    x:(r7+$23),x0
        sub     x0,b
        move    x:(r7+$2b),x0
        add     x0,b
        move    #>$7ff,x0
        and     x0,b                    ; i0
        move    b,a
        add     x0,a
        and     x0,a                    ; i1
        move    x:(r7+$37),x0
        add     x0,b
        add     x0,a
        move    a,x1
        move    b,r5
        move    x:(r7+$24),y1
        move    x1,a
        move    y:(r5),b                ; d0
        move    a,r5
        move    b,x:(r7+$25)
        move    b,x0
        move    y:(r5),a                ; d1
        sub     x0,a
        move    a,x0
        mpy     x0,y1,a
        move    x:(r7+$25),x0
        add     x0,a
        move    x:(r7+$3c),b
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,x:(r7+$3c)
        move    a,x:(r7+$18)

        move    r1,a                    ; line 3 read, tap 733
        move    #>$fffd23,x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$13),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$3d),b            ; fills the AGU slot
        move    x:(r7+$1f),y0
        move    y:(r5),a
        sub     b,a
        move    a,x0
        mpy     x0,y0,a
        add     b,a
        move    a,x:(r7+$3d)
        move    a,x:(r7+$19)

; ---- 4x4 Hadamard --------------------------------------------------------
        move    x:(r7+$17),x0
        move    x:(r7+$16),a
        add     x0,a
        move    a,x:(r7+$1a)            ; u0 = d0+d1
        move    x:(r7+$16),a
        sub     x0,a
        move    a,x:(r7+$1b)            ; u1 = d0-d1
        move    x:(r7+$19),x0
        move    x:(r7+$18),a
        add     x0,a
        move    a,x:(r7+$1c)            ; u2 = d2+d3
        move    x:(r7+$18),a
        sub     x0,a
        move    a,x:(r7+$1d)            ; u3 = d2-d3

; ---- feedback and write back --------------------------------------------
        move    x:(r7+$1e),y0           ; g/2
        move    x:(r7+$1c),x0
        move    x:(r7+$1a),a
        add     x0,a
        move    a,x0
        mpy     x0,y0,a
        move    x:(r7+$15),x0
        add     x0,a
        move    a,x:(r7+$14)
        move    r1,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$10),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$14),a            ; fills the AGU slot
        move    x:(r7+$1e),y0
        move    a,y:(r5)

        move    x:(r7+$1d),x0
        move    x:(r7+$1b),a
        add     x0,a
        move    a,x0
        mpy     x0,y0,a
        move    x:(r7+$15),x0
        sub     x0,a
        move    a,x:(r7+$14)
        move    r1,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$11),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$14),a
        move    x:(r7+$1e),y0
        move    a,y:(r5)

        move    x:(r7+$1c),x0
        move    x:(r7+$1a),a
        sub     x0,a
        move    a,x0
        mpy     x0,y0,a
        move    x:(r7+$27),x0
        sub     x0,a
        move    a,x:(r7+$14)
        move    r1,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$12),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$14),a
        move    x:(r7+$1e),y0
        move    a,y:(r5)

        move    x:(r7+$1d),x0
        move    x:(r7+$1b),a
        sub     x0,a
        move    a,x0
        mpy     x0,y0,a
        move    x:(r7+$27),x0
        add     x0,a
        move    a,x:(r7+$14)
        move    r1,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$13),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$14),a
        move    x:(r7+$1e),y0
        move    a,y:(r5)

; ---- wet added to dry ----------------------------------------------------
        move    x:(r7+$20),y1           ; wet gain
        move    x:(r7+$17),a
        move    x:(r7+$18),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$2d)            ; wet L
        move    x:(r7+$16),a
        move    x:(r7+$19),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$2e)            ; wet R

; ---- WIDTH: mid/side, then MIX, then onto the dry -----------------------
        move    x:(r7+$2d),a
        move    x:(r7+$2e),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$25)            ; M
        move    x:(r7+$2d),a
        sub     x0,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$2c),y0           ; WIDTH
        mpy     x0,y0,a
        move    a,x:(r7+$26)            ; w*S
        move    x:(r7+$25),a
        move    x:(r7+$26),x0
        add     x0,a
        move    a,x0
        mpy     x0,y1,a                 ; * MIX
        move    x:(r0),x0
        add     x0,a
        move    a,x:(r0)                ; L in place
        move    x:(r7+$25),a
        move    x:(r7+$26),x0
        sub     x0,a
        move    a,x0
        mpy     x0,y1,a
        move    x:(r0+n0),x0
        add     x0,a
        move    a,x:(r0+n0)             ; R in place
        move    (r1)+                   ; the shared phase
        move    #>$2,n0
        move    (r0)+n0                 ; advance one stereo frame
rvend:

; ---- per-block: write the underivable state back -------------------------
        move    x:(r7+$3f),r5
        move    #>$ffffff,m5
        move    x:(r7+$3e),a            ; fills the AGU slot
        move    a,y:(r5)+
        move    x:(r7+$3a),a
        move    a,y:(r5)+
        move    x:(r7+$3b),a
        move    a,y:(r5)+
        move    x:(r7+$3c),a
        move    a,y:(r5)+
        move    x:(r7+$3d),a
        move    a,y:(r5)+

; DIFF: v50 saved the phase to $83 here; the graft derives it, so the save
; is simply gone -- $83 belongs to the ladder counter.
engskip:

out:
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts
