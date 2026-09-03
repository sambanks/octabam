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

`modules/chonverb/reverb_server.asm`, the `md_*` block. Three values per mode:

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

---

## Round 8 — 8 Aug 2026: kill the metallic, make shimmer cascade

Three root causes, all zero-word fixes (voicing constants + one register offset).

### PLATE had zero per-pass damping

`$72 = $7fffff` (1.00). A one-pole with coefficient 1.0 is a wire — no HF
attenuation per circulation. ROOM uses 0.945, BIG used 0.445. This is the
likeliest single cause of "metallic" in PLATE mode: the tail has no spectral
tilt, so HF resonances sustain indefinitely.

Changed to `$7A0000` (0.953). Still the brightest mode (ROOM is 0.945), but
with actual HF rolloff. The metallic edge is the sound of zero filtering; even
a 5% per-pass cut compounds over 60+ circulations. May voice higher, but 1.00
was not "bright" — it was pathological.

### BIG decay sat at the stability limit

`$1e = $5A8279` (exact 2/√8 = 0.7071, zero headroom below the unit circle).
ROOM and PLATE both scale this down (0.92×, 0.965×). BIG at 1.00× gives narrow
FDN resonances no room to decay — the "ringing" character, separate from
damping (which only shapes the spectrum, not the resonance sustain).

Changed `$1e` to `$4CCCCD` (0.60, ~18% headroom). To compensate for the faster
energy loss, `$72` raised from `$390000` (0.445) to `$480000` (0.563): a
slightly brighter tail preserves perceived decay length. The character should
shift from "resonant cave" to "large diffused space."

### Shimmer was a one-shot parallel send

Two problems: (a) the shifted signal entered the tank once and never saw the
shifter again — no cascading pitch rise; and (b) the source was `$6a`
(pre-diffusion dry mono, local-only), so cross-core tracks got reverb but no
shimmer.

Fix: read `$25` (mono wet sum) instead of `$6a`. `$25 = (wet_L+wet_R)/2` is
the raw tank output, computed from the previous sample's line outputs — before
WIDTH and MIX, so it's pure wet signal.

Cascading: shimmer output → `$15` → tank write-back → next sample's tap reads
include it → next sample's `$25` reflects it → shimmer reads its own previous
output → shifts again. Each circulation delays the re-shift by the mean tap
(~72 ms at SIZE max), which is exactly the gradual evolving rise.

Cross-core: `$25` is the wet sum of ALL tank output, and cross-core tracks
feed the reverb bus accumulator which enters the tank — so they appear in `$25`
the same way local tracks do.

Stability: SHMR starts at 0 (open loop). The tank's DAMP+LO filters tame the
shifted content each circulation. The shimmer's own anti-alias one-pole
(c=0.35) and −12 dB attenuation provide additional headroom.

Comment block updated; the `$15` flutter rationale and the cross-core
LIMITATION paragraph are archived in the source and superseded.

### $0c double-use bug found, deferred — ✅ FIXED 9 Aug 2026

The per-mode lines-4-7 tap scale (stored to `$0c` by each md_* block) overwrites
the bus auto-gain 1/N (also stored to `$0c` at line 506). The per-sample
multiplier at line 2089 therefore reads ~0.75 instead of 1/N. Affects cross-core
level but not sound character. `$6c` is the only free r7 slot and was reserved
for the shimmer fix that `$25` now makes unnecessary — it is the obvious home
for either the tap scale or the bus gain. ~~Not fixed here.~~

**Fixed by moving the tap scale to `$6c`** (three md_* stores + the SIZE-block
read). Measured both ways: the insert-path render is **bit-identical** (same
audio hash), proving the relocation changed no line length; the send-path
render (`send_probe.py --layout RS`, one sender) rose **+2.87 dB = exactly
1/0.71875**, ROOM's tap scale — the value the auto-gain had been wrongly
multiplying by — with THD, every harmonic and every spur identical to 0.1 dB.
A pure gain restoration. Note this bug meant **no build before the fix ever
truly carried v121's auto-gain**, including any render used to judge multi-track
bus behaviour.

### Verification

```
make check   → ALL CHECKS PASSED, 179 words free, 1022 cycles spare
make render  → ROOM (0.12 FS / −37.6 dB), PLATE (0.28 FS / −31.2 dB), BIG (0.13 FS / −35.0 dB)
```

All three modes render distinct hashes. Tail 7.90 s at defaults with SPEED=64
(shimmer half). PLATE is still the loudest mode (highest damping = most HF
retained per pass). **Needs ear: A/B against git stash of the old constants,
each mode, wet-only.** Commands in the commit message.

---

## Round 9 — 9 Aug 2026: the nonlinearity is a THRESHOLD, and the harness lies again

### ⚠️ FIRST: `render_reverb.py` could not be run twice at once, and that faked a bug

`out/dsp/_render_in.raw` and `_render_out.raw` were **fixed paths**. Two renders
running concurrently fed each other's audio through the emulator and wrote each
other's output. Fixed 9 Aug — the scratch names now carry the pid.

It cost two measurements, and the failure is worth recognising because of what
it *looked* like. Two background jobs overlapping produced an output peak that
was **non-monotonic in input gain**:

    gain 0.70 -> peak 0.1376      gain 0.60 -> peak 0.2016
    gain 0.55 -> peak 0.3347      gain 0.50 -> peak 0.0983

A smaller input producing a louder output is the signature of a conditional
instability in the tank — a serious, structural, entirely fictitious bug. It
**survived a determinism check** (`identical: True`), because each render on its
own really is deterministic; only the overlap was not. A second anomaly at
gain 0.580, with a plausible sustained-excursion shape (72,368 samples above
half-peak against 11,775 for its neighbours), was the same thing again: a
foreground probe render launched while a background sweep was still going.

**Neither reproduced when re-run serially.** The reflex that caught it was the
cheap one this file already relies on — *re-run the anomalous point on its own
before believing it* — and the tell was that the single render disagreed with
the sweep for the same gain.

### The real measurement, run serially

Residual `r = out(G) - 2*out(G/2)`, wet only, ROOM, `melody.wav`, relative to
`out(G)`. A linear system gives silence.

| gain | peak (FS) | residual |
|---|---|---|
| 1.00 | 0.1966 | **−24.00 dB** |
| 0.90 | 0.1770 | −26.13 |
| 0.80 | 0.1573 | −29.13 |
| 0.70 | 0.1376 | −34.12 |
| 0.60 | 0.1180 | −60.95 |
| 0.50 | 0.0983 | −79.40 |
| 0.25 | 0.0492 | −73.35 |
| 0.125 | 0.0246 | −67.35 |
| 0.0625 | 0.0123 | −61.35 |
| 0.03125 | 0.0061 | −55.23 |

**Two regimes, and the second one is not a nonlinearity at all.** Below gain
0.5 the residual rises **+6.0 dB per halving** (−79.4, −73.35, −67.35, −61.35,
−55.23 — differences 6.05/6.00/6.00/6.12). That is the signature of a *fixed
additive floor*, i.e. 24-bit output quantisation: the measurement floor, not
the engine. **The engine is linear to the floor at any input below −6 dBFS.**

Above that there is a genuine threshold nonlinearity with a **knee between gain
0.6 and 0.7** (−60.95 → −34.12, a 27 dB jump for a 1.4 dB level change), which
then grows only slowly to −24 dB at full scale. Steep onset then saturation is
the classic hard-clip shape.

### 🔴 RETRACTED: "the engine is nonlinear by −21.8 dB in PLATE and −27.1 dB in ROOM. That is gross."

PLAN.md and Round 7 state this as a property of the engine. It is a **single
point** on the curve above — the value at full-scale input — reported without
the sweep that gives it meaning. The engine is not "grossly nonlinear"; it is
**clean until it clips**, and it clips only in the top ~4 dB of input range.
That is a different defect with a different fix and a different priority.

### Where it is NOT: the output sum

The output stage sums eight line outputs with ± signs into one 24-bit store
(`move a,x:(r7+$2d)`), which can grow 8× and saturates — an obvious suspect.
**Ruled out by the peak column:** output peak is 0.1966 × gain at *every* gain
from 0.5 to 1.0, exact to four figures. A saturating output stage compresses
the peak; this one does not. The clip is **inside the feedback loop**.

🟡 **Leading remaining candidate, not yet confirmed: the FWHT's intermediate
stores.** Three butterfly stages, each `add`/`sub` then `move a,x:(...)` into a
24-bit slot, with the decay gain applied only *afterwards* in the write-back.
Element growth through the transform is up to 8× (√8 in RMS), so line outputs
above ~1/√8 ≈ 0.35 FS start saturating the stage stores — which is exactly the
"tank saturation above ~0.35 FS" item PLAN.md has carried for months.

⚠️ **Not confirmed, and one obstacle is that the naive gain accounting does not
close.** Taking `mpy`'s fractional doubling into account, the write-back
multiplier is `2 × $1e` ≈ 1.06–1.42, and with H8's √8 that implies a loop gain
around 3.7, which would diverge instantly. The engine demonstrably decays
(RT60 ≈ 2 s in ROOM), so something in that chain is scaled differently from
how it reads. **Do not act on the FWHT hypothesis until the gain structure is
measured rather than derived** — the honest state is "threshold clip, inside
the loop, site not established".

## Round 10 — 9 Aug 2026: SETUP — per-line decay gains, judged by ear

The 1.1 build (per-line decay gains, anchor 1/√8, commit `d381805`) measured
right: per-line decay spread 63 → 2 dB/s, envelope drift flattened, stability
by norm at every corner. This round is the ear's verdict — **is the
lush-turns-metallic complaint gone?** — plus first impressions for the 1.3
re-voice.

**Renders**: `out/voicing_ab/` — {pad, stab, hat, melody} × {ROOM, PLATE,
BIG} × {A, B}. **A = pre-1.1** (uniform gain, the engine every previous round
was heard on). **B = current** (per-line). Wet-only, defaults, tail 8 s,
sources from `scripts/make_test_audio.py` (out/test_audio). All files
level-matched to −20 dBFS active-RMS (100 ms windows above −60), so louder
can't win.

**Play**: `out/voicing_ab/ab.sh pad ROOM` (A/B/A/B; third arg = repeats).

What each source asks:
- **pad** — THE question: does the held tail stay dense as it decays, or
  thin out into the metallic few-line ring? Meters say B holds it
  (tail-to-−60: ROOM 1.5→2.2 s, PLATE 2.5→5.7 s, A→B).
- **stab** — pitched bloom: smoother rise/fall, no comb-like coloration late.
- **hat** — HF tail: 1.2 closed per-line damping as not-warranted; if B's
  hat tail turns sparse or metallic at the top end, that reopens it (the
  revisit spec is in PLAN.md 1.2). Also audible here if at all: the AP-mod
  HF shelf (~55 dB down — likely inaudible).
- **melody** — the musical audition; B runs ~1.5 dB hotter in wet RMS at
  equal knobs (short lines contributing longer), which the level-match hides
  — judge character, not loudness.

Note for the log: B's decay is genuinely longer at the same TIME knob (the
short lines no longer die early), so if B reads as "too long", that is TIME
recalibration (mechanical, expected — PLAN 1.1's r₀ note), not a fault.

**Verdicts** (fill in after listening):
- pad ROOM / PLATE / BIG: (pending)
- stab:
- hat (reopen 1.2?):
- melody:
- Overall: does 1.1 ship to the re-voice as-is?

## Round 11 — 9 Aug 2026: the VintageVerb pivot, and the tilt inversion

**Baselines reset (Sam): "none of it has ever sounded good."** Reference
chosen: Valhalla VintageVerb demo (4.0.5d), Room / Plate / Hall1984, all at
DECAY 2.02 s, damping 6 kHz / HighShelf −24 dB, BassMult 1.5×@300 Hz, mod
2.53 Hz/38%, COLOR 1980s, mix 100%. Sam's bounces: `out/vv_ref/{room,plate,
hall}/{pad,stab,hat,melody}_1.wav` (48k/24-bit; stab hits every ~4 s, hat
every ~2 s — consistent hit levels across the file prove no demo fade landed).
Supermassive is REASSIGNED to BongDelay (a diffused feedback delay is what it
is); ChonVerb voices against VintageVerb alone.

Round 10 verdicts (pad A/B, level-matched): **B > A clearly** (per-line gains
keep the tail dense) but the bar is not met: tail still metallic + wrong
tone. (Also this round: the first A/B kit was 24-bit renders sheared through
a 16-bit read in the level-match — Sam heard "mostly static" and was right;
kit rebuilt with 24-bit I/O and a flatness+duration screen now runs before
any listening.)

**Measured gap table** (stab tail band slopes dB/s; crest = 30 ms peak/RMS
grain metric; corr = L/R correlation early/late):

| | LF 150-500 | MF 0.5-2k | HMF 2-6k | HF 6-10k | crest | corr |
|---|---|---|---|---|---|---|
| VV room | −21.1 | −23.3 | −25.2 | −29.7 | 8.9 | +.32/+.15 |
| VV plate | −21.3 | −26.9 | −28.8 | −32.9 | 8.9 | −.17/+.19 |
| VV hall | −17.4 | −21.4 | −24.4 | −33.4 | 8.8 | −.06/+.25 |
| us ROOM | −24.9 | −29.8 | −33.6 | **−26.4** | 7.3 | +1/+1 |
| us PLATE | −16.3 | −17.0 | −13.0 | **−10.8** | 8.1 | +1/+1 |
| us BIG | −29.0 | −29.1 | −26.4 | **−22.6** | 8.4 | +1/+1 |

Three findings, in order of audible damage:
1. **The metallic/wrong-tone complaint is an INVERTED HF ladder.** Every VV
   mode decays monotonically faster with frequency; every one of ours lets
   HF outlive the mids (PLATE's tail literally brightens — its damping scale
   is 0.953 ≈ none). VV uses in-loop damping PLUS an output high-shelf/cut;
   we have no wet-path high-cut at all. Fix: add one (mode-voiced), retune
   per-mode damping toward the measured ladders.
2. **Density is NOT the gap** — crest 7.3–8.4 vs 8.9. The grain hypothesis
   dies; it was tilt all along.
3. **Local renders are mono** (corr +1.00): WIDTH is a companion field
   dsp_host cannot drive, so every render ever judged locally had WIDTH=0.
   Needs a build-time WIDTH= override (like MODE=) before stereo can be
   voiced. VV's field is strongly decorrelated.

Round 11 targets: our band-slope rows bracket VV's per mode; then ears.

### Round 11 addendum — the constants cannot bridge it: line length is the gap

Wet high-cut built (one-pole on M and w*S, coeff $7a per mode, states
$78/$79) and per-mode damping retuned (ROOM 0.95→0.75, PLATE 0.953→0.78).
Measured tilt trajectories (HMF−MF and HF−MF at 0.4 s → 1.6 s into the stab
tail):

| | HMF−MF | HF−MF |
|---|---|---|
| VV room | −11.1→−11.6 | −29.0→−32.1 |
| VV plate | −10.2→−12.2 | −25.1→−31.4 |
| VV hall | −9.7→−9.6 | −24.7→−35.7 |
| us ROOM | −17.4→−22.6 | −50.9→−49.8 |
| us PLATE | −27.6→−16.3 (brightens!) | −53.7→−33.2 (brightens!) |
| us BIG | −26.1→−23.3 | −53.3→−55.7 |

We are 6–25 dB TOO DARK in the upper bands while ALSO letting HF outlive
the mids — dark and zingy at once. No constant fixes both: our lines are
9–20 ms (50–110 passes/s), so damping strong enough to kill the late zing
destroys the early top end. VV's loop delays are several times longer, so
the same per-pass damping lands bright-early/dark-late. Round 5's verdict
("the only structural lever is more total delay") returns with a measured
target attached.

**Next: relayout increment 2 — double the lines to 8×4096 (93 ms).**
Increment 1 (b2bab52) left private Y holding only the 8×2048 lines: the
memory is already there. Then re-run this table.

## Round 12 — 9 Aug 2026: the doubled lines, measured against VintageVerb

Sam's Round 11 listening verdict on the retuned constants: better shape,
still metallic/ringy, and VV still far lusher and broader. That is what the
addendum predicted — so relayout increment 2 went in: **the eight tank lines
doubled to 4096 words (93 ms max)**, filling the whole private 32K that
increment 1 emptied for exactly this. Commit eb1c8b2. Folded in: the TIME→g
mapping reverted to 0.875..0.999 (the 0.935..0.9995 range was g_old^0.5,
derived FOR the halved taps), and a latent PRE defect healed (the 4096-word
pre-delay derivation assumed a 0..4095 phase the halving had taken away —
PRE above ~46 ms read never-written memory).

Verified before any voicing: make check clean; the module disassembled with
dsp56kDisassemble and every edited site checked word-by-word (asr #$a =
0c1c14, stock's own encoding; modulo loads 05f42x 000fff; bases, strides
and g constants exact). No mis-encodes.

### The gap table, re-measured (new pure-python filterbank, VV re-measured
### with the SAME bank so rows compare; slopes dB/s over 0.4–1.6 s of the
### stab tail; tilt = band minus MF at 0.4 s → 1.6 s)

| | LF | MF | HMF | HF | HMF−MF | HF−MF | crest | corr E/L |
|---|---|---|---|---|---|---|---|---|
| VV room | −19.2 | −19.8 | −20.2 | −20.7 | −9.8→−9.9 | −23.1→−23.6 | 8.6 | +.36/−.03 |
| VV plate | −14.8 | −18.9 | −21.2 | −22.9 | −9.6→−10.5 | −22.2→−24.4 | 9.1 | −.16/−.06 |
| VV hall | −14.4 | −17.9 | −19.8 | −21.1 | −8.2→−10.6 | −20.5→−24.9 | 8.2 | −.09/+.43 |
| us ROOM T64 | −21.5 | −20.3 | −19.9 | −20.3 | −8.4→−8.5 | −22.7→−23.2 | 9.2 | +1/+1 |
| us PLATE T32 | −16.0 | −18.7 | −21.4 | −22.3 | −8.8→−10.6 | −22.5→−25.3 | 8.6 | +1/+1 |
| us BIG T8 | −20.2 | −17.7 | −18.0 | −18.5 | −10.2→−11.2 | −24.5→−25.9 | 8.2 | +1/+1 |

**The tilt inversion is GONE.** Every mode now darkens as it decays, inside
VV's tilt bracket — the Round 11 damping/high-cut constants finally have
lines long enough to act on. PLATE at TIME=32 sits within 0.6 dB/s of VV
plate in three of four bands.

### PLATE decay scale retuned, empirically

On the doubled lines PLATE's fastest decay (TIME=0) measured MF −15.1 dB/s
vs VV plate's −18.9: the knob could not reach a real plate's tightness.
$1e $5753E3 → $50A000. ⚠️ The first attempt (×0.972 by per-pass gain
accounting) delivered only 2.5 of the needed 6.9 dB/s — $1e feeds the
per-line formula through the 1/√8 anchor SPREAD, so scale moves less gain
than naive accounting says. Measured sensitivity: ~2.5 dB/s per 0.019 of
scale. Do not retune these by derivation.

### Decay-matched knob pairings (for A/B and for the manual)

ROOM = TIME 64 ↔ VV room · PLATE = TIME 32 ↔ VV plate · BIG = TIME 8 ↔
VV hall1984 (all at VV DECAY 2.02 s). BIG reaching hall-at-2s at TIME=8 is
fine: VV's own DECAY runs to 70 s, the knob top is for long tails.

### What the table says is still missing

1. **Stereo, still.** corr +1.00: every local render is MONO (WIDTH is a
   companion field dsp_host cannot drive). VV's field is decorrelated ±0.4.
   "Lush and broad" is partly THIS — a WIDTH= build override (like MODE=)
   is the next mechanical item, before any more tone chasing.
2. **LF dies too fast.** VV's LF outlives its mids in every mode (BassMult
   1.5×@300 Hz); ours decays LF FASTER than mids in ROOM and BIG. A
   bass-mult (LF decay boost, the inverse of the LO cut) is the candidate
   lever for "lush". Caveat: the LF band has the fewest cycles per window;
   confirm on a bass source before building anything.
3. **Metallic-by-ear: unjudged on the new lines.** The measured tilt is
   right; whether 93 ms lines kill the ring is the ear's call.

**Renders**: `out/vv_ab/` — {pad, stab, hat, melody} × {ROOM, PLATE, BIG},
**A = VintageVerb** (Sam's bounces, trimmed to 12 s), **B = ChonVerb** at
the matched TIME above, wet-only, level-matched to −20 dBFS active-RMS,
24-bit I/O, flatness+duration screen run before writing (Round 11's rule).
**Play**: `out/vv_ab/ab.sh stab PLATE` (A/B/A/B; third arg = repeats).

**Verdicts** (fill in after listening):
- pad ROOM / PLATE / BIG: (pending)
- stab (the ring test):
- hat:
- melody:
- Overall: how far did the lines close the lush gap?

### 🔴 Round 12 addendum — RETRACTION: the table above was shimmer-polluted

Sam, listening to the kit: "is the shimmer on? there is still a high zingy
bit in the bg." **It was.** SPEED has been SHMR since v101, the render
harness defaulted it to 64, and 64 quarter-scaled is an octave-up loop gain
of ~0.13 recirculating through the tank — in every "us" row of the Round 12
table, and in every measured row of every earlier round since v101. (The
session notes had it backwards — "shimmer excised by default" was memory,
not code: build_bus.py ships it IN unless NOSHIM=1.)

Measured, stab PLATE T32: MF slope −18.7 dB/s with SHMR=64 vs **−22.8
without** — the shimmer was not just zing on top, it recirculates and
lengthens every band's sustain. So the decay-matched pairings above were
matched against a shimmer-inflated decay, and are retracted with the rows.

**Shimmer-free rows and pairings** (same filterbank, SPEED=0):

| | LF | MF | HMF | HF | HMF−MF | HF−MF | crest |
|---|---|---|---|---|---|---|---|
| us ROOM T80 | −20.8 | −20.1 | −21.1 | −21.6 | −8.7→−9.5 | −23.0→−24.4 | 9.2 |
| us PLATE T80 | −14.4 | −18.5 | −21.5 | −22.3 | −9.4→−11.6 | −23.2→−26.4 | 8.1 |
| us BIG T64 | −17.1 | −17.9 | −18.9 | −19.4 | −10.2→−12.3 | −24.5→−27.1 | 7.9 |

**ROOM=TIME 80 ↔ VV room (−20.1 vs −19.8) · PLATE=TIME 80 ↔ VV plate
(−18.5 vs −18.9) · BIG=TIME 64 ↔ VV hall (−17.9 vs −17.9, exact).** All
mid-knob. The tilt-inversion-gone conclusion SURVIVES the retraction — the
shimmer-free rows darken even more cleanly than the polluted ones. The
PLATE $1e retune also survives (re-validated shimmer-free: the match sits
at T80 with a tight-plate bottom below and ~4.3 s at T127).

Kit REBUILT shimmer-free at these TIMEs (same protocol, same screens).
render_reverb.py's SPEED default is now 0 so this confound cannot recur;
shimmer auditioning is opt-in (-p SPEED=n).

Open question for the ear now that the zing has an owner: how much of the
remaining ring (if any) is the tank's, and does the shimmer's own v3 sound
hold up at sane levels on the doubled lines (SHMR sweet spot was measured
at raw 0.20 on the OLD 2048 tank — re-find it).

### Round 12b — Sam's verdict on the shimmer-free kit, and STEREO renders

**Sam, on the shimmer-free kit: "sooooo much better, still a little
metallic and not as lush but huge improvement."** The doubled lines plus
the accidental-shimmer excision carried most of the distance; what remains
is "a little metallic" and "not as lush".

**WIDTH= build-time override built** (the item Round 11 finding 3 asked
for): same mechanism as MODE= — build_bus.py clobbers the extracted
companion value with an immediate at `; WIDTH_OVERRIDE`, wired through
render_reverb.py's fingerprint. Every render before this was mono.
Measured at WIDTH=100, stab PLATE: L/R corr **−0.11/+0.02** against VV
plate's −0.16/−0.06 — on the reference — with decay slopes bit-identical
to the mono row (WIDTH is post-tank, as it should be). ROOM at WIDTH=100
runs wider late (−0.50) than VV room (−0.03); left wide on purpose —
erring toward "broad" — narrow by ear if ROOM smears.

Also fixed: BUILD_ENV still listed the dead SHIMMER flag instead of
NOSHIM, so a NOSHIM build did not change the render-cache fingerprint —
the exact stale-cache bug that list exists to prevent.

**Kit REBUILT: B-sides now stereo** (WIDTH=100, SHMR=0, same TIME
pairings). This is the first time our stereo field has ever been
auditioned locally.

Remaining, in order of the measured gaps: LF bass-mult (VV's LF outlives
its mids; ours dies faster — confirm on a bass source first), then the
residual metallic (diffusion/AP-mod voicing on the doubled lines).

### Round 12b addendum — the LF claim mostly dies with the shimmer too

Re-measured on a bass source (bass.wav through BIG, shimmer-free): LF and
MF decay DEAD EQUAL (−21.6 vs −21.7 dB/s). And the shimmer-free stab rows
already had LF outliving MF in PLATE (−14.4 vs −18.5) and BIG (−17.1 vs
−17.9). 🔴 So "ours dies LF-first" — Round 12's finding 2 — was mostly the
shimmer's broadband recirculation flattering MF/HF sustain, not an LF
defect. Remaining LF gap: ROOM only, ~1.3 dB/s vs VV room. A bass-mult is
DEPRIORITIZED until the ear asks for more low bloom.

That reorders the open list to: **1. the residual "little metallic"**
(levers: MOD depth, DIFF, AP-mod rate — the first two are free knobs),
**2. ROOM's small LF shortfall**, 3. shimmer re-voicing on the new tank.

**Sweeps for the ear**: `out/vv_ab/sweeps/sweep.sh mod` (MOD 20/60/100/127)
and `sweep.sh diff` (DIFF 20/64/100/127), PLATE fixed at the VV-matched
settings otherwise. Ear-anchor: ../stab_PLATE_A.wav. Question for MOD: does
more smear kill the ring before it turns seasick? For DIFF: does the ring
live in the diffusers (DIFF up = denser but more allpass coloration)?

## Round 13 — 9 Aug 2026: SETUP — the metallic hunt, ROOM and BIG

Sam on the stereo kit: "yeah so much better, just need to chase down the
metallics, especially on the non-plate ones." So: why is PLATE the least
metallic? The per-mode lever table says PLATE has the FASTEST mod (rate
scale 1.0 vs ROOM 0.70/BIG 0.25), the MOST input diffusion (offset 0.125
vs 0.094/0.031), and the narrowest tap spread. BIG's mod philosophy ("a
huge space barely moves", rate 0.25 = well under 0.1 Hz effective) is the
prime suspect: a near-static tank rings — this file's own rule — and the
VV reference everything is judged against runs its mod at 2.53 Hz.

**Renders**: `out/vv_ab/metallic/` — {room, big} × {base, mod127, diff127,
vmod, vdiff}, stab, VV-matched TIME, WIDTH=100, SHMR=0, level-matched.
mod127/diff127 are free knobs (depth 3.2x / allpass g up); vmod/vdiff are
one-constant variants (mod smear to PLATE's, diffusion offset raised).
**Play**: `out/vv_ab/metallic/hunt.sh room` / `big`. VV anchors:
`../stab_ROOM_A.wav`, `../stab_BIG_A.wav`.

**Verdicts** (fill in after listening):
- room: which of the four beats base, and is any un-metallic enough?
- big:
- Does the winner survive on pad/melody (smear cost)?

### Round 13 — the hunt's findings (in-session, Sam's ear + late-tail probe)

Single levers (MOD/DIFF knobs, mod-to-PLATE constants, diffusion offsets):
Sam — "they all reduced it a little". Combos: "creeping closer... it just
rings at the end in a metallic way on all modes, which vv doesnt."

**Late-tail probe built** (scratchpad latetail.py: spectral crest of the
−40..−60 dB tail segment, 2-8 kHz). Ours: crest 47-65 dB vs VV 30-40 —
few towering modes late where VV stays washy. Gain sweep: crest falls
~6 dB per input halving, no knee → the PEAKS are linear modal ring
scaling with input over a FIXED floor (in-loop truncation noise). Not
the Round 9 clip — a modal-prominence problem.

**The binding lever was mod RATE, pinned near 0.4 Hz since v101** (VV
demo runs 2.53 Hz). Slow-deep mod cannot spread a mode across bins;
fast-shallow can. Base rate x8 (asr #$b -> #$8 in the RATE block,
~2.2 Hz), depth scales trimmed to hold vibrato ≤~12 cents: ROOM crest
65 -> 49, the largest single movement of any lever. Sam: "lot better but
still more to go. valhalla tails sound denser and brighter right until
they tail off, where ours seem to thin out and are darker."

**Damping rebalance (v2/v3): move tone from the LOOP to the OUTPUT.**
In-loop damping compounds per pass (late HF collapse = thin+dark end);
VV carries tone in output EQ which does not compound. Damping scales up
(ROOM 0.75 -> 0.953, BIG 0.5625 -> 0.8125), wet high-cut down (ROOM
0.55 -> 0.414, BIG 0.60 -> 0.4375): late HF−LF ROOM −50 -> −38, BIG
−52 -> −33.5 (VV room −21.5, hall −31.4 — BIG on target, ROOM still
short). TIME re-matched: ROOM=56 (MF −19.9 vs VV −19.8 exact),
BIG=44 (−17.1 vs −17.9).

Structural candidates if the ear still says thin after v3: in-loop APs
on only 2 of 8 lines (six lines re-inject undiffused), per-line decay
spread late, and the truncation floor.

### Round 13 CLOSE — the bloom, found and shipped (commits through this one)

The second half of the round chased Sam's "VV has a bloom of energy at the
start" through eleven A/B'd variants (v5-v16), each one lever. What
survived into the SHIPPING engine:

1. **Sparse injection** — input drives only the two shortest lines (3 in
   group A, 7 in group B, sum zero); the Hadamard spreads energy to all
   eight over 2-4 passes. Density BUILDS, Lexicon-style, instead of
   arriving complete. (Driving the two LONGEST lines instead put a ~90 ms
   hole before BIG's first sound — measured, killed.)
2. **The driven lines are excluded from the output sums** — the wet comes
   from lines that fill by recirculation (the swell) — and the sums gain
   the bloom component instead.
3. **BLOOM ALLPASSES**: two long, high-g APs in series (41/29 ms, primes,
   g=0.867 fixed — deliberately NOT DIFF's coefficient) on a side branch:
   chain out -> APs -> 0.5x into the sums, pre-high-cut so the tone stays
   tamed. Rings ~600+ ms: the bloom LENGTH no short-diffuser setting could
   make. Buffers in the ex-margin at shared+0x4800/+0x5000; the warm-up
   clear is EXTENDED to +0x57ff to cover them (80 words/block, was 64).
4. **Input diffusers 3.6x longer** (641/1051/1511/1949, primes, 14-44 ms,
   all modes): the diffusers are the bloom generator; Dattorro-short taps
   could not stretch the attack.
5. **Mode constants** (ROOM/BIG; PLATE untouched): both mod rate scales to
   1.0 (~2.2 Hz — BIG's "a huge space barely moves" 0.25 left a
   near-static tank, and a static tank rings); BIG depth 0.60; ROOM tap
   scale 0.60; diffusion offsets up (ROOM->0.125, BIG->0.094); damping
   way up (ROOM 0.953, BIG 0.8125) with tone moved to the wet high-cut
   (both 0.523) -- in-loop damping compounds and was thinning+darkening
   the tail end ("thins out and darker", Sam).

**Fit**: 2720/2724 words -- the v16 audition build was 1 word OVER and ran
under --dev; the shipping fold paid for itself plus the warm-up extension
with the leaner sparse chain (-1), a short n5 immediate (-1), and deriving
bloom AP b's base from AP a's r5 (-2). Verified: make check clean, every
new site disassembled (mpysu x0,y0 with positive-constant y0 = the audited
family; asr #$3,b,b = 0c1c87; do #<$50; count*80 math exact).

**Sam's verdicts along the way**: fast-shallow LFO "lot better"; damping
rebalance "lot closer now, tails are pretty good"; bloom v13 "slightly too
loud... I was confusing brightness and volume with lushness and length";
v15/v16 (bloom APs) "getting closer... we aren't as lush but that's
probably close enough. Awesome effort."

**Ear pairings for the kit** (out/vv_ab, rebuilt on the shipping engine):
ROOM=T56, PLATE=T64, BIG=T44, DIFF=120, WIDTH=100, SHMR=0.

**Open for next round**: (1) PLATE inherited every structural change
UNAUDITIONED -- it needs its own ear pass (its mod rate also jumped to
~2.2 Hz via the global x8). (2) The lushness residual: candidates are
in-loop APs on more than 2 of 8 lines, and modulating the bloom APs.
(3) TIME->decay calibration needs re-deriving with a bloom-aware fit
window (the 0.4-1.6 s window now catches the tail of the bloom, so slopes
read shallow). (4) verify_slots / hardware publish for DIFF at 120 as a
default is a knob question, not a code one.

## Round 14 setup: WET MAKEUP GAIN (10 Aug 2026) — built, ear pass pending

Sam's hardware finding on R14: fully wet is much quieter than dry. Inherent
(v96's own note measured the straight crossfade −7 dB), now with ear
evidence. Built as a top-half makeup so the knob's bottom half is untouched:

    $20 stores wgain/2; the mix stage asl-doubles the wet product.
    wgain'(MIX) = MIX/2                    MIX <= 64   (doubled back exactly:
                                                        BIT-IDENTICAL below half)
                = MIX/2 + (MIX - 64)       MIX >  64   (reaches ~2x = +6 dB at 127,
                                                        mirroring the dry fade-out)

**Measured** (dsp_host A/B vs the pre-makeup engine, SHMR pinned 0 — the
6-param default leaves SHMR at 64 and it POLLUTED the first A/B to a flat
+0.00 dB, the Round-12 trap again; pin page 2 in every dsp_host measurement):
- MIX=64: bit-identical, by construction and verified.
- MIX=127, pure diffuse tail: ratio 2.017 = **+6.1 dB** ✅
- Input-correlated material moves less (the residual dry at 0.0156 still
  rivals the thin-spread instantaneous wet), so bulk-rms A/Bs under-read;
  judge the makeup on TAILS.

**Ear pass: ✅ CONFIRMED on hardware, 10 Aug 2026 (R15 flash, tag 34) —
Sam: "mix is great."** Cost 15 words (payload A at 163 free).

## R18 — 10 Aug 2026: the Valhalla Shimmer gap (single-octave, lerp heads,
## an R17 bug, and BIG's decay ceiling)

Sam, with VallhallaShimmer refs on the same sources: "still much richer and
energetic and modulated." The ref bounces (out/vv_ref/shimmer, settings
screenshot alongside: mix .5, shift +12, FEEDBACK 0, diffusion .91, size .5,
low cut 10, high cut 8k, mod .59/.30, PITCH SINGLE, bright) were mined for
numbers first: dry extracted by aligned subtraction (alpha .75, so the
bounces carry dry — all wet-vs-wet comparisons use the residual), 24-BIT
loaders (the first hour of numbers was garbage int16 reads of Logic's 24-bit
bounces — flat-white "ref spectra" were the tell).

Measured gaps at R17-tag-36 baseline, wet vs wet (pad/stab, BIG T64 S64):
MF tail decay -21 vs VV -8.3 dB/s; 6-9k body -8..-10 dB darker; 6-9k
spectral crest (isolated towers over wash) 27-39 dB vs VV 15-20; 1-4k mod
index .37-.45 vs .52-.54. Diagnosis in five parts, each verified by its own
A/B render + gap re-measure:

1. **CASCADE OFF (architectural, R17's deferred item).** The shifter now
   reads the BLOOM branch ($08 -- diffused input through the two long APs,
   zero shimmer recirculation, 600 ms smeared so the old $15 stutter has no
   transient structure to stutter on) instead of the prev-sample wet sum
   $25. One shift, +12 only, feedback=0 -- the ref's own topology. The
   +24/+36 climb is gone WITH the 6-9k splice-HF it regenerated every pass.
   Crest pad 38.6 -> 34.7 on this change alone.
2. **SUB-SAMPLE HEAD READS.** The R17 chorus wobbled the heads by INTEGER
   buffer words = 2-sample splices, hundreds/s of zipper right in 6-9k. The
   heads now interpolate: frac_words = ($21&3)/4 + $22/4 (the tank's own
   pairing rule applied to the shimmer), lerp t0+frac*(t1-t0) per head.
   With the hash gone, 9-12k dropped 9 dB -- the "brightness" it faked is
   off the books, which is what let the real levers below be sized.
3. **R17 BUG, found by disassembling the region: head 0's smoothstep parked
   g^2 in X1 -- the register holding the modulated phase head 1 reads as
   its POSITION.** Every head-0 ramp pass sent head 1 to a garbage position
   at up to full window gain. Fixed: g^2 parks in $14. (mpy audit of the
   new code: signed mpy x0,y1 everywhere it must be; one mpysu x0,y0 with
   frac in the unsigned slot -- non-negative by construction, audited-safe
   family. Disassembled from the BUILT image this time, not the stock one.)
4. **BIG's decay CEILING was the "less energetic" core.** md 0.60 was cut
   from 2/sqrt(8) for "headroom" before the 1.1 norm proof existed; ceiling
   measured ~-15 dB/s vs the ref's -8.3 (TIME barely moved it: 64->118 was
   -21->-15.5). md -> $568000 = 0.67578: max $1e = 0.3376 < 1/sqrt(8), the
   1.1 stability argument holds unchanged (radius <= 0.976, strictly <1 BY
   NORM at every knob). T100 now lands -8.1 dB/s == the ref. Falsifier
   rendered: -10 dB click, TIME=127 x SIZE {0,127}, SPEED=96 MOD=64 --
   per-second envelopes (the only metric the retraction ledger trusts for
   this) decay monotonically to the -103 dB floor, no growth. Two trap
   notes from running it: a -26 dB click renders SILENT -- first blamed on
   the 16-bit output floor, ❌ RETRACTED same session: it was the GATE=0
   threshold bug (below); and the tail-to--60 metric printed "7.90 s" --
   the retraction ledger's own divergence number, here a genuine tail, but
   only the envelope says so. NOTE: the
   whole BIG knob lengthens -- kit TIMEs for non-shimmer BIG re-map (old
   T44 character now sits near T20-ish; TIME refit remains open in PLAN 1.3).
5. **Tone opened toward the ref**: pre-shift one-pole c .35 -> .45 (~8.4k
   post-shift, = the ref's high cut); BIG wet high-cut .523 -> .60 (~6.4k,
   still under PLATE); BIG in-loop damping .8125 -> .90 (measured the
   binding 6-9k lever -- the wet high-cut raise alone moved the band <1 dB).

RETIRED along the way (both measured, neither shipped): per-head wobble
from a second LFO (crest 34.7 -> 38.2 -- every window crossfade hands off
between mismatched phases; per-head modulation is structurally wrong in a
windowed 2-head shifter) and a shared second-LFO at half depth (null).

**Where the numbers stand** (new engine, BIG T100 S96 MOD64 DIFF120, wet):
decay -7.9..-8.1 vs ref -8.3/-8.4 (matched); mod index .515 vs .524
(matched); 6-9k crest 32 vs 19.5 pad, 26 vs 15 stab (improved from 39/27,
still the open item -- remaining towers are tank-modal + residual splice);
body spectrum still bottom-heavy vs the ref above 4k (the ref's shifter
path is bright by design; ours shifts the full-band bloom -- a shifter
input HP needs a Y-table state slot, deferred until the ear asks).

Program: payload A FREE 50 (was 104). Cycles: room for new work 827.
make check green. NOT committed until Sam's ears pass the kit.

**Ear kit** (out/vv_ab/shimmer, level-matched to the VV body rms, mono
48k): {pad,stab,melody}_{VV,R18} + {pad,stab}_R17 (old engine at ITS best,
T118). Listen for: (1) splice harshness on the stab tail -- R17's zingy
6-9k vs R18 vs VV's wash; (2) sheen vs mud on the pad -- is R18's octave
thick where VV's is airy (the deferred shifter-HP question); (3) movement
-- does R18's chorus now breathe like VV; (4) does the long tail hold its
energy (the md change) without ringing metallic.

### R18 ear round -- the artifact hunt, and what actually shipped

Stab first: tail "brilliant", but "their primary tone is much more forward
... and goes for longer." Three levers tried IN THE WET SUMS for the
forward primary, two retired by ear:

- ❌ PRESENCE TAP ($1b raw diffuser chain into the sums): built, sounded
  right on the stab, retired -- the archived $15-stutter warning applies to
  its transient response, and it was never exonerated in the glitch hunt.
- ❌ BLOOM RAISES (0.5x -> 1x/1.5x/2x, g 0.867 -> 0.91): stab loved them
  ("length is perfect", "reaaly nice") -- and the melody FALSIFIED them:
  "fast glitchy artifacts." Bisected by ear on 4 s snippets: presence off
  -> still there; g back to 0.867 at 1.5x -> STILL THERE; level back to
  0.5x -> gone. The bloom allpasses' impulse response is a sparse 41/29 ms
  pulse train; above ~0.5x it reads as flutter on plucked transients at ANY
  g. The bloom stays exactly at R13's voicing (0.5x, g=0.867).
- ✅ DRIVEN LINES BACK IN THE SUMS at half weight (l3 -> L, l7 -> R, kept
  split for width). Dense, input-correlated, rings with the tank's own
  decay, no pulse train. Melody "clean", stab "yep good", pad "good, not
  quite as forward but good enough if we have to meet in the middle."

**GATE=0 BUG, found mid-hunt and FIXED**: the R16 gate's trigger threshold
is 0.094 FS on the tank input, and GATE=0 merely set a 95 s hold -- it
still needed ONE loud trigger to open. Quieter sources never opened it
(a -12 dB melody rendered at -146 dB: SILENT), and material with a quiet
opening got per-attack open/shut chops. GATE=0 now forces GCNT full +
GLVL open every block: a true bypass. This also retracts the "16-bit
floor" reading of the silent quiet-click renders (stability falsifier
above -- the sweep itself, run at -10 dB, stays valid: the click DID
open the gate).

Hunt lessons, at protocol level: (1) the glitch was inaudible to every
metric tried (click detector, HF flux, envelope jumps, linearity null --
the null itself was invalidated by the gate bug) and was localized only by
EAR-BISECTING 4-SECOND SNIPPETS -- cut the audio, not the lever list;
(2) two naive linear resamples in the kit pipeline (48k source -> 44.1k
render -> 48k kit) were a real, separate artifact Sam heard first -- kit
files are now built at the render rate with a sinc-resampled source.

**Final R18 stack** (tag 37): single-octave shimmer off the bloom branch;
sub-sample interpolated heads; the R17 x1-clobber fix; BIG md 0.676 /
damping 0.90 / wet high-cut 0.60; pre-shift LP 0.45; driven lines at 0.5x
in the sums; GATE=0 bypass. Kit files: {stab,pad,melody}_R18i vs _VV in
out/vv_ab/shimmer.

**Verdicts (Sam), final kit:** stab "yep good"; melody "clean"; pad
"good, not quite as forward but good enough if we have to meet in the
middle." Open for next round: the pad's last bit of forwardness (a driven-
line weight between 0.5 and 1, or per-mode), 6-9k crest still 32 vs VV
19.5 on the pad, and the deferred shifter-input HP (Y-table state).

---

## BongDelay v2 stage 5 -- GRAIN, ear round 1 (12 Aug 2026)

**PASSED FIRST TIME**, which no BongDelay mode had done: PITCH's first ear
pass failed the splice and needed a window fix, a retraction, jitter and
the cascade cut before it was usable.

Kit: `out/grain_ab/melody_{clean,spray0,spray64,spray127}_lvl.wav` --
Sam's own `melody_1_dry.wav` (48k mono) through the DS layout, TIME 40,
FDBK 45, MIX 110, PTCH +12, level-matched to -20 dBFS rms with peak
protection (the GRAIN variants needed +12.5 to +13.2 dB against CLEAN's
+8.7, which is the scatter's own level cost showing up).

Presented in one order, one file per play, narrated: CLEAN as the
baseline, then SPRAY 0 / 64 / 127.

**Verdict (Sam): "spray killed robo and 127 was good as well."**

That is the stage-2 defect closed by the mechanism it was diagnosed for.
The PITCH ear pass established that the "robo" was PERIODICITY -- two heads
a fixed distance apart cancelling on a metronome -- not window shape, and
that widening the window only moved the rate (buzz -> flutter, both
rejected). GRAIN attacks it directly: four grains, each re-randomising its
source position at its own wrap, so the cancellation is aperiodic. SPRAY=0
is the control that makes this legible -- it puts all four grains on ONE
read, i.e. deliberately back in the coherent regime -- and the knob's
effect is exactly the difference between the two.

BOTH ends of the usable range pass, so SPRAY is a character control rather
than a "find the one good value" knob. Default stays 64 (mid).

Measured alongside, for the next round rather than against this one:

| | reference granular | GRAIN |
|---|---|---|
| L/R correlation, WHOLE FILE | +0.51 (melody/pad/stab), +0.72 (hat) | **0.00** |
| L/R correlation, GRAIN LAYER ONLY | **0.00 / +0.03 / -0.02** | **0.00** |

⚠️ **RETRACTED 13 Aug 2026: "GRAIN is WIDER than the reference device" was
wrong, and the whole-file row is why.** The reference is not a wet render --
it is `dry + grain layer`, with the MONO dry sitting at exactly 0.707. That
mono dry is what pulled the whole-file correlation to +0.51. Fit the dry out
(scalar least-squares, per channel) and the reference's grain layer alone is
uncorrelated, same as ours. **The two agree; there is no width gap.**
Falsifiable the same way it was found: refit the dry, remeasure the
residual. The old lever advice (PING crossfeed, or correlating the two
lines' scatter) applies only if an ear reports "no centre" -- no
measurement asks for it now.

Also: the reference files carry content only in their
first ~25-35 s; the rest of each is trailing silence.

Still unheard, and the two combinations the design was built toward:
FREEZE + GRAIN (the texture hold) and GRAIN through the ->VERB send (the
delay->reverb wash the whole framing assumes).

---

## BongDelay v2 stages 5b–5e — the voicing pass (12–13 Aug 2026)

Method: Sam's own source material (`melody_1_dry.wav` and friends, 48k mono)
rendered through the DS layout, level-matched, one file per play, narrated.
The reference was **his own granular** applied to the same samples
(`melody_3.wav` et al.) — the first time this project has had a target
rather than an adjective. Content in those files is only the first ~25–35 s;
the rest is trailing silence.

**Sam on which source shows it: "melody is an especially good one to display
the musical random sounding pitched repeats and the smooth glassy sound."**
Those two phrases drove every change below.

### Round 1 — SPRAY sweep (0 / 40 / 80 / 127), wet only

Verdict: **"they were all granular in that they had random grains playing.
But there was still a lot more of the melody lines playing and it was just
kind of changing pitch of beat and every now and then."**

Two findings in one sentence, and both were structural:
- "a lot more of the melody lines playing" → the four grains sum to exactly
  1.0 at all times, so the output is GAPLESS. The flat-sum rule came from
  PITCH, where ripple was the defect; in a granular the gaps ARE the
  texture. → **DENSITY** (stage 5d).
- "changing pitch every now and then" → the interval rolled at 1-in-8, a
  measured hold of 3.5 × TIME. → **1-in-4**, measured at 1.05 × TIME.

### The rate criterion, because "which is best?" deserved an answer

Sam, fairly: **"best in what way?"** The target character is *repeats at
different pitches*, which fails in two directions — hold much longer than a
repeat and many repeats share a pitch (harmonic drift); much shorter and the
pitch changes DURING a repeat (warble). So the criterion is **hold ≈ 1–2 ×
TIME**, which is measurable rather than a taste call:

| roll rate | hold | × TIME (161 ms) | reads as |
|---|---|---|---|
| every wrap | 64 ms | 0.40 | warble, changes 2.5× within a repeat |
| 1 in 2 | 109 ms | 0.68 | still sub-repeat |
| **1 in 4** | **170 ms** | **1.05** | **one interval per repeat** ✅ |
| 1 in 8 | 559 ms | 3.47 | 3–4 repeats share a pitch |

The criterion picked a value none of the three offered variants had, which
is why it was derivable rather than guessable. ⚠️ The pocket is TIME-
dependent and the dice are not: the hold is ~170 ms absolutely, so it drifts
out of the pocket at TIME extremes. Tying the probability to TIME needs a
reciprocal and a slot neither of which exists yet.

### Round 2 — "sounds nothing like a granular", and a wrong diagnosis

Sam: **"Are we choosing the end sound or an aspect? This sounds nothing like
a granular just sounds like a slightly effected verb."** Both halves fair —
the roll rate had become the whole conversation while the gross balance had
never been auditioned.

⚠️ **Two causes were offered and one was invented.** The claim that a unity
dry was swamping it was reasoned from `out = dry + wet*MIX` in the source;
the harness says `-inmask` feeds the SENDS only, so a server's own track is
silent and every `--pick D` render was already 100% wet. The real cause was
duller: those renders were `--pick R`, the reverb's output. **Do not judge
the delay through the reverb** — it is a wash with grain in it.

What survived is a genuine hardware defect the harness could not see, and
`--inall` was added so it can (dry remaining 100/53/7.1% at MIX 0/64/127).

### Round 3 — density, and a bug an ear caught in one pass

Sam: **"plays random high grains on left side and a noise wash on the right.
dens seems to be working though."** The density mechanism was fine; the
noise was a condition-code clobber between two Tcc's (now a CLAUDE.md trap).
R's zcr 10888 → 744 against L's 739. **`make check` and the bit-identity
gate were both GREEN through this** — the code was deterministic and every
mode assembled. Only ears found it, which is the argument for auditioning
every stage rather than trusting the gate.

Then: **"both sides working now. It's still jumping around in a not very
musical fashion, but is starting to work more like granular."**

### Round 4 — the split

Narrowing the set to {+12, +7} was "somewhat better" — the wide leaps were
part of it. The rest was structural and is stage 5e: all four grains shared
one accumulator, so a roll made the whole layer leap at once, and **unison
was unreachable** (rate 1.0 → the age never advances → no wrap → no
re-scatter). "Mostly at pitch, some shifted" is most of what makes a cloud
musical, and it was not in the set because it *could not be*.

### Where it stands

Mechanically GRAIN is now a real granular: independent per-grain pitch,
position, and on/off, with unison in the set. ✅ **EAR PASS ON THE SPLIT
(13 Aug): Sam, "yeah it was good."** So the direction is settled and the
grain core is done being redesigned — the remaining work on GRAIN is
voicing and cost, not mechanism.

Open voicing questions: where DENSITY and SPRAY should default,
whether the interval set wants weighting toward unison rather than uniform
draws, and grain SIZE — now a free parameter for the first time (it is one
constant in the schedule step) with no page-2 slot left to put it on.

---

## GRAIN stage 5g — the reference-matched pass (13 Aug 2026)

Method changed, and that is the headline. The reference granular was
finally **measured** rather than described: identified as **Efx Fragments,
preset "1 Bar Glimmers"**, and — critically — found to be `dry + grain
layer`, with the mono dry sitting at exactly **0.707 (-3 dB, equal-power
50/50)** in all four of Sam's sources, both channels. Every number below is
taken on the RESIDUAL after fitting that dry out. Doing this retracted the
"+0.51 vs our 0.00, ours is WIDER" reading recorded above.

### The metric that found what the others could not

Level, gaps, L/R correlation and the shift histogram all MATCHED on the
first pass, and Sam still said: *"those sound close now but the nature is
completely different. Ref has sparse melodic musical pitches. Ours all have
dense fast changing (oscillating?) pitch."* Every one of those metrics is
TIME-AVERAGED. What sees it is the **envelope modulation spectrum + spectral
flux of the grain layer**:

| | flux | 0.5-4 Hz | 4-20 Hz | 20-120 Hz |
|---|---|---|---|---|
| reference | 0.0168 | **63.6%** | 21.2% | 15.2% |
| shipping GRAIN | 0.0248 | 34.8% | 31.0% | 34.3% |
| **v3 (DENS 45)** | 0.0083 | **63.9%** | **21.0%** | **15.1%** |

### What each round established

1. **A REGRESSION, found by ear.** 5e dropped 5b's interval roll: the rate
   latches at EVERY grain wrap, so with four grains at quarter offsets the
   cloud re-pitches every 11.6 ms. Both gates were green throughout.
2. **The first fix was WRONG, instructively.** Gating the SHARED candidate
   holds one pitch across the whole cloud. Sam: *"more like a pitch shifter
   than granular."* The gate belongs on each grain's OWN latch.
3. **"Not very many actual different notes"** -> the 4-entry set became 8
   (unison x2, +12, +7, +5, -5, -12, -19), indices 0/1/2 unchanged.
4. **Grain SIZE is the envelope lever, and it is line-bound.**
   `ceiling = 16382 - (r_max - r_min) * L`, which reproduces the shipping
   13310 exactly. **Per-grain reset** changes it to `16382 - max|1-r|*L`,
   which is what bought L=8192 (186 ms) with +12 kept.
5. **Down-only was tried and REJECTED BY EAR** — *"down only isn't going to
   cut it as the only approach"* — despite being the cheapest route to long
   grains. It also raised 20-120 Hz from 20% to 33%, **cause unknown**; TIME
   sweeps do not move it, so the read-near-the-write-pointer explanation is
   falsified. Set aside, not solved.

### ✅ EAR PASS, on `dsp/delay_grain_v3.asm`

**Sam, on melody at DENSITY 45 and 80: "both sound great."** Earlier in the
same pass: *"sounding better and better"*, and on the 93 ms build *"that
classic granular sound but not too over the top like an Eventide Crystals"*.

**BOTH ENDS OF DENSITY PASS, so it is a character control, not a
find-the-one-value knob** — the same conclusion SPRAY reached in 5a, and the
argument for leaving it mid. The trade it spans is real and measured:
DENS 45 matches the reference's modulation split almost exactly but leaves
the grain layer ~8 dB under the dry; DENS 80 brings that to ~-6 dB with gaps
at the reference's 6.9%, at the cost of more 20-120 Hz.

### The demo pass (13 Aug) -- two findings the metrics could not have given

Sixteen renders across the Discord demo sources (band / drums / guitar /
piano), four voicings varying BOTH the delay and the reverb, all through the
FIXED `->VERB`. Two verdicts from Sam:

- ⚠️ **"It sounds a lot better lower."** Every voicing was re-mixed **6 dB
  down** -- shifting each rather than flattening them to one number, so each
  keeps its own grain-vs-wash balance. The set now runs grain -11 to -18 dB
  under the dry, where it started at -5 to -12. **The engine was being
  auditioned too loud all session**, including in the melody/pad/stab
  rounds, which were judged at roughly the dry's own level.
- ⚠️ **THE INTERVAL SET IS SOURCE-DEPENDENT, and this is the one thing no
  measurement here could have found.** On a whole-band recording Sam
  preferred **set 1 (unison + 12 only)** over the wide 8-entry set 3, at
  identical settings and level. The wide set's -19 / -5 / +5 grains land as
  WRONG NOTES against a full arrangement; on a solo line (melody, pad, stab)
  the same set ear-passed. **Nothing in the modulation spectrum, the shift
  profile, the gap statistics or the flux can see a wrong note against a
  chord** -- the same class of blind spot as the pitch oscillation, but
  harmonic rather than temporal.
  → This is an argument for KEEPING the PTCH select's set-WIDTH meaning
  rather than treating set 3 as simply "the good one", and it means the
  DEFAULT should probably be narrow, with width as the character control.

### Defaults this pass recommends

MODE GRAIN, interval set **3** (the wide 8-entry draw), TIME **32**,
FDBK **127**, SPRAY **64**, TONE **127**, DENSITY **45-80**.
⚠️ **SPRAY must not be 0** — it collapses the grain layer's L/R correlation
from 0.00 to **+0.50**. (The SHIPPING default is already 64 and always was;
the 0 is `send_probe`'s test default, which is what produced the measurement.
Noted so nobody "fixes" a default that is already correct.)

### Two claims from this pass that were WRONG and are retracted here

- **"4->2 grains saves ~60 cycles"** — a mis-citation of 5f's different
  restructure. Halving the grain count halves the roll, so it is order
  **300** cycles. 🟡 inferred from 5f's measured 289w + 609-cycle split.
- **"Sub-4 Hz is the Crystals direction Sam ruled out"** — wrong reading.
  Sam: *"when I ruled out crystals it wasn't the bar length it's always just
  heaps and heaps of crazy sounding busy notes."* Crystals fails on
  BUSYNESS, so sparser is TOWARD the target, and 63.6% stays legitimate.

### ✅ GRAIN THROUGH `->VERB`, heard for the first time (13 Aug)

One of the two combinations PLAN had listed as unheard since GRAIN landed.
Rendered honestly: BOTH outputs taken from ONE `--layout RDS` run (`--pick D`
and `--pick R`), so the wash really is this grain through ChonVerb rather
than a separate reverb pass, then summed offline against the dry at the
approved DENS 45 balance. **Sam: "sounds great."** at wash -8 dB and +2.9 dB
relative to the grain.

⚠️ Two things not to over-read from those files: the balance is CHOSEN
OFFLINE (no single render gives dry + delay + wash in hardware
proportions -- on the unit those come from the real send knobs), and the
level below is a genuine defect.

~~⚠️ **`->VERB` SATURATES: a MEASURED defect, not a suspicion.** At VRBW 100
with the reverb's own track live the REVERB output peaks at **1.000 FS**.
VRBW 25 gives 0.220 and VRBW 50 gives 0.426, so the usable range is roughly
**VRBW <= 50** and the knob's printed 0..127 is mostly unusable headroom.
This is the unregistered x8/N writer already on the voicing list; fix it
before the cross-send ships.~~

✅ **CLOSED 17 Aug 2026 (BongDelay v3 stage 1) -- BY DELETING THE KNOB.** The
/8 half landed in 5g; the range refit never did, and v3 made it unnecessary:
`->VERB` is now a hardwired constant (`$7fffff`, the maximum a Q1.23
multiplier carries -- ear-picked 17 Aug from $2d0000 / $5a0000 / $7fffff on
GRAIN through ChonVerb; Sam took the loudest, and max is exactly ONE FULL
CLIENT'S SHARE of the reverb bus, the most any single track can drive it) and the send
REGISTERS in the REVERB count, which was the deferred half. Both were needed
together: an unregistered writer's effective level is x8/N_registered, so a
"fixed" amount would still have drifted ~18 dB between one sender and eight,
and a constant that is not constant is worse than a knob. VRBW (p5) and VRBD
(p8) are retired.
⚠️ **The falsifier went with it.** The 12 Aug proof that `->VERB` works was
"VRBW=0 renders digital silence"; there is no knob to zero now, so that
control has to come from a build flag instead. The 17 Aug isolation control
used `->DELAY` at 0 (nothing reaches the delay, so nothing can reach the
reverb) and did render digital silence.
✅ **The constant HAS now been heard** (17 Aug, three-way A/B on GRAIN through
the reverb, Sam: "the loudest was best"). ⚠️ Still a value that cannot be
changed without a flash, and the A/B summed delay and reverb at UNITY faders
where the unit has two separate tracks -- so what was really being judged is
how hard the delay drives the reverb relative to other SENDERS, not the
audible balance, which is a fader.

### Still open

- ⚠️ **FREEZE + GRAIN IS NOT MERELY UNHEARD -- IT IS UNHEARABLE WITH THIS
  HARNESS, and that is a finding, not a to-do.** `DFRZ` is a BUILD-TIME
  constant, so a frozen build is frozen from sample 0: the line never takes
  input and the engine loops silence. Measured 13 Aug -- peak **0.003 FS**.
  The reason the override exists at all is the same reason it cannot
  demonstrate the mode: slot 11 is a companion LOW-BYTE field and
  `dsp_host`'s `-params` cannot drive one, so FREEZE can never be toggled
  MID-RENDER. Hearing it needs one of: a DEV-only "freeze after N samples"
  hook (~10 words), extending `dsp_host` to drive companion fields, or
  hardware. The same blocker applies to ANY audition that needs a
  companion-field change part-way through a render.

- ✅ **THE `->VERB` SATURATION IS FIXED** (in `dsp/delay_grain_v3.asm`), and
  the cause was exact rather than guessed. `dsp/send_client.asm` scales its
  contribution by **1/8** before accumulating and registers in the Y:$983
  SEND COUNT; `reverb_server` then applies the 1/N auto-gain and `asl #$3`
  to undo that headroom. The delay's `->VERB` write did NEITHER, so the
  reverb's `asl #$3` amplified it **eight times**. One `asr #$3,a,a` on the
  combined contribution fixes it, and the measurement confirms the factor is
  exactly 8: isolated reverb peak at VRBW 25/50/100/127 went
  0.220/0.426/~0.88/1.000(clipped) -> **0.027/0.055/0.110/0.140**, linear
  across the whole knob with no saturation anywhere.
  ⚠️ **HALF THE BUG IS DELIBERATELY LEFT**: this send still does not
  REGISTER in the send count, so N excludes it and the auto-gain divides by
  one client too few. Fixing that changes the balance of every OTHER send on
  the bus, so it wants hardware thought rather than a same-session patch.
- The interval hold is **no longer load-bearing at L=8192**: disabling it
  entirely leaves flux unchanged (0.0083 either way). It was a real fix at
  46 ms grains. 13 words; keep until an ear says otherwise, but do not
  describe it as carrying the sound.
- **Flux is still half the reference** (0.0083 vs 0.0168) at a matched
  modulation split. Structural: the reference uses SHORT grains spaced
  SPARSELY, we use LONG grains overlapping DENSELY.
- **hat still does not match** — the reference is loud AND sparse (-6.7 dB
  at 72% gaps, crest 27); our density gate only subtracts, so we get
  -3.9 dB at 21% gaps or -9.4 dB at 75%, never both. Needs makeup gain on
  surviving grains, which does not exist.
- pad, stab and hat have not had an ear pass on v3 at all.

## R45 — shifter-input HP corner + wet makeup slope (23 Aug 2026)

**HP corner, judged by ear on the 4-corner ladder** (melody, SHMR=100,
wet-only, peak-normalised; files oct_570/oct_280/oct_170/oct_off in the
session scratchpad): Sam heard the flashed 570 Hz as "a bit thin" on
hardware; on the local ladder "second one [280 Hz] is good". Shipped
c = $050000 (~280 Hz). 170 Hz and off remain unheard-by-comparison —
reopeners if 280 still reads thin on the unit.

**Wet makeup slope ×(1+IN) → ×(1+2·IN)** ("reverb could still be mixed
louder"). Measured on melody (hot, sustained) and clap (percussive):
clap wet at IN=127 now −34.3 dBFS vs dry −23.5 (11 dB under; was 20 before
any makeup), zero clipping. Melody clips the store above IN≈90 (7302
clipped samples at 96, none at 64) — the knob's top is for sparse/quiet
sources, by design. Dry ducking was considered and REJECTED by Sam as the
old crossfade road.

## Full MIDI-driven hardware voice pass (24 Aug 2026, evening)

Sam's own set on the unit (R57), driven end-to-end over MIDI (`tools/hw_sweep.py`:
scripted CC/notes -> EVO4 capture -> metrics; Rytm-over-USB transport control;
chromatic note 84 on a track's channel as the deterministic one-shot stimulus —
sample-trig notes 36-43 never fired and T1 turned out to be a THRU track from
the Rytm, so chromatic one-shots on T3/T4/T6 are THE stimulus method).
Layout measured: T1 thru (Rytm), T3 bass + BongDelay, T4 acid, T5 ChonVerb,
T6 lead, T7 empty, T8 master. Wet-only instrument: solo the host track
(+ AMP VOL 0 on T3 so only bus-fed wet remains).

**Levels: NO clipping anywhere, on either effect, at any page-1 setting or
stacked extreme.** Reverb: 3 senders at 127 + TIME/SIZE/MOD 127 -> wet peak
−20 dBFS; delay: FDBK 127 held 12 s, no runaway (−20.7); full mix all sends
127 + FDBK 100 + series -VRB 127 -> −17.4 dBFS peak. Reverb TIME 20->127
raises steady wet only +4.8 dB. Modes ROOM/PLATE/BIG now span only ~3.6 dB
at equal send (BIG quietest; the old clip knee unreachable, re-confirmed with
one-shots). GATE 16 and SHMR 90 level-safe; Sam's stored part runs both hot
and every capture inherited that state (by design — his set is the deliverable).

**Pitch: exact, no adjustment needed.** Note->interval (R57) on real material:
+12/+6/0/−5/−12 all land within the estimator's 1/4-semitone floor (log-f
spectrum cross-correlation dry vs wet, `hw_sweep.shift_semitones`). GRAIN
scatter (DRV 80) fragments the 790 ms periodicity comb into 150-800 ms spread
at unison pitch, deterministic per trigger; wow (DPTH 90) smears the lead
fundamental 129 -> ~190-250 Hz width. REVERSE verified by envelope
cross-correlation against time-reversed dry (0.121 vs 0.085 fwd on lead).
FREEZE: hold flat ±0.5 dB over ~25 s, input correctly ignored while held,
**no audible seam (Sam's ear)** — the R43 crossfade fix confirmed on hardware —
clean release.

**Open ear items (the honest residue):**
- **PING lean**: at PING 127 (default) the wet leans ~8 dB left at FDBK 60;
  at FDBK 0 the right channel is SILENT (single hard-left slap). Inherent to
  the serial ping-pong (R only receives L's feedback). With no send-fed
  makeup this is the whole "delay reads quiet vs reverb" story (−5 dB L /
  −13 dB R at equal send). Candidate fixes, unbuilt: input into both lines
  at high PING, and/or +4 dB send-fed wet makeup (one instruction, output
  stage). Needs Sam's ear ruling first.
- ~~GATE slam-time unmeasured~~ **RETRACTED same evening: it WAS measured** —
  at GATE 16, cutting the send left the capture (opening ~0.4 s later)
  silent: the wet shut in <400 ms, vs a seconds-long tail at Sam's stored
  high GATE. The 'failed' gatecut captures were the result.

**Instrument notes:** a capture chain can lie several ways in one evening —
**stopping the transport mid-pattern leaves any LOOP-enabled sample droning**
(the "mystery constant signal" episode: balanced L/R, identical stats across
different stimuli — first misread as the EVO4 capturing its mics, which is
RETRACTED; the EVO4's post-sleep 96 kHz renegotiation was real, the mic
theory was not); the Midihub silently reverted to its stored preset (params
40-45 passed, notes + CC 49/50 blocked — SAVE the pipe config to a preset);
and a card pulled mid-session degrades Static-machine stimuli. Every "it
went quiet" had a rig cause, never a DSP one.

**Cross-bus residual check (same evening):** the open "T4 sending + delay
MODE 1 (CLEAN)" combo from XBUS.md, on Sam's set layout (ChonVerb on T5 as
housekeeper, delay on T3): rolling-pattern and one-shot wet captures show no
hash (CLEAN wet correlates 0.90/zero-shift with the PITCH wet of the same
stimulus), and **Sam's ear on the monitors: "sounded clean."** Caveats: T2
carries no audio in this set (that axis untestable here), and artifacts
RELOCATE — this clears this layout, not the residual; its suspected
structural cause stays open in XBUS.md.

## R58 — PING balance + delay return makeup (24 Aug 2026, late evening)

Sam's ear pass on local renders ("sounds good", drums A/B, wet-only,
PING 127 FDBK 60): **both wet channels gain x1.5 (+3.5 dB), and R
additionally gains 0.75*PING*wet** — output stage only, loop gain and the
->VERB stash untouched, so bus levels and the series path are unchanged.
Measured (emulator, send path): lean at PING 127/FDBK 60 +7.9 -> +4.4 dB
on drums/bass/melody alike; PING 0 exactly symmetric (no shelf); FDBK 20
worst case 17.5 -> 14.0 dB; no clipping on any render (drums peak -2.4).
At FDBK 0 the right line still has no repeat to lift — inherent to the
serial ping-pong, accepted. Tag 77. FLASHED + hardware-ratified the same night: lean +4.2/+4.6 dB on the unit (predicted 4.4), wet +3.8 dB (predicted +3.5), no clipping. (Flash detour for the record: a raw mainos_bus.bin on the card gives LENGTH ERROR — the card path needs `make image` ELUP packing, one OS bin on the root at a time; the "wrong checksum" complaints that evening were PROJECT files, not the OS.)

## R59 — the VintageVerb refs revisited on the current engine (31 Aug 2026)

The Round-12 A/B kit rebuilt from scratch against the CURRENT build:
`out/vv_ab2/` (12 pairs, {pad,stab,hat,melody} x {ROOM,PLATE,BIG}, A = the
9 Aug VV bounces, B = wet-only ChonVerb, 24-bit 44.1k STEREO — width has
been pinned wide since v6, so the Round-11 mono limitation is gone), built
by `out/vv_ab2/build_kit.py`: ffmpeg-sinc prep (no naive resample in the
path), -20 dBFS active-RMS level match with the peak trim applied to the
PAIR jointly, decay re-matched by peak->-40 dB tail time on the stab.

**The Round-13 decay match had drifted with the engine**: ROOM = TIME 24
(was 56 — ran ~0.5 s long), PLATE = 64 (unchanged, matches VV plate at
2.20 s to the frame), BIG = 38 (was 44). DIFF=120 carried over from the
old recipe for the kit renders.

**Sam's verdicts** (stab PLATE/ROOM/BIG, hat BIG, pad BIG, melody ROOM
played A/B): "ours are all wetter sounding but sound pretty good"; stab
ROOM early tail "a bit" thicker than VV, "but the primary doesn't go as
long. not necessarily a bad thing."

**"Wetter" localized to DIFF in-session.** All pairs are level-matched
wet-only, so wetter = energy distribution, and the early-tail slopes agree
(every stab/hat B row shallower than its A: stab ROOM -18.4 vs -23.2, hat
BIG -17.8 vs -29.9 dB/s). One knob change, stab PLATE DIFF 120 -> 64:
early-tail slope -18.0 -> -21.3 dB/s against VV's -19.0, and Sam on the
render: tightens up, "still a bit shorter but similar ballpark." The match
point is ~DIFF 80-90, bracketed not measured.

**Found while calibrating, parked as open items:**
- **ROOM's early tail has a TIME-independent floor**: TIME 16->56 moves the
  0.4-1.6 s stab slope only -19.0 -> -15.6 dB/s (VV room -23.2). Something
  in the early tail (bloom/driven-line energy?) decays at its own rate.
  Inferred candidate only — needs a probe, not a guess.
- **BIG has a knee between TIME 38 and 44**: peak->-40 dB on the stab jumps
  2.7 s -> 15.2 s (the inter-hit tail stops dropping 40 dB at all). Half of
  BIG's dial is effectively infinite. Unknown whether real slow decay or a
  scatter/truncation floor — one measurement would say.
- **hat BIG still shows the inverted-HF signature** (-17.8 vs VV -29.9
  dB/s) — the one row where HF outlives the mids on the current engine.
- **The TIME dial's useful range has drifted off the knob**: a VV-matched
  2 s room lives at TIME 24/127. Per-mode TIME re-mapping is settings work,
  no engine change.

Direction agreed in-session: settings first (DIFF character/default, TIME
range re-map), the BIG damping + knee measurements after. The kit and its
build script stay in out/vv_ab2/ (gitignored; script is self-contained).

### R59 addendum — Sam, after the session's DIFF finding landed

"verb is actually sounding really nice to me now." The reverb tuning
urgency drops; the settings items (DIFF default/range, TIME re-map) stay
queued but the sound itself passes. Focus moves to the delay.

## R60 — REVERSE diagnosed: the ring is the segment comb (31 Aug 2026)

Sam, from the remixer (piano_chords, TIME 68 FDBK 79 PING 16 -VRB 61
DPTH 48 RATE 18 PTCH 1 DRV 55): REVERSE "sounds not great ... a fast
metallicy ringing that seems to be specific to reverse."

**Diagnosis, measured then source-confirmed — working as built, with a
sweet-spot problem:**
- No defect: no splice clicks in any variant (max inter-sample step
  0.04 FS); wow, DRV and -VRB each exonerated by isolation renders
  (out/vv_ab2/prep/rev_*.wav, journal-driven exact repro).
- The ring is a comb at ODD multiples of ~10.8 Hz = the 2S period of
  PTCH=1's 46 ms segment (REVERSE sizes: PTCH 0/1/2/3 = 93/46/23/12 ms,
  delay_server.asm rsz table). On SUSTAINED harmonic material a reversed
  46 ms chunk is the same chord re-phased, so the comb is all you hear;
  FDBK 79 restacks it every repeat. Spectral diff vs CLEAN at identical
  knobs: +13 to +23 dB on the comb lines (rev_spec.py).
- Ear-confirmed: PTCH=0 (93 ms) on the piano "a bit" better; drums at the
  same settings read as texture, not ringing. The wav wasn't wrong -- it
  was the revealing case.

**Work items opened:**
1. SETTINGS: REVERSE's useful sustained-source range is basically PTCH=0;
   1-3 are stutter/texture. Same family as the reverb's TIME drift (R59).
2. STRUCTURAL: 93 ms is the CEILING -- reversing S samples spans 2S of
   history and the 16K line caps S at 4096. A musical phrase-reverse
   (0.5 s+) needs a longer line: a payload-B memory-layout item, not a
   knob. Parked on the delay design list next to GRAIN makeup gain
   (DENS = the DPTH/WOW knob in GRAIN; sparse still only subtracts).

## R61 — GRAIN density: the knob that barely existed, fixed + makeup gain
## (31 Aug 2026, ear-passed on local renders)

**The DENS knob was a two-position switch, and nobody knew.** The decode
fed the 3-bit gate comparison knob>>1 (the $2d slot holds knob<<13 and the
gate shifted down 14), so every knob value >=15 saturated to full density:
the whole musical range lived in knob 0..14 and the shipped default (48)
was silently "always full". Measured before the fix: FLAT from DENS 16 to
127, -7.1 dB only at 0. Every GRAIN density impression ever formed on a
default-ish knob was full-density. Fix: shift 17 (knob>>4 -> dens3 0..7),
both draw sites; the dial now tapers smoothly across its full travel
(0/-0.4/-1.0/-1.9/-2.8/-3.8/-5.4/-7.1 dB at dens3 7..0).

**Makeup gain built on top** (the PLAN §1 item): per-sample coeff
1/2 + (7-dens3)/14 (Q23, top of ramp $7FFFFF by construction), parked in
GRAIN's $57 (dead from the pre-hoist park until the reader's t0 park),
multiplied into the window in the builder -- 1/2 at full density is the
old fixed halving exactly. Measured after: **flat within +-1.2 dB across
the whole dial** (cap +6 dB, so DENS 0 keeps a -1.2 dB residue).

Verified: CLEAN/PITCH/REVERSE renders BIT-IDENTICAL before/after;
make check green; encodings proven by standalone dsp_asm listing
(asr #$11,a,a = 0c1c22, mpy x0,y1 = 2000c8 signed, constant intact) and
image bytes. Cost 25 words -- **payload B FREE 5, the pool is spent**.

**Sam's ear, sparse (DENS 16) A/B before/after makeup: "sparse sounds way
better now."** Committed on that verdict; hardware ear-ratify rides the
next flash (DSP-side change only, no descriptor edit, no new publish
risk).

⚠️ Behavior change on stored settings: DPTH 48 in GRAIN now means MID
density, not full. That is the knob working for the first time; the
makeup holds the level through it.

## R62 — REVERSE's default is the musical segment; the -19 check closes
## (31 Aug 2026)

**The R60 settings item, done in zero words**: REVERSE's size table indices
0 and 1 swapped, so the PANEL DEFAULT (PTCH=1) now selects the 93 ms
segment -- the one R60's ear round preferred on sustained sources -- and
46 ms moves to index 0. 23/12 ms stay at 2/3. Sizes unchanged, order
changed; the 93 ms line-ceiling item stays open (structural, and payload
B FREE 5 means it needs a space lever first).

Verified by exact exchange: new PTCH=1 render == the old PTCH=0 render
(rev_seg93, the one Sam ear-approved in R60) BIT-FOR-BIT, new PTCH=0 ==
the old PTCH=1 bit-for-bit, CLEAN/PITCH bit-identical, GRAIN untouched by
inspection ($62 unread by GRAIN; $60/$61 rewritten per-sample by its hoist
before any read). make check green; FREE unchanged at 5.

**GRAIN -19 interval: the reference-match swap LANDED long ago** -- the
shipping 4-entry set is +12 / unison / -19 / -12 (no +7; the wide 8-entry
set keeps +7 at entry 7). Verified in the set table this session; the
open-item note in the 30 Aug memory was stale. With this and R61, the
delay quality pass's buildable items are done: what remains on the list
is structural (REVERSE line length) or taste (a future ear round).

## R63 — GRAIN v4: Nimbus's grain readers over the delay lines (3 Sep 2026)

**The cycle lever for the BamSep26 rig, and a voicing change.** GRAIN's v2
engine (eight lerped heads, per-grain rates, a rolled builder) was 1,385 of
the delay's 2,372 worst-path cycles. v4 is Nimbus's engine over the delay
lines: four unity-rate grains, two per line a half period apart, integer
reads, one-multiply windows. `make cycles`: delay **2,372 → 1,255**, words
2,469 → 2,308, payload B FREE 5 → 166. Core 1 is no longer the tight core.

Kept: TIME as the read-back distance (it is still a granular DELAY), the R61
density law and makeup, SPRAY on DRV, FREEZE, the shifted-output routing.
PTCH becomes grain SIZE (23/46/93/186 ms), the same reading REVERSE gives it.
Gone: the pitched grains (+12 / −19 / −12 / +5 / −5 / +7). v4.1 = a
continuous grain PITCH on RATE, one rate for all four, Clouds-style.

Measured: DC gate −124 dB (windows sum to exactly 1, a0 multiplier right);
CLEAN/PITCH/TAPE/REVERSE/unknown-mode bit-identical to v3 (verify_delay
against the v3 source, only the three GRAIN cases differ); density law
−12.3/−8.7/−7.8/−8.0/−8.8 dBFS at DPTH 0/32/64/96/127 (sparse end 3.5 dB
down: two grains per line); **v4 is 3.3–3.6 dB quieter than v3** on real
material at matched settings.

⬜ Ear pass pending (Sam): `out/ab/grain_v4/` — `glow_intro` and
`guitar_dry`, `_v3` vs `_v4_lm` (v4 raised 3.45 dB to level-match). Listen
for: texture rather than pitch (no octave content now), the cloud morphing
rather than stepping, no zipper at grain edges, and whether the 3.4 dB should
go into the makeup law.

## R64 — GRAIN v5: four per line, pitched, PITCH mode retired (3 Sep 2026)

Sam heard v4's two-per-line cloud buzz at the grain rate with scatter up,
and asked where GRAIN's pitch had gone: a four-position switch cannot be a
pitch. So: four grains per line (v2's density), a continuous pitch on RATE
(±2 octaves, 64 = unison; the latched MIDI note when one is held), and
PITCH mode retired -- GRAIN at full density and zero scatter IS the
harmoniser. MODE is CLEAN / GRAIN / REVRS; the PTCH switch is SIZE, in
REVERSE's index order.

Two defects found by measuring pitch rather than DC: Nimbus's read geometry
plays an octave up at unity (955 Hz for 438 in -- the read moves with the
head AND the phase), and dsp_host's boot garbage in the latched-note slot
drove every local GRAIN render's pitch until the knob visibly did nothing.
Both fixed; `modules/nimbus/README.md` carries the first as an open item.

Numbers: delay 2,469 → 2,151 words (B FREE 323), 2,372 → 1,757 cycles.
Pitch law measured to the grain-rate comb (see the module README's table);
DC gate p-p 0; CLEAN/REVERSE/wow bit-identical to v3; density flat within
1.3 dB from DPTH 32 up; v5 ~6 dB quieter than v3 on real material at
matched settings (four decorrelated grains), a makeup decision for the ear.

⬜ Ear pass pending (Sam): `out/ab/grain_v4/` -- `_v3` vs `_v5_r64_lm`
(unison) and `_v5_r96_lm` (+12), glow_intro and guitar_dry.

