**Crush insert.** Drive into a wavefolder, hard/soft clip, then combined
bit-depth + sample-rate crush, with a feedback loop and tone shelf. MODE
**CHAOS** flips feedback polarity from a free-running ramp so the loop
self-modulates into hash and dropouts. **LIM** is a stereo peak limiter
after **MIX**. **MIX 0** is exact dry when **LIM** is 0.

![SHATTER: DRV → FOLD → CLIP → CRSH with FDBK loop into MIX, then LIM.](../../img/shatter/path.svg)

## Access

Select a track, press **`[FX2]`** (or **`[FX1]`** when the remix lists it
there), pick **SHATTER**.

## Operation

Start with **MIX** up and everything else at 0. Raise **DRV** into the
folder, **FOLD** for folds, **CLIP** for the brick, **CRSH** for bit/SRR
grit. **FDBK** recirculates the crush path. **TONE** shelves that loop.
MODE **CHAOS** flips **FDBK** polarity at **RATE**. Raise **LIM** to catch
the post-MIX peaks when the crush path is hot.

**DRV** 127 clips ordinary input levels. Keep it down, follow with
**CLIP**, or raise **LIM**, when the source is already hot.
MODE/**TONE**/**RATE** are easiest with **CLIP** open and **FDBK** up.

## Parameters

| Knob | Default | What it does |
|---|---|---|
| DRV | 0 | pre-gain on dry only (~×9 at 127); 0 is unity |
| FOLD | 0 | wavefolder; 0 skips; 1…127 only increases fold |
| CLIP | 0 | mid-chain clip threshold (0 open, 127 brick wall) |
| CRSH | 0 | combined bit-depth and sample-rate crush |
| FDBK | 0 | feedback around fold/clip/crush (needed for TONE/RATE/CHAOS) |
| MIX | 127 | dry/wet; 0 is exact passthrough when LIM is 0 |
| MODE | HARD | HARD / SOFT / CHAOS (CHAOS flips FDBK polarity) |
| TONE | 64 | feedback shelf: 0 dark, 127 bright |
| RATE | 64 | CHAOS polarity flip rate; ignored in HARD/SOFT |
| LIM | 0 | peak limiter after MIX; 0 off, 1..127 ≈ -2.5..-12 dB ceiling |

**LIM** leaves quiet passages at their original level. Higher settings lower
the peak ceiling from about -2.5 to -12 dBFS. It adds no makeup
gain. Hot signals see progressive gain reduction. At LIM max, block peaks cap
at about -12 dBFS.
