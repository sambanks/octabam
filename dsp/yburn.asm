; ---------------------------------------------------------------------------
; How many Y accesses a sample can ONE instance sustain?
;
; ownprobe says every word of the 0x4000 allocation holds our own signature a
; block later, on both tracks, at every offset. So the extent is real and
; uncontended, and the remaining candidate for the two-track hang is the rate:
; the tank does 8 Y accesses a sample per instance (four tap reads, four line
; writes) and that doubles with the second track.
;
; No probe has ever measured this. cycleburn burned NOPs, which cost an
; instruction slot and nothing else. memburn2 used X memory. Y:0x4000 and up is
; where the delay buffers live and may well be external with wait states, in
; which case an access costs far more than a slot.
;
; TIME sets the burn: N = (TIME >> 2) + 1 read/write pairs a sample, so
;
;     Y accesses a sample = 2N = 2 .. 66
;
; walking our own buffer with a 97-word stride under modulo so the pattern is
; scattered like the reverb's rather than sequential. Audio is untouched --
; this is a pure passthrough with a load on it.
;
; Sweep TIME upward on ONE track and find where it breaks up or stops. The tank
; needs 8, so if the ceiling is anywhere near 16 the second instance cannot fit
; and the fix is to cut accesses, not cycles.
; ---------------------------------------------------------------------------

init:
        move    x:>$213,r4
        move    r7,a
        asr     #$8,a,a
        move    x:(r4),x0
        move    #>$800,y0
        add     y0,a
        move    a,r5
        move    #>$ffffff,m5
        move    #>$ffffff,m0
        move    x0,y:(r5)
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        rts

proc:
        move    #>$ffffff,m0
        move    #>$ffffff,m5

; ---- recover the base ----------------------------------------------------
        move    r7,a
        asr     #$8,a,a
        move    #>$800,y0
        add     y0,a
        move    a,r5
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    y:(r5),b                ; base

; ---- burn count: N = (TIME >> 2) + 1, so 1..32 --------------------------
        move    x:(r6),a
        asr     #$12,a,a                ; TIME<<16 >> 18 = TIME >> 2
        move    #>$1,x0
        add     x0,a
        move    a,y1

; ---- walk our own buffer, scattered, under modulo -----------------------
        move    b,r5
        move    #>$7ff,m5
        move    #>$61,n5                ; 97-word stride

        do      n7,>pend
        move    y1,x0
        do      x0,>bend
        move    y:(r5),a
        move    a,y:(r5)+n5
bend:
        nop
pend:

        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts
