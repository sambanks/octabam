; ---------------------------------------------------------------------------
; stageprobe4 -- stop guessing: make the probe DISCRIMINATE.
;
; stageprobe3's hardware result: the quiet -> loud static cycle SURVIVED moving
; every write onto proven ground. That is two hard facts, not one failure:
;
;   * gain depends only on stage, stage only on the count, and the count was
;     tagged inside $83 -- a clean run climbs the ladder once and stays at the
;     floor. A repeating cycle therefore means the COUNT KEEPS GETTING
;     DESTROYED: the host scrambles $83 between calls. "The one slot proven to
;     persist" was proven by luck, over windows shorter than the reset period.
;     Ripple 1: stageprobe v1's stage attribution is VOID -- its counter sat in
;     $83 unprotected, so it may never have escalated past stage 1-2, and
;     "8 Y accesses a sample survives two tracks" was never demonstrated.
;     Ripple 2: v46 does not contradict this -- a scrambled tank phase is a
;     momentary tail glitch every few seconds, easy to miss by ear.
;   * the static survived two scratch layouts and two r0 idioms (v3's audio
;     stage is v50's verbatim instructions). Stage 1 should have been clean
;     mono program material; it was not. So amplifying x:(r0) yields noise,
;     and the probe must stop amplifying input at all.
;
; What v4 changes -- the experiment is otherwise v3's, stages and all:
;
;   * the audible readout is a SYNTHESIZED BUZZ: a square wave from bit 1 of
;     the count, ADDED to the dry signal exactly the way v46 adds wet. Input
;     is never amplified. Clean buzz = the write path is fine and v2/v3's
;     static was garbage INPUT; buzzing static = the pointer or write path.
;     The buzz PITCH measures calls per block: bit 1 toggling once per block
;     is ~690 Hz, twice per block is ~1.4 kHz.
;   * a TAG-FAIL CLICK: every time the tag check fails, one loud block
;     (5.8 ms). The click train makes the host's resets audible, with their
;     period. The buzz needs no input, so this runs with the SEQUENCER
;     STOPPED: clicks only while playing = the reset is sequencer-driven;
;     click period scaling with BPM = confirmation.
;   * the count RECYCLES at the top (back to $1c000, stage 14) instead of
;     saturating, so bit 1 keeps toggling and the floor buzz never freezes
;     into silent DC.
;   * a new tag ($2c, was $5a) so a leftover v3 word fails on the first call.
;
;   stage 0   nothing audible. 8 Y accesses a sample (stageprobe's stage 4).
;   stage 1   + AUDIO: buzz added to both channels, r0 walked -- v46's shape
;   stage 2   + PARAMS: the eight x:(r6+n) reads. Buzz drops 6 dB.
;   stage 3   + Y to 16 a sample. Another 6 dB. And so on:
;   stage 4   + Y to 24    stage 5  + Y to 36    stage 6  + 80 instr/sample
;   stage 7+  everything stays on, buzz at the floor, forever.
;
; WHAT A CLEAN RUN SOUNDS LIKE (one track, sequencer stopped): one click when
; the effect lands, ~3 s of silence, buzz fades in at -12 dB, five clean 6 dB
; steps down (~3 s each, half that if the dispatcher makes two calls a block),
; then the floor, FOREVER. Repeating clicks = the host resets $83, and their
; rhythm is the fingerprint of what does it. Cycling loudness = the ladder
; replaying after each click.
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
; The A accumulator is the dispatcher's mode flag. stageprobe ignores it and
; survives, so it is NOT gated on here -- everything below runs on both calls,
; exactly as in the survivor. It is only kept so the audio stage can refuse to
; write through r0 on a call where r0 is not an audio pointer.
        move    a,x:(r7+$16)

; ---- the counter: tag and count in the one slot, plus the click flag ----
; word = tag | count.  tag = bits 23..17 = $2c0000 (bit 23 clear -- a set sign
; bit would poison A2 through every mask and compare below). count = bits
; 16..0. The fields are disjoint, so tag | count is an add. A wrong tag means
; the slot was scrambled -- host write, first run, or a leftover from another
; build -- so restart at zero AND raise the click flag: this block will be
; loudly audible, and the click train is the measurement.
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
        move    a,x1                    ; keep the count for the stage
        move    #>$2c0000,x0
        add     x0,a                    ; tag | count
        move    a,x:(r7+$83)
        move    x1,a
        asr     #$d,a,a                 ; stage = count >> 13, 0..15
        move    a,x:(r7+$15)            ; every stage test reads it from here

        move    #>$ffffff,m0
        move    #>$ffffff,m5

; ---- recover the base, derive the line bases ----------------------------
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

; ---- the state block, one Y read and one Y write per block --------------
        move    x:(r7+$10),a
        move    #>$3800,x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m1
        move    y:(r5),a
        move    a,x:(r7+$14)
        move    x:(r7+$14),a
        move    a,y:(r5)

; ---- stage 2: the parameter reads, once per block -----------------------
; v50 reads eight parameter slots through r6 every block; stageprobe never
; touches r6 at all. The values are stored and never used -- this is about the
; access, not the number.
        move    x:(r7+$15),a
        move    #>$2,x0
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
; Built by a fall-through chain of shifts rather than a variable-count shift,
; because the count at stage 1 would be zero and `do`/`rep` with a zero count
; runs 65536 times on this core. Computed here, before b becomes the phase.
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
; A square wave from bit 1 of the count, at ladder gain - 12 dB, so stage 1
; starts at -12 dBFS and the stage-7 floor sits at -48. Input is NEVER read
; into this -- the buzz is synthesized, so it works with the sequencer stopped
; and it cannot inherit static from a garbage input buffer.
        move    x:(r7+$17),a
        asr     #$2,a,a                 ; ladder gain - 12 dB
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

; ---- stage 3+: the extra Y pointers -------------------------------------
; Post-increment through the four lines. One instruction per access, so the Y
; ramp raises Y traffic WITHOUT raising the instruction count much -- that is
; the whole point, since stageprobe's own idiom costs nine instructions an
; access and would confound the two axes.
;
; Each pointer advances at most four words a sample, so 64 a block, from a line
; base. The furthest reach is 0x1800 + 0x40, well inside the 0x3800 layout that
; ownprobe proved is ours.
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    x:(r7+$10),r1
        move    x:(r7+$11),r2
        move    x:(r7+$12),r3
        move    x:(r7+$13),r4
        move    x:(r7+$15),x1           ; two data moves before any use
        move    x:(r7+$16),x1

; ---- the sample loop -----------------------------------------------------
; The phase is not persistent: it restarts at 0 every block. The point is the
; traffic, not the sound.
        clr     b                       ; b = phase, and nothing below clobbers b
        do      n7,>pend

; ---- stage 0: read all four lines ---------------------------------------
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

; ---- stage 1: touch the audio -------------------------------------------
; The one thing v50 does every sample that stageprobe does not do at all: read
; the frame through r0, write it back, and walk r0 forward. The buzz is ADDED
; to the dry signal -- v46's shape, add wet in place -- so the dry is never
; amplified and never replaced. A tag-fail click forces this stage on even at
; stage 0, so a reset is audible wherever the ladder was.
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

; ---- stage 3: Y traffic to 16 a sample ----------------------------------
        move    x:(r7+$15),a
        move    #>$3,x0
        cmp     x0,a
        blt     ydone
        move    y:(r1),a
        move    a,y:(r1)+
        move    y:(r2),a
        move    a,y:(r2)+
        move    y:(r3),a
        move    a,y:(r3)+
        move    y:(r4),a
        move    a,y:(r4)+

; ---- stage 4: Y traffic to 24 a sample ----------------------------------
        move    x:(r7+$15),a
        move    #>$4,x0
        cmp     x0,a
        blt     ydone
        move    y:(r1),a
        move    a,y:(r1)+
        move    y:(r2),a
        move    a,y:(r2)+
        move    y:(r3),a
        move    a,y:(r3)+
        move    y:(r4),a
        move    a,y:(r4)+

; ---- stage 5: Y traffic to 36 a sample ----------------------------------
; Twice what v50 does. If it survives here, Y bandwidth across two instances is
; not the difference and the fault is a feature, not a rate.
        move    x:(r7+$15),a
        move    #>$5,x0
        cmp     x0,a
        blt     ydone
        move    y:(r1),a
        move    a,y:(r1)+
        move    y:(r2),a
        move    a,y:(r2)+
        move    y:(r3),a
        move    a,y:(r3)+
        move    y:(r4),a
        move    a,y:(r4)+
        move    y:(r1)+,a
        move    y:(r2)+,a
        move    y:(r3)+,a
        move    y:(r4)+,a
ydone:

; ---- stage 6: 80 instructions a sample, no memory at all ----------------
; cycleburn measured a ceiling of ~806 instructions a sample with ONE instance.
; It has never been measured with two, and two is the whole question. The loop
; body costs ~80 instructions a sample at stage 0 and ~225 at stage 6 -- ~450
; across the pair, still under that ceiling. Surviving here closes the cycle
; axis for two instances; freezing here reopens it with a number attached.
;
; b is the phase and is not touched. Only a, x0 and y0 move.
;
; It sits BEFORE the phase increment, and its skip branches to bdone rather than
; to the end of the loop: on this core the loop-end address is the last
; instruction IN the loop, and branching to it is not allowed. Keeping pend
; exactly where stageprobe has it keeps that shape identical to the survivor.
        move    x:(r7+$15),a
        move    #>$6,x0
        cmp     x0,a
        blt     bdone
        move    #>$123456,x0
        move    #>$234567,y0
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
        mpy     x0,y0,a
        add     x0,a
bdone:

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
