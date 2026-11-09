; ---------------------------------------------------------------------------
; DLSTUB -- the lazy-binding stub in front of the demand-loaded effects
; (docs/contributing/DEMAND_LOADER.md). One body serves them all; the build adds a
; trampoline per effect where the marker below is.
;
; Each effect's id dispatches to the stub. While the real code is not resident the
; stub passes the audio through (the stock null stub's loop). Once DLCOPY has
; published the code, each instance runs the real init once, with the proc's
; registers kept, and from then on jumps to the real proc. Every path that selects
; an effect ends in INIT[id] and PROCESS[id], so nothing on the ColdFire side has to
; guard the setters.
;
; INIT[id] is `init` for every effect (it only clears the instance's flag).
; PROCESS[id] is the effect's trampoline, which leaves the effect's entry address in
; x:$3f4c and enters `proc`. The entry, x:$33da3 + 8 k (DLCOPY writes it):
;   +0 BOUND  $b0a5ed when the code is resident, anything else if not
;   +1 the real init   +2 the real proc
; Per core (X, private): x:$3f00..$3f3f one word per instance, 1 once its init
; has run; x:$3f40..$3f4c the registers kept across the init, the entry a and the entry.
; ---------------------------------------------------------------------------

init:
        move    r7,a
        asr     #$8,a,a
        and     #>$3f,a
        move    #>$3f00,x0
        add     x0,a
        move    a1,r2
        clr     a
        move    a,x:(r2)                 ; this instance has not run the real init
        rts

; TRAMPOLINES
proc:
        move    a1,x:>$3f4b              ; proc is called with a = 0 or 1 in a: kept for the real code
        move    x:>$3f4c,r2
        move    x:(r2),a
        cmp     #>$b0a5ed,a
        bne     dl_pass
        move    r7,a
        asr     #$8,a,a
        and     #>$3f,a
        move    #>$3f00,x0
        add     x0,a
        move    a1,r2
        move    x:(r2),a
        tst     a
        bne     dl_run
        move    r2,x:>$3f4a
        move    r0,x:>$3f40
        move    n0,x:>$3f41
        move    r6,x:>$3f42
        move    r7,x:>$3f43
        move    n7,x:>$3f44
        move    m0,x:>$3f45
        move    m1,x:>$3f46
        move    x:>$3f4c,r2
        move    x:(r2+1),r2
        jsr     (r2)
        move    x:>$3f40,r0
        move    x:>$3f41,n0
        move    x:>$3f42,r6
        move    x:>$3f43,r7
        move    x:>$3f44,n7
        move    x:>$3f45,m0
        move    x:>$3f46,m1
        move    x:>$3f4a,r2
        move    #>$1,x0
        move    x0,x:(r2)
dl_run:
        move    x:>$3f4b,a
        move    x:>$3f4c,r2
        move    x:(r2+2),r2
        jmp     (r2)
dl_pass:
        move    r0,r1
        do      n7,>dl_end
        move    x:(r0)+,a
        move    x:(r0)+,b
        move    a,x:(r1)+
        move    b,x:(r1)+
dl_end:
        rts
