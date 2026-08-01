; Which state location persists? Corrected test.
;
; The previous version let the counter accumulate in a 56-bit accumulator with no
; masking, so it saturated at full scale and stayed there -- a persisting counter
; produced silent DC rather than a tone, which is not distinguishable by ear from
; a dead channel. This masks the counter every sample so it wraps into a clean
; sawtooth whatever happens.
;
;   LEFT  = counter at r7+$50    (per-instance state block)
;   RIGHT = counter at X:0x9000  (absolute)
;
;   low tone (~86 Hz)    -> carries between calls
;   high buzz (~5.5 kHz) -> resets every block
;   silence              -> now genuinely means the location is unreadable,
;                           rather than an artefact of saturation
init:
        move    #>$ffffff,m0
        move    #>$ffffff,m5
        rts

proc:
        move    r0,r5
        move    #>$ffffff,m5
        move    #>$8000,x0              ; step: wraps every 512 samples
        move    #>$7fffff,x1            ; mask: keeps the counter in range so it
                                        ; wraps instead of saturating
        move    x:(r7+$50),a
        move    x:>$9000,b
        and     x1,a                    ; sanitise whatever was there
        and     x1,b
        do      n7,>rend
        add     x0,a
        and     x1,a
        add     x0,b
        and     x1,b
        move    a,x:(r5)+               ; L
        move    b,x:(r5)+               ; R
rend:
        move    a,x:(r7+$50)
        move    b,x:>$9000
        move    #>$ffffff,m0
        move    #>$ffffff,m5
        rts
