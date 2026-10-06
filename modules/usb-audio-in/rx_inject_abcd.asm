; USB AUDIO IN ABCD, DSP side: while the host's stream is open, write its four
; channels over inputs A-D in core 0's current RX block; while it is closed,
; leave the block alone and the jacks come through.
;
; Placed by the build in payload A's donor region and reached from the frame
; head: P:$88's `move r2,x:>$204` becomes `jsr >inject` (schema.DspHook) and
; is replayed here. Every stock reader of the RX block (x:>$202) runs after
; P:$88 in the frame, so one inject serves both cores and the recorder.
;
; The ColdFire's frame transfer lands 160 halfwords at the working bank's
; +$320 (usbaudio_in.s in_build): word 0 = 1 while the stream is open, then
; 16 x (A hi, A lo, B hi, B lo, C hi, C lo, D hi, D lo), hi = sample[23:8],
; lo = sample[7:0], in host channel order 1-4 = A-D. The top byte of a host
; word is not zero, so every word is masked.
;
; The RX block is 16 samples x 4 slots: slots 2/3 are inputs A/B, 0/1 are
; C/D (the firmware's GAIN assignment, hardware 26 Sep 2026). Bryan T's
; four-channel inject (usbin-test, build 16 on his MKII) wrote the same
; slots in DSP order; this one takes host order and stores by displacement.
; Live at P:$88: r2 (stored here), r4-r7, b. Free: a, x1, r0, r1.
;
; Forms: as rx_inject_ab.asm, plus move a1,x:(rN) (P:$b6's form).

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
        move    x:(r0)+,a               ; A, bits 23:8
        asl     #8,a,a
        move    a1,x1
        move    x:(r0)+,a               ; A, bits 7:0
        and     #>$ff,a
        add     x1,a                    ; x1's low byte is zero: add = or
        move    a1,x:(r1+2)             ; slot 2 = input A (a1: no limiting)
        move    x:(r0)+,a               ; B
        asl     #8,a,a
        move    a1,x1
        move    x:(r0)+,a
        and     #>$ff,a
        add     x1,a
        move    a1,x:(r1+3)             ; slot 3 = input B
        move    x:(r0)+,a               ; C
        asl     #8,a,a
        move    a1,x1
        move    x:(r0)+,a
        and     #>$ff,a
        add     x1,a
        move    a1,x:(r1)               ; slot 0 = input C
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
