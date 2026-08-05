# Effect bus: shared delay + reverb sends (design, in progress)

**Status: both buses and the cross-bus sends are emulator-verified; the
ColdFire menu has been through two hardware flashes.** Flash 1 found a
chooser-overdraw bug; flash 2 found the real cause of "no knobs" — the
descriptor clone was copied from `E` rather than `P = E+0x38`, losing the
record's last `0x38` bytes and with them the **per-parameter enable
bitmap** (`P+0x18a`/`P+0x18e`), so every clone declared itself to have no
parameters. That, a missing selectable `NONE`, and donor defaults that were
wrong for our algorithms (DARK's `MIX`=0 would have made REVERB SERVER
silent regardless) are all fixed. See "Hardware test 1" and "Hardware test
2" below. Third flash pending. `dsp/send_client.asm` (the client),
`dsp/reverb_server.asm` (the REVERB server, reusing the existing engine) and
`dsp/delay_server.asm` (the DELAY server, a new algorithm — task 9) all exist
and are emulator-verified, individually and together (Mechanism section
below) — guard-clean, and a value that only exists in the shared bus scratch
has been shown to reach each server's engine and come back out its own WET
buffer. Task 10 (cross-bus sends) is also built and verified: REVERB
SERVER's dry `→DELAY` send and DELAY SERVER's `→VERB` wet+dry sends both
land correct, hand-checkable Q1.23 values in the other bus's accumulator
(Cross-bus sends section below). Task 11 (`tools/build_menu.py`) replaces
FX2's chooser with exactly the three entries below, each a fresh cloned
descriptor under a brand-new id so FX1 is never touched even in the sense of
shared-descriptor text bleed-through — verified against the real, decompiled
ColdFire chooser functions (Menu and slot layout section below), not yet
against the DSP dispatch tables (a separate, not-yet-scoped follow-up). It
builds entirely on mechanisms `REVERB.md`, `DSP.md` and `PARAM_PAGES.md`
already proved out, plus its own now-verified bus plumbing and menu tables —
this document adds no new reverse-engineering beyond that. Where it leans on
something still unverified, that's called out.

## Start here (state as of 4 Aug 2026)

**Built and running on hardware.** Three FX2 effects sharing a send bus:
`ChonVerb`, `BongDelay`, `Send`. Build with `python3 tools/build_bus.py`
(writes `out/mainos_bus.bin`), check with `python3 tools/verify_menu.py`, then
wrap and flash per `README.md` §3. Latest flashed image carries `ChonVerb21`
(5 Aug 2026); `BUILD_TAG` in `tools/build_bus.py` is the source of that number.
**`ChonVerb22` is built but NOT yet flashed** — the v98 repack below.

**What we take from stock, and what we don't (v98).** All three servers pack
into **PLATE REV + SPRING REV + DARK REV** alone — 2724 contiguous words
against 2672 of code, 52 free. Those three ids are silenced on FX1; that is
the whole cost, and it is the trade the project was always making: three
stock reverbs for a better one.

**CHORUS is NOT taken and works normally.** It housed `Send`'s 166 words until
v98 — collateral rather than a considered trade, since Send fits inside the
reverb region with room over. Its code is byte-identical to stock and id
`0x12` keeps its stock dispatch entries, both payloads, asserted at build
time. Nothing had to be *recovered* to do this: every build starts from a
pristine `out/raw/section_3_MAIN_OS.bin`, so stock code is only ever
overwritten on the way out, never destroyed.

| | |
|---|---|
| build | `tools/build_bus.py` — DSP placement + all five ColdFire tables, both payloads |
| verify | `tools/verify_menu.py` — menu tables vs the real decompiled chooser |
| sources | `dsp/reverb_server.asm`, `dsp/delay_server.asm`, `dsp/send_client.asm` |
| probes | `dsp/page2_probe.asm`, `dsp/xmem_probe.asm` (diagnostics, `PROBE=1` / `XPROBE=1`) |

**ChonVerb is feature-complete and voiced as of `ChonVerb21` (5 Aug 2026)**:
32K re-layout, tank headroom, modulated in-loop allpasses, early reflections, a
MODE select varying six per-mode levers, and a dry/wet law that does not lose
level as it is turned up — all confirmed on hardware by ear. Per-mode voicing
is **done** (`VOICING.md` Rounds 1–5); what remains on the reverb is small and
listed at the end of `REVERB.md`. **BongDelay is still placeholder** — the
plumbing is verified, the algorithm has never been designed or voiced, and it
is now the largest open piece of work on the bus.

The effect's displayed name carries its build number (`BUILD_TAG` in
`tools/build_bus.py`) — bump it every time a `.bin` is wrapped. Three debugging
rounds were lost to not being able to tell which firmware was on the unit.

Cycle budget is **measured, not guessed** — by `python3 tools/cycle_count.py`,
which is the only correct way to get it: `tools/dsp_host` CANNOT measure this
(its `instructions/sample` does not scale with frame count). A full bank
(reverb + delay + two sends) is **930 of ~1080 cycles/sample — 86% used, 150
free**, and that is a floor, since the count models no memory-contention
stalls. Earlier hand counts of 529 and ~700 were both wrong; see `REVERB.md`
for the correction and for the one large lever that is left. **Re-run the tool
after any change to a sample loop.**

**Read before touching parameters:** `DSP.md` §9 (page-2 slot mapping, measured
— two earlier guesses were wrong and cost flashes) and `PARAM_PAGES.md` §5e
(the five tables, and the P-vs-E descriptor trap that cost two more).

**Constraints that are settled, don't re-chase them:** 32,768 words per server
is the memory ceiling (`DSP.md` §7c, probed); 12 parameters per effect, six
page-1 knobs plus three page-2 knobs and three page-2 selects (`DSP.md` §9).

## Motivation

The custom reverb (`REVERB.md`) is a per-track insert, run independently on
all 8 tracks. That's about as far as an insert can go. The Digitakt/Digitone
pattern — one shared reverb (and delay) that every track sends into at its
own level, rather than 8 independent copies — isn't something the OT's stock
firmware or ours currently offers, and stock hardware makes delay+reverb
coexisting on one track impossible at all (two simultaneous reverbs already
glitch, `PARAM_PAGES.md` §5d). This is a plan for building a send/return bus
inside a machine that was never given one.

## Why a real bus doesn't exist and can't be added the direct way

The DSP dispatcher (`DSP.md` §5–6) calls each track's FX1 and FX2 effect
independently, once per track per frame — every effect gets its own `r6`
param block, its own `r7` state, and its own track's audio in `r0`. There is
no discovered point where multiple tracks' audio is summed before an insert
runs. Building a literal pre-effect bus would mean patching the ColdFire
frame builder that assembles audio for the DSP — a much bigger reverse-
engineering project than the reverb itself, and out of scope here.

**The two DSPs are also a hard boundary, not a soft one.** Tracks 1–4 are
physically wired to chip A, tracks 5–8 to chip B (`ARCHITECTURE.md` §6,
`DSP.md`'s boot sequence) — separate chips, separate DMA/host-port channels.
The "shared" external 64K SRAM isn't a bridge between them either: it's
partitioned in half at build time, one half per payload. Nothing found so far
suggests the two chips exchange audio with each other in real time. So
whatever gets built here is **scoped per bank of four tracks (1–4, 5–8),
independently — not a single global 8-track bus.** A true unified bus would
need to solve real-time inter-chip communication, an open unknown, not a
known-but-unexplored lever like the ones below.

## The mechanism: fake a bus inside the per-track dispatch

Since every track already gets an independent effect call every frame, the
bus doesn't need new hardware access — it can be built entirely from effect
code that reads and writes a small piece of **shared absolute Y scratch**
(anywhere ≥ `0x800`, the one region proven safe across both payloads'
different loaded-module maps — `DSP.md` §11).

- A **client** track's process() call scales its own dry sample and adds it
  into a shared accumulator.
- A **server** track's process() call runs the real algorithm, using the
  accumulator (built up by every client this block) as input, and writes its
  wet result to a second shared scratch word.
- **Correction: clients don't read wet back.** `SEND`'s menu entry has
  exactly two knobs (`→DELAY`, `→REVERB`, both send-only — see Menu section);
  there's no third knob for a return level, and building `dsp/send_client.asm`
  made the earlier "every client reads that wet word back" claim above
  concrete enough to notice it doesn't match the menu it was describing. Wet
  only ever comes out via whichever track holds the `SERVER` role for that
  bus, through its own normal post-fx signal chain and existing `MIX` knob —
  the server's channel *is* the bus's return, in the same sense a mixing
  console's return channel is, not something piped back into every sender.

**Latency, made deliberate rather than accidental.** Round-robin per-track
dispatch means some tracks are called before the server each frame and some
after, which would otherwise give some tracks fresher data than others. Fix:
pin it — every send always writes into *next* block's input, every readback
always reads *last* block's wet. Same one-block latency for every track,
server included, rather than an inconsistency that depends on dispatch
order. At a handful of samples per block this is very likely inaudible
either way, but uniform is free and asymmetric isn't obviously so.

**Built and emulator-verified (`dsp/send_client.asm`, not flashed).** Two
double-buffered 16-word-per-block regions per bus (one bank's worth of
samples), plus a one-word parity flag, all in the same absolute-Y window as
the hardcoded server bases:

```
Y:0x900            parity -- which buffer is this block's write target
Y:0x901..0x920     REVERB bus accumulator, buffers 0 and 1 (16 words each)
Y:0x921..0x940     REVERB bus wet, buffers 0 and 1        (servers write,
Y:0x941..0x980     DELAY  bus accumulator + wet, same shape  SEND never reads)
```

The swap needs exactly one piece of code to run it once per block, not once
per track, and BUS.md doesn't get to assume a global hook for that — so
whichever physical track is **position 0** (`r7 == 0x6200`, DSP.md §11's
fixed dispatch order — the first FX2 call in the bank every block, true
regardless of which of the three roles that track holds) flips the parity
and clears the new write-target buffers, before anyone — including itself —
accumulates into them that block. Every other track just reads whatever
parity that leaves. `tools/dsp_host` gained a `-peeky <addr,...>` flag to
make this checkable at all (it had no way to inspect final Y-memory
contents before).

```sh
dsp_host -mem out/dsp/mem_send.mem -init 1252 -proc 1253 -inst 2 \
         -params 64,32,... -params 32,64,... -guard 32768 -blocks 2 \
         -peeky 900,901,911,941,951
# block 1: Y:0x900=1, Y:0x911/0x951=0x300000 (both clients' contributions
#          summed into the SAME buffer this block), Y:0x901/0x941=0 (idle)
# block 2: Y:0x900=0 (flipped back), Y:0x901/0x941=0 (cleared, this block's
#          silent input correctly summed to nothing), Y:0x911/0x951 STILL
#          0x300000 (last block's data, correctly left alone, not re-cleared)
# 0 CLOBBERING a loaded module in either run
```

That confirms the double-buffer swap, the position-0 election, and
same-block summation across two simultaneous clients all behave as designed.

**Bug found and fixed while wiring `REVERB SERVER` (task 8): the position-0
election above was wrong under a nonzero split.** `dsp/reverb89.asm`'s own
dispatcher note (its proc: comment) says a track's proc() runs *twice* in a
block that has a nonzero split — `a=0` first for frames `[0,split)`, then
always `a=1` for `[split,16)` — and `REVERB SERVER` inherits that call
pattern from the reverb engine unconditionally (it runs its body on both
calls, same reason `REVERB.md` gives: skipping the `a=0` call leaves a gap
in the tail after every trig). Gating the flip on `r7==0x6200` alone, as
first written, flips the parity **once per call** — twice in a split block —
which cancels itself out and silently desyncs the bus for that block. The
same gap existed on the write side: every call's per-sample ACC/WET writes
started at index 0 regardless of call, so a split `a=1` call would stomp the
start of the block instead of continuing from where `a=0` left off.

Fixed in both `dsp/send_client.asm` and `dsp/reverb_server.asm` with a small
per-call frame-offset computed from the SAME `r7+$14` call-flag idiom
`REVERB.md`'s engine already uses: the first call of a block (either the
`a=0` call, or the `a=1` call when there was no `a=0` this block) gets
offset 0 and may flip; a following `a=1` call gets the stashed split point
as its offset and may not. Verified in `tools/dsp_host` — 1 block, `-split
5`, position-0 (`r7==0x6200`): `Y:0x900` reads `1` after the run in both
files, where the un-fixed version left it back at `0` (flipped twice).

**Emulator-verified end-to-end (`dsp/reverb_server.asm`, task 8, not
flashed).** `tools/dsp_host` gained `-pokey addr=val,...` (seed Y memory
before the run) and `-peekx` (read X memory after), since the harness only
supports one `-init`/`-proc` pair per run and can't literally run a SEND
instance and a SERVER instance side by side. Instead: run `REVERB SERVER`
alone, as a non-position-0 instance (so nothing in the run touches the
shared parity/ACC on its own), silent audio throughout, and `-pokey` a
constant value into the REVERB ACC read-buffer to stand in for "SEND clients
have been contributing to this bus" —

```sh
# control: ACC seeded to 0 -- 900 blocks (past the ~256-block warm-up and
# long enough for the tank's own delay lines to complete a cycle), silence in
dsp_host -mem out/dsp/mem_reverb_server_A.mem -init 1252 -proc 1253 \
         -inst 1 -r7 4 -alloc 3 -blocks 900 -in silence.raw -pokey 900=0
#   0 non-zero output samples, Y:0x921 (WET) = 0 -- correctly silent

# test: same run, REVERB ACC read-buffer seeded nonzero throughout
dsp_host ... -pokey 900=0,911=200000,912=200000,...,920=200000
#   15481 non-zero output samples, Y:0x921 = 0xff9269 -- the bus contribution
#   alone, with no local audio at all, drives the reverb and reaches WET
```

That confirms the chain the Mechanism section describes end to end: a
value that only exists in the shared ACC buffer reaches the tank, comes back
out through the real algorithm, and lands in the shared WET buffer. Also
confirmed: hardcoded base independent of the allocator table (0 CLOBBERING
at `-alloc 1` and at a deliberately mismatched `-alloc 3`, matching step 1's
probe) and the split-aware fix above, both under `-guard`/`-dirty`.

**Built and emulator-verified end to end (`dsp/delay_server.asm`, task 9, not
flashed).** Unlike REVERB SERVER, there was no existing engine to reuse (the
stock DELAY effect was never reverse-engineered past "selectable but
produces no audible output on FX1", `PARAM_PAGES.md` §5d) — this is a new
algorithm: a two-line ping-pong delay, shared `Y:0x30000` base (32K, payload
A literal — see the file's header for the still-open payload-B literal
gap), one-pole tone-shaped feedback (the same "s += c*(d-s)" idiom
`dsp/reverb89.asm`'s HI control uses), and the same bus plumbing duplicated
verbatim a third time.

**Bug found and fixed by the emulator before it ever reached hardware: the
first design made the PING (ping-pong amount) knob provably do nothing.**
The first draft summed the track's own dry input into *both* delay lines
every sample, on the theory that PING=0 should behave as an ordinary
independent stereo echo. But this project's test input is unavoidably mono
(`tools/dsp_host`'s `-in` duplicates one stream to L and R, and the
undubbed default impulse does the same) — and for identical L/R input
entering a perfectly symmetric two-line system, the two lines' state
equations are identical at every sample, for *any* value of PING. A
symmetric system fed a symmetric input at a symmetric entry point cannot
diverge; this isn't specific to the emulator, it would have been true on
real hardware with real mono material too. Confirmed by running the
impulse test below on that draft: L and R came back bit-identical at every
echo, regardless of the PING param.

The fix: input enters LINE L ONLY, the textbook ping-pong topology. This
breaks the symmetry at the entry point instead of relying on the source
material being stereo, so the bounce is genuine for mono content AND
verifiable with this project's mono-only test harness. The tradeoff, stated
plainly rather than hidden: at PING=0, line R never receives anything (it
only ever hears `fbIntoR = fR`, and `fR` started at zero with no other way
in), so DELAY SERVER is a single-line (L-only) delay until PING moves off
zero — a real v1 characteristic, open to revisiting later, same
"starting point, not final" status as the 32K/32K memory split.

```sh
# impulse response, TIME=40(~5184 samples)/FDBK=90/TONE=100/PING=127/MIX=127,
# 1500 blocks x 15 frames, custom -in file: silence past warm-up then one
# impulse at frame 3900 (well after the 256-block warm-up completes)
dsp_host -mem out/dsp/mem_delay_server_A.mem -init 1252 -proc 1253 \
         -inst 1 -r7 4 -alloc 3 -blocks 1500 -frames 15 \
         -params 40,90,100,127,127 -in delay_impulse.raw -guard -dirty 0xC0FFEE
# echo 1 @ frame 9084 (3900+5184, exact TIME match): L only         -- input entry
# echo 2 @ frame 14268 (+5184 again):                dominant on R  -- first bounce
# echo 3 @ frame 19452 (+5184 again):                dominant on L  -- bounced back
# PING=0 control (same TIME/FDBK/TONE, same impulse): every echo stays L-only,
# R is silent throughout, exactly as the header note above predicts
# 0 CLOBBERING a loaded module in either run
```

That is a genuine alternating bounce, not an artifact — confirmed by
re-running with PING=0 and watching R go completely silent as the fix
predicts.

```sh
# bus wiring: silent local audio throughout, DELAY ACC's READ buffer seeded
# directly (parity 0 -> the ACC read comes from buffer 1, Y:0x951..0x960,
# not buffer 0 -- the same offset-by-16 mistake worth flagging: the first
# attempt at this test seeded 0x941..0x950 and got 0 output, which is the
# WRITE buffer, not the read one)
dsp_host ... -in silence.raw -pokey 900=0                              # control
#   0 non-zero output samples, Y:0x961 (WET) = 0
dsp_host ... -in silence.raw -pokey 900=0,951=200000,...,960=200000    # test
#   4476 non-zero output samples, Y:0x961 = 0x0fffff
```

Also confirmed: the split-aware parity fix holds in this file too (`Y:0x900`
reads `1`, not `0`, after a 1-block `-split 5` run at position 0), and
guard-clean (0 CLOBBERING) both with and without a split active.

**Built and emulator-verified end to end (task 10: cross-bus sends, not
flashed).** Both halves of the Cross-bus sends section below now exist in
code: `dsp/reverb_server.asm` gained a dry `→DELAY` send (one new knob on
the confirmed-dead `$d`/MONO slot) and `dsp/delay_server.asm` gained two new
knobs, `→VERB` WET and `→VERB` DRY. All three read the track's own signal
(dry mono, or — for DELAY SERVER's WET knob only — its own already-computed
processed output) and add a scaled contribution into the *other* bus's
accumulator, using the exact same per-call address bookkeeping (write parity
+ split-aware offset) the client and server files already established; no
new bus mechanism was needed; this is the ACC-bus write half of the same
addressing scheme send_client.asm's read/write already relies on.

```sh
# REVERB SERVER's ->DELAY (dry only): non-position-0 instance, one active
# block (blocks=257 lands exactly one call past the 256-call warm-up),
# constant dry input 0x100000 (Q1.23 0.125), DELAY ACC buffer pre-cleared
dsp_host -mem out/dsp/mem_reverb_server_A.mem -init 1252 -proc 1253 \
         -inst 1 -r7 4 -alloc 3 -blocks 257 -frames 15 \
         -params 0,0,0,0,0,0,0,0,100 -in loud.raw \
         -pokey 900=0,941=0,...,94f=0 -guard -dirty 0xC0FFEE \
         -peeky 941,...,94f,950
# control (->DELAY level 0): Y:0x941..0x94f all 0
# test (level 100, knob raw 100<<16 = Q1.23 0.78125): Y:0x941..0x94f all
# 0x0c8000 -- EXACTLY dry(0.125) * level(0.78125) * 0x800000 = 819200 = 0xc8000,
# hand-derivable to the bit. Y:0x950 (the buffer's 16th word) stays 0, correctly
# unused since a 15-frame block only fills 15 of its 16 slots.
```

```sh
# DELAY SERVER's ->VERB DRY: same shape, own dry tap ($83, stashed before the
# DELAY bus is folded into x_in) into the REVERB ACC bus
dsp_host -mem out/dsp/mem_delay_server_A.mem ... -params 0,0,0,0,0,0,110 ...
# DRY level 110 (raw 110<<16 = Q1.23 0.859375): Y:0x901..0x90f all 0x0dc000,
# exactly dry(0.125)*0.859375*0x800000 = 901120 = 0xdc000. DRY=0 control: 0.

# DELAY SERVER's ->VERB WET: needs the delay's own feedback to become
# genuinely nonzero first, which needs TIME samples of real elapsed audio --
# unlike the dry taps, this one can't be verified in a single block. TIME=0
# floors to 64 samples (this file's header), so with WET=127, DRY=0, FDBK=40,
# 5 active blocks (75 samples, just past the floor):
dsp_host ... -blocks 261 -frames 15 -params 0,40,127,0,0,127,0 -in loud_long.raw ...
# Y:0x901..0x904 (samples 60-63 elapsed, still short of TIME=64): exactly 0
# Y:0x905 onward (samples >=64 elapsed): nonzero and growing -- the transition
# lands EXACTLY at the sample TIME predicts, confirming the WET tap really is
# reading the delay's own processed signal and not some coincidental nonzero
# value. WET=0 control: silent throughout, same run otherwise.
```

That confirms both new sends independently: dry taps land exact,
hand-derivable Q1.23 products (same rigor as the ACC/WET bus tests above),
and the wet tap's nonzero onset lines up with TIME to the sample, which only
happens if it's really reading the delay engine's own state rather than raw
input. Also confirmed: guard-clean (0 CLOBBERING) in every configuration
above, and the split-aware parity fix still holds in both files after these
additions (`Y:0x900` reads `1`, not `0`, after a 1-block `-split 5` run at
position 0 in each). One test-methodology note worth keeping in mind for
future bus tests: a non-position-0 test instance never clears the ACC
buffers between blocks, so multi-active-block runs (needed for the WET test
above) accumulate every active block's contribution into the same words —
expected and accounted for above, not a bug, and irrelevant on real hardware
where whichever track holds position 0 clears the buffer every block.

## Menu and slot layout

**FX2's menu, on both banks, is replaced with exactly three entries:**

| entry | what it does |
|---|---|
| `DELAY SERVER` | runs the real delay algorithm on this track's own (post-FX1) signal |
| `REVERB SERVER` | runs the real reverb algorithm (the existing engine — `REVERB.md`) on this track's own signal |
| `SEND` | two knobs, `→DELAY` and `→REVERB` — dry, parallel taps into each bus's accumulator |

Any track can be given any of the three, selected exactly like any other
effect (`FUN_40052474`'s normal id-store path, `PARAM_PAGES.md` §5e). Nothing
is hardcoded to a specific track number — this took a real check, not just an
assumption: the per-instance allocator table (`X:0x255`) *is* fixed by track
position (`DSP.md` §11), which would have pinned server roles to specific
tracks had the servers read it. They don't (see Memory section below), which
is what keeps this claim true. On a four-track bank, the natural shape is one
`DELAY SERVER`, one `REVERB SERVER`, two `SEND` — but that's a convention,
not an enforced rule (see Known limitations).

**FX1 is untouched, on every track, including servers.** It keeps its full
stock menu — chorus, filter, phaser, whatever. This is deliberate: it means
none of this work touches FX1's descriptor, chooser list, or dispatch at
all, and every track keeps a normal per-track insert effect regardless of
its FX2 role.

**Built and verified, task 11 (`tools/build_menu.py`, `tools/verify_menu.py`).
Not flashed.** The ColdFire side of the three-entry menu above is done:
`PARAM_PAGES.md` §5e's five tables (id lookup, chooser list, descriptor
record, descriptor's own id byte, id→cursor reverse map) are all wired for
three brand-new ids —

| entry | id | donor (bytes cloned, not the donor's own id/slot) |
|---|---|---|
| `DELAY SERVER` | `0x01` | SPRING REV's descriptor (safe page-2 shape, see below) |
| `REVERB SERVER` | `0x02` | DARK REV's descriptor (same shape it already had) |
| `SEND` | `0x03` | FILTER's descriptor (only needs page-1 slots 0/1, safe regardless of shape) |

**Why clone-to-a-new-id instead of reusing a donor's own id (a correction
from the currently-shipped reverb build)**: the shipped `reverb71.asm` build
(`tools/build_reverb.py`) reuses DARK REV's *own* id and descriptor with no
ColdFire edits, which is why it needed none — but it also means FX1's own
DARK REV entry silently runs the new reverb engine too, accepted at the time
because it already shipped before this menu redesign existed. Task 11 is
already touching ColdFire tables, so there's no reason to repeat that
trade-off: each entry here is a full 402-byte copy of a donor's bytes at a
fresh address (`tools/build_menu.py`'s `CLONE_BASE`, a confirmed-free cave),
under an id (`0x01`/`0x02`/`0x03`) that was previously unassigned system-wide
and that FX1's own (untouched) id lookup and chooser list can never reach.
The donor's own id/descriptor/chooser slot is left completely alone —
`tools/verify_menu.py` diffs SPRING/DARK/FILTER's own descriptor bytes
against the pristine image and confirms all three are byte-identical, i.e.
FX1 selecting any of them still shows its original name and knobs.

**Donor choice is about page-2 safety, not theme.** `DSP.md` §9 / `REVERB.md`
measured (on real hardware, via `dsp/pagemap_probe.asm`) that page 2 is not
at `r6+6` and not in display order for the "class B" descriptors (page-class
handler `0x400328e4`: PLATE, SPRING, DARK, COMPRESSOR, MULTIBCOMP, LO-FI, DJ
EQ) — only `r6+$b/$c/$d/$e` are real, and DARK/PLATE's identical page-2 byte
layout (same names, same defaults, same counts, confirmed by dumping both)
is strong evidence the four-slot shape is fixed per class, not per effect.
No equivalent hardware measurement exists yet for "class A" (`0x40032814`:
FILTER, SPATIALIZER, DELAY, EQ, PHASER, FLANGER, CHORUS, COMB) — whether
*its* page 2 is safely straight (`r6+6..11`) is an open question this task
deliberately avoids answering by guessing. So: REVERB SERVER (already reads
`$b`/`$c`/`$d` for real, working knobs — Mechanism section) and DELAY SERVER
(now also reading `$d`, below) both clone class-B donors; SEND clones a
class-A donor but only ever touches page-1 slots 0/1, so the open class-A
page-2 question never applies to it.

**`dsp/delay_server.asm`'s `→VERB DRY` knob moved from the task-10 emulator
placeholder (`r6+$b`) to its real, final offset, `r6+$d`** — the same
"MONO"-shaped slot `dsp/reverb_server.asm` already uses for its own
`→DELAY` send on a *different* instance (no conflict, `r6` is per-instance).
Re-verified in `tools/dsp_host` at the new offset: DRY=110 lands the same
exact `0x0dc000` Q1.23 product as before (dry 0.125 × level 0.859375 ×
`0x800000`), DRY=0 is silent, guard-clean. `→VERB WET` stays at `r6+5`
(page 1's last slot, already safe by the general page-1-is-always-straight
rule, no class question at all) — unchanged by this task.

**Built and verified, task 13 (`tools/build_bus.py`). Not flashed.** The
three servers' own DSP code is now actually placed in P memory and
dispatched, both payloads:

**Superseded by v98 — the table below is the original per-donor placement and
is kept for the reasoning, not the addresses.** All three now pack into one
region, PLATE+SPRING+DARK, and CHORUS is given back; see "What we take from
stock" in *Start here*, and `tools/build_bus.py`'s docstring for the layout.

| entry | id | P-code donor | budget |
|---|---|---|---|
| `SEND` | `0x03` | ~~CHORUS~~ (329 words, confirmed no inbound branches — `tools/build_dspprobe.py`'s relocatability scan) | 127/329 |
| `DELAY SERVER` | `0x01` | PLATE REV (594 words, confirmed no inbound branches — `tools/build_reverb.py`'s own note) | 453/594 |
| `REVERB SERVER` | `0x02` | SPRING + DARK's front (2037/2130 words combined, the same budget `tools/build_reverb.py` already proved safe on hardware) | 1215/2037 |

These are DSP P-memory donors, unrelated to task 11's ColdFire descriptor
donors above (different address space, independent decisions).

**The relocation itself is cheap, and that is worth knowing.** Our code is
assembled from source with an `-org`, so moving a server is an argument
change plus two dispatch entries — the v98 repack moved all three and the
rendered output stayed **bit-identical across all four modes** and a
`TIME=127 SIZE=127 DIFF=127` wet case. Stock code is not relocatable on the
same terms: we have it only as a binary full of absolute branch targets, so
reclaiming more space means *taking a neighbour's module*, never *shuffling
theirs out of the way*.

**One trap the repack exposed:** `tools/render_reverb.py` had the engine's
entry point hardcoded as `1252/1253`. A hardcoded entry point does not fail
loudly when code moves — it jumps into the middle of whatever now lives
there. It now reads `X:0x215`/`X:0x235` out of the `.mem` being rendered,
which is also what makes `--mem` honest when the two builds being compared
put the engine at different addresses.

**Donor ids point at the proven-silent null stub, not our code** — a
deliberate departure from the currently-shipped reverb build, which
repoints SPRING/DARK's *own* ids at the new engine. That's fine there
because nothing else offers those ids once the three-entry menu replaces
the whole FX2 chooser — but FX1's chooser is untouched and can still select
CHORUS, PLATE REV, SPRING REV or DARK REV by name, and if their dispatch
pointed at our servers, selecting one on FX1 would run the same
hardcoded-Y-base engine a second, uncontrolled time on whatever track holds
it — exactly the multi-instance collision the hardcoded-base design assumes
can't happen (Memory section above). Repointing `0x12`/`0x14`/`0x15`/`0x16`
at `P:0x007c8`/`0x007c9` (payload A) / `P:0x00588`/`0x00589` (payload B)
avoids that: this is the *exact* null stub `tools/build_dspprobe.py` already
used and hardware-proved silent — and coincidentally identical to stock
DELAY's own dispatch, so FX1 selecting any of the four donor names now
behaves exactly like stock DELAY already does today.

**`dsp/delay_server.asm`'s payload-B Y-literal limitation is fixed**,
closing the last open item from task 9/10: `tools/build_bus.py` substitutes
`$30000`→`$38000` in the source text before assembling payload B's copy (one
occurrence, checked). Verified statically (not via `tools/dsp_host`, see
below) — the built image's payload-B module carries the substituted literal
at the exact word offset a standalone reassembly predicts.

**Verified in `tools/dsp_host`, payload A**: all three ids, called at their
real dispatch addresses (not a synthetic donor stand-in), reproduce their
already-established correct behaviour — DELAY SERVER's `→VERB DRY` send
still lands the exact Q1.23 product, REVERB SERVER's engine still passes
its guard-clean regression, SEND's two knobs land exact products in the
correct (REVERB vs DELAY) accumulator. 0 CLOBBERING in every case. **Payload
B could only be checked statically**: `tools/dsp_host`'s boot-setup step
(`runRange(0x372,0x39e)`, reading frame context from `x:0x415`) is a
payload-A-specific assumption baked into the harness itself, predating this
task — BUS.md already flagged "emulator testing so far only exercises
payload A" before task 13 existed, so this is a standing harness limitation
being hit for the first time, not a new gap this task introduced.

**Verification method, and why it stops short of Unicorn-executing the real
menu functions**: `tools/GhidraMenuFuncs.java` decompiled `FUN_40052474`
(fires when a cursor position is confirmed) and `FUN_4005996c` (menu-open,
one-time init) straight out of the firmware (Ghidra 12.1.2, the `out/ghidra_fx`
project already built for earlier chooser research). Both are pure data
computations over the five tables — list-length scan, `FX2_LIST[cursor]`
vs. independent `FX2_IDS[id]` lookup agreement, `ID2POS[id]` cursor seed —
which `tools/verify_menu.py` replicates directly against the built image and
confirms for all three new entries. It does *not* drive Unicorn through the
real functions, because `FUN_4005996c`'s one-time branch also calls several
indirect widget-setup function pointers (real screen/LCD drawing code) that
would need their own convincing stub, which is orthogonal to what task 11
needs to prove. This is the same "measure, don't guess" discipline in the
form the ColdFire side allows without a full UI emulation harness.

### Hardware test 1: two real bugs, both ColdFire-side, neither caught by the emulator

First real flash of `out/mainos_bus.bin` (ids `0x01`/`0x02`/`0x03`). Symptoms:
chooser correctly showed DELAY SERVER / REVERB SVR / SEND (proving the
five-table menu mechanism itself works), followed by **garbled symbols**
past the third entry; selecting any of the three showed **no parameter
knobs at all**; DELAY SERVER produced a **solid, unchanging tone**, REVERB
SERVER and SEND were silent. Both bugs turned out to be ColdFire-side, and
both are things nothing in this project's emulator could ever have caught —
`tools/dsp_host` only exercises the DSP chip directly (`-params` pokes `r6`
by hand), so it has never modeled the ColdFire→DSP parameter-push path at
all, on this build or the already-shipped one.

**Bug 1 — the chooser list renderer draws a fixed 7-row viewport, not the
real list length.** Decompiled `FUN_4005996c`'s menu-open path
(`tools/GhidraRenderFunc.java`, `tools/GhidraWidgetFuncs.java`): it correctly
*counts* the real list length by scanning to the terminator, but then calls
`FUN_4007ec60(&DAT_460d5ca0, 7, iVar4)` — the **literal `7`** becomes the
viewport height the row-drawing loop in `FUN_40037590` iterates over,
completely independent of `iVar4` (the real count, stored separately and
used only for scroll-clamping). The stock 15-entry list always had enough
real rows to fill that fixed 7, so this never mattered before. With only 3
real entries, rows 4–7 read `FX2_LIST[3..6]` — past our single terminator —
as raw memory, and rendered whatever bytes were there as a string pointer.
**Fixed** in `tools/build_menu.py`/`tools/build_bus.py`: the list is now
padded to a full 7 entries with the stock `NONE` descriptor's pointer
(`0x400d4618`, confirmed via a static check that it's the standard
"no effect" sentinel — `PARAM_PAGES.md`'s entry 14) before the real
terminator, so scrolling past the 3 real names shows blank/NONE rows
instead of garbage. `tools/verify_menu.py` now checks this directly.

**Bug 2 (likely) — ids `0x00`–`0x03` are hard-wired synonyms for "no
effect", not just currently-unused gaps.** A static table dump (all 32 FX2
ids against `FX2_IDS`) shows `0x00`–`0x03` *and* several other ids all
currently resolve to the same `NONE` descriptor — but `0x00`–`0x03` are the
**specific four low values** stock firmware uses as "no effect", which
strongly suggests some ColdFire logic elsewhere does a raw numeric `id < 4`
check rather than only ever consulting the descriptor-pointer table (the
chooser *naming* path does use the real table, which is why names displayed
correctly even while parameter values apparently never reached the DSP).
That would explain "no knobs" uniformly across all three (whatever pushes
page-1/page-2 values from the ColdFire descriptor into the DSP's `r6` block
per instance silently no-ops for a low id) and DELAY SERVER's solid tone as
a straightforward consequence — feedback (`FDBK`) and every other knob
stuck at uninitialized/zero rather than their real defaults is exactly the
shape of self-oscillation `DSP.md` §7e already flagged ("a flat envelope is
proof of instability"). **Not fully proven** — the actual parameter-push
mechanism itself hasn't been reverse-engineered, only ruled risky by this
one shared characteristic — but cheap and well-precedented to route around:
switched to `0x06`/`0x07`/`0x09`, ordinary unused gap ids that were never
given that special low-number meaning. `0x06` specifically is the same id
`tools/build_dspprobe.py` already proved runs custom DSP code correctly on a
real MKII (`DSP.md` §7d) — reusing a hardware-confirmed precedent rather
than a fresh guess. If knobs still don't work after this change, that rules
out the `id < 4` theory and points squarely at the unproven parameter-push
mechanism as the next thing to reverse-engineer.

Both fixes are in `tools/build_menu.py` and `tools/build_bus.py`; the DSP
code itself (`dsp/reverb_server.asm`/`delay_server.asm`/`send_client.asm`)
is untouched — re-verified in `tools/dsp_host` at the new dispatch addresses
and produces bit-identical results to before the id change, as expected
(the DSP side never knew or cared what id ColdFire used to reach it).

### Hardware test 2: the id theory was WRONG, and the real cause found

Second flash (ids `0x06`/`0x07`/`0x09`, padded list). Result: the garbage
symbols were gone and DELAY SERVER's stuck tone was gone — but **still no
knobs on any of the three**, and still **no way to switch FX2 off**. So the
`id < 4` theory above was wrong, or at least not the cause. Two real bugs,
both now found and both properly evidenced rather than guessed:

**The actual no-knobs cause: the descriptor clone was copied from the wrong
base, losing the parameter enable bitmap.** `FUN_400326d4` (stages a page)
and `FUN_40037590` (draws it) both call
`FUN_400a6994(*(u32*)(P+0x18a), *(u32*)(P+0x18e), paramIndex)` and gate on
the returned bit 0 — for staging the value, and for drawing the knob at
all. Dumping those two words across stock effects shows exactly what they
are: **a per-parameter enable bitmap, one nibble per parameter**, with
`P+0x18e` holding params 0–7 (low nibble = param 0) and `P+0x18a` params
8–11. The correspondence is perfect on every effect checked — SPRING's
`TIME --- --- HP LP MIX | TYPE BAL --- --- --- ---` gives nibbles
`1,0,0,1,1,1,1,1 | 0,0,0,0`, PLATE/DARK likewise, every `---` slot a zero
and every real knob bit 0 set.

`PARAM_PAGES.md` §5b already recorded the crucial fact — the canonical
record base is **`P = E + 0x38`**, and the record is `0x192` bytes long
*measured from P*, i.e. it spans `E+0x38 .. E+0x1ca`. Both earlier builds
copied `E .. E+0x192` instead: starting `0x38` bytes too early (picking up
the tail of the *previous* record) and ending `0x38` bytes short. `P+0x18a`
and `P+0x18e` sit precisely in that lost tail, so every clone read cave
zeros there — which means "this effect has no parameters at all". That is
exactly the observed symptom, and it also explains why the *names* were
fine: `P+0x16` (parameter names) was inside the copied range, while the
bitmap was not. **Fixed**: both scripts now copy from `donor_P` to
`clone_P` and use P-relative field offsets throughout (`P+0x03` id,
`P+0x16` names, `P+0x5e` defaults, `P+0x6a` min, `P+0x9a` count — the last
two independently confirmed by §5b's own decompilation). The enable bitmap
is written **explicitly** per effect rather than inherited, so a knob can
never appear that our DSP code doesn't read, or vice versa;
`tools/verify_menu.py` now asserts the enabled set matches the intended
one and that every enabled knob has a non-empty name.

**No selectable NONE.** The three-entry list never included one, so FX2
could not be switched off, and clicking a padding row appeared to do
nothing — it stores id 0, whose `ID2POS[0]` then re-seeded the cursor to
position 0, which was DELAY SERVER rather than NONE. **Fixed**: NONE now
sits at position 0 exactly as it does in the stock list, with `ID2POS[0]=0`
pointing back at it, and the three servers shifted to positions 1–3.

**Donor defaults were also actively wrong for our algorithms** — inherited
per-slot values that mean something different under our code. DARK REV's
`MIX` default is **0**, so a freshly selected REVERB SERVER would have been
inaudible even once knobs worked; SPRING's default on what is now our
`TONE` slot is 0, our darkest possible setting. Every enabled knob now gets
an explicit default chosen for our own algorithm (audible echo and reverb
out of the box), except both `SEND` levels and all three cross-bus sends,
which deliberately default to 0 so nothing routes anywhere until asked.

**The id change is retained but is now unattributed.** With the real cause
found, nothing proves `0x01`–`0x03` were ever a problem — the missing
bitmap alone explains every symptom. `0x06`/`0x07`/`0x09` are kept because
`0x06` is the id `tools/build_dspprobe.py` hardware-proved (`DSP.md` §7d)
and there's no reason to spend a flash reverting a harmless change, but
the "ids `0x00`–`0x03` are special" claim in Hardware test 1 above should
be treated as **unproven speculation, not a finding**.

The DSP memory image is **bit-identical** before and after this fix
(checked by diffing the dumped payload-A image), confirming this was
entirely a ColdFire descriptor-layout bug and that none of the
emulator-verified DSP work is implicated.

### Hardware test 3: both servers work; two real design faults exposed

Third flash. **DELAY SERVER works, page-1 knobs work, REVERB SERVER works on
a fresh track, and the `NONE` entry works** — the descriptor-clone fix was
correct. Two faults remain, both consequences of the hardcoded-base design
rather than bugs in it:

**Fault 1 — a track will not switch between the two servers.** Both keep
their warm-up counter in the same `r7+$82` slot with the same `$2c0000` tag,
and the dispatcher does not clear the per-instance state block when a
track's effect id changes. So the incoming effect read the *outgoing* one's
counter, saw a valid tag at full count, skipped its warm-up entirely and ran
on the other algorithm's leftover buffers. **Fixed**: `delay_server.asm` now
tags `$2e0000`, `reverb_server.asm` keeps `$2c0000`. A counter left by the
other effect now fails the tag compare, which restarts warm-up exactly as a
cold start does. (Verified by construction — both tags survive the `$fffe00`
mask distinctly — not by emulator test: `tools/dsp_host` cannot switch an
effect mid-run, and has no `-pokex` to plant a counter in X.)

**Fault 2 — two of the same server self-oscillated into a solid tone.** Both
servers use a fixed Y base identical for every instance, so a second DELAY
SERVER shared the first's delay lines and each drove the other's feedback
path. **Fixed** with a **role lock**: two new shared-scratch words,
`Y:0x981` (DELAY role) and `Y:0x982` (REVERB role), released once per block
by whichever effect is position 0 — alongside the parity flip it already
does — and claimed here in dispatch order. The first instance to arrive owns
the role; a duplicate `rts`s without touching the audio buffer, an exact dry
passthrough. Keyed on `r7`, so a split block's second call matches the same
owner rather than looking like a duplicate.

Emulator-verified: with two instances, the owner runs normally (delay 11
non-zero output samples and 905 stray write regions; reverb 10309 and 2160)
while the duplicate produces **2 non-zero output samples — the dry impulse
alone — and 0 stray write regions**, i.e. it touched no memory whatsoever.
The two roles claim different words, so a delay and a reverb coexist
untouched. Guard-clean in every configuration.

**Housekeeping election, fixed in the same flash.** Adding `NONE` to the menu
broke an assumption the bus had relied on since task 7: the per-block
housekeeping (parity flip, accumulator clear, role-lock release) was done by
whichever track is position 0 (`r7 == 0x6200`, the bank's first FX2 call).
Set that track's FX2 to `NONE` and our code never runs there, so nobody
housekeeps and the accumulators saturate. Every menu entry used to do the
job, so this only became reachable once `NONE` existed.

Replaced with a **self-healing election**, in all three effects: position 0
still housekeeps whenever it is running, and any other instance takes over if
it observes that the parity has *not* changed since the last time it ran —
which can only mean nobody housekept in between. It costs one `r7` word per
effect (the parity that instance last saw) and needs no new global signal.
Gated on the split offset first, so a split block's second call can never
flip twice — the same trap the original position-0 code was written around.

Emulator-verified both ways. With **no** instance at position 0 (`r7` =
`0x6500` only, i.e. track 1 set to `NONE`) the parity now flips every block
— `1, 0, 1` across 1/2/3-block runs, where before it would have stuck. With
three instances and still no position 0, it flips exactly **once** per block,
not once per instance, and the DELAY accumulator reads `0x21c000` =
3 × `0x0b4000`, i.e. exactly one contribution each. The normal four-instance
case including position 0 is unchanged: one flip per block, `0x2d0000` =
4 × `0x0b4000`.


### Hardware test 4: a cold-boot DSP freeze, and its cause

Fourth flash. The renames, the warm-up-tag fix (a track now switches between
the two servers), and the role lock (a duplicate server is silent instead of
a solid tone) all work. But **selecting `SEND` on any track from a clean
boot froze the unit** — audio and sequencer both, the signature of a DSP
stall (`DSP.md` §7d: the sequencer is clocked by the DSP frame interrupt).

Cause, found by reading rather than bisecting: the split-aware frame-offset
code that all three effects share reads three `r7` state slots that hold
**boot garbage** the first time an instance runs. The a=1 path tested
`x:(r7+$65)` with `tst`/`bne` — *any* nonzero garbage passes — then copied
`x:(r7+$66)` unmasked into `x:(r7+$67)`, and that value is added straight
into `r1`/`r2` as a Y pointer. The per-sample loop then wrote through a wild
address every frame. This is the same class as `DSP.md`'s masked-garbage AGU
saturation, and it was latent in `dsp/send_client.asm` from task 7 — it only
became reachable once a cold boot could leave the wrong garbage in those
slots.

**Fixed** in all three files: the flag is masked and compared against
**exactly 1** rather than merely nonzero, and the stashed split point is
masked to `0..15` (its full legitimate range, so the mask cannot narrow a
real value) with the project's usual A2-clean on each. `r1` is now bounded
to `0x901 + parity*16 + 0..15` by construction, so no garbage can produce a
wild pointer. Guard-clean under `-dirty`, and the emulator cannot plant
garbage in an X state slot (`tools/dsp_host` has `-pokey` but no `-pokex`),
so this one is argued from bounds rather than reproduced in the harness.

**Still open**: the menu should make duplicate server roles *unselectable*
rather than merely harmless — the DSP lock is a fail-safe, not the intended
UX. That is the stage-2 selector work (hide a role once another track in the
bank claims it).

## Memory: pooling a bank's FX2 allocation

Every FX2 slot on a chip is already the same size — 16,384 words, two backed
by internal RAM (`0x4000`, `0x8000`), two by the external shared SRAM
(`0x30000`+) — so there's no "big" and "small" slot to begin with
(`DSP.md` §11). A bank's total FX2 pool is `4 × 16,384 = 65,536` words.

With the menu narrowed to two servers + client stubs, most of that pool
would otherwise sit idle (a `SEND` stub needs essentially no buffer), so the
two servers should split the whole bank's pool evenly — 32,768 words
(~744 ms) each — rather than leaving two slots' worth of memory unused.
This is `REVERB.md`'s "lever 2" ("4 large: 2 × 32K per DSP").

**Originally planned as a `X:0x255` allocator-table edit; superseded.**
Dumping the real table from both stock payloads (`tools/dsp_modmap.py
--dumpmem`) confirmed `DSP.md` §11's model exactly: FX2 instance *k* always
lands on table entry `1 + 2k`, which is **fixed by track position**, not by
which effect is selected there. Repointing the two sacrificed entries (3
and 7, both payloads — bases `0x8000` and `0x34000`/`0x3c000`) to the dead
region above `0xC000` (measured silent by `dsp/ymemprobe.asm`, confirmed on
real hardware) would work, but it permanently pins the two server roles to
tracks 1 and 3 of every bank and `SEND` to tracks 2 and 4 — contradicting
"any track, any role" below.

**Emulator-checked (`dsp/probe_hardcoded_base.asm`, not flashed).** A stand-in
for a server — init clears a literal-addressed `Y:0x4000..0xBFFF`, proc
touches both ends of that 32K span every block, never reads `x:0x213` at all —
run in `tools/dsp_host` against the real, unmodified stock table:

```sh
dsp_host -mem out/dsp/mem_probe_hcb.mem -init 1252 -proc 125d -inst 1 \
         -alloc 1 -guard 32768 -dirty 0xC0FFEE -blocks 50
#   base = Y:0x04000 (X:0x256 idx 1)
#   0 stray write regions, 0 CLOBBERING a loaded module -- guard clean
```

`dsp/minimal.asm` (already hardware-proven zero-footprint, DSP.md's two-track
freeze work) stood in for `SEND` at the neighboring real slot, `-alloc 3`
(table value `0x8000`, squarely inside the probe's 32K span): zero Y writes,
guard clean regardless of window. Together that is the whole safety argument
— the hardcoded probe never leaves `0x4000..0xBFFF`, and whatever legitimately
owns `0x8000..0xBFFF` under the new menu (`SEND`) never touches it either, so
they cannot collide no matter which physical track ends up hosting which role.

Rerunning the probe with a deliberately *mismatched* `-alloc 3` (table value
`0x8000`, not the `0x4000` the code hardcodes) confirms the independence
directly: the writes land at `Y:0x04000` regardless, reported as "stray"
against the table-derived window but **0 CLOBBERING a loaded module** — proof
the address doesn't move with the table, not a bug.

**Decision: don't touch `X:0x255` at all.** Instead each server hardcodes
its own fixed absolute Y base — `REVERB SERVER` always `Y:0x4000` (32K,
spans `0x4000–0xBFFF`), `DELAY SERVER` always `Y:0x30000` (payload A) /
`Y:0x38000` (payload B) (32K external) — the same technique pre-v22
single-instance builds used, instead of reading `x:0x213`/`x:(r4)`. This
reuses a proven pattern rather than opening new ground, and it restores true
track independence: whichever physical track's *real* table entry legitimately
overlaps one of these fixed bases is never a problem, because that track can
only ever be running `SEND` (menu-restricted to the three entries below) and
`SEND` touches zero per-instance buffer. The only requirement carried over
from the old plan is the same one already in Known limitations — at most one
instance of each server role per bank, self-enforced, not hardware-enforced.

The split doesn't have to be even forever — reverb is the one with
measured "more memory = smoother" behavior (`REVERB.md`'s spectral-flatness
findings), delay doesn't have the same mode-overlap problem. 32K/32K is the
agreed **starting point**, with room to weight it later once there's
something to listen to.

## Cross-bus sends

**Built and emulator-verified, task 10 (Mechanism section above has the
test evidence). Not flashed.** Every track, server or client, can reach both
buses:

| track role | own bus | other bus |
|---|---|---|
| `SEND` | — | `→DELAY` and `→REVERB` knobs, dry, parallel |
| `DELAY SERVER` | runs delay | `→VERB` **wet** (its own repeats bleed into reverb) + `→VERB` **dry** (its own signal, parallel) |
| `REVERB SERVER` | runs reverb | `→DELAY` **dry** only (parallel) |

**Delay → reverb (wet) is one-directional, deliberately.** This mirrors the
real Digitakt II, confirmed by its manual: the delay page carries its own
reverb-send parameter, signal order delay → reverb. There is **no**
reverb → delay wet chain — that would close a loop (delay's processed output
reaches reverb, reverb's processed output reaches delay, and round again),
which is exactly the shape of thing that self-oscillated on real hardware
during the reverb's own development (`DSP.md` §7e, "a flat envelope is proof
of instability").

**Dry parallel sends are safe in any direction and any number**, because
they tap a track's original signal, never another bus's output — there's no
way for them to close a loop. That's what makes the reciprocal dry sends
(both servers also acting as `SEND` clients to the other bus) free to add:
same mechanism as an ordinary client, just running inside code that's
already executing because that track owns a server role.

`REVERB SERVER`'s `→DELAY` knob turned out free in exactly the way
predicted: it reads the existing reverb descriptor's confirmed-dead `$d`
(MONO) slot — proven to do nothing on hardware (`REVERB.md`'s parameter
table) — with no layout change. `$e` (MIXF) remains unused, spare for later.

`DELAY SERVER`'s two new knobs (`→VERB` WET and DRY) are built as `p5` and a
second slot — read `x:(r6+$5)` and `x:(r6+$b)` respectively, not `$5`/`$6`,
because there is no real DELAY SERVER descriptor yet to fix a layout (task
11), and `$b` is simply the next offset `tools/dsp_host`'s `-params` flag
can drive for testing purposes (it emulates the specific remap DARK's real
descriptor uses, which `DELAY SERVER` doesn't inherit). Revisit the exact
offsets once that descriptor exists — nothing about the algorithm depends on
them.

**Decided: a knob, not a fixed coefficient**, for `DELAY SERVER`'s wet chain
into reverb — it fills the `p5` slot the file's header had already reserved
for exactly this, and it cost nothing extra to build as a knob once the
ACC-write addressing needed for the dry sends already existed.

## Known limitations

- **The position-0 double-buffer swap has to be duplicated verbatim in all
  three effect types.** There's no global per-block hook to hang it on
  (Memory/Mechanism sections above), so `SEND`, `DELAY SERVER` and
  `REVERB SERVER` each carry their own copy of the same parity-flip-and-clear
  code, keyed to the same literal addresses (`Y:0x900..0x980`, `r7==0x6200`)
  AND now the same split-aware frame-offset fix (Mechanism section). If a
  future edit changes those constants, or the offset logic, in one file and
  not the others, the bus goes silently out of sync rather than erroring —
  same character as the next bullet, but for the mechanism itself rather
  than user error. All three files (`send_client.asm`, `reverb_server.asm`,
  `delay_server.asm`) now carry this copy; any future fourth would too.
- ~~`DELAY SERVER`'s payload-B base literal is not yet parameterized~~
  **fixed, task 13** — `tools/build_bus.py` substitutes `$30000`→`$38000` in
  the source text before assembling payload B's copy. Checked statically
  (word-for-word against a standalone reassembly); `tools/dsp_host` itself
  can't run payload B at all yet (next bullet), so this couldn't be
  re-verified the same way task 10's other offsets were.
- **`tools/dsp_host` cannot run payload B.** Its boot-setup step
  (`runRange(0x372,0x39e)`, then reading frame context from `x:0x415`) is a
  fixed address range that only produces sane context for payload A's own
  boot content — pointed at a payload-B dump it reads all zeros and the
  harness reports "frame count is 0". Pre-existing (this doc already said
  "emulator testing so far only exercises payload A" before task 13), hit
  for the first time in task 13 when payload B needed its own check. Not
  investigated further — would need its own reverse-engineering of whatever
  payload B's equivalent setup routine is, which is out of scope here.
- **`DELAY SERVER`'s PING knob is L-only at PING=0 by construction, not
  oversight.** An earlier draft fed input into both delay lines so PING=0
  would be an ordinary independent stereo echo; that version's PING knob
  was provably inaudible on any mono source (Mechanism section's bug
  writeup) because a symmetric system fed identical L/R input never
  diverges regardless of the crossfeed matrix. The fix makes PING=0 mean
  "line R never receives anything" instead — correct and verifiable, but
  a real behavioural limitation worth a future look (e.g. a small fixed
  direct-to-R tap), not yet done.
- **No enforcement against picking the same server role twice on one
  bank.** Selecting `DELAY SERVER` on two tracks in the same four-track
  group means both write the same shared accumulator/wet scratch — an
  audible glitch, not a hardware risk, the same soft-failure character as
  the already-documented "reverb on FX1 and FX2 at once" case
  (`PARAM_PAGES.md` §5d). Documentation-only guard for v1, not a structural
  fix.
- **A server track's own musical content unavoidably feeds its own bus.**
  There's no way to run the algorithm without some signal going into it,
  and that signal is whatever the track is playing. Pick server tracks for
  the character you actually want soaked in that bus (a washy pad, a
  vocal chop) rather than treating them as neutral utility slots.
- **Reassigning which track holds a server role cuts, not crossfades.**
  Changing any effect selection resets that slot's state (the dispatcher's
  id-change-triggers-init behavior) — the outgoing server's tail stops
  abruptly, the incoming one starts cold. This already happens today
  swapping any effect on any track; not a new failure mode.
- **Bank-scoped, not instrument-wide.** Two independent bus pairs (1–4,
  5–8), not one shared across all 8 tracks. A track on one bank can never
  reach the other bank's buses.
- **Two full algorithms sharing one chip's cycle budget is unmeasured.**
  Three of four reverb instances collapsing into cheap send stubs frees a
  lot of headroom, but "should have room" isn't "measured has room" —
  `DSP.md` §12's standing rule (measure, don't guess) applies here same as
  everywhere else in this project.
- **Internal- vs external-backed FX2 memory under the merged 32K
  allocation is untested.** `DSP.md` §7 flagged unsettled timing
  differences between internal and external P memory; nothing directly
  tests whether the two external-backed FX2 slots (`0x30000`+) behave
  identically to the internal ones (`0x4000`/`0x8000`) once merged into a
  32K instance. The existing 8-track reverb milestone exercises both kinds
  without documented issue, which is reassuring but not the same as
  measuring this specific case.

## Open work (not yet designed)

- ~~`DELAY SERVER`'s own core sound~~ **decided and built, task 9** — a
  two-line ping-pong delay, tone-shaped one-pole feedback, TIME/FDBK/TONE/
  PING/MIX knobs (see Mechanism section and `dsp/delay_server.asm`'s
  header). Not yet on hardware, and the PING=0 single-line behaviour
  (Known limitations) is still a loose end.
- ~~Whether `DELAY SERVER`'s reverb send is a knob or fixed~~ **decided and
  built, task 10** — a knob (`p5`), see the Cross-bus sends section above.
- Exact split of the 32K/32K starting point if it ever moves off even.
- ~~Fixing `DELAY SERVER`'s payload-B base literal~~ **fixed, task 13** —
  see Known limitations.
- ~~`DELAY SERVER`'s two new `→VERB` knobs sit on `r6+$5`/`r6+$b` for
  emulator testing purposes only~~ **decided and built, task 11** — final
  offsets `r6+$5`/`r6+$d`, on DELAY SERVER's own cloned (SPRING-donor)
  descriptor. See Menu and slot layout.
- Whether class A's (`0x40032814`: FILTER, SPATIALIZER, DELAY, EQ, PHASER,
  FLANGER, CHORUS, COMB) page 2 is safely straight (`r6+6..11`) like class
  B's `$b/$c/$d/$e` shape is known to be (Menu and slot layout) — unmeasured,
  and task 11 deliberately routed around needing an answer rather than
  guessing one.
- ~~Placing `dsp/reverb_server.asm` / `delay_server.asm` / `send_client.asm`'s
  assembled code in P memory and repointing `X:0x215`/`X:0x235`~~ **decided
  and built, task 13** — see Menu and slot layout.
- `tools/dsp_host` cannot run payload B at all (Known limitations) — its
  boot-setup step assumes payload-A-shaped context. Unmeasured whether this
  is worth fixing versus just accepting static-only verification for payload
  B indefinitely.

## Build order, if this goes ahead

1. Verify the hardcoded-base approach in isolation first — confirm in
   `tools/dsp_host` (guard + dirty memory) that a server using a fixed
   absolute Y base never violates the guard even though it ignores
   `x:0x213` entirely, before it's tangled up with new effect code. Lighter
   than the allocator-table edit this replaced, since nothing about the
   stock table changes — the remaining risk lives entirely in our own
   effect code and gets covered by steps 2–4 anyway.
2. ~~`SEND` client stub~~ **done, emulator-verified, not flashed** —
   `dsp/send_client.asm`, see the Mechanism section above. Two knobs, zero
   footprint on its own per-instance buffer (confirmed alongside step 1's
   probe), and the position-0 double-buffer swap the whole bus depends on.
3. ~~One server~~ **done, emulator-verified, not flashed** —
   `dsp/reverb_server.asm`, see the Mechanism section above. Reuses
   `dsp/reverb89.asm`'s engine unchanged apart from the hardcoded base and
   the bus plumbing; found and fixed the split double-flip bug (Mechanism
   section) along the way, in both this file and `dsp/send_client.asm`.
4. ~~The other server~~ **done, emulator-verified, not flashed** —
   `dsp/delay_server.asm`, see the Mechanism section above. A new
   algorithm (no engine to reuse this time): two-line ping-pong delay,
   tone-shaped feedback, same bus plumbing duplicated a third time. Found
   and fixed a real design bug along the way (PING was provably inaudible
   on any mono source in the first draft — Mechanism section).
5. ~~Cross-bus sends~~ **done, emulator-verified, not flashed** — a dry
   `→DELAY` knob on `dsp/reverb_server.asm` (the confirmed-dead `$d`/MONO
   slot) and `→VERB` WET + DRY knobs on `dsp/delay_server.asm` (Mechanism and
   Cross-bus sends sections above). Both dry taps land exact, hand-derivable
   Q1.23 values in the other bus's accumulator; the wet tap's nonzero onset
   lines up with DELAY SERVER's own TIME knob to the sample, confirming it
   reads the delay engine's real state.
6. ~~ColdFire menu integration~~ **done, verified against the real
   decompiled chooser functions, not flashed** — `tools/build_menu.py`
   replaces FX2's chooser with exactly DELAY SERVER / REVERB SERVER / SEND,
   each a fresh cloned descriptor under a new id (Menu and slot layout
   section above). `tools/verify_menu.py` confirms the five tables agree
   with each other and with what `FUN_40052474`/`FUN_4005996c` actually read
   (decompiled via `tools/GhidraMenuFuncs.java`), and that FX1's own tables
   and every donor's own descriptor bytes are untouched.
7. ~~DSP code placement + dispatch~~ **done, emulator-verified (payload A;
   payload B checked statically), not flashed** — `tools/build_bus.py`
   combines task 11's menu tables with placing the three servers' own
   assembled code in real P memory (originally SEND on CHORUS, DELAY SERVER
   on PLATE REV, REVERB SERVER on SPRING+DARK; **since v98 all three pack
   into PLATE+SPRING+DARK and CHORUS is given back**) and wiring
   `X:0x215`/`X:0x235` for ids `0x01`/`0x02`/`0x03`, both payloads. Donor ids
   are repointed to the same null stub `tools/build_dspprobe.py` already
   proved silent on hardware, not to the new servers, so FX1 selecting a
   donor by name can never collide with the hardcoded-Y-base design (Menu
   and slot layout section above has the full reasoning). Also closed the
   payload-B Y-literal gap task 9/10 had left open. `out/mainos_bus.bin` is
   the first image in this project carrying a complete, dispatched,
   three-entry bus — still nothing flashed.

Next, if this goes ahead for real: a hardware flash of `out/mainos_bus.bin`,
one variable at a time as ever — first confirm the menu itself renders and
selects correctly (the one thing no emulator here can check), then confirm
each of the three roles produces the expected audio on a real unit.

Same discipline as the rest of this project: one variable per flash,
emulator-clean before hardware, bit-identical diffs where nothing should
have changed.
