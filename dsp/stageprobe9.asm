; ---------------------------------------------------------------------------
; stageprobe9 -- strip v8 toward v50 from the SURVIVING side.
;
; v51 (nop burn on the control call) and v52 (stock-style param latch on the
; control call) both froze: neither time nor r7-write traffic on a=0 is the
; protection. Guessing which scaffold element shields v8 has failed twice,
; so stop guessing: v8 provably survives with this exact engine, and this
; series REMOVES scaffold elements group by group. When a strip freezes,
; the last thing removed is the protection. Deterministic convergence.
;
; v9 = v8 minus the entire AUDIO-side scaffold:
;   * no buzz loop (silence from the scaffold; the engine is the only audio)
;   * no gain ladder, no buzz sample, no click override
; Kept, still to be stripped in later steps:
;   * the entry stores (mode flag -> $16, r0 -> $32)
;   * the counter/tag machinery ($83 written on EVERY call, incl. a=0)
;   * the derived phase in $1a (v50 instead persists phase in $83 at the
;     END of each audio call -- the last a=1-side delta, tested next)
;   * the r0 restore before the engine (a no-op now, nothing walks r0)
;   * the M epilogue on every exit
;   * the engine gate shape (threshold 0: engine on every audio call)
;
;   v9 survives two tracks -> the protection is among the kept items;
;       v10 strips the counter (phase reverts to v50's $83 persistence).
;   v9 freezes -> the buzz stage's audio writes were the protection --
;       astonishing, and immediately actionable.
;
; NOTE the audio through this build: no buzz, engine from the first call.
; The knobs prove the engine (they feed nothing else). The "laddering
; static" heard on v50/51/52 track 1 will still be here -- it is the
; engine's own bug (uncleared lines; and the derived phase steps 32/block
; against 16 written frames, scrambling the tank) -- separate from the
; freeze, fixed after it.
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
