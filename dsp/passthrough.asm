; the null-effect stub, P:0x7c8 -- reassembled to validate the toolchain
; expected: 00000c 221100 06df00 0007cf 56d800 57d800 565900 575900 00000c
        rts                     ; init: do nothing
        move    r0,r1           ; process: copy input to output
        do      n7,>$7d0
        move    x:(r0)+,a
        move    x:(r0)+,b
        move    a,x:(r1)+
        move    b,x:(r1)+
        rts
