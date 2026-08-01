; Does X:0x9000 survive from one frame to the next?
;
; The four-bases probe appeared to prove this, but its INIT wrote the values --
; and init turns out to run repeatedly, refreshing them every frame. So that
; test showed nothing about persistence, and the reverb's tank staying empty is
; consistent with the delay buffers being overwritten between calls.
;
; This tests it using proc alone: read what we left last frame, use it as the
; audio mask, then leave it again.
;
;   steady heavy distortion -> the location persists; the reverb's problem is
;                              its own state (r7), not the buffers
;   clean / noise / silence -> X:0x9000 does NOT survive between frames, and the
;                              delay lines must live somewhere else
init:
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        rts

proc:
        move    x:>$9000,y0             ; what we left last frame
        move    #>$e00000,x0
        move    x0,x:>$9000             ; leave it again
        move    r0,r1
        do      n7,>pend
        move    x:(r0)+,a
        move    x:(r0)+,b
        and     y0,a
        and     y0,b
        move    a,x:(r1)+
        move    b,x:(r1)+
pend:
        rts
