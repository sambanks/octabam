; USB AUDIO IN, DSP side: while the host's stream is open, write its stereo
; pair over inputs C and D in core 0's current RX block; while it is closed,
; leave the block alone and the jacks come through.
;
; Placed by the build in payload A's donor region and reached from the frame
; head: P:$88's `move r2,x:>$204` becomes `jsr >inject` (schema.DspHook) and
; is replayed here. Every stock reader of the RX block (x:>$202) runs after
; P:$88 in the frame, the core 0 -> core 1 handoff and the read-back the
; recorder takes included, so one inject serves both cores and the recorder.
;
; The ColdFire's frame transfer lands 96 halfwords at the working bank's
; +$320 (usbaudio_in.s in_build): word 0 = 1 while the stream is open, then
; 16 x (C hi, C lo, D hi, D lo), hi = sample[23:8], lo = sample[7:0]. The
; top byte of a host word is not zero, so every word is masked.
;
; The RX block is 16 samples x 4 slots; slots 0 and 1 are inputs C and D
; (the firmware's GAIN assignment, hardware 26 Sep 2026), 2 and 3 are A/B.
; Live at P:$88: r2 (stored here), r4-r7, b. Free: a, x1, r0, r1.
;
; Every form has a stock site in payload A: move x:(r0)+,a (P:$b2),
; and #>$ff,a (P:$b3), asl #n,a,a (P:$11a), move a1,x:(rN+$n) (P:$51a), move a1,x:(rN) (P:$b6's form),
; lua (r1+$4),r1 (P:$341), do #<n (P:$9f); move r6,a / add #>n,a /
; move a1,x1 ran on Bryan T's unit as usbin-test's inject (build 16).

inject:
        move    r2,x:>$204              ; the displaced instruction
        move    r6,a
        add     #>$320,a
        move    a,r0                    ; r0 = working bank + $320
        move    x:(r0)+,a               ; word 0: 1 while the host streams
        and     #>$ff,a
        beq     inj_end                 ; closed: the jacks stay
        move    x:>$202,r1              ; r1 = the current RX block
        do      #16,inj_end
        move    x:(r0)+,a               ; C, bits 23:8
        asl     #8,a,a
        move    a1,x1
        move    x:(r0)+,a               ; C, bits 7:0
        and     #>$ff,a
        add     x1,a                    ; x1's low byte is zero: add = or
        move    a1,x:(r1)               ; slot 0 = input C (a1: no limiting)
        move    x:(r0)+,a               ; D
        asl     #8,a,a
        move    a1,x1
        move    x:(r0)+,a
        and     #>$ff,a
        add     x1,a
        move    a1,x:(r1+1)             ; slot 1 = input D
        lua     (r1+4),r1               ; next sample's four slots
inj_end:
        rts
