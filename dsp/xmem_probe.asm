; ---------------------------------------------------------------------------
; Is the high X region real, usable memory? (DSP.md section 7c)  v2.
;
; v1 tested THREE SINGLE WORDS and reported failure. That was not good enough:
;   * X:0x09000 turned out to be clobbered even in the emulator, where only the
;     DSP's own setup and our effect run -- so v1's "fail" may have been that
;     one bad address, not the region.
;   * Its signatures made the hardware result ambiguous: a single-address
;     failure mutes one channel, which is easily reported as "silent".
;   * It skipped the A2-clean discipline the rest of this project follows.
;
; v2 writes and verifies a full 1024-word BLOCK at each of two addresses, with
; a walking value so no two words share a pattern (a dead address whose bus
; holds the last value written cannot pass). Unambiguous signatures:
;
;   0x0C000..0x0C3FF bad -> LEFT silent
;   0x0F000..0x0F3FF bad -> RIGHT silent
;   both blocks good     -> HALF VOLUME  (positive proof the probe ran)
;
; 2048 words touched per block is ~270 cycles/sample -- affordable, and far
; stronger evidence than three isolated words.
; ---------------------------------------------------------------------------

init:
        rts

proc:
        move    #>$400000,a             ; assume pass
        move    a,x:(r7+$10)
        move    a,x:(r7+$11)

; ---- block 1: fill 0x0C000.. with a walking value, then verify -------------
        move    #>$0c000,r1
        move    #>$ffffff,m1
        move    #>$100001,a
        do      #1024,>xw1
        move    a,x:(r1)+
        add     #>$1,a
xw1:
        move    #>$0c000,r1
        move    #>$100001,b
        do      #1024,>xv1
        move    x:(r1)+,a
        move    a1,x0
        move    x0,a                    ; A2-clean before the compare
        move    b1,x0
        cmp     x0,a
        beq     xs1
        clr     a
        move    a,x:(r7+$10)            ; block 1 bad -> LEFT silent
xs1:
        add     #>$1,b
xv1:

; ---- block 2: same at 0x0F000 ---------------------------------------------
        move    #>$0f000,r1
        move    #>$200001,a
        do      #1024,>xw2
        move    a,x:(r1)+
        add     #>$1,a
xw2:
        move    #>$0f000,r1
        move    #>$200001,b
        do      #1024,>xv2
        move    x:(r1)+,a
        move    a1,x0
        move    x0,a
        move    b1,x0
        cmp     x0,a
        beq     xs2
        clr     a
        move    a,x:(r7+$11)            ; block 2 bad -> RIGHT silent
xs2:
        add     #>$1,b
xv2:
        move    x:(r7+$10),y0
        move    x:(r7+$11),y1
        move    #>$1,n0
        do      n7,>x_end
        move    x:(r0),x0
        mpy     x0,y0,a
        move    x:(r0+n0),x0
        mpy     x0,y1,b
        move    a,x:(r0)
        move    b,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
x_end:
        nop
        rts
