; ---------------------------------------------------------------------------
; stageprobe6 -- the shapes are eliminated too; now stage the REGISTER IDIOMS.
;
; stageprobe5, EIGHT tracks, hardware: every instance climbed the ladder and
; nothing froze. Since the stages are cumulative, stage 7 ran all four shapes
; AT ONCE -- scattered tap reads, tank write-behind, allpass read-modify-write,
; LFO-modulated interpolated reads -- on four instances per DSP, at roughly
; 1080 instructions a sample per DSP. Every access PATTERN the reverb needs is
; now proven survivable, individually and combined, at 4x the instance count
; that kills v50.
;
; What remains between the probe and v50 is not WHAT memory is touched but
; HOW -- the register idioms:
;
;   * v50 carries its phase in r1, a live AGU register advanced with (r1)+
;     every sample, and derives every address from it. The probe has only
;     ever computed addresses into r5 from scratch.
;   * v50 writes n1/n4/n5 every block from an mpy chain -- generator
;     leftovers the loop never reads, but writes to AGU registers sitting
;     next to live pointer use. The v47 freeze was an interlock of exactly
;     this class ("an M load interlocks with its address register").
;   * v50 runs a dense X dataflow per sample: four one-pole damping states,
;     the Hadamard, the feedback chain -- dozens of X scratch accesses and
;     ~15 multiplies. The probe's X traffic is far lighter.
;   * and the old v40-vs-v41 result -- same cycles, one froze -- blamed
;     y:(rN+nN) indexed reads: a register idiom, not a rate. v50 itself has
;     none left, but the class is under test here.
;
;   stage 0   the proven baseline: 8 Y accesses a sample, silent
;   stage 1   + audio buzz + params (proven; the ladder readout)
;   stage 2   + the CARRIED POINTER: r1 rebuilt per block from the phase,
;             advanced (r1)+ per sample, two tap reads derived from it with
;             v50's exact idiom -- including its data-move fills, where the
;             scaffold uses M-register fills
;   stage 3   + the DEAD n WRITES: n1/n4/n5 from mpy -> asr -> neg every
;             block, never read, exactly as v50 leaves them
;   stage 4   + the X DATAFLOW: two one-pole damping states and a
;             Hadamard-style combine, per sample, through X scratch
;   stage 5   + FEEDBACK WRITES: computed values (not the loop index)
;             written into two lines at the carried write phase
;   stage 6   + ALL OF v5'S SHAPES on top: four tap reads, two allpasses,
;             one interpolated double-read. Everything, combined.
;   stage 7+  the lot, forever. The count recycles; the buzz never stops.
;
; IF TWO TRACKS FREEZE, THE LEVEL YOU LAST HEARD NAMES THE IDIOM:
;
;   -12 dB (loudest)  scaffold regression -- tell me
;   -18 dB            the carried pointer / (r1)+
;   -24 dB            the dead n-register writes
;   -30 dB            the X dataflow density
;   -36 dB            feedback writes at the carried phase
;   -42 dB / floor    only the full combination
;   runs forever      the idioms are innocent too -- the remaining diff is
;                     v50's exact instruction ORDER, and v7 is v50's own
;                     loop body grafted whole onto this scaffold
;
; Readout as ever: buzz level = stage, pitch = calls per block, trig
; re-pitching = the split (solved, BPM-verified), click = counter scrambled.
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
        move    a,x1                    ; keep the count for the stage and phase
        move    #>$2c0000,x0
        add     x0,a                    ; tag | count
        move    a,x:(r7+$83)
        move    x1,a
        asr     #$d,a,a                 ; stage = count >> 13, 0..15
        move    a,x:(r7+$15)

; ---- the tank phase, derived from the count -----------------------------
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
        move    a,x:(r7+$2c)            ; allpass 0 base
        move    #>$2400,a
        add     x0,a
        move    a,x:(r7+$2d)            ; allpass 1 base

; ---- the carried pointer, rebuilt per block -----------------------------
; v50's shape exactly: r1 = base + phase, m1 linear, advanced (r1)+ per
; sample from stage 2. Rebuilt every block whatever the stage, so the first
; stage-2 block starts from a defined pointer.
        move    x:(r7+$1a),a
        move    x:(r7+$10),x0
        add     x0,a
        move    a,r1
        move    #>$ffffff,m1            ; linear -- v50 loads m1 right after r1
        move    #>$ffffff,m2

; ---- the tap offsets, folded with the phase once per block --------------
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
        move    x:(r7+$10),a
        move    #>$3800,x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m3
        move    y:(r5),a
        move    a,x:(r7+$14)
        move    x:(r7+$14),a
        move    a,y:(r5)

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

; ---- stage 3: the dead n-register writes, once per block ----------------
; v50 computes SIZE-scaled taps into n1/n4 and a pre-delay offset into n5
; every block, through the multiplier, and the loop never reads any of them.
; The writes sit right against the carried r1's per-sample use -- the exact
; interlock class the v47 freeze taught. Reproduced verbatim.
        move    x:(r7+$15),a
        move    #>$3,x0
        cmp     x0,a
        blt     nonw
        move    x:(r7+$22),x0           ; a parameter word, as v50 uses r6+2
        move    #>$700000,y1
        mpy     x0,y1,a
        move    #>$100000,x0
        add     x0,a
        move    a,x1
        move    #>$30f800,x0            ; 1567 as a fraction of 2048
        mpy     x0,x1,a
        asr     #$b,a,a
        neg     a
        move    a,n1                    ; dead, exactly as v50 leaves it
        move    #>$16e800,x0            ; 733 as a fraction of 2048
        mpy     x0,x1,a
        asr     #$b,a,a
        neg     a
        move    a,n4                    ; dead
        move    x:(r7+$27),a            ; the PRE parameter word
        asr     #$c,a,a
        move    #>$1,x0
        add     x0,a
        neg     a
        move    a,n5                    ; dead
nonw:

; ---- the readout gain: 6 dB down per stage ------------------------------
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
        tst     b
        beq     noclick
        move    #>$3fffff,a
        move    a,x:(r7+$18)
noclick:

; ---- the sample loop -----------------------------------------------------
        clr     b                       ; b = phase, and nothing below clobbers b
        do      n7,>pend

; ---- stage 0: read all four lines (the proven baseline) -----------------
        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$10),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5            ; two instructions before r5 is used
        move    #>$ffffff,m3
        move    y:(r5),a

        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$11),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m3
        move    y:(r5),a

        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$12),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m3
        move    y:(r5),a

        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$13),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m3
        move    y:(r5),a

; ---- stage 0: write all four lines --------------------------------------
        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$10),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m3
        move    b,a
        move    a,y:(r5)

        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$11),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m3
        move    b,a
        move    a,y:(r5)

        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$12),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m3
        move    b,a
        move    a,y:(r5)

        move    b,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$13),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m3
        move    b,a
        move    a,y:(r5)

; ---- stage 1: the audio buzz --------------------------------------------
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

; ---- stage 2: two reads through the carried pointer ---------------------
; v50's line-0 and line-3 read idiom VERBATIM: address from the live r1,
; constant negative tap, mask, base, r5 -- and the fills are DATA MOVES, the
; way v50 fills them, where every fill above is an M write.
        move    x:(r7+$15),a
        move    #>$2,x0
        cmp     x0,a
        blt     ncp
        move    r1,a
        move    #>$fff9e1,x0            ; -1567, v50's line-0 tap
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$10),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$17),y0           ; data-move fill, v50's habit
        move    x:(r7+$17),y0           ; and again
        move    y:(r5),a
        move    a,x:(r7+$1d)            ; d0, for the stage-4 dataflow

        move    r1,a
        move    #>$fffd23,x0            ; -733, v50's line-3 tap
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$13),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$17),y0
        move    x:(r7+$17),y0
        move    y:(r5),a
        move    a,x:(r7+$1e)            ; d3, for the stage-4 dataflow
        move    (r1)+                   ; the carried phase advances -- v50's
                                        ; one AGU register alive across samples
ncp:

; ---- stage 4: the X dataflow --------------------------------------------
; Two one-pole damping states through the multiplier, then a Hadamard-style
; combine, all in X scratch -- the density v50 runs and no probe has.
        move    x:(r7+$15),a
        move    #>$4,x0
        cmp     x0,a
        blt     nxd
        move    x:(r7+$1d),a            ; d0
        move    x:(r7+$3a),x0           ; s0
        sub     x0,a                    ; d - s
        move    a,x1
        move    #>$400000,y1
        mpy     x1,y1,a                 ; c*(d-s)
        move    x:(r7+$3a),x0
        add     x0,a
        move    a,x:(r7+$3a)            ; s0 += c*(d0-s0)
        move    x:(r7+$1e),a            ; d3
        move    x:(r7+$3b),x0           ; s1
        sub     x0,a
        move    a,x1
        mpy     x1,y1,a
        move    x:(r7+$3b),x0
        add     x0,a
        move    a,x:(r7+$3b)            ; s1 += c*(d3-s1)
        move    x:(r7+$3b),x0
        move    x:(r7+$3a),a
        add     x0,a
        move    a,x:(r7+$1f)            ; u0 = s0+s1
        move    x:(r7+$3a),a
        sub     x0,a
        move    a,x:(r7+$1b)            ; u1 = s0-s1
        move    x:(r7+$1f),x0
        move    #>$3c0000,y0
        mpy     x0,y0,a                 ; g*u0 -- the feedback multiply
        move    x:(r7+$18),x0
        add     x0,a
        move    a,x:(r7+$1f)            ; the value stage 5 writes back
nxd:

; ---- stage 5: feedback writes at the carried phase ----------------------
; Computed values -- not the loop index -- written into two lines at the
; carried write phase, v50's write-back idiom with its data-move fills.
        move    x:(r7+$15),a
        move    #>$5,x0
        cmp     x0,a
        blt     nfw
        move    r1,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$10),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$1f),a            ; the computed value; fills the slot
        move    x:(r7+$17),y0           ; second fill, a data move
        move    a,y:(r5)

        move    r1,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$11),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$1b),a            ; u1; fills the slot
        move    x:(r7+$17),y0
        move    a,y:(r5)
nfw:

; ---- stage 6: all of v5's shapes on top ---------------------------------
; Four tap reads, two allpass read-modify-writes, one interpolated
; double-read: everything stageprobe5 proved, combined with the idioms.
        move    x:(r7+$15),a
        move    #>$6,x0
        cmp     x0,a
        blt     nsh
        move    b,a
        move    x:(r7+$28),x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$10),x0
        add     x0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m3
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
        move    #>$ffffff,m3
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
        move    #>$ffffff,m3
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
        move    #>$ffffff,m3
        move    y:(r5),a

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
        move    x:(r7+$2c),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$1c),a
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
        move    y:(r5),a
        move    a,x0
        mpy     x0,y0,a
        move    x:(r7+$18),x0
        add     x0,a
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

        move    b,a
        move    x:(r7+$1a),x0
        add     x0,a
        move    #>799,x0
        add     x0,a
        move    #>$7ff,x0
        and     x0,a
        move    x:(r7+$11),x0
        add     x0,a
        move    a,r5
        move    a,x1                    ; hold the address, fills the slot
        move    #>$ffffff,m5
        move    y:(r5),a                ; d0
        move    a,x:(r7+$1c)
        move    x1,a
        move    #>$1,x0
        sub     x0,a                    ; the adjacent word
        move    a,r5
        move    #>$200000,y1            ; a fixed fraction; fills the slot
        move    x:(r7+$1c),x0           ; d0, second fill
        move    y:(r5),a                ; d1
        sub     x0,a
        move    a,x1
        mpy     x1,y1,a                 ; f*(d1-d0)
        move    x:(r7+$1c),x0
        add     x0,a                    ; the interpolated tap, discarded
nsh:

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
