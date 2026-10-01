; DOOM, DSP side: Doom's sound added into MAIN L/R after the mixdown.
;
; Placed by the build in payload A's donor region and reached right after
; the mixdown: P:$2d5's `move x:>$206,r0` becomes `jsr >doomsnd`
; (schema.DspHook) and is replayed at the end. The mixdown (P:$238..$2d4,
; both the plain and the MASTER TRACK paths end here) has just written this
; frame's 16 samples into the ring half at x:>$203, eight words a sample:
; words 0/1 the cue bus, 2/3 MAIN L/R (git show 666b6154:docs/firmware/COLDFIRE_PORT.md O23,
; "the buffer map"). Doom's pair is added into words 2/3 with the store's
; limiter, so it is on MAIN whatever the mixer says, and in what the
; recorder's MAIN source and the cue mix read after this point.
;
; The ColdFire's frame transfer (doom_audio.c via entry.S's state-7 shim,
; USB AUDIO IN's mechanism) lands 64 halfwords at the working bank's +$320:
; word 0 = 1 while Doom's sound runs, then 16 x (L, R), 16-bit signed. The
; top byte of a host word is stale, so each is shifted up 8 and a1 kept.
;
; Live at P:$2d5: nothing this uses -- r0/n0/r1/n1 are reloaded by the
; next four instructions, m0 was just made linear, a/b/x0 are dead after
; the mixdown's stores. Every form has a stock site in payload A:
; move x:>$20n,a; move x:(r0)+,a; and #>$ff,a; asl #$8,a,a; move a1,x0;
; move x:(r1),a; add x0,a; move a,x:(r1)+; move (r1)+n1 (P:$2d2);
; add #>n,a / move a,r0 ran on Bryan T's unit as usbin-test's inject.

doomsnd:
        move    x:>$207,a               ; the working bank (the bank take's r6)
        add     #>$320,a
        move    a,r0
        move    x:(r0)+,a               ; word 0: 1 while Doom sounds
        and     #>$ff,a
        beq     dsnd_out
        move    x:>$203,r1              ; this frame's ring half
        move    #$6,n1
        move    (r1)+
        move    (r1)+                   ; word 2: MAIN L of sample 0
        do      #16,dsnd_out
        move    x:(r0)+,a               ; Doom L
        asl     #8,a,a
        move    a1,x0
        move    x:(r1),a
        add     x0,a
        move    a,x:(r1)+               ; MAIN L + Doom L, limited
        move    x:(r0)+,a               ; Doom R
        asl     #8,a,a
        move    a1,x0
        move    x:(r1),a
        add     x0,a
        move    a,x:(r1)+               ; MAIN R + Doom R
        move    (r1)+n1                 ; the next sample's word 2
dsnd_out:
        move    x:>$206,r0              ; the displaced instruction
        rts
