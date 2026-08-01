; ---------------------------------------------------------------------------
; base probe -- read the per-instance buffer base off the hardware, and test the
; mechanism for carrying it from init into process at the same time.
;
; The r7 probe returned 98, so r7 = 0x6200 and r7 IS 0x6000-based. But index 2
; gives table[2] = 0x1c00, which is a 3072-word FX1 slot; a 16K layout starting
; there runs to 0x53ff, through the other FX1 buffers and into FX2 slot 0. That
; is the noise. The two pointers advance together but the index does not map
; straight across -- FX2 effects do not take even table entries.
;
; Rather than deduce the mapping from the dispatcher listing again (which is what
; produced the wrong formula), measure it.
;
; X:0x213 is only valid during init -- that is where the stock reverbs read it.
; The problem has always been getting the value from there to process, because
; only ONE r7 word persists and the tank phase needs it. This probe uses the
; trick the reverb will use if it works: stash the base in absolute Y at an
; address that is unique per instance,
;
;     Y:(0x735 + (r7 >> 8))       ->  0x795..0x79d for r7 = 0x6000..0x6800
;
; which lands in the free window above the loaded coefficient module at
; 0x715..0x794, and below the FX1 buffers at 0x1000. One word per instance, so
; instances do not collide even though the address is absolute.
;
; init stashes the base; process reads it back and passes audio only when the
; TIME knob equals base >> 9:
;
;     32 -> base 0x4000      14 -> 0x1c00      8 -> 0x1000
;     64 -> base 0x8000      20 -> 0x2800     26 -> 0x3400
;
; Silence across the whole sweep means the stash did not survive, which is just
; as useful to know.
; ---------------------------------------------------------------------------

init:
        move    x:>$213,r4
        move    r7,a
        asr     #$8,a,a                 ; r7 >> 8; also fills the AGU slot
        move    x:(r4),x0               ; this instance's base
        move    #>$735,y0
        add     y0,a
        move    a,r5                    ; unique stash address
        move    #>$ffffff,m5
        move    #>$ffffff,m0
        move    x0,y:(r5)
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        rts

proc:
        move    #>$ffffff,m0
        move    #>$ffffff,m5

; ---- read the stashed base ----------------------------------------------
        move    r7,a
        asr     #$8,a,a
        move    #>$735,y0
        add     y0,a
        move    a,r5
        move    x:(r6),b                ; TIME, value<<16
        asr     #$10,b,b                ; -> 0..127
        move    y:(r5),a                ; the base we stashed in init
        asr     #$9,a,a                 ; base >> 9
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
