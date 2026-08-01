; ---------------------------------------------------------------------------
; r7 probe -- read the actual per-instance state pointer off the hardware
;
; The per-instance buffer base was being derived as
;
;     n = (r7 - 0x6000) >> 8        base = x:(0x255 + n)
;
; on the reasoning that the dispatcher advances X:0x20a (state blocks, 0x100
; apart) and X:0x213 (buffer bases, 1 apart) in lockstep. Bisection says that is
; wrong: v29, identical except with the base hardcoded to Y:0x4000, is clean,
; while v28 with the derivation is noise from boot.
;
; Every value in that formula was READ OUT OF THE IMAGE, not measured. X:0x20a's
; initial value of 0x6000 comes from an immediate in P:0x002bf; whether r7 is
; actually 0x6000 + n*0x100 at the moment our effect runs has never been checked.
;
; So check it. The effect passes audio ONLY when the TIME knob equals r7 >> 8:
;
;     sweep TIME, note where sound appears  ->  that value IS r7 >> 8
;
; r7 = 0x6100 would show at 97, r7 = 0x6200 at 98, and so on. Anything else, or
; nothing at all across the whole sweep, means the assumption is wrong and by how
; much. Dry passes through on a match, so this is unambiguous: silence everywhere
; except one knob position.
;
; No buffers, no state, nothing persistent -- it cannot fail for any of the
; reasons the reverb has been failing.
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

; ---- compare r7 >> 8 against the TIME knob ------------------------------
        move    r7,a
        asr     #$8,a,a                 ; r7 >> 8
        move    x:(r6),b                ; TIME arrives as value<<16
        asr     #$10,b,b                ; -> 0..127
        move    b,x0
        cmp     x0,a
        beq     match

; ---- no match: silence the block ----------------------------------------
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
