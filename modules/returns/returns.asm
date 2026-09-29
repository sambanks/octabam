; ---------------------------------------------------------------------------
; RETURNS: the bus returns' levels on T8's FX2, and the mixdown hook that
; adds them (docs/proposals/RETURNS.md; stage A the reverb, stage B the
; delay). Payload A (core 0) only.
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
;   x:$3e00..$3e1f  the reverb's buffer, 16 x (L, R) BusVerb -> mixhook
;                 (private X, 0x2900-0x3eff measured never written)
;   y:$e20        ALIVE, magic while RETURNS runs    RETURNS -> BusVerb
;   y:$e21        VRB, the knob word as published    RETURNS -> mixhook
;   y:$e22        FRESH, magic once the buffer is new BusVerb -> mixhook
;   y:$e23        the gain, glided                  mixhook only
;   y:$e25        DLY, the knob word as published    RETURNS -> mixhook
;   y:$e26        the delay's gain, glided          mixhook only
;
; Shared window (core 1 -> core 0; BusDelay writes, spelled bus+n there and
; relocated by the build; absolute here, and the build refuses RETURNS with
; the bus anywhere but $36000):
;   y:$36200..$362ff  8 buffers x 16 x (L, R): the delay's wet, written at
;                     its write rotation (read here as x:, the window
;                     aliases X and Y, measured on hardware, CHIP.md)
;   y:$36300..$36307  per buffer: $5a0000 | write offset once written;
;                     cleared by mixhook after it adds the buffer
;   y:$36308          ALIVE_D: RETURNS stamps it every block; BusDelay
;                     reads and clears it with 3 blocks of grace
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
        clr     a                       ; the gains start at zero: the first
        move    a,y:>$e23               ; returns fade in
        move    a,y:>$e26
        rts

proc:
        move    r7,a
        move    #>$6b00,x0
        cmp     x0,a
        bne     rtn_skip                ; not T8's FX2 on core 0
        move    x:(r6),a                ; VRB, page-1 slot 0
        move    a,y:>$e21
        move    x:(r6+$1),a             ; DLY, page-1 slot 1
        move    a,y:>$e25
        move    #>$5a5a5a,x0
        move    x0,y:>$e20              ; ALIVE (BusVerb, core 0)
        move    x0,y:>$36308            ; ALIVE_D (BusDelay, core 1)
rtn_skip:
        rts

mixhook:
; ---- the reverb: the buffer BusVerb marked fresh (y:$e22) ------------------
        move    y:>$e22,a               ; FRESH?
        cmp     #>$5a5a5a,a
        bne     mh_dly
        clr     a
        move    a,y:>$e22               ; consumed
        move    y:>$e21,a               ; VRB
        move    #>$e23,r1               ; its glided gain
        bsr     mh_gain
        move    #>$3e00,r0              ; the reverb's buffer (private X)
        bsr     mh_add
; ---- the delay: the buffer three back of the rotation core 0 sees, if its
; stamp says BusDelay wrote it (y:$36300 + index = $5a0000 | offset) -------
mh_dly:
        move    y:>$36000,a             ; the rotation (the housekeeper flips
        add     #>$50,a                 ; it later in this frame): three
        and     #>$70,a                 ; buffers back, as the servers read
        move    a,x1                    ; x1 = the offset, 0..112 (the word is
                                        ; always stored masked: A2 is clean)
        asr     #$4,a,a                 ; the buffer's index
        add     #>$36300,a
        move    a,r1                    ; its stamp word
        move    #>$5a0000,a
        add     x1,a                    ; the stamp it must carry
        move    a,x0
        move    y:(r1),a
        cmp     x0,a
        bne     mh_end                  ; not written for this read: nothing
        clr     a
        move    a,y:(r1)                ; consumed
        move    x1,a
        asl     a                       ; stereo: 2 words a frame
        add     #>$36200,a
        move    a,r0                    ; the buffer
        move    y:>$e25,a               ; DLY
        move    #>$e26,r1               ; its glided gain
        bsr     mh_gain
        bsr     mh_add
mh_end:
        move    x:>$206,r0              ; the displaced instruction
        rts

; ---- mh_gain: a = the knob word, r1 -> the glided gain; out x0 = this
; block's gain, (knob/128)^2 approached a quarter of the way per block.
; Clobbers a, b, x0, y1. r0 untouched.
mh_gain:
        and     #>$7f0000,a             ; the knob: bits 16-22, value/128
        move    a1,x0
        mpy     x0,x0,a                 ; (value/128)^2, the target
        move    y:(r1),b                ; the gain as it stands
        and     #>$7fffff,b             ; never negative (boot word masked)
        move    b1,y1
        sub     y1,a                    ; target - gain
        asr     #$2,a,a                 ; a quarter
        add     y1,a
        move    a,y:(r1)
        move    a,x0
        rts

; ---- mh_add: add x0 x the 16 stereo frames at x:(r0) where MASTER TRACK
; says: T8's record (on: bit 10 of T8's word $7e, raw scale, before T8's
; chain) or MAIN, ring words 2/3 of x:>$203 at 8 a frame (off: x 0.5618,
; the plain mode's track gain, then the mixdown's x4). Clobbers a, b, x0,
; y0, y1, r0, r1.
mh_add:
        move    x:>$207,a               ; this bank's record base
        add     #>$7e,a
        move    a,r1
        move    x:(r1),a                ; T8's record word $7e
        btst    #$a,a                   ; MASTER TRACK -> C (stock tests the
        bcs     mh_master               ; same bit with brset at P:$257; the
                                        ; assembler encodes brset/brclr with
                                        ; an ABSOLUTE target, AGENTS.md)
        move    #>$47e9ff,y1            ; 0.5618
        mpy     x0,y1,a                 ; gain x 0.5618 (both positive)
        move    a,x0
        move    x:>$203,a
        add     #>$2,a
        move    a,r1
        do      #<$10,>mh_plain
        move    x:(r0)+,y0              ; wet L
        mpy     y0,x0,b
        asl     #$2,b,b                 ; the mixdown's x4
        move    x:(r1),a
        add     b,a
        move    a,x:(r1)+               ; MAIN L (the store limits)
        move    x:(r0)+,y0              ; wet R
        mpy     y0,x0,b
        asl     #$2,b,b
        move    x:(r1),a
        add     b,a
        move    a,x:(r1)+               ; MAIN R
        lua     (r1+$6),r1              ; the next frame's words 2/3
mh_plain:
        rts
mh_master:
        move    x:>$209,a
        add     #>$1f8,a
        move    a,r1                    ; T8's record: 16 x (L, R)
        do      #<$20,>mh_rec
        move    x:(r0)+,y0              ; wet
        move    x:(r1),a
        mac     y0,x0,a
        move    a,x:(r1)+
mh_rec:
        rts
