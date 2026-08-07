# The target architecture: one reverb, one delay, all eight tracks

Agreed 7 Aug 2026. This supersedes `BUS.md`'s bank-scoped design, whose founding
constraint — "the two DSPs are a hard boundary" — is now known to be false.

## What we're building

```
CORE 0   track 1   ChonVerb      pools all 4 of core 0's FX2 slots  = 65,536 words = 1.49 s
         2,3,4     Send
CORE 1   track 5   BongDelay     pools all 4 of core 1's FX2 slots  = 65,536 words = 1.49 s
         6,7,8     Send

         every track sends to both, through accumulators in the shared window
         delay wet -> reverb  (series, the direction that is already built)
```

**Two wins, and they are different resources.**

*Cycles*: each core runs ONE effect with its full ~4,535 cycles/sample instead
of both cores running both effects. Roughly doubles the effects budget.

*Memory*: 372 ms → 743 ms (done, the 32K re-layout) → **1.49 s**. Four slots per
core instead of two, because a core no longer has to house a reverb *and* a
delay.

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

## Path, in order, with the gate at each step

0. ~~Find the metallic artifact.~~ **DONE** — it was the shimmer, stuck
   half-on and unturnoffable; excised by default, hardware-confirmed gone.

1. **Does the relocated bus still work SAME-CORE?** ← *cannot be judged until 0
   is fixed; the artifact appears on the plain build too.*
   `XBUS28` put the scratch at `0x3E000` and it broke even with both effects
   on ONE core — so cross-core was innocent and the address was the fault.
   `0x3E000` is outside the init pass that zeroes `0x30000-0x37FFF` (so it
   comes up as garbage) and payload A had never been shown to write there at
   all: `alias_probe` only ever tested payload A in the LOWER half. `XBUS29`
   retries at `0x36000` — inside the zeroed region, and between two addresses
   payload A has demonstrably written and read back. **Nothing below means
   anything until this is clean.**
2. **Does a cross-core send arrive?** Send on track 5, reverb on track 1.
   Already known to carry *something* — it scaled with the send dial — so this
   is about whether it arrives *intact*.
3. **Synchronisation.** Expected to be needed. The two cores have independent
   splits and block alignment, and the bus's frame offset is per-track; a
   cross-core send cannot use it. The ICC (cross-core interrupts + data
   registers, RM 1.4.14) is the untouched tool for this.
4. **Re-plan the memory** against `CHIP.md` §3a — four slots per core, in two
   non-contiguous regions, dodging stock's 72-word staging at
   `0x30000-0x30047` (rewritten EVERY FRAME) and using the fact that the
   bootstraps at `0x31000`/`0x32000` are dead after boot.
5. **Then the effects**: the shimmer (the reverb is not finished — the shimmer
   verb is not usable), and BongDelay, which is an untested first draft.

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
