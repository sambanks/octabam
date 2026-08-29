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
; every DELAY-bus writer registers per block in the DELAY count and writes asr #3;
; this server multiplies the accumulator by 1/count and shifts back up 3.
;
; ---------------------------------------------------------------------------
; BUS.md task 9: DELAY SERVER. An algorithm from scratch -- unlike REVERB
; SERVER (task 8), there is no existing engine to reuse, so this file is the
; first build of it. Same three structural pieces as modules/chonverb/reverb_server.asm
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
;    rotation-flip-and-clear housekeeping as modules/send/send_client.asm and
;    modules/chonverb/reverb_server.asm, split-aware-offset fix included, copied
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
;    ✅ PING=0's HOLE IS CLOSED (v3 stage 2). It used to leave LineR at
;    digital silence for ever -- "R being silent at PING=0 is a real v1
;    characteristic ... worth revisiting" is what this note said, and the
;    revisit measured it: the wet was hard left at PING=0 and leaned
;    +20.1/+14.7/+11.5/+9.2 dB at 32/64/96/127, with no centred setting
;    anywhere on the knob. The input now enters LineR too, scaled by
;    1-PING, so the knob sweeps CENTRED MONO -> FULL PING-PONG with no
;    hole at either end. See the LineR write for why scaling by the knob
;    is what keeps the knob alive on a mono input.
;    PING=~1: full swap -- input enters on L, the first repeat
;    comes back on R, the next on L, alternating. Total loop gain per line
;    is a convex combination of fL/fR scaled by FDBK, so it never exceeds
;    FDBK regardless of PING; stability doesn't depend on this knob, and
;    the new input term is not in the loop at all.
;
;    THE HOST TRACK IS A RETURN, NOT AN INSERT (v3 stage 1, 17 Aug 2026;
;    dry passthrough added in v5, 23 Aug 2026).
;    This is the architectural decision the rest of the file now assumes, so
;    it is stated once, here. The track BongDelay sits on prints the delay's
;    wet PLUS ITS OWN DRY AT UNITY (v5 -- v3..v4 printed the wet alone,
;    which muted any audio living on the host track); its OT track fader is
;    the output level; and its own audio reaches the ENGINE only through the
;    IN knob, on exactly the terms every other track's ->DELAY knob gets --
;    scaled, given the 3-bit headroom, summed into the accumulator's total
;    and divided by a count that includes it. The unity dry is a passthrough,
;    not a privilege: it never enters the engine and never touches the bus.
;
;    What it replaced, and why: the host track used to be privileged twice
;    over. Its dry entered the engine at UNITY, after the bus had already
;    been auto-gained, so it was immune to 1/N and therefore as loud into the
;    delay as every sender combined -- with no knob to trim it (measured
;    17 Aug: host -24.78 dB vs a full-knob send -24.85, identical). And that
;    same dry was MIX's crossfade reference, so MIX did two unrelated jobs at
;    once and walked the stereo image 0.00 -> 7.82 dB across its travel,
;    purely from crossfading a centred mono dry against a wet that leans
;    left. One asymmetry, two symptoms; removing the dry from the output
;    removes both and frees the knob.
;
;    CROSS-BUS SEND (BUS.md task 10): ->VERB, HARDWIRED, no knob. It carries
;    this delay's own processed output into the shared REVERB bus as an
;    additive contribution alongside whatever SEND clients and REVERB
;    SERVER's own dry sum add that block, and it registers in the REVERB
;    count like any other writer. The DRY half and both knobs are gone: a
;    return track has no pre-effect signal worth forwarding, and delay ->
;    reverb is the designed topology rather than a routing option.
;    Delay->reverb is allowed to carry WET;
;    reverb->delay (modules/chonverb/reverb_server.asm's ->DELAY send) is dry only -- see
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
;   r7+$27/$28          TAPE wow / flutter LFO phase (persistent, masked)
;   r7+$29              TAPE mod: the summed offset, then its integer part
;   r7+$2a/$2b/$2c      TAPE per-sample scratch (phase then smoothstep /
;                       t0 / the Q23 lag fraction)
;   r7+$2d/$2e          TAPE wow depth / flutter depth (per block, from the
;                       WOW knob; their sum is bounded by TIME's floor)
;   r7+$2f/$30          TAPE saturation per-sample scratch (the parked write
;                       value w, and its soft-clipped form)
;   r7+$26              FREEZE flag (per block, from the slot-11 select:
;                       0 = running, nonzero = hold the lines)
;   r7+$24/$25          PITCH shifted OUTPUT tap L / R (per sample). Kept
;                       separate from the loop's taps ($79/$7a) so the shift
;                       never re-enters the feedback -- the non-cascading
;                       topology, v2 stage 2c
;   r7+$31              LineL base (hardcoded literal, stashed for symmetry
;                       with modules/chonverb/reverb_server.asm's convention)
;   r7+$32              GRAIN base age, Q11.12 (persistent, masked on load AND
;                       save -- same discipline as $6c/$6d). ONE age serves
;                       all four grains; each takes a fixed quarter-cycle
;                       offset from it, so a single advance moves the cloud
;   r7+$33              SHIFTED-OUTPUT flag (per block): nonzero when the wet
;                       comes from $24/$25 -- PITCH or GRAIN. Replaces the
;                       per-sample MODE compare at the substitution point, so
;                       adding modes there costs nothing per sample
;   r7+$34..$53         GRAIN grain table, 8 records of 4 words, INTERLEAVED
;                       L0 R0 L1 R1 L2 R2 L3 R3 so that the builder walks it
;                       straight through and each reader strides by 8:
;                         +0 age_int, 0..2047       (rebuilt every sample)
;                         +1 latched scatter        (PERSISTENT, see below)
;                         +2 sample fraction, Q23   (rebuilt every sample)
;                         +3 window gain / 2, Q23   (rebuilt every sample)
;                       The field order IS the consumption order in both
;                       loops, which is what lets every access be a plain
;                       post-increment instead of an indexed read
;   r7+$54/$55          this sample's scatter candidates, line L / line R --
;                       two DISJOINT fields of one PRNG word, each scaled by
;                       SPRAY. Per-line candidates are what keep L and R
;                       decorrelated while they share ages and window gains
;   r7+$56..$5b         GRAIN per-sample scratch (builder: age_fx / age_int /
;                       frac / gain / smoothstep temp; reader: phase / t0)
;   r7+$5c              SPRAY depth, Q23 (per block, from the SPRAY knob)
;   r7+$5d              GRAIN per-grain age cursor (the builder's running age)
;   r7+$5e              REVERSE segment phase, 23-bit (persistent, masked on
;                       load AND save). ONE phase for both lines and both
;                       heads -- head 1 is simply half a segment further on
;   r7+$5f              PTCH/SIZE select index, raw 0..3 (per block). Stored
;                       by the PTCH decode so REVERSE can read the SAME select
;                       as a segment SIZE without a second override marker
;   r7+$60/$61          REVERSE segment length S / phase step 2^23/S (per
;                       block, from that index)
;   r7+$62              REVERSE lag floor = min(TIME, 16320 - 2S) (per block)
;                       -- ⚠️ THIS IS THE LAST FREE r7 SLOT. $32..$62 is now
;                       fully allocated and $84+ hangs the unit, so a further
;                       mode needs the Y state table, not this block.
;                       REVERSE reuses GRAIN's $56..$5b as per-sample scratch,
;                       which is safe because the mode alternatives are
;                       mutually exclusive within a sample.
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
;   r7+$76              IN -- this track's OWN send level into the delay
;                       (per block, raw knob used directly as Q1.23). Was
;                       MIX; v3 stage 1 made the host track a return, so
;                       there is no dry left to cross-fade and the knob
;                       became the host's counterpart of send_client's p0
;   r7+$77/$78          TONE filter state, line L / R (persistent)
;   r7+$79/$7a          scratch: dL/dR, raw taps (per sample)
;   r7+$7b/$7c          scratch: fL/fR, damped taps == this sample's wet
;                       outputs (per sample)
;   r7+$7d              scratch: x_in, own dry mono + bus (per sample)
;   r7+$7e/$81          scratch: fbIntoL/fbIntoR (per sample)
;   r7+$7f              bus auto-gain 1/sqrt(N) (per block; read per sample). The
;                       delay-bus mirror of the reverb's $0c -- kept in its
;                       own slot with nothing else ever parked here (the $0c
;                       collision lesson)
;   r7+$80              1 - PING (per block)
;   r7+$82              warm-up tagged counter (stock DARK's slot
;                       convention, reused -- see dsp/reverb89.asm)
;   r7+$83              DRIVE amount d (18 Aug 2026; was FREE since v3 --
;                       ->VERB DRY send, which is gone with its knob
;   r7+$84              this call's REVERB ACC write address (BUS.md task 10,
;                       per-call, advances per sample -- same shape as $63/$64)
;   r7+$85              -VRB level (per block) -- a knob again since 18 Aug
;                       2026 (p5, default 0); was a hardwired $7fffff from v3
;                       stage 1, when the return design was delay-only
;   r7+$86              this block's RESOLVED write offset (0/16/32/48).
;                       Was FREE after v3 stage 1; taken 17 Aug 2026 by the
;                       rotation-tracking fix (docs/XBUS.md step 3). Every bus
;                       address in this file derives from here rather than
;                       from a fresh read of the shared rotation word.
;                       Previously: FREE (v3 stage 1). Held the ->VERB DRY level
;   r7+$87              this sample's own mono wet, stashed at the same point
;                       it's written to the shared DELAY WET buffer (BUS.md
;                       task 10 -- the ->VERB WET send taps that same value)
;
; Parameters (page 1, knob arrives as value<<16, value 0..127):
;   p0 TIME  -> delay length, 64 .. 16320 samples (~1.5 .. 370 ms), a FREE
;              dial that STICKY-SNAPS to a tempo division (24 Aug 2026):
;              near 1/32T .. 1/4 of the tempo the ColdFire cave publishes at
;              r6+$6/$7 it snaps, holds that division through tempo changes,
;              and lets go when the knob moves; the panel prints the
;              division name while held, ms otherwise (modules/tempo-sync/time_fmt.s). See
;              the STICKY SNAP block in proc. floor +
;              value*128 via the same and/asr trick dsp/reverb89.asm's PRE
;              uses (asr #$9 == >>16 then <<7, i.e. *128 without an mpy).
;   p1 FDBK  -> feedback gain, 0 .. ~0.87 (mpy by $700000, no floor: FDBK=0
;              is a single echo, not silence).
;   p2 TONE  -> one-pole coefficient, 0.125 (dark) .. 0.99 (bright). Exact
;              same mapping as reverb89's HI control (proven-safe constants).
;   p3 PING  -> crossfeed amount, 0 (parallel stereo) .. ~0.99 (full
;              ping-pong swap). Used directly as a Q1.23 fraction -- knob<<16
;              already IS value/128 in that format, no mpy needed.
;   p4 IN    -> THIS TRACK'S OWN SEND LEVEL into the delay, 0 .. ~0.99, same
;              "raw knob as Q1.23 multiplier" trick as before. v3 stage 1:
;              was MIX. The host track is a RETURN -- it prints the wet plus
;              its own dry at unity (v5; v3..v4 printed wet alone) -- so the
;              dry/wet crossfade had nothing left to
;              cross-fade and the slot became the host's own ->DELAY knob,
;              identical in range, headroom and 1/N share to the one every
;              other track already has (modules/send/send_client.asm p0).
;   p5       -> FREE. Was ->VERB WET; the send is hardwired now (see $85).
;   p8       -> FREE. Was ->VERB DRY; the send is gone entirely.
;   p7 MODE  -> engine select, page-2 slot 7 companion (r6+$c bits 8-15),
;              count 5: 0 = CLEAN, 1 = PITCH, 2 = (was TAPE -- retired
;              18 Aug 2026, falls through to CLEAN), 3 = GRAIN,
;              4 = REVERSE. Landed with stage 2, per the stage-1 rule that a
;              one-value select draws a dead knob; every unknown value still
;              falls through to CLEAN.
;   p10 SPRAY-> GRAIN scatter depth, page-2 slot 10 KNOB field (r6+$e bits
;              16-22 -- the SAME WORD as FRZE, which is its low byte), 0..127
;              used directly as a Q23 multiplier on each grain's random source
;              offset: 0 = every grain reads the same place (four heads, one
;              position -- the coherent, most PITCH-like end), 127 = the full
;              0..1015-sample scatter. Only read in GRAIN.
;   p6 WOW   -> TAPE wow depth, page-1 slot 6 KNOB field (r6+$b), 0..127.
;              Scales flutter with it (wow/8). Only read in TAPE; harmless
;              in the other modes.
;   p11 FRZE -> FREEZE select, page-2 slot 11 companion (r6+$e low bits),
;              count 2: 0 = running, 1 = hold. Orthogonal to MODE -- frozen
;              + PITCH is shifted reads over held material; frozen while
;              TIME is tempo-locked (always, see p0) is a tempo-locked loop.
;              `DFRZ=n` is the local override (it forces the decoded VALUE;
;              dsp_host also drives companions via -params 7/9/11).
;   p9 PTCH  -> in REVERSE this same select is SIZE: 0 = 4096 samples (93 ms,
;              the longest the line allows -- playing S samples backwards
;              spans 2S of history), 1 = 2048, 2 = 1024, 3 = 512. One select,
;              two meanings, because MODE already says which is in force and
;              page 2 has no spare slot.
;   p9 PTCH  -> PITCH interval select, page-2 slot 9 companion (r6+$d low
;              bits), count 4: 0 = +12, 1 = +7, 2 = -12, 3 = +-detune
;              (~15 cents, L up / R down). Selects, not smooth knobs -- the
;              WIDTH lesson: companion fields read near-boolean at count 128
;              on hardware, small counts publish. DINT=n (build_bus.py) is
;              the local override (dsp_host also drives companions through
;              -params indices 7/9/11 since 17 Aug 2026).
;   p6 ->VERB DRY -> this track's own pre-effect signal, parallel tap into the
;              same REVERB ACC bus, same shape as modules/send/send_client.asm's knobs.
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
; every instance, same reasoning as modules/chonverb/reverb_server.asm's init.
; ---- seed the tracked rotation, so a cold boot cannot start out of step ---
; ⚠️ THE TRACKING CANNOT SELF-CORRECT A BAD START, and the commit that added it
; claimed otherwise. "This client legitimately read PRE-FLIP" and "this client
; is stuck one step AHEAD" give an identical comparison result, every block,
; forever -- no observation separates them, so a client that boots one step
; ahead stays there. Harmless when written; NOT harmless once the clear moved
; one block ahead, because a client stuck one step ahead then writes precisely
; the buffer core 0 is clearing, and every core-1 sender is wiped. That was the
; metallic on every power cycle of R25, and why re-selecting the effect cured
; it: the instance misses blocks during the switch, falls BEHIND, and snaps.
; If it cannot self-correct it must begin correct. init runs on instantiation
; -- exactly what re-selecting does -- so seeding here makes a cold boot
; deterministic. The shared word may advance one step before the first proc;
; that direction DOES snap, so it is safe.
; build_bus.py emits a body here for PAYLOAD B ONLY -- payload A recomputes the
; offset from the shared word every block and has nothing to seed.
; ROTINIT
        rts

proc:
; ---- BOTH calls are audio -------------------------------------------------
; Same dispatcher shape as every other effect in this project -- see
; dsp/reverb89.asm's proc: comment for the full mechanism. Everything below
; re-derives from r7 state per call, so the two sub-calls of a split block
; are sample-continuous by construction.
        move    a,x:(r7+$14)            ; call flag: $010000 = the a=1 call

; ---- BUS.md: split-aware frame offset + position-0 election --------------
; Verbatim from modules/send/send_client.asm / modules/chonverb/reverb_server.asm (BUS.md Known
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

; ---- position-0 housekeeping: flip the shared bus rotation, clear the new
; write-target ACC buffers. Gated on r7==0x6200 AND offset==0 -- copied from
; modules/send/send_client.asm / modules/chonverb/reverb_server.asm, must stay identical.
; Housekeeping is normally done by position 0 (r7 == 0x6200, the bank's first
; FX2 call). That alone breaks the moment the first track's FX2 is NONE: our
; code never runs there, so nobody flips the rotation or clears the
; accumulators, and the bus saturates. NONE became selectable with the task-11
; menu, so this is reachable in ordinary use.
;
; Self-healing election instead. Position 0 still housekeeps whenever it runs.
; Any other instance takes over if it sees that the rotation has NOT changed
; since the last time it ran -- which can only mean nobody housekept in
; between. Costs one r7 word (the rotation this instance last saw) and no new
; global signal, so it needs nothing the bus does not already have.
;
; Gated on the split offset FIRST: only a block's first call may housekeep, so
; a split block's second call can never flip a second time -- the same trap
; the original position-0 code was written around.
; XBUS_GATE -- build_bus.py substitutes a payload gate here when XBUS=1.
; A shared-memory bus is housekept by ONE core only: both cores number their
; own instances from zero, so each core's position 0 believes it is the
; housekeeper and they would flip the shared rotation TWICE a block, cancelling
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
        move    y:>$900,a
        and     #>$30,a
        move    a1,x0
        move    x0,a                    ; offset now, A2-clean
        move    x:(r7+$88),x0
        cmp     x0,a
        bne     bus_seen                ; it moved: someone else housekept
bus_dohk:                               ; nobody did -- take over this block

; y:>$900 holds the WRITE OFFSET (0/16/32/48), not the bare buffer index --
; see the layout comment in modules/send/send_client.asm. FOUR buffers, so the rotation
; is +16 mod 4 and the mask that does the modulo sanitises boot garbage too.
; No `asl #$4` follows: the value is already scaled.
        move    y:>$900,a
        add     #>$10,a
        and     #>$30,a
        move    a,y:>$900               ; the new CURRENT rotation
; ⚠️ CLEAR THE BUFFER WRITTEN **NEXT** BLOCK, NOT THIS ONE (17 Aug 2026).
; Clearing the buffer we are about to write races the OTHER core's writers:
; core 0 clears at the start of its block and everyone fills it during that
; block, so a core-1 writer that gets there BEFORE core 0's housekeeper has
; its contribution written and then wiped. Straddle that boundary and the
; sender drops out on some blocks and not others -- intermittent dropout,
; which is broadband hash exactly like the two defects before it.
; The four-buffer rotation fixed clear-vs-READ and the per-core tracking fixed
; which-buffer; NEITHER touches clear-vs-WRITE. This does, and it is free:
; with four buffers there is an idle slot. The buffer written next block was
; last READ a full block ago and will not be WRITTEN for another full block,
; so clearing it now has a block of margin on both sides.
        add     #>$10,a                 ; one further on: the NEXT block's
        and     #>$30,a                 ; write target, idle right now
        move    a,x0                    ; bases for the clear AND the count

        move    #>$901,a
        add     x0,a
        move    a,r1                    ; r1 = REVERB ACC[new] base
        move    #>$961,b                ; the DELAY accumulator's base MOVED when
        add     x0,b                    ; the REVERB one grew to four buffers
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
        move    a,y:>$9c1               ; DELAY SERVER role owner
        move    a,y:>$9c2               ; REVERB SERVER role owner
; ---- reset the new write buffer's SEND COUNTs, alongside its accumulators --
; Kept in step with modules/send/send_client.asm / modules/chonverb/reverb_server.asm (the standing
; rule: the housekeeping copies must stay identical). NOTE this copy was
; MISSING the REVERB count reset from v121 until the delay auto-gain landed -- dead
; code in every live build, because the XBUS payload gate keeps this payload
; from ever housekeeping, but a divergent copy is exactly the silent-desync
; class the rule exists for. x1 holds the NEW OFFSET from the rotation above.
; The counts are one word per buffer rather than sixteen, so the offset scales
; back down to an index.
        move    x0,a                    ; the SAME buffer the clear loop just
        asr     #$4,a,a                 ; zeroed: count and accumulator move
        move    #>$9c3,x0               ; together (0..3)
        add     x0,a
        move    a,r3
        move    #>$ffffff,m3
        clr     a
        move    a,y:(r3)                ; REVERB count = 0
        move    #4,n3                   ; SHORT immediate: 1 word (address reg).
        move    (r3)+n3                 ; 4, not 2: four buffers -> four counts
        move    a,y:(r3)                ; DELAY count = 0
bus_seen:
        move    y:>$900,a               ; remember this block's offset so next
        and     #>$30,a                 ; block we can tell whether anybody
                                        ; else housekept in between
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$88)
bus_notfirst:
; ---- resolve THIS BLOCK'S WRITE OFFSET, ONCE, into r7+$86 ---------------
; See the long note in modules/send/send_client.asm: every client used to read y:>$900
; at its own dispatch time, which is not a stable value on payload B because
; core 0 owns the flip. This server is on payload B, so it is exposed.
; build_bus.py substitutes a per-payload body here; both leave the offset in
; r7+$86, and every site downstream reads that instead of the shared word.
; ROTLATCH

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
        move    y:>$9c1,a
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
        move    a,y:>$9c1
bus_mine:

; ---- this call's DELAY ACC read address and DELAY WET write address ------
; READ is the OTHER buffer from the current write rotation -- the one every
; SEND client (and our own dry sum, below) finished filling last block.
; WRITE uses the SAME rotation clients currently write into, for a future
; cross-bus reader (task 10), not consumed by anything yet.
; ⚠️ THE OFFSET COMES FROM r7+$86, NOT y:>$900. This server lives on payload B
; and cannot read the shared rotation at its own dispatch time -- core 0 flips
; it asynchronously, so a core-1 client whose window straddles the flip sees a
; different value on different blocks. The resolve block at bus_notfirst
; tracks a stable rotation for this core; see the long note there and
; docs/XBUS.md step 3.
; The offset is already scaled by the 16-word buffer stride, so the write
; addresses need no shift at all. THE READ TARGET IS TWO BUFFERS
; BACK, `write + 32 & $30`. THIS IS THE LINE THE WHOLE RACE FIX IS FOR: with
; four buffers there is an idle block on each side of this read, so core 0's
; housekeeper can lead or lag core 1 by up to a full block and still never
; clear or write the words being read here. Two buffers had no such margin at
; any clear time, which is why the delay stuttered on track 1 and not track 4
; (hardware, 17 Aug 2026 -- dispatch position moved the read relative to the
; other core's flip).
        move    x:(r7+$86),a
        move    a,x1                    ; x1 = write offset (0/16/32/48)
        add     #>$20,a                 ; two buffers on == two buffers back
        and     #>$30,a                 ; mod 4
        move    a,x0                    ; x0 = the read offset
        move    #>$961,a
        add     x0,a
        move    x:(r7+$67),b            ; this call's split-aware frame offset
        add     b,a
        move    a,x:(r7+$63)            ; this call's DELAY ACC read address
; The WET buffers are TWO deep, not four -- nothing reads them, so they cannot
; carry a race. This is the second of the two sites that narrows the offset.
        move    x1,a
        and     #>$10,a                 ; write offset, narrowed to {0,16}
        move    a,x0
        move    #>$9a1,a
        add     x0,a
        add     b,a
        move    a,x:(r7+$64)            ; this call's DELAY WET write address

; ---- this call's REVERB ACC write address (BUS.md task 10: ->VERB sends) --
; ⚠️ x0 holds the NARROWED (wet) offset from the block just above, not the
; write offset -- the REVERB accumulator is four deep, so this reloads from x1.
; b (the split-aware frame offset) is still valid.
; ⚠️ THIS IS A CROSS-CORE WRITE. BongDelay runs on payload B and this line
; writes payload A's reverb accumulator, so the race documented in
; docs/XBUS.md step 3 ran in BOTH directions -- the bus damaged what arrived
; at the delay, and the delay's ->VERB damaged what arrived at the reverb.
; The fourth buffer covers this direction too, for the same reason.
        move    x1,x0                   ; the full write offset, 0/16/32/48
        move    #>$901,a
        add     x0,a
        add     b,a
        move    a,x:(r7+$84)            ; this call's REVERB ACC write address

; ---- bus auto-gain: resolve 1/sqrt(N) for this block's READ buffer --------
; The DELAY-bus mirror of the reverb's v121 fix (XBUS.md "Gain staging"):
; N clients summing into one accumulator word drive the delay N x as hard as
; one, and the shared word clamps at 1.0. Every DELAY-bus writer (SEND's
; ->DELAY tap, the reverb's ->DEL send) now registers once per block in a
; per-buffer DELAY count and writes with 3 bits of headroom
; (asr #3); this block divides by the count and the per-sample read shifts
; back up by 3, so the send knob sets a track's SHARE of the delay rather
; than how hard the line is hit.
; ⚠️ THE LAW IS 1/sqrt(N), NOT 1/N (17 Aug 2026) -- see the long note at the
; reverb's copy of this table. N sources sum as N only when CORRELATED;
; uncorrelated ones (actual different tracks) sum as sqrt(N), so dividing by N
; over-corrects real material by 3 dB per doubling, 9 dB at eight senders.
; The original verification was blind to it: send_probe feeds the SAME tone to
; every sender, which is exactly the correlated case 1/N gets right.
; Same table order as the reverb's: count is masked to 0..7, so 8 writers wrap
; to index 0, which therefore holds 1/sqrt(8). A count of 0 (nobody wrote)
; lands there too -- harmless, the accumulator is zero then anyway.
;
; The table lives in the shared bus scratch at $9cb-$9d2 (relocated with the
; rest of the $9xx layout under XBUS) because this server has no free ground
; of its own: both line buffers fill its entire half-window. Rebuilt each
; block; the stores are free in cycle terms. x1 (write_rotation) is still
; valid from the address block above.
        move    #>$9cb,b                ; reciprocal table base
        move    b,r5
        move    #>$ffffff,m5
        move    #>$2d413c,a
        move    a,y:(r5)+       ; [0] = 1/sqrt(8)  (count 8 wraps to here)
        move    #>$7fffff,a
        move    a,y:(r5)+       ; [1] = 1/sqrt(1)
        move    #>$5a8279,a
        move    a,y:(r5)+       ; [2] = 1/sqrt(2)
        move    #>$49e69d,a
        move    a,y:(r5)+       ; [3] = 1/sqrt(3)
        move    #>$400000,a
        move    a,y:(r5)+       ; [4] = 1/sqrt(4)
        move    #>$393e4b,a
        move    a,y:(r5)+       ; [5] = 1/sqrt(5)
        move    #>$34417a,a
        move    a,y:(r5)+       ; [6] = 1/sqrt(6)
        move    #>$306123,a
        move    a,y:(r5)        ; [7] = 1/sqrt(7)

        move    x1,a                    ; the count belongs to the buffer this
        add     #>$20,a                 ; block READS, which is two buffers back
        and     #>$30,a                 ; mod 4
        asr     #$4,a,a                 ; scaled back down -- the counts are one
        move    #>$9c7,x0               ; word per buffer, not sixteen
        add     x0,a
        move    a,r5
; ⚠️ THIS TRACK COUNTS AS A CLIENT TOO (v3 stage 1). IN feeds our own dry
; into the same sum the bus arrives on, so N must include us or every other
; sender is divided by one too few and we are effectively louder than all of
; them -- which is exactly the asymmetry the return architecture exists to
; remove (measured 17 Aug 2026: the host track drove the delay at -24.78 dB
; against a full-knob send's -24.85, i.e. identically, while being immune to
; the 1/N that scales everyone else).
; Only when actually sending: at IN=0 we contribute nothing, and counting a
; silent client would dilute the real ones by (N+1)/N -- 6 dB with one sender.
; ⚠️ `clr` SETS THE CONDITION CODES, so it goes BEFORE the tst it must not
; disturb (the flag-clobber trap in CLAUDE.md, and the reason 5d shipped a
; noise wash on one channel). Tcc takes a register source, never an
; accumulator, so the increment travels through x0.
; ⚠️ AND b HELD THE RECIPROCAL TABLE BASE from the table build above -- the
; Tcc needs an accumulator, so it takes b and the base is RE-LOADED below
; rather than "still live". Costs one word; the version that trusted the old
; comment indexed the table at address 0 or 1, a wild Y read.
        move    #>$1,x0                 ; the "one more client" increment
        clr     b                       ; b = 0 -- BEFORE the tst below
        move    x:(r6+$5),a             ; IN (p5 since the 18 Aug swap), read
                                        ;  from the knob directly: the per-block
                                        ;  decode runs AFTER this block
        tst     a                       ; Z set == IN is 0 == not sending
        tne     x0,b                    ; sending -> b = 1
        move    y:(r5),a                ; clients that wrote the buffer we read
        add     b,a                     ; ... plus ourselves, if sending
        and     #>$7,a                  ; masked: boot garbage cannot index wild
        move    a1,x0
        move    x0,a                    ; A2-clean before it becomes an address
        move    #>$9cb,b                ; table base, RE-LOADED (see above)
        add     b,a
        move    a,r5
        move    y:(r5),a
        move    a,x:(r7+$7f)            ; this block's bus gain, used per sample

; ---- register as a REVERB bus client, once per block (v3 stage 1) --------
; The ->VERB send below writes the REVERB accumulator every sample, so this
; server must appear in the REVERB count exactly as SEND does and as
; reverb_server does for the DELAY count -- otherwise ChonVerb's auto-gain divides
; by one client too few and our contribution comes out x8/N louder than it
; should. That was the shipping defect ("->VERB usable only to about VRBW
; 50"); the 5g /8 fix removed the constant factor and this removes the
; N-dependence, which together are what make a HARDWIRED amount meaningful.
;
; Same once-per-block gate as every other registration: keyed on the split
; offset, so a split block's two calls count ONCE. Same WRITE-rotation choice
; as send_client -- count the buffer we are about to add into, not the one
; being read.
        move    x:(r7+$67),a
        tst     a
        bne     vrcnt_done              ; not this block's first call
; ---- and ONLY while -VRB is up (18 Aug 2026) -- the phantom-client gate,
; the same block as ChonVerb's ->DEL and SEND's per-bus registrations: knob
; read from r6 DIRECTLY (the per-block decode runs later), clr BEFORE the tst,
; increment through x0 (Tcc takes a register), b carrying the flag across the
; address arithmetic below (which touches a and x0 but not b).
        move    #>$1,x0                 ; the "one more client" increment
        clr     b                       ; b = 0 -- BEFORE the tst below
        move    x:(r6+$4),a             ; the -VRB knob itself (p4 since the
                                        ;  18 Aug swap -- IN took p5 so both
                                        ;  effects' IN sits bottom-right)
        tst     a
        tne     x0,b                    ; sending -> b = 1
        move    x:(r7+$86),a            ; write offset -- the RESOLVED one, not
        asr     #$4,a,a                 ; y:>$900: re-reading the shared word
        move    a1,x0                   ; here would reintroduce the very
                                        ; disagreement the resolve block removes
        move    x0,a                    ; A2-clean before it becomes an address
        add     #>$9c3,a
        move    a,r5
        move    #>$ffffff,m5
        move    y:(r5),a
        add     b,a                     ; REVERB count += (sending ? 1 : 0)
        move    a,y:(r5)
vrcnt_done:

; ---- hardcoded base (BUS.md task 9: DELAY SERVER) ------------------------
; No x:0x213 read, no per-instance stash. The 0x30000 literal below is the
; SOURCE default; build_bus.py substitutes the correct half-window base per
; payload at build time (SOLVED -- see this file's header; BongDelay ships
; on payload B, base 0x38000, serving tracks 1-4).
        move    #>$ffffff,m0            ; audio is read and written via r0
        move    #>$ffffff,m4            ; GRAIN walks its table with r4 -- the
                                        ; one free AGU pointer, held at the
                                        ; global linear invariant like the rest
        move    #>$30000,x0
        move    x0,x:(r7+$31)

; ---- warm-up: zero both lines and persistent state before running --------
; Same tagged-counter idiom as dsp/reverb89.asm/modules/chonverb/reverb_server.asm, but a
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
        and     #>$fffe00,a             ; tag field -- AND cleans A1 only
        move    a1,x0
        move    x0,a                    ; A2-clean before the compare
        move    #>$2e0000,x0
        cmp     x0,a
        beq     dwarmtag
        clr     a                       ; garbage tag: warm-up starts at 0
        bra     dwarmrun
dwarmtag:
        move    x:(r7+$82),a
        and     #>$1ff,a
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
        move    b,x:(r7+$27)            ; TAPE LFO phases: persistent, and
        move    b,x:(r7+$28)            ; masked on load, but determinism is
                                        ; what verify-delay bit-compares
        move    b,x:(r7+$32)            ; GRAIN base age
        move    b,x:(r7+$5e)            ; REVERSE segment phase
; GRAIN's eight LATCHED SCATTERS (record +1 of each of the eight grains).
; Only these persist -- every other field of the table is rewritten by the
; builder before the readers touch it, every sample, so boot garbage there
; cannot survive one sample. A garbage SCATTER would, and it subtracts
; straight into a read address, so it is cleared like the PITCH offsets are.
        move    b,x:(r7+$35)            ; L0
        move    b,x:(r7+$39)            ; R0
        move    b,x:(r7+$3d)            ; L1
        move    b,x:(r7+$41)            ; R1
        move    b,x:(r7+$45)            ; L2
        move    b,x:(r7+$49)            ; R2
        move    b,x:(r7+$4d)            ; L3
        move    b,x:(r7+$51)            ; R3
        move    #>$123456,a             ; PRNG seed: any nonzero word (xorshift
        move    a,x:(r7+$18)            ; is dead at 0), fixed for determinism
        move    x:(r7+$15),a            ; reload count
        add     #>$1,a
        add     #>$2e0000,a             ; tag | count+1
        move    a,x:(r7+$82)
        bra     dry                     ; output stays dry until warm
dwarmdone:
        move    x:(r7+$31),x0           ; LineL base

; ---- per-block: TIME, FDBK, TONE, PING, -VRB, IN, ... ---------------------
        move    x:(r6),a
        and     #>$7f0000,a             ; knob field only
        asr     #$9,a,a                 ; value*128 (0..16256)
        move    #>64,x0
        add     x0,a                    ; floor 64 samples (~1.45 ms)
        move    a,x:(r7+$75)            ; TIME, 64..16320 samples

; ---- TIME: STICKY SNAP to a tempo division (24 Aug 2026, v3 of the day) --
; TIME is a FREE dial that snaps to a tempo division when it lands near one,
; and then HOLDS that division through tempo changes until the knob moves --
; Sam's "sticky snap" (a free-with-labels dial in the style of newer boxes,
; plus tempo-following once snapped). The ColdFire never told the DSP the
; tempo (docs/DSP.md 6c), so the tempo cave (modules/tempo-sync/tempo_cave.s) publishes two
; dead halfwords of this track's record:  r6+$6 = tempo24 (BPM*24) and
; r6+$7 = samples per MIDI clock (1/24 beat) in Q12.4 -- both <<8 like every
; published word. One signed mpy per candidate: x0 = ticks*16 << 8,
; y0 = M << 11  ->  a1 = (x0*y0*2) >> 24 = ticks*M.
; RULE (modules/tempo-sync/time_fmt.s, the panel formatter, uses the SAME integers):
;   free = knob*128 + 64;  tol = free/16 (+-6%)
;   candidate = the LAST M in {2,3,4,6,8,9,12,16,18,24} with |ticks*M-free| < tol
;   knob moved since last block -> held = candidate;  else held stays
;   TIME = held ? min(ticks*held, 16320) : free      (0 ticks -> free)
; 1/2T and 1/4. are not candidates: they never fit the 370 ms line below
; ~170 BPM. Neighbours 8 and 9 clocks are 11% apart, so +-6% windows
; barely touch; last-match-wins on both sides keeps them consistent.
; State: Y 0908h (last knob) and 0909h (held M<<11), core-private, ABSOLUTE
; addressing beside the proven 0901h-0907h words -- NEVER (r)+ (R48-R50,
; docs/DSP.md 6c-i). Per CORE, not per instance: two delays on one core
; would re-evaluate every block (correct, just not sticky); one server per
; core is the design. Branch-free; unpublished ticks read 0, every product
; is 0, nothing is within tolerance, the teq falls back to free -- the
; emulator without -tempo, or a NOTEMPO build, behaves as before.
        move    x:(r7+$75),a            ; free-running TIME, from the knob
        move    a,y1
        asr     #$4,a,a
        move    a,x1                    ; tolerance = free/16
        move    x:(r6+$7),x0            ; ticks Q12.4 << 8 (0 = not published)
        clr     b                       ; candidate: 0 = nothing near
        move    #>$1000,y0              ; M=2  (1/32T)
        mpy     y0,x0,a                 ; ticks*M
        sub     y1,a
        abs     a                       ; |d - free|
        cmp     x1,a
        tlt     y0,b                    ; within tolerance -> candidate
        move    #>$1800,y0              ; M=3  (1/32)
        mpy     y0,x0,a                 ; ticks*M
        sub     y1,a
        abs     a                       ; |d - free|
        cmp     x1,a
        tlt     y0,b                    ; within tolerance -> candidate
        move    #>$2000,y0              ; M=4  (1/16T)
        mpy     y0,x0,a                 ; ticks*M
        sub     y1,a
        abs     a                       ; |d - free|
        cmp     x1,a
        tlt     y0,b                    ; within tolerance -> candidate
        move    #>$3000,y0              ; M=6  (1/16)
        mpy     y0,x0,a                 ; ticks*M
        sub     y1,a
        abs     a                       ; |d - free|
        cmp     x1,a
        tlt     y0,b                    ; within tolerance -> candidate
        move    #>$4000,y0              ; M=8  (1/8T)
        mpy     y0,x0,a                 ; ticks*M
        sub     y1,a
        abs     a                       ; |d - free|
        cmp     x1,a
        tlt     y0,b                    ; within tolerance -> candidate
        move    #>$4800,y0              ; M=9  (1/16.)
        mpy     y0,x0,a                 ; ticks*M
        sub     y1,a
        abs     a                       ; |d - free|
        cmp     x1,a
        tlt     y0,b                    ; within tolerance -> candidate
        move    #>$6000,y0              ; M=12 (1/8)
        mpy     y0,x0,a                 ; ticks*M
        sub     y1,a
        abs     a                       ; |d - free|
        cmp     x1,a
        tlt     y0,b                    ; within tolerance -> candidate
        move    #>$8000,y0              ; M=16 (1/4T)
        mpy     y0,x0,a                 ; ticks*M
        sub     y1,a
        abs     a                       ; |d - free|
        cmp     x1,a
        tlt     y0,b                    ; within tolerance -> candidate
        move    #>$9000,y0              ; M=18 (1/8.)
        mpy     y0,x0,a                 ; ticks*M
        sub     y1,a
        abs     a                       ; |d - free|
        cmp     x1,a
        tlt     y0,b                    ; within tolerance -> candidate
        move    #>$c000,y0              ; M=24 (1/4)
        mpy     y0,x0,a                 ; ticks*M
        sub     y1,a
        abs     a                       ; |d - free|
        cmp     x1,a
        tlt     y0,b                    ; within tolerance -> candidate
; ---- knob moved? then held = candidate, else keep ---------------------------
        move    b,x1                    ; candidate (B2 clean: clr/Tcc only)
        move    x:(r6),a
        and     #>$7f0000,a
        asr     #$10,a,a                ; knob, 0..127
        move    a,y0
        move    y:>$0908,x0             ; last knob
        move    y0,y:>$0908
        move    y:>$0909,b              ; held M<<11 (0 = free)
        cmp     x0,a                    ; knob - last
        tne     x1,b                    ; moved -> re-evaluated
        move    b,y:>$0909
; ---- TIME = held ? ticks*held : free ---------------------------------------
        move    b,y0
        move    x:(r6+$7),x0
        mpy     y0,x0,a                 ; 0 when free or unpublished
        move    #>16320,x1
        cmp     x1,a
        tgt     x1,a                    ; clamp to the line
        move    x:(r7+$75),x1
        tst     a
        teq     x1,a                    ; free
        move    a,x:(r7+$75)

; ---- TIME SLEW (24 Aug 2026): glide, don't jump ---------------------------
; TIME is applied once per block, so turning the knob (or the tempo moving a
; synced TIME between zones) stepped the read head and crackled -- Sam heard
; it on the unit. A one-pole per block, coefficient 1/1024 in Q8, makes the
; head GLIDE instead: the worst case (a full-range jump, 16,256 samples) moves
; ~16 samples per 15-sample block -- about an octave, gone in a few blocks;
; a one-zone synced step (~1,800 samples) bends ~2 semitones and settles in
; ~1 s. Tape-delay behaviour, which is the character this delay already has.
; Truncation (asr) parks the glide up to 4 samples short from below and lands
; exactly from above -- inaudible. State at Y 0907h, core-private, ABSOLUTE
; addressing beside the proven 0901h-0904h words (R48-R50 died to an
; init-built table written through (r1)+ -- docs/DSP.md 6c-i). Zero at boot
; seeds from the target, so an instantiate does not swoop up from 0.
        move    x:(r7+$75),a            ; target, integer samples
        asl     #$8,a,a                 ; Q8
        move    a,x0
        move    y:>$0907,b              ; slewed TIME, Q8 (0 at boot)
        tst     b
        teq     x0,b                    ; boot: start AT the target
        move    b,y0
        sub     y0,a                    ; target - state
        asr     #$a,a,a                 ; /1024 per block
        add     y0,a                    ; state += step
        move    a,y:>$0907
        asr     #$8,a,a                 ; back to integer samples
        move    a,x:(r7+$75)            ; TIME, as every consumer below sees it

        move    x:(r6+$1),x0
        move    #>$700000,y1
        mpy     x0,y1,a
        move    a,x:(r7+$73)            ; FDBK, 0 .. ~0.87

        move    x:(r6+$2),x0
        move    #>$700000,y1
        mpy     x0,y1,a
        add     #>$100000,a
        move    a,x:(r7+$72)            ; TONE, 0.125 (dark) .. 0.99 (bright)

        move    x:(r6+$3),x0
        move    x0,a
        move    a,x:(r7+$74)            ; PING, 0 .. ~0.99
        move    #>$7fffff,a
        sub     x0,a
        move    a,x:(r7+$80)            ; 1 - PING

; ---- -VRB: the delay's send into the reverb -- A KNOB AGAIN (18 Aug 2026) --
; Hardwired at $7fffff from v3 stage 1 until here. The hardwire predated the
; symmetric RETURN design: now that BOTH effects are returns on a series bus,
; the delay is just another track sending to the reverb, and every other track
; has a -VRB knob -- the hard connect was the last asymmetry in the box.
; -VRB returns at p4 (IN moved to p5 in the same change, so IN sits
; bottom-right on BOTH effects), SAME NAME as SEND's, default 0.
;
; ⚠️ It also fixes a live phantom client: the hardwired send REGISTERED
; UNCONDITIONALLY, so an idle delay took a reverb share and diluted every real
; -VRB sender -- the defect class killed twice on 17 Aug, still alive in this
; one path. Registration now follows the knob (the vrcnt block below).
;
; The knob's ceiling is the old ceiling: 127 = one full client's share, the
; most any single track can drive the reverb -- identical in range, headroom
; and auto-gain share to every SEND track's -VRB. The 17 Aug rms figures
; comparing the wash to the delay's own output live in git history with the
; hardwire; they were valid against each other under the then-current 1/N law.
; ⚠️ The audible delay-vs-reverb balance is still NOT this knob's job -- the
; two effects sit on different TRACKS with their own faders. This sets how
; hard the delay drives the reverb relative to other senders.
        move    x:(r6+$4),a             ; -VRB, val<<16 == val/128 Q1.23
        move    a,x:(r7+$85)            ; (the MIX/PING trick, multiplier as-is)

; ---- IN: this track's OWN send level into the delay (v3 stage 1) ---------
; The exact counterpart of every other track's ->DELAY knob (send_client p0):
; same range, same scaling, same 3-bit headroom, same auto-gain share. See
; the input block for the arithmetic.
; ⚠️ p5, NOT p4, since 18 Aug 2026: IN and -VRB swapped slots so that IN sits
; BOTTOM-RIGHT on BOTH effects (the reverb's IN is p5). Old projects: stored
; p4/p5 values swap meaning -- covered by FLASHING.md's first-load step.
; ⚠️ THIS DECODE WAS SILENTLY DELETED for one day (6d2690b's -VRB splice ate
; it; caught 18 Aug during this swap): $76 went entirely unwritten, so IN
; multiplied warm-up garbage. It reached two wrapped images (R30/R31),
; NEITHER FLASHED. The matrix now has an IN-nonzero render so a dead IN can
; never again pass silently -- verify_bus alone cannot see it because every
; default render has IN at 0.
        move    x:(r6+$5),x0
        move    x0,x:(r7+$76)           ; IN, 0 .. ~0.99

; ---- MODE: engine select, page-2 slot 7 ($c bits 8-15) -- v2 spine --------
; Same field, same extract, same MSB-aligned convention as ChonVerb's MODE
; (modules/chonverb/reverb_server.asm). STAGE 1: CLEAN is the only engine, so every value
; -- including whatever an undefined descriptor slot leaves in this word on
; hardware -- runs CLEAN. When PITCH lands, the dispatch compares MSB-aligned
; short immediates on $69, and unknown values must keep falling through to
; CLEAN: a wrong select degrades to the trad delay, never to silence. The
; descriptor's MODE select (RENAMES/DEFAULTS/PAGE2_COUNTS in build_bus.py)
; lands with the second mode. DMODE=n (build_bus.py) substitutes a literal
; at the marker below (dsp_host can also drive companions via -params 7/9/11;
; the override forces the decoded VALUE, so DFRZ=2 means frozen, not SYNC).
        move    x:(r6+$c),a
        and     #>$ff00,a               ; slot 7's companion field, not the knob
        move    a1,x0
        move    x0,a                    ; A2-clean (AND cleans A1 only)
        asl     #$8,a,a                 ; -> MSB-aligned ($010000 per step)
; DMODE_OVERRIDE
        move    a,x:(r7+$69)            ; MODE, this block (0 = CLEAN)

; ---- SHIFTED-OUTPUT flag: which modes replace the wet with $24/$25 --------
; PITCH, GRAIN and REVERSE all leave their result in the shifted-output taps
; are substituted into the wet AFTER the lines are written (stage 2c, so
; nothing shifted can re-enter the feedback). Resolving "is this such a mode"
; ONCE PER BLOCK instead of at the substitution point makes that per-sample
; test a `tst`, the same shape as FREEZE's -- it costs two words fewer than
; the single compare it replaces and does not grow when a fourth mode wants
; the same treatment. Branchless: cmp sets Z, the intervening moves do not
; disturb it, and teq moves a CLEAN register in (never a hand-rolled mask).
        clr     a
        move    x:(r7+$69),b            ; MODE
        move    #>$10000,x0             ; 1 << 16 = PITCH
        cmp     x0,b
        move    #>$1,x0
        teq     x0,a
        move    #>196608,x0             ; 3 << 16 = GRAIN. DECIMAL, DELIBERATELY:
                                        ; in hex this immediate IS the payload-A
                                        ; Y base literal, and build_bus.py's
                                        ; blanket substitution would rewrite it
                                        ; to the payload-B base -- i.e. to mode
                                        ; 0x38. Same trap the census caught on
                                        ; DMODE=3; writing this comment WITH the
                                        ; hex spelled out trips the census too,
                                        ; which is the cheapest possible reminder
        cmp     x0,b
        move    #>$1,x0
        teq     x0,a
        move    #>$40000,x0             ; 4 << 16 = REVERSE
        cmp     x0,b
        move    #>$1,x0
        teq     x0,a
        move    a,x:(r7+$33)            ; nonzero = the wet comes from $24/$25

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
        and     #>$7f00,a               ; slot 9's companion field: BITS 8-15, the
        asr     #$8,a,a                 ; same place MODE's is -- see the note there
; DINT_OVERRIDE
        move    a1,x0
        move    x0,a                    ; A2-clean before the compares
        move    a,x:(r7+$5f)            ; the RAW index, kept for REVERSE --
                                        ; which reads this same select as a
                                        ; segment SIZE. Stashing it here is
                                        ; what avoids a second read of r6+$d,
                                        ; and therefore a second copy of the
                                        ; interval-override marker, which
                                        ; build_bus.py refuses: it requires
                                        ; EXACTLY ONE, and a marker spelled
                                        ; out in a comment counts (the same
                                        ; family as the base-literal census)
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

; ---- MIDI note -> PITCH interval (branch midi, 24 Aug 2026) ---------------
; The ColdFire cave (modules/tempo-sync/tempo_cave.s v2) re-stores the host track's held
; MIDI note into record halfword +0x2a = r6+$9 every frame (bits 8-15 after
; the <<8, like every other published byte); 0 = released or no cave. The
; OT's chromatic range is 72..96 with 84 = unison (the stock code p-locks
; PTCH as 64+5*(note-84)), so interval = note-84, +-12. HOLD semantics: the
; last note LATCHES in a core-private Y slot and the select above is overridden for as
; long as any note has ever arrived -- a track that never sees MIDI behaves
; exactly as before. Both scouts' facts: docs/midi_re_note.md.
;   step = $1000 * (2^(n/12) - 1), computed by starting at r = 2^(13/12)/4
;   and multiplying by 2^(-1/12) (97 - note) times: r = 2^(n/12)/4, and
;   step = (r_word >> 9) - $1000. Error < 1 cent across the range (checked
;   in python, 24 Aug). No table: R48-R50 died on an init-built Y table, and
;   a P table needs an AGU register the block has no spare of. <= 25 mpys
;   per block, per-block cost only. `do y0` is the shipped bus_zclr idiom.
        move    x:(r6+$9),a
        and     #>$7f00,a               ; the note, bits 8-15
        asr     #$8,a,a
; DNOTE_OVERRIDE
        move    a1,x0
        move    x0,a                    ; A2-clean
        tst     a
        move    y:>$090a,b              ; latched note (0 = never)
        tne     x0,b                    ; a new note replaces it; a release
                                        ; (0) leaves it -- the moves between
                                        ; tst and tne do not touch the flags
        move    b,y:>$090a
        tst     b
        beq     qend                   ; no note ever -> the select stands
        move    #>97,a
        sub     b,a                     ; count = 97 - note = 13 - n
        move    #>1,x0
        cmp     x0,a
        tlt     x0,a                    ; clamp 1..25 (belt and braces: the
        move    #>25,x0                 ; chromatic map cannot exceed it)
        cmp     x0,a
        tgt     x0,a
        move    a1,y0                   ; loop count
        move    #>$43ce3e,a             ; 2^(13/12)/4
        move    #>$78d0e0,y1            ; 2^(-1/12)
        do      y0,>qmul
        move    a,x0                    ; |a| < 1, immediate-loaded: clean
        mpy     x0,y1,a                 ; SIGNED order (x0,y1) -- not mpysu
qmul:
        asr     #$9,a,a                 ; r_word >> 9 = 2^(n/12) * $1000
        move    #>$1000,x0
        sub     x0,a                    ; - 1.0 -> the age step
        move    a,x:(r7+$6a)            ; both lines: the note is one
        move    a,x:(r7+$6b)            ; interval, never a detune
qend:

; ---- TAPE depths from the WOW knob (v2 stage 4) --------------------------
; Page-1 slot 6 is a KNOB field (r6+$b, value<<16, 0..127), not a select:
; wow depth is a continuous voicing control unlike MODE/PTCH/FRZE.
;   wow depth = knob << 10  -> up to 31.75 samples, Q11.12
;   flutter   = wow >> 3    -> up to  3.97 samples
; The CEILING IS LOAD-BEARING, not taste: the modulated read sits at lag
; TIME + mod, TIME's floor is 64 samples (knob 0 -> 0*128+64), and the two
; depths sum to at most 35.7 -- so the lag can never reach 0 and wrap onto
; the sample about to be written, which is a whole lap old (a full-scale
; discontinuity every LFO cycle). Any future depth increase must re-check
; that sum against TIME's floor.
        move    x:(r6+$c),a             ; $c, NOT $b: the panel publishes slot 6
        and     #>$7f0000,a             ; to $c's KNOB field (R16's SHMR probe
        asr     #$3,a,a         ; x8 RELAW (18 Aug 2026): the old law's
                                        ; full-knob wobble measured +-2 CENTS --
                                        ; inaudible by construction, which is
                                        ; why 'mod does nothing' was true on
                                        ; every build ever. Wow now reaches
                                        ; ~+-254 samples (~+-17 cents at 0.8 Hz);
                                        ; safety moved from the static depth
                                        ; bound to the per-sample lag clamp below                 ; found the same). The mask is now needed
                                        ; because $c also carries MODE at bits
                                        ; 8-15; on $b nothing shared the word
        move    a1,x0
        move    x0,a                    ; A2-clean
        move    a,x:(r7+$2d)            ; WOWD
        asr     #$3,a,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$2e)            ; FLTD = WOWD/8

; ---- RATE: modulation speed -- page-2 slot 8 KNOB (18 Aug 2026) -----------
; One factor, val/64 (64 = exactly 1x, 0 = frozen, 127 = ~2x), scaling BOTH
; LFO increments so the anti-lock wow:flutter ratio survives. The constants
; are PRE-DOUBLED ($130 = 2x$98, $ada = 2x$56d) so the mpy's val/128 becomes
; val/64 with NO post-shift -- an asl after truncation broke bit-identity at
; the default by one LSB of the odd flutter increment, which is exactly the
; kind of failure the DPTH=0 gate exists to catch.
; Results live in CORE-PRIVATE Y 0901h/0902h (see the warning below;
; XBUS): r7 is full, and the server-role lock guarantees ONE delay per bank,
; so the shared words have one writer.
        move    x:(r6+$d),a
        and     #>$7f0000,a             ; RATE knob field
        move    a1,x0
        move    #>$130,y1
        mpy     x0,y1,a                 ; wow inc = $98 * val/64
; ⚠️ 0901h-0904h: CORE-PRIVATE Y, and the ZERO-PADDED SPELLING IS LOAD-BEARING.
; (0904h is the v6 freeze-crossfade ramp r -- same family, same reasoning.)
; These three words (wow inc / flutter inc / drive d) lived at shared-window
; Y 0x360d3-5 for one image (R36) and were DEAD ON HARDWARE: -VRB and FRZE
; proved the decodes execute and the $e word publishes, yet DPTH/RATE/DRV all
; behaved as zero -- the per-block writes and in-loop reads do not meet on
; silicon there, mechanism unknown (they were the first in-loop absolute Y
; reads in the shared window; the emulator's flat memory passes either way,
; so no local test can see whatever silicon does). Moved to the OLD BUS
; RANGE, core-private low Y -- empty since XBUS relocated the bus out, and
; hardware-proven for exactly this write-per-block/read-per-sample pattern
; by stock and the v121 bus. The `$09xx` spelling dodges build_bus.py's
; blanket `$9xx` relocation regex ON PURPOSE: `0901h` would be rewritten to
; 0x36001, straight into the shared REVERB accumulator. build_bus
; census-guards the count (exactly 8 refs since v6: RATE's four plus the
; freeze ramp's four; the old "6" here predated d's move to r7+$83).
        move    a,y:>$0901
        move    #>$ada,y1
        mpy     x0,y1,a                 ; flutter inc = $56d * val/64
        move    a,y:>$0902

; ---- DRIVE amount: p10 in every mode but GRAIN --------------------------
; GRAIN's p10 is SPRA (scatter), the established multi-meaning pattern -- so
; in GRAIN, d is pinned 0 and the grains run undriven; everywhere else the
; knob is DRV. knob<<16 IS d in Q1.23 (the MIX/PING trick). Y 0903h:
; same reasoning as the RATE increments above.
        move    x:(r7+$69),b            ; MODE
        move    #>196608,x0             ; 3 << 16 = GRAIN. DECIMAL (base literal)
        cmp     x0,b
        beq     drvz
        move    x:(r6+$e),a             ; p10 knob field
        and     #>$7f0000,a
        bra     drvw
drvz:
        clr     a
drvw:
        move    a,x:(r7+$83)            ; d -> r7 (18 Aug 2026, probe V0/V127:
                                        ; d via Y read INSIDE the bsr callee
                                        ; measured dead on hardware -- crest
                                        ; unchanged at levels where a 4x knee
                                        ; must crush ~6 dB -- while the SAME
                                        ; in-loop Y mechanism works for the
                                        ; increments read INLINE. $83 was the
                                        ; delay's one free r7 slot; both ends
                                        ; are now the battle-proven r7 path)

; ---- FREEZE select (v2 stage 3) ------------------------------------------
; Page-2 slot 11's companion field, r6+$e LOW bits -- the same low-byte
; select idiom as PTCH ($d low) and ChonVerb's WIDTH/->DEL, count 2. Any
; nonzero value freezes, so boot garbage in the field cannot do anything
; worse than hold; the masked read also keeps a wild value out of the flag.
; Decoded every block regardless of MODE: freeze is orthogonal to the engine
; (frozen + PITCH = shifted reads over held material, PLAN 3.1 stage 3).
        move    x:(r6+$e),a
        and     #>$7f00,a               ; slot 11's companion field: BITS 8-15. No
                                        ; shift: $26 is only ever tested zero /
                                        ; nonzero, so the index's scale is moot.
                                        ; (24 Aug 2026: briefly a 4-way with a
                                        ; SYNC bit; on the unit position 2 froze
                                        ; too, and freeze is performative --
                                        ; Sam: SYNC does not live here.)
; DFRZ_OVERRIDE
; (24 Aug 2026: a crossfader -> FREEZE hard-lock lived here for an evening
; and was removed at Sam's request -- nothing is to be welded to the fader.
; Page 1 scene-locks morph like any stock effect; page 2 cannot be locked,
; and that is where it stays. The cave still publishes fader+1 at r6+$8,
; unread.)
        move    a1,x0
        move    x0,a                    ; A2-clean before the store
        move    a,x:(r7+$26)            ; 0 = running, nonzero = frozen
; v6: while RUNNING, keep the engage-crossfade ramp armed at ~1 (satdrv's
; tail decays it only while frozen, so the fade always starts exactly here,
; at the engage edge). teq off the flag's own tst; the moves between do not
; disturb the condition codes.
        tst     a
        move    y:>$0904,b              ; r (core-private, like RATE/DRV's
                                        ; 0901h-0903h -- 0x360d3-5 is dead
                                        ; on hardware, R36)
        move    #>$7fffff,x0
        teq     x0,b                    ; running -> re-arm
        move    b,y:>$0904

; ---- SPRAY: GRAIN scatter depth (v2 stage 5) ------------------------------
; Page-2 slot 10's KNOB field -- the SAME WORD as FRZE, whose select is its
; low byte, which is why the two masks here are disjoint and neither reads
; the other's field. knob<<16 already IS value/128 in Q1.23, so it is used
; directly as a multiplier with no mpy to build it (the MIX/PING trick).
; SPRAY=0 puts every grain on the same read position -- four heads in a
; cluster, the most coherent and least granular end -- and 127 gives the
; full 0..1015-sample scatter. Decoded every block regardless of MODE, like
; PTCH and FRZE; harmless in the modes that never read it.
        move    x:(r6+$e),a
        and     #>$7f0000,a             ; knob field only
        move    a1,x0
        move    x0,a                    ; A2-clean (AND cleans A1 only)
        move    a,x:(r7+$5c)            ; SPRAY, 0 .. ~0.992 as Q23
        move    #>4,n4                  ; GRAIN's readers stride one record
                                        ; past the other line's, per block so
                                        ; the sample loop never pays for it

; ---- REVERSE: segment size, phase step, and the lag floor (v2 stage 6) ----
; The PTCH select read as a SIZE. S must be a POWER OF TWO, and that is not
; taste: the phase step is 2^23/S, so only a power of two makes it an exact
; integer -- and exactness is what makes the segment-local sample index
; p = phase*S/2^23 land on WHOLE SAMPLES, which is why REVERSE needs no lerp
; at all while PITCH and TAPE do.
;
; ⚠️ THE SIZE CEILING IS THE LINE, NOT TASTE. Playing S samples backwards
; takes S samples, during which the write pointer advances S -- so the head
; reaches a lag of LAG0 + 2S and the buffer must hold 2S of history. With a
; 16384-word line that caps S at 4096 (93 ms) once the floor is allowed
; anything at all. Any future size increase must re-check LAG0 + 2S < 16384.
        move    x:(r7+$5f),a            ; select index
        move    #>$1,x0
        cmp     x0,a
        beq     rsz1
        move    #>$2,x0
        cmp     x0,a
        beq     rsz2
        move    #>$3,x0
        cmp     x0,a
        beq     rsz3
        move    #>4096,a                ; index 0 (and any garbage): 93 ms
        move    a,x:(r7+$60)
        move    #>2048,a                ; step = 2^23 / S
        move    a,x:(r7+$61)
        move    #>8128,a                ; cap = 16320 - 2S
        bra     rszend
rsz1:
        move    #>2048,a                ; 46 ms
        move    a,x:(r7+$60)
        move    #>4096,a
        move    a,x:(r7+$61)
        move    #>12224,a
        bra     rszend
rsz2:
        move    #>1024,a                ; 23 ms
        move    a,x:(r7+$60)
        move    #>8192,a
        move    a,x:(r7+$61)
        move    #>14272,a
        bra     rszend
rsz3:
        move    #>512,a                 ; 12 ms -- stutter territory
        move    a,x:(r7+$60)
        move    #>16384,a
        move    a,x:(r7+$61)
        move    #>15296,a
rszend:
        move    a,x:(r7+$56)            ; the cap for this size
        move    x:(r7+$75),a            ; TIME
        move    x:(r7+$56),x0
        sub     x0,a                    ; sub/branch, not cmp (the
        tst     a                       ; cmp-encodes-as-max trap family)
        ble     rlagok
        clr     a                       ; over the cap: excess -> 0
rlagok:
        add     x0,a                    ; min(TIME, cap)
        move    a,x:(r7+$62)            ; RLAG0, the reversed chunk's lag floor

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
; ---- v3 stage 1: OUR OWN DRY IS JUST ANOTHER CLIENT ----------------------
; It used to be added at UNITY, after the bus had already been auto-gained --
; which made the host track immune to 1/N and therefore as loud into the
; delay as every sender combined, with no knob to trim it. Now it goes
; through the identical path a SEND client's contribution takes: scaled by
; its own level knob, given the same 3 bits of headroom, summed with the
; others, and divided by a count that includes it.
;
; mpy x0,y1 is the SIGNED order (2000c0) -- x0 is audio and goes negative,
; y1 is a knob and never does. Disassembled from the emitted image; the
; assembler silently downgrades unknown operand orders to mpysu, which would
; corrupt every negative sample here.
        move    a,x0                    ; own dry mono
        move    x:(r7+$76),y1           ; IN, this track's send level
        mpy     x0,y1,a                 ; our contribution to the bus
        asr     #$3,a,a                 ; the 3 bits of headroom EVERY writer
                                        ; applies, so N of them cannot rail
                                        ; the sum before it is divided
        move    a,x:(r7+$7d)            ; park our share
        move    x:(r7+$63),a            ; this sample's ACC read address
        move    a,r5
        move    y:(r5),x0               ; last block's fully-summed sends
        move    x:(r7+$7d),a
        add     x0,a                    ; the full sum, our own share included
        move    a,x0
        move    x:(r7+$7f),y1           ; this block's bus gain 1/sqrt(N); N
                                        ; COUNTS US (see the resolve block)
        mpy     x0,y1,a                 ; hold total drive constant vs N --
                                        ; signed (2000c0): x0 is a bus sample
                                        ; and can be negative, y1 (the gain) never
        asl     #$3,a,a                 ; undo the writers' 3-bit headroom
        move    a,x:(r7+$7d)            ; x_in = the averaged bus, us included
        move    x:(r7+$63),a
        add     #>$1,a
        move    a,x:(r7+$63)            ; advance ACC read pointer

; ---- the FEEDBACK LOOP's taps: ALWAYS the unshifted read (v2 stage 2c) ----
; NON-CASCADING PITCH. Until stage 2c the shifted taps WERE the loop's taps,
; so every repeat was shifted again: repeat n had been through the shifter n
; times and carried n generations of splice artifact. That compounding, not
; the splice itself, is most of what an ear calls "machine" -- and ChonVerb
; hit exactly this and fixed it the same way (its shimmer deliberately cut
; its own cascade; see modules/chonverb/reverb_server.asm's SHIMMER block).
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
; ---- LOOP taps: lerped read at lag TIME + wow/flutter, EVERY mode ---------
; (18 Aug 2026.) This is TAPE's machinery promoted to the common path -- the
; loop's recirculating tap is the same in every mode since stage 2c, so the
; drift belongs to the INSTRUMENT, not to a mode. DPTH (p6, was WOW) sets the
; summed depth; RATE (p8) scales BOTH LFO increments by one factor, val/64
; with 64 = exactly 1x -- preserving the deliberate non-integer wow:flutter
; ratio that keeps the pair from ever locking. DPTH=0 reads lag TIME with
; fraction 0, which the lerp passes through exactly -- bit-identical to the
; old CLEAN taps, and that is the gate this refactor shipped under.
; The load-bearing depth bound is unchanged and rate-independent: wow+flutter
; sum <= 35.7 samples against TIME's floor of 64.
        move    x:(r7+$27),a           ; wow phase
        move    y:>$0901,x0           ; wow increment (core-private -- see RATE decode)
                                        ; (p8), computed per block. Y bus
                                        ; scratch, because r7 is full and the
                                        ; role lock means ONE delay per bank
        add     x0,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a                    ; A2-clean; boot garbage dies here
        move    a,x:(r7+$27)
        bsr     smoothw                 ; s = g^2*(3-2g), 0..1 (v6 roll --
                                        ; the inline copy parked g^2 in $2a;
                                        ; smoothw parks in $5a, equally dead
                                        ; here)
        move    a1,x0
        move    x:(r7+$2d),y1         ; WOWD
        mpy     x0,y1,a                 ; s*depth
        asl     #$1,a,a
        move    x:(r7+$2d),x0
        sub     x0,a                    ; depth*(2s-1): centred, +-depth
        move    a,x:(r7+$29)            ; running mod total

        move    x:(r7+$28),a           ; flutter phase
        move    y:>$0902,x0           ; flutter increment (core-private,
                                        ; NOT a multiple of the wow: the
                                        ; anti-lock ratio survives RATE because
                                        ; ONE factor scales both) x RATE
        add     x0,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a                    ; A2-clean; boot garbage dies here
        move    a,x:(r7+$28)
        bsr     smoothw                 ; s = g^2*(3-2g), 0..1 (v6 roll)
        move    a1,x0
        move    x:(r7+$2e),y1         ; FLTD
        mpy     x0,y1,a                 ; s*depth
        asl     #$1,a,a
        move    x:(r7+$2e),x0
        sub     x0,a                    ; depth*(2s-1): centred, +-depth
        move    x:(r7+$29),x0
        add     x0,a                    ; mod = wow + flutter, Q11.12 signed

; ---- split the offset: integer samples + Q23 fraction ---------------------
; asr floors (arithmetic, so negative offsets too) and the masked low 12
; bits are the POSITIVE remainder -- the pairing the lerp below assumes.
        move    a,x:(r7+$2a)            ; park mod
        asr     #$c,a,a                 ; integer samples, signed
        move    a1,x0
        move    x0,a                    ; move-to-accumulator sign-extends
        move    a,x:(r7+$29)            ; mod_int
; ---- lag clamp (18 Aug 2026, with the x8 relaw): keep TIME+mod inside the
; line. Replaces the old static bound (sum < TIME's floor), which is what had
; capped the depth at inaudibility. Low side: lag >= 8 (never reads the write
; head); high side: lag <= 16376 (never wraps the $3fff mask at max TIME).
; Pinning briefly at an extreme is a soft flat-spot in the wobble -- graceful,
; where a wrap is a full-lap discontinuity. x1 is free in this span.
        move    #>8,a
        move    x:(r7+$75),x0           ; TIME
        sub     x0,a                    ; 8 - TIME = lowest legal mod
        move    a,x1
        move    x:(r7+$29),a
        cmp     x1,a
        tlt     x1,a                    ; below -> pin at low limit
        move    a,x:(r7+$29)
        move    #>16376,b
        move    x:(r7+$75),x0
        sub     x0,b                    ; highest legal mod
        move    b,x1
        cmp     x1,a
        tgt     x1,a                    ; above -> pin at high limit
        move    a,x:(r7+$29)
        move    x:(r7+$2a),a
        and     #>$fff,a                ; fraction (A2 stale until cleaned)
        asl     #$b,a,a                 ; -> Q23
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$2c)            ; frac

; ---- TAPE Line L: lerped read at lag TIME + mod ---------------------------
        move    r1,a
; lerp read rolled into modtap (18 Aug 2026): line base staged in $30, the
; pointer arrives in a, the tap returns in a. Same word-saving move as satdrv.
        move    x:(r7+$31),x0
        move    x0,x:(r7+$30)
        bsr     modtap
        move    a,x:(r7+$79)          ; dL, wobbled -- the LOOP's own tap

; ---- TAPE Line R: lerped read at lag TIME + mod ---------------------------
        move    r2,a
        move    x:(r7+$68),x0
        move    x0,x:(r7+$30)
        bsr     modtap
        move    a,x:(r7+$7a)          ; dR, wobbled
; ---- MODE dispatch: PITCH additionally computes the SHIFTED OUTPUT taps ---
; 0 and every unknown value run the loop's clean taps alone -- a wrong select
; degrades to the trad delay, never to silence (the stage-1 rule). The
; compare is the safe `cmp x0,a` form.
; MODEFORK_BEGIN -- cycle_count.py: BEGIN..first MID is the dispatch and
; always runs; each MID..next is one mutually exclusive alternative, and the
; tool charges dispatch + the WORST alternative, never every engine summed.
        move    x:(r7+$69),a
        move    #>$10000,x0             ; 1 << 16, MSB-aligned like the store
        cmp     x0,a
        beq     pmode
        move    #>196608,x0             ; 3 << 16 = GRAIN (v2 stage 5). DECIMAL
                                        ; for the base-literal reason above
        cmp     x0,a
        beq     gmode
        move    #>$40000,x0             ; 4 << 16 = REVERSE (v2 stage 6)
        cmp     x0,a
        beq     rmode
        bra     pdone                   ; CLEAN, and every unknown value
; MODEFORK_MID -- alternative 1: PITCH

; ---- PITCH: dual crossfaded lerp heads per line (v2 stage 2) --------------
; The shimmer-v3 machinery (modules/chonverb/reverb_server.asm SHIMMER block) reading the
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
; (v7: both heads' read+window bodies live in phead; LineL's base is staged
; once here for both calls -- staging touches only x0, and a still holds
; age_fx.)
        move    x:(r7+$31),x0           ; LineL base -> phead's staging slot
        move    x0,x:(r7+$30)
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
        bsr     phead                   ; lerped read + window (v7 roll):
                                        ; out $17 = tap, $15 = g^2, y1 = 1-g
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
        bsr     phead                   ; ($30 still holds LineL's base)
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
        move    x:(r7+$68),x0           ; LineR base -> phead's staging slot
        move    x0,x:(r7+$30)           ; (once, for both R heads' calls)
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
        bsr     phead                   ; ($30 holds LineR's base)
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
        bsr     phead                   ; ($30 still holds LineR's base)
        move    x:(r7+$15),x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     x0,a
        move    a1,y1
        move    x:(r7+$17),x0
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$25)            ; shifted OUTPUT tap R
        bra     pdone
; (alternative 2 was TAPE -- RETIRED 18 Aug 2026. Its wow/flutter machinery
; moved into the always-run loop-tap read above: since stage 2c every mode
; recirculates the same clean tap, so the modulation was never mode-shaped,
; and once DPTH/RATE became knobs TAPE was CLEAN with the knobs up. Sam:
; "tape wasn't offering much." Its MODE position falls through to CLEAN, the
; stage-1 rule, so old projects' stored TAPE parts still play.)
; MODEFORK_MID -- alternative 3: GRAIN

; ---- GRAIN: four overlapping grains per line, rolled (v2 stage 5) ---------
; THE FLAGSHIP, and the honest answer to "it doesn't sound like a Microcosm":
; density is the mechanism, not a better two-head shifter. PITCH's ear pass
; established the framing this is built on -- a granular device is artifacts
; made DENSE and APERIODIC until they read as texture, not a clean shifter.
; So GRAIN is PITCH's machinery with twice the heads and an independent
; random source position per grain, on a knob.
;
; N = 4, AND N MUST BE EVEN. With the full-overlap triangle window, grains
; staggered by 1/N sum to: N=2 -> 1.0000, N=4 -> 2.0000 (both exactly flat,
; because the grains pair up complementarily -- 0 with 2, 1 with 3), N=3 ->
; 0.21 dB ripple, N=5 -> 0.03 dB. An ODD count puts a ripple AT THE GRAIN
; RATE, which is a periodic amplitude modulation -- exactly the artifact
; class stages 2b/2c existed to remove. Four it is, and each gain is HALVED
; as it is built so the four sum to 1.0 and no partial sum can saturate on
; its way through the accumulator.
;
; THE ROLL IS MANDATORY, not an optimization. PITCH spends 524 words on four
; head evaluations; eight of them unrolled is ~1,048 words against payload
; B's ~940 free -- it does not fit. Rolled, the body is emitted three times
; (one builder, one reader per line) instead of eight. Precedent: the tank
; roll and the LFO roll in modules/chonverb/reverb_server.asm.
;
; WHAT IS SHARED AND WHAT IS NOT. One base age serves all four grains, each
; taking a fixed quarter-cycle offset, so a single advance moves the whole
; cloud; the window gain, integer age and sample fraction depend only on that
; age, so they are computed ONCE and used by both lines. What is per-line is
; the SCATTER -- an independent random source offset per grain per line --
; and that alone is what keeps L and R decorrelated. (A single scatter shared
; by both lines would make the two channels identical up to the ping-pong
; matrix, which is the mono trap this file's header already documents once.)
;
; OUTPUT ONLY, NEVER IN THE LOOP -- stage 2c, and it is not optional here: a
; cascade would put every repeat through eight more splices, and compounding
; is what an ear calls "machine". The result lands in $24/$25 exactly like
; PITCH's, and the substitution below is mode-blind via the $33 flag.
;
; A `do` body must be BRANCH-FREE, so every conditional here is a Tcc --
; already the house idiom, and the reason the scatter latch is `tmi`.
;
; mpy orientation throughout: the possibly-negative operand (t1-t0, the tap)
; is ALWAYS x0, the audited-signed `mpy x0,y1` form; y1 only ever carries a
; fraction or a window gain, both non-negative.
gmode:
; ---- GRAIN, v2 stage 5e: the SCHEDULE and the RATE are separate ----------
; Until now one accumulator drove both the window envelope and the read
; position. That single fact forced three things at once, and Sam heard all
; three: every grain shifted by the SAME interval and they all jumped
; TOGETHER (a step in the whole layer, "jumping around in a not very musical
; fashion"); UNISON WAS IMPOSSIBLE, because a rate of 1.0 means the age never
; advances, so the grain never wraps and never re-scatters -- which is why
; the interval set had no unison in it, and "mostly unison with occasional
; shifts" is most of what makes a grain cloud sound musical rather than
; arbitrary; and grain size was welded to the pitch ratio.
;
; So: a SCHEDULE phase ticks at a fixed rate and drives ONLY the envelope,
; while each grain carries its OWN read-offset accumulator advancing at its
; own rate. The cloud now morphs instead of stepping, and unison is a legal
; draw.
;
; Record, 8 of them (L0 R0 L1 R1 ...), FOUR words -- exactly the 32 the old
; table used, so this costs no r7 space (there is none):
;   +0 rate delta, signed Q9 per sample   (PERSISTENT, latched at the wrap)
;   +1 mute flag                          (PERSISTENT, latched at the wrap)
;   +2 read offset, Q14.9                 (PERSISTENT, accumulates)
;   +3 window gain / 2, Q23               (rebuilt every sample)
; The field order is the BUILDER's access order, so every access is a plain
; post-increment; the readers start at +2 and stride 8 with n4.
;
; RATE DELTAS are (1 - r) in Q9, because the read address is wr - lag and the
; write pointer runs away at 1 sample/sample:
;   unison r=1.0 -> 0      +12 r=2.0 -> -512
;   +7     r=1.5 -> -256   -12 r=0.5 -> +256
; A grain at +12 therefore traverses 2048 samples over its 2048-sample life,
; which is why the offset RESETS to 2048 + scatter and why the lag ceiling
; below subtracts 3072. ⚠️ That bound is load-bearing: LAG0 + 2048 + scatter
; + 1024 must stay inside the 16384-word line, or a head reads across the
; write pointer -- a full-scale discontinuity once per grain.
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
; ---- this sample's scatter candidates, SPRAY-scaled ---------------------
        move    a,x0                    ; state, 0 .. ~1.0 (always positive)
        move    x:(r7+$5c),y1           ; SPRAY
        mpy     x0,y1,a                 ; both operands non-negative
        asr     #$a,a,a
        and     #>$1fff,a               ; 0..8191 samples (186 ms)
        move    a1,x0
        move    x0,a
        move    #>0,x0                  ; the SCATTER ALONE now -- the
        add     x0,a                    ; reserve is added PER GRAIN below,
        asl     #$9,a,a                 ; (4096 + scatter) in Q14.9. Also
        move    a1,x0                   ; per-sample-constant, so the builder
        move    x0,a                    ; no longer rebuilds it four times.
        move    a,x:(r7+$54)            ; reset form, line L
        move    x:(r7+$18),a
        asl     #$b,a,a                 ; a DISJOINT field of the same word,
        and     #>$7fffff,a             ; so no bit feeds both lines
        move    a1,x0
        move    x:(r7+$5c),y1
        mpy     x0,y1,a
        asr     #$a,a,a
        and     #>$1fff,a
        move    a1,x0
        move    x0,a
        move    #>0,x0                  ; the SCATTER ALONE now -- the
        add     x0,a                    ; reserve is added PER GRAIN below,
        asl     #$9,a,a                 ; (4096 + scatter) in Q14.9. Also
        move    a1,x0                   ; per-sample-constant, so the builder
        move    x0,a                    ; no longer rebuilds it four times.
        move    a,x:(r7+$55)            ; reset form, line R
; ---- the SCHEDULE: fixed rate, drives the envelope alone -----------------
; 2^23 / 4096 = 2048 samples per grain (46 ms). Grain SIZE is now free to
; become a parameter -- it is this constant and nothing else -- but page 2
; has no spare slot, so it stays fixed until something is given up.
        move    x:(r7+$32),a
        move    #>$400,x0
        add     x0,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a                    ; A2-clean; boot garbage dies here
        move    a,x:(r7+$32)
        move    a,x:(r7+$5d)            ; the builder's cursor
; ---- GRAIN's lag base, from SPRAY ---------------------------------------
        move    x:(r7+$5c),a            ; SPRAY, Q23
        asr     #$a,a,a                 ; ~ its max scatter in samples
        move    a1,x0
        move    #>8190,a                ; 16382 - 8192 (a +12 grain's own
        sub     x0,a                    ; grain's upward traversal)
        move    a,x:(r7+$57)
        move    x:(r7+$75),a            ; TIME
        move    x:(r7+$57),x0
        sub     x0,a
        tst     a
        ble     grcapok
        clr     a
grcapok:
        add     x0,a
        move    a,x:(r7+$56)            ; GRAIN's lag base, this sample
; ---- HOISTED: the three per-sample draws (v2 stage 5f, optimisation) -----
; These read ONLY per-sample-constant state -- the select index, the PRNG
; word (advanced once above) and the DENS knob -- so all four builder
; iterations were computing IDENTICAL values four times over. Lifting them is
; therefore BIT-IDENTICAL, not merely equivalent, and the gate proves it.
;
; It is also correct for a second, independent reason worth writing down: the
; four grains sit at exact quarter offsets of a schedule advancing $1000 per
; sample, so their wraps are 512 samples apart and AT MOST ONE GRAIN WRAPS
; PER SAMPLE. A single candidate is all that can ever be consumed.
;
; They live in REVERSE's per-block slots, which is sound for the same reason
; GRAIN already borrows its scratch: the mode alternatives are mutually
; exclusive within a sample, and REVERSE rebuilds these every block.
; The select is the SET WIDTH, and entry 0 is +12 so that a mask of 0 --
; select index 0 -- pins every grain to the octave. That is the fixed engine,
; the nearest thing to what was ear-passed before the split, and it stays
; reachable for comparison.
;   index 0 -> mask 0: +12 only          index 1 -> mask 1: +12 / unison
;   index 2,3 -> mask 3: +12 / unison / +7 / -12
        move    x:(r7+$18),a            ; the interval-hold roll draw
        asr     #$c,a,a                 ; bits 12-13: a field no other draw
        and     #>$3,a                  ; touches (set 0-2, density 5-10)
        move    a1,x0                   ; the AND leaves A2 stale, so the
        move    x0,a                    ; value leaves through a1
        move    a,x1                    ; park: 0 == re-pitch at this wrap.
                                        ; x1, NOT y1 -- the builder's window
                                        ; smoothstep clobbers y1 every pass.
                                        ; p = 1/4, so a grain holds ~4 lives.
        move    x:(r7+$5f),a            ; select index
        move    #>$7,b                  ; index 3 -> the WIDE 8-entry set
        tst     a
        move    #>$0,x0
        teq     x0,b                    ; index 0 -> fixed +12
        move    #>$1,x0
        cmp     x0,a
        move    #>$1,x0
        teq     x0,b                    ; index 1 -> +12 / unison
        move    #>$2,x0
        cmp     x0,a
        move    #>$3,x0
        teq     x0,b                    ; index 2 -> the shipping 4-entry set
        move    b,x0
        move    x:(r7+$18),b
        and     x0,b
        move    b1,x0
        move    x0,b                    ; A2-clean before the compares
        move    #>$fffe00,a             ; 0 -> +12  (-512)
        move    #>$1,x0
        cmp     x0,b
        move    #>$0,x0                 ; CLR is accumulator-only; a zero
        teq     x0,a                    ; immediate is the register form
                                        ; 1 -> UNISON (delta 0) -- impossible
                                        ; before the split, and most of what
                                        ; keeps the cloud musical
        move    #>$2,x0
        cmp     x0,b
        move    #>$155,x0               ; 2 -> -19  (+341)
        teq     x0,a
        move    #>$3,x0
        cmp     x0,b
        move    #>$100,x0               ; 3 -> -12  (+256)
        teq     x0,a
        move    #>$4,x0
        cmp     x0,b
        move    #>$0,x0
        teq     x0,a                    ; 4 -> UNISON again: 2/8, so the cloud
                                        ; still sits mostly at pitch
        move    #>$5,x0
        cmp     x0,b
        move    #>$ffff55,x0            ; 5 -> +5   (-171)
        teq     x0,a
        move    #>$6,x0
        cmp     x0,b
        move    #>$80,x0                ; 6 -> -5   (+128)
        teq     x0,a
        move    #>$7,x0
        cmp     x0,b
        move    #>$ffff00,x0            ; 7 -> +7   (-256)
        teq     x0,a
        move    a,x:(r7+$5e)            ; the candidate rate, this sample
        move    x:(r7+$18),b            ; density: three PRNG bits vs DENS
        asr     #$5,b,b
        and     #>$7,b
        move    b1,x0
        move    x0,b
        move    x:(r7+$2d),a            ; DENS (the WOW knob in GRAIN)
        asr     #$e,a,a
        move    a1,x0
        move    x0,a
        sub     b,a                     ; N SET == this grain stays silent
        clr     b
        move    #>$1,x0
        tmi     x0,b                    ; b = 1 when muted
        move    b,x:(r7+$60)            ; candidate mute, line L
        move    x:(r7+$18),b            ; its own density draw, so L and R
        asr     #$8,b,b                 ; gap independently
        and     #>$7,b
        move    b1,x0
        move    x0,b
        move    x:(r7+$2d),a
        asr     #$e,a,a
        move    a1,x0
        move    x0,a
        sub     b,a
        clr     b
        move    #>$1,x0
        tmi     x0,b
        move    b,x:(r7+$61)            ; candidate mute, line R

; ---- BUILDER ------------------------------------------------------------
        move    r7,a
        move    #>$34,x0
        add     x0,a
        move    a,r4                    ; -> record L0
        move    #>2,n4
        do      #4,>grnbz
; window gain from the SCHEDULE phase alone, halved (four grains sum to 2.0)
        move    x:(r7+$5d),a
        bsr     smoothw                 ; smoothstepped triangle (v6 roll --
                                        ; y0's wrap flag is parked AFTER this
                                        ; point, and smoothw never touches y0
                                        ; anyway)
        asr     #$1,a,a                 ; halved
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$59)            ; gain/2
; ---- this grain's own wrap: prev = (phase - SSTEP) & mask ----------------
        move    x:(r7+$5d),a
        move    #>$400,x0
        sub     x0,a
        and     #>$7fffff,a
        move    a1,x0                   ; prev (A1 only: the AND leaves A2
                                        ; stale, so it leaves through a1)
        move    x:(r7+$5d),a
        sub     x0,a
        abs     a
        move    #>$400000,x0
        sub     x0,a                    ; N SET == did NOT wrap
        move    a,y0                    ; ⚠️ PARK THE FLAG AS A VALUE, in y0 --
                                        ; free throughout the builder, and a
                                        ; register restore is a word cheaper
                                        ; than a memory one at every site. Eight
                                        ; Tcc's below depend on it and the
                                        ; arithmetic between them SETS the
                                        ; condition codes -- the exact bug
                                        ; stage 5d shipped and an ear caught.
                                        ; Every one of them restores it first.
; ---- the candidate rate for this grain, drawn from the SET ---------------
; unison is IN the set and is drawn as often as anything else, which is what
; keeps the cloud musical: most grains at pitch, some shifted.
; ---- record: rate, mute, offset, gain -- L then R ------------------------
        move    x1,a                    ; this sample's roll draw
        tst     a                       ; Z SET == re-pitch on this wrap
        move    #>$800000,x0            ; else force "did not wrap", so the
        move    y0,a                    ; grain KEEPS its own current rate
                                        ; (a MOVE leaves the flag alone)
        tne     x0,a                    ; roll missed -> hold this pitch
        tst     a                       ; sign = wrapped AND rolled
        move    x:(r7+$5e),x0           ; candidate rate, hoisted
        move    x:(r4),b                ; current rate
        tpl     x0,b                    ; wrapped -> take the new one
        move    b,x:(r4)+
        move    b,x:(r7+$5a)            ; this grain's LIVE rate, for the
                                        ; offset update two words along
        move    y0,a
        tst     a
        move    x:(r7+$60),x0           ; candidate mute L, hoisted
        move    x:(r4),b                ; current mute
        tpl     x0,b                    ; wrapped -> take the new one
        move    b,x:(r4)+
        move    b,x:(r7+$5b)            ; the LIVE mute
; offset: reset to (2048 + scatter) << 9 at the wrap, else += rate
        move    x:(r7+$5a),a            ; this grain's rate delta
        neg     a                       ; -delta: POSITIVE only for upshifts
        move    #>$0,x0
        tmi     x0,a                    ; a downshift reserves NOTHING
        asl     #$d,a,a                 ; x8192 = (drift samples) << 9 at L=8192
        move    a1,x0                   ; asl leaves A2 stale
        move    x0,a
        move    x:(r7+$54),x0           ; + (scatter << 9), hoisted
        add     x0,a
        move    a1,y1                   ; this grain's own RESET form
        move    x:(r4),a                ; current offset
        move    x:(r7+$5a),x0           ; this grain's live rate
        add     x0,a                    ; the RUNNING form, in a
        move    y1,x0                   ; the RESET form -- Tcc takes
                                        ; a REGISTER source, never an accumulator
        move    y0,b                    ; the parked wrap flag
        tst     b                       ; N SET == did not wrap
        tpl     x0,a                    ; wrapped -> reset
        move    a,x:(r4)+
; gain, zeroed when this grain is muted
        clr     b
        move    x:(r7+$5b),a            ; live mute
        tst     a
        move    x:(r7+$59),x0           ; gain/2
        teq     x0,b                    ; mute==0 -> sounds
        move    b,x:(r4)+
; ---- the same four words for line R -------------------------------------
        move    y0,a
        tst     a
        move    x:(r7+$5b),x0
        move    x:(r4),b
        move    x:(r7+$5a),x0           ; R shares the grain's RATE
        tpl     x0,b
        move    b,x:(r4)+
        move    y0,a
        tst     a
        move    x:(r7+$61),x0           ; candidate mute R, hoisted
        move    x:(r4),b
        tpl     x0,b
        move    b,x:(r4)+
        move    b,x:(r7+$5b)
        move    x:(r7+$5a),a            ; this grain's rate delta
        neg     a                       ; -delta: POSITIVE only for upshifts
        move    #>$0,x0
        tmi     x0,a                    ; a downshift reserves NOTHING
        asl     #$d,a,a                 ; x8192 = (drift samples) << 9 at L=8192
        move    a1,x0                   ; asl leaves A2 stale
        move    x0,a
        move    x:(r7+$55),x0           ; + (scatter << 9), hoisted
        add     x0,a
        move    a1,y1                   ; this grain's own RESET form
        move    x:(r4),a
        move    x:(r7+$5a),x0
        add     x0,a
        move    y1,x0                   ; the RESET form
        move    y0,b
        tst     b
        tpl     x0,a
        move    a,x:(r4)+
        clr     b
        move    x:(r7+$5b),a
        tst     a
        move    x:(r7+$59),x0
        teq     x0,b
        move    b,x:(r4)+
; ---- next grain: a quarter of the schedule further round -----------------
        move    x:(r7+$5d),a
        move    #>$200000,x0
        add     x0,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$5d)
grnbz:
        nop
; ---- READER, line L: offset at +2, gain at +3, stride 8 -----------------
        move    r7,a
        move    #>$36,x0
        add     x0,a
        move    a,r4
        move    #>6,n4
        clr     b
        do      #4,>grnlz
        move    x:(r4)+,x0              ; this grain's offset, Q14.9 -- it
        move    x0,x:(r7+$5b)           ; carries BOTH the integer lag and the
                                        ; lerp fraction now, because each grain
                                        ; advances at its own rate and so has
                                        ; its own sub-sample position. There is
                                        ; no shared fraction any more.
        move    x0,a
        asr     #$9,a,a                 ; integer samples
        move    a1,x0
        move    x0,a                    ; A2-clean
        move    a,x:(r7+$5a)
        move    x:(r7+$5b),a
        and     #>$1ff,a                ; the fractional part
        asl     #$e,a,a                 ; -> Q23
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$5b)            ; park frac
        move    r1,a                    ; LineL write pointer
        move    x:(r7+$56),x0           ; GRAIN's lag base
        sub     x0,a
        move    x:(r7+$5a),x0           ; this grain's integer offset
        sub     x0,a
        and     #>$3fff,a               ; read phase, t0
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$5a)            ; park phase
        move    x:(r7+$31),x0           ; LineL base
        add     x0,a
        move    a,r5
        move    y:(r5),a                ; t0
        move    a,x:(r7+$57)            ; park t0
        move    x:(r7+$5a),a
        move    #>$1,x0
        sub     x0,a
        and     #>$3fff,a               ; one sample OLDER
        move    a1,x0
        move    x0,a
        move    x:(r7+$31),x0
        add     x0,a
        move    a,r5
        move    y:(r5),a                ; t1
        move    x:(r7+$57),x0           ; t0
        sub     x0,a                    ; t1 - t0, signed
        move    a1,x0                   ; -> FIRST mpy operand
        move    x:(r7+$5b),y1           ; frac, prepared above
        mpy     x0,y1,a
        move    x:(r7+$57),x0
        add     x0,a                    ; tap = t0 + frac*(t1-t0)
        move    a,x0                    ; LIMITING move
        move    x:(r4)+,y1              ; this grain's window gain / 2
        mpy     x0,y1,a
        add     a,b
        move    (r4)+n4
grnlz:
        nop
; +6 dB GRAIN MAKEUP (18 Aug 2026). Measured wet-only, GRAIN ran 14.2 dB
; under CLEAN at Sam's settings (SPRA 64, set 3) -- the largest mode-switch
; level jump in the box, mostly the 4-grain windowed sum's duty cycle. +6 is
; the HEADROOM-SAFE first step, not the whole gap: at SPRA 0 all four grains
; cluster coherently and can sum to ~4x a single tap, so closing the full 14
; would rail exactly there. asl, not a mpy: A2-consistent, no new constant.
        asl     #$1,b,b
        move    b,x:(r7+$24)            ; shifted OUTPUT tap L
; ---- READER, line R -----------------------------------------------------
        move    r7,a
        move    #>$3a,x0
        add     x0,a
        move    a,r4
        move    #>6,n4
        clr     b
        do      #4,>grnrz
        move    x:(r4)+,x0              ; this grain's offset, Q14.9 -- it
        move    x0,x:(r7+$5b)           ; carries BOTH the integer lag and the
                                        ; lerp fraction now, because each grain
                                        ; advances at its own rate and so has
                                        ; its own sub-sample position. There is
                                        ; no shared fraction any more.
        move    x0,a
        asr     #$9,a,a                 ; integer samples
        move    a1,x0
        move    x0,a                    ; A2-clean
        move    a,x:(r7+$5a)
        move    x:(r7+$5b),a
        and     #>$1ff,a                ; the fractional part
        asl     #$e,a,a                 ; -> Q23
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$5b)            ; park frac
        move    r2,a
        move    x:(r7+$56),x0
        sub     x0,a
        move    x:(r7+$5a),x0           ; this grain's integer offset
        sub     x0,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$5a)
        move    x:(r7+$68),x0           ; LineR base
        add     x0,a
        move    a,r5
        move    y:(r5),a
        move    a,x:(r7+$57)
        move    x:(r7+$5a),a
        move    #>$1,x0
        sub     x0,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$68),x0
        add     x0,a
        move    a,r5
        move    y:(r5),a
        move    x:(r7+$57),x0
        sub     x0,a
        move    a1,x0
        move    x:(r7+$5b),y1
        mpy     x0,y1,a
        move    x:(r7+$57),x0
        add     x0,a
        move    a,x0
        move    x:(r4)+,y1
        mpy     x0,y1,a
        add     a,b
        move    (r4)+n4
grnrz:
        nop
        asl     #$1,b,b                 ; +6 dB makeup, matching the L side
        move    b,x:(r7+$25)            ; shifted OUTPUT tap R
        bra     pdone
; MODEFORK_MID -- alternative 4: REVERSE

; ---- REVERSE: windowed backward reads (v2 stage 6) -----------------------
; The cheapest mode left, and cheap only BECAUSE the crossfade machinery
; already exists -- it is the same two complementary heads PITCH uses, with
; the head walking BACKWARDS through the line instead of drifting.
;
; THE MECHANISM, and why it needs no lerp. A phase runs 0..2^23 and the
; segment-local sample index is p = phase*S/2^23, which is EXACTLY what a
; fractional mpy of the phase by S computes -- so p advances by exactly 1
; per sample and the read lands on a whole sample every time. Contrast
; PITCH and TAPE, where the read sits between samples and the lerp is
; mandatory (the truncation floor that cost the first shimmer). Reverse at
; unity rate is the one moving read in this file that is exact.
;
;   read = wr - (LAG0 + 2p)
;
; and since wr advances by 1 per sample while p does too, the read address
; DECREASES by exactly 1 per sample: backwards, at unity speed. The 2 is
; not a fudge -- it is the write pointer running away from the read.
;
; Two heads half a segment apart, complementary-triangle windowed on the
; phase and smoothstepped, so g0 + g1 == 1 EXACTLY at every phase and the
; splice at each segment restart happens where that head's gain is 0. Both
; heads and BOTH LINES share one phase: each line reads its own buffer at
; the same lag, and the lines already hold different material (the input
; enters L only and crosses over through PING), so nothing is gained by
; giving them separate phases and one r7 slot is saved.
;
; OUTPUT ONLY, never in the loop -- stage 2c. A reverse read HAS a splice,
; so recirculating it would compound one per repeat, which is exactly the
; mechanism the PITCH ear pass rejected.
;
; mpy orientation: the possibly-negative operand (the tap) is always x0, the
; audited-signed `mpy x0,y1` form; y1 carries S or a window gain, both
; non-negative.
rmode:
        move    x:(r7+$5e),a            ; segment phase
        move    x:(r7+$61),x0           ; step = 2^23 / S
        add     x0,a
        and     #>$7fffff,a             ; wrap: one segment
        move    a1,x0
        move    x0,a                    ; A2-clean; boot garbage dies here
        move    a,x:(r7+$5e)
; ---- head 0: lag and window from the phase -------------------------------
        move    a1,x0                   ; phase
        move    x:(r7+$60),y1           ; S, non-negative
        mpy     x0,y1,a                 ; p = phase*S/2^23, EXACT (the
                                        ; product is a whole multiple of
                                        ; 2^23, so nothing is rounded)
        asl     #$1,a,a                 ; 2p -- the write pointer's run-away
        move    a1,x0
        move    x:(r7+$62),a            ; RLAG0
        add     x0,a
        move    a,x:(r7+$56)            ; lag0, shared by both lines
        move    x:(r7+$5e),a            ; phase again
        bsr     smoothw                 ; s = g^2*(3-2g) (v6 roll)
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$57)            ; g0
; ---- head 1: half a segment further on, same machinery -------------------
        move    x:(r7+$5e),a
        move    #>$400000,x0
        add     x0,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$5b)            ; park phase1
        move    a1,x0
        move    x:(r7+$60),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a1,x0
        move    x:(r7+$62),a
        add     x0,a
        move    a,x:(r7+$58)            ; lag1
        move    x:(r7+$5b),a
        bsr     smoothw                 ; (v6 roll)
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$59)            ; g1, and g0+g1 == 1 exactly
; ---- Line L: both heads, windowed and summed -----------------------------
        move    r1,a                    ; LineL write pointer
        move    x:(r7+$56),x0           ; lag0
        sub     x0,a
        and     #>$3fff,a               ; read phase (exact: the base is
        move    a1,x0                   ; 0x4000-aligned, so it falls out
        move    x0,a                    ; of the mask)
        move    x:(r7+$31),x0           ; LineL base
        add     x0,a
        move    a,r5
        move    y:(r5),a                ; tap, head 0
        move    a,x0                    ; possibly negative -> FIRST operand
        move    x:(r7+$57),y1           ; g0
        mpy     x0,y1,a
        move    a,b
        move    r1,a
        move    x:(r7+$58),x0           ; lag1
        sub     x0,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$31),x0
        add     x0,a
        move    a,r5
        move    y:(r5),a                ; tap, head 1
        move    a,x0
        move    x:(r7+$59),y1           ; g1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$24)            ; shifted OUTPUT tap L -- NOT $79
; ---- Line R: identical, on r2 / base $68 ---------------------------------
        move    r2,a
        move    x:(r7+$56),x0
        sub     x0,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$68),x0           ; LineR base
        add     x0,a
        move    a,r5
        move    y:(r5),a
        move    a,x0
        move    x:(r7+$57),y1
        mpy     x0,y1,a
        move    a,b
        move    r2,a
        move    x:(r7+$58),x0
        sub     x0,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$68),x0
        add     x0,a
        move    a,r5
        move    y:(r5),a
        move    a,x0
        move    x:(r7+$59),y1
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

; ---- write both lines: LineL receives x_in in full, LineR receives it
; scaled by 1-PING (v3 stage 2 -- was "LineR only ever hears whatever
; crosses over", which left PING=0 with no path into R at all) ------------
        move    x:(r7+$7e),x0           ; fbIntoL
        move    x:(r7+$73),y1           ; FDBK
        mpy     x0,y1,a
        move    x:(r7+$7d),x0           ; x_in
        add     x0,a
; ---- TAPE loop saturation (v2 stage 4b) ----------------------------------
; The record head compresses. y = w - w^3/3, applied to what each line is
; ABOUT TO BE WRITTEN (input + feedback for LineL, crossfed feedback for
; LineR) -- so it is in the loop, and every repeat is saturated again:
; -0.03 dB at 0.1 FS, -0.76 at 0.5, -3.52 at full scale, and a hot repeat
; train rounds off progressively the way tape does.
;
; WHY THIS CURVE AND NOT A DRIVE STAGE: small-signal gain is EXACTLY 1 and
; the curve is monotonic with |y| <= |w| over the whole fixed-point range,
; so it can only ever REDUCE magnitude. It therefore adds no loop gain and
; cannot introduce self-oscillation at any FDBK -- unlike a pre-gain soft
; clipper, which would also fold back above unity (y = u - u^3/3 turns over
; at u = 1) and need a clamp. There is no drive knob for the same reason
; the depth ceiling exists in the LFO block: the safe version is the one
; that cannot be knocked into a bad regime from the panel. Slot 10 is still
; free if the ear later asks for DRIVE.
;
; TAPE ONLY, via the same Tcc substitution as the FREEZE hold and the PITCH
; wet: cmp sets Z, moves do not disturb it, teq moves a CLEAN register in.
; CLEAN and PITCH are untouched, which is what keeps verify-delay's
; bit-identity gate green.
;
; Applied BEFORE the FREEZE substitution below on purpose: a frozen line
; must hold its contents EXACTLY (gain 1, a copy), and re-saturating the
; held loop every lap would grind it down instead.
; sat + drive, SHARED: the transform is identical for both lines, so it is a
; bsr subroutine (satdrv, end of file) -- the roll that paid for DRIVE's
; words. In: a = the value about to be written. Out: a. Clobbers b/x0/y0/y1
; and $2f/$30, none live across this point in either channel.
; FREEZE (v2 stage 3, crossfaded v6): while held, the write becomes the raw
; tap -- unity recirculation with the input excluded, so the last TIME
; samples loop for ever (read at wr-TIME, written at wr; the pointers must
; keep running or the reads would stall). FDBK, PING and the input are all
; bypassed while held; MIX, ->VERB and the PITCH heads keep working, so you
; can play over it. The hold select and its v6 engage-crossfade live in
; satdrv's tail (one copy for both lines); this line's raw tap rides in
; through x1, which satdrv never touches.
        move    x:(r7+$79),x1           ; the unshifted tap, this sample
        bsr     satdrv
        move    a,y:(r1)+                ; LineL write, advance

        move    x:(r7+$81),x0           ; fbIntoR
        move    x:(r7+$73),y1
        mpy     x0,y1,a
; ---- LineR ALSO takes the input now, scaled by 1-PING (v3 stage 2) -------
; LineR used to receive NOTHING but crossfeed, which made PING=0 a hole: with
; no path in, LineR stayed at digital silence for ever and the whole wet was
; hard left. Measured 17 Aug 2026 across the knob (CLEAN, TIME 40, FDBK 60):
; PING 0 left R at -999 dB; 32/64/96/127 leaned +20.1/+14.7/+11.5/+9.2 dB.
; There was no setting anywhere on the knob that produced a centred image.
;
; Scaling the new term by 1-PING rather than a fixed fraction is what keeps
; the knob meaningful, and it is why the obvious "just feed both lines" fix
; was rejected when this file was written: x_in is a MONO scalar by
; construction (the input block sums L+R), so a symmetric entry would make
; the two lines' state equations identical at every step for ANY value of
; PING -- provably, by induction -- and the knob would do nothing at all.
; Tying the asymmetry TO the knob dodges that: the lines are identical only
; at PING=0, and diverge everywhere above it.
;
; Measured after the change, same conditions: lean 0.00/2.26/4.90/7.76/7.83 dB
; and correlation +1.000/+0.998/+0.964/+0.714/-0.078 at PING 0/32/64/96/127 --
; a monotonic sweep from a perfectly centred mono delay to a decorrelated
; ping-pong, with no hole at either end.
;
;   PING   0 -> both lines fed equally -> a CENTRED MONO delay (corr +1.000)
;   PING  64 -> R fed at half -> partial bounce
;   PING 127 -> R fed 1/128 -> the classic ping-pong
;
; ⚠️ NOT quite "127 is unchanged": the knob's top is 127/128, so 1-PING is
; 0.008 rather than 0, and R keeps 0.8% of the direct input. That is enough to
; move the top of the knob measurably -- lean 9.17 -> 7.83 dB -- so PING=127
; is NOT bit-identical to the old engine and should not be described as such.
;
; ⚠️ The lean that REMAINS at PING=127 is not a defect and must not be
; "fixed": it is exactly one repeat's decay, because R's train IS L's train
; one repeat later. Verified across a 6:1 FDBK range -- lean 18.72/12.69/
; 9.17/5.60/2.96 dB against a per-repeat decay of 19.20/13.18/9.65/6.13/3.63
; at FDBK 20/40/60/90/120, a constant -0.5 dB residual. It is the arithmetic
; identity of any ping-pong fed on one side, and it shrinks as FDBK rises.
;
; mac, not a second mpy: the product accumulates onto fbIntoR*FDBK already in
; a. Same signed x0,y1 operand order as every other multiply in this file.
        move    x:(r7+$7d),x0           ; x_in
        move    x:(r7+$80),y1           ; 1 - PING
        mac     x0,y1,a                 ; + the direct input's share
; sat + drive, SHARED: the transform is identical for both lines, so it is a
; bsr subroutine (satdrv, end of file) -- the roll that paid for DRIVE's
; words. In: a = the value about to be written. Out: a. Clobbers b/x0/y0/y1
; and $2f/$30, none live across this point in either channel.
        move    x:(r7+$7a),x1           ; LineR's raw tap (see the L note)
        bsr     satdrv
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

; ---- PITCH / GRAIN: the wet becomes the SHIFTED tap (v2 stage 2c) --------
; Placed HERE deliberately: both lines have already been written above from
; the clean tap, so the shift can never re-enter the feedback loop. From
; this point on the wet -- own-track MIX, the shared DELAY WET buffer and
; the ->VERB send -- carries the shifted signal, and everything downstream
; stays mode-blind.
;
; Branchless via Tcc: tst sets Z, the intervening moves do not disturb it,
; and tne moves a CLEAN register into the accumulator (never a hand-rolled
; mask -- the A2-staleness store trap). In CLEAN and TAPE the flag is 0, tne
; does not fire and the wet is bit-identical to v1's.
;
; The mode test itself moved OUT of the sample loop in stage 5 ($33, resolved
; once per block): PITCH and GRAIN both land here, and an in-loop compare
; would have had to grow a second one to say so.
        move    x:(r7+$33),a            ; SHIFTED flag: PITCH or GRAIN
        tst     a
        move    x:(r7+$24),x0           ; shifted L
        move    x:(r7+$7b),b            ; loop's wet L
        tne     x0,b
        move    b,x:(r7+$7b)
        move    x:(r7+$25),x0           ; shifted R
        move    x:(r7+$7c),b
        tne     x0,b
        move    b,x:(r7+$7c)

; ---- own track: DRY AT UNITY + WET (v5, 23 Aug 2026) ----------------------
; The host track is still a RETURN in every bus-arithmetic sense -- its audio
; reaches the ENGINE only through IN, it is counted as a client only while
; IN>0, and its OT track fader scales the whole output -- but its own dry now
; passes through at unity underneath the wet. v3 stage 1's wet-alone output
; meant a sample on the delay's track with IN=0 was SILENT ("the effect
; deleted my audio"); Sam hit exactly that in the field, 23 Aug 2026, and
; called it: a return should not mute its host.
;
; Why unity and not a knob: the control story is already complete. Dry level
; is the track fader; the host's own wet amount is IN; everyone else's wet
; amount is their ->DELAY send. A DRY knob would duplicate the fader and cost
; a cloned descriptor (the formatter-inheritance trap family) for nothing.
;
; What v3 stage 1 fixed STAYS FIXED: the MIX image-walk cannot recur (the dry
; is added at unity, never crossfaded against the wet's different stereo
; geometry), and the host still gets no privileged engine drive -- IN puts it
; through the same 3-bit headroom and 1/N auto-gain as every sender. With
; a silent host track the added dry is zero and the output is bit-identical
; to v3's wet-alone, so pure-return usage is unchanged. The sum saturates on
; store like any dry+wet mixer; that is accepted, not guarded.
;
; (v3's history, kept short: v1 was `dry + wet*MIX`, v2 stage 5c a crossfade,
; both retired 17 Aug 2026 because they privileged the host's dry as the
; crossfade reference and its engine drive was immune to the 1/N -- measured
; as a 0.00 -> 7.82 dB image walk across MIX's travel. IN defaults to 0 --
; load-bearing, see build_bus.py's DEFAULTS: a nonzero default registers an
; audio-less client and dilutes every real sender.)
; ---- DRIVE MAKEUP (18 Aug 2026): out = wet * (1 + d/2), OUTPUT STAGE ONLY --
; The V0b/V127b captures proved the drive WORKS (peak -4.2 dB, crest -2.5,
; harmonics +5.3) and also why it reads as "not much": flat-top without
; makeup is quieter-and-harsher, not driven. +3.5 dB at full d matches the
; measured loss. ⚠️ OUTPUT STAGE ONLY, never inside satdrv: makeup on the
; recirculating write is loop gain, and the drive curve's whole safety
; argument is that it adds none.
;
; The dry is read STRAIGHT FROM THE BUFFER at the store site -- x:(r0) still
; holds this frame's input because nothing between the input read and here
; writes the audio buffer (n0 stays 1 throughout the loop). No stash slot,
; no r7 pressure. The old `move a,b / move x0,a / add b,a` dance collapsed
; to `add x0,a` (same a1 result: the dance truncated d*wet/2's low word via
; the limiting a->b move, but those bits sit below the stored a1 either way
; and the unity add cannot carry up from a0) -- the two words that freed per
; channel are exactly what the dry add costs, so v5 is net ZERO program
; words on payload B, which had 1 free.
; IN-KEYED WET MAKEUP (v8, 23 Aug 2026 -- the reverb's law, ported on Sam's
; "delay wet is quiet"): out gains + 2*IN*wet, so full IN lifts the wet
; +9.5 dB while IN=0 adds EXACTLY zero -- every send-fed return level stays
; bit-identical, drive included (additive term from the PRE-drive wet, so
; the drive path's store-clamp behaviour is untouched). y0 is free across
; this whole block; the mpy is the audited-signed y0,x0 form.
        move    x:(r7+$76),y0           ; IN, this block
        move    x:(r7+$7b),x0           ; wet L = fL
        move    x:(r7+$83),y1           ; d
        mpy     x0,y1,a                 ; d*wet
        asr     #$1,a,a                 ; d*wet/2
        add     x0,a                    ; wet * (1 + d/2)
; PING BALANCE + RETURN MAKEUP (R58, 24 Aug 2026, ear-approved locally the
; same evening). Two terms, OUTPUT STAGE ONLY (loop gain and the ->VERB
; stash r7+$87 untouched): both channels gain wet/2 (x1.5, +3.5 dB -- the
; delay return measured 5-13 dB under the reverb at equal send), and R
; additionally gains 0.75*PING*wet, centring the serial ping-pong's
; aggregate image (measured lean +7.9 dB at PING 127/FDBK 60 -> +4.4 dB;
; PING 0 was already symmetric and gets no shelf). At FDBK 0 the right
; line still has no repeat to lift -- inherent, documented in VOICING.md.
; mpy x0,y1 below is the audited-SIGNED order (wet in x0 goes negative).
        move    x0,b
        asr     #$1,b,b                 ; wet/2 -> x1.5 both channels
        add     b,a
        mpy     y0,x0,b                 ; IN * wet
        asl     #$1,b,b                 ; 2*IN*wet
        add     b,a                     ; + the makeup
        move    x:(r0),b                ; dry L, still in place
        add     b,a                     ; + dry at unity (v5)
        move    a,x:(r0)                ; L in place -- dry + wet
        move    x:(r7+$7c),x0           ; wet R = fR
        mpy     x0,y1,a
        asr     #$1,a,a
        add     x0,a
        move    x0,b
        asr     #$1,b,b                 ; wet/2 -> x1.5, matching L
        add     b,a
        move    x:(r7+$74),y1           ; PING (y1's d is done for this channel)
        mpy     x0,y1,b                 ; wet*PING (signed order)
        asr     #$1,b,b
        add     b,a                     ; + wet*PING/2
        asr     #$1,b,b
        add     b,a                     ; + wet*PING/4 -> R shelf 0.75*PING
        mpy     y0,x0,b                 ; makeup, R channel
        asl     #$1,b,b
        add     b,a
        move    x:(r0+n0),b             ; dry R
        add     b,a
        move    a,x:(r0+n0)             ; R in place -- dry + wet

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
        add     #>$1,a
        move    a,x:(r7+$64)            ; advance WET write pointer

; ---- ->VERB: wet (this delay's own output) + dry (this track's own
; pre-effect signal), scaled and summed into the shared REVERB ACC bus
; (BUS.md task 10). One-directional by construction -- see this file's
; header and modules/chonverb/reverb_server.asm's ->DELAY note for why the reverse never
; carries wet.
        move    x:(r7+$87),x0           ; delay's own wet, this sample
        move    x:(r7+$85),y1           ; -VRB (p5; hardwired v3..R29)
        mpy     x0,y1,a                 ; the whole contribution: the DRY half
                                        ; is GONE with its knob -- a return
                                        ; track has no pre-effect signal worth
                                        ; forwarding, and the designed path is
                                        ; delay WET -> reverb
        asr     #$3,a,a                 ; ⚠️ THE 3 BITS OF HEADROOM EVERY OTHER
                                        ; WRITER APPLIES. modules/send/send_client.asm
                                        ; scales its contribution by 1/8 before
                                        ; accumulating, and reverb_server undoes
                                        ; it with `asl #$3` after the auto-gain
                                        ; auto-gain -- so a writer that skips
                                        ; the /8 is amplified EIGHT TIMES on the
                                        ; way out. Measured 13 Aug: at VRBW 100
                                        ; the REVERB output pinned at 1.000 FS
                                        ; and only VRBW <= 50 was usable. An
                                        ; arithmetic shift, so A2 stays
                                        ; consistent and the store below cannot
                                        ; hit the saturation trap.
                                        ; ✅ AND IT NOW REGISTERS TOO (v3 stage
                                        ; 1, at the block above) -- the half
                                        ; that was deferred on 13 Aug. It had
                                        ; to land WITH the hardwiring: an
                                        ; unregistered writer's effective level
                                        ; is x8/N_registered, so a "fixed"
                                        ; amount would still have drifted by
                                        ; 18 dB between one sender and eight.
                                        ; A constant that is not constant is
                                        ; worse than a knob. ⚠️ It does change
                                        ; the balance of every OTHER reverb
                                        ; send by N/(N+1) -- that was the
                                        ; reason for deferring, and it is now
                                        ; a deliberate cost, not an oversight.
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
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts

; ---- modtap: the modulated lerped line read, shared by both lines ---------
; (18 Aug 2026, rolled with the x8 relaw.) In: a = line write pointer, $30 =
; the line's base. Out: a = the lerped tap at lag TIME + mod. Clobbers
; x0/y1/r5 and $2a/$2b (scratch); $2c (frac) is read-only here.
modtap:
        move    x:(r7+$75),x0           ; TIME
        sub     x0,a
        move    x:(r7+$29),x0           ; mod_int, signed
        sub     x0,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a                    ; A2-clean
        move    a,x:(r7+$2a)            ; park phase
        move    x:(r7+$30),x0           ; line base, staged by the caller
        add     x0,a
        move    a,r5
        move    y:(r5),a
        move    a,x:(r7+$2b)            ; t0
        move    x:(r7+$2a),a
        move    #>$1,x0
        sub     x0,a
        and     #>$3fff,a               ; one sample OLDER
        move    a1,x0
        move    x0,a
        move    x:(r7+$30),x0
        add     x0,a
        move    a,r5
        move    y:(r5),a                ; t1
        move    x:(r7+$2b),x0
        sub     x0,a                    ; t1 - t0, signed
        move    a1,x0                   ; -> FIRST mpy operand
        move    x:(r7+$2c),y1           ; frac
        mpy     x0,y1,a
        move    x:(r7+$2b),x0
        add     x0,a                    ; tap = t0 + frac*(t1-t0)
        rts

; ---- satdrv: loop saturation + DRIVE blend, shared by both line writes ----
; (18 Aug 2026 -- rolled when DRIVE landed; the two inline copies were the
; word cost that had blocked a drive stage since stage 4b.) See the call
; sites for the register/liveness contract. bsr, not jsr: dsp_asm implements
; only the RELATIVE b-forms.
satdrv:
        move    a,x:(r7+$2f)            ; park w. A LIMITING store: the sum
                                        ; can exceed full scale and a raw a1
                                        ; would WRAP where this saturates
        move    x:(r7+$2f),x0           ; w, saturated
        move    x0,y1
        mpy     x0,y1,b                 ; w^2   (signed x signed)
        move    b,y1                    ; limiting move: w^2 <= 1
        mpy     x0,y1,b                 ; w^3
        move    b,x0
        move    #>$2aaaab,y1            ; 1/3
        mpy     x0,y1,b                 ; w^3/3
        move    x:(r7+$2f),a            ; w
        move    b,x0
        sub     x0,a                    ; sat = w - w^3/3
        move    a,x:(r7+$30)
; SATURATION KEYS ON DPTH now, not MODE (18 Aug 2026, with TAPE's retirement):
; drift and tape-glue arrive together, which is exactly what selecting TAPE
; used to mean -- old TAPE at WOW=w>0 is bit-identical to CLEAN at DPTH=w
; INCLUDING this. The one retired corner: saturation with ZERO wobble (old
; TAPE at WOW=0), never voiced. A standalone DRIVE can decouple them later.
; tne, not teq: NONZERO depth takes the saturated write.
        move    x:(r7+$2d),b            ; DPTH (wow depth; zero iff knob is 0)
        tst     b
        move    x:(r7+$2f),a            ; w back (DPTH=0 keeps it)
        move    x:(r7+$30),x0           ; sat
        tne     x0,a
; ---- DRIVE (18 Aug 2026): blend toward the 2x-driven curve ----------------
; out = w + d*(hot - w), hot = sat(clamp(2w))/2. Unity small-signal at EVERY
; d (the blend of two unity-small-signal curves), monotonic, |out| bounded --
; so it adds no loop gain and cannot self-oscillate at any FDBK, the same
; argument as the base curve above. The LIMITING move on 2w IS the knee's
; hard half above |w| = 0.5, on purpose: clamp-then-cubic is the harder drive.
; d comes from core-private Y 0903h (p10 in every mode but GRAIN, where p10 stays SPRA and
; d is pinned 0 -- the per-block decode owns that fork). d = 0 is an EXACT
; bypass: the R35 gates all survive at DRIVE 0, which is this change's gate.
; w1 is already parked in $2f by the saturation block above -- reused, and u
; is parked in y0, which nothing reads between here and its next reload.
        move    a,x:(r7+$2f)            ; w1 (post-DPTH-select), limited park
        asl     #$2,a,a                 ; 4w (18 Aug 2026: the 2x knee measured
                                        ; under 1 dB at real repeat levels --
                                        ; "drive no". The knee now bites from
                                        ; 0.25 FS, and the clamp plateau above
                                        ; it is the flat-top half of the sound)
        move    a,x0                    ; u = 4w, LIMITED
        move    x0,y0                   ; park u
        move    x0,y1
        mpy     x0,y1,b                 ; u^2
        move    b,y1
        mpy     x0,y1,b                 ; u^3
        move    b,x0
        move    #>$2aaaab,y1
        mpy     x0,y1,b                 ; u^3/3
        move    y0,a                    ; u
        move    b,x0
        sub     x0,a                    ; sat(u)
        asr     #$2,a,a                 ; hot = sat(4w)/4
        move    x:(r7+$2f),x0           ; w1
        sub     x0,a                    ; hot - w1 (possibly negative)
        move    a,x0
        move    x:(r7+$83),y1           ; d (r7 -- see the decode's V0/V127 note)
        mpy     x0,y1,a                 ; d*(hot-w1) -- signed form, x0 negative-capable
        move    a,x0
        move    x:(r7+$2f),a
        add     x0,a                    ; w1 + d*(hot-w1)

; ---- FREEZE crossfaded hold (v6, 23 Aug 2026) -----------------------------
; THE SEAM CLICK FIX. v2 stage 3's hold switched the write from the live
; chain to the raw tap in ONE SAMPLE, so the captured loop carried a step
; between its newest and oldest sample -- and the copy-forward hold replays
; that step bit-exactly once per lap. Measured (DFRZAT repro, 23 Aug): one
; ~33x-local-slope spike every TIME+64 samples, forever; the hold itself
; was perfect (lap-to-lap identical), the capture boundary was the defect.
;
; Fix: write v = tap + r*(live - tap), with r armed at ~1 every RUNNING
; block (the decode's re-arm) and decaying by g per call -- two calls a
; sample, ~1.5 ms to silence -- ONLY while frozen. The first frozen writes
; are ~the live chain (continuous with what precedes them), morphing
; smoothly into the pure copy, so the loop content never contains a step.
; The heal happens once; after r reaches 0 the write is the tap EXACTLY
; (r == 0 makes v == tap to the bit), so the hold stays a bit-exact copy
; and neither decays nor grows -- stage 3's invariant survives.
;
; Lives HERE, not at the two call sites, for the same reason satdrv itself
; does: the transform is identical for both lines. The caller stages this
; line's raw tap in x1 (satdrv never touches x1) and the whole select moved
; in with it -- the sites shrank from six words to three. r lives in
; core-private Y 0904h, after the delay's RATE/DRV state at 0901h-0903h
; (the h spelling in prose keeps the census exact): the shared-window words
; at 0x360d3-5 are DEAD ON HARDWARE (R36), which is why none of this state
; goes there. r >= 0 always, and both mpy's below are the audited-signed
; x0,y1 form regardless.
;
; The running path is BIT-IDENTICAL to v5: the select takes the live value
; (the same limited store), r holds its armed value, and v is computed and
; discarded. One tst feeds BOTH Tcc pairs -- only moves and Tcc sit between
; them, the documented flag-sharing idiom, with nothing else allowed in.
        move    a,y0                    ; live (the limiting copy applies the
                                        ; same clamp the line store would)
        move    y:>$0904,y1             ; r
        sub     x1,a                    ; live - tap
        asr     #$1,a,a                 ; /2 keeps the product path in range
        move    a,x0
        mpy     x0,y1,a                 ; r*(live-tap)/2  [audited-signed]
        asl     #$1,a,a
        add     x1,a                    ; v = tap + r*(live-tap)
        move    a,x1                    ; v (the tap is consumed)
        move    #>$7b7889,x0            ; g ~ 0.9646/call = 0.93/sample:
                                        ; r reaches 1% in ~64 samples, 1.5 ms
        mpy     x0,y1,b                 ; g*r
        move    b,x0                    ; decayed candidate
        move    x:(r7+$26),a            ; FREEZE flag
        tst     a
        move    y1,a                    ; running: r keeps its armed value
        tne     x0,a                    ; frozen: r decays
        move    a,y:>$0904
        move    y0,a                    ; live
        tne     x1,a                    ; frozen -> crossfaded hold (same Z:
                                        ; moves and Tcc do not disturb it)
        rts

; ---- smoothw: smoothstepped triangle window from a phase (v6 roll) --------
; In: a = phase, 0..$7fffff. Out: a = s = g^2*(3-2g), Q23, where g is the
; triangle fold of the phase (t/2^22; the LIMITING move clips the single
; peak value, exactly as every site this replaces did). Clobbers x0/y1 and
; the $5a park; y0/x1/b are untouched -- GRAIN's builder parks its wrap flag
; in y0 across its call, and the freeze tap rides x1 through satdrv.
;
; THE ROLL THAT PAID FOR THE FREEZE CROSSFADE: this exact 17-instruction
; sequence appeared FIVE times (wow LFO, flutter LFO, GRAIN's builder,
; REVERSE head 0, REVERSE head 1), 21 words each -- found mechanically by
; scanning the built module for repeated instruction runs. 105 inline words
; became 22 + five 1-word bsr's. The wow/flutter copies parked g^2 in $2a
; and the others in $5a; both parks are transient, so the roll unifies on
; $5a ($2a stays the LFO block's own "park mod" scratch, untouched here).
; Bit-identity across all modes is the gate this shipped under, same as the
; modtap/satdrv rolls before it.
smoothw:
        move    #>$400000,x0
        sub     x0,a
        abs     a
        neg     a
        add     x0,a                    ; triangle, 0..$400000
        asl     #$1,a,a                 ; g, 0..1 (limiting move clamps the peak)
        move    a,x0
        move    a,y1
        mpy     x0,y1,a                 ; g^2
        move    a,x:(r7+$5a)
        move    #>$7fffff,a
        sub     x0,a
        move    a,y1                    ; 1-g
        move    x:(r7+$5a),x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     x0,a                    ; s = g^2*(3-2g)
        rts

; ---- phead: one PITCH head -- lerped line read + smoothstep window --------
; (v7 roll, 23 Aug 2026.) The identical 45-instruction body appeared FOUR
; times (head 0/1 x Line L/R), 62 words each: the single biggest repeat the
; n-gram scan ever found in either server. Rolled to unblock verify_burn's
; plain-layout fit (the burn sweep re-measures the cycle ceiling, which is
; the live constraint again) -- the shipping payloads bank the rest.
; In: a = write pointer minus PLAGB minus age_int, with this head's SCATTER
; staged in x0 (the first sub consumes it); $15 = age_fx (frac source),
; $6f = age_int; the line base staged in $30 (modtap's convention -- per
; LINE, not per head: nothing between the two heads' calls touches it).
; Out: a1 (via a,y1 at the tail's last move) = 1-g staged for the caller's
; smoothstep finish; $17 = the lerped tap; $15 = g^2. Clobbers x0/y1/r5 and
; $16. b IS PRESERVED -- head 0's contribution rides it through head 1's
; call. Cycle cost: bsr+rts per head, and PITCH's fork path stays under
; GRAIN's, so the priced worst path is unchanged.
phead:
        sub     x0,a
        and     #>$3fff,a               ; read phase (t0, the newer neighbour)
        move    a1,x0
        move    x0,a                    ; A2-clean
        move    a,x:(r7+$16)            ; park phase
        move    x:(r7+$30),x0           ; line base, staged by the caller
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
        move    x:(r7+$30),x0
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
        rts
