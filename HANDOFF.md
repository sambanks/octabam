# Two-track freeze — state of the investigation

**Symptom.** The reverb works on one track and sounds right. The moment it is
enabled on a second track the machine freezes, sequencer stuck on step one,
regardless of knob positions and regardless of whether the second track is
playing.

**Not solved.** Sixteen builds, zero correct hypotheses. Everything below is
either measured on hardware or read out of the dispatcher listing.

## The one build that survives two tracks

`dsp/stageprobe.asm` — never freezes on two tracks. It escalates every ~3 s:

| stage | what runs |
|---|---|
| 0 | `rts`, nothing at all |
| 1 | recover base from the stash, write 4 r7 slots |
| 2 | load and save the state block at base+0x3800 |
| 3 | read all four delay lines every sample |
| 4 | write all four delay lines every sample |

Stage 4 is 8 Y accesses a sample per instance and it survives. Build up from
this, not down from the reverb — every attempt to subtract from a working
reverb broke something else.

> **CAVEAT (2 Aug):** this probe's counter lived in $83 unprotected and it
> had no audible readout, so whether the stages actually escalated on
> hardware was never verified — only "never froze" was. (v4 later proved
> $83 IS stable, which restores confidence, but the attribution was still
> never observed directly; v4's audible ladder supersedes this probe.)

## THE AXES ARE ELIMINATED (stageprobe4, two tracks, 2 Aug)

Both instances climbed the ladder **audibly, stage by stage,** and nothing
froze — the first two-track result with proof the load actually escalated.
Eliminated for two simultaneous instances, in one verified run: **audio
buffer access, parameter reads, Y traffic at 36/sample each (72 across the
pair, double v50's need), and ~450 instructions/sample across the pair.**

The freeze is not a rate. It is a SHAPE — one of the four things v50 does
that raw traffic does not: the scattered tap reads, the tank's write-behind
pattern, the allpass read-modify-write, or the LFO-modulated interpolated
reads. `dsp/stageprobe5.asm` staged exactly those.

**And the shapes are eliminated too (stageprobe5, EIGHT tracks, 2 Aug).**
Every instance climbed the ladder, nothing froze — and the stages are
cumulative, so stage 7 ran all four shapes AT ONCE on four instances per
DSP (~1080 instr/sample per DSP, well past cycleburn's "ceiling", which was
therefore also conservative). Every access pattern the reverb needs is
survivable, individually and combined, at 4× the instance count that kills
v50. What remains between the probe and v50 is not WHAT memory is touched
but HOW — the register idioms. `dsp/stageprobe6.asm` stages those:
the loop-carried (r1)+ phase pointer, the dead per-block n1/n4/n5 writes,
the X dataflow density (one-poles, Hadamard, feedback mpy chain), feedback
writes at the carried phase, then everything combined with v5's shapes.

**And the idioms are eliminated too (stageprobe6, 2 Aug: no freeze).** Every
component of the reverb — rates, shapes, register idioms — is now cleared.
The one untested thing left is v50 ITSELF: its exact instruction stream.

## stageprobe7 (flashed: two tracks, NO FREEZE, engine verified live)

v50's ENTIRE ENGINE, verbatim, on a minimal ladder scaffold. Verified graft:
550 instructions diffed against reverb50.asm — the only deviations are the
documented five (the a-gate head replaced by the scaffold's, two phase reads
$83→$1a since $83 is the counter and the phase is derived count<<4, the
dry-bypass labels, and the now-pointless phase save dropped). r0 is stashed
at entry and restored before the engine because the buzz loop walks it. The
engine freely clobbers all scaffold slots by design — everything re-derives
from $83 each call, and the engine runs strictly after the last scaffold
read. 970 words, 4 clear of PLATE's helper.

Ladder: stage 0 silence, stage 1 buzz at −12, stage 2+ buzz at −18 AND the
engine. The buzz excites the reverb, so a ringing tail behind the tone is
the engine audibly alive.

Two tracks:
* **freezes ~3–6 s after the second track lands** → the freeze is
  reproduced ON INSTRUMENT inside a proven vehicle, and v8 bisects the
  engine body on the ladder.
* **runs, reverb tail audible** → the engine is innocent in this vehicle
  and the fault was in what surrounded it in the real build — v50's own
  entry/init/dispatch context. A genuinely new place to look.

Emulator, `-inst 2 -guard 16384`, both instances through the full engine:
clean, count exact, output live. (Trap relived while validating: the fast
variant's debug exports pushed past 974 words, the builder refused, and the
stale image nearly got "validated" — check the builder's output, always.)

**Hardware result: two tracks, no freeze, and the engine is verifiably
running** — the knobs (which feed only the engine; the buzz reads no
parameters) audibly change the output. The wash is masked by the constant
buzz (a steady tone through a reverb is nearly inaudible as reverb) and by
MIX: emulator-measured, MIX=0 gives a mathematically bare square (2 distinct
sample values) while MIX=64 gives ~6,000 distinct values at 3× the peak.

**v50's engine is innocent.** The remaining deltas between surviving v7 and
freezing v50, exhaustively: (1) v7's ladder held the engine silent through
the first ~6 s — it SLEPT THROUGH THE ENABLE TRANSITION, and the original
symptom was always "freezes THE MOMENT it is enabled on a second track";
(2) the buzz input; (3) the r0 stash/restore; (4) derived vs persisted
phase; (5) the entry head. Delta (1) explains the symptom's timing exactly.

## stageprobe8 (flashed: NO FREEZE — the enable window is innocent too)

v7 with ONE INSTRUCTION changed (diff-verified): the engine's stage gate
threshold is 0, so the engine runs from the very first proc call — straight
through the enable window. Buzz unchanged.

* **freezes the moment track 2 is enabled** → FOUND IT: the engine is fine,
  running it during the enable window is fatal. v9 = v50 + a warm-up guard
  (dry for the first ~64 blocks after init), no buzz, no ladder — the
  shippable reverb.
* **still no freeze** → the enable window is innocent and the remaining
  deltas (buzz, r0 handling, phase, head) get one flash each.

**Result: still no freeze.** v8 contains v50's engine as a strict superset,
runs it from the first call through the enable window on two tracks, and
does not die. The four remaining deltas are all semantically inert — there
is no longer a good hypothesis for why v50 freezes and v8 does not.

## the control (flashed): v50 STILL FREEZES — the differential is real

When every remaining explanation looks impossible, re-verify the
phenomenon. Every v50 freeze predates today: different session, different
project state, sixteen build-generations ago — and several historical
"freezes" were later traced to since-fixed self-inflicted bugs. Nobody has
flashed actual v50 today. This is `dsp/reverb50.asm` rebuilt unchanged
(445,152 bytes — the same artifact as the NOPREMOD.bin that was on the
card this morning). Two tracks, the canonical gesture:

* **freezes** → the differential is real and current: v8-vs-v50 differ by
  exactly {buzz input, r0 stash/restore, derived vs persisted phase, entry
  head}, and each gets one flash. Expect the freeze; power-cycle recovery
  as usual.
* **does not freeze** → the "two-track freeze" no longer exists in
  today's environment — it was keyed to something historical (an old
  project state, an interaction since perturbed) — and v46/v50 may simply
  be shippable now. Then flash v46 (the good-sounding build) and enjoy it,
  while the archaeology becomes optional.

**Result: track 1 runs; track 2 freezes it IMMEDIATELY.** Reproduced
today, in this project. The v8-vs-v50 differential is real and current.

Also observed, and it reframes the morning: v50 on track 1 — the
unmodified reverb, no ladder, no buzz — STILL sounds like "laddering
static". The v2/v3 "cycling static" was never the probes' defect, and "I
never really heard the wash" now has a candidate cause: the delay lines
are NEVER CLEARED. init zeroes nothing; the tank recirculates whatever
garbage the 0x3800-word allocation held, the LFO swells it, and the wash
drowns. A separate bug from the freeze; the fix is clearing the lines at
init (or a dry warm-up that writes zeros). Do not chase it before the
freeze is closed.

## v51 (flashed: FROZE) — time alone is not the protection

The last structural delta standing, isolated across the whole build
history:

| build class | a=0 control call | two tracks |
|---|---|---|
| stock DARK REV | reads its parameter slots (~dozens of instr) | fine |
| every surviving stageprobe (v1–v8) | ~60 instr of scaffold, every call | fine |
| pre-v44 (ignored the flag) | ran the ENGINE against r0=0 — destructive | froze |
| v44/v46/v50 (honoured the flag) | `rts` in 3 instructions | froze |

Everything that idles ~60 instructions on the control call survives;
everything that returns instantly (or corrupts) freezes. stageprobe7/8
carry THIS ENGINE and survive — the engine is not the difference; the
control call is. v51 = v50 + `do #60 / nop` before the a=0 rts. One
change, diff-verified.

* **no freeze** → the two-track freeze was a CONTROL-CALL TIMING contract
  all along, the fix is ~4 words, and v51 IS the reverb (modulo the
  garbage-line cleanup above and v46's pre-delay restoration).
* **freezes** → time alone is not the protection and the scaffold's a=0
  X-writes ($83 et al.) are; v52 adds those.

Emulator, -inst 2 -guard 16384: clean, wet output live.

**Result: FROZE.** A 60-instruction nop burn on the control call does not
protect. It is the TRAFFIC, not the time. And the M-epilogue candidate is
excluded by stock behaviour (stock effects do not touch M registers on the
control call and survive). What stock does that v50 does not is exactly
one thing: **the control call latches parameters into r7 state.**

## v52 (flashed: FROZE) — param latching is not the protection either

v50 with the control call doing what stock DARK does: read the eight
parameter slots, store them into r7 ($20..$27 — slots the audio call
freely overwrites with its own derivations, so the reverb is unchanged).
Diff-verified: only the a=0 latch differs from v50.

* **no freeze** → the contract is found: the control call must touch the
  r7 block (or the param slots specifically). v52 IS the reverb; what
  remains is audio quality (clear the garbage lines, restore the
  pre-delay).
* **freezes** → the protection is elsewhere in the scaffold's per-call
  behaviour, and the search flips: strip v8 (which survives) toward v50
  piece by piece — buzz stage out first, then the counter — one flash
  each, from the surviving side.

**Result: FROZE. And track 1 still ladders static** — the audio bug is the
engine's own (uncleared lines; plus the grafts' derived phase steps
32/block against 16 written frames, scrambling the tank — both on the
audio-fix list, after the freeze).

Two guessed protections dead (v51 time, v52 param latch). No more
guessing: **strip v8 toward v50 from the surviving side** — remove
scaffold elements group by group; the strip that freezes names the
protection. Deterministic.

## stageprobe9 (flashed: NO FREEZE) — the audio scaffold was not the protection

v8 minus the entire audio-side scaffold: no buzz loop, no gain ladder, no
click override. Kept, to strip next: the entry stores, the counter/tag
machinery ($83 written on EVERY call including a=0), the derived phase in
$1a (v50 instead persists phase into $83 at the END of each audio call —
the last a=1-side delta, tested by the next strip), the r0 restore (now a
no-op), the M epilogue, the engine gate shape.

* **survives** → the protection is among the kept items; v10 strips the
  counter and reverts the phase to v50's $83 persistence — if THAT
  freezes, the killer is the counter/derived-phase group, and one more
  build splits it.
* **freezes** → the buzz stage's audio writes were the protection —
  astonishing, and immediately actionable.

No buzz in this build: the engine is the only audio; knobs prove it runs.
908 words. Emulator: guard clean, wet live.

**Result: no freeze.** The protection is among the kept items, and sorting
every build's fate by what it leaves in $83 collapses the whole history
into one table:

| leaves in $83 | builds | two tracks |
|---|---|---|
| huge tagged values ($2c0000+) | every surviving probe | fine |
| bare phase, 0..0x7ff forever | v44 v46 v50 v51 v52 | FREEZE |
| never writes it | stock effects | fine |

"$83 persists" only ever proved the host does not WRITE it — not that it
does not READ it. Stock layouts avoiding the offset is what a host-owned
field looks like. A small value there reads as valid (an index, a
pointer); a huge one falls out of range. Would also explain the two-track
requirement: the reading host path may only matter with two live FX2
instances.

## v53 (flashed: FROZE) — the $83 value is not the mechanism

v50 + TWO INSTRUCTIONS, diff-verified: the phase save becomes
$2c0000 | phase. The load path already masks $7ff, so the reverb is
bit-identical in behaviour. The test doubles as the fix.

* **no freeze** → closed: the freeze was a small number parked in a
  host-owned word. Ship path: v53 + clear the delay lines at init (the
  "laddering static") + restore v46's pre-delay.
* **freezes** → the value story is dead; resume the strip series from v9
  (strip the counter next, phase back to bare $83 — isolating the
  remaining kept items one at a time).

**Result: FROZE. And then the disassembly rewrote two assumptions at
once** (payload_A.asm, stock DARK at P:0x1679):

* the ONLY code in payload A touching (r7+$83) is stock DARK itself, at
  P:0x1718/0x1723/0x172a. The host NEVER references $83. Every
  host-reads-$83 theory is dead.
* **$83 is stock DARK's own WARM-UP COUNTER**: incremented per audio call
  until 0x100 (256 blocks ≈ 1.5 s), with **$82 as the warmed-up flag**
  (0 while warming). The stock effect has exactly the warm-up guard this
  investigation kept proposing to invent.
* **stock DARK runs its body on BOTH calls** — the old "its a=0 path only
  reads parameter slots" was a misreading of `beq func_00172e`, which
  skips only the warm-up bump. Stock also ignores the dispatcher's r0
  for its writes (r0 is redirected via an (r7+$1a) check to a dummy at
  X:0x110 — mute machinery) and saves r0/r6 to $17/$18 at entry.

## READY TO FLASH: `dsp/reverb54.asm` / `OCTATRACK_V54.bin`

Eliminated on the control call so far: time (v51), r7-write traffic
(v52), the $83 value (v53). The last untested SINGLE delta between every
survivor and every freezer: **the M-register epilogue on the a=0 exit.**
The scaffolds restore m0..m5 = $ffffff on every exit; the freezing
builds leave M untouched on a=0. v54 = v50 + exactly that, diff-verified
(six instructions).

* **no freeze** → the contract is M-restoration on the control call;
  investigate who leaves M non-linear (the host between calls?) at
  leisure — v54 is the reverb.
* **freezes** → no SINGLE a=0-side addition protects. The protection is
  a=1-side or a combination; next is the v9-side strip: v9 with the
  counter removed and the phase back to v50's $83 load/save (isolating
  the phase-LOAD-position and entry-store deltas).

## stageprobe2, hardware result: NO FREEZE — but the run is INVALID

Flashed and run on one and two tracks. Nothing froze, but one track cycled
**quiet → loud static → quiet → loud static**, which a working escalation
cannot produce. The diagnosis, from the symptom alone:

* the cycle is the **counter resetting**. $85/$86/$87 are written and read
  within the same call and cannot cause a period; the sentinel at **$82** is
  the one word that had to survive *between* calls, and only $83 was ever
  proven to. Host rewrites $82 → count restarts → the ladder replays: dry
  (quiet) → stage 1 at full gain (loud) → 6 dB steps (quiet) → reset. So
  stages 3–6 likely **never ran**, and "no freeze" cannot be banked.
* the static is the **r0 advance**: two `(r0)+n0` steps (n0=1) one data move
  apart, an idiom never before run on hardware. v46/v50 advance one frame as
  n0=2, single `(r0)+n0`, and v46 sounds right on track 1.

The guard could not have caught either: it shadows **Y and P only** — an X
write to a host-owned r7 slot is invisible to it. Audit r7 offsets by hand
against the proven set: $10..$3f (v46, clean audio on track 1) plus $83.

## stageprobe3, hardware result: the cycle SURVIVED the fix — $83 is NOT safe

v3 tagged the counter inside $83 itself, the one "proven" slot, and moved all
scratch onto slots v46 uses. One track still cycled quiet → loud static →
quiet. Gain depends only on stage, stage only on the count, so a clean run
climbs the ladder once and stays at the floor — a repeating cycle means the
count keeps getting DESTROYED — which at the time read as "the host
scrambles $83 between calls". **v4 later disproved that** (no tag failures,
ever); the real explanation was ladder replays from the user's own toggles
and power cycles, heard through split-boundary distortion (below). Kept as
written for the record of what the ripples were believed to be:

* **stageprobe v1's stage attribution is void.** Its counter sat in $83
  unprotected. If the host resets it every few seconds, v1 never escalated
  past stage 1–2, and "8 Y accesses a sample survives two tracks" was never
  demonstrated. v1 also had no audible readout, so a resetting counter was
  invisible — it only ever reported "did not freeze".
* **v46 does not contradict this.** A scrambled tank phase is a momentary
  tail glitch every few seconds, easy to miss by ear. It proves the
  scrambling is intermittent, not absent.

Separately: the static survived two scratch layouts and two r0 idioms (v3's
audio stage is v50's verbatim instructions). Stage 1 should have been clean
mono program; it was not. Amplifying x:(r0) yields noise, cause unknown — so
the probe must stop amplifying input.

Suspects for the scrambler, none yet discriminated: host writes into its own
r7 bookkeeping between calls; init re-invocation ("most blocks"); sequencer
events — pattern loop, trigs, scene/crossfader. v4 measures which.

## stageprobe4 (flashed, done — the scaffold is proven)

Same ladder, but the probe now DISCRIMINATES instead of assuming:

* the readout is a **synthesized buzz** — a square from bit 1 of the count,
  ADDED to the dry the way v46 adds wet, input never read into it. Clean buzz
  = write path fine, v2/v3's static was garbage input. Buzzing static = the
  pointer or write path itself.
* buzz **pitch measures calls per block**: ~690 Hz = the count steps once a
  block, ~1.4 kHz = twice (control + audio both run).
* a **tag-fail click**: one loud 5.8 ms block every time the tag check fails.
  The click train IS the host-reset measurement — its rhythm fingerprints the
  scrambler.
* the count **recycles at the top** (to stage 14) so the floor buzz never
  freezes into DC; the tag changed ($2c, was $5a) so a leftover v3 word fails
  on the first call.

**Run protocol, in order:**

1. One track, **sequencer STOPPED** (buzz needs no input). Clean world: one
   click, ~3 s silence, buzz in at −12 dB, five 6 dB steps (~3 s each, half
   that if two calls a block), then the floor, forever.
2. Repeating clicks with the sequencer stopped → the host resets $83 even at
   rest. Clicks only once playing → sequencer-driven; **vary the BPM** — if
   the click period scales, that is confirmation.
3. Then two tracks, as always. If it freezes, the buzz level at death is the
   stage that killed it.

Emulator (after fixing the two harness bugs below): guard clean at two
instances, count = calls exactly, buzz sign alternates per block, ladder
magnitudes exact, click fires on a scrambled $83 and clears the call after.

### v4 hardware, first session: the pitch IS a dispatcher observable

One track: a clean solid tone, stable at rest, and **every sequencer trig
changes its pitch, which then holds until the next trig**. Decoded:

* clean tone → the audio write path is fine; v2/v3's "static" was never the
  write side.
* pitch = calls per block (~689 Hz one, ~1378 Hz two, rough ~1034 three).
* trigs therefore set the per-track SPLIT (`+$1e` bits 8..11) to a value
  that **persists until the next trig** — almost certainly the trig's
  micro-timing within the block. On-grid trig → split 0 → one call → low
  tone; off-grid → split ≠ 0 → two calls → the octave.
* this rewrites the v3 static too: with split ≠ 0, v3's replace-the-audio
  stage only processed [split, 16) — the first split frames of every block
  kept raw input, and that boundary discontinuity at 2.7 kHz block rate IS
  the "static". An effect that REPLACES audio must handle split; one that
  ADDS (v46, the buzz) is immune.
* **the "$83 scrambling" claim is RETRACTED**: confirmed no clicks or pops,
  ever, playing or stopped. The tag never fails; $83 is stable. v3's
  "cycling" was the ladder replaying after the user's own toggles and power
  cycles, heard through split-boundary distortion.

Second session of answers:

* **six distinct pitches, cycling — the 7th trig repeats the 1st** — with
  every trig ON the grid (user is firm, and right: no micro-timing set).
  Theory: the beat grid does not divide the block grid. A step is a
  non-integer number of 16-frame blocks, so consecutive on-grid trigs land
  at different offsets INSIDE a block, cycling with period = the
  denominator of the fractional blocks-per-step — 6 at this tempo. The
  offset is what the host writes into split, and each split value has its
  own audible waveform. **Prediction: the cycle length changes with BPM.**
  If six survives every tempo, the theory is dead.
Third session — every pending question answered:

* **the intro ladder is real**: power cycle, listen from boot → the ladder
  runs, audibly. The stage machinery is verified on hardware.
* **the block-phase split theory is verified**: the pitch-cycle length
  changes with BPM — 80 → 2 tones, 100 → 1, 114 → 4, 120 → 1. The split is
  the trig's landing offset inside the 16-frame block, set by the tempo
  grid beating against the block grid, persisting until the next trig.
* **TWO TRACKS COMPLETED THE LADDER AND DID NOT FREEZE.** Both instances
  stepped down audibly and settled into the trig-pitch behaviour. See "THE
  AXES ARE ELIMINATED" above — this is the result the whole ladder was
  built for.

## stageprobe5 (flashed, done — eight tracks, no freeze, shapes eliminated)

The v4 scaffold (proven two-track survivable, including its readout) with
the Y ramp and instruction burn dropped — those axes are closed — and the
reverb's four remaining SHAPES staged in their place:

| stage | adds | if it dies here, the buzz was at |
|---|---|---|
| 1 | audio buzz + params (proven) | −12 dB |
| 2 | 4 reads at v50's tap offsets (481/799/1071/1315 behind the head) | −18 dB |
| 3 | + 4 writes at the write phase — the full tank pattern | −24 dB |
| 4 | + 2 allpass read-modify-writes, mpy chain between | −30 dB |
| 5 | + 2 interpolated double-reads, fixed offset | −36 dB |
| 6 | + LFO on line 1's offset — full modulated addressing | −42 dB |
| 7+ | everything, forever | floor |

~270 instructions/sample per instance at full load, ~540 across the pair —
near what v4 proved. The tank phase is derived from the count (p0 =
count<<4 masked), since $83 holds the counter; the LFO phase persists in
the state block at base+0x3800, which the scaffold already loads and saves.

**Run: both tracks, let both ladders complete, leave it running a minute.**
If it freezes, the last buzz level names the feature (table above). If it
runs forever, no single shape is the killer and the next bisect is
COMBINATIONS — most likely candidate then: the full engine's register
pressure or the wet path's second mpy chain.

Emulator, `-inst 2 -guard 16384` (the default 0x3800-word window is one
word short of the state block — v4 never tripped it only because it wrote
the state word back unchanged): clean, count exact, LFO offset wandering
791..799 as designed.

Built up from the survivor, one axis every ~3 s. Y traffic is in it, but it is
not first: two *structural* things v50 does and stageprobe never does at all are
cheaper to test, so they go ahead of the ramp.

| stage | adds | Y/sample | instr/sample |
|---|---|---|---|
| 0 | stageprobe's stage 4, verbatim | 8 | 79 |
| 1 | **AUDIO** — read/write x:(r0), walk r0 per frame | 8 | 95 |
| 2 | **PARAMS** — the eight x:(r6+n) reads v50 does | 8 | 95 |
| 3 | Y to 16 | 16 | 109 |
| 4 | Y to 24 | 24 | 121 |
| 5 | Y to 36 (twice v50's) | 36 | 137 |
| 6 | 80 instructions a sample of pure arithmetic | 36 | 223 |

Stage 1 is the one the old handoff never listed: **r0 was eliminated for the Y
buffer, never for the audio buffer.** Both instances are handed r0 = x:0x20e,
which is 0 in steady state — the same pointer.

Stage 6 closes the cycles axis *for two instances*; cycleburn only ever measured
one. 223 a sample is 446 across the pair, still under the ~806 it measured.

**Two readouts, so the stage is not timed blind.** From stage 1 the track goes
MONO, and from stage 1 it drops **6 dB per stage** (stage 2 half, stage 3 a
quarter … stage 6 −30 dB). Count the drops: the level you last heard is the
stage it died in. This matters because the counter advances once per *proc
call* — if the dispatcher makes both the control and the audio call, escalation
is ~1.5 s a stage, not 3 s. Trust the drops, not the clock.

Unlike stageprobe, the counter starts from a known point instead of from
whatever garbage the slot held: the tag check fails on garbage and resets the
count. init cannot do it — the dispatcher re-invokes init most blocks and the
counter would never leave stage 0.

**Run it on one track first** and let it pass 21 s, to prove the escalation is
harmless. Then enable both tracks in QUICK SUCCESSION — each instance counts its
own blocks, so the two escalations run offset by however long you take.

A freeze inside the first three seconds means the *baseline* broke, not that a
null effect is fatal — stageprobe already proved a null effect is not.

Emulator, `-inst 2 -guard`, all seven stages: guard clean, and the only stray
writes are the two intended base stashes at Y:0x862 / Y:0x864 — byte-identical
to what the known-good stageprobe produces.

## Eliminated, with the evidence

| ruled out | how |
|---|---|
| base delivery, the init stash | `dsp/instprobe.asm`: r7 = 0x6200/0x6500, bases 0x4000/0x8000, distinct and valid. The probe itself runs on two tracks. |
| r7 state blocks | same, plus the dispatcher advances x:0x20a three times a track |
| buffer extent | `dsp/ownprobe.asm`: every word of the 0x4000 allocation still holds that instance's own signature a block later, at every offset, both tracks |
| Y bandwidth (one instance) | `dsp/yburn.asm`: no break at 66 accesses a sample |
| cycles | v40 and v41 are both 135 instr/sample; one freezes, one does not |
| parameters reaching an address | v38: taps as compile-time constants, still froze |
| r7 slot region | v39: scratch moved into DARK REV's own $1a..$4x, still froze |
| the A mode flag | v44 honours it; still froze |
| **modulo addressing** | v50 has none anywhere, every M register linear, **still froze** |

## Dispatcher ABI, read from payload A

* `P:0x372` resets x:0x418, x:0x20a=0x6000, x:0x213=0x255, falls into the track
  loop at `P:0x385`, four iterations (x:0x418 steps 0x20 to 0x80), exits 0x53e.
  Four tracks per payload, two payloads, eight tracks.
* Per track: x:0x20a advances 0x100 three times (0x4ae, 0x4e4, 0x51e), x:0x213
  advances 1 twice (0x4d8, 0x526). Reproduces the measured r7 and bases exactly.
* `x:0x415 + t*0x20` is a track's PENDING config, `x:0x416 + t*0x20` its CURRENT.
  FX1 id at `+$1b`, FX2 id at `+$1c`, as value<<8.
* `+$1e` bits 8..11 are an effect-change SPLIT POINT, not a block size.
  x:0x20c = split, x:0x20d = 16 - split, x:0x20e = split*2.
* **Both proc calls are audio.** A block is 16 frames and it is split: the
  CURRENT effect gets [0, split) at r0=0 with a=0, the PENDING effect gets
  [split, 16) at r0=split*2 with a=1. A crossfade across an effect change. In
  steady state split is 0, the outgoing call is skipped, and the effect gets the
  whole block at r0=0.
* FX2 is handed `r6 = x:0x208 + 12`; FX1 gets +6.
* init is re-invoked whenever a slot's effect id differs from the previous
  slot's, which is most blocks — this is why "init runs more often than once".

## Harness

`tools/dsp_host/dsp_host.cpp`:

* `-inst N` — N instances with correct per-instance r7, base and audio
* `-dispatch N` — **runs the host's own dispatcher** rather than imitating it.
  Configures N tracks with the effect on FX2 and executes `P:0x372` onward.
  `-split N` models the effect-change transition. Stock DARK REV completes at
  one and two tracks, so a negative from it means something.
* `-guard [words]` — shadows Y:0x0000..0xBFFF and loaded P from before the first
  init; separates a stray write from one landing on a loaded module
* `-dirty SEED` — fill Y with garbage first; hardware does not hand out zeroed
  buffers
* It does **not** reproduce the freeze, at either instance count, steady state or
  transition. Time is the thing it cannot model.

Three things about it that cost half a session to rediscover:

* **`-dispatch N` never completes** once the context is real. It hangs at any
  block count, and it hangs identically for `stageprobe`, which is the build that
  survives on hardware — so a hang there says nothing about the effect. Use
  `-inst N`, which is what the guard section of `DSP.md` documents anyway.
* **`instructions/sample` and `-trace` cannot see inside a `do` loop.** The
  emulator's `do_exec` runs the whole loop within a single `execInterpreter`
  step, so the harness counts a 15-frame sample loop as one instruction and the
  trace jumps straight from the `do` to the epilogue. A reported "6.8
  instructions/sample" is an artifact, **not** an effect that is idling — do not
  read it as one. The guard is unaffected: it still sees every in-loop write.
* **`-proc` is per source file.** `build_reverb.py` prints the address; a stale
  one silently runs whatever bytes are at the old offset and reports a plausible
  number. Copy it from the build output every time.

Feeding it: `python3 tools/dsp_modmap.py --dumpmem A <out.mem>` reads the
hardcoded stock image, so for a patched build call `dsp_modmap.dumpmem()`
directly against `out/mainos_reverb.bin`.

Two more, found and FIXED while validating stageprobe4:

* the audio call's mode flag was set as `a.var = 1`, which is a0 = 1. The
  dispatcher's `move #$1,a` is left-aligned: a1 = $010000. Invisible to
  `tst a`, but `move a,x:..` transfers A1 — an effect that stores the flag
  and tests the copy read 0 in the harness and silently skipped its audio
  path. Now set hardware-accurately.
* `-noctl` decremented the parse index on a flag that consumes nothing, so
  the argument loop re-read it forever. The flag had hung the harness since
  the day it was added.

## Standing rules for the engine, learned by freezing the machine

* two instructions between writing r5 and using it — and they must be **data
  moves**, never M-register writes (an M load interlocks with its address
  register; this froze one track in v47)
* no M-register write inside the sample loop
* a modulo offset larger than the buffer is undefined: silent, not an error
* absolute Y scratch must sit at 0x800 or above — payload B loads modules to
  Y:0x7a4 where payload A stops at 0x794 (this was the v30/v31 hang)
* X:0x213 is only valid during init; reading it in process gives whatever the
  last init left (this was the v33 hang)
* check the generated assembly and the assembler's exit status, not the
  generator. `build_reverb.py | grep` masks a failed assemble and the emulator
  will then happily "verify" a stale image.

## Builds worth keeping

| file | what it is |
|---|---|
| `dsp/reverb46.asm` | computed tank, modulo pre-delay. **Works on track 1**, freezes on 2. The reference good build. |
| `dsp/reverb50.asm` | v46 with the pre-delay removed. No modulo anywhere. Freezes on 2 — the result that killed the modulo theory. |
| `dsp/stageprobe.asm` | the two-track survivor. Start here. |
| `dsp/stageprobe2.asm` | first build-up attempt. Hardware: no freeze but cycling noise — INVALID, wrote four unproven r7 slots. Kept as the record of why. |
| `dsp/stageprobe3.asm` | v2 on proven slots, counter tagged inside $83. Its "cycling" was misread as $83 scrambling; v4 disproved that. |
| `dsp/stageprobe4.asm` | the proven scaffold: buzz readout, click train, pitch = calls/block. Two-track ladder completed — the axes eliminator. |
| `dsp/stageprobe5.asm` | the scaffold + the four shapes. EIGHT tracks, ladders complete, no freeze — the shapes eliminator. |
| `dsp/stageprobe6.asm` | the scaffold + the register idioms. No freeze — the idioms eliminator. |
| `dsp/stageprobe7.asm` | v50's entire engine, verbatim, on the ladder. Two tracks: NO freeze, engine live. The engine's acquittal. |
| `dsp/stageprobe8.asm` | v7 with one constant changed: engine from the FIRST call. No freeze — the enable window's acquittal. |
| `dsp/reverb50.asm` (as `OCTATRACK_V50CONTROL.bin`) | the CONTROL. Flashed: still freezes on track 2, today — the differential is real. |
| `dsp/reverb51.asm` (as `OCTATRACK_V51.bin`) | v50 + a nop burn on the control call. FROZE — time is not the protection. |
| `dsp/reverb52.asm` (as `OCTATRACK_V52.bin`) | v50 + a stock-style param latch on the control call. FROZE — not the protection. |
| `dsp/stageprobe9.asm` (as `OCTATRACK_STAGES9.bin`) | v8 minus the audio scaffold. No freeze — narrowed the protection to the $83/counter group. |
| `dsp/reverb53.asm` (as `OCTATRACK_V53.bin`) | v50 + tagged phase save. FROZE — the $83 value is not the mechanism. |
| `dsp/reverb54.asm` (as `OCTATRACK_V54.bin`) | v50 + M epilogue on the control call — the last untested single delta. **The one to flash.** |
| `dsp/instprobe.asm` `dsp/ownprobe.asm` `dsp/yburn.asm` | the measurement probes, all safe to run |

`RV_DROP=` drops stages subtractively (`pre,diff,mod,size,lines`);
`RV_TANK_ADDR=modulo|computed`; `RV_LINE_LEN=` shrinks the lines.
