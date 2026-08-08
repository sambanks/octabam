> ⚠️ **READ `PLAN.md` FIRST.** As of 8 Aug 2026 this file is the *architecture*
> record — how the cross-core bus works and why. The **plan** (end-state
> resource ledger, work order, what to do next) lives in `PLAN.md`, which
> supersedes this file's "Recommended order" section.

# The target architecture: one reverb, one delay, all eight tracks

Agreed 7 Aug 2026. This supersedes `BUS.md`'s bank-scoped design, whose founding
constraint — "the two DSPs are a hard boundary" — is now known to be false.

## What we're building

```
CORE 0   track 1   ChonVerb   Y:0x4000-0xBFFF (private) + Y:0x30000-0x37FFF (shared lo)  = 65,536 words = 1.49 s
         2,3,4     Send
CORE 1   track 5   BongDelay  Y:0x4000-0xBFFF (private) + Y:0x38000-0x3FFFF (shared hi)  = 65,536 words = 1.49 s
         6,7,8     Send

         every track sends to both, through accumulators in the shared window
         delay wet -> reverb  (series, the direction that is already built)
```

⚠️ **Corrected arithmetic — "all 4 of core 0's FX2 slots = 65,536 words" was
wrong, and wrong in a way that would have collided.**

The real pool is `32K private + 32K private + 64K shared = 128K words`, and it
divides as above: each server gets its own core's two private slots plus **half**
the shared window, **65,536 words each**.

❌ **RETRACTED 9 Aug 2026 — "`X:0x255` is the same table in both payloads:
FX2 slots are `0x4000 0x8000 0x30000 0x34000` on each core, so core 0's slots
3–4 and core 1's slots 3–4 are the same physical memory."** That is false, and
the conclusion it was used to reach ("only if the delay is given
`0x38000-0x3FFFF`, which the allocator never hands out at all") is false with
it. ✅ **Measured** by dumping the table out of both payloads of the *raw*
stock image — it is **not** the same table:

| | payload A | payload B |
|---|---|---|
| `X:0x255` | `001000 004000 001c00 008000 002800` **`030000`** `003400` **`034000`** | `001000 004000 001c00 008000 002800` **`038000`** `003400` **`03c000`** |

**Stock already separates the two cores' shared-window slots.** Payload A is
handed `0x30000` and `0x34000`; payload B is handed `0x38000` and `0x3C000`.
The allocator hands out `0x38000` on core 1 as a matter of course, and the two
cores' FX2 slots cannot collide in the shared window even if all four were
taken.

This *strengthens* the split rather than changing it: core 0 owning
`0x30000-0x37FFF` and core 1 owning `0x38000-0x3FFFF` is what the stock
allocator already believes, so the hardcoded bases agree with the table
instead of merely dodging it. The raw-vs-built comparison also confirms our
build does **not** modify `X:0x255` in either payload — the difference is
stock.

Falsified by: dumping module `X:0x255` from `out/raw/section_3_MAIN_OS.bin`
for both entries of `dsp_modmap.PAYLOADS`. Both servers still hardcode their
bases, so the table is documentation here, not a dependency.

**Three wins, and they are different resources. The third one is new and is the
one that has been missed.**

*Cycles*: each core runs ONE effect with its full ~4,535 cycles/sample instead
of both cores running both effects. Roughly doubles the effects budget.

*Memory*: 372 ms → 743 ms (done, the 32K re-layout) → **1.49 s**.

*Program space*: **the payloads no longer have to be the same code.**
`build_bus.py` already assembles and places each payload independently — one
`for tag, va, ln in PAYLOADS` loop, its own region, its own placement — and the
2,724-word region is **per core**. Today both payloads carry all three effects
and both are at **2,723 of 2,724 words, ONE free**. Under one-server-per-core:

| payload | carries | words | **free** |
|---|---|---|---|
| A (core 0) | SEND 212 + ChonVerb 2,018 | 2,230 | **494** |
| B (core 1) | SEND 212 + BongDelay 507 | 719 | **2,005** |

✅ Measured, not estimated: `XBUS=1 python3 tools/build_bus.py` already prints
`FREE 484` per payload, because the XBUS path drops the delay to a 10-word stub.
That build is the specialization, done crudely and by accident.

**Program space was the binding constraint on all three effects, and
specialization alone removes it — before a single line of code is written.**

**What the memory actually buys, since this is easy to get wrong: NOT a longer
tail.** The current engine already does 8.7 s RT60 out of 743 ms of buffer —
tail length comes from feedback gain. More memory buys longer taps, longer
pre-delay and lower modal density, i.e. a **bigger, smoother space**. 743 ms is
exactly why `REVERB.md` ruled out Blackhole-class and substituted a
Valhalla-flavoured big mode. 1.49 s reopens that.

## STATE AS OF 7 Aug 2026 — SOLVED: the artifact was the SHIMMER

**Hardware-confirmed.** Sam flashed `ChonVerb31` (shimmer excised) and the
metallic/staticky artifact is **GONE**. The send path was never at fault.

### What it was

The shimmer (`v101`, a +12 pitch shifter in the feedback path) was running on
every build anyone has ever heard, at roughly half strength, **with no way to
turn it off**:

- Page-2 slot 6 is `SHMR`, and `build_bus.py`'s `DEFAULTS` set it to **48**.
  The comment there still read *"SPEED slow-ish"* — stale since `v101` renamed
  that slot from SPEED to the shimmer amount and never revisited the default.
  `41d252c` fixed the default to 0, but the card was running `BASE30`
  (`0d4248c`), which predates it.
- The knob could not correct it, because a page-2 slot **draws a knob without
  necessarily publishing a value** — `PARAM_PAGES.md` §"What a probe build
  would have to establish" wrote this down before it ever bit us. So SHMR sat
  pinned at 48.
- The shimmer is documented as metallic in its own right (`REVERB.md`: a blind
  splice), so this was a known-bad effect stuck permanently half-on.

### Why it took so long, and the lesson

Two things hid it, and both were self-inflicted:

1. **The emulator had `SHMR=0` in every render.** `render_reverb.py`'s `PARAMS`
   still labels index 6 "SPEED" (the pre-v101 name), that label was copied into
   `send_probe.py`, and the slot was then set to 0 to keep LFO sidebands out of
   a THD metric. **Zeroing a parameter to clean up a measurement hid the bug
   that parameter caused.** Every "the send path renders clean" result was true
   and useless.
2. **"The reverb sounds right on its own track" was treated as ruling SHMR
   out** (the v114 handoff says so explicitly). It does the opposite: at
   partial MIX the dry masks the shimmer, while a SEND is heard 100% wet, which
   is exactly the asymmetry that made it look like a send-path fault.

The measurement that finally matched was per-mode shimmer contribution —
ROOM +19.8, PLATE +22.9, HALL +22.6, **BIG +1.8 dB** — which predicted Sam's
"mode 4 is a lot less bad" before that was known to be diagnostic. The hardware
signature it had to match: **+20.1 dB at 2.5–5 kHz, discrete lines (HF
peak/mean 40.9 dB), music untouched (top-8 bins 95.3% before and after)**.

### The fix, and its state

**The shimmer is now excised BY DEFAULT.** `build_bus.py` cuts everything
between `; SHIMMER_BEGIN` and `; SHIMMER_END` in `dsp/reverb_server.asm` unless
`SHIMMER=1` is set, which prints a do-not-ship warning. Excising rather than
zeroing matters: a zeroed coefficient still leaves the shifter reading and
writing its buffer every sample.

- Verified **bit-identical** to a `SHMR=0` render, so no side effects.
- **2040 → 1950 words**, and the payload region's free space **11 → 101 words**.
- Reclaims the 2048-word buffer at `base+0x7800`.
- The code is preserved in git behind the markers, for the pitch-synchronous
  rewrite (`REVERB.md`), which is where the shimmer should return from.

**On the card: `OCTATRACK_NOSHIM31.bin`, reading `ChonVerb31`.**

### What this unblocks

The send path is exonerated and the reverb now matches how it was actually
voiced (`VOICING.md` rounds were done without shimmer). Everything below in
this document — the cross-core bus, the 1.49 s re-layout — is no longer
blocked.

### Still open, found along the way

- **BIG rings.** ~30 dB more HF than the other modes even with no shimmer: a
  dense cluster of non-harmonic lines in 2–2.8 kHz. `md_big` sets the decay
  scale `x:(r7+$1e)` to `$7FFFFF` = **exactly 1.000000**, where ROOM/PLATE/HALL
  leave headroom (0.920/0.965/0.980). Not simple runaway feedback — HF *falls*
  as TIME rises and is already high at TIME=0, so it is the input/early path.
  A mode at unity feedback scale is a hazard regardless.
- ~~**Gain staging.**~~ **FIXED (v121)** — the bus now auto-scales by the number
  of clients that actually wrote it, so 1 to 8 tracks all drive the reverb
  identically. Each SEND registers itself once per block in a parity-indexed
  count at `Y:0x983/0x984` and writes its contribution with **3 bits of
  headroom** (`asr #3`), so eight clients at full scale sum to exactly 1.0 and
  the shared word can no longer be summed into its rail. The server reads the
  count for the buffer it is READING, looks up 1/N in a table at `base+0x7800`
  (rebuilt each block, in the space the shimmer freed), multiplies, and shifts
  back up by 3. Measured before/after at 0.15 FS per send:

  | sends | THD before | THD after |
  |---|---|---|
  | 1 | −44.6 | −44.6 |
  | 3 | −16.3 | −44.6 |
  | 5 | −3.0 | −44.6 |
  | 7 | −0.6 | −44.6 |

  Eight tracks at 0.35 FS each are now clean (−44.6). The reverb's OWN tank
  still saturates above ~0.35 FS — unchanged, separate, and now the only limit.
  **The DELAY accumulator did NOT get this treatment**; BongDelay is an
  untested draft and can take the same change when it is worked on.
- **The payload region is FULL: 2723 of 2724 words, ONE spare.** Anything added
  to any of the three effects now needs space found first.
- **Emulator/device alignment.** The proven gap is parameter delivery:
  `-params` pokes `r6` directly, so every slot looks live locally, while on
  hardware a slot can draw a knob and publish nothing. That single gap is what
  let the emulator report "clean" for a whole session.

### What was measured about the bus, and stands

| Question | Result |
|---|---|
| Does the bus carry audio? | **Yes.** 175,972 non-zero samples with the reverb's own input silenced. |
| Is the send path faithful? | **Yes.** SEND vs DIRECT within **0.3 dB THD at every level**. |
| A regression in the 24 commits? | **No.** Smooth drift, no step; `40f7167` is worse than the commit after it. |
| Mismatched per-track splits? | **No.** All combinations ≈ −36.2 dB. |
| Multiple sends? | **No bug.** They sum linearly. |
| Cycle budget? | **Not close.** ~44 instr/sample against a ~2400 ceiling. |
| LFO rate (measured, not inferred)? | **0.10–0.69 Hz**, as designed. The `$2f` audio-rate theory is dead. |

`dsp_host` gained what was needed to establish these: **list `-init`/`-proc`**
(a different effect per instance — the first true SEND→SERVER run anywhere),
**`-inmask`**, **per-instance `-split`**, and **`-track`** (r7-relative words
dumped every block, so a *rate* can be differenced; `-peekx` only snapshots
once). `tools/send_probe.py` and `tools/capture_hw.py` drive and analyse it.

⚠️ **Traps that each cost a wrong conclusion:**
- **Zeroing a parameter to clean up a metric hides the bug it causes** (above).
- **`tools/dsp_host/` is COPIED into `vendor/` by `setup.sh`'s
  `stage_dsp_host`.** Building without re-copying silently runs the OLD binary
  — the giveaway was two different renders coming out byte-identical.
- **`MODE=n` writes `out/mainos_bus_mode<n>.bin`, NOT `out/mainos_bus.bin`.**
  Comparing the latter compares the ordinary build with itself, which is what
  produced a bogus "the MODE override is a no-op" claim in v115.

## Steps 0–3 are DONE

0. ~~Find the metallic artifact.~~ **DONE** — the shimmer, stuck half-on and
   unturnoffable; excised by default, hardware-confirmed gone.
1. ~~Relocated bus, same core.~~ **DONE** at `0x36000`.
2. ~~Does a cross-core send arrive?~~ **DONE — cross-core works.**
3. ~~Synchronisation.~~ Not needed as feared; the ICC stays unused.

Steps 4 (memory re-plan) and 5 (the effects) are what remains, and the
re-evaluation below is what they should now be.

---

# THE RE-EVALUATION — what a whole core per effect actually buys

## The constraint has INVERTED, and this is the headline

Every optimisation in this project so far traded program words for cycles,
because cycles were the wall: the density pass (432 → 297), the v97 Hadamard
rewrite (24 words → 16), the v99 early-reflection rewrite (254 → 181 cycles).
That rule is now **backwards**.

| resource | before | after specialization | ratio |
|---|---|---|---|
| cycles, core 0 (reverb + 3 sends, FX1 filters off) | ~2,432 spare ✅ | **~2,576 spare** 🟡 | ~3.4× the engine's 763 |
| cycles, core 1 (delay + 3 sends) | — | **~3,176 spare** 🟡 | ~19× the placeholder's 163 |
| Y memory per server | 32,768 words / 743 ms ✅ | **65,536 / 1.486 s** ✅ | 2× |
| **program space, payload A** | **1 word** ✅ | **494 words** ✅ | — |
| **program space, payload B** | **1 word** ✅ | **2,005 words** ✅ | — |

(Cycle figures are the measured 2,432 spare — filters off, full bank live —
plus the per-sample cost of whatever that core no longer runs. 🟡 because the
measurement was taken in a different configuration, not because the arithmetic
is loose. Re-run the burn probe in the real configuration before spending the
last few hundred.)

**So: spend cycles to buy program words, everywhere.** Two consequences that
are worth more than any voicing change:

- **Roll the unrolled loops back up.** The reverb's four tank lines are
  unrolled: tank taps 101 instructions, feedback/write-back 101, STAGE-2 read
  offsets 44, LFOs 19 — **265 instructions for four lines, ~66 per line** ✅
  (counted). A hardware `do` on the 56300 is zero-overhead, so the cost is
  per-line constants becoming table reads instead of immediates. **Eight lines
  rolled is SMALLER than four lines unrolled.** Mechanics, the strided state
  layout and the two traps: §"Rolling the tank loop" below.
- **AGU modulo is no longer mandatory.** Power-of-2 alignment is what caps a
  single delay line at 16,384 words in the private region. A manual compare-
  and-wrap costs ~4–6 cycles/sample — unaffordable before, free now — and
  unlocks arbitrary line lengths. This is the only way BongDelay gets a
  single 1.49 s line.

## The shared window can hold CODE, and we have only ever spent it on buffers

**This is the "we freed up a heap of everything" intuition, and it is right —
but not for program space, which is the one resource the shared memory and the
cross-core work did not touch at all.** P/X/Y alias in `0x30000-0x3FFFF` ✅, so
those 65,536 words are addressable as **program memory** just as readily as
buffer, and nothing has ever tried it.

Stock already does it, in production, today ✅:

| | |
|---|---|
| `P:0x30000` | 171 words — the DSP host-port loader + ESAI setup, payload A |
| `P:0x31000` / `P:0x32000` | bootstraps A (50 words) and B (58) |
| `P:0x38000` | 19 words — **payload B's entry stub, which `jsr`s into `0x30082`/`0x3008a`** |

That last row is the existence proof and it is the important one: it is a live
P module, loaded by the ordinary module loader (space byte 0 = P, exactly like
our code), executing after boot, and reaching **across into payload A's code**.

**`0x38000` is also the half that SURVIVES.** Init zeroes `0x30000-0x37FFF` —
all 32,768 words, disassembled at `P:0x040` ✅ — so anything preloaded into the
lower half is wiped. The upper half is not zeroed, which is exactly why that
19-word stub is still there to be called.

🟡 **So the hypothesis: our effect code can live at `P:0x38000+`.** The
dispatcher does `jsr (r2)` with an address out of `X:0x215`/`X:0x235`; a 24-bit
`0x38000` is as valid a target as `0x01000`, and the loader already places P
modules there.

**What would falsify it:**
- ~~The OMR memory map may not expose the shared window as P to a core.~~
  ✅ **DEAD — Ch. 3 has now been read.** "Shared RAM" appears in the **Program**
  column of all five memory-map figures (3-2 through 3-6), including the
  default. The window is program-addressable in every configuration.
- Instruction fetch there costs **1 wait state** (vs 0 as X/Y) ✅, so code in
  the window runs slower. Cheap now that cycles are abundant, but it must be
  measured, not assumed.
- **Contention.** Instruction fetch is a bus access, so code in an 8K block the
  other core is hammering costs arbitration. Put code in a block that core does
  not touch.

## And the bigger one: Ch. 3 says the 8K program wall is a SETTING

**This is why program space has been so desperate, and it was never a property
of the chip.** ✅ Read from `DSP56720RM.pdf` Ch. 3 and confirmed against the
image:

| map | MS | MSW1 | MSW0 | **Program** | X | Y | usable? |
|---|---|---|---|---|---|---|---|
| Fig 3-2 **default** | 0 | – | – | **8K** | 36K | **48K** | ← what stock runs |
| Fig 3-3 | 1 | 1 | 1 | **16K** | 36K | 40K | ✅ costs `Y:0xA000-0xBFFF` |
| Fig 3-4 | 1 | 1 | 0 | **24K** | 36K | 32K | ✅ costs `Y:0x8000-0xBFFF` |
| Fig 3-5 | 1 | 0 | 1 | **32K** | 36K | 24K | 🟡 eats into FX2 slot 1 |
| Fig 3-6 | 1 | 0 | 0 | 36K | **32K** | 24K | ❌ **ruled out, see below** |

Every row totals 92K words. **The three spaces are one pool of RAM that OMR
redistributes**, and the trade is word for word.

**Stock runs the default map, and this is now measured, not assumed:**

- ✅ **Nothing writes OMR.** Disassembling every P module in both payloads finds
  exactly two OMR-class instructions, both `andi #$fc,mr` — that is the *mode
  register*, not OMR. `MS`, `MSW1`, `MSW0` all reset to 0 (bits 7 and 22:21,
  Table 5-2), so the core boots the default map and nothing ever changes it.
- ✅ **The hardware Y sweep matches Fig 3-2 exactly** — Y present
  `0x00000-0x0BFFF`, absent from `0x0C000`. That is the default map's 48K, to
  the word.
- ✅ **Payload A's P code ends at `0x01fdf` — 33 words short of `0x2000`**, the
  top of the default map's 8K. 8,159 of 8,192 used. *That* is the wall, and our
  2,724-word donor region sits inside it.

**Fig 3-6 is ruled out by measurement:** it drops X to 32K (`0x0-0x7FFF`) and
stock's X modules reach **`0x08d98`**. It would break stock outright.

**The prize.** `MS=1, MSW1=1, MSW0=1` **doubles program RAM, 8K → 16K: +8,192
words**, against a region with *one* free word today. Cost: `Y:0xA000-0xBFFF`,
i.e. the reverb's private pool drops 32K → 24K, so the reverb goes 65,536 →
57,344 words (1.49 s → 1.30 s). Fig 3-4 buys +16,384 P words for 1.09 s.

🟡 **Untested, and the risk is real.** OMR must be written **before any module
is loaded into the newly-available P**, which means patching the boot path —
the natural site is bootstrap A/B (`P:0x31000`/`0x32000`, 50 and 58 words, in
the shared window and already ours to patch). Open questions, none answered:

- Does the ColdFire-side loader assume the default extents anywhere?
- Does anything in stock's *runtime* allocate Y above `0x9FFF`? No loaded
  module does (the highest Y module ends at `0x795`), but the FX2 allocator
  hands out `Y:0x8000` as a slot base, and that slot's top half disappears.
  Under our three-entry menu only ChonVerb lives there, so we control it — but
  that is an argument about our build, not about stock.
- Is the switch safe *after* reset at all, or only at reset?

**Sequence if this is ever taken: change the map first and prove the machine
still boots with the code where it already is.** Do not combine it with moving
code into the new region — that is two variables, and `REVERB.md`'s "change one
thing per flash" was written after five changes at once cost a whole session.

**The trade, and it is the honest part: shared words spent on code are words
neither effect gets as buffer.** 4,096 words of P would take BongDelay from
65,536 to 61,440 (1.49 s → 1.39 s). Against a program region that has *one*
free word today, that is an extraordinary rate of exchange — but it is a trade,
not the free lunch the alias makes it look like.

**Do not confuse this with specialization.** Specialization (494 / 2,005 free
words) is real, costs nothing, and needs no new hypothesis. This is the lever
*after* that one, and it should be tested only if the reverb's 494 words prove
too tight — which rolling the tank loop may well prevent.

## What to build with it — the reverb

The known limit is modal overlap, and `REVERB.md` closed it as "no structural
lever left under the 32K ceiling". **1.49 s and 2,500 spare cycles reopen it,
and the lever is more lines, not longer ones.**

Mode spacing is `sr / total_delay_read`. Today: 12,574 samples → 3.5 Hz →
overlap **0.157** at RT60 4 s, against the ≥ 1 that reads as smooth.

Doubling total delay halves the spacing, and there are two ways to do it:
**8 lines × 4,096**, or **4 lines × 8,192**. Both give overlap ~0.31. Take the
first — at equal total delay, more short lines beat fewer long ones (more
independent paths, richer Hadamard mixing, no drift toward a longer and more
separated character), and it keeps the per-line length the modes were voiced
against.

A layout that fits 65,536 words exactly:

| offset | size | what |
|---|---|---|
| tank | 8 × 4,096 = 32,768 | eight lines, 8×8 Hadamard |
| input diffusers | 8 × 2,048 = 16,384 | one per line |
| pre-delay | 8,192 | 186 ms, double today's |
| in-loop allpasses | 4 × 2,048 = 8,192 | double today's two |

Costs, against ~2,576 spare cycles and 494 free words:

- **Cycles** 🟡 ~+450 for four more lines, ~+32 for the 8-point fast Hadamard
  (12 butterflies vs 4). Call it **~1,250 total** against 2,576. Comfortable.
- **Program space** 🟡 ~+340 instructions ≈ **450–500 words** if unrolled,
  against 494 free. *Fits, with nothing left, and that estimate carries ±20%.*
  **Roll the tank loop and the problem disappears** — this is exactly why the
  inversion above matters more than the feature does.

## Rolling the tank loop — what it means, and why it is the enabler

**"Rolling" = turning an unrolled loop back into a loop.** The tank's four
delay lines are not written as a loop; the same code is written out four times
with different registers and constants.

✅ **Measured, not impression:** the tank-tap block is **4 × 25 instructions,
and once constants and address registers are normalised all four repeats are
identical**. Same shape in feedback/write-back (101), the STAGE-2 read offsets
(44) and the LFOs (19). **265 instructions doing 66 instructions' worth of
distinct work.**

Unrolling is the classic spend-words-to-save-cycles trade, and it was right
when cycles were the wall. It is now backwards — which is why **8 lines rolled
is SMALLER than 4 lines unrolled**, and why the modal-density fix stops costing
program space at all instead of needing ~450–500 words against 494 free.

### It is more tractable than it looks: the state is already strided

✅ Four of the five per-line state groups are **already stride-1 across the
lines**, so rolling them is mechanically `base + k`:

| state | line 0 | 1 | 2 | 3 | |
|---|---|---|---|---|---|
| tap copy | `$16` | `$17` | `$18` | `$19` | ✅ stride 1 |
| damping | `$3a` | `$3b` | `$3c` | `$3d` | ✅ |
| LO state | `$41` | `$42` | `$43` | `$44` | ✅ |
| interpolation carry | `$47` | `$48` | `$49` | `$4a` | ✅ |
| LFO fraction | `$24` | `$22` | `$57` | `$59` | ❌ irregular |

The odd one out is **not sloppiness** — it is the deliberate crosswise LFO
assignment (lines 0 and 2 on the inverse triangle, 1 and 3 on the forward, see
`REVERB.md` §Signal path). Fix by reordering the LFO state array so line *k*
reads slot *k* while preserving the same phase relationships. ⚠️ The **pairing
rule** applies here and it has already cost one bug: each line's interpolation
fraction must come from the same LFO as the integer offset its `nK` was built
from. Getting that wrong put a 1-sample sawtooth at ~76 Hz on two lines and
measured −29.6 dB — the loudest artifact ever found in this engine.

**Bonus: it frees registers.** `r1–r4` hold the four line pointers and `m1–m4`
*all hold the same `$fff`*. Rolled needs one pointer and one modifier, freeing
three address registers and three modifiers — which `REVERB.md` already wants
for the r7-access optimisation, and which is the tax that halved the v97
Hadamard's saving.

### Two things that will bite

- **`r7` is FULL.** The tank taps alone use **20 of its words for 4 lines**;
  8 lines wants 40, and `$84+` **hangs the DSP** ([[octamax-r7-slots-full]]).
  The extra state must go to **absolute Y in the server's own buffer** — a
  proven pattern (`dsp/cycleburn.asm` parks LFO and damping state there, and
  `DSP.md`'s v27 build showed absolute Y works where `r7+$84` hangs). There is
  exactly one server per bank, so absolute-Y scalars cannot collide.
  **The rolling re-layout and the r7-full problem have the SAME fix**, which is
  the argument for doing them together rather than in sequence.
- 🟡 **Nested `do`.** The tank loop would sit inside the existing
  `do n7,>END` sample loop. The 56300 supports nested hardware loops via the
  stack, but **verify it rather than assume it** — the failure mode here is a
  wrong RT60, not a crash, which is exactly the class of bug the `tfr a,b`
  mis-encoding produced and which reads as "voicing changed".

**Verification standard for this work**, since it is a pure refactor: the
rolled build must render **bit-identical** to the unrolled one at four lines,
across all four modes plus a `TIME=127 SIZE=127 DIFF=127` wet case. Add the
single-`nop` control that proves the comparison is not blind
([[octamax-assembler-traps]]). Only once that passes does the line count change.

## FX1 must keep working — and FILTER is probably NOT the worst case

**FX1 stays fully usable on all four tracks. That is a product requirement, not
a margin, so it comes out of the budget before anything is designed against it.**

⚠️ **FILTER is the only stock effect whose cost has ever been measured**
(~260 cycles each, 1,040 for four ✅). Treating `4 × FILTER = 1,040` as the
worst case is an assumption, and there are two reasons to doubt it:

1. **260 is already far more than a biquad should cost.** `CHIP.md` flags this
   ("much more than a filter looks like it should"). The likeliest explanation
   is a large **fixed per-call overhead every effect pays** — in which case 260
   is close to the *floor* for any FX1 effect, not the ceiling.
2. **Several stock effects plainly do more work.** 🟡 Ranked by structure, not
   measurement:

   | likely cost | effects |
   |---|---|
   | above FILTER | **MULTIBCOMP** (crossovers + multiple detectors), **COMB**, **FLANGER**, **PHASER**, **CHORUS** (modulated interpolated delay lines) |
   | near FILTER | EQ, DJ EQ (biquad stacks) |
   | below FILTER | SPATIALIZER, LO-FI, COMPRESSOR |
   | **free** | **DELAY** — it has no DSP code at all ✅ ([[octamax-stock-delay-mystery]]) |

   Of the 15 stock effects, 11 are live on FX1 for us (DELAY is a passthrough;
   PLATE/SPRING/DARK are our donors and are silenced).

**And the worst case to measure is not `4 × worst effect`.** A realistic kit
puts a *different* FX1 effect on each track. The number the design actually
needs is one reading: **four different heavy FX1 effects, one per track, plus
the bank — sweep once.**

**This costs ONE flash, not eleven.** The burn probe is a front-panel
instrument: once a `BURN=1` build is on the card, every configuration is a knob
sweep with no further flash ✅ (`CHIP.md` §2). Sweep the loaded kit, then sweep
a few single-effect ×4 configurations to find which effect is actually the
ceiling.

**Until that reading exists, budget the reverb at ~1,200 cycles, not 1,500** —
1,040 is a measured floor for the FX1 load and the real figure can only be
higher. The 8-line tank is estimated at ~1,250 🟡, so **this measurement is
what decides whether 8 lines fits**, and it should be taken before the tank is
rewritten, not after.

**Not in scope: the three stock reverbs.** PLATE / SPRING / DARK are our
donors (594 / 1,063 / 1,067 words ✅) and stay taken — losing them on FX1 is
accepted, and "FX1 must work" means the other eleven effects and the cycles
they cost. Do not re-open this to give donors back; core 0 has none to give
anyway (ChonVerb + SEND = 2,230 against PLATE+SPRING = 1,657).

## What to build with it — the delay

BongDelay was scoped as an afterthought (507 words, 163 cycles, a placeholder)
and **has still never been heard**. It should not get its first audition
against the old budget. Payload B gives it:

- **2,005 free program words** — five times its current size
- **~3,176 spare cycles** — nineteen times its current cost
- **65,536 words = 1.49 s**, as two 32,768-word modulo lines (`Y:0x8000` and
  `Y:0x38000` are both 32K-aligned ✅) or one 1.49 s line with a manual wrap

That is a flagship budget, not a placeholder's: multi-tap, stereo ping-pong,
per-tap filtering, tape wow/flutter, diffused or pitch-shifted feedback,
reverse. **Re-scope the delay before designing it.**

## Memory re-plan (step 4), concretely

The shared window is not flat. Three things to dodge, all already mapped:

| range | what | verdict |
|---|---|---|
| `0x30000-0x30047` | stock's per-frame parameter staging, 72 words, **rewritten EVERY FRAME** ✅ | never usable |
| `0x31000` / `0x32000` | bootstraps A and B, 50 / 58 words ✅ | dead after boot, usable |
| `0x34000` | ~~a single word written here corrupts audio after ~5.45 s~~ ❌ **RETRACTED 8 Aug** — v107's own bisect covered this exact address with ONE instance and found it clean; the fault was always duplication (`CHIP.md` §6) | **usable** |

**The bus scratch needs a permanent home, and there is a free one.** It sits at
`0x36000` today, which is inside the reverb's new `0x34000-0x37FFF` block. But
`0x30000-0x300FF` is already unusable for modulo buffers (stock's staging is in
it), so put the 133-word scratch at `0x30080-0x30104` and reserve
`0x30000-0x301FF`. **Cost to the reverb: 512 of 65,536 words, 0.8%** — versus
carving a hole out of a power-of-2 buffer anywhere else.

The rest of `0x30000-0x33FFF` then carves as a buddy allocator with alignment
intact: 8K at `0x32000`, 4K at `0x31000`, 2K at `0x30800`, 1K at `0x30400`,
512 at `0x30200`. **16,256 of 16,384 words recovered.**

**Contention is free if the split is respected** — the manual guarantees no bus
contention when the two cores touch different 8K blocks ✅. Reverb in blocks
0–3 (`0x30000-0x37FFF`), delay in blocks 4–7 (`0x38000-0x3FFFF`) satisfies it
exactly, except for the scratch, which both cores must touch by definition:
133 words in block 0, negligible.

## The four things that could bite, in order

1. ~~**`Y:0x34000` corrupts audio after ~5.45 s.**~~ ❌ **DEAD, 8 Aug 2026 —
   and it was dead before it was ever ranked here.** `dsp/shared_probe.asm`'s
   `ADDR = 0` *is* `0x34000`, and v107's bisect row "one `SharePrb` + three
   `Send`s → clean at every ADDR and INC" therefore already measured a single
   instance writing that exact word, clean. The two builds that "reproduced"
   it both had two instances running — `04a24cf` says so itself. **The
   reverb's pool is not blocked and this costs no flash.** Full retraction in
   `CHIP.md` §6.
2. ~~**`dsp_host` cannot boot payload B.**~~ **MITIGATED — the `DEV=1` hatch is
   built.** The risk was real: `XBUS=1` stubs the delay out, and the specialized
   build puts BongDelay in payload B only, which `dsp_host` cannot boot
   (`REVERB.md`) — so the delay would have lost its local render loop exactly
   when it needed one.

   `DEV=1` keeps all three servers real in both payloads and dumps
   `out/dsp/mem_dev_A.mem` beside the image. It pays for the space by taking
   **CHORUS back as a fourth donor** (329 words, immediately below PLATE and
   contiguous with it — the build asserts that rather than assuming it), because
   SEND + REVERB + a gated DELAY is **2,744 words against the 2,724** the three
   reverbs alone provide. That costs FX1 its chorus, so a DEV build writes
   `out/mainos_bus_dev.bin`, never `out/mainos_bus.bin`, and refuses to combine
   with `BURN`/`PROBE`/`XPROBE`/`DELAYPROBE`.

   `send_probe.py --layout` now takes **`D`** alongside `R` and `S`, and
   `--dlevel` drives the `→DELAY` send (`x:(r6+0)`) — a separate knob from
   `→REVERB` (`x:(r6+1)`), which is why the first run rendered silence.

   ```sh
   DEV=1 XBUS=1 python3 tools/build_bus.py
   python3 tools/send_probe.py --mem out/dsp/mem_dev_A.mem --layout DS
   ```

   ✅ **Verified: BongDelay produced audio over the bus for the first time** —
   peak 0.074 FS, −14.6 dBFS, THD −35.2 dB, against **digital silence** on a
   non-DEV image. And the existing reverb path is **bit-for-bit unchanged**:
   `--layout RS` against `HEAD`'s script and the new one agree to every digit
   (peak 0.243, −15.2 dBFS, THD −11.08, same spurs). SEND vs DIRECT at 0.15 FS
   is −36.18 vs −36.17 — the send path is still faithful; the −11 dB at 0.5 FS
   is the known tank saturation above ~0.35 FS, not a regression.
3. **Asymmetric payloads make the menu a footgun.** Selecting ChonVerb on
   track 6 would dispatch into whatever now occupies that address in payload B.
   The mechanism to prevent it already exists and is proven — the null stub
   (`nul_i`/`nul_p`) and the id-0 → SEND aliasing. Wire ChonVerb → SEND on
   payload B and BongDelay → SEND on payload A, deliberately.
4. **`tools/cycle_count.py` still prints `budget/DSP 1080`**, a number
   retracted twice. It will report a design that fits as over budget. Fix the
   constant before anyone uses it to make a decision.

## Recommended order

1. ~~**`DEV=1` local-render escape hatch for the delay**~~ — **DONE**, see
   risk 2 above. BongDelay now renders locally for the first time.
2. **One `BURN=1` flash, then sweep.** Now settles ONE thing, not two —
   `Y:0x34000` was retracted from the docs rather than measured (risk 1). What
   remains is **the real FX1 worst case**, which decides whether 8 lines fits.
   Sweep the loaded kit first, then a few single-effect x4 configurations to
   find which stock FX1 effect is actually the ceiling. The burn knob is a
   front-panel instrument: one flash, then every further configuration is a
   knob sweep.
3. ~~**Specialize the payloads.**~~ ✅ **DONE, 8 Aug 2026 (v123, `SPEC=1`).**
   `XBUS=1 SPEC=1 python3 tools/build_bus.py`: payload A carries SEND +
   ChonVerb (**FREE 494**), payload B SEND + BongDelay (**FREE 1998**). The
   absent server's id is aliased to SEND on each core, which is risk 3's fix
   applied rather than deferred. Predicted 494 / 2,005; the 7-word gap on B is
   the delay's XBUS gate. The plain build is byte-identical with the flag off.
   **Not yet flashed.**
4. **Roll the reverb's tank loop**, and move the per-line state to absolute Y
   in the same pass — the two have the same fix. Cycles for words at a very
   good rate, and it is what makes 8 lines affordable rather than marginal.
   Gate: bit-identical to the unrolled build at four lines. See the section
   above for the strided state layout and the two traps.
5. **Eight lines.** The first real audible step the memory buys.
6. **Re-scope BongDelay against its actual budget**, then audition it.

## Still open, and unchanged by any of this

- **BIG rings.** ~30 dB more HF than the other modes with no shimmer: a dense
  cluster of non-harmonic lines at 2–2.8 kHz. `md_big` sets the decay scale
  `x:(r7+$1e)` to `$7FFFFF` = exactly 1.000000 where ROOM/PLATE/HALL leave
  headroom (0.920/0.965/0.980). NOT simple runaway feedback — HF *falls* as
  TIME rises and is already high at TIME=0, so suspect the input/early path.
- **Tank saturation above ~0.35 FS.** The only level limit left since v121.
- **The DELAY accumulator has no auto-gain.** Same fix as v121; fold it into
  the delay re-scope.
- **Emulator/device alignment.** The proven gap is parameter delivery:
  `-params` pokes `r6` directly so every slot looks live locally, while on
  hardware a slot can draw a knob and publish nothing.
- **Flash a build carrying v121.** The card holds `OCTATRACK_NOSHIM31.bin`,
  which predates the bus auto-gain.

~~**Hard constraint: the payload region is FULL, one spare word.**~~
**Retracted by specialization, and now BUILT** — 494 free on A, 1,998 on B
(`SPEC=1`, v123, 8 Aug 2026).

## Constraints that shape it

- **`0x36000` is inside core 0's FX2 slot 4.** Fine while every core-0 track is
  ChonVerb (hardcoded `Y:0x4000`) or a Send (zero-footprint). NOT fine once the
  reverb pools all four slots — the accumulators need a permanent home that is
  not an FX2 slot. Candidate: the free low-Y window `0x795-0xFFF` is core-
  private and therefore useless here; this needs solving in step 4.
- **Modulo addressing needs power-of-2 alignment**, so a 16,384-word buffer in
  the shared window must start at `0x30000` or `0x34000`. `0x34000-0x37FFF` is
  clean; `0x30000-0x33FFF` has the staging in its first 72 words.
- **The two regions are not contiguous** (`0xC000-0x2FFFF` is absent), so no
  single 65,536-word buffer. Irrelevant for a bank of separate lines.
- **Series is one-directional**: delay wet → reverb is allowed and built;
  reverb wet → delay is forbidden, it closes a feedback loop.
- **One block of latency already exists** by design (everyone reads the
  previous block's summed buffer). Cross-core adds at most one more. ~0.36-0.7
  ms; inaudible for a send.
