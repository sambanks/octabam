; dsp/silence_stub.asm -- DIAGNOSTIC ONLY, never part of a flashable product.
;
; WHY THIS EXISTS. Stock Echo Freeze Delay is a normal per-track FX2 effect,
; its descriptor carries id 0x08, and id 0x08 dispatches to the stock NULL STUB
; at P:0x007c8 -- which is a passthrough, not silence. Three rounds of static
; search have failed to find anything on either processor that does something
; audible with that id (DSP.md 5). So we ask the running machine instead.
;
; This is the stock stub's exact shape, writing ZEROS where it wrote the input:
;
;     0007c9: move r0,r1        proc: output buffer = input buffer
;     0007ca: do   n7,>$7d0
;     0007cc: move x:(r0)+,a
;     0007cd: move x:(r0)+,b    two interleaved channels
;     0007ce: move a,x:(r1)+
;     0007cf: move b,x:(r1)+
;     0007d0: rts
;
; The reads are KEPT so r0 advances exactly as stock does; only the two stores
; change. That keeps the one variable under test to "what lands in the buffer".
;
; WHAT EACH OUTCOME MEANS, with id 0x08 pointed here and DELAY on FX2:
;
;   delay still sounds       -> its audio does not flow through the FX2 insert.
;                               The insert is dead weight and OUR code can take
;                               id 0x08's slot and keep the delay (BUS.md, the
;                               parked Send design).
;   everything goes silent   -> the passthrough is load-bearing: the delay's
;                               audio DOES pass through this insert, applied up-
;                               or downstream in the same chain.
;   dry silent, delay remains-> cleanest answer: the delay is a parallel/send
;                               path and the insert only ever carried dry.
;
; Build:  DELAYPROBE=1 python3 tools/build_bus.py   -> out/mainos_bus_delayprobe.bin

init:
        rts

proc:
        move    r0,r1                   ; same in-place convention as the stub
        clr     a
        do      n7,>zend
        move    x:(r0)+,b               ; read and discard, so r0 tracks stock
        move    x:(r0)+,b
        move    a,x:(r1)+               ; ...but write silence
        move    a,x:(r1)+
zend:
        rts
