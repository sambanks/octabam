SHATTER is a distortion and bitcrusher insert effect that chains input drive
into a wavefolder, a hard or soft clipper, and a combined bit-depth and
sample-rate crusher, wrapped in a feedback loop with a tone shelf. In
**CHAOS** mode, a free-running ramp flips the feedback polarity so the loop
self-modulates into noise bursts and dropouts. **LIM** is a stereo peak
limiter placed after **MIX**. Setting **MIX** to 0 gives an exact dry
passthrough when **LIM** is 0.

![SHATTER: DRV → FOLD → CLIP → CRSH with FDBK loop into MIX, then LIM.](../../img/shatter/path.svg)

## Access

Select a track, press **`[FX2]`** (or **`[FX1]`** when the remix lists it
there), and choose **SHATTER**.

## Operation

Start with **MIX** turned up and all other controls at 0. Raise **DRV** to
push the signal into the wavefolder, **FOLD** to add wavefolding, **CLIP** to
lower the clipping threshold toward a brick wall, and **CRSH** to add
bit-depth and sample-rate reduction. **FDBK** feeds the crushed signal back
through the chain, and **TONE** applies a tilt shelf inside the feedback loop.
In **CHAOS** mode, **RATE** sets how fast the feedback polarity flips.

**DRV** and **FOLD** both add gain ahead of the distortion stages. SHATTER
compensates for **DRV** after the chain, whereas **FOLD** uses partial
compensation so the folded signal gets louder as you turn it up (quiet inputs
can become noticeably louder at high **FOLD** settings). **CLIP**, **CRSH**,
and **FDBK** also affect both timbre and level, though **FDBK** uses a reduced
maximum loop gain to stay controllable. Use **MIX** to balance the wet signal,
and raise **LIM** to catch post-mix peaks when the processed signal runs hot.
**MODE**, **TONE**, and **RATE** are easiest to hear with **CLIP** open and
**FDBK** raised.

## Parameters

| Knob | Default | What it does |
|---|---|---|
| DRV | 0 | drive on the dry signal; output gain is compensated after the dirt stages |
| FOLD | 0 | wavefolder; 0 skips; higher settings fold more with partial output gain compensation |
| CLIP | 0 | mid-chain clip threshold (0 open, 127 brick wall) |
| CRSH | 0 | combined bit-depth and sample-rate crush |
| FDBK | 0 | feedback around fold/clip/crush with a reduced maximum (needed for TONE/RATE/CHAOS) |
| MIX | 127 | dry/wet; 0 is exact passthrough when LIM is 0 |
| MODE | HARD | HARD / SOFT / CHAOS (CHAOS flips FDBK polarity) |
| TONE | 64 | feedback shelf: 0 dark, 127 bright |
| RATE | 64 | CHAOS polarity flip rate; ignored in HARD/SOFT |
| LIM | 0 | peak limiter after MIX; 0 off, 1..127 ≈ -2.5..-12 dB ceiling |

**LIM** leaves quiet passages at their original level and applies no makeup
gain. Raising it lowers the peak ceiling progressively from about -2.5 dBFS
down to -12 dBFS, so hot signals receive increasing gain reduction and block
peaks cap at about -12 dBFS at maximum.
