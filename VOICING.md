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
