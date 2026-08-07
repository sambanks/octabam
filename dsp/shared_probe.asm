; ---------------------------------------------------------------------------
; SHARED-MEMORY PROBE, round 3 -- now also a fault probe.
;
; Built with BURN=1, which swaps this in for DELAY SERVER (and gives ChonVerb
; the cycle burn). BongDelay is a placeholder, so its 507 words are the
; cheapest diagnostic space on the chip.
;
; ---------------------------------------------------------------------------
; THE ORIGINAL QUESTION
; ---------------------------------------------------------------------------
; BUS.md's founding constraint is that "the two DSPs are a hard boundary" --
; separate chips, nothing exchanging audio, so a true 8-track bus is
; impossible and reverb-on-one-core cannot feed delay-on-the-other.
;
; The board photo (7 Aug 2026) says that may be wrong: the part is a
; DSPB56721AG, and the DSP56721 block diagram shows Core-0 and Core-1 both
; reaching a common "Shared Memory, 8 blocks x 8K, 64K total" through Shared
; Bus 0 / Shared Bus 1 and Arbiters 0-7, with no EMC block anywhere. 8 * 8192
; = 65536 = 0x10000, exactly the span of the Y:0x30000..0x3FFFF window.
;
; Our own evidence cannot settle it: payload A writing 0x30000 and payload B
; writing 0x38000 behaves identically whether that memory is shared or
; core-local, because they are DIFFERENT ADDRESSES either way. So this probe
; puts both payloads on the SAME address.
;
; ---------------------------------------------------------------------------
; WHAT ROUNDS 1 AND 2 ACTUALLY FOUND, AND WHY THIS ROUND EXISTS
; ---------------------------------------------------------------------------
; ESTABLISHED ON HARDWARE, 7 Aug 2026:
;   * The track->core map is REAL: track 1 reads as writer (payload A), track
;     5 as reader (payload B). The 1-4 / 5-8 split is confirmed, not assumed.
;   * The READER is clean. Track 5 sits at -24 dB and sounds right, so the
;     gain loop, m0 and the mpy scaling are all correct.
;   * The WRITER's own track degrades into "metallic feedbacky noise" after
;     ~32 steps at 88 BPM = 5.45 s, persistently, and only when unmuted.
;   * It is NOT the audio path: round 1's writer never touched the audio
;     buffer at all -- it wrote one word and rts'd -- and failed identically.
;   * It is NOT the machine or the project: ChonVerb on the same track, same
;     conditions, past the same point, is CLEAN. ChonVerb lives at
;     Y:0x4000..0xBFFF and never touches this window.
;
; So the fault is the single store `move a,y:>$34000`, and 0x34000 was a bad
; choice: DSP.md's allocator table reads
;
;     FX2:  0x4000  0x8000  0x30000  0x34000   stride 0x4000 = 16384 words
;
; -- 0x34000 is FX2 SLOT 4's BASE, a real per-track buffer, and the second
; half of DELAY SERVER's own 32K pool. Not scratch.
;
; ---------------------------------------------------------------------------
; THE FOUR HYPOTHESES THIS ROUND SEPARATES, IN ONE FLASH
; ---------------------------------------------------------------------------
; Two knobs. Both were chosen so that a single sweep discriminates rather than
; confirms -- the project's own lesson is that a probe returning a NUMBER beats
; a build testing a guess.
;
; p2 = INC, used directly as the increment (0..127). This separates the VALUE
; from the ACT:
;   INC = 0    the word is rewritten every block but never CHANGES.
;              Still fails  -> the act of writing is the fault.
;              Now clean    -> the changing value is the fault.
;   INC = n    the counter climbs n times faster, so if the trigger is the
;              value crossing a threshold the onset time DIVIDES BY n. At
;              INC=16 the 5.45 s failure should arrive in ~0.34 s; if instead
;              it still takes 5.45 s, onset is governed by elapsed time or
;              write count, not by the value.
;
; That second one is the real prize. 5.45 s is ~15,000 blocks and 2^14 =
; 16,384 -- close enough to be worth testing, far enough off (9%) that it
; would be irresponsible to assume it.
;
; p1 = ADDR, four targets, so one flash asks whether the address matters:
;   0  Y:0x34000   FX2 slot 4 base, payload A's half -- the KNOWN-BAD control
;   1  Y:0x3C000   payload B's half -- and the true cross-core target, since
;                  the allocator gives A 0x30000-0x37FFF and B 0x38000-0x3FFFF
;   2  Y:0x37FFF   last word of A's half, clear of every slot BASE
;   3  Y:0x3FFFF   very top of the window
;
; If 0 fails and 2 does not, slot bases are special. If every address in A's
; half fails, the window is unsafe for payload A writes -- which BongDelay
; would hit anyway, since it lives at Y:0x30000..0x37FFF, and that is a
; finding about the delay's memory regardless of the sharing question.
;
; ---------------------------------------------------------------------------
; READOUT -- four states; every track announces its own ROLE
; ---------------------------------------------------------------------------
;   FULL LEVEL   reader, tag matches AND changing  -> THE CORES SHARE IT
;   -12 dB       this track is the WRITER          -> it is on payload A
;   -24 dB       reader, not live                  -> not shared
;   silence      not running at all, or broken
;
; With INC=0 the reader can never report LIVE (nothing changes), so in that
; setting -24 dB is the CORRECT reading and carries no information about
; sharing -- INC=0 tests the fault only.
;
; ---------------------------------------------------------------------------
; NO BUS HOUSEKEEPING HERE, DELIBERATELY
; ---------------------------------------------------------------------------
; dsp/delay_server.asm -- which this replaces -- runs the position-0
; parity-flip-and-clear with a self-healing election, and BUS.md requires any
; effect that can land at position 0 to duplicate it. This file does not, and
; that IS a defect for anything shipping.
;
; It is left out of the diagnostic on purpose. Every unassigned track defaults
; to SEND (id 0 is aliased to it, and there is no selectable NONE), and
; send_client carries the same self-healing election, so the bus is housekept
; whatever position we land in. Nothing consumes the accumulators during this
; test anyway. Copying forty lines of unverified bus plumbing into a build
; whose entire purpose is isolating one fault would add exactly the kind of
; confound this round is trying to remove. RESTORE IT before any of this
; becomes a real effect.
;
; WHAT THE EMULATOR CANNOT CHECK: dsp_host cannot boot payload B, so the
; reader path has never executed anywhere but hardware.
; ---------------------------------------------------------------------------

init:
        rts

proc:
; ---- ADDR: pick the target, BEFORE the role split so both agree ----------
; The whole test is that both payloads hit the SAME address, so this must not
; be per-payload substituted the way the role literal below is.
;
; p1 arrives as value<<16. >>21 leaves the top 2 bits of a 0..127 knob, i.e.
; 0..3, so the knob's four quarters select the four targets.
;
; `cmp x0,a` is register-to-accumulator and encodes correctly. The
; accumulator-to-accumulator form does NOT -- `cmp b,a` assembles as
; `maxm a,b` (see the assembler-traps memory). Do not "simplify" these.
        move    x:(r6+$1),a             ; ADDR knob
        asr     #$15,a,a                ; -> 0..3
        move    #>$34000,y0             ; 0: FX2 slot 4 base, A's half
        move    #>$1,x0
        cmp     x0,a
        bne     ad1
        move    #>$3c000,y0             ; 1: B's half -- the cross-core target
ad1:
        move    #>$2,x0
        cmp     x0,a
        bne     ad2
        move    #>$37fff,y0             ; 2: top of A's half, no slot base
ad2:
        move    #>$3,x0
        cmp     x0,a
        bne     ad3
        move    #>$3ffff,y0             ; 3: very top of the window
ad3:
        move    y0,r5
        move    #>$ffffff,m5            ; r5 must be linear, and this also
        move    #>$1,n0                 ; spaces the AGU write from its use --
                                        ; reverb_server does the same thing
                                        ; ("two instructions before r5 is used")

; ---- which payload am I? -------------------------------------------------
; build_bus.py substitutes this single 0x30000 literal for 0x38000 on payload
; B (and asserts there is exactly ONE occurrence, which is why every mention
; of it in these comments is written 0x-style). Payload A falls through to the
; writer; payload B branches.
        move    #>$30000,a
        move    #>$38000,x0
        cmp     x0,a
        beq     reader

; ---- WRITER (payload A, core 0) -----------------------------------------
; Read, add INC, re-tag, store. INC comes straight off p2 as an integer, so
; INC=0 rewrites the same word forever and INC=n climbs n times faster.
;
; A2 is cleaned before the mask: the word starts as boot garbage, AND clears
; A1 only, and a bit-23-set A2 sign-extends into anything derived from it.
; Nothing here reaches an address register so it cannot hang, but the tag
; would be wrong on the first block and the reader would never match.
        move    y:(r5),a
        move    x:(r6+$2),b             ; INC knob
        asr     #$10,b,b                ; -> 0..127, integer
        move    b1,x0
        add     x0,a
        move    a1,x0                   ; A2-clean before masking
        move    x0,a
        and     #>$00ffff,a             ; keep the count
        move    #>$5a0000,x0
        or      x0,a                    ; re-apply the tag
        move    a,y:(r5)
        move    #>$200000,y1            ; -12 dB: the WRITER's signature level
        bra     gain

reader:
; ---- READER (payload B, core 1) -----------------------------------------
; Two independent conditions, both required: the tag proves it is OUR writer's
; word, the change proves the writer is RUNNING rather than having left the
; value behind on an earlier assign. Nothing clears this window, so a value
; written once survives -- a static signature could not tell those apart.
        move    y:(r5),a
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
; `sub b,a` and NOT `cmp b,a`: dsp_asm encodes the accumulator-to-accumulator
; forms of CMP/CMPM/TFR as different instructions entirely -- `cmp b,a` comes
; out as `maxm a,b`, comparing MAGNITUDES and overwriting b. ADD and SUB are
; correct in that form, and SUB sets Z on equality exactly as CMP would. a is
; dead after this, so destroying it costs nothing.
        sub     b,a
        beq     notlive                 ; unchanged: stale, or INC=0
        move    #>$7fffff,y1            ; LIVE -> full level
        bra     gain
notlive:
        move    #>$080000,y1            ; -24 dB, still audible on purpose

; ---- shared: apply y1 to this track's audio -----------------------------
; mpy x0,y1 and NOT x1,y1: the 56300 encodes only eight MPY operand pairs and
; x1*y1 is not one of them -- dsp_asm silently emits `mpysu` rather than
; erroring.
;
; NO `asr #1` after the mpy. MPY is a FRACTIONAL multiply and its shift-left
; is exactly what makes the result correctly scaled; dsp/send_client.asm
; multiplies a send level with a bare `mpy x1,y1,a` and no correction. Round 2
; had a stray asr that halved everything, which made the reader's LIVE state
; unreachable by construction.
;
; m0 MUST be set: r0 is not merely read here, it is WRITTEN, and
; dsp/reverb_server.asm sets `#>$ffffff,m0` for exactly this reason -- its
; comment reads "audio is read and written via r0". Left at whatever modifier
; the previous effect happened to leave, `move a,x:(r0)` scatters samples to
; wrapped addresses: energy and envelope survive, the waveform does not.
gain:
        move    #>$ffffff,m0            ; audio is read AND WRITTEN via r0
        move    #>$1,n0
        do      n7,>rd_end
        move    x:(r0),x0               ; L
        mpy     x0,y1,a
        move    a,x:(r0)
        move    x:(r0+n0),x0            ; R
        mpy     x0,y1,a
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0                 ; next stereo frame
        move    #>$1,n0
rd_end:
        nop
        rts
