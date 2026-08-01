; Echo using the stock convention: Y memory, small buffer, state in r7.
;
; DARK REV sets modulo registers directly to delay lengths (646, 922, 608, 1376,
; 896, 1292, 2047), never loads an address above 0x200, uses Y memory heavily,
; and keeps counters in the r7 state block. Everything here follows that, unlike
; v1-v4 which used four 4096-word lines in self-chosen X memory.
;
; Buffer: Y:0x800-0xfff, above the loaded Y data (which ends at 0x794).
; Tap 1376 = 31 ms, one of DARK's own lengths.
; Phase in r7+$83.
;
;   audible echo -> this is the right convention; rebuild the FDN on it
;   dry only     -> Y with r7 state is not it either
init:
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m5
        rts

proc:
        move    x:(r7+$83),a            ; phase, masked on load
        move    #>$7ff,x0
        and     x0,a
        move    #>$800,x0               ; buffer base, above loaded Y data
        add     x0,a
        move    a,r1
        move    #>$7ff,m1               ; 2048-word circular
        move    #>$fffaa0,n1            ; -1376
        move    r0,r5
        move    #>$ffffff,m5
        move    #>$400000,y0            ; 0.5 feedback

        do      n7,>eend
        move    y:(r1+n1),y1            ; delayed sample, Y memory
        move    x:(r0)+,a               ; L
        move    x:(r0)+,x1              ; R
        move    y1,x0
        mpy     x0,y0,b
        add     a,b
        move    b,y:(r1)+               ; back into the line
        move    y1,x0
        add     x0,a
        move    a,x:(r5)+
        move    x1,a
        add     x0,a
        move    a,x:(r5)+
eend:
        move    r1,a
        move    #>$7ff,x0
        and     x0,a
        move    a,x:(r7+$83)
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m5
        rts
