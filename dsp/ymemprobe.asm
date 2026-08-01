; ---------------------------------------------------------------------------
; Y memory extent probe -- one build, the whole map, swept by the TIME knob
;
; Y:0x800..0x27ff is proven working. The reverb's tank lines are only 1024 words
; each, which is short enough that at long decay times the density is doing work
; that length should be doing. Before adding SIZE or lengthening the lines we
; need to know how far Y actually goes.
;
; No bus configuration to read: the AAR/BCR-looking constants in the stock DSP
; code ($fffffb, $fffff6) turn out to be negative N-register offsets, not
; peripheral writes. So this is measured, not deduced.
;
; The probe is a wet-only echo whose buffer moves with p0:
;
;     base = (p0 + 1) << 12        p0=0 -> Y:0x1000 ... p0=127 -> Y:0x80000
;
; Second sweep, coarser and much further out. The first one stepped 1024 words
; and stopped at 0x20000, which was enough to find the end of the low region at
; 0xC000 -- but the host's own allocator table hands out bases at 0x30000 and
; 0x34000 (and 0x38000/0x3c000 in payload B), so there is a second region we
; have never characterised. This steps 4096 and reaches 0x80000.
;
; 1024 words at base, tap 1000 (~23 ms), feedback 0.5, and the OUTPUT IS WET
; ONLY. That makes it a clean yes/no rather than a judgement call:
;
;     clear repeating echo  ->  that page is real and persists
;     silence               ->  reads back zero: no memory there
;     noise / breakup       ->  something else lives there, or it aliases
;     hang                  ->  it aliased onto loaded module memory
;
; Reference points: p0=3 is Y:0x4000 (known good, an FX2 slot), p0=10 is 0xB000
; (the last known-good page), p0=11 is 0xC000 (known absent), p0=47 is 0x30000
; and p0=63 is 0x40000. What matters is whether the echo comes BACK anywhere
; above p0=11.
;
; Addressing is v13's: computed, masked, no modulo and no N register, which is
; the only style proven not to hang.
;
; State:  r7+$70 base   r7+$71 phase   r7+$72 delayed   r7+$73 write value
;         r7+$83 persistent phase
; ---------------------------------------------------------------------------

init:
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts

proc:
        move    #>$ffffff,m0
        move    #>$ffffff,m5

; ---- base = (p0 + 1) << 10 ----------------------------------------------
; p0 arrives as value<<16, so shift it back down first.
        move    x:(r6),a
        asr     #$10,a,a                ; a1 = p0, 0..127
        move    #>$1,x0
        add     x0,a
        asl     #$c,a,a                 ; (p0+1) * 4096
        move    a,x:(r7+$70)

; ---- phase, masked on LOAD as well as on save ---------------------------
        move    x:(r7+$83),a
        move    #>$3ff,x0
        and     x0,a
        move    a,x:(r7+$71)

        do      n7,>pend

; ---- read the delayed sample: base + ((phase + 24) & $3ff), tap 1000 ----
        move    x:(r7+$71),a
        move    #>$18,x0
        add     x0,a
        move    #>$3ff,x0
        and     x0,a
        move    x:(r7+$70),x0
        add     x0,a
        move    a,r5
        move    #>$400000,y0            ; feedback 0.5, and fills the AGU slot
        move    #>$1,n0                 ; also fills the AGU slot
        move    y:(r5),a
        move    a,x:(r7+$72)            ; delayed

; ---- mono input ---------------------------------------------------------
        move    x:(r0),b
        move    x:(r0+n0),x0
        add     x0,b
        asr     #$1,b,b

; ---- write = in + 0.5 * delayed -----------------------------------------
        move    x:(r7+$72),x0
        mpy     x0,y0,a
        add     b,a
        move    a,x:(r7+$73)

; ---- write it at base + phase -------------------------------------------
        move    x:(r7+$71),a
        move    x:(r7+$70),x0
        add     x0,a
        move    a,r5
        move    x:(r7+$73),a            ; both of these fill the AGU slot
        move    x:(r7+$72),b
        move    a,y:(r5)

; ---- WET ONLY, both channels: silence is a real answer -------------------
        move    b,x:(r0)
        move    b,x:(r0+n0)

; ---- advance the phase and the audio pointer ----------------------------
        move    x:(r7+$71),a
        move    #>$1,x0
        add     x0,a
        move    #>$3ff,x0
        and     x0,a
        move    a,x:(r7+$71)
        move    #>$2,n0
        move    (r0)+n0                 ; one stereo frame
pend:

        move    x:(r7+$71),a
        move    a,x:(r7+$83)
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts
