; ---------------------------------------------------------------------------
; Which words of the 16K allocation are actually OURS when two instances run?
;
; v41 (no buffer traffic) runs on two tracks and v40 (identical bar four line
; reads and four line writes) hangs, so the fault is the Y buffer access. The
; two candidates are how OFTEN we touch it and how MUCH of it we touch, and the
; builds meant to tell them apart both came back "dry" -- one because it was
; genuinely broken, one because a 5.8 ms box is not an audible reverb. Judging a
; tail by ear is not a measurement.
;
; So measure ownership instead of listening for it. Once per block:
;
;     addr  = base + (TIME << 7)          0 .. 0x3f80, the whole allocation
;     read  y:(addr) and compare with r7
;     write r7 to y:(addr)
;     audio passes ONLY if the read matched
;
; r7 differs per instance (0x6200 and 0x6500, measured), so the value each
; instance writes is its own signature. A word that still holds our signature a
; block later is ours. A word that does not is being written by the other
; instance or by the host -- which is exactly the thing that would make a 14K
; layout fatal at two instances and harmless at one.
;
; ONE word written per block, so bandwidth cannot be a factor and this isolates
; extent completely.
;
; Sweep TIME. The first block after any change reads a stale value and stays
; silent, so give each position a moment. Expect, if the allocation really is
; 0x4000 words per instance: audio at every position, on both tracks. The
; position where it STOPS is the true size of the allocation, and
;
;     size = TIME_at_which_it_breaks << 7
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
        move    #>$ffffff,m0
        move    #>$ffffff,m5

; ---- recover the base ----------------------------------------------------
        move    r7,a
        asr     #$8,a,a
        move    #>$800,y0
        add     y0,a
        move    a,r5
        move    #>$ffffff,m1            ; two instructions before r5 is used
        move    #>$ffffff,m2
        move    y:(r5),x0               ; base

; ---- addr = base + (TIME << 7) -------------------------------------------
        move    x:(r6),a                ; TIME arrives as value<<16
        asr     #$9,a,a                 ; -> value << 7, max 0x3f80
        add     x0,a
        move    a,r5
        move    r7,b                    ; our signature; fills the AGU slot
        move    #>$ffffff,m3
        move    y:(r5),a                ; what is there now
        move    b,y:(r5)                ; leave our signature for next block

; ---- pass audio only if the word survived the last block ------------------
        move    b,x0
        cmp     x0,a
        beq     match

        clr     a
        move    #>$1,n0
        do      n7,>zend
        move    a,x:(r0)
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
zend:
        nop

match:
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts
