; ---------------------------------------------------------------------------
; BUS.md task 12 probe: does a "server" that never reads x:0x213 at all, and
; just hardcodes its buffer base as a literal, stay inside its own window
; regardless of which table entry the dispatcher actually handed it?
;
; This stands in for REVERB SERVER's planned base (Y:0x4000, 32K, spans two
; stock FX2 slots -- 0x4000..0x7fff and 0x8000..0xbfff). init clears the
; whole window once; proc touches both ends of it every block (first word and
; last word) plus passes audio through unchanged, so a guard run can see
; writes at the far edge of the claimed 32K, not just near the base.
;
; No stash, no read of x:>$213 anywhere -- that absence is the entire point.
; Run alongside dsp/minimal.asm (already hardware-proven zero-footprint) as
; the second instance, on whatever alloc index its real table entry gives it
; (e.g. 3, base 0x8000 -- squarely inside this probe's 32K window), to show
; the two coexist without collision: this probe only ever touches the window
; it hardcodes, and minimal.asm never touches its own base at all.
; ---------------------------------------------------------------------------

; BASE = $4000, TOP = $7fff (last word offset of the 32K window) -- inlined
; below, the assembler has no equ/macro support.

init:
        move    #>$4000,r1
        move    #>$ffffff,m1            ; linear, for the one-time clear
        move    #>$8000,x0              ; 32768 words
        clr     a
        do      x0,>iclr
        move    a,y:(r1)+
iclr:
        rts

proc:
        move    #>$4000,r4
        move    #>$7fff,x0
        move    r4,a
        add     x0,a
        move    a,r5                    ; r5 = BASE + TOP, the far edge

        move    x:(r7+$50),a            ; a free-running counter, so the
        add     #>1,a                   ;   guard sees changing values, not
        move    a,x:(r7+$50)            ;   a write-once no-op
        move    a,y:(r4)
        move    a,y:(r5)

        move    r0,r1
        do      n7,>pend
        move    x:(r0)+,a
        move    x:(r0)+,b
        move    a,x:(r1)+
        move    b,x:(r1)+
pend:
        rts
