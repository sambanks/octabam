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
;    Each line is a plain circular buffer read via modulo indexed addressing
;    (dsp/probe_echo.asm's proven shape: rN holds the write pointer, y:(rN+
;    nN) reads TIME-behind without moving it, y:(rN)+ writes and advances) --
;    simpler than reverb89's phase-plus-fixed-offset scheme, which exists
;    there to support per-line LFO modulation this file doesn't have.
;
; Memory (base = Y:0x30000, aligned to 0x4000 as modulo addressing requires):
;   LineL   base+0x0000 .. base+0x3fff   16384 words (max ~371 ms @ 44.1kHz)
;   LineR   base+0x4000 .. base+0x7fff   16384 words
;   total   0x8000 (32768) words -- BUS.md's 32K DELAY SERVER allocation
;
; State (all in the per-instance r7 block):
;   r7+$14              call flag stash (proc entry accumulator)
;   r7+$31              LineL base (hardcoded literal, stashed for symmetry
;                       with dsp/reverb_server.asm's convention)
;   r7+$63              this call's DELAY ACC read address (BUS.md bus)
;   r7+$64              this call's DELAY WET write address (BUS.md bus)
;   r7+$65..$67         split-aware bus bookkeeping (shared mechanism)
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
;   p6 ->VERB DRY -> this track's own pre-effect signal, parallel tap into the
;              same REVERB ACC bus, same shape as dsp/send_client.asm's knobs.
;              Reads x:(r6+$d) -- BUS.md task 11 gave DELAY SERVER its own
;              descriptor (cloned from SPRING REV's bytes, not SPRING's own
;              id/slot -- tools/build_menu.py), and $d is the page-2 slot
;              that class's real hardware wiring puts at the same "MONO"-
;              equivalent position dsp/reverb_server.asm's ->DELAY send
;              already uses on its own (different instance's) $d -- no
;              conflict, r6 is per-instance. See DSP.md section 9 / REVERB.md
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

; ---- hardcoded base (BUS.md task 9: DELAY SERVER, Y:0x30000 payload A) ---
; No x:0x213 read, no per-instance stash -- see header note above about
; payload B's literal not yet being parameterized by the build tooling.
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

        move    x:(r7+$71),a            ; LineR phase
        move    #>$3fff,x0
        and     x0,a
        move    a1,x0
        move    x0,a
        move    x:(r7+$31),x0
        move    #>$4000,b
        add     x0,b                    ; b = LineL base + 0x4000 = LineR base
        move    b,x0
        add     x0,a
        move    a,r2                    ; LineR write pointer

        move    #>$3fff,m1              ; MODULO 16384: each line wraps
        move    #>$3fff,m2              ; inside its own 0x4000-aligned half

; ---- shared tap offset: both lines use the same TIME ----------------------
        move    x:(r7+$75),a
        neg     a
        move    a,n1
        move    a,n2

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
        move    y:(r5),b                ; last block's fully-summed sends
        move    x:(r7+$7d),a
        add     b,a
        move    a,x:(r7+$7d)            ; x_in = dry + bus
        move    x:(r7+$63),a
        move    #>$1,x0
        add     x0,a
        move    a,x:(r7+$63)            ; advance ACC read pointer

; ---- read both delayed taps (pointer stays put; n1/n2 look TIME back) ----
        move    y:(r1+n1),a
        move    a,x:(r7+$79)            ; dL
        move    y:(r2+n2),a
        move    a,x:(r7+$7a)            ; dR

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
