; ---------------------------------------------------------------------------
; What does the host actually hand the SECOND instance?
;
; r7 has only ever been measured with one instance (dsp/r7probe.asm returned 98,
; so r7 = 0x6200). The base has only been measured in one project's FX layout
; (dsp/baseprobe.asm returned 32 and 64). Everything since has assumed those
; generalise: that r7 steps by 0x100 and that the second reverb lands on an FX2
; slot. Five builds have now been designed around those assumptions and all five
; hang, so measure them in the configuration that actually fails.
;
; One build, two readings, selected by the HI knob:
;
;   HI <  64   pass audio when TIME == r7 >> 8
;   HI >= 64   pass audio when TIME == base >> 9   (base from the init stash)
;
; Sweep TIME on each track and note where sound appears. Expected if every
; assumption holds:
;
;   track 1   HI low -> 98 (r7 0x6200)    HI high -> 32 (base 0x4000)
;   track 2   HI low -> 100 (r7 0x6400)   HI high -> 64 (base 0x8000)
;
; Anything else is the answer. Two tracks reporting the SAME value means they
; share that resource. Nothing anywhere on the HI-high sweep means the stash did
; not survive, which is equally decisive.
;
; It writes one word of Y in init and nothing else, ever. It cannot hang for any
; of the reasons the reverb has been hanging.
; ---------------------------------------------------------------------------

init:
        move    x:>$213,r4
        move    r7,a
        asr     #$8,a,a                 ; r7 >> 8; also fills the AGU slot
        move    x:(r4),x0               ; this instance's base
        move    #>$800,y0               ; 0x800, not 0x735: the old window is
        add     y0,a                    ; inside a loaded module on payload B
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

; ---- default reading: r7 >> 8 -------------------------------------------
        move    r7,a
        asr     #$8,a,a

; ---- HI >= 64 switches to the stashed base >> 9 -------------------------
        move    x:(r6+$1),b
        asr     #$10,b,b
        move    #>64,x0
        cmp     x0,b
        blt     have

        move    r7,b
        asr     #$8,b,b
        move    #>$800,y0
        add     y0,b
        move    b,r5
        move    #>$ffffff,m5            ; two instructions between r5 and its use
        move    #>$ffffff,m0
        move    y:(r5),a                ; the base init stashed for us
        asr     #$9,a,a

have:
; ---- pass audio only when TIME matches the reading ----------------------
        move    x:(r6),b
        asr     #$10,b,b
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
