# Two-track freeze — SOLVED AND CONFIRMED ON HARDWARE (2 Aug)

**The cause.** v46/v50's phase load: `move x:(r7+$83),a` then `and #$7ff`.
On the FIRST call after enable, $83 holds leftover garbage. `and` cleans
**A1 only** — garbage with **bit 23 set** sign-extends A2 = $ff, the
accumulator reads as a huge negative, and every subsequent `move a,rN`
goes through the **limiter and saturates to $800000**. `move r1,a`
re-poisons A2 each block, so every "masked" address derivation saturates
again — and the first delay-line access lands at **Y:0x800000**: off-chip,
unmapped, the external bus waits forever. Machine frozen, sequencer on
step one.

Why two tracks: track 1's state page leftover at X:0x6283 happened to be
bit-23-clear; track 2's at X:0x6583 was not. Deterministic per project —
which made it look structural for fifty builds. Why the emulator never
saw it: `-dirty` fills **Y only**; the X state pages stayed zero, so the
load was always clean.

**Reproduced**: poisoning the second instance's $83 with bit-23-set
garbage in the harness makes v50 emit exactly the saturated accesses
(750 hits at Y:0x800000 in 5 blocks). **Fixed**: `dsp/reverb55.asm` =
v50 + four instructions — the `move a1,x0 / move x0,a` A2-clean (v50's
own LFO idiom, "extract without saturating on A2") after both masked $83
loads. Same poison: zero saturated accesses, guard clean.

The rule for the standing-rules list: **`and` masks A1 only. Any
persistent word that can hold garbage and feeds an address register must
be A2-cleaned after masking, or the limiter will saturate the pointer.**

## READY TO FLASH: `dsp/reverb57.asm` / `out/OCTATRACK_V57.bin` — run the body on BOTH calls

**v56's hardware result rewrote the "control call" one final time.** v56
played clean after its warm-up — until the first trig, at which point the
static started, immediately and permanently (2 bars then trig → static at
bar 3; 4 bars then trig → static at bar 5). No freeze on two tracks;
knobs fine. Decoded against stageprobe4's discovery and confirmed in the
dispatcher listing (P:0x4b8..0x4d7):

* the a=0 call is **not a control call. It is the FIRST SUB-BLOCK**:
  frames [0,split) of the same 16-frame buffer at r0=0 with **n7=split**,
  made ONLY when the track's split is nonzero. The a=1 call always
  follows with n7=16-split, r0=split*2. At split=0 (a track that has
  never trig'd) the first call is skipped — which is why "rts on a=0"
  ever seemed to work.
* every trig sets the split to its landing offset inside the block and it
  **persists until the next trig**. So from the first trig onward, v56's
  a=0 rts drops frames [0,split) from the tank's input and leaves the wet
  absent from those frames — a gap train at 2.76 kHz block rate cut into
  a continuous tail. That is the "static after a trig".

v57 = v56 + run the body on both calls (stock DARK does the same; its
a=0 `beq $172e` skips only the warm-up bump). Everything already
re-derives from $83 per call and saves phase/damping state per call, so
the sub-blocks are sample-continuous by construction. The only
once-per-block state, the LFO advance, now gates on the a flag (the flag
is stashed at entry in $14; both calls USE the advanced value so the
sub-blocks agree). The warm-up counter deliberately counts calls — under
a nonzero split it just warms in 128 blocks instead of 256.

928 words, 46 clear. **HARDWARE CONFIRMED: the trig static is gone.**
Flashed, played, trigged — "sounds good". Items 1 and 3 are closed.

⚠️ **The emulator claim originally written here was WRONG and is
retracted**: "bit-identical at split 0, 5 and 11" was measured against a
STALE harness binary that ignored `-split` entirely (see the harness
note below — the build compiles the vendored copy, not `tools/`). Every
`-split` run in that session was really the legacy shape, so the three
configs were trivially identical and the comparison proved nothing.
Re-measured with a correct binary, **v57 is NOT split-invariant**: at
split 0 the impulse onset is block 46, at split 5 and 11 it is block 28
(those two agree with each other exactly), 4797 of 6000 samples differ,
max |diff| 0x2475d (~0.0018 FS), and the diffs are spread evenly across
all in-block positions rather than clustering at the sub-block boundary.
The internal state is provably identical either way — traced $83, $3e,
$30 and n5 per block, phase advances +15/block in both modes — so it is
NOT the engine running twice. **Unexplained; the top open item.** It did
not stop the build sounding right on hardware, but it is a real
discrepancy in a build that is supposed to be split-continuous, and it
must be understood before it is trusted.

## v56 (flashed): warm-up VERIFIED, then the trig static named the real bug

v56's warm-up worked as designed — clean wash at first enable, no
laddering static, no freeze on two tracks, knobs fine. The remaining
static proved to be trig-keyed (see v57 above): the a=0 sub-block call
was being rts'd. The warm-up machinery carries into v57 unchanged.

Audio-quality item 1, built and emulator-validated. v56 = v55 + the
warm-up that kills the "laddering static": the lines hold boot garbage
and the tank recirculates it (confirmed in the emulator — v55 with
`-dirty` lines outputs a full-scale-ish garbage wash from block 0,
every output sample nonzero, peak $24a1cc, before any input arrives).

The shape is stock DARK's own (P:0x1718–0x172c), adapted: stock counts
blocks in $83 to 0x100 with $82 as the warmed flag, but our $83 already
holds the tank phase, so the counter lives in **$82, tagged**
($2c0000 | count) — tagged because init cannot be the reset point (the
dispatcher re-invokes init most blocks) and $82 holds garbage on the
first call; stageprobe4 proved the tagged-counter idiom stable. While
warming (256 audio calls ≈ 1.5 s): zero 56 words of the 0x3800-word
allocation per block (256×56 covers all of it), zero the LFO/damping
state block, stay completely DRY. Then the engine runs, forever. The tag
field and the count are each masked AND A2-cleaned before use — the
count feeds the zero pointer, so the standing rule applies.

925 words, 49 clear of PLATE's helper. Emulator, `-inst 2 -r7 2,5
-guard 16384 -dirty`, both instances' $82/$83 poisoned with bit-23-set
garbage: no hang, guard clean; output **bit-silent** through the whole
warm-up despite garbage-filled lines, then a clean 300-block tail from
an impulse fed after warm-up; an impulse fed DURING warm-up passes
through exactly dry (2 nonzero samples, no tail).

Run protocol: flash, enable on one track, play. Expect ~1.5 s of dry
after first enabling the effect, then the wash — CLEAN, for the first
time, no laddering static. Then two tracks as always (the warm-up path
touches only proven slots and its own buffer, but two-track confirmation
stays the ritual). Knobs after warm-up: TIME/HI/MIX as in v55.

* **static gone, wash audible** → item 1 closed; next is item 2 below.
* **static persists after the dry warm-up window** → the garbage is not
  (only) boot leftovers in the lines — something writes them while
  running, and the phase-step mismatch noted at v52 (grafts stepped 32
  vs 16 written frames) deserves a re-check against v56's real phase.

## THE KNOBS DO NOT MATCH THEIR LABELS — measured 2 Aug

Asked "what are the HP and LP knobs doing?", because they were barely
audible. They are barely audible because **one of them does nothing at
all and the other is secretly the LFO depth.** We inherited DARK REV's
descriptor, so the UI shows DARK REV's parameter names while the DSP
code reads whatever slot it likes. Names read straight out of the
descriptor at `0x400d58b8` (6-byte stride from E+0x4e):

| knob | UI label | slot | what our code actually does with it |
|---|---|---|---|
| 1 | TIME | +$0 | TIME (feedback) — **matches** |
| 2 | SHVG | +$1 | HI / high-cut damping coefficient |
| 3 | SHVF | +$2 | SIZE (scales all four tap lengths) |
| 4 | **HP** | +$3 | **nothing — never read** |
| 5 | **LP** | +$4 | MOD — LFO modulation depth |
| 6 | MIX | +$5 | MIX — **matches** |
| p2 | PRE | +$c | PRE — **matches as of v59** (v58 read $e and was knob-deaf) |
| p2 | ? | +$b | WIDTH — **suspect: stock never reads $b** |
| p2 | ? | +$d | RATE — **suspect: stock never reads $d** |
| p2 | flag | +$e | nothing now; stock uses it as a `btst #$8` flag |

Stock DARK reads only `$0..$5`, `$c` and `$e`. Everything else on page 2
is likely host-side (routing/balance) and may read as a constant to the
DSP — so **WIDTH and RATE are probably dead knobs too**, and the remap
should verify each slot against stock's reads before trusting it.

So HP is a dead knob, and LP is a subtle chorus depth — exactly the
reported symptom. The fix is free (no ColdFire work, no descriptor
edit): change which `x:(r6+N)` slots the DSP reads so the behaviour
lands under the right names. The obvious assignment, since a one-pole in
the feedback path IS a low-pass: **LP (+$4) → the high-cut damping**
(currently on SHVG), and give HP (+$3) a real high-pass on the wet, or
park SIZE/MOD there. TIME and MIX already match and must not move.

## NEXT — the audio-quality track, remaining

2. **ON THE CARD NOW: `dsp/reverb59.asm` / `out/OCTATRACK_V59.bin`** —
   the pre-delay, on the RIGHT PARAMETER SLOT.

   v58 flashed and PRE was inaudible and did not respond to the knob.
   The pre-delay code was fine; **the slot was wrong.** Read from stock
   DARK's own disassembly rather than guessed:

   * **`$e` is a FLAG word.** Stock does `move x:(r6+$e),a / btst #$8,a`
     and branches (P:0x173c, P:0x1a0d). A knob arrives as value<<16, so
     bit 8 is always clear, and `asr #$c` of it is 0 — a one-sample
     pre-delay, forever, no matter where the knob is. Exactly the
     reported symptom.
   * **`$c` is stock's PRE**, and its code at P:0x17d4 is the same
     design as ours: mask the knob field (`and #>$7f0000`), scale it
     (`mpy #$7f0 / add #$10` ≈ v*16+16, max 2031 — our v*16, max 2032,
     is the same ramp), `m5 = $7ff` for a 2048-word modulo buffer, back
     a pointer up by the offset, read delayed / write input, persist the
     pointer. Only the slot was ever wrong.

   The old note in `dsp_host.cpp` — "index 9 -> +$e (knob PRE)", from
   `pagemap_probe` — is WRONG for DARK REV and has been corrected there.
   **Stock's own reads are the authority on slot meaning; the probe was
   not.** Stock reads only `$0..$5, $c, $e`, which also means our WIDTH
   (`$b`) and RATE (`$d`) may be dead knobs — check them during the
   remap.

   v59 = v58 + two instructions (diff-verified): the read moves `$e`→`$c`
   and gains stock's `and #>$7f0000` mask, since the slot can carry bits
   outside the knob field. 942 words, 32 clear. Emulator: wet onset
   moves block 47 → 115 → 182 as PRE goes 0 → 64 → 127, guard clean at
   two instances; sweeping the OLD slot `$e` now changes nothing.

   v58 (superseded) — v57 + exactly two deltas (diff-verified):
   `m5` back to `$7ff` in the SIZE section, and v46's seven loop-body
   instructions restored. 940 words, 34 clear. $30 is re-derived per
   call from $83 + the pre-delay base (already A2-cleaned), so it is
   split-continuous by the same construction as everything else.
   Emulator: identical output at split 0 vs 5 at PRE=0/64/127, guard
   clean, and PRE demonstrably live — impulse onset moves block
   47 → 115 → 182 as PRE goes 0 → 64 → 127.

   Run protocol: flash, one track, play something percussive with MIX
   well up (a 46 ms shift is easy to miss on sustained material), and
   sweep PRE end to end. Then two tracks as always.
   * **PRE sweeps the gap before the wash** → the audio-quality track is
     done bar tuning; next is the knob remap.
   * **PRE still does nothing** → the slot is right (stock's own code
     proves it), so suspect the loop body: check `n5` and `$30` reach
     it, and that `m5` really is `$7ff` at the pre-delay access.
   * **anything freezes** → the modulo theory gets a second life after
     all, and `m5 = $7ff` is the only non-linear M register in the build.
3. **Then the knob remap** (table above), decided 2 Aug: LP → the
   high-cut damping, and HP → either a NEW one-pole high-pass on the wet
   (~25-30 words of the 34 clear; the musically right answer) or SIZE if
   it will not fit. TIME, MIX and PRE already match and must not move.
4. **Then tuning.**

## OPEN: the two-instance split divergence (emulator only)

Not a shipping blocker — hardware sounds right — but unexplained, and
this project does not leave those lying. Narrowed on 2 Aug:

* v57 at **one** instance: output identical at split 0 and split 5.
* v57 at **two** instances: instance 0's output DIFFERS between split 0
  and split 5, from block 28, ~80% of samples, max |diff| 0x2475d.
* split 5 and split 11 agree with each other **exactly** — so it depends
  on whether a second call happens, not where the boundary falls.
* adding a second instance with NO split changes nothing.
* instance 0's r7 state is bit-identical block for block ($82/$83/$3e/
  $30/n5 all traced), and the guard reports no cross-buffer writes.

So it needs two instances AND the extra call, while leaving instance 0's
own state and buffers provably untouched. That combination points at
**register carryover between instances in the harness** — something read
before it is written, holding instance 1's leftovers instead of instance
0's — rather than an engine fault. The harness does not reset x0/x1/y0/
y1/b/r1-r5/n0-n6/m0-m5 between instances; the effect is believed to
re-derive all of them, and finding the one it does not is the next step.
v58 does NOT show the divergence, which is itself a clue: the pre-delay
adds the only read of $30 in the loop.

Rules that must survive into any new build: the A2-clean after every
masked load that feeds an address register; check the builder's word
count (974 limit) and the assembler's exit status; emulator `-dirty`
fills Y only — poison X state words by appending records to the .mem
(see the v50/v55 poison test) when garbage-sensitivity matters.

Below, the investigation as it unfolded — kept because the probes,
harness fixes and ABI corrections along the way are permanently useful.

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

**Result: FROZE — which forced the a=1-side re-read that found it.** See
the SOLVED section at the top: the phase load's A2 pollution, the
limiter, Y:0x800000. The probes all survived because the tag check
laundered $83 before any address was derived from it.

## v55: the fix

`dsp/reverb55.asm` / `OCTATRACK_V55.bin` — v50 + the four A2-clean
instructions. Emulator: v50+poison = 750 saturated accesses; v55+poison
= 0, guard clean, wet live. **HARDWARE CONFIRMED: two tracks, no freeze.**

Still open after the freeze closes (the audio-quality track):
* the delay lines are never cleared at init — the "laddering static" —
  stock DARK's own answer is its warm-up counter ($83!) and $82 flag:
  256 blocks of guard after init. Adopt the same shape.
* restore v46's pre-delay (dropped in v50 for the modulo theory, which
  was never the problem).
* stock DARK also runs its body on BOTH calls and redirects r0 through
  an (r7+$1a) mute check to a dummy at X:0x110 — worth matching if
  split-boundary artifacts remain audible.

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
* `+$1e` bits 8..11 are the per-track SPLIT POINT, not a block size.
  x:0x20c = split, x:0x20d = 16 - split, x:0x20e = split*2.
* **Both proc calls are audio** (P:0x4b8..0x4d7, re-read for v57): when
  split ≠ 0 the dispatcher first calls with a=0, r0=0, **n7=split** —
  frames [0,split) — then always calls with a=1, r0=split*2,
  n7=16-split. At split=0 the first call is SKIPPED and the a=1 call gets
  the whole block. The split is set by an effect change (crossfade) AND
  by **every trig** (its landing offset inside the block, persisting
  until the next trig) — so after the first trig, an effect that rts's
  the a=0 call permanently drops [0,split) from its input and output.
  The n7 handed to each call is the sub-block length; honour it.
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

* `-split N` (now also in `-inst` mode) — models the post-trig steady
  state faithfully: a=0 call with r0=buffer, n7=N, then a=1 with
  r0=buffer+2N, n7=frames−N. The definitive split test is
  bit-identical output across `-split 0/5/11`. Without `-split`, the
  legacy shape (a=0 at r0=0, n7=frames) is kept — it matches what an
  a=0-rts effect sees, but for a both-calls effect it double-runs the
  engine; use `-noctl` or `-split` for those.
* `DSP_DBG=N` env var — prints instance 0's $82/$83/$3e for the first N
  blocks; the cheap way to watch phase/warm-up/LFO advance per block.

Four things about it that cost sessions to rediscover:

* **the harness SOURCE is `tools/dsp_host/dsp_host.cpp`, but the build
  compiles `vendor/dsp56300/source/dsp_host/dsp_host.cpp`.** Copy
  tools→vendor before `make dsp_host` or you will run the old binary
  while reading the new source. (Cost half a session: a "-split" run
  that silently ignored the flag.)

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
| `dsp/reverb54.asm` (as `OCTATRACK_V54.bin`) | v50 + M epilogue on the control call. FROZE — and forced the re-read that found the real cause. |
| `dsp/reverb55.asm` (as `OCTATRACK_V55.bin`) | **THE FIX, HARDWARE CONFIRMED**: v50 + A2-clean after both $83 loads. Two tracks run. |
| `dsp/reverb56.asm` (as `OCTATRACK_V56.bin`) | v55 + the tagged $82 warm-up. **Hardware: warm-up works, clean until a trig** — the trig static exposed the a=0 sub-block bug. |
| `dsp/reverb57.asm` (as `OCTATRACK_V57.bin`) | v56 + body on BOTH calls (a=0 is the first sub-block) + LFO gated per-block. **HARDWARE CONFIRMED: trig static gone.** Emulator shows an unexplained split-dependence — see above. |
| `dsp/reverb58.asm` (as `OCTATRACK_V58.bin`) | v57 + v46's pre-delay restored. Flashed: PRE INAUDIBLE — read parameter slot $e, which is a flag word, not PRE. |
| `dsp/reverb59.asm` (as `OCTATRACK_V59.bin`) | v58 with the PRE read moved to $c (stock DARK's own pre-delay slot) + stock's knob mask. **ON THE CARD, awaiting hardware.** |
| `dsp/instprobe.asm` `dsp/ownprobe.asm` `dsp/yburn.asm` | the measurement probes, all safe to run |

`RV_DROP=` drops stages subtractively (`pre,diff,mod,size,lines`);
`RV_TANK_ADDR=modulo|computed`; `RV_LINE_LEN=` shrinks the lines.

## PRE STILL INAUDIBLE AFTER v59 — the slot probe

v59 flashed and PRE still could not be heard; the user's read was "maybe
it's me". It is probably not. Two separate things were being conflated,
and they need separating before another hopeful flash:

1. **A 46 ms pre-delay on this reverb is subtle by nature.** Pre-delay
   reads on an isolated transient with the wet well up. Against a
   running sequence with a 3-7 s tail, shifting the whole wet by 46 ms
   is close to imperceptible even when perfectly correct. "Cannot hear
   it" is a plausible outcome from a CORRECT build.
2. **There is still no positive proof the PRE knob reaches the DSP.**
   The emulator proves the pre-delay code works once a value arrives; it
   CANNOT prove which knob writes slot $c, because the harness writes
   parameters directly. That link has been inferred twice and was wrong
   once ($e). Do not infer it a third time — measure it.

**Free test first, no flash:** MIX full wet, TIME minimum, sequencer
stopped, one percussive hit, A/B PRE at 0 and 127. That strips out
everything that masks pre-delay.

**`dsp/preprobe.asm` / `out/OCTATRACK_PREPROBE.bin` settles it in one
flash.** It is v59 with the wet GAIN driven by slot $c instead of MIX
($5) — so the slot we believe is PRE controls how LOUD the reverb is,
a readout that cannot be missed. Sweep every knob on both pages:

* **the PRE knob changes reverb volume** → the mapping is right, the
  pre-delay has been working all along and is merely subtle. Go back to
  v59 and lengthen the pre-delay if more is wanted (0x800 words spare in
  the allocation ≈ 93 ms total).
* **a DIFFERENT knob changes volume** → that knob is $c; read the real
  PRE slot straight off which one moved.
* **NO knob changes volume** → $c is not knob-driven on hardware and the
  whole page-2 mapping needs a fresh probe.

MIX stops working in this build by design; it is a diagnostic, and v59
is one flash away again. 945 words, 29 clear. Emulator: slot $c = 0
gives a bit-silent wet, 32 and 127 give audible wet — the readout works.
Built with the standing A2-clean rule applied to the masked gain.

### PROBE RESULT: the PRE knob drives slot $c. Mapping CONFIRMED.

Flashed `preprobe`, swept the knobs: **the PRE knob changes the reverb
volume.** So slot $c is PRE, v59's read is correct, and the pre-delay
has been working since v59 — it is simply too subtle to hear at 46 ms
in this reverb. Not a bug, and the parameter path is now MEASURED
rather than inferred, which it never was before.

Card restored to v59.

**Why 46 ms hides here, and what it would take to fix.** The wet already
starts ~20 ms after the dry (allpasses 7-21 ms, then the tank taps), and
it is a diffuse wash rather than a sharp onset, so shifting the whole
thing by 46 ms reads as a mild spaciousness change, not an obvious gap —
especially against a running sequence with a 3-7 s tail.

Doubling it to ~93 ms is NOT a two-instruction change, and the reason is
worth writing down: **the pre-delay pointer $30 is re-derived every call
as `pre_base + (phase & $7ff)`, and that phase is the TANK phase, masked
to 2048.** So the buffer cannot exceed 2048 words while the pointer is
derived that way, however much Y is free. Getting past it needs one of:

* **a persistent pre-delay pointer** (what stock DARK does — it keeps
  its own in r7+$2e) instead of deriving it from the tank phase. Must be
  sanitised per call (mask into the buffer) or a garbage $30 aims the
  modulo region at arbitrary Y — the exact shape of the v55 freeze.
* **arithmetic addressing** with a power-of-2 mask instead of modulo,
  which also drops the only non-linear M register. Needs a 4096-word
  buffer, i.e. base+0x3000..0x3fff — which leaves nowhere for the 5-word
  state block at base+0x3800. Freeing it means either moving the LFO and
  damping state into r7 (persistence there is now well evidenced: $82
  and $83 both hold), or shrinking allpass 3 to 512 words (its tap is
  331, so it fits) and parking the state in the freed 0x2e00 region.

Either way it is ~20-30 instructions a sample and 30+ words against 32
clear — tight enough that it wants its own build and its own flash, not
a bolt-on. **Weigh it against the knob remap, which is worth more per
flash**: HP is dead, LP is the LFO depth, and WIDTH ($b) and RATE ($d)
are probably dead too since stock never reads those slots.

## CODE SPACE: the branch scan, and 974 -> 2037 or 2724 words

Ran the inbound-reference scan over both payloads. **First, a correction
to the module identities** — the 1063-word module adjacent to DARK is
**SPRING REV, not PLATE**. Confirmed from the dispatch table at X:0x215:

| id | effect | module | words |
|---|---|---|---|
| 0x14 | PLATE REV | P:0x1000 (B: 0xdc0) | 594 |
| 0x15 | SPRING REV | P:0x1252 (B: 0x1012) | 1063 |
| 0x16 | **DARK REV — ours** | P:0x1679 (B: 0x1439) | 1067 |

All three are **contiguous** in both payloads: 0x1000 + 594 = 0x1252,
0x1252 + 1063 = 0x1679. That is 2724 words of contiguous P.

**Every reference into these modules from outside, payload A:**

| into | branches in | from |
|---|---|---|
| PLATE | **0** | — |
| SPRING | 3 (`jsr` -> 0x1586) | **stock DARK, all three** |
| DARK | 1 (`jsr` -> 0x1a47 = +974) | PLATE |

Address-sized immediates were checked too and are all false positives:
PLATE's `$19c0/$1a00/$1a80/$1b00/$1c00` are its **Y** delay-line bases
(each is `move #>$x,a / add x0,a` against the instance base — our own
idiom), and the `#>$1000`s are arithmetic constants. Only the `jsr`s are
real.

**This also explains the old "vacating SPRING hung the DSP".** SPRING's
only inbound callers are stock DARK — and that attempt vacated SPRING
while stock DARK was still live, so DARK's `jsr 0x1586` landed in the
new code. **We have since replaced DARK entirely and our reverb never
calls 0x1586, so that dependency no longer exists.** The old warning in
the standing rules is now obsolete for SPRING specifically.

### The options

| take | contiguous words | costs | notes |
|---|---|---|---|
| nothing (today) | **974** | — | capped by PLATE's `jsr` to DARK+974 |
| + SPRING | **2037** (0x1252..0x1a46) | SPRING REV | must still preserve the helper at DARK+974 |
| + SPRING + PLATE | **2724** (0x1000..0x1aa3) | SPRING + PLATE REV | PLATE is the helper's only caller, so +974 cap disappears too |

Builder work either way: our blob must be split across the separate
module RECORDS (each has its own load address), and the vacated effects'
dispatch entries at X:0x215/X:0x235 must be repointed — SPRING's init
would otherwise land on our code at a wrong offset. `build_reverb.py`
already patches those tables, so it is a modest change. Pointing a
vacated id at our own init/proc makes selecting it simply run the
reverb, which is a harmless outcome.

## Blackhole: no pitch shifter (asked 2 Aug)

Blackhole is a reverb with delay-line modulation, not a pitch shifter.
Mod Depth/Rate sweep the taps, which Doppler-detunes — which is exactly
what our two interpolated modulated lines already do. The octave-up
"shimmer" people associate with big Eventide reverbs is a DIFFERENT
algorithm family (Eventide's own ShimmerVerb, Valhalla Shimmer, Strymon
Shimmer mode), which feeds a pitch shifter into the regeneration path.
Blackhole's character comes from Gravity (decay-envelope inversion),
very long feedback and heavy modulation instead.

So the mechanism we have IS Blackhole's. Adding true shimmer would be a
deliberate move to a different effect: an octave-up needs a second read
pointer at double rate with a crossfaded window, ~25-40 instructions a
sample plus state. Cycles are available (~135-165 used against ~1080/DSP
proven); it is CODE SPACE that decides, which is what the scan above is
about.

## SPRING TAKEN: 974 -> 2037 words. ON THE CARD as `OCTATRACK_V60.bin`

Decided and done. `tools/build_reverb.py` now assembles the blob at
**SPRING's** address and lets it run straight through into DARK's, since
the three reverb modules are contiguous:

    PLATE   P:0x1000 (B 0x0dc0)   594 words   left alone
    SPRING  P:0x1252 (B 0x1012)  1063 words   TAKEN
    DARK    P:0x1679 (B 0x1439)  1067 words   front 974 available, unused so far

**Budget is now 2037 words** (SPRING 1063 + DARK's front 974). v59's code
is 942, so **1095 words are clear** where there were 32.

Mechanics, all enforced by the builder:
* the modules are separate RECORDS with their own load addresses, so the
  blob is split — first 1063 words into SPRING's record, the rest into
  DARK's. At 942 words it currently all fits in SPRING and DARK's module
  is left completely untouched.
* the builder asserts SPRING+1063 == DARK and that SPRING's record really
  is 1063 words, and refuses any blob over 2037.
* **SPRING's dispatch entries are repointed at our init/proc**, so
  selecting SPRING REV runs the reverb rather than jumping into the
  middle of our code. Both ids (0x15 SPRING, 0x16 DARK) now run it.

Verified before flashing:
* PLATE's module UNTOUCHED, DARK's module UNTOUCHED, and the helper at
  DARK+974 **byte-identical to stock** in both payloads (checked
  directly against the stock image, not assumed).
* Emulator at the new address: two instances, poisoned $82/$83, dirty Y,
  split 5 — no hang, guard clean, and PRE still live (onset block
  47 / 115 / 182 at PRE 0 / 64 / 127), matching v59 exactly.

`OCTATRACK_V60.bin` is **v59's code, relocated — no audio change is
intended.** It is a structural verification flash, deliberately not
bundled with a feature so a failure is unambiguous.

Test protocol:
1. the reverb still sounds like v59 on DARK REV, one track then two;
2. **PLATE REV still works** — it is the one effect that reaches into
   our neighbourhood, via the helper at DARK+974;
3. SPRING REV now runs the reverb instead of a spring (or at minimum
   does not hang);
4. CHORUS still works, as the usual bystander check.

If all four hold, the code budget is 2.1x and the sound-design work can
finally start: LO on knob 4 (the slot `gen_reverb.py` always reserved
for it), Gravity, and a tank rebalance for size. PLATE's 594 words remain
available as a second step — it has NO inbound branches at all — if
shimmer or anything else needs them.
