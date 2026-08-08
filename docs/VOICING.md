# ChonVerb per-mode voicing log

The last open item on the reverb (`REVERB.md`): MODE's per-mode constants —
tap scale, early-reflection level, diffusion offset — are first-pass, chosen by
analysis rather than by ear. This file records what was actually decided by
listening, and why, so a later session doesn't re-litigate settled ground or
mistake a measured claim for a heard one.

**Loop**: one hypothesis per round, the minimum listening needed to settle it,
one answer recorded, constants adjusted, re-render. Renders are local
(`tools/render_reverb.py --mode all`, ~8 s for all four) so nothing here costs a
flash. Hardware still has the last word on anything at the cycle-budget or UI
layer — see `REVERB.md`.

**Sources** (card, `PRESETS/AUDIO/Legowelt Dry/`, all 16-bit/44.1k mono):
`LW Snare 094` transients → early reflections · `LW Stab Microdot` pluck →
buildup · `LW Pad Softspoken` sustained → tail density.

## The constants under test

`dsp/reverb_server.asm`, the `md_*` block. Three values per mode:

| mode | tap scale | early reflections | diffusion offset |
|---|---|---|---|
| ROOM | `$399999` 0.45 | `$600000` strong | `$0c0000` high |
| PLATE | `$530000` 0.65 | `0` none | `$100000` highest |
| HALL | `$730000` 0.90 | `$200000` weak | `$060000` medium |
| BIG | `$7fffff` 1.00 | `0` none | `$040000` lowest |

## Measured before any listening

Wet-only RMS by window, defaults, synthetic pluck. This is what the constants
*do*; whether it is what they *should* do is the point of the rounds below.

| mode | 20–60 ms | 0.5 s | 2 s |
|---|---|---|---|
| ROOM | −12.6 | −21.0 | −33.9 |
| PLATE | −16.7 | −19.6 | −34.7 |
| HALL | −15.4 | −22.9 | −31.3 |
| BIG | −16.8 | −29.3 | −32.8 |

The 20–60 ms column tracks the ER constant exactly, including PLATE and BIG
(both ER=0) landing 0.1 dB apart — so the MODE override is genuinely reaching
the engine, and these are the real constants rather than a stuck build.

## Rounds

### Round 1 — level matching, and whether BIG is big or just thin

**Hypotheses.**

1. The four modes are not level-matched, consistently in one direction: ROOM
   loudest on every source (peak 0.45/0.46/0.59), PLATE and BIG quietest
   (0.35/0.35/0.46) — 1–2 dB RMS, up to 2.4 dB peak. That is ROOM's early
   reflections adding energy to the wet sum. Two consequences: turning MODE on
   hardware changes loudness as well as character, and every A/B in this file
   is biased until it is settled, because louder reads as better.
2. BIG may read as thin rather than vast — 8 dB below the others at 0.5 s but
   louder at 2 s, i.e. a long slow buildup. Correct in principle for a large
   space; the question is whether it just sounds absent at the front.

**Listening**: BIG vs HALL on the stab, wet only, level-matched, alternated
twice. Wet-only mattered: the first attempt was wet+dry at MIX=64, where the dry
masks the character and the two were genuinely hard to tell apart — judge modes
wet, or the source drowns the thing being judged.

**Answers.**

1. **Level: match, but only roughly** — pull the worst outlier in, leave some
   natural variation between characters.
2. **BIG vs HALL: too close to call**, even wet and level-matched. That
   supersedes the "is BIG thin" question: the modes are **under-differentiated**,
   which is a bigger finding than any one mode's buildup, and it changes what
   gets tuned first. Hypothesis 2 is neither confirmed nor rejected — it cannot
   be judged until the modes are actually distinct.

**Diagnosis, from the constants rather than from the ear.** Tap scale sets the
space: `tap = 3958 × f × mode_scale`, with SIZE giving `f = 0.400..0.989`.

| step | ratio | tap range (longest line) |
|---|---|---|
| ROOM 0.45 | — | 713–1761 samples, 16–40 ms |
| PLATE 0.65 | 1.44× | 1030–2544, 23–58 ms |
| HALL 0.90 | 1.38× | 1425–3522, 32–80 ms |
| BIG 1.00 | **1.11×** | 1583–3914, 36–89 ms |

HALL and BIG are 11% apart in tap length, against ~40% for every other step.
An 11% size difference is not audible as a different space, which is exactly
what was heard. BIG is already at the `$7fffff` ceiling, so it cannot move up.

Spreading downward is bounded too: v77 deliberately RAISED the SIZE floor
because small spaces were metallic ("smallest size sounds worst", and at
SIZE=16 nearly half the spectrum's energy sat in 1% of the bins). ROOM's floor
is already 713 samples against the 566 that was measured bad, so there is not
much room beneath.

**The actual gap: the implementation is a subset of the agreed design.**
`REVERB.md` specifies that MODE "should reconfigure tap lengths, diffusion
depth, damping and modulation together — not merely rescale SIZE". The `md_*`
blocks set three things: tap scale (`r7+$6f`), ER level (`r7+$6c`) and
diffusion offset (`r7+$3f`). **Damping and modulation were specified and never
wired in.** Those are the two that most separate a plate from a hall from a big
space — a large room is darker and more moving in the tail, not merely longer.
Nudging tap scale within its remaining headroom cannot buy what those two would.

**Next**: add per-mode damping and modulation depth, then re-run this A/B.

### Round 2 — the respread, and a real bug found by ear

Changes made (v95, `dsp/reverb_server.asm`):

- **Diffusion double-add fixed.** The mode offset was added to `g` twice. The
  span above it is sized so `base + full DIFF + largest offset` lands at
  0.352+0.326+0.125 = 0.802 — the "under ~0.80" its own comment claims, and
  true only with ONE add. The second put PLATE at 0.93 at DIFF=127, inside the
  near-oscillator range the same comment warns about.
- **Tap scales respread**: PLATE 0.65 → 0.5625, HALL 0.90 → 0.72. Steps are now
  1.25× / 1.28× / 1.39× where HALL→BIG had been 1.11×.
- **Per-mode damping (`r7+$72`) and mod depth (`r7+$73`) wired in**, as
  `REVERB.md`'s design always specified.

**Two things measurement caught that the ear would have taken longer to.**

1. *Damping is per-pass; brightness is per-second.* The first damping constants
   made BIG measurably **brighter** than HALL despite a darker coefficient,
   because shortening HALL's lines raised its circulation rate ~39% and it
   therefore damps more often per second. Retention over equal time goes as
   `c^(1/tapscale)`, and the constants are now chosen on that.
2. *Damping has little spectral authority here anyway.* Sweeping the LP knob
   across its **entire** range moves the tail's >3 kHz energy ratio only
   0.035 → 0.046. So per-mode damping cannot be the differentiator this file
   assumed it would be. The tap respread is doing the real work.
   **[RETRACTED in Round 3 — this is false.]** Measured with a proper FFT the
   LP knob moves the 3–8 kHz tail by **56 dB**. The 0.035 → 0.046 figure came
   from an analysis that aliased everything above 2756 Hz. Damping turned out
   to be the strongest differentiator available, and acting on this claim cost
   two rounds. See Round 3.

**Verdict by ear**: BIG and HALL are now different but "hard to quantify, not
super different". Still short of the goal. Deliberately left there, because the
same round turned up something worse.

### Round 2b — modulation is generating broadband noise (PRE-EXISTING BUG)

Heard as "crackle or static, not super loud, heavier at the start" on the pad.
Chased properly rather than guessed at, and each step ruled something out:

| test | result |
|---|---|
| clipped samples | **0** — peaks −0.48/−1.00 dBFS |
| max sample-to-sample step | 0.047 FS — no overflow wraparound |
| tail envelope | smooth ~3 dB/0.5 s down to −79 dBFS — no limit cycle |
| input cut 12 dB, gain restored after | **unchanged** — not a level-dependent overflow |
| dry source alone | **clean** — not the sample |
| **MOD=0 vs MOD=40, level-matched** | **crackle only with modulation on** |

**It is not mine.** HALL's mod-depth scale is unity in v95, so its modulation
path is byte-identical to `ChonVerb19` — the build already on hardware.

**Mechanism**: `dsp/reverb_server.asm:1112` gates the LFO advance on the call
flag, so the modulation offset is constant within a block and jumps at every
block boundary. The delay-time derivative is a staircase rather than a ramp,
which radiates energy at the block rate (~2.8 kHz) and its harmonics. All four
lines *are* interpolated (the header's "two lines" is stale), so this is the
stepping itself, not missing interpolation.

**Corroborating measurement**: on the tail excerpt, MOD=0 needed **+11.6 dB**
to match MOD=40. Smearing does not add 12 dB to a tail; injected broadband
noise does.

**Fix, not yet built**: advance the LFO per sample, or interpolate its value
across the block so the delay time ramps instead of stepping. Per-sample is
cheaper to reason about but costs cycles in the sample loop, which
`REVERB.md`'s budget rules say must be counted statically rather than guessed.

**This supersedes further voicing.** Tuning mode constants against a tail with
broadband noise in it means voicing the noise as much as the reverb.

### Round 2c — two wrong causes, then the likely real one

**Wrong cause 1: block-stepped LFO.** Plausible, unproven, and not acted on.

**Wrong cause 2 (but a real bug, fixed): the interpolation fraction shift had
regressed.** All six sites computed the fraction with `asl #$8` where `n = 8`
for the integer part and the mask is `2^(24-8)-1`, so the fraction must scale by
`2^7`. `REVERB.md`'s "interpolation fraction rule" documents this exactly and
records it as **live from v72 to v79** — it had come back, with the rule written
in the comment directly above the offending shift. Now `asl #$7` at all six.
**Kept, because it is correct, but it did NOT fix the crackle.**

Also recorded honestly: the "+11.6 dB with modulation on" figure was cited as
corroboration that modulation injects noise. It is not — after the fraction fix
the gap is +11.97 dB, essentially unchanged, and modulation legitimately adds
tail energy by breaking up modal cancellation. That inference was too quick.

**The likely real cause, not yet fixed.** `dsp/reverb_server.asm:1567`: "The
interpolation partner needs no second address: the read pointer advances one per
sample, so d1 THIS sample is d0 LAST sample." That holds only while the delay
offset is CONSTANT. Each time the modulation's integer offset steps by one
sample, the carried `d1` was read at a different delay position, so that
sample's interpolation is built from a mismatched pair — a one-sample error.
The offset traverses ~76 samples/s, so across four lines that is ~300 events/s:
faint, broadband, signal-proportional, and gone at MOD=0. It fits every
observation and every negative test above.

**Fix to try**: read the real partner (`n1 ± 1`) instead of carrying the
previous sample — one extra Y read per line per sample, 4 per sample total.
Count it statically against the budget first (`REVERB.md`), since the carried
partner exists precisely to avoid that read.

**Caution from `REVERB.md` before "cleaning up" modulation artifacts**: the v72
fraction bug "was also doing something useful ... it is a noise source, and
interpolation dither is a real technique for breaking up delay-line artifacts.
Every build the user liked had it." Removing this class of noise may expose
ringing that it was masking. If so, the principled replacement is deliberate
randomisation, not restoring a bug.

### Round 2d — the interpolation partner is measured, fixed, and exonerated

Round 2c's "likely real cause" above is **wrong**, on two independent grounds.
The full measurement is in `REVERB.md`; the short version:

**The four tank lines were never exposed.** They are seeded before the loop,
one sample further back with the new offset — which is exactly the block
boundary the carry argument fails at — and the offset cannot change mid-block.
The suspect line 1567 quoted above is immune. Deleting the seed reads *does*
change the output, so that priming is load-bearing, not vestigial.

**The two in-loop allpasses (v90) genuinely had the bug** and are now primed
the same way. Cost: 28 instructions per *block*, outside the sample loop, so
zero against the cycles/sample budget — the "one extra Y read per line per
sample" costed above was never needed. Verified correct by forcing the allpass
LFO depth to zero, which makes the prime a no-op: ref and fixed renders come
out **bit-identical**, which a wrong address could not do.

**But it is not the crackle.** Isolated at MOD=0 (where the allpass depth is
fixed and still stepping, but the tank is not), the correction *is* a click
train — crest 28.0 dB against the tail's 10.8 dB, exactly the predicted shape
— but at −94.7 dBFS RMS under a −30.5 dBFS tail. ~64 dB down. Inaudible.

**The observation that should have settled this was already on this page.**
Round 2b: the crackle is *gone at MOD=0*. The allpass depth never follows MOD,
so this defect is fully active at MOD=0 and cannot be a fault that disappears
there. That ruled it out before any of the above was rendered.

**So: back to wrong cause 1.** The block-stepped LFO is the leading candidate
again, by elimination rather than evidence. It is the only mechanism left that
survives the MOD=0 test. Note the two were never rivals — both come from the
offset being piecewise-constant per block. Priming fixed the boundary *sample*;
the delay time is still a staircase in between, and that is the larger signal
by far.

### Round 2e — wrong cause 1 is ALSO wrong; the pairing is the real one

Round 2d's "back to wrong cause 1" lasted one round. Building it settled it.

**The block-stepped LFO was implemented and measured: −62.5 dB.** Each line
carries a running packed position (integer offset in the top 8 bits, fraction
in the low 16) and walks 1/16 of the way to the block's target every sample,
so the delay time ramps instead of stepping. Verified by an invariant: at
MOD=0 there is nothing to ramp, and the rebuilt engine is **bit-identical** to
the old one — which it can only be if every offset, fraction and `nK` still
lands exactly where it did. Cost: 64 cycles/sample.

It changes the tail by **−62.5 dB**, the same order as the allpass carry fix
in Round 2d, and moves the 8–16 kHz band by +0.01 dB. The staircase is real
and inaudible. In hindsight the arithmetic said so: the offset traverses
~76 samples/s, so across one 15-sample block it moves ~0.026 of a sample.
**Not kept — 64 cycles/sample for −62.5 dB is a bad trade.**

**The real one: lines 0 and 2 took their interpolation fraction from a
DIFFERENT LFO than their integer offset.**

| line | integer offset | fraction | |
|---|---|---|---|
| 0 (`r1`) | `$23` LFO B | `$57` LFO **C** | wrong |
| 1 (`r2`) | `$21` LFO A | `$22` LFO A | ok |
| 2 (`r3`) | `$56` LFO C | `$24` LFO **B** | wrong |
| 3 (`r4`) | `$58` LFO D | `$59` LFO D | ok |

B's and C's fractions were swapped. The effective delay of lines 0 and 2 was
`tap + offset_B + fraction_C`, and a foreign fraction is a sawtooth that wraps
every time *its* LFO's integer steps — so those two lines carried a 1-sample
sawtooth on their delay at ~76 Hz.

**−29.6 dB**, against −62.5 and −64 for the two structural candidates: 33 dB
louder than anything else found, and the only one with the magnitude to be
audible. It passes every negative test in Round 2b — vanishes at MOD=0,
signal-proportional, broadband, not the sample. Fix is a two-slot swap, no
cycles, no words.

**Not yet judged by ear, and this one needs it.** It is exactly the shape
`REVERB.md` warns about: an accidental noise source that may have been doing
perceptual work. `ChonVerb19` — the build on hardware, the one that was liked
— has this bug. Removing it may expose ringing the sawtooth was smearing, in
which case the answer is deliberate randomisation, not putting the swap back.

**Method note.** Three candidates, three magnitudes, one ranking: −29.6 dB
beats −62.5 and −64 by more than 30 dB. None of it needed a flash, and the two
that lost were the two that had been reasoned about most confidently.

### Round 2f — heard: the pairing WAS the crackle

A/B/A/B on the pad, wet only, both peak-normalised to −1 dBFS, first 8 s.
**Verdict: "yes, fixed in B."** Round 2b's crackle is closed — it was the
foreign-LFO fraction on lines 0 and 2, and the two-slot swap is the fix.

Worth keeping for the method: the fault was found by measurement (−29.6 dB,
33 dB clear of two structural candidates) and confirmed by ear, and the two
candidates that lost were the two that had been argued for most confidently
in Rounds 2c and 2d. Neither cost a flash.

**Open: did removing it expose ringing?** The v72 caution applies directly —
the sawtooth was an accidental dither and `ChonVerb19` has it. First listen on
the 4–12 s tail was inconclusive ("would need another couple listens").

The measurement leans toward yes but **cannot settle it, for the reason
`REVERB.md` already records about spectral flatness.** Peak-to-median bin
energy over 200 Hz–6 kHz in the late tail:

| | 5 s | 7 s | 9 s | mean |
|---|---|---|---|---|
| A, sawtooth present | 52.8 | 51.7 | 49.9 | 51.5 dB |
| B, paired | 59.9 | 58.7 | 54.2 | **57.6 dB** |

+6 dB more modal contrast in B, which is what exposed ringing looks like —
but A's broadband noise raises the **median**, which compresses the ratio on
its own, with or without any change in the modes. This metric has exactly the
flaw this file's own rule warns about, only in the numerator's favour rather
than the denominator's. It is a hint, not a finding. **Settle it by ear, or
with a metric that tracks narrowband DECAY RATE rather than level contrast.**

**Settled by ear: nothing was exposed.** Second pass on the same 4-12 s tail,
three rounds, A then B: *"sound the same as far as ringing goes."* So the
+6 dB of peak-to-median contrast was the **median moving**, not the modes --
the old build's broadband noise had been sitting on the floor and lifting it,
and taking it away raised the ratio without touching what rings. The metric
was confounded exactly as suspected, and the ear settled it in one pass.

**Do not build the narrowband decay-rate metric on this evidence.** It was
proposed to break this tie and the tie no longer exists.

**This lifts Round 2b's block on voicing.** "Tuning mode constants against a
tail with broadband noise in it means voicing the noise as much as the
reverb" -- the noise is gone, the tail did not get worse, and the per-mode
constants can be judged on their own terms again. Round 1's finding stands as
the open question: the modes are **under-differentiated**, and damping was
measured to have little spectral authority, so tap scale is doing the work.
(That damping claim is RETRACTED — see Round 3; it was an aliasing artifact.)

**And a counter-example worth keeping.** `REVERB.md`'s standing caution --
that removing an accidental noise source may expose ringing it was masking,
because "every build the user liked had it" -- did NOT hold this time. The
caution came from the v72 fraction bug and is real, but it is a thing to
CHECK, not a thing to assume. Checking it cost two listens.

### Round 3 — per-mode tap spread and the damping that was never the problem

**Hypothesis**: the modes shared one modal *pattern*. The four line lengths were
hardcoded once (`1.000 : 0.855 : 0.731 : 0.625`, spread 1.60:1) and every mode
multiplied all four by a single scalar, so MODE could only *transpose* the space,
never reshape it. Wired the four tap fractions into `r7+$74..$77` and gave each
mode its own spread. Costs nothing — the SIZE section now reads them from `r7`
instead of four two-word immediates, which is a cycle *cheaper* each.

**First attempt was wrong, and the measurement caught it.** Pinning the longest
tap at 3958 in every mode and shortening the other three changed each mode's
*mean* delay (PLATE +12%, BIG −13%), so the new spread lever pushed straight
against the tap-scale lever already carrying the differentiation. Mean pairwise
separation went DOWN (spectral 3.85 → 3.72, buildup 4.16 → 3.21). Fix: hold the
mean tap at ROOM's 3178 in every mode, so scale and spread are independent.
Corrected version measures 4.24 / 4.42. **ROOM is unchanged and renders
bit-identical**, which is what verifies the `r7` indirection.

By ear: "still too close" for PLATE vs HALL — which was also the weakest pair in
the measurement (2.98 spectral, the lowest of six). Ear and metric agreed.

**Then two measurement errors of my own, both worth recording.**

1. *Analysed a still-playing source as a tail.* The pad is 10 s long; the decay
   was being measured at 1.0–3.5 s. Use `stab` (0.57 s) or window after the
   source ends.
2. *The DFT was aliasing.* For speed the band analysis summed over every 8th
   input sample, which folds everything above 44100/16 = **2756 Hz** back down.
   Every "hi" and "air" figure above that was meaningless — the giveaway was the
   air column reading *exactly* 3.2 dB at every knob position. Replaced with a
   real radix-2 FFT (`spec.py` in the scratchpad).

**Consequence: `REVERB.md`'s "damping has little spectral authority" is WRONG,
and so was the version of it I reported before fixing the FFT.** Measured
properly, the LP knob moves the 3–8 kHz tail by **56 dB**:

| LP | 800 Hz–3k | 3k–8k | 8k–16k |
|---|---|---|---|
| 0 | −98.0 | −105.2 | −107.6 |
| 64 | −22.1 | −88.7 | −97.4 |
| 127 | −19.2 | −48.9 | −87.6 |

**The real cause of PLATE ≈ HALL was mundane.** Per-second retention is
`c^(1/tapscale)`. PLATE sat at 1.000 and HALL at 0.861 — **14% apart on a
control with 56 dB of range**. Nothing else they differ in could overcome
sounding like the same brightness. HALL 0.90 → 0.70 per pass (0.607 per second)
opens the 3–8 kHz gap from ~4 dB to **20.2 dB**, with the per-second ordering
preserved: PLATE 1.000 > ROOM 0.882 > HALL 0.607 > BIG 0.445.

**By ear: "a little better ... acceptably different now, but not different like
the modes in the CXM."** So the constants are no longer the binding constraint;
the shared *structure* is. Three things are still identical in every mode:

- **Early reflections** — six taps at FIXED positions, only the level varies. A
  near wall and a far wall currently arrive at the same time.
- **Diffusion** — four input allpasses at fixed taps and a fixed 1.6:1 packing,
  plus two in-loop allpasses at 298/446. Only the coefficient varies.
- **Modulation** — one fixed set of LFO rates. Only depth varies, and a plate's
  shimmer is a different RATE from a hall's drift, not a different depth.

**Method note.** Three measurement errors this session (decimal-for-hex slot
numbers, a still-playing source, an aliasing DFT). Two were caught by invariants
that should have been cheap habits from the start: *make the change a no-op and
require bit-identical output* caught the first, and *a column that does not move
at all is a broken measurement, not a null result* caught the third.

### Round 4 — the modes finally separate, and it was decay all along

Round 3 left the constants no longer binding and the shared *structure* binding
instead. Four things were made per-mode. Three were the ones predicted; the
fourth was not, and it was the one that mattered.

**1. Early-reflection ARRIVALS.** The six ER taps were fixed at
331/557/919/1301/1723/2213 in every mode with only their LEVEL varying — a near
wall and a far wall arrived at the same time and differed only in loudness.
Now ROOM 4.5–21 ms (tight cluster), HALL 20–77 ms (late, sparse), all prime,
all inside the 4096-word pre-delay.

**2. Input diffuser taps.** The four series allpasses were fixed at
1994/1706/1438/1226; only the coefficient varied, so every mode built echo
density identically. Now PLATE shortest (1447/1259/1103/953), BIG longest
(2011/1789/1531/1297).

**3. LFO rate.** Only depth varied per mode. A plate's shimmer is a different
RATE from a hall's drift. PLATE 1.00 → BIG 0.25.

By ear after those three: *"PLATE is better, and ROOM vs HALL is the weakest
pair"* — which is exactly what the metric said (3.72, lowest of six). Ear and
measurement have now agreed on the weakest pair twice running.

**4. DECAY TIME — the one MODE never touched at all.** Measured at TIME=64 the
four modes ran **6.9 / 9.8 / 10.3 / 11.6 s**, and even that spread was
incidental: shorter lines circulate more often, so they decay faster at the same
`g`. Nothing in `md_*` set decay. Decay time is the single biggest room-vs-hall
cue, so ROOM vs HALL was always going to be the weakest pair however the other
five levers were set. A ROOM with a 6.9 s tail is a cathedral.

Per-mode scale on the feedback gain: ROOM 0.92, PLATE 0.965, HALL 0.99, BIG
1.00. Result **2.7 / 4.7 / 7.7 / 10.0 s**. Scaling `g` DOWN is always safe; it
is scaling up that self-oscillates.

**By ear: "much better!"** Six levers now vary per mode, against three at the
start of the session (tap scale, ER level, diffusion coefficient).

**The r7 block is FULL, and the pattern that got round it.** `$7e..$81` were the
last free slots and went to the diffuser taps; `r7+$84..$8a` **hangs the DSP**
(host-owned, `DSP.md`). The LFO rate and decay scale needed no slot at all: the
`md_*` block writes its scale into the slot the later parameter block is going
to overwrite anyway (`$2f` for rate, `$1e` for decay), and that block folds it
into its own multiply. Setup order makes it safe — `md_*` runs before every
parameter block. **Anything else per-mode has to use this trick or free a slot.**

**Method note — say what is playing BEFORE it plays.** Announcing the order in
the message *after* an A/B is useless: the text arrives when the audio is over.
Speech synthesis between clips was worse (truncated and distracting). Settled on
a non-verbal count-in: N short 880 Hz pips = mode N (1 ROOM, 2 PLATE, 3 HALL,
4 BIG), then the clip. `pip1..4.wav` alongside `gap.wav` in the scratchpad.

### Round 4b — BIG gets its early reflections back

One constant. BIG's ER level 0 → **0.19**, just under HALL's 0.25, firing into
the 39–92 ms taps Round 4 gave it and which had been sitting unused.

The old reasoning was "a big space has no close walls to hear" — true of CLOSE
walls, false of the space as a whole. A large hall's reflections are faint and
**late**, and lateness is the cue that says *vast* before the tail arrives.

By ear: **good, kept.** The risks it was checked against were that the taps
would read as a slapback stuck on the front rather than as scale, and that they
would muddy the onset — BIG has the lowest diffusion coefficient of the four, so
discrete taps get the least smearing there. Neither happened.

### Round 5 — chasing "metallic", and a metric that measured the wrong thing

Asked to reduce ringing. Excited with a **20 ms broadband noise burst**, because
the first attempt used the pad and its strongest tail peaks came out at 263.8 /
349.9 / 522.2 Hz — C4, F4, C5. Those are the pad's own notes. **A musical source
cannot reveal tank modes**; it only shows you its own harmonics ringing on.

**Then a fourth measurement error.** Ranked the modes by peak-to-median bin
energy and got ROOM 26.5 / PLATE 23.9 / HALL 33.0 / **BIG 48.0 dB**, and was
about to "fix" BIG. The tell that it was wrong: **nothing moved it** — not MOD
depth, not SPEED, not DIFF. A number insensitive to every control that should
affect it is not measuring what you think. It was tracking **spectral tilt**:
BIG has the darkest damping, so its band above ~1 kHz is empty, which drags the
global median down and inflates the ratio. The ranking was just the damping
order re-spelled.

Corrected by measuring each bin against a **local** median (±40 Hz) instead of
the global one, so a dark tail and a bright one are each judged against their
own envelope. That inverts the answer completely:

| mode | prominence over local envelope | total delay |
|---|---|---|
| ROOM | 10.8 dB | 5,657 samples |
| PLATE | 9.4 dB | 7,072 |
| HALL | 8.2 dB | 9,036 |
| BIG | **7.9 dB** | 12,572 |

**BIG is the SMOOTHEST of the four, not the worst.** And the ordering is exactly
monotonic in total delay, which is what modal theory predicts (modal density ∝
sum of line lengths). Reproducing theory across four independent configurations
is the reason to trust this metric where the previous one earned no trust.
(ROOM's figure is taken at t=1.0 s; by t=3.0 s it is near its own noise floor at
RT60 2.7 s and reads a meaningless 20 dB.)

**Conclusion: there is no clear fix to make, and that is the finding.**

* The only structural lever is **more total delay**, and memory is at the 32K
  hard ceiling. Splitting the same memory into more lines would not help —
  modal density depends on the SUM of the delays, not the line count.
* The mode that is most modal is **ROOM**, which is physically correct: small
  rooms really are modal, and at RT60 2.7 s it has the least time to ring.
* The available knobs buy very little. MOD 0 → 64 gains 1.4 dB and then flattens;
  SPEED has a shallow optimum near 40 (default is 64); and **higher DIFF makes it
  WORSE** (7.5 → 9.3 dB across the knob), which vindicates BIG's low diffusion
  offset rather than arguing against it.
* Absolute prominence of 8–11 dB over the local envelope is modest. This is not
  a badly metallic reverb, and the ear agreed — the pad passed before any of
  this was measured.

**Method note — four measurement errors in one session, three of them caught by
the same reflex.** Decimal-for-hex slot numbers; a 10 s source analysed as a
tail; a DFT aliasing above 2756 Hz; and a metric tracking tilt instead of
structure. The reflex that caught three: **a number that does not respond to the
control that should move it is a broken measurement, not a null result.** The
fourth was caught by demanding bit-identical output from a change that should
have been a no-op. Both are cheaper than the debugging they prevent.

### Hardware, 5 Aug 2026 — `ChonVerb21`, confirmed

Flashed and heard on the unit. **"Much better."** Everything voiced in Rounds
2d–5 plus the MIX law was emulator-only until this point; it all holds up on
hardware.

That closes the loop this file was opened for. Round 1's finding — *the modes
are under-differentiated* — is answered, and the answer was six per-mode levers
where there had been three, with **decay time** the one that mattered most and
the one MODE had never touched.

Still open and deliberately not acted on: modal prominence at 8–11 dB over the
local envelope (Round 5), whose only structural lever is more total delay
against a 32K hard ceiling. And two things the emulator cannot check at all —
the cycle budget with a full bank live, and the UI surface for WIDTH and →DEL,
whose companion fields `-params` cannot drive.

---

### Round 6 — the eight-line tank, 8 Aug 2026: four faults, then a voicing item

Not a voicing round. Every judgement here was about whether the engine *worked*,
and the answer was no four times running. Logged because the verdicts were made
by ear and because Round 7 — the actual re-voicing — starts from where this
left the engine.

**The harness lied first, and that is the reusable lesson.** `render_reverb.py`
keyed its build cache on mode and mtime but not on the ENGINE, and
`build_bus.py` writes every `MODE=` build to one path whatever `RVSRC` says. So
A/B-ing two engines replayed whichever build landed there first. The eight-line
tank "sounded exactly like" the four-line one because it **was** the four-line
one. Before trusting any comparison, confirm the thing you think you are
rendering is the thing being rendered — this is the 24-bit-parse trap of 7 Aug
wearing different clothes.

The second lie was a metric. `tail to -60 dB` scores the last window above
-60 dB **relative to the tail's own peak**, so a tail that *grows* scores as a
magnificent one. It reported 7.90 s for an engine that was diverging — the
number that had been written down as proof the eight-line tank worked. **Read
the per-second envelope; a single scalar cannot tell decay from runaway.**

| # | played | verdict |
|---|---|---|
| A | v4 vs 8-line, after the matrix, input-sign and frozen-line fixes | *"still not parity quality wise, but the fault is clearly gone"* |
| B | after the output-tap fix | *"closer but there is a stutter in the tail on the 8 line"* |
| C | after giving lines 4-7 distinct lengths | *"the distorted stutter is still there. Couple glitches in the first hit and then the stutter in the second hit"* |
| D | 4 clips: v4 / 8-line / 8-line MOD=0 / 8-line PLATE | *"glitches went away on 4 ... still a bit of a thwack but that's been around for ages and is tuning rather than a fault"* |

All wet-only, RMS-matched to -22 dBFS, same source. Round D is the one that
localised it, and it did so because each clip removed exactly one thing.

**What each verdict cost, and what it bought.** B followed the output tap being
moved ahead of the FWHT — the transform overwrites its slots in place, so the
output had been applying Hadamard rows to a Hadamard transform and collapsing
to one line per channel at 8x. C followed lines 4-7 getting their own tap
lengths; they had been reusing lines 0-3's four fractions, so the tank had four
duplicate pairs and the modal-overlap doubling the whole step was justified by
had never happened. Neither is a tuning choice — both were structurally wrong.

**Where Round 7 starts.** The remaining artifact is **ROOM's early reflections**,
and it is voicing, not a fault: the ER accumulator is byte-identical to the
four-line engine. Two things moved underneath it. The output-tap fix dropped the
tank ~9 dB relative to ER, and lines 4-7 now sit at 11-18 ms, overlapping the
ER taps at 4.5-21.3 ms where the four-line's lines sat at 14-22 ms. So ROOM's
`$6c` = 0.75 is a balance struck against a tank that no longer exists.

Two more things to re-voice, both known-compromised rather than chosen:

* **Lines 4-7's tap lengths are derived, not voiced** — one `x1` scale of 0.789
  applied to lines 0-3's fractions, chosen to interleave (488/571/618/667/723/
  781/846/989 samples, every gap >= 47) and *not* to sound like anything. They
  want their own per-MODE constants; the region now has 6 free words.
* **Every MODE constant** was tuned against four lines at a different density.

⚠️ Judge at eight lines and wet-only, and do not re-enable `SHIMMER=1` — it
stays excised, and a new shifter is a separate job.

---

## Round 7 — 9 Aug 2026: the ER is a flutter echo, and MODE had two positions

Judged by ear throughout, wet-only, level-matched, on `out/test_audio/melody.wav`
(a bare triangle-wave phrase — hard note onsets, no vibrato, so it hides
nothing).

### ⚠️ RETRACTION: every PLATE and HALL verdict in this log is void

`move #$1,x0` is the SHORT immediate form and the DSP56300 places short
immediates **MSB-aligned** — x0 got `$010000` while `a` held `$000001`. The
mode compare could never match, so **modes 1 and 2 both fell through to BIG**.
Only ROOM was reachable (it is selected by `tst a; beq`, not a compare).
PLATE, HALL and BIG rendered byte-identical: `9c080ce81e92`.

So **PLATE and HALL have never been heard.** In particular Round 1's "HALL and
BIG were indistinguishable wet and level-matched" was true because they were
the same code, and the tap-scale respacing that finding justified (v95) was
reasoning from an artefact. `8ed9acf`'s per-mode tap scales for PLATE and HALL
set constants that never executed.

Fixed with long immediates; the four modes now render four distinct hashes
(ROOM `1a0f9a5649d1`, PLATE `3c620c6ebeaa`, HALL `abbec50628fc`, BIG
`9c080ce81e92`). **Both modes need voicing from scratch.**

Found by the render harness printing `*** IDENTICAL ***`, not by reading code.

### ROOM's early reflections: structural, not voicing

Round 6 left this as "voicing rather than a fault". **That was wrong.** Sam,
9 Aug: *"like a playing card in a desk fan"*.

Localised properly — ROOM with `$6c` forced to 0, every other constant
identical, is **clean**. Not inferred from PLATE this time; PLATE differs in
about ten constants and attributing its cleanliness to ER alone was the error
that cost Round 6.

The ER implementation is **correct**. Measured, not assumed:

* linear to **−101 dB** (quarter input scaled ×4 against full input), so the
  accumulator does not overflow, despite three taps per channel summing to
  1.83 × full scale before `$6c` is applied
* time-invariant to **−67 dB** across block phase
* 99% of its impulse energy inside 21.3 ms, nothing past 60 ms (−224 dB):
  a pure six-tap output-summed FIR, exactly as written

It is what it was written to do that is wrong. **Six discrete taps summed onto
the output is a flutter echo.** Real ER sections use 20–100 taps; at six the
comb notches are 47–222 Hz apart, sparse enough to be heard as *pitch*, which
is what "robotic" means. Every lever was tried and every one failed the same
way:

| change | verdict |
|---|---|
| level `$6c` 0.75 → 0.27 | "lighter, like a playing card in a desk fan" — scales the comb |
| taps 4.5–21.3 ms → 8.0–68.9 ms | "quieter but still there" — re-tunes the comb |
| ER routed into the diffuser | "springs under a snare" — dispersed, not diffused |
| input diffuser 22–36 ms → 2.6–8.0 ms, ER on output | "card in the spokes" — ER bypasses the diffuser |
| both together | "different but still not right" — six seeds are still six seeds |

**The fix is more taps, and it needs program space payload A does not have
(0 free).** Not attempted. Until then ROOM's ER is the reverb's worst artefact
and `$6c` = 0 is the only clean setting for it.

Contributing, and worth its own fix: the input diffuser runs **22.5–36.4 ms**
where a classic Dattorro input diffuser is 4–13 ms. At that length an allpass
disperses rather than diffuses — the same failure this file already documents
for the in-loop allpasses. That is why routing the ER through it produced a
spring.

### Also measured, and a separate open bug

The tank is **nonlinear by −21.8 dB** in PLATE and −27.1 dB in ROOM (half the
input, scale ×2, compare). That is gross, and it matches the "tank saturation
above ~0.35 FS" item already in PLAN.md. Not the flutter — PLATE is nonlinear
and sounds clean — but far too much distortion to leave unexamined.

### Shimmer: clean, and not the culprit

The new shifter was confirmed clean **in isolation** (`SHIMONLY6.wav`, the
shimmer's contribution alone by subtraction, normalised up 15 dB). The stutter
heard "as soon as the shimmer went in" was ROOM's ER all along; the shimmer
made it more audible rather than causing it. See the commit log for the two
real faults fixed in the shifter itself (the 4-copy window and the dirty A2).

### ⚠️ Method note, paid for the hard way

Three metrics were used to judge shifter changes and **all three disagreed with
Sam's ears**: largest-spectral-peak (ranked a change he called "a big step
backward" as 18.7 dB better), lap-harmonic energy (predicted −7.2 dB for one he
called "basically the same"), and envelope-percentile spread (called the real
fix a no-op at 1.2 → 1.3 dB).

What worked every time: **feed it an impulse and count the events.** Four
equal copies → stutter; two → "a single pitch shifted tone". Do that first.

And: **isolate by subtraction.** `wet(knob=max) − wet(knob=0)` is the stage's
own contribution, and muting one stage at a time is what finally localised the
ER. Both are one render each and neither was run until very late.
