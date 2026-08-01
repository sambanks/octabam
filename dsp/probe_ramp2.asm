; Which state locations survive between proc calls? Two at once, one per channel.
;
; X:0xb000 does NOT persist (high buzz), yet X:0x9000 appeared to (steady
; distortion when read back each frame). So the persistent region is narrower
; than assumed and our delay buffers, at 0x9000-0xafff, may straddle its edge.
;
; This runs two independent counters and sends one to each channel:
;
;   LEFT  = counter kept at r7+$50      (the per-instance state block)
;   RIGHT = counter kept at X:0x9000    (proven to hold a value across frames)
;
; low tone (~86 Hz) on a channel -> that location carries between calls
; high buzz (~5.5 kHz)           -> it does not
;
; One flash answers both, and tells us where the reverb's phase should live.
init:
        move    #>$ffffff,m0
        move    #>$ffffff,m5
        rts

proc:
        move    r0,r5
        move    #>$ffffff,m5
        move    #>$8000,x0
        move    x:(r7+$50),a            ; LEFT counter  -- r7 state block
        move    x:>$9000,b              ; RIGHT counter -- absolute X
        do      n7,>rend
        add     x0,a
        add     x0,b
        move    a,x:(r5)+               ; L
        move    b,x:(r5)+               ; R
rend:
        move    a,x:(r7+$50)
        move    b,x:>$9000
        move    #>$ffffff,m0
        move    #>$ffffff,m5
        rts
