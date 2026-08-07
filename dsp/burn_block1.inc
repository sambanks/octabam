; ---- BURN PROBE 1 of 2: the cycle burn ----------------------------------
; Placed HERE, at the very top of proc, because this is the only point where
; the register state is trivially known: `a` has just been saved to r7+$14 and
; nothing else is live yet -- r6 is still the parameter block (it is repointed
; to the pre-delay inside the sample loop) and n7 is the dispatcher's frame
; count. Anywhere later and the burn would have to be proved not to clobber
; the address setup. The next instruction below is `clr a`, so a, b, x0, x1
; and y0 are all free to use.
;
; burn = 32 * p3 cycles/sample: (8 * p3 * n7) iterations of a four-word body,
; over n7 samples.
;
; FOUR nops, not one. A one-word DO body is precisely the case where "one word
; == one cycle" stops being obviously true on this core, and the entire value
; of this probe is that the number it returns is exact. Four is clear of that
; and of the two-word case, at a cost of three words.
;
; THE SCALING IS A MULTIPLY, not a repeated-add loop, because the region is
; full: the shimmer spent the 52 words v98 freed, and the first draft of this
; block (29 words) overran by 13. Reading the parameter straight into y0 and
; letting mpy do the work is 14 words for the same arithmetic.
;
; The alignment, since it is the one place this could be silently wrong: mpy
; is FRACTIONAL, so for two integers it leaves 2*X*Y in A[47:0]. Here X = n7
; and Y = p3<<16 (the raw parameter word -- page-1 knobs carry no companion
; field, which is why the LO code it replaces multiplied the word directly),
; giving p3*n7*2^17. A1 is A[47:24], so asl #$a lands 8*p3*n7 in A1 exactly.
; Max 8*127*16 = 16256 iterations, nowhere near overflowing.
;
; The zero guard is load-bearing and ONE guard covers both cases -- the
; product is zero if EITHER p3 or n7 is zero. DO with a count of zero loops
; 65536 times, which would burn ~260k cycles and hang the instrument on the
; knob position that is supposed to be the safe one.
; y1 AND NOT y0, and this is not style. The 56300's MPY encodes only eight
; operand pairs and x0*y0 is NOT one of them -- and dsp_asm does not reject
; the invalid pair, it silently emits `mpysu` (signed x unsigned), a different
; instruction. Same family as the `tfr a,b` -> `rnd b` mis-encoding this
; project already lost two attempts to. `mpy x0,y1` is encodable and is what
; the engine uses everywhere else, which is why nothing here tripped it before.
        move    x:(r6+$3),y1            ; p3, as the raw value<<16 word
        move    n7,x0                   ; frames on THIS call
        mpy     x0,y1,a
        asl     #$a,a,a                 ; A1 = 8 * p3 * n7
        tst     a
        beq     noburn
        move    a1,x0                   ; a1, not a: raw, no limiting
        do      x0,>burnend
        nop
        nop
        nop
        nop
burnend:
noburn:
