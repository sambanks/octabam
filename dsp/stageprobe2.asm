; ---------------------------------------------------------------------------
; stageprobe2 -- build UP from the two-track survivor, one axis every ~3 s.
;
; dsp/stageprobe.asm never freezes on two tracks. dsp/reverb50.asm always does.
; This starts at exactly what stageprobe survives and adds, one at a time, each
; thing v50 does that stageprobe does not. Whatever stage it dies in is the axis.
;
;   stage 0   0-3 s    stageprobe's stage 4, verbatim. 8 Y accesses a sample.
;   stage 1   3-6 s    + AUDIO: read and write x:(r0), advance r0 per frame
;   stage 2   6-9 s    + PARAMS: the eight x:(r6+n) reads v50 does per block
;   stage 3   9-12 s   + Y to 16 a sample
;   stage 4   12-15 s  + Y to 24 a sample
;   stage 5   15-18 s  + Y to 36 a sample   (v50 does 18)
;   stage 6   18-21 s  + 80 instructions a sample of pure arithmetic
;   past 21 s          none of these axes is the difference
;
; A freeze inside the FIRST three seconds means the baseline itself broke, not
; that a null effect is fatal -- stageprobe already proved a null effect is not.
;
; TWO READOUTS, so the stage does not have to be timed blind:
;
;   * from stage 1 the track collapses to MONO -- that is stage 1 arriving, and
;     it calibrates the stopwatch against the real escalation rate.
;   * from stage 1 the track is also attenuated 6 dB per stage: stage 1 full,
;     stage 2 half, stage 3 a quarter ... stage 6 is -30 dB. Count the drops.
;     The level you last heard IS the stage it died in.
;
; The counter is per instance, in r7+$83, and nothing resets it -- init cannot,
; because the dispatcher re-invokes init most blocks and the counter would never
; leave stage 0. It is instead initialised ONCE against a sentinel in r7+$82, so
; the escalation starts from a known point rather than from whatever garbage the
; slot held. That is the one thing stageprobe left to luck.
;
; HOW TO RUN IT. Enable the effect on both tracks in QUICK SUCCESSION -- each
; instance counts its own blocks, so the two escalations run offset by however
; long you take. Then let it climb and note the level at the freeze.
;
; Run it on ONE track first and let it pass 21 s, to prove the escalation itself
; is harmless.
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
; write through r0 on a control call, where r0 is not an audio pointer.
        move    a,x:(r7+$86)

; ---- initialise the counter once, against a sentinel --------------------
        move    x:(r7+$82),a
        move    #>$5a5a5a,x0
        cmp     x0,a
        beq     havectr
        move    x0,x:(r7+$82)
        clr     a
        move    a,x:(r7+$83)
havectr:

; ---- block counter -> stage ---------------------------------------------
        move    x:(r7+$83),a
        move    #>$1,x0
        add     x0,a
        move    a,x:(r7+$83)
        asr     #$d,a,a                 ; stage = counter >> 13
        move    a,x:(r7+$85)            ; every stage test reads it from here

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
        move    x:(r7+$85),a
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
        move    x:(r7+$85),b
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
        move    a,x:(r7+$87)            ; wet gain for the audio stage

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
        move    #>$1,n0                 ; audio: the right channel offset
        move    x:(r7+$85),x1           ; and two data moves before any use
        move    x:(r7+$86),x1

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
; the frame through r0, write it back, and walk r0 forward. n0 is set once a
; block, not inside the loop, and r0 advances as two separate +1 steps with a
; data move between them, so nothing here is an AGU write landing next to its
; own use. If this stage is the one that kills it, it is the ACCESS, not an
; interlock.
        move    x:(r7+$85),a
        move    #>$1,x0
        cmp     x0,a
        blt     noaud
        move    x:(r7+$86),a
        tst     a
        beq     noaud                   ; control call: r0 is not an audio pointer
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a                 ; mono -- the audible marker for stage 1
        move    a,x0
        move    x:(r7+$87),y0           ; 6 dB per stage: the audible readout
        mpy     x0,y0,a
        move    a,x:(r0)
        move    a,x:(r0+n0)
        move    (r0)+n0
        move    x:(r7+$85),x1           ; a data move between the two r0 steps
        move    (r0)+n0
noaud:

; ---- stage 3: Y traffic to 16 a sample ----------------------------------
        move    x:(r7+$85),a
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
        move    x:(r7+$85),a
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
        move    x:(r7+$85),a
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
; It has never been measured with two, and two is the whole question. Counted
; from this file, the loop body costs 79 instructions a sample at stage 0, 137
; by stage 5 and 223 at stage 6 -- 446 across the pair, still under that
; ceiling. Surviving here closes the cycle axis for two instances; freezing
; here reopens it with a number attached.
;
; b is the phase and is not touched. Only a, x0 and y0 move.
;
; It sits BEFORE the phase increment, and its skip branches to bdone rather than
; to the end of the loop: on this core the loop-end address is the last
; instruction IN the loop, and branching to it is not allowed. Keeping pend
; exactly where stageprobe has it keeps that shape identical to the survivor.
        move    x:(r7+$85),a
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
