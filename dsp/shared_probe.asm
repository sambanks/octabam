; ---------------------------------------------------------------------------
; SHARED-MEMORY PROBE -- do the two DSP cores see the same Y:0x30000 window?
;
; Built with BURN=1, which swaps this in for DELAY SERVER (and gives ChonVerb
; the cycle burn -- one flash, two answers). BongDelay is a placeholder anyway,
; so its 507 words are the cheapest space on the chip for a diagnostic.
;
; WHY THIS MATTERS MORE THAN ANYTHING ELSE OPEN. BUS.md's founding constraint
; is that "the two DSPs are a hard boundary, not a soft one" -- separate chips,
; the shared 64K "partitioned in half at build time, one half per payload",
; nothing exchanging audio between them. Every downstream decision inherits it:
; the bus is scoped per bank of four tracks, a true 8-track bus is impossible,
; and reverb-on-one-core-feeding-delay-on-the-other is off the table.
;
; The board photo (7 Aug 2026) says that may be wrong. The part is a
; DSPB56721AG, and the DSP56721 block diagram shows Core-0 and Core-1 reaching
; a common "Shared Memory, 8 blocks x 8K, 64K total" through Shared Bus 0 /
; Shared Bus 1 and Arbiters 0-7. There is a bridge in hardware. And the
; arithmetic is a suspiciously exact match: 8 * 8192 = 65536 = 0x10000, which
; is precisely the span of the Y:0x30000..0x3FFFF window DELAY SERVER was
; given, split 0x8000 per payload. There is also no EMC block anywhere in the
; diagram, so that window cannot be external memory -- it is on-chip, and the
; only on-chip memory both cores reach is the shared block.
;
; WHAT OUR OWN EVIDENCE CANNOT DO IS DISTINGUISH THE TWO CASES. Payload A
; writing 0x30000 and payload B writing 0x38000 works identically whether that
; memory is shared or core-local, because they are different addresses either
; way. So this probe puts BOTH payloads on the SAME address -- that is the
; entire point, and it is why the address below is NOT substituted per payload
; the way DELAY SERVER's base is.
;
; ROLES, off the existing substitution. build_bus.py already rewrites the one
; 0x30000 literal to 0x38000 for payload B, and asserts there is exactly ONE
; occurrence -- which is why every mention of it in these comments is written
; 0x-style: a blind text substitution would rewrite them too, and the count
; assertion would fire before the build ever got that far.
; Comparing that literal against a hardcoded `$38000` therefore tells the code
; which payload it is, with no new build machinery: payload A writes, payload
; B reads.
;
; THE SIGNAL IS A LIVE COUNTER, NOT A CONSTANT, and that is deliberate. A
; static signature cannot distinguish "the other core wrote this" from "this
; word happened to already hold it" -- nothing clears that window, so a value
; written once survives, including across a re-assign. The writer increments
; every block; the reader demands the value CHANGED since last block. Only a
; running writer produces that.
;
; AND IT CARRIES A TAG. The counter's top byte is forced to $5a and the reader
; checks it. Without that, any unrelated word that happens to churn at this
; address reads as success -- and a false positive here is the expensive kind,
; because it would send us building an 8-track bus that cannot work.
;
; READOUT -- three states, so "it did not work" and "it is not running" cannot
; be confused. The reader never mutes: it passes its track's audio at
;
;   FULL LEVEL   tag matches AND the value is changing -> THE CORES SHARE IT
;   -24 dB       otherwise                             -> not shared
;   silence      the probe is not running at all, or is broken
;
; HOW TO RUN IT. Order matters, because the window retains what was written:
;
;   1. Assign this effect to a track in 5-8 (core 1, the READER) ONLY, with a
;      sample playing. Expect QUIET. If it is silent, stop -- the probe is not
;      running and nothing below means anything.
;   2. Now also assign it to a track in 1-4 (core 0, the WRITER), playing or
;      not -- the writer needs no audio, it only counts.
;   3. If the reader jumps to FULL LEVEL, the cores share the window and
;      BUS.md's hard-boundary constraint is dead.
;   4. Un-assign the writer. The reader should fall back to quiet within a
;      block. If it stays loud, something OTHER than our writer is churning
;      that address and the result is void.
;
; Step 4 is the control and it is not optional. Steps 1-3 alone are satisfied
; by any address that happens to be busy.
;
; WHAT THE EMULATOR CANNOT CHECK: dsp_host cannot boot payload B at all, so
; the reader path has never executed anywhere. Only the writer path and the
; assembly are verified locally. This probe is a hardware question by
; construction.
; ---------------------------------------------------------------------------

; The one address both payloads use. Deliberately mid-window, clear of both
; halves' edges. Stock's per-frame parameter staging is at X:0x30000, and X
; and Y have been settled as non-aliasing, so Y here is ours.
;   Y:$34000   the tagged counter

init:
        rts

proc:
; ---- which payload am I? -------------------------------------------------
; build_bus.py substitutes this single 0x30000 literal for 0x38000 on
; payload B (and asserts there is exactly one), so the compare below is the
; role select. Payload A falls through to the writer; payload B branches.
        move    #>$30000,a
        move    #>$38000,x0
        cmp     x0,a
        beq     reader

; ---- WRITER (payload A, core 0) -----------------------------------------
; Increment, re-tag, store. The audio buffer is never touched, so a track
; running the writer sounds exactly as it would with no effect -- the writer
; is meant to be assignable without changing what you hear.
;
; A2 is cleaned before the mask for the standing reason this project learned
; the hard way: the word starts as boot garbage, AND clears A1 only, and a
; bit-23-set A2 sign-extends and saturates anything derived from it. Nothing
; here reaches an address register so it could not hang, but the tag would be
; silently wrong on the first block and the reader would never match.
        move    y:>$34000,a
        move    #>$1,x0
        add     x0,a
        move    a1,x0                   ; A2-clean before masking
        move    x0,a
        and     #>$00ffff,a             ; keep the count
        move    #>$5a0000,x0
        or      x0,a                    ; re-apply the tag
        move    a,y:>$34000
        rts

reader:
; ---- READER (payload B, core 1) -----------------------------------------
; Two independent conditions, both required: the tag proves it is OUR writer's
; word, the change proves the writer is RUNNING rather than having left the
; value behind on an earlier assign.
        move    y:>$34000,a
        move    a1,x0
        move    x0,a                    ; A2-clean, same reasoning as above
        move    a,x1                    ; keep the whole word
        and     #>$ff0000,a
        move    #>$5a0000,x0
        cmp     x0,a
        bne     notlive                 ; wrong tag: not our writer at all
        move    x1,a
        move    x:(r7+$20),b            ; what we saw last block
        move    a,x:(r7+$20)            ; remember for the next one
; `sub b,a` and NOT `cmp b,a`, and this cost a disassembly to catch. dsp_asm
; encodes the ACCUMULATOR-TO-ACCUMULATOR forms of CMP, CMPM and TFR as
; entirely different instructions -- `cmp b,a` comes out as `maxm a,b`, which
; would have compared MAGNITUDES and overwritten b. ADD and SUB are correct in
; the same form, and SUB sets Z on equality exactly as CMP would, so it is a
; free substitution. a is dead after this, so destroying it costs nothing.
        sub     b,a
        beq     notlive                 ; unchanged: stale, writer not running
        move    #>$7fffff,y1            ; LIVE -> full level
        bra     rdgain
notlive:
        move    #>$080000,y1            ; -24 dB, still audible on purpose
rdgain:

; ---- apply the gain to this track's audio -------------------------------
; mpy x0,y1 and NOT x1,y1: the 56300 encodes only eight MPY operand pairs and
; x1*y1 is not one of them -- dsp_asm silently emits `mpysu` instead of
; erroring (see the memory on assembler traps; this is the second member of
; that family after `tfr a,b` -> `rnd b`). x0*y1 is encodable.
;
; asr #1 undoes mpy's fractional doubling, so a gain of $7fffff is unity.
        move    #>$1,n0
        do      n7,>rd_end
        move    x:(r0),x0               ; L
        mpy     x0,y1,a
        asr     #$1,a,a
        move    a,x:(r0)
        move    x:(r0+n0),x0            ; R
        mpy     x0,y1,a
        asr     #$1,a,a
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0                 ; next stereo frame
        move    #>$1,n0
rd_end:
        nop
        rts
