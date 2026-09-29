; ---------------------------------------------------------------------------
; RETURNS: the bus returns' levels on T8's FX2, and the mixdown hook that
; adds them (docs/proposals/RETURNS.md). Payload A (core 0) only.
;
; proc, on T8's FX2 (r7 == $6b00): the audio block is left alone; page-1
; slot 0 (VRB) is published to y:$e21 and the magic word to y:$e20, which
; tells BusVerb to print into the buffer instead of onto T5. Anywhere else
; RETURNS does nothing at all.
;
; mixhook, at P:$2d5 (`move x:>$206,r0`, replayed): if BusVerb marked the
; buffer fresh (y:$e22 == magic), clear the mark, glide the gain toward
; (VRB/128)^2 and add gain x buffer into T8's record (MASTER TRACK on: bit
; 10 of T8's record word $7e, the stock test at P:$257) or into MAIN, ring
; words 2/3 of x:>$203 at 8 per sample (off), x 0.5618 x 4 there: the mix
; gain the firmware gives a track at the same LEVEL in each mode (measured
; under the port, 29 Sep 2026, LEVEL 55: 0x17a180 on, 0xd4ad0 off).
;
; Private Y, core 0 (claimed by BusVerb, which owns the print buffer):
;   y:$e00..$e1f  the buffer, 16 x (L, R)          BusVerb -> mixhook
;   y:$e20        ALIVE, magic while RETURNS runs    RETURNS -> BusVerb
;   y:$e21        VRB, the knob word as published    RETURNS -> mixhook
;   y:$e22        FRESH, magic once the buffer is new BusVerb -> mixhook
;   y:$e23        the gain, glided                  mixhook only
;
; At P:$2d5 the stock code that follows reloads r0, n0, r1, n1 and every data
; ALU register before it reads them (func P:$55a, then P:$2ec..); m0 is
; linear (P:$28f / P:$2d3), m1 is linear by convention. mixhook uses r0,
; r1, n0 and the data ALU only. Every form has a stock site in payload A.
; ---------------------------------------------------------------------------

; The proc has no per-sample loop: it publishes the knob once per call
; (tools/build/cycle_count.py prices it at zero per sample on this marker).
; NO SAMPLE LOOP

init:
        clr     a                       ; the gain starts at zero: the first
        move    a,y:>$e23               ; return fades in
        rts

proc:
        move    r7,a
        move    #>$6b00,x0
        cmp     x0,a
        bne     rtn_skip                ; not T8's FX2 on core 0
        move    x:(r6),a                ; VRB, page-1 slot 0
        move    a,y:>$e21
        move    #>$5a5a5a,x0
        move    x0,y:>$e20              ; ALIVE
rtn_skip:
        rts

mixhook:
        move    y:>$e22,a               ; FRESH?
        move    #>$5a5a5a,x0
        cmp     x0,a
        bne     mh_end
        clr     a
        move    a,y:>$e22               ; consumed
; ---- the gain: (VRB/128)^2, glided a quarter of the way per block --------
        move    y:>$e21,a
        and     #>$7f0000,a             ; the knob: bits 16-22, VRB/128
        move    a1,x0
        mpy     x0,x0,a                 ; (VRB/128)^2
        move    a,x1                    ; target
        move    y:>$e23,a               ; the gain as it stands
        and     #>$7fffff,a             ; never negative (boot word masked)
        move    a1,y1
        move    x1,a
        sub     y1,a                    ; target - gain
        asr     #$2,a,a                 ; a quarter
        add     y1,a
        move    a,y:>$e23
        move    a,x0                    ; x0 = this block's gain
; ---- where: T8's record (MASTER TRACK on) or MAIN (off) -------------------
        move    x:>$207,a               ; this bank's record base
        add     #>$7e,a
        move    a,r1
        move    #>$e00,r0
        move    x:(r1),a                ; T8's record word $7e
        btst    #$a,a                   ; MASTER TRACK -> C (stock tests the
        bcs     mh_master               ; same bit with brset at P:$257; the
                                        ; assembler encodes brset/brclr with
                                        ; an ABSOLUTE target where the chip
                                        ; takes a displacement, 29 Sep 2026)
; ---- off: MAIN, ring words 2/3, 8 per sample, after the mixdown's x4 ------
        move    #>$47e9ff,y1            ; 0.5618: the plain mode's track gain
        mpy     x0,y1,a                 ; gain x 0.5618 (both positive)
        move    a,x0
        move    x:>$203,a
        add     #>$2,a
        move    a,r1
        do      #<$10,>mh_plain
        move    y:(r0)+,y0              ; wet L
        mpy     y0,x0,b
        asl     #$2,b,b                 ; the mixdown's x4
        move    x:(r1),a
        add     b,a
        move    a,x:(r1)+               ; MAIN L (the store limits)
        move    y:(r0)+,y0              ; wet R
        mpy     y0,x0,b
        asl     #$2,b,b
        move    x:(r1),a
        add     b,a
        move    a,x:(r1)+               ; MAIN R
        lua     (r1+$6),r1              ; the next sample's words 2/3
mh_plain:
        bra     mh_end
; ---- on: T8's record, raw (the master sum has no x4), before T8's chain ---
mh_master:
        move    x:>$209,a
        move    #>$1f8,x1
        add     x1,a
        move    a,r1                    ; T8's record: 16 x (L, R)
        do      #<$20,>mh_rec
        move    y:(r0)+,y0              ; wet
        move    x:(r1),a
        mac     y0,x0,a
        move    a,x:(r1)+
mh_rec:
mh_end:
        move    x:>$206,r0              ; the displaced instruction
        rts
