; ---------------------------------------------------------------------------
; Page-2 slot probe (BUS.md). Temporary diagnostic, NOT a shipping effect.
;
; DSP.md section 9 measured knob-LABEL -> r6 offset, never display-SLOT-INDEX
; -> offset. Two attempts to infer the slot mapping from the labels were both
; wrong, and produced page-2 knobs that did nothing. This settles it the same
; way section 9 settled the offsets originally: give each of the four real
; page-2 offsets a violently obvious and DISTINCT audible signature, flash
; once, sweep each page-2 knob, and read the mapping straight off the result.
;
;   r6+$6  turned past 64  ->  LEFT channel silent
;   r6+$7  turned past 64  ->  RIGHT channel silent
;   r6+$8  turned past 64  ->  BOTH silent
;   r6+$9  turned past 64  ->  half volume
;   r6+$a  turned past 64  ->  quarter volume
;
; v3. v1 measured slots 6/8/10 -> $b/$d/$e and found $c unreachable,
; leaving slots 7/9/11 unexplained. Stock FILTER has all six page-2
; slots live, so they must drive something -- and DSP.md section 9's
; 'r6+6..$a is touched by nothing, what lives there is unknown' is
; exactly five untested offsets. This probes those.
;
; Everything else is a plain passthrough, so an untouched knob leaves the
; track sounding normal. Gains are applied with mpy rather than branches so
; the per-sample loop stays branch-free -- branching inside a do loop is the
; kind of thing that hangs this chip.
; ---------------------------------------------------------------------------

init:
        rts

proc:
; v7. Slots 6 and 7 BOTH light r6+$c, so they share that word -- but in which
; fields? Split $c into its three candidate ranges, each with its own
; signature, and the answer falls out of which one each slot moves:
;   $c bits 16..22 (the knob field, $7f0000)  -> LEFT silent
;   $c bits  8..15 ($00ff00)                  -> RIGHT silent
;   $c bits  0..7  ($0000ff)                  -> BOTH silent
;   $e low bits (slot 11, known good)         -> half volume  [live control]
        move    #>$7fffff,a
        move    a,x:(r7+$10)
        move    a,x:(r7+$11)

        move    x:(r6+$e),a             ; control: slot 11 must still fire
        and     #>$00ffff,a
        move    a1,x0
        move    x0,a
        tst     a
        beq     p_ne
        move    #>$400000,a
        move    a,x:(r7+$10)
        move    a,x:(r7+$11)
p_ne:
        move    x:(r6+$c),a             ; $c knob field
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        tst     a
        beq     p_c1
        clr     a
        move    a,x:(r7+$10)
p_c1:
        move    x:(r6+$c),a             ; $c middle byte
        and     #>$00ff00,a
        move    a1,x0
        move    x0,a
        tst     a
        beq     p_c2
        clr     a
        move    a,x:(r7+$11)
p_c2:
        move    x:(r6+$c),a             ; $c low byte
        and     #>$0000ff,a
        move    a1,x0
        move    x0,a
        tst     a
        beq     p_c3
        clr     a
        move    a,x:(r7+$10)
        move    a,x:(r7+$11)
p_c3:
        move    x:(r7+$10),y0
        move    x:(r7+$11),y1
        move    #>$1,n0
        do      n7,>p_end
        move    x:(r0),x0
        mpy     x0,y0,a
        move    x:(r0+n0),x0
        mpy     x0,y1,b
        move    a,x:(r0)
        move    b,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
p_end:
        nop
        rts
