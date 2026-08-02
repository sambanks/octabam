; ---------------------------------------------------------------------------
; Make the freeze say how far it got.
;
; Twelve builds have been shipped on hypotheses and every one was wrong, because
; a freeze tells us nothing except that it froze. This makes TIME the readout:
; the effect starts as a literal null and switches on one more piece of itself
; every ~3 seconds. Whatever it was doing when the machine died is the stage it
; had just reached.
;
; The counter lives in r7+$83, the one slot proven to persist between calls, and
; the stage is counter >> 13. At 16 frames a block and 44.1 kHz that is 2756
; blocks a second, so 8192 blocks is 2.97 s.
;
;   stage 0   0-3 s    rts. Nothing at all. Not one memory access.
;   stage 1   3-6 s    + recover the base from the stash, write 4 r7 slots
;   stage 2   6-9 s    + load and save the 5-word state block at base+0x3800
;   stage 3   9-12 s   + read the four delay lines, every sample
;   stage 4   12-15 s  + write the four delay lines, every sample
;   past 15 s          it does not freeze at all
;
; Run it on ONE track first and let it pass 15 seconds, to prove the escalation
; itself is harmless. Then add the second track and time it.
;
; Stage 0 is the null test on its own: if two tracks die inside the first three
; seconds, an effect that executes a single rts is fatal, the DSP code is
; irrelevant, and the fault is in the host or the descriptor.
;
; Audio is never touched, so this is a passthrough throughout and the track
; stays audible until the moment it dies.
; ---------------------------------------------------------------------------

init:
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
; ---- block counter -> stage ---------------------------------------------
        move    x:(r7+$83),a
        move    #>$1,x0
        add     x0,a
        move    a,x:(r7+$83)
        asr     #$d,a,a                 ; stage = counter >> 13
        move    a,x1

        tst     a
        beq     out                     ; ---------------- stage 0: nothing

        move    #>$ffffff,m0
        move    #>$ffffff,m5

; ---- stage 1: recover the base, derive the line bases -------------------
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

        move    x1,a
        move    #>$2,x0
        cmp     x0,a
        blt     out                     ; ---------------- stage 1 stops here

; ---- stage 2: the state block, one Y read and one Y write per block -----
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

        move    x1,a
        move    #>$3,x0
        cmp     x0,a
        blt     out                     ; ---------------- stage 2 stops here

; ---- the sample loop -----------------------------------------------------
; The phase is not persistent here: it restarts at 0 every block. That is fine,
; the point is the memory traffic, not the sound.
        clr     b                       ; b = phase
        do      n7,>pend

; ---- stage 3: read all four lines ---------------------------------------
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

        move    x1,a
        move    #>$4,x0
        cmp     x0,a
        blt     nowrite                 ; ---------------- stage 3 stops here

; ---- stage 4: write all four lines --------------------------------------
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

nowrite:
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
