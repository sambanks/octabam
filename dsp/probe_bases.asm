; Are the reverb's four delay-line bases usable, without bulk writing?
;
; Known: 1 word at X:0x4000 works. 1024 words at X:0x9000 hangs. That changed
; address AND size together, so this separates them -- single words, but at the
; four addresses the reverb actually uses.
;
;   heavy distortion -> all four bases hold their value; the ADDRESSES are fine
;                       and the bulk write is what breaks it
;   silence/clean    -> a base does not read back; the region is in use
;   hang             -> even touching one of these addresses is fatal
init:
        move    #>$e00000,x0
        move    x0,x:>$9000
        move    x0,x:>$9800
        move    x0,x:>$a000
        move    x0,x:>$a800
        rts

proc:
        move    x:>$9000,a              ; AND all four together: any one that
        move    x:>$9800,x0             ; fails to read back clears the mask
        and     x0,a
        move    x:>$a000,x0
        and     x0,a
        move    x:>$a800,x0
        and     x0,a
        move    a,y0
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
