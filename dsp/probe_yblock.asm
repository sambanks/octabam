; Is a large block of Y memory safe to use as a delay buffer?
;
; Established: DARK's slot is fine, and four sparse single words at
; X:0x9000/0x9800/0xa000/0xa800 survive -- but a 1024-word contiguous fill at
; X:0x9000 hangs, and so does an 8192-word one regardless of loop structure. So
; the X region is IN USE at runtime, and the sparse probes were simply too thin
; to hit whatever lives there. That fits the ColdFire DMAing audio into X memory
; at addresses chosen at runtime, which no load map can show.
;
; The stock reverbs keep their delay lines in Y: DARK REV has 103 instructions
; touching y:, and loaded Y data stops at 0x00794. So Y:0x2000 should be free.
;
; ONE variable changed from the build that hangs: x: -> y:.
;
;   heavy distortion -> Y takes bulk writes; move the reverb's delay lines to Y
;   silence/clean    -> the block does not survive there either
;   hang             -> Y is no better, and we need a different approach entirely
init:
        move    #>$2000,r1
        move    #>$ffffff,m1
        move    #>$400,x0               ; 1024 words, same size that hangs in X
        move    #>$e00000,a
        do      x0,>yclr
        move    a,y:(r1)+
        move    a,y:(r1)+
yclr:
        move    #>$ffffff,m1
        rts

proc:
        move    y:>$2200,y0             ; read back from the middle of the block
        move    r0,r1
        do      n7,>yend
        move    x:(r0)+,a
        move    x:(r0)+,b
        and     y0,a
        and     y0,b
        move    a,x:(r1)+
        move    b,x:(r1)+
yend:
        rts
