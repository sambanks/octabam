; X-memory probe effect.
;
; Question: is X:0x08d98..0x0ffff (29,288 words / 664 ms) real memory? It is
; unreferenced anywhere in the firmware, and if it exists a new reverb can have
; several times the stock delay allocation.
;
; The answer has to be audible, so: write a pattern high in X, read it back, and
; bitcrush the audio by an amount that says which addresses survived.
;
;   heavy crush (3-bit, obviously nasty)  -> X:0xf000 works, so X RAM reaches 64K
;   mild crush  (6-bit, clearly dirty)    -> X:0xa000 works but 0xf000 does not
;   clean audio (unchanged)               -> neither works, X RAM ends below 0xa000
;
; Audio follows the passthrough stub's convention (r0 = interleaved stereo block
; processed in place, n7 = frame count), which is proven to work on hardware --
; it is what an unimplemented effect id does, and selecting DELAY on FX1 audibly
; passed signal through unchanged.
;
; This is also the first custom code through the whole pipeline: assemble ->
; insert as a module -> point dispatch entries at it -> ColdFire descriptor ->
; flash. ~20 instructions of risk instead of a thousand-word reverb.

; ---------------------------------------------------------------- init --------
; Called when the effect id changes. Stamp both probe addresses.
init:
        move    #>$5a5a5a,x0
        move    x0,x:>$a000
        move    #>$a5a5a5,x0
        move    x0,x:>$f000
        rts

; ------------------------------------------------------------- process --------
; Called every frame.
proc:
        move    x:>$f000,a              ; did the high probe survive?
        move    #>$a5a5a5,x0
        cmp     x0,a
        beq     heavy
        move    x:>$a000,a              ; did the mid probe survive?
        move    #>$5a5a5a,x0
        cmp     x0,a
        beq     mild
        move    #>$ffffff,y0            ; neither: pass through unchanged
        bra     run
mild:
        move    #>$fc0000,y0            ; 6-bit
        bra     run
heavy:
        move    #>$e00000,y0            ; 3-bit
run:
        move    r0,r1
        do      n7,>loopend     ; label goes AFTER the last loop instruction,
        move    x:(r0)+,a       ; as the stock stub does (do n7,>$7d0 with the
        move    x:(r0)+,b       ; rts at $7d0) -- otherwise the final store falls
        and     y0,a            ; outside the loop and r0/r1 diverge
        and     y0,b
        move    a,x:(r1)+
        move    b,x:(r1)+
loopend:
        rts
