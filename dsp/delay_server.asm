; ---------------------------------------------------------------------------
; BongDelay v2, STAGE 1: CLEAN (PLAN.md 3.1, 12 Aug 2026).
;
; This file is v1's engine carried bit-identically through the v2 spine --
; the refactor-first gate (tools/verify_delay.py, the verify_roll pattern):
; prove equivalence, THEN add modes. Two spine changes, no behavior change:
;
;   * MODE select read (page-2 slot 7, r6+$c bits 8-15, ChonVerb's exact
;     idiom). Stage 1 has one engine, so every value runs CLEAN -- the
;     dispatch grows compares when PITCH lands, and unknown values must
;     keep degrading to CLEAN (the trad delay), never to silence.
;   * NO AGU MODULO. m1/m2 stay at the global linear invariant ($ffffff);
;     read addresses are computed and write pointers wrapped by hand
;     (details at the sample loop). This is what frees later modes --
;     grain readers at scattered offsets, reverse reads, a single full-
;     window line -- from the aligned-modulo-per-rN constraint.
;
; Deliberately NOT in stage 1 (each is its own gated commit):
; the Y state table (no new persistent state yet), PITCH/FREEZE/TAPE/GRAIN/
; REVERSE, and the descriptor-side MODE select (a one-value select would
; draw a dead knob; it lands with the second mode).
;
; BUS AUTO-GAIN LANDED as its own gated commit after stage 1 (the behavior
; change stage 1 deliberately excluded -- measured like the reverb's $0c
; fix, not bit-compared). Mechanism at the "bus auto-gain" block below:
; every DELAY-bus writer registers per block in $985/$986 and writes asr #3;
; this server multiplies the accumulator by 1/count and shifts back up 3.
;
; ---------------------------------------------------------------------------
; BUS.md task 9: DELAY SERVER. An algorithm from scratch -- unlike REVERB
; SERVER (task 8), there is no existing engine to reuse, so this file is the
; first build of it. Same three structural pieces as dsp/reverb_server.asm
; (hardcoded base, shared bus plumbing duplicated verbatim, everything else
; is this file's own new code):
;
; 1. HARDCODED BASE. Y:0x30000, 32768 words (BUS.md's Memory section 32K/32K
;    split), same technique as dsp/probe_hardcoded_base.asm and REVERB
;    SERVER: no x:0x213 read, no per-instance stash, every instance uses the
;    same literal. At most one DELAY SERVER per bank is self-enforced
;    convention, not something this file checks (BUS.md Known limitations).
;
;    ✅ SOLVED, and this comment was stale for longer than the bug existed.
;    tools/build_bus.py substitutes the base literal per payload (`_sub`,
;    PP[tag]["ybase"] = 0x30000 for A / 0x38000 for B). The old text here
;    named tools/build_reverb.py, which does not build this file at all.
;
;    ✅ VERIFIED IN THE EMITTED IMAGE, 9 Aug 2026, not in the source: walking
;    out/mainos_bus.bin's payload records and scanning the placed P words,
;    payload B's region carries the immediate 0x38000 five times and the
;    payload-A base ZERO times. Reading build_bus.py would not have been
;    enough -- it is a blanket string replace, and what matters is what
;    landed in the binary.
;
;    ⚠️ THE SUBSTITUTION IS A BLANKET TEXT REPLACE OVER THE WHOLE SOURCE,
;    and it rewrites COMMENTS as well as code. Any file it is applied to
;    (SEND and REVERB SERVER too, under XBUS) must not spell the payload-A
;    base as a bare assembler literal anywhere it is not meant to move to
;    0x38000 on payload B. Write shared-window addresses as offsets from a
;    register-held base instead.
;
;    build_bus.py counts the occurrences and refuses to build if the total
;    is not what the current flag combination expects. That guard is load-
;    bearing: writing this very comment with the literal spelled out tripped
;    it, which is the cheapest possible way to find out.
;
; 2. SHARED BUS PLUMBING. Every proc() call runs the same position-0
;    parity-flip-and-clear housekeeping as dsp/send_client.asm and
;    dsp/reverb_server.asm, split-aware-offset fix included, copied
;    byte-for-byte (BUS.md Known limitations: this duplication is mandatory,
;    not stylistic -- a divergent copy desyncs the bus silently). The engine's
;    own input additionally sums in the shared DELAY bus accumulator, and its
;    clean mono wet (pre-mix, the algorithm's own output before this track's
;    dry blend) is written to the shared DELAY WET buffer for a future
;    cross-bus consumer (task 10 -- DELAY SERVER's own ->VERB send) to read.
;
; 3. THE ALGORITHM (new, this file): a two-line ping-pong delay, feedback
;    tone-shaped by a one-pole low-pass inside the loop (the same "s +=
;    c*(d-s)" idiom dsp/reverb89.asm's HI control uses -- a large c tracks
;    the input and keeps highs, a small c is dark).
;
;    Both lines share one TIME (no independent stereo detune -- v1 scope).
;    Input enters LINE L ONLY -- the classic ping-pong topology, and NOT an
;    arbitrary choice: an earlier draft summed input into BOTH lines so
;    PING=0 would behave as an ordinary independent stereo echo, but for a
;    MONO source (L==R, which is also all this project's mono-only emulator
;    test input can ever supply) that makes the two lines' state
;    equations identical at every step, for ANY value of PING -- provably,
;    by induction, since a symmetric system fed a symmetric input at a
;    symmetric entry point never diverges. That version's PING knob would
;    have done NOTHING audible on real hardware, and the bug was only
;    visible once dsp_host's impulse response showed L and R bit-identical
;    at every echo regardless of the PING param. Feeding L only breaks the
;    symmetry at the entry point instead of relying on the source material,
;    so the bounce is both real on a mono source AND the one topology this
;    harness can actually verify (see the emulator test below).
;
;    PING controls a continuous 2x2 crossfeed matrix on the FEEDBACK path:
;
;        fbIntoL = fL*(1-PING) + fR*PING
;        fbIntoR = fR*(1-PING) + fL*PING
;        LineL[write] = x_in + fbIntoL*FDBK
;        LineR[write] =        fbIntoR*FDBK
;
;    PING=0: LineL is a plain single-line feedback delay and LineR never
;    receives anything, ever (it only ever hears fbIntoR = fR, and fR
;    started at 0 with no other way in) -- so MIX'd wet is L-only until
;    PING moves off zero. PING=~1: full swap -- input enters on L, the
;    first repeat comes back on R, the next on L, alternating. Total loop
;    gain per line is a convex combination of fL/fR scaled by FDBK, so it
;    never exceeds FDBK regardless of PING; stability doesn't depend on
;    this knob. R being silent at PING=0 is a real v1 characteristic, not
;    hidden: worth revisiting (e.g. a small fixed direct-to-R tap) once
;    there's something to listen to, same "starting point, not final"
;    status as the 32K/32K memory split.
;
;    CROSS-BUS SEND (BUS.md task 10): ->VERB, two knobs -- WET (this delay's
;    own processed output bleeding into the shared REVERB bus) and DRY (this
;    track's own pre-effect signal, parallel, same tap shape as
;    dsp/send_client.asm's two knobs). Both are additive contributions into
;    the REVERB ACC bus alongside whatever SEND clients and REVERB SERVER's
;    own dry sum add that block. Delay->reverb is allowed to carry WET;
;    reverb->delay (dsp/reverb_server.asm's ->DELAY send) is dry only -- see
;    that file's header for why the wet direction only ever runs one way
;    (closing it both ways reproduces the self-oscillation this project has
;    already seen once).
;
;    Each line is a plain circular buffer, wrapped BY HAND (v2 spine): rN
;    holds the write pointer as a plain linear address, the TIME-behind read
;    address is computed per sample as base + ((wr - TIME) & $3fff), and the
;    post-write pointer is folded back the same way. The AND is exact
;    because both line bases are 0x4000-aligned, so the base falls out of
;    the mask. v1 used AGU modulo (m1/m2 = $3fff) for the same addresses --
;    proven bit-identical at the swap (tools/verify_delay.py, 12 Aug 2026).
;
; Memory (base = Y:0x30000, aligned to 0x4000 as modulo addressing requires):
;   LineL   base+0x0000 .. base+0x3fff   16384 words (max ~371 ms @ 44.1kHz)
;   LineR   base+0x4000 .. base+0x7fff   16384 words
;   total   0x8000 (32768) words -- BUS.md's 32K DELAY SERVER allocation
;
; State (all in the per-instance r7 block):
;   r7+$14              call flag stash (proc entry accumulator)
;   r7+$15/$16/$17      per-sample scratch for the PITCH heads (age_fx /
;                       phase then g^2 / t0 then tap). $15 doubles as the
;                       warm-up count stash -- warm-up and the sample loop
;                       are mutually exclusive by construction
;   r7+$18              grain-jitter PRNG state, 23-bit xorshift (persistent,
;                       seeded nonzero at warm-up: xorshift is dead at 0)
;   r7+$19/$1a          previous ageL head 0 / head 1, for wrap detection
;   r7+$1b/$1c          latched grain scatter, LineL head 0 / head 1, in
;                       samples 0..1023 (persistent, held for a whole grain)
;   r7+$1d/$1e          previous ageR head 0 / head 1
;   r7+$1f/$20          latched grain scatter, LineR head 0 / head 1
;   r7+$21              this sample's PRNG candidate offset (per-sample)
;   r7+$22/$23          per-sample scratch for the wrap latches (parked age)
;   r7+$24/$25          PITCH shifted OUTPUT tap L / R (per sample). Kept
;                       separate from the loop's taps ($79/$7a) so the shift
;                       never re-enters the feedback -- the non-cascading
;                       topology, v2 stage 2c
;   r7+$31              LineL base (hardcoded literal, stashed for symmetry
;                       with dsp/reverb_server.asm's convention)
;   r7+$63              this call's DELAY ACC read address (BUS.md bus)
;   r7+$64              this call's DELAY WET write address (BUS.md bus)
;   r7+$65..$67         split-aware bus bookkeeping (shared mechanism)
;   r7+$68              LineR base = LineL base + 0x4000 (per block, for the
;                       per-sample manual wraps -- v2 spine)
;   r7+$69              MODE, MSB-aligned select (per block; 0 = CLEAN,
;                       1 = PITCH -- stage 2; every other value runs CLEAN)
;   r7+$6a/$6b          PITCH age step L / R, Q11.12 signed (per block, from
;                       the PTCH interval select; they differ only in DETUNE)
;   r7+$6c/$6d          PITCH head age L / R, Q11.12 (persistent, masked on
;                       load AND save -- same discipline as $70/$71)
;   r7+$6e              PITCH lag base = min(TIME, 13311) (per block; TIME +
;                       window 2048 + jitter 1023 + the lerp's -1 must stay
;                       inside the 16384-word line, or a head would read
;                       data newer than this lap)
;   r7+$6f              per-sample scratch for the PITCH heads (age_int)
;   r7+$70/$71          LineL/LineR write-pointer phase, persistent, masked
;                       on load AND save (same two-track-freeze discipline
;                       as dsp/reverb89.asm's $83 -- garbage with bit 23 set
;                       would saturate the AGU and hang the bus forever)
;   r7+$72              TONE coefficient (per block)
;   r7+$73              FDBK coefficient (per block)
;   r7+$74              PING amount (per block)
;   r7+$75              TIME, integer sample count (per block)
;   r7+$76              MIX (per block, raw knob used directly as Q1.23)
;   r7+$77/$78          TONE filter state, line L / R (persistent)
;   r7+$79/$7a          scratch: dL/dR, raw taps (per sample)
;   r7+$7b/$7c          scratch: fL/fR, damped taps == this sample's wet
;                       outputs (per sample)
;   r7+$7d              scratch: x_in, own dry mono + bus (per sample)
;   r7+$7e/$81          scratch: fbIntoL/fbIntoR (per sample)
;   r7+$7f              bus auto-gain 1/N (per block; read per sample). The
;                       delay-bus mirror of the reverb's $0c -- kept in its
;                       own slot with nothing else ever parked here (the $0c
;                       collision lesson)
;   r7+$80              1 - PING (per block)
;   r7+$82              warm-up tagged counter (stock DARK's slot
;                       convention, reused -- see dsp/reverb89.asm)
;   r7+$83              this sample's own pre-effect dry mono, stashed before
;                       the DELAY bus is folded into $7d (BUS.md task 10 --
;                       the ->VERB DRY send taps dry alone, not dry+bus)
;   r7+$84              this call's REVERB ACC write address (BUS.md task 10,
;                       per-call, advances per sample -- same shape as $63/$64)
;   r7+$85              ->VERB WET level (per block, from knob p5)
;   r7+$86              ->VERB DRY level (per block, from knob p6, r6+$d --
;                       see the parameter table below)
;   r7+$87              this sample's own mono wet, stashed at the same point
;                       it's written to the shared DELAY WET buffer (BUS.md
;                       task 10 -- the ->VERB WET send taps that same value)
;
; Parameters (page 1, knob arrives as value<<16, value 0..127):
;   p0 TIME  -> delay length, 64 .. 16320 samples (~1.5 .. 370 ms). floor +
;              value*128 via the same and/asr trick dsp/reverb89.asm's PRE
;              uses (asr #$9 == >>16 then <<7, i.e. *128 without an mpy).
;   p1 FDBK  -> feedback gain, 0 .. ~0.87 (mpy by $700000, no floor: FDBK=0
;              is a single echo, not silence).
;   p2 TONE  -> one-pole coefficient, 0.125 (dark) .. 0.99 (bright). Exact
;              same mapping as reverb89's HI control (proven-safe constants).
;   p3 PING  -> crossfeed amount, 0 (parallel stereo) .. ~0.99 (full
;              ping-pong swap). Used directly as a Q1.23 fraction -- knob<<16
;              already IS value/128 in that format, no mpy needed.
;   p4 MIX   -> wet added to dry, 0 .. ~0.99, same "raw knob as Q1.23
;              multiplier" trick as reverb89's MIX.
;   p5 ->VERB WET -> this delay's own processed output, scaled and summed into
;              the shared REVERB ACC bus (BUS.md task 10). One-directional:
;              see dsp/reverb_server.asm's ->DELAY header note for why the
;              reverse (reverb wet -> delay) is deliberately never built.
;   p7 MODE  -> engine select, page-2 slot 7 companion (r6+$c bits 8-15),
;              count 2: 0 = CLEAN, 1 = PITCH. Landed with stage 2, per the
;              stage-1 rule that a one-value select draws a dead knob.
;   p9 PTCH  -> PITCH interval select, page-2 slot 9 companion (r6+$d low
;              bits), count 4: 0 = +12, 1 = +7, 2 = -12, 3 = +-detune
;              (~15 cents, L up / R down). Selects, not smooth knobs -- the
;              WIDTH lesson: companion fields read near-boolean at count 128
;              on hardware, small counts publish. DINT=n (build_bus.py) is
;              the local override -- dsp_host cannot drive companion fields.
;   p6 ->VERB DRY -> this track's own pre-effect signal, parallel tap into the
;              same REVERB ACC bus, same shape as dsp/send_client.asm's knobs.
;              Reads x:(r6+$d) -- BUS.md task 11 gave DELAY SERVER its own
;              descriptor (cloned from SPRING REV's bytes, not SPRING's own
;              id/slot -- tools/build_menu.py), and $d is the page-2 slot
;              that class's real hardware wiring puts at the same "MONO"-
;              equivalent position. (The reverb's ->DELAY send moved to its
;              $e low bits in R16; the old "same $d" note is history. No
;              conflict either way -- r6 is per-instance.) See DSP.md section 9 / REVERB.md
;              for how $b/$c/$d/$e were measured, and tools/build_menu.py's
;              docstring for why SPRING (not stock DELAY) was the donor.
; ---------------------------------------------------------------------------

init:
; Hardcoded base, no per-instance stash needed -- literal is identical for
; every instance, same reasoning as dsp/reverb_server.asm's init.
        rts

proc:
; ---- BOTH calls are audio -------------------------------------------------
; Same dispatcher shape as every other effect in this project -- see
; dsp/reverb89.asm's proc: comment for the full mechanism. Everything below
; re-derives from r7 state per call, so the two sub-calls of a split block
; are sample-continuous by construction.
        move    a,x:(r7+$14)            ; call flag: $010000 = the a=1 call

; ---- BUS.md: split-aware frame offset + position-0 election --------------
; Verbatim from dsp/send_client.asm / dsp/reverb_server.asm (BUS.md Known
; limitations: this copy must stay byte-identical across all three files).
        clr     a
        move    a,x:(r7+$67)            ; default: offset 0 (first call)
        move    x:(r7+$14),a
        tst     a
        bne     bus_a1
        move    #>$1,a
        move    a,x:(r7+$65)            ; "a=0 ran this block"
        move    n7,a
        and     #>$f,a                  ; same mask on the way in
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$66)            ; stash split for the matching a=1
        bra     bus_off_done
bus_a1:
; COLD-BOOT SAFETY. These slots hold boot garbage the first time an instance
; runs, and x:(r7+$67) feeds straight into r1/r2 as a Y pointer below -- an
; unmasked garbage value there makes the per-sample loop write through a wild
; address, which hangs the DSP. Reproduced on hardware: selecting SEND on any
; track from a clean boot froze the unit. Same class as DSP.md's masked-garbage
; AGU saturation, so the same discipline -- mask AND A2-clean before use.
        move    x:(r7+$65),a
        and     #>$ff,a                 ; flag field only
        move    a1,x0
        move    x0,a                    ; A2-clean before the compare
        move    #>$1,x0
        cmp     x0,a                    ; EXACTLY 1, not merely nonzero --
        bne     bus_off_done            ; "nonzero" accepts almost any garbage
        clr     a
        move    a,x:(r7+$65)            ; consume the flag
        move    x:(r7+$66),a
        and     #>$f,a                  ; a split point is 0..15 by
        move    a1,x0                   ; construction, so this cannot narrow a
        move    x0,a                    ; legitimate value -- it only makes
        move    a,x:(r7+$67)            ; garbage harmless
bus_off_done:

; ---- position-0 housekeeping: flip the shared bus parity, clear the new
; write-target ACC buffers. Gated on r7==0x6200 AND offset==0 -- copied from
; dsp/send_client.asm / dsp/reverb_server.asm, must stay identical.
; Housekeeping is normally done by position 0 (r7 == 0x6200, the bank's first
; FX2 call). That alone breaks the moment the first track's FX2 is NONE: our
; code never runs there, so nobody flips the parity or clears the
; accumulators, and the bus saturates. NONE became selectable with the task-11
; menu, so this is reachable in ordinary use.
;
; Self-healing election instead. Position 0 still housekeeps whenever it runs.
; Any other instance takes over if it sees that the parity has NOT changed
; since the last time it ran -- which can only mean nobody housekept in
; between. Costs one r7 word (the parity this instance last saw) and no new
; global signal, so it needs nothing the bus does not already have.
;
; Gated on the split offset FIRST: only a block's first call may housekeep, so
; a split block's second call can never flip a second time -- the same trap
; the original position-0 code was written around.
; XBUS_GATE -- build_bus.py substitutes a payload gate here when XBUS=1.
; A shared-memory bus is housekept by ONE core only: both cores number their
; own instances from zero, so each core's position 0 believes it is the
; housekeeper and they would flip the shared parity TWICE a block, cancelling
; out and silently desyncing the bus -- the same trap the split-call gate
; below was written around, one level up. Payload B is sent straight to
; bus_notfirst, so it still finds this block's write targets but never elects.
; Inert in a normal build: it is a comment.
        move    x:(r7+$67),a
        tst     a
        bne     bus_notfirst                ; not this block's first call
        move    r7,a
        move    #>$6200,x0
        cmp     x0,a
        beq     bus_dohk                ; position 0: always the housekeeper
        move    #>$1,x0
        move    y:>$900,a
        and     x0,a
        move    a1,x0
        move    x0,a                    ; parity now, A2-clean
        move    x:(r7+$88),x0
        cmp     x0,a
        bne     bus_seen                ; it moved: someone else housekept
bus_dohk:                               ; nobody did -- take over this block

        move    #>$1,x0
        move    y:>$900,a
        and     x0,a
        move    a,x1
        move    #>$1,a
        sub     x1,a
        and     x0,a
        move    a,y:>$900
        asl     #$4,a,a
        move    a,x0
        move    #>$901,a
        add     x0,a
        move    a,r1                    ; r1 = REVERB ACC[new] base
        move    #>$941,b
        add     x0,b
        move    b,r2                    ; r2 = DELAY  ACC[new] base
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        clr     a
        move    #>16,y0
        do      y0,>bus_zclr
        move    a,y:(r1)+
        move    a,y:(r2)+
bus_zclr:
        nop
; ---- release both server-role locks for this block (BUS.md hardware test 3)
; a is still 0 from the clear loop above. Whichever of the three effects is
; position 0 does this, so the locks are freed exactly once per block and
; re-claimed below in dispatch order.
        move    a,y:>$981               ; DELAY SERVER role owner
        move    a,y:>$982               ; REVERB SERVER role owner
; ---- reset the new write buffer's SEND COUNTs, alongside its accumulators --
; Kept in step with dsp/send_client.asm / dsp/reverb_server.asm (the standing
; rule: the housekeeping copies must stay identical). NOTE this copy was
; MISSING the $983 reset from v121 until the delay auto-gain landed -- dead
; code in every live build, because the XBUS payload gate keeps this payload
; from ever housekeeping, but a divergent copy is exactly the silent-desync
; class the rule exists for. x1 still holds the OLD parity from the flip
; above, so the buffer just made current is 1 - x1.
        move    #>$1,a
        sub     x1,a                    ; new parity
        move    #>$983,x0
        add     x0,a
        move    a,r3
        move    #>$ffffff,m3
        clr     a
        move    a,y:(r3)                ; REVERB count = 0
        move    #2,n3                   ; SHORT immediate: 1 word (address reg)
        move    (r3)+n3                 ; -> the DELAY count, same parity
        move    a,y:(r3)                ; DELAY count = 0
bus_seen:
        move    #>$1,x0                 ; remember this block's parity so next
        move    y:>$900,a               ; block we can tell whether anybody
        and     x0,a                    ; else housekept in between
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$88)
bus_notfirst:

; ---- server-role lock: only ONE DELAY SERVER may run per bank -----------------
; Both servers use a FIXED, hardcoded Y base identical for every instance, so
; two of the same role would share one set of buffers and drive each other's
; feedback path -- measured on hardware as a solid, unchanging tone (BUS.md's
; hardware test 3). The lock is released once per block by whichever effect is
; position 0 (above) and claimed here in dispatch order: the first instance to
; arrive owns the role for that block, any duplicate rts's without touching
; the audio buffer at all, which is an exact dry passthrough.
;
; Keyed on r7 (this instance's own state block), so a split block's two calls
; both match the same owner and the second is not mistaken for a duplicate.
        move    y:>$981,a
        move    a1,x0
        move    x0,a                    ; A2-clean before the compare
        tst     a
        beq     bus_claim               ; free: take it
        move    r7,x0
        cmp     x0,a
        beq     bus_mine                ; already ours (split block's 2nd call)
        rts                             ; a duplicate: pass audio through
bus_claim:
        move    r7,a
        move    a,y:>$981
bus_mine:

; ---- this call's DELAY ACC read address and DELAY WET write address ------
; READ is the OTHER buffer from the current write parity -- the one every
; SEND client (and our own dry sum, below) finished filling last block.
; WRITE uses the SAME parity clients currently write into, for a future
; cross-bus reader (task 10), not consumed by anything yet.
        move    #>$1,x0
        move    y:>$900,a
        and     x0,a                    ; write_parity
        move    a,x1
        move    #>$1,a
        sub     x1,a                    ; a = 1 - write_parity = read_parity
        asl     #$4,a,a
        move    a,x0
        move    #>$941,a
        add     x0,a
        move    x:(r7+$67),b            ; this call's split-aware frame offset
        add     b,a
        move    a,x:(r7+$63)            ; this call's DELAY ACC read address
        move    x1,a
        asl     #$4,a,a                 ; write_parity*16
        move    a,x0
        move    #>$961,a
        add     x0,a
        add     b,a
        move    a,x:(r7+$64)            ; this call's DELAY WET write address

; ---- this call's REVERB ACC write address (BUS.md task 10: ->VERB sends) --
; x1 (write_parity) and b (split-aware frame offset) are both still valid
; from the block just above -- nothing between there and here touches them.
        move    x1,a
        asl     #$4,a,a                 ; write_parity*16
        move    a,x0
        move    #>$901,a
        add     x0,a
        add     b,a
        move    a,x:(r7+$84)            ; this call's REVERB ACC write address

; ---- bus auto-gain: resolve 1/N for this block's READ buffer --------------
; The DELAY-bus mirror of the reverb's v121 fix (XBUS.md "Gain staging"):
; N clients summing into one accumulator word drive the delay N x as hard as
; one, and the shared word clamps at 1.0. Every DELAY-bus writer (SEND's
; ->DELAY tap, the reverb's ->DEL send) now registers once per block in a
; parity-indexed count at $985/$986 and writes with 3 bits of headroom
; (asr #3); this block divides by the count and the per-sample read shifts
; back up by 3, so the send knob sets a track's SHARE of the delay rather
; than how hard the line is hit. Same table order as the reverb's: count is
; masked to 0..7, so 8 writers wrap to index 0, which therefore holds 1/8.
; A count of 0 (nobody wrote) also lands on 1/8 -- harmless, the accumulator
; is zero then anyway, since writers register unconditionally.
;
; The table lives in the shared bus scratch at $988-$98f (relocated with the
; rest of the $9xx layout under XBUS) because this server has no free ground
; of its own: both line buffers fill its entire half-window. Rebuilt each
; block; the stores are free in cycle terms. x1 (write_parity) is still
; valid from the address block above.
        move    #>$988,b                ; reciprocal table base
        move    b,r5
        move    #>$ffffff,m5
        move    #>$100000,a
        move    a,y:(r5)+               ; [0] = 1/8  (count 8 wraps to here)
        move    #>$7fffff,a
        move    a,y:(r5)+               ; [1] = 1/1
        move    #>$400000,a
        move    a,y:(r5)+               ; [2] = 1/2
        move    #>$2aaaab,a
        move    a,y:(r5)+               ; [3] = 1/3
        move    #>$200000,a
        move    a,y:(r5)+               ; [4] = 1/4
        move    #>$199999,a
        move    a,y:(r5)+               ; [5] = 1/5
        move    #>$155555,a
        move    a,y:(r5)+               ; [6] = 1/6
        move    #>$124925,a
        move    a,y:(r5)                ; [7] = 1/7

        move    #>$1,a
        sub     x1,a                    ; read_parity: the count belongs to
        move    #>$985,x0               ; the fully-summed one-block-old
        add     x0,a                    ; buffer this block READS
        move    a,r5
        move    y:(r5),a                ; clients that wrote the buffer we read
        move    #>$7,x0
        and     x0,a                    ; masked: boot garbage cannot index wild
        move    a1,x0
        move    x0,a                    ; A2-clean before it becomes an address
        add     b,a                     ; b = table base, still live
        move    a,r5
        move    y:(r5),a
        move    a,x:(r7+$7f)            ; this block's bus gain, used per sample

; ---- hardcoded base (BUS.md task 9: DELAY SERVER) ------------------------
; No x:0x213 read, no per-instance stash. The 0x30000 literal below is the
; SOURCE default; build_bus.py substitutes the correct half-window base per
; payload at build time (SOLVED -- see this file's header; BongDelay ships
; on payload B, base 0x38000, serving tracks 1-4).
        move    #>$ffffff,m0            ; audio is read and written via r0
        move    #>$30000,x0
        move    x0,x:(r7+$31)

; ---- warm-up: zero both lines and persistent state before running --------
; Same tagged-counter idiom as dsp/reverb89.asm/dsp/reverb_server.asm, but a
; DIFFERENT TAG -- $2e0000, where reverb_server uses $2c0000. Both effects
; keep their counter in the same r7+$82 slot and the dispatcher does NOT clear
; the state block when a track's effect changes, so with a shared tag the
; incoming effect read the outgoing one's counter, saw a valid tag at full
; count, skipped warm-up entirely and ran on the other algorithm's leftover
; buffers. Measured on hardware as "the track will not switch between DELAY
; and REVERB SERVER" (BUS.md's hardware test 3). A distinct tag makes the
; other effect's counter fail the tag compare, restarting warm-up exactly as
; a cold start does. ($82 = $2e0000 | count.) Necessary here too: LineL and
; LineR hold boot garbage on
; first use, and this engine has real feedback, so uncleared garbage would
; recirculate rather than just play once and vanish. Sized for this file's
; 32768-word allocation: 128 words/block * 256 blocks = 32768 exactly.
        move    x:(r7+$82),a
        move    #>$fffe00,x0
        and     x0,a                    ; tag field -- AND cleans A1 only
        move    a1,x0
        move    x0,a                    ; A2-clean before the compare
        move    #>$2e0000,x0
        cmp     x0,a
        beq     dwarmtag
        clr     a                       ; garbage tag: warm-up starts at 0
        bra     dwarmrun
dwarmtag:
        move    x:(r7+$82),a
        move    #>$1ff,x0
        and     x0,a
        move    a1,x0
        move    x0,a                    ; the count, A2-clean
        move    #>$100,x0
        cmp     x0,a
        bge     dwarmdone               ; warmed: run the delay
dwarmrun:
        move    a,x:(r7+$15)            ; count, for the save below
        asl     #$7,a,a                 ; count*128
        move    x:(r7+$31),x0
        add     x0,a
        move    a,r5                    ; base + count*128
        clr     b                       ; the zero source ...
        move    x:(r7+$31),x0           ; ... and both fill the AGU slot
        do      #128,>dwarmz
        move    b,y:(r5)+
dwarmz:
        move    b,x:(r7+$70)
        move    b,x:(r7+$71)
        move    b,x:(r7+$77)
        move    b,x:(r7+$78)
        move    b,x:(r7+$6c)            ; PITCH head ages start at 0 (they are
        move    b,x:(r7+$6d)            ; masked on load too, but determinism
                                        ; is what verify-delay bit-compares)
        move    b,x:(r7+$19)            ; grain-jitter state: previous ages and
        move    b,x:(r7+$1a)            ; the four latched offsets all start at
        move    b,x:(r7+$1b)            ; 0, so a fresh instance is
        move    b,x:(r7+$1c)            ; reproducible (verify-delay compares
        move    b,x:(r7+$1d)            ; bit-exactly, and a boot-garbage
        move    b,x:(r7+$1e)            ; offset would index a wild read)
        move    b,x:(r7+$1f)
        move    b,x:(r7+$20)
        move    b,x:(r7+$21)
        move    b,x:(r7+$24)            ; shifted output taps: only read in
        move    b,x:(r7+$25)            ; PITCH, cleared for determinism
        move    #>$123456,a             ; PRNG seed: any nonzero word (xorshift
        move    a,x:(r7+$18)            ; is dead at 0), fixed for determinism
        move    x:(r7+$15),a            ; reload count
        move    #>$1,x0
        add     x0,a
        move    #>$2e0000,x0
        add     x0,a                    ; tag | count+1
        move    a,x:(r7+$82)
        bra     dry                     ; output stays dry until warm
dwarmdone:
        move    x:(r7+$31),x0           ; LineL base

; ---- per-block: TIME, FDBK, TONE, PING, MIX -------------------------------
        move    x:(r6),a
        and     #>$7f0000,a             ; knob field only
        asr     #$9,a,a                 ; value*128 (0..16256)
        move    #>64,x0
        add     x0,a                    ; floor 64 samples (~1.45 ms)
        move    a,x:(r7+$75)            ; TIME, 64..16320 samples

        move    x:(r6+$1),x0
        move    #>$700000,y1
        mpy     x0,y1,a
        move    a,x:(r7+$73)            ; FDBK, 0 .. ~0.87

        move    x:(r6+$2),x0
        move    #>$700000,y1
        mpy     x0,y1,a
        move    #>$100000,x0
        add     x0,a
        move    a,x:(r7+$72)            ; TONE, 0.125 (dark) .. 0.99 (bright)

        move    x:(r6+$3),x0
        move    x0,a
        move    a,x:(r7+$74)            ; PING, 0 .. ~0.99
        move    #>$7fffff,a
        sub     x0,a
        move    a,x:(r7+$80)            ; 1 - PING

        move    x:(r6+$4),x0
        move    x0,x:(r7+$76)           ; MIX, 0 .. ~0.99

        move    x:(r6+$5),x0
        move    x0,x:(r7+$85)           ; ->VERB WET level (BUS.md task 10)

        move    x:(r6+$d),x0
        move    x0,x:(r7+$86)           ; ->VERB DRY level (BUS.md task 10/11)

; ---- MODE: engine select, page-2 slot 7 ($c bits 8-15) -- v2 spine --------
; Same field, same extract, same MSB-aligned convention as ChonVerb's MODE
; (dsp/reverb_server.asm). STAGE 1: CLEAN is the only engine, so every value
; -- including whatever an undefined descriptor slot leaves in this word on
; hardware -- runs CLEAN. When PITCH lands, the dispatch compares MSB-aligned
; short immediates on $69, and unknown values must keep falling through to
; CLEAN: a wrong select degrades to the trad delay, never to silence. The
; descriptor's MODE select (RENAMES/DEFAULTS/PAGE2_COUNTS in build_bus.py)
; lands with the second mode. DMODE=n (build_bus.py) substitutes a literal
; at the marker below -- dsp_host cannot drive companion fields.
        move    x:(r6+$c),a
        and     #>$ff00,a               ; slot 7's companion field, not the knob
        move    a1,x0
        move    x0,a                    ; A2-clean (AND cleans A1 only)
        asl     #$8,a,a                 ; -> MSB-aligned ($010000 per step)
; DMODE_OVERRIDE
        move    a,x:(r7+$69)            ; MODE, this block (0 = CLEAN)

; ---- PITCH interval select -> per-line age steps (v2 stage 2) -------------
; Page-2 slot 9's companion field, r6+$d LOW bits -- ChonVerb's WIDTH/->DEL
; idiom exactly (companion low-byte fields publish small counts; this one is
; count 4). Decoded every block regardless of MODE (cheap, and keeps the
; PITCH state warm across a MODE flip). The step is the head's age advance
; per sample in Q13.10: age DECREASES by (rate-1) for an upshift, so
;   +12 (rate 2.0)  -> step +$400 (1.0 sample/sample)
;   +7  (rate 1.5)  -> step +$200 (0.5)
;   -12 (rate 0.5)  -> step -$200 (age grows: the head falls behind)
;   det (rate 1+-e) -> +-$9 = +-15.1 cents, L up / R down -- the one select
;                      where the two lines' steps differ
; Stored as full signed words; the per-sample update wraps with & $7fffff,
; and two's complement subtraction is exact under that mask.
        move    x:(r6+$d),a
        and     #>$7f,a                 ; select index 0..3 (companion low byte)
; DINT_OVERRIDE
        move    a1,x0
        move    x0,a                    ; A2-clean before the compares
        move    #>$1,x0
        cmp     x0,a
        beq     pint7
        move    #>$2,x0
        cmp     x0,a
        beq     pintm12
        move    #>$3,x0
        cmp     x0,a
        beq     pintdet
        move    #>$1000,a               ; index 0 (and any garbage): +12
        move    a,x:(r7+$6a)
        move    a,x:(r7+$6b)
        bra     pintend
pint7:
        move    #>$800,a                ; +7
        move    a,x:(r7+$6a)
        move    a,x:(r7+$6b)
        bra     pintend
pintm12:
        move    #>$fff800,a             ; -12
        move    a,x:(r7+$6a)
        move    a,x:(r7+$6b)
        bra     pintend
pintdet:
        move    #>$24,a                 ; detune: L up 15 cents
        move    a,x:(r7+$6a)
        move    #>$ffffdc,a             ; R down 15 cents
        move    a,x:(r7+$6b)
pintend:

; ---- PITCH lag base: TIME clamped to keep lag + window + lerp in the line -
; Max head lag = base + 8191 (age) + 1 (lerp's older neighbour); it must not
; reach 16384 or the read wraps onto data written THIS lap. sub/branch, not
; cmp (the cmp-encodes-as-max trap family: sub sets N and V properly).
        move    x:(r7+$75),a            ; TIME, 64..16320
        move    #>13311,x0              ; 16384 - 2048 - 1024 - 1 (window, the
                                        ; grain jitter's max, and the lerp's
                                        ; older neighbour)
        sub     x0,a
        tst     a
        ble     plagok                  ; TIME <= cap: keep it
        clr     a                       ; over: excess -> 0, i.e. clamp
plagok:
        add     x0,a                    ; min(TIME, 14335)
        move    a,x:(r7+$6e)            ; PLAGB, the pitch heads' lag base

; ---- rebuild both line pointers from saved phase --------------------------
; Same A2-clean discipline as dsp/reverb89.asm's phase reload: garbage with
; bit 23 set would sign-extend and saturate the following move a,rN to
; $800000, which hangs the bus forever (the two-track-freeze mechanism).
        move    x:(r7+$70),a            ; LineL phase
        move    #>$3fff,x0
        and     x0,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$31),x0           ; LineL base
        add     x0,a
        move    a,r1                    ; LineL write pointer

        move    x:(r7+$31),a            ; LineR base = LineL base + 0x4000,
        move    #>$4000,x0              ; stashed for the per-sample manual
        add     x0,a                    ; wraps (v2 spine)
        move    a,x:(r7+$68)

        move    x:(r7+$71),a            ; LineR phase
        move    #>$3fff,x0
        and     x0,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$68),x0           ; LineR base
        add     x0,a
        move    a,r2                    ; LineR write pointer

; v2 SPINE: NO AGU MODULO. m1/m2 stay at the linear invariant ($ffffff);
; the TIME-behind read address is computed per sample and the write
; pointers are wrapped by hand below. n1/n2 are unused.

        move    #>$1,n0
        do      n7,>dlyend

; ---- input: own dry mono sum + shared DELAY bus accumulator --------------
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$7d)            ; own dry mono
        move    a,x:(r7+$83)            ; own dry mono, stashed BEFORE the bus
                                        ; is folded in below -- the ->VERB DRY
                                        ; send (BUS.md task 10) taps dry alone
        move    x:(r7+$63),a            ; this sample's ACC read address
        move    a,r5
        move    y:(r5),x0               ; last block's fully-summed sends
        move    x:(r7+$7f),y1           ; this block's bus gain 1/N
        mpy     x0,y1,b                 ; hold total drive constant vs N --
                                        ; signed (2000c8, disassembled from
                                        ; the emitted image): x0 is a bus
                                        ; sample and can be negative, y1
                                        ; (1/N) never
        asl     #$3,b,b                 ; undo the writers' 3-bit headroom
        move    x:(r7+$7d),a
        add     b,a
        move    a,x:(r7+$7d)            ; x_in = dry + bus
        move    x:(r7+$63),a
        move    #>$1,x0
        add     x0,a
        move    a,x:(r7+$63)            ; advance ACC read pointer

; ---- the FEEDBACK LOOP's taps: ALWAYS the unshifted read (v2 stage 2c) ----
; NON-CASCADING PITCH. Until stage 2c the shifted taps WERE the loop's taps,
; so every repeat was shifted again: repeat n had been through the shifter n
; times and carried n generations of splice artifact. That compounding, not
; the splice itself, is most of what an ear calls "machine" -- and ChonVerb
; hit exactly this and fixed it the same way (its shimmer deliberately cut
; its own cascade; see dsp/reverb_server.asm's SHIMMER block).
;
; Now the loop recirculates the CLEAN tap and the shifter sits on the OUTPUT
; only, so every repeat is shifted exactly ONCE: a fixed-interval harmoniser
; on the delay's output rather than a climbing ladder. TONE, PING, FDBK and
; the write-back are all mode-blind and bit-identical to CLEAN's; the
; substitution happens after the lines are written (below), so nothing
; shifted ever re-enters the loop.
;
; ⚠️ The climb is GONE by construction -- +12 no longer walks up in octaves.
; That was the Crystal behaviour stage 2 chose on purpose; it is exactly
; what compounds the artifact, and the ear rejected it (12 Aug). If a climb
; is ever wanted back it belongs on a select, not as the only topology.
;
; ---- CLEAN taps: manual wrap, no AGU modulo (v2 spine) --------------------
; read addr = base + ((wr - TIME) & $3fff). The AND is exact because both
; line bases are 0x4000-aligned, so the base falls out of the mask; wr-TIME
; never goes negative (base >= 0x30000 > TIME's 16320 max). A2 stays
; consistent through the AND (small positive values only) and is re-cleaned
; via the a1->x0->a idiom regardless -- the A2-staleness store trap.
        move    r1,a
        move    x:(r7+$75),x0           ; TIME
        sub     x0,a                    ; wr - TIME
        and     #>$3fff,a               ; read phase
        move    a1,x0
        move    x0,a                    ; A2-clean
        move    x:(r7+$31),x0           ; LineL base
        add     x0,a
        move    a,r5
        move    y:(r5),a
        move    a,x:(r7+$79)            ; dL

        move    r2,a
        move    x:(r7+$75),x0           ; TIME
        sub     x0,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$68),x0           ; LineR base
        add     x0,a
        move    a,r5
        move    y:(r5),a
        move    a,x:(r7+$7a)            ; dR

; ---- MODE dispatch: PITCH additionally computes the SHIFTED OUTPUT taps ---
; 0 and every unknown value run the loop's clean taps alone -- a wrong select
; degrades to the trad delay, never to silence (the stage-1 rule). The
; compare is the safe `cmp x0,a` form.
; MODEFORK_BEGIN -- cycle_count.py: exactly one of the two paths between here
; and MODEFORK_END runs per sample; the tool prices the WORST one, not both.
        move    x:(r7+$69),a
        move    #>$10000,x0             ; 1 << 16, MSB-aligned like the store
        cmp     x0,a
        bne     pdone
; MODEFORK_MID -- CLEAN's path is the fall-through above; PITCH starts here

; ---- PITCH: dual crossfaded lerp heads per line (v2 stage 2) --------------
; The shimmer-v3 machinery (dsp/reverb_server.asm SHIMMER block) reading the
; DELAY LINE ITSELF -- no separate shift buffer exists or fits; both line
; buffers fill this server's entire half-window, and reading the line at
; moving lag is the Microcosm-family topology anyway (GRAIN inherits exactly
; this addressing). Per line:
;
;   age (Q11.12, persistent, wraps mod 2048 samples) advances by the
;   interval step; head lag = PLAGB + age + JITTER, so an upshift's head
;   slides TOWARD the write pointer, replaying material at rate
;   (1 + step/4096). Head 1 runs half a window (1024 samples) behind head 0.
;   Each head: FULL-OVERLAP complementary triangle window on AGE
;   (t = 1024-|age-1024|), smoothstepped, times a LERPED line read (integer
;   lag from age's top bits, Q23 fraction from its low 12 -- truncation is
;   the floor that cost the first shimmer, lerp is mandatory). Smoothstep
;   obeys s(g)+s(1-g)=1, so g0+g1 == 1 EXACTLY at every age: loop gain never
;   exceeds FDBK and PITCH inherits CLEAN's stability bound.
;
;   FULL-OVERLAP WINDOW, 12 Aug 2026, replacing the shimmer trapezoid (ramp
;   256, flat top, silent upper half). Measured on a 219.98 Hz sine, single
;   generation, +12: the trapezoid's near-rectangular switching put splice
;   sidebands every +-43.1 Hz at -18.7 dB with a slowly-decaying harmonic
;   ladder (-27, -28, -33...) -- audibly "glitchy metallic" on a naked echo
;   (the reverb wash hid the same machinery in shimmer). Full-overlap turns
;   the switching waveform sinusoidal: higher orders collapsed 20-25 dB,
;   first pair -18.7/-20.9 -> -26.0/-33.7. Ear (Sam): "bit better", still
;   "robo".
;
;   ❌ WIDENING THE WINDOW IS RETRACTED, same day, by measurement AND ear.
;   4x (2048 -> 8192, age Q13.10) was built on the theory that the residual
;   pair was a lattice displacement that scales with window length. It is
;   not: at EVERY window length the octave arrives as TWO EQUAL LINES a lap
;   apart with nothing at 2f -- suppressed-carrier AM, i.e. the two heads
;   (a half window = 93 ms apart on the line, so an arbitrary relative
;   phase -- 158 deg for this tone) cancelling once per lap. Widening only
;   moved the cancellation rate 43.1 -> 10.8 Hz, i.e. buzz -> flutter; Sam
;   heard the 8192 build as "robo and fluttery" and it cost half the PITCH
;   delay range. A ramp-width sweep at C=8192 (R=512/1024/2048/4096)
;   confirmed the trade is 1-D and has no good point: envelope ripple
;   6.3/10.3/12.6/13.5 dB against off-carrier energy -8.7/-10.3/-14.5/
;   -35.6 dB. The defect is PERIODICITY, not window shape -- see the
;   jitter block below.
;
; The shifted taps land in $79/$7a exactly where CLEAN's taps land, so
; everything downstream -- TONE damping, the PING crossfeed, FDBK write-back,
; MIX, the ->VERB send -- is one engine, mode-blind. Each REPEAT re-shifts:
; the climbing-octave Crystal behaviour, on purpose (the reverb's shimmer
; deliberately removed its cascade; a delay's discrete repeats are where a
; climb IS the effect).
;
; mpy orientation throughout: the possibly-negative operand (tap, t1-t0) is
; ALWAYS x0, the first operand of the audited-signed `mpy x0,y1` form; y1
; only ever carries frac or a window gain, both strictly non-negative.
pmode:
; ---- grain jitter PRNG (v2 stage 2b) --------------------------------------
; 23-bit xorshift, shifts 15/15/8: maximal period 8388607 (190 s of samples,
; verified by simulation against the exact masked recurrence, along with a
; flat distribution of the 10-bit field taken below). Every shift result is
; re-cleaned through the a1->x0->a idiom because `and`/`eor` write A1 only
; and leave A2 STALE -- the store trap. Advanced every sample; each head
; LATCHES it at its own wrap, so the four grains scatter independently.
        move    x:(r7+$18),a            ; state
        move    a1,x0
        asl     #$f,a,a
        and     #>$7fffff,a
        eor     x0,a                    ; x ^= (x << 15)
        move    a1,x0
        move    x0,a
        asr     #$f,a,a                 ; state is always positive, so the
        eor     x0,a                    ; arithmetic shift IS a logical one
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        and     #>$7fffff,a
        eor     x0,a                    ; x ^= (x << 8)
        move    a1,x0
        move    x0,a                    ; A2 clean before the store
        move    a,x:(r7+$18)
        asr     #$d,a,a                 ; take the top 10 bits: 0..1023 samples
        and     #>$3ff,a                ; of scatter (23 ms), the SPRAY depth
        move    a1,x0                   ; GRAIN will put on a knob
        move    x0,a
        move    a,x:(r7+$21)            ; this sample's candidate offset
; ---- Line L: age update ---------------------------------------------------
        move    x:(r7+$6c),a            ; ageL, Q11.12
        move    x:(r7+$6a),x0           ; stepL (signed)
        sub     x0,a
        and     #>$7fffff,a             ; wrap mod 2048 samples
        move    a1,x0
        move    x0,a                    ; A2-clean; boot garbage dies here
        move    a,x:(r7+$6c)
; ---- grain scatter: each head latches a new offset at ITS OWN wrap --------
; The whole point of stage 2b. With a FIXED grain start the two heads sit a
; half window (23 ms) apart on the line for ever, so for any steady partial
; their relative phase is constant and they cancel on a metronome: measured,
; the octave arrives as two equal lines one lap apart with nothing at 2f
; (suppressed-carrier AM). Sam heard that as "robo" at a 43 Hz lap and
; "fluttery" at 10.8 Hz -- the same defect at two rates, which is why no
; window shape or length fixed it. Re-scattering each grain's source
; position by 0..1023 samples makes the cancellation APERIODIC: the ear
; stops tracking it as a machine and hears texture, which is what the
; granular reference (PLAN 3.1) is actually made of.
;
; The jump is inaudible because a head's window gain is exactly 0 at its own
; wrap -- so the full-overlap window is a PREREQUISITE for this, not just a
; cleanup. GRAIN (stage 5) is this mechanism with more heads and the depth
; on a SPRAY knob.
        move    a,x:(r7+$22)            ; park age
        move    x:(r7+$19),x0
        sub     x0,a                    ; d = age - previous age
        abs     a
        move    #>$400000,x0
        sub     x0,a                    ; |d| > half a cycle == this head just
                                        ; wrapped; N set means it did NOT
        move    x:(r7+$21),b            ; this sample's candidate offset
        move    x:(r7+$1b),x0           ; the grain's current offset
        tmi     x0,b                    ; no wrap -> keep it. Tcc, never a
                                        ; hand-rolled mask (A2 staleness)
        move    b,x:(r7+$1b)
        move    x:(r7+$22),a
        move    a,x:(r7+$19)           ; prevL0 := ageL0
; head 1 runs half a window ahead, so it wraps half a lap later
        move    #>$400000,x0
        add     x0,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a                    ; A2 clean
        move    a,x:(r7+$23)            ; park age
        move    x:(r7+$1a),x0
        sub     x0,a                    ; d = age - previous age
        abs     a
        move    #>$400000,x0
        sub     x0,a                    ; |d| > half a cycle == this head just
                                        ; wrapped; N set means it did NOT
        move    x:(r7+$21),b            ; this sample's candidate offset
        move    x:(r7+$1c),x0           ; the grain's current offset
        tmi     x0,b                    ; no wrap -> keep it. Tcc, never a
                                        ; hand-rolled mask (A2 staleness)
        move    b,x:(r7+$1c)
        move    x:(r7+$23),a
        move    a,x:(r7+$1a)           ; prevL1 := ageL1
        move    x:(r7+$22),a            ; ageL0 back for the heads below
; ---- Line L, head 0: lerp read at lag PLAGB + age + scatter ---------------
        move    a,x:(r7+$15)            ; park age_fx
        asr     #$c,a,a                 ; age_int, 0..2047
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$6f)            ; park age_int
        move    r1,a                    ; LineL write pointer
        move    x:(r7+$6e),x0           ; PLAGB
        sub     x0,a
        move    x:(r7+$6f),x0           ; age_int
        sub     x0,a
        move    x:(r7+$1b),x0           ; this grain's scatter
        sub     x0,a
        and     #>$3fff,a               ; read phase (t0, the newer neighbour)
        move    a1,x0
        move    x0,a                    ; A2-clean
        move    a,x:(r7+$16)            ; park phase
        move    x:(r7+$31),x0           ; LineL base
        add     x0,a
        move    a,r5
        move    y:(r5),a                ; t0
        move    a,x:(r7+$17)            ; park t0
        move    x:(r7+$16),a
        move    #>$1,x0
        sub     x0,a
        and     #>$3fff,a               ; phase-1, wrapped: one sample OLDER
        move    a1,x0
        move    x0,a
        move    x:(r7+$31),x0
        add     x0,a
        move    a,r5
        move    y:(r5),a                ; t1
        move    x:(r7+$17),x0           ; t0
        sub     x0,a                    ; t1 - t0, signed
        move    a1,x0                   ; -> FIRST mpy operand
        move    x:(r7+$15),a            ; age_fx
        and     #>$fff,a                ; sample fraction, Q12 (a2 already 0)
        asl     #$b,a,a                 ; -> Q23
        move    a1,y1                   ; frac
        mpy     x0,y1,a                 ; frac*(t1-t0), signed
        move    x:(r7+$17),x0
        add     x0,a                    ; tap = t0 + frac*(t1-t0)
        move    a,x:(r7+$17)            ; park tap (t0 dead)
; window: full-overlap triangle t = 1024 - |age-1024|, smoothstepped
        move    x:(r7+$6f),a            ; age_int
        move    #>1024,x0
        sub     x0,a
        abs     a
        neg     a
        add     x0,a                    ; t = 1024 - |age-1024|, 0..1024
        asl     #$d,a,a                 ; g = t/1024, Q23; t=1024 -> 2^23,
                                        ; exact in the 56-bit acc
        move    a,x0                    ; LIMITING move: 2^23 clips $7fffff
        move    a,y1                    ; smoothstep s = g^2*(3-2g), zero-slope
        mpy     x0,y1,a                 ; g^2       joins at both ends
        move    a,x:(r7+$15)            ; park g^2 (age_fx dead)
        move    #>$7fffff,a
        sub     x0,a
        move    a,y1                    ; 1-g
        move    x:(r7+$15),x0
        mpy     x0,y1,a                 ; g^2*(1-g)
        asl     #$1,a,a
        add     x0,a                    ; s = g^2 + 2*g^2*(1-g)
        move    a1,y1                   ; g0
        move    x:(r7+$17),x0           ; tap (signed) first
        mpy     x0,y1,a
        move    a,b                     ; b = head 0's contribution
; ---- Line L, head 1: age + half a window, same machinery ------------------
        move    x:(r7+$6c),a
        move    #>$400000,x0            ; +1024 samples in Q11.12 (half the
                                        ; window)
        add     x0,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a                    ; age1_fx, clean
        move    a,x:(r7+$15)
        asr     #$c,a,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$6f)
        move    r1,a
        move    x:(r7+$6e),x0
        sub     x0,a
        move    x:(r7+$6f),x0
        sub     x0,a
        move    x:(r7+$1c),x0           ; this grain's scatter
        sub     x0,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$16)
        move    x:(r7+$31),x0
        add     x0,a
        move    a,r5
        move    y:(r5),a
        move    a,x:(r7+$17)
        move    x:(r7+$16),a
        move    #>$1,x0
        sub     x0,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$31),x0
        add     x0,a
        move    a,r5
        move    y:(r5),a
        move    x:(r7+$17),x0
        sub     x0,a
        move    a1,x0
        move    x:(r7+$15),a
        and     #>$fff,a
        asl     #$b,a,a
        move    a1,y1
        mpy     x0,y1,a
        move    x:(r7+$17),x0
        add     x0,a
        move    a,x:(r7+$17)
        move    x:(r7+$6f),a
        move    #>1024,x0
        sub     x0,a
        abs     a
        neg     a
        add     x0,a
        asl     #$d,a,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    a,x:(r7+$15)
        move    #>$7fffff,a
        sub     x0,a
        move    a,y1
        move    x:(r7+$15),x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     x0,a
        move    a1,y1                   ; g1
        move    x:(r7+$17),x0
        mpy     x0,y1,a
        add     b,a                     ; g0*tap0 + g1*tap1, g0+g1 ~= 1
        move    a,x:(r7+$24)            ; shifted OUTPUT tap L -- NOT $79:
                                        ; the loop's tap stays unshifted
; ---- Line R: identical, on r2/base $68/age $6d/step $6b -------------------
        move    x:(r7+$6d),a
        move    x:(r7+$6b),x0
        sub     x0,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$6d)
        move    a,x:(r7+$22)            ; park age
        move    x:(r7+$1d),x0
        sub     x0,a                    ; d = age - previous age
        abs     a
        move    #>$400000,x0
        sub     x0,a                    ; |d| > half a cycle == this head just
                                        ; wrapped; N set means it did NOT
        move    x:(r7+$21),b            ; this sample's candidate offset
        move    x:(r7+$1f),x0           ; the grain's current offset
        tmi     x0,b                    ; no wrap -> keep it. Tcc, never a
                                        ; hand-rolled mask (A2 staleness)
        move    b,x:(r7+$1f)
        move    x:(r7+$22),a
        move    a,x:(r7+$1d)           ; prevR0 := ageR0
        move    #>$400000,x0
        add     x0,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$23)            ; park age
        move    x:(r7+$1e),x0
        sub     x0,a                    ; d = age - previous age
        abs     a
        move    #>$400000,x0
        sub     x0,a                    ; |d| > half a cycle == this head just
                                        ; wrapped; N set means it did NOT
        move    x:(r7+$21),b            ; this sample's candidate offset
        move    x:(r7+$20),x0           ; the grain's current offset
        tmi     x0,b                    ; no wrap -> keep it. Tcc, never a
                                        ; hand-rolled mask (A2 staleness)
        move    b,x:(r7+$20)
        move    x:(r7+$23),a
        move    a,x:(r7+$1e)           ; prevR1 := ageR1
        move    x:(r7+$22),a            ; ageR0 back
        move    a,x:(r7+$15)
        asr     #$c,a,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$6f)
        move    r2,a
        move    x:(r7+$6e),x0
        sub     x0,a
        move    x:(r7+$6f),x0
        sub     x0,a
        move    x:(r7+$1f),x0           ; this grain's scatter
        sub     x0,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$16)
        move    x:(r7+$68),x0           ; LineR base
        add     x0,a
        move    a,r5
        move    y:(r5),a
        move    a,x:(r7+$17)
        move    x:(r7+$16),a
        move    #>$1,x0
        sub     x0,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$68),x0
        add     x0,a
        move    a,r5
        move    y:(r5),a
        move    x:(r7+$17),x0
        sub     x0,a
        move    a1,x0
        move    x:(r7+$15),a
        and     #>$fff,a
        asl     #$b,a,a
        move    a1,y1
        mpy     x0,y1,a
        move    x:(r7+$17),x0
        add     x0,a
        move    a,x:(r7+$17)
        move    x:(r7+$6f),a
        move    #>1024,x0
        sub     x0,a
        abs     a
        neg     a
        add     x0,a
        asl     #$d,a,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    a,x:(r7+$15)
        move    #>$7fffff,a
        sub     x0,a
        move    a,y1
        move    x:(r7+$15),x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     x0,a
        move    a1,y1
        move    x:(r7+$17),x0
        mpy     x0,y1,a
        move    a,b
        move    x:(r7+$6d),a
        move    #>$400000,x0
        add     x0,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$15)
        asr     #$c,a,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$6f)
        move    r2,a
        move    x:(r7+$6e),x0
        sub     x0,a
        move    x:(r7+$6f),x0
        sub     x0,a
        move    x:(r7+$20),x0           ; this grain's scatter
        sub     x0,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$16)
        move    x:(r7+$68),x0
        add     x0,a
        move    a,r5
        move    y:(r5),a
        move    a,x:(r7+$17)
        move    x:(r7+$16),a
        move    #>$1,x0
        sub     x0,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$68),x0
        add     x0,a
        move    a,r5
        move    y:(r5),a
        move    x:(r7+$17),x0
        sub     x0,a
        move    a1,x0
        move    x:(r7+$15),a
        and     #>$fff,a
        asl     #$b,a,a
        move    a1,y1
        mpy     x0,y1,a
        move    x:(r7+$17),x0
        add     x0,a
        move    a,x:(r7+$17)
        move    x:(r7+$6f),a
        move    #>1024,x0
        sub     x0,a
        abs     a
        neg     a
        add     x0,a
        asl     #$d,a,a
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    a,x:(r7+$15)
        move    #>$7fffff,a
        sub     x0,a
        move    a,y1
        move    x:(r7+$15),x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     x0,a
        move    a1,y1
        move    x:(r7+$17),x0
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$25)            ; shifted OUTPUT tap R
; MODEFORK_END
pdone:

; ---- one-pole damping in the feedback path: s += c*(d-s) ------------------
        move    x:(r7+$77),b            ; state L
        move    x:(r7+$79),a            ; dL
        sub     b,a
        move    a,x0
        move    x:(r7+$72),y1           ; TONE coefficient
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$77)            ; new state L
        move    a,x:(r7+$7b)            ; fL == this sample's wet L

        move    x:(r7+$78),b            ; state R
        move    x:(r7+$7a),a            ; dR
        sub     b,a
        move    a,x0
        move    x:(r7+$72),y1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$78)            ; new state R
        move    a,x:(r7+$7c)            ; fR == this sample's wet R

; ---- ping-pong crossfeed matrix, feedback path only -----------------------
        move    x:(r7+$7b),x0           ; fL
        move    x:(r7+$80),y1           ; 1-PING
        mpy     x0,y1,a
        move    x:(r7+$7c),x0           ; fR
        move    x:(r7+$74),y1           ; PING
        mpy     x0,y1,b
        add     b,a                     ; fbIntoL
        move    a,x:(r7+$7e)

        move    x:(r7+$7c),x0           ; fR
        move    x:(r7+$80),y1
        mpy     x0,y1,a
        move    x:(r7+$7b),x0           ; fL
        move    x:(r7+$74),y1
        mpy     x0,y1,b
        add     b,a                     ; fbIntoR
        move    a,x:(r7+$81)

; ---- write both lines: only LineL receives x_in -- LineR only ever hears
; whatever crosses over through the PING matrix (header note above) -------
        move    x:(r7+$7e),x0           ; fbIntoL
        move    x:(r7+$73),y1           ; FDBK
        mpy     x0,y1,a
        move    x:(r7+$7d),x0           ; x_in
        add     x0,a
        move    a,y:(r1)+                ; LineL write, advance

        move    x:(r7+$81),x0           ; fbIntoR
        move    x:(r7+$73),y1
        mpy     x0,y1,a
        move    a,y:(r2)+                ; LineR write, advance -- no x_in term

; ---- wrap both write pointers by hand (the modulo this engine no longer
; asks the AGU for). After the +1 a pointer is base .. base+0x4000 inclusive;
; masking the phase and re-adding the base folds base+0x4000 back to base
; and leaves every other value alone.
        move    r1,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a                    ; A2-clean
        move    x:(r7+$31),x0           ; LineL base
        add     x0,a
        move    a,r1
        move    r2,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$68),x0           ; LineR base
        add     x0,a
        move    a,r2

; ---- PITCH: the wet becomes the SHIFTED tap (v2 stage 2c) ----------------
; Placed HERE deliberately: both lines have already been written above from
; the clean tap, so the shift can never re-enter the feedback loop. From
; this point on the wet -- own-track MIX, the shared DELAY WET buffer and
; the ->VERB send -- carries the shifted signal, and everything downstream
; stays mode-blind.
;
; Branchless via Tcc: cmp sets Z, the intervening moves do not disturb it,
; and teq moves a CLEAN register into the accumulator (never a hand-rolled
; mask -- the A2-staleness store trap). In CLEAN mode teq does not fire and
; the wet is bit-identical to v1's.
        move    x:(r7+$69),a
        move    #>$10000,x0
        cmp     x0,a                    ; Z set == PITCH
        move    x:(r7+$24),x0           ; shifted L
        move    x:(r7+$7b),b            ; loop's wet L
        teq     x0,b
        move    b,x:(r7+$7b)
        move    x:(r7+$25),x0           ; shifted R
        move    x:(r7+$7c),b
        teq     x0,b
        move    b,x:(r7+$7c)

; ---- own track: wet added to dry, MIX-scaled ------------------------------
        move    x:(r7+$7b),x0           ; wet L = fL
        move    x:(r7+$76),y1           ; MIX
        mpy     x0,y1,a
        move    x:(r0),x0
        add     x0,a
        move    a,x:(r0)                ; L in place

        move    x:(r7+$7c),x0           ; wet R = fR
        move    x:(r7+$76),y1
        mpy     x0,y1,a
        move    x:(r0+n0),x0
        add     x0,a
        move    a,x:(r0+n0)             ; R in place

; ---- write mono wet to the shared DELAY WET buffer (BUS.md) --------------
        move    x:(r7+$64),a            ; this sample's WET write address
        move    a,r5
        move    x:(r7+$7b),a            ; fL
        move    x:(r7+$7c),x0           ; fR
        add     x0,a
        asr     #$1,a,a                 ; mono average
        move    a,x:(r7+$87)            ; stash for the ->VERB WET send below
        move    a,y:(r5)
        move    x:(r7+$64),a
        move    #>$1,x0
        add     x0,a
        move    a,x:(r7+$64)            ; advance WET write pointer

; ---- ->VERB: wet (this delay's own output) + dry (this track's own
; pre-effect signal), scaled and summed into the shared REVERB ACC bus
; (BUS.md task 10). One-directional by construction -- see this file's
; header and dsp/reverb_server.asm's ->DELAY note for why the reverse never
; carries wet.
        move    x:(r7+$87),x0           ; delay's own wet, this sample
        move    x:(r7+$85),y1           ; ->VERB WET level
        mpy     x0,y1,a
        move    x:(r7+$83),x0           ; this track's own dry, this sample
        move    x:(r7+$86),y1           ; ->VERB DRY level
        mpy     x0,y1,b
        add     b,a                     ; combined contribution
        move    x:(r7+$84),b            ; this call's REVERB ACC write address
        move    b,r5
        move    y:(r5),b
        add     b,a
        move    a,y:(r5)                ; REVERB ACC[write][i] += contribution
        move    x:(r7+$84),a
        move    #>$1,x0
        add     x0,a
        move    a,x:(r7+$84)            ; advance REVERB ACC write pointer

        move    #>$2,n0
        move    (r0)+n0                  ; advance one stereo frame
        move    #>$1,n0
dlyend:

; ---- save both phases, restore the M registers ----------------------------
        move    r1,a
        move    #>$3fff,x0
        and     x0,a
        move    a,x:(r7+$70)
        move    r2,a
        move    #>$3fff,x0
        and     x0,a
        move    a,x:(r7+$71)
dry:
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m5
        rts
