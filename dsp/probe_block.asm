; Does a LARGE region of X memory survive being used as a buffer?
;
; The single-word probe proved X:0x4000/0xc000/0xf000 are readable and writable.
; But the reverb writes thousands of words continuously and hangs, and the stock
; reverbs keep their delay lines in Y memory, not X. So the question is not
; "does this address respond" but "is this region actually free at runtime" --
; the load map only shows what is INITIALISED, not what is USED.
;
; init  fills 1024 words at X:0x9000 with a mask
; proc  reads one word from the middle of that block and applies it
;
;   heavy distortion -> the block survives; X:0x9000 is genuinely free
;   clean / silence  -> something else overwrites it
;   hang             -> writing the block corrupts something vital
init:
        move    #>$9000,r1
        move    #>$ffffff,m1
        move    #>$400,x0               ; 1024 words
        move    #>$e00000,a
        do      x0,>bclr
        move    a,x:(r1)+
bclr:
        move    #>$ffffff,m1
        rts

proc:
        move    x:>$9200,y0             ; middle of the block
        move    r0,r1
        do      n7,>bend
        move    x:(r0)+,a
        move    x:(r0)+,b
        and     y0,a
        and     y0,b
        move    a,x:(r1)+
        move    b,x:(r1)+
bend:
        rts
