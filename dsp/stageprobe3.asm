; ---------------------------------------------------------------------------
; stageprobe3 -- stageprobe2 with every write moved onto proven ground.
;
; stageprobe2's hardware result: NO FREEZE, but one track cycled quiet ->
; loud static -> quiet -> loud static, so the stages cannot have escalated
; cleanly and the "no freeze" means nothing. Two defects, both introduced by
; v2 and present in neither the survivor nor v46:
;
;   * it wrote four r7 slots with no evidence: $82 (sentinel), $85 (stage),
;     $86 (mode), $87 (gain). Only $83 was ever proven to persist. $85..$87
;     are written and read within the same call, so they cannot explain a
;     cycle -- but $82 must survive BETWEEN calls, and if the host owns it
;     the counter resets whenever the host rewrites it. The escalation then
;     REPLAYS: dry (quiet) -> stage 1 at full gain (loud) -> 6 dB steps
;     (quiet) -> reset. That is exactly the cycle heard on hardware, and it
;     means stages 3..6 likely never ran.
;   * it advanced r0 with two (r0)+n0 steps, n0=1, one data move apart --
;     an idiom this project has never run on hardware. v46/v50 advance one
;     stereo frame as n0=2, a single (r0)+n0, and v46 sounds RIGHT on
;     track 1. A mis-advancing r0 scrambles frames: static.
;
; So: the counter now lives entirely in $83, tagged in-word -- bits 23..17
; are a signature, bits 16..0 the count, and the count SATURATES at max
; rather than wrapping, so past stage 7 everything simply stays on. Stage,
; mode and gain live at $15..$17, inside the $10..$3f scratch v46 writes
; every sample on track 1 with clean audio. The audio advance is v50's
; idiom verbatim. Nothing else changed from stageprobe2.
;
;   stage 0   stageprobe's stage 4, verbatim. 8 Y accesses a sample.
;   stage 1   + AUDIO: read and write x:(r0), advance r0 per frame
;   stage 2   + PARAMS: the eight x:(r6+n) reads v50 does per block
;   stage 3   + Y to 16 a sample
;   stage 4   + Y to 24 a sample
;   stage 5   + Y to 36 a sample   (twice v50's 18)
;   stage 6   + 80 instructions a sample of pure arithmetic
;   stage 7+  everything stays on; the count saturates instead of wrapping
;
; Readout unchanged: MONO from stage 1, then 6 dB down per stage. The level
; you last heard is the stage it died in. The counter advances once per proc
; CALL -- if the dispatcher makes both the control and the audio call, a
; stage is ~1.5 s, not 3 s. Count the drops, not the clock.
;
; What a CLEAN run sounds like, one track: dry, then clean mono at full
; level (if stage 1 is still static, the r0 idiom is still wrong), then six
; clean steps down to a floor, where it STAYS. Any return to dry or full
; level means the counter was reset -- $83 is not safe either, and that is
; its own result, worth knowing.
;
; The ladder does not restart when the effect is toggled: $83 persists. To
; re-run it, switch FX2 to another effect and back, which scrambles $83 and
; fails the tag.
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
        move    a,x:(r7+$16)

; ---- the counter: tag and count in the ONE proven slot -------------------
; word = tag | count.  tag = $2d in bits 23..17 ($5a0000), count in bits
; 16..0. The fields are disjoint, so tag | count is an add. A wrong tag means
; the slot holds garbage (first run, or another effect used it): restart at 0.
        move    x:(r7+$83),a
        move    #>$fe0000,x0
        and     x0,a
        move    #>$5a0000,x0
        cmp     x0,a
        beq     tagok
        move    #>$5a0000,a             ; wrong tag: count = 0
        move    a,x:(r7+$83)
tagok:
        move    x:(r7+$83),a
        move    #>$01ffff,x0
        and     x0,a                    ; count
        cmp     x0,a                    ; count - max
        beq     atmax                   ; saturate, never wrap
        move    #>$1,x0
        add     x0,a
atmax:
        move    a,x1                    ; keep the count for the stage
        move    #>$5a0000,x0
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
        move    a,x:(r7+$17)            ; wet gain for the audio stage

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
; the frame through r0, write it back, and walk r0 forward. The read offset
; and the advance are v50's exact instructions -- n0=1 for the right channel,
; then n0=2 and a single (r0)+n0 -- because that shape is proven to sound
; RIGHT on hardware, and this stage must only ever test the ACCESS.
        move    x:(r7+$15),a
        move    #>$1,x0
        cmp     x0,a
        blt     noaud
        move    x:(r7+$16),a
        tst     a
        beq     noaud                   ; control call: r0 is not an audio pointer
        move    #>$1,n0
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a                 ; mono -- the audible marker for stage 1
        move    a,x0
        move    x:(r7+$17),y0           ; 6 dB per stage: the audible readout
        mpy     x0,y0,a
        move    a,x:(r0)
        move    a,x:(r0+n0)
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
