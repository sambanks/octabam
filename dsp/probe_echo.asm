; The simplest possible delay: a 40 ms slapback echo.
;
; Everything above this has assumed delay lines work. The FDN plays, writes
; land, and the tank is empty -- which is what you get if reads never return
; what was written. Rather than keep debugging a 4-line network, this tests one
; delay line doing one thing.
;
;   audible echo -> delay lines work; the bug is in the FDN itself
;   dry only     -> the delay read/write pair does not work, and the modulo
;                   addressing or the tap offset is wrong
;
; buffer X:0x9000 (2048 words, proven to persist), tap 1789 samples = 40 ms,
; phase at X:0xb000 (outside the buffer), feedback 0.5 so it repeats a few times.
init:
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m5
        rts

proc:
        move    x:>$b000,a              ; write phase, masked on load
        move    #>$7ff,x0
        and     x0,a
        move    #>$9000,x0
        add     x0,a
        move    a,r1
        move    #>$7ff,m1               ; 2048-word circular buffer
        move    #>$fff903,n1            ; -1789: read behind the write pointer
        move    r0,r5
        move    #>$ffffff,m5
        move    #>$400000,y0            ; 0.5 feedback

        do      n7,>eend
        move    x:(r1+n1),y1            ; the delayed sample
        move    x:(r0)+,a               ; L
        move    x:(r0)+,x1              ; R
        move    y1,x0
        mpy     x0,y0,b                 ; 0.5 * delayed
        add     a,b                     ; + input
        move    b,x:(r1)+               ; back into the line
        move    y1,x0
        add     x0,a                    ; L + delayed
        move    a,x:(r5)+
        move    x1,a
        add     x0,a                    ; R + delayed
        move    a,x:(r5)+
eend:
        move    r1,a                    ; save the phase
        move    #>$7ff,x0
        and     x0,a
        move    a,x:>$b000
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m5
        rts
