# Working in this repository

**Read `PLAN.md` first.** It carries the end state, the resource ledger and the
work order. `docs/XBUS.md` is the architecture record, not the plan.

The repo is organised as **modules** (`modules/<name>/manifest.py` declares one
contribution) composed into **remixes** (`remixes/<name>.py` selects a set).
`make modules` lists them, `make remix` composes one. `docs/MODULES.md` is the
contributor guide. Two consequences for working here: a module's declared
`priority` is byte-load-bearing, and the build refuses to start when two
selected modules claim the same FX2 id, cave, hook site, core-private Y word,
or the per-core FX2 buffer region.

**Modules come in kinds, and most of the traps below are a SERVER's.** An
insert (six of the ten) has no bus role, no shared-window claim, sits in both
payloads and runs on any track; it never touches the rotation, the
housekeeping election, the auto-gain, or the payload asymmetry. A server pays
all of that. Read a warning below asking which kind it applies to.

**If you change the BUILD rather than a module, prove it changed nothing:**
`scripts/refhash.sh save` on a tree you trust, then `scripts/refhash.sh check`
— 26 configurations, artifacts and build reports, bit-identical. The whole
remix refactor was done under that gate, and every module added since has
been proven not to change it.

This is a DSP effects project. The firmware reverse engineering in `docs/` is
infrastructure that makes the effects possible — it is not the deliverable.

## Build and check

```bash
make bus        # THE build (XBUS=1 SPEC=1) -> out/mainos_bus.bin
make check      # build + cycle budget + verification, no hardware needed
make render     # hear the bus locally, ~6x real time
make reverb IN=loop.wav ARGS='--wet --mode all'
```

Never claim an effect works because it assembled. `make check` is the floor.

## Traps that have already cost real work

**The assembler mis-encodes instructions, silently.** `dsp_asm` encodes
`tfr a,b` as `rnd b`, and **any `mpy` operand order it doesn't know as
`mpysu`** — found with `mpy x0,y0`, confirmed 9 Aug 2026 for `mpy x1,y1`
and `mpy x0,x1` too (23 sites in the shipping reverb are mpysu; all audited
safe because their second operand is always positive, which is the only
reason the engine works). `mpysu` treats the SECOND operand as unsigned, so
a negative multiplier there is silently corrupted. `mpy x0,y1` and
`mpy y0,x0` encode signed. Both assemble clean and do the wrong thing.
**Disassemble what you assemble** when a result surprises you — and always
for a new `mpy` whose second operand can go negative. A related family bit
us in shipping code: `cmp a,b` had encoded as `max a,b`, which updates only
the C bit while `blt` tests N^V.

**READING `a0` EXPOSES THE FRACTIONAL LEFT SHIFT THAT READING `a1` HIDES.**
`mpy` aligns the Q46 product into Q47, so `a1` is the plain fractional
product — which is why "mpy does not double here" is true, and stays true,
for every module that reads a1 (all of them until 29 Aug 2026). Read the LOW
word instead — the idiom for turning an integer product into a wrapping
ramp — and you see the RAW 48-bit content, shift included, so the effective
integer scale is **2× your multiplier**. Nimbus's grain window is one
`mpy phase,2^(23-k)` plus `abs`; written with the arithmetically obvious
`2^(24-k)` it assembled, rendered, and made a perfectly plausible granular
noise while running the window at DOUBLE RATE, which put the two grains of
each pair in phase instead of interleaving. Found by a DC gate, not by ear
and not by any existing check: two triangle windows a half period apart sum
to exactly 1, so **DC in must come back flat** — it came back with 2×-DC
ripple, and went flat (−122 dB) when the multiplier was halved. If you use
a0 for anything, pin it with a test whose arithmetic you can predict exactly.

**A logical op (`and`/`or`/`not`/`asr`-as-mask) on an accumulator leaves the
extension byte (A2/B2) STALE, and the next `move a,x:` SATURATES to full
scale.** Building a sign mask with `move a,b / asr #$17,b,b / not b` and
storing the result writes `0x7FFFFF`, not the bits you computed — the
store's limiter sees A2 inconsistent with A1's sign and clamps. This cost a
long session on the gated-reverb envelope: a branchless mask-select looked
correct and disassembled correctly but pinned the gate open, because every
masked value saturated on store. **Fix: don't hand-roll sign masks. Use the
conditional-transfer ops** — `tmi x0,a` (floor to 0 if negative), `teq x0,a`,
`tpl`/`tge` — which move a CLEAN register into the accumulator, so no A2
staleness. A plain `move #imm,reg` does NOT disturb the condition codes, so
the `sub`/`tst` that sets the flag survives to the Tcc. (This is also why the
sample loop stays branch-free: Tcc replaces the branch AND avoids the trap.)

**A Tcc pair that shares ONE compare is broken by ANY arithmetic between
them — and nothing at the second site looks wrong.** The branch-free idiom
here is `cmp`/`tst` once, then several `Tcc`s that all read the same
condition codes, relying on the fact that MOVES do not disturb them. That
holds until someone inserts real work in the middle. GRAIN's two scatter
latches (line L, line R) shared one wrap flag; adding a density gate
containing `clr b` and `tst a` between them left line R testing garbage, so
it re-latched a random read position EVERY SAMPLE instead of once per grain.
That is broadband noise, and it was audible as a hiss **on the right channel
only** — found by ear (13 Aug), not by any check, because `make check` and
the bit-identity gate were both green: the code was deterministic and every
mode still assembled. Fix: park the compare's RESULT in a scratch slot and
restore the flag with `tst` before each Tcc that needs it. **When you add
anything to a block, check what the code BELOW it assumed about the
condition codes** — the dependency is invisible at the point you edit, and
`clr`, `and`, `abs`, `tst` and every arithmetic op all set them. Same family
as the A2-staleness trap: legal instructions, correct-looking source, wrong
machine behaviour.

**`Tcc` takes a REGISTER source, never an accumulator, and `clr` takes an
accumulator, never a register.** `tpl b,a` and `clr x0` are both
InvalidInstruction — caught at assembly, which is the cheap case, but they
look plausible enough to write repeatedly. Move the value through `x0`.

**`dsp_asm` resolves labels by PREFIX, so no new label may have an existing
label as its prefix.** Adding a loop labelled `warmz2` next to the existing
`warmz` assembled to

```
do #<$40,>$13632     ; 064080 013631      (should have been 001374)
```

— `warmz`'s address `0x1363` with the leftover `2` appended. The loop branched
into hyperspace and `dsp_host` SIGSEGVed with no diagnostic. Same family as the
three above: clean assembly, wrong machine code. Found 9 Aug 2026, after three
wrong guesses (emulator memory limits, buffer alignment, a stale modulo) that
were all *reasoned about* rather than disassembled. **Disassembling first would
have cost one step instead of four** — the rule above is not advice.

**Build-time markers and base literals count when they appear in COMMENTS.**
`build_bus.py` census-checks the number of `$30000` literals in the delay
source and requires exactly one `; DMODE_OVERRIDE` / `; DINT_OVERRIDE`
marker — and the substitution is a blanket text replace over the whole file.
Writing *about* either in a comment trips the guard: both happened while
documenting stage 5/6 (a comment explaining why mode 3's immediate must be
decimal spelled the hex out; another explaining the override marker spelled
the marker out). The build refuses, loudly, which is the guard working —
describe them in prose instead of spelling them.

**`SPEC=1` requires `XBUS=1`.** Without it the accumulators stay in core-private
memory and each half of the tracks can reach only its own core's server — worse
than today, **and it still makes sound.** The build guards this. Do not ungate it.

**The track↔core mapping is INVERTED from old assumptions**: payload A serves
**tracks 5-8** (BusVerb), payload B serves **tracks 1-4** (BusDelay).
Measured 10 Aug 2026 via the MrkVerb32 marker flash, after the assumption cost
two flashes and a session chasing "R13 is dead" (it was alive on tracks 5-8).
Kept deliberately: delay on low tracks, reverb downstream. Test the reverb on
**track 5**, not track 1.

**`→DELAY` and `→REVERB` are separate knobs**: `x:(r6+0)` and `x:(r6+1)`.
Driving the wrong one renders silence, which reads as a broken algorithm.

**A DESCRIPTOR'S DISPLAY FORMATTER OVERRIDES ITS VALUE COUNT, and a cloned
descriptor inherits the DONOR's.** A slot can carry a correct count, default,
name and enable bit and still draw as something else entirely — or as nothing
at all. Found on the 17 Aug flash: BusDelay clones SPRING REV, the formatter
fix-up in `build_bus.py` was gated to the reverb, and three of six page-2
slots drew wrong. WOW inherited SPRING TYPE's word-label renderer whose table
has THREE entries, was asked to draw 0..127, and **drew no knob at all**;
MODE inherited SPRING BAL's bipolar pair and drew as a balance dial reading
−64…−60 instead of a 5-way select. Every existing check passed, because every
field they checked was right. `verify_menu` now checks the renderer against
the count (`count < 128` → the enumerated pair with `0x12a` zero; `128` → both
formatters zero). **The general form: when you clone a descriptor, every field
you did not explicitly write is the donor's, and some of them outrank the ones
you did.** Same family as "a slot can draw a knob and publish nothing" — the
panel and the DSP are separate mechanisms and neither validates the other.

**STOCK UNICORN HALVES EVERY ColdFire FRACTIONAL-MODE MULTIPLY AND ADDS
WHERE `msac` SUBTRACTS, and the firmware runs its EMAC in fractional mode
(`MACSR = 0x20`).** Unicorn 2.1.4 computes `macl`/`macw` under `F/I = 1` as
an UNSIGNED product `>> 32` where the MCF5445x does a SIGNED product `>> 31`
(the 2.62 product shifted left one bit, upper 40 bits accumulated), and it
reads the MAC/MSAC bit from the opcode word where ColdFire keeps it in the
extension word, so every `msac` accumulated with the wrong sign (the
sequencer's frame builder is one). One defect, three symptoms that were each
investigated as firmware behaviour for a day (7 Sep 2026, RTOS_FORK
§10.16): the recorder length converter wrote 10,336 for Bryan's 20,672
(explained away as "2-sample units"), the recorder's block walk stalled at
3,072 samples ("needs a DSP position feed"), and the sequencer's per-frame
timing byte advanced 8 per 16-sample frame, which dropped half the tempos'
recorder trigs ("nothing re-locks the step clock", plus a compensation
lever). The firmware's own reciprocal tables (`0x80003c20`: 2^31 / block
size) said which side was wrong. **Route A refuses to run on a stock EMAC**
(`emu_bringup.emac_selftest`); `scripts/build_unicorn.sh` builds the fixed
library (`tools/unicorn_emac_fractional.patch`). The general rule is the
same as "disassemble what you assemble": when firmware arithmetic comes out
exactly 2× or ½ off, suspect the INSTRUMENT before inventing a unit, and
find a site in the firmware whose constants only make sense one way.

**MACSR S/U IS BIT 6, AND IN FRACTIONAL MODE IT IS NOT SIGNED/UNSIGNED:
it selects 16-BIT ROUNDING ON THE ACCUMULATOR READ-OUT.** The ColdFire port
had S/U as bit 4 (that is R/T) and returned every `movclrl` as `ACC[39:8]`;
the firmware's level chain at `0x4000ccae` runs at MACSR `0x60` and keeps the
LOW words of two reads as a voice record's mode:level, which the CFPRM's
pseudocode (`OMC,S/U == 01`: `ACC[39:24]` rounded into `Rx[15:0]`, upper half
zero) puts there and a plain `>> 8` leaves at zero — every voice rendered
silent for a whole session (8 Sep 2026, O9b). The self-test never exercised
S/U. Read the CFPRM's MOVCLR pseudocode before touching `accRead`.

**THE VENDORED DSP AGU LEFT A MODULO BUFFER ON A PRE-DECREMENT FROM ITS
BASE.** `x:-(r2)` with r2 = 0 and m2 = 0x3f gave `0xffffbf` where the chip
gives `0x3f`, the next sixteen sample writes walked the peripheral registers,
a timer interrupt came alive whose vector in payload B is `move x0,y:(r4)+`,
and the corruption surfaced as a 196,608-iteration voice loop thirteen frames
after the first trig. Found with a one-word write watch, a DSP PC watch with
registers and an interrupt-vector histogram (O9b); fixed in `agu.h`. It is
the eleventh vendored-emulator defect and `dsp_host` renders every effect on
that AGU — `make check`'s bit-identity gates are the audit.

**A REWRITTEN TRAMPOLINE IS NOT RETRANSLATED.** The ColdFire emulator's
EMAC-with-load shim ran every shimmed instruction from one scratch address,
rewriting its bytes each time; in a long-running Unicorn the address kept
its first translation, so the trampoline executed whichever instruction had
been translated there LAST — `msacl ..,%acc1` ran as the previous `msacl
..,%acc0` and corrupted the sequencer's timing byte (RTOS_FORK §10.16.2,
7 Sep 2026). Fresh-Uc micro-tests could not show it; a per-instruction
trace of the real run did. Rule: never rewrite emulated code in place — give
each distinct instruction its own slot (`r.emac_slots`), and when a
micro-test disagrees with the running emulator, the difference is state,
so trace the running emulator.

**A MEASUREMENT CAN BE STRUCTURALLY BLIND TO THE THING YOU ARE USING IT TO
RULE OUT — and it will report "clean" with total confidence.** Two instances,
both on 17 Aug 2026, both costing hours:
- `send_probe`'s THD metric sums harmonics **2f..9f of a 438 Hz tone**. A
  block-rate discontinuity (~2940 Hz) is not a harmonic of 438 Hz, so the
  metric cannot see it. It reported −45 dB ("clean") on audio that hardware
  measurement later showed carrying +22 to +31 dB of inharmonic hash. Every
  "no change" conclusion drawn from it that day was worthless.
- XBUS step 3 concluded "synchronisation not needed" from a cross-core send
  measured **through the reverb** — the one consumer that smears per-sample
  damage into a multi-second tail. It shipped a cross-core race for months.
**Before trusting a null result, ask what the instrument physically cannot
see.** A reverb cannot show you a discontinuity. A harmonic metric cannot show
you an inharmonic one. A lock-step emulator cannot show you a race between
two cores — `dsp_host` boots both payloads since 7 Sep 2026 and `-skew` can
interleave them, but that is a fuzz of the hardware's timing, not the
timing, so a local "clean" is still NOT evidence a bus timing defect is
gone (a local red IS a defect). When local says clean and hardware says
broken, believe the hardware and go looking for what the harness omits.

**A BUS CLIENT THAT REGISTERS BUT CONTRIBUTES NOTHING STEALS EVERYONE ELSE'S
LEVEL.** The auto-gain divides the accumulator by the number of registered
clients, so a writer that registers unconditionally and then writes zero
dilutes the real senders by N/(N+1) — **−6 dB with a single sender.** Two
instances found the same day, 17 Aug: BusVerb registered for its `→DEL` send
even when `→DEL` was off (since gated on the knob, measured −6.02 → +0.00 dB;
the send itself was later retired), and BusDelay's own `IN` knob would have
done it too if its default
had stayed non-zero on a return track with no audio to send. **Gate the
registration on the knob, and remember the level knob is usually decoded
LATER in the block than the registration runs** — read it from `r6` directly,
or use the previous block's value and accept one block of latency. Symptom to
watch for: a level that is flat across sender count in one layout and drifts
in another. It surfaced as an "unexplained residual" in a completely
different effect's send level, and the effect being blamed was innocent.

**r7 scratch is COMPLETELY FULL — `$00..$83` all in use as of 10 Aug 2026**
(the "only `$00..$0c` free" note held until the R16–R18 work consumed the
rest). New per-track state goes in the Y state table, not r7. `$84+` hangs
the unit. (Do not scan for these with `"\$$s"` in a shell — it expands.)

**A dump can resolve a perfectly plausible dispatch entry for an effect it
does not contain.** `SPEC=1` (which `make render` sets) aliases the absent
server's id to the SEND client — deliberately, so a wrong chooser pick
becomes a send. Locally that alias renders a dry passthrough: silence over
the bus, dry in a `--direct` control, no error anywhere. This produced the
12 Aug "BusDelay outputs nothing in any config" session — the delay was
never instantiated; every measurement ran a SEND. Delay work needs the
hatch (`make render-delay`), and `send_probe.py` now dies when a D layout's
DELAY entry equals SEND's. The general rule: before believing a *negative*
result, check which code the dispatch entry actually points at — same
family as "disassemble what you assemble".

**IN THE SHIPPING REMIX, payload A's half of the shared window is FULLY
OWNED** (a remix without the reverb frees it, which is how the insert
collection has room to stack): BusVerb's
relocated buffers at `0x30000`/`0x34000`, bus scratch at `0x36000-0x360d2`
(grew 12 Aug for the DELAY send counts + reciprocal table, and again 17 Aug
when the accumulators went to FOUR buffers for the cross-core race fix).
There is no free ground in it for delay lines — the DEV build places the
delay at its shipping base `0x38000` (payload B's half) for exactly this
reason. A delay based at `0x30000` sweeps the rotation word, all four ACC
buffers and both role locks every 16,384 samples and blows up any
multi-server layout (found 12 Aug, RDS full-scale garbage).

**AN FX2 ID IS ALSO AN FX1 ID: the DSP dispatch tables are indexed by the
raw id and shared by both menus.** A module on a stock effect's id replaces
that effect's code wherever it is selected, FX1 included, and a remix that
omits the module then aliases the id to SEND and takes the stock effect
away from FX1 too. Rungs sat on EQUALIZER's `0x0c` and Nimbus on DJ EQ's
`0x0d` from 29 Aug to 2 Sep 2026, in every local image, unflashed. The
schema now refuses `STOCK_FX2_IDS`; the stock effects themselves are kept
in a chooser by listing them in the remix (`tools/remix/stock.py`).

**`dsp_host`'S DEFAULT AUDIO BLOCK (X:0x80) SITS INSIDE THE SCRATCH THE
STOCK EFFECTS USE.** On hardware the dispatcher passes `r0 = 0`: the audio
block is at X:0 and stock code scratches X:0x20–0xff every block. Our
modules never touch low X, so the default was harmless for months and then
made the stock FLANGER render as Nyquist-rate hash and five other stock
effects 5–17 dB dirtier while passing as "credible" (2 Sep 2026). Eight
instruction probes were spent clearing the emulator first. `send_probe`
passes `-audio 0` for a stock render; if a stock effect sounds wrong
locally, suspect the harness before the effect.

**A DESCRIPTOR NAME THAT EXACTLY FILLS ITS FIELD LEAVES NO NUL, AND THE
CRASH LANDS SOMEWHERE ELSE ENTIRELY.** `abbr` is a 5-byte field holding FOUR
characters plus a terminator; `fullname` is 13 bytes holding TWELVE (and the
build tag is appended after your string). A 5-character abbr assembled,
built, drew correctly on the panel and behaved normally under manual knob
use — and threw a line-F exception (VEC:0B) the moment a parameter was
**LFO-MODULATED**, faulting PC `0x48454C4C` = `"HELL"`. It presented as
"custom effects can't be modulated", which points at the clone mechanism,
not at a string. Found 2 Sep 2026 by Bryan T contributing `modules/hello/`,
after the build accepted it silently. A faulting PC made of the field's own
ASCII is a smashed return address, so the copy destination is fixed-size —
INFERRED, the copy is not located; the rule itself is measured (all 30 stock
page descriptors are ≤4 chars with byte 5 zero). `schema.MenuEntry` now
refuses both over-lengths and `build_bus.py` re-checks the string it writes,
tag included — which caught two diagnostic delay names (`BusDlyRPLY`,
`BusDlyNOCF`) that had been filling all 13 bytes since 24 Aug 2026.

**A PART SAVED UNDER AN OLDER SLOT LAYOUT FEEDS THE NEW LAYOUT ITS OLD
BYTES, AND THE SEQUENCER STALLS ON THE FIRST PLAY.** Moving MODE from slot 7
to slot 6 (4 Sep 2026) passed every local check and both hardware claims —
then pressing play went 1, 2, 1 and froze, because every other track's part
still held a 0–127 SHMR/MDEP byte in what was now a count-3 select, the
"value outside its count is used as an index" trap in stored form. The
schema cannot see stored data. Re-selecting the effect on the track you are
looking at is NOT enough; the sequencer runs every track of the part. After
any change to a slot's count, position or meaning: `tools/ot_project.py
stamp-defaults <project> <remix>` on the card BEFORE play, and say so in the
flash notes. (Cause inferred from the symptom and a refreshed project
running clean; not measured.)

**THE PART THE EMULATED LOAD APPLIES IS NOT THE PART THAT PLAYS.** `ot_emu`'s
load applies bank 1 part 1; its transport start re-applies the SAVED bank's
pattern part and the refresher at `0x4000c19c` rewrites the live lane from
it. A fixture that edited "part 1 and its saved copy" measured a track whose
FX2 was still SEND — for a whole O9c session (8 Sep 2026): "the THRU monitor
is pre-FX2", "the page-2 select never crosses" and "X:0x2c0 is the FX2
instance" were all this one fixture, and the last was `stamp-slot` landing in
the track's FX1 (it stamps both slots). Write fixtures into EVERY part of
EVERY bank (`ot_project.py set-fx`, `stamp-slot`), and before believing a
DSP-side "byte-identical" between two cards, run both with `--block-dump`
and `tools/scratch/blockdump.py diff`: if no host-port block differs, the
cards did not differ where it matters.

**A parameter slot can draw a knob and publish nothing.** The page descriptor
and the DSP-side read are separate mechanisms; `dsp_host` pokes r6 directly, so
everything looks live locally even when the real unit would publish nothing.
See `docs/PARAM_PAGES.md`.

**Flash cycles are expensive** — each one is a manual firmware write. Render
locally and measure instead of guessing. This is why the emulator path exists.

**When the unit misbehaves, check `docs/FAILURE_MODES.md` first** — the
register of hardware failure modes (symptom -> cause -> fix). Add any new one
the moment it is seen; do not let it live only in a commit message.

## How claims are written here

The project has been burned by stale confident numbers more than once — a
cycle budget of 1080 that was never a ceiling, a burn probe that measured an
engine we do not ship, a blocker our own bisect had already falsified.

So: **separate measured from inferred.** `docs/CHIP.md` marks every number with
a confidence marker and keeps retracted values beside current ones. Do the
same. Say what would falsify a claim. Do not write "found it" for something
you have inferred, and when a retraction lands, propagate it to every document
that repeated the old number — not just the one you were editing.

## History

The tree was pruned hard in the octabam refactor: ~350 files of ColdFire
archaeology, emulator scratch and 89 `reverbN.asm` voicing snapshots were
removed. They are all still reachable — that is why the history was carried
across rather than starting fresh.

Comments still cite probes like `dsp/baseprobe.asm` or `dsp/ymemprobe.asm` as
the provenance of a measurement. Those statements remain true; the files live
in history. Recover one with:

```bash
git log --all --oneline -- dsp/baseprobe.asm
git show <sha>:dsp/baseprobe.asm
```

Leave those citations alone. Rewriting them to remove a filename would erase
how the number was obtained, which is the opposite of the point.
