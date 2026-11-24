# `shatter`: SHATTER

A per-track crush insert: drive into a wavefolder, hard or soft clip,
combined bit-depth and sample-rate crush, then a feedback loop with a tone
shelf. MODE CHAOS flips feedback polarity from a free-running ramp so the
loop self-modulates into hash and dropouts. DRV gain is compensated after the
dirt chain. FOLD gets partial output compensation. LIM is a stereo-linked peak limiter after MIX
(current-block peak + one block-rate div). MIX 0 is bit-exact dry when LIM is 0.

Sits beside CHARACTER (channel-strip dirt) and LOFI2 (modulator + SRR/BRR):
this one is self-modulating destruction.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | DRV | 0–127 | drive on dry only; output gain compensation follows the dirt stages |
| 1 | 1 | FOLD | 0–127 | wavefolder; 0 = off; higher settings fold more with partial gain compensation |
| 1 | 2 | CLIP | 0–127 | mid-chain clip amount (0 open, 127 brick) |
| 1 | 3 | CRSH | 0–127 | bit + sample-rate crush |
| 1 | 4 | FDBK | 0–127 | feedback around the crush path |
| 1 | 5 | MIX | 0–127 | dry/wet; 0 = exact passthrough when LIM is 0 |
| 2 | 6 | MODE | HARD / SOFT / CHAOS | clip flavour; CHAOS flips FDBK polarity |
| 2 | 7 | TONE | 0–127 | feedback shelf |
| 2 | 8 | RATE | 0–127 | CHAOS flip rate |
| 2 | 9 | LIM | 0–127 | stereo peak limiter after MIX; 0 off, ceiling ~-2.5..-12 dB (count=128 overrides DARK GATE's 0/1) |

**DRV** and **FOLD** add drive before the nonlinear stages. DRV's small-signal
gain is fully compensated after the dirt chain. FOLD uses partial compensation
to keep ordinary signals louder as the wave folds. In `dsp_host`, a 440 Hz,
0.3 FS sine measured 0.98x dry RMS at FOLD 64 and 0.71x at 127. The previous
full inverse curve measured 0.31x and 0.17x at those settings. At 0.003 FS,
the new curve measured 3.16x dry RMS at FOLD 64 and 4.23x at 127. Those figures
are `dsp_host` measurements; other signals, CLIP, CRSH, and FDBK change the
output level. FDBK's maximum loop coefficient is now 0.25.
On a 0.15 FS, 220 Hz sine with TONE 127, FDBK 127 raised late RMS by 2.47 dB;
the previous 0.5 maximum raised it by 5.9 dB. The gate checks this sweep with
LIM off. Raise LIM when the processed signal is already hot.

On 24 Nov 2026, Ilia tested the revised FOLD compensation on an MKII with
`CX CW.RMX`.

Page-2 MODE/TONE/RATE are easiest to hear with CLIP open and FDBK up
(CLIP 100 bricks the path so HARD≈SOFT and CHAOS is easy to miss).

Live icons (`ui.s`): FOLD and FDBK match CX OSC; CLIP sine→square; CRSH
sample-hold steps; MODE is brick / blob / shards; TONE is a shelf wedge
(flat at 64); RATE is tick density. DRV, MIX, and LIM stay stock dials.

## Storage and stock firmware

The page descriptor is cloned from **DARK REV**. A Part saved with SHATTER
keeps FX id `0x0a` and the page bytes. Stock 1.40C has no effect on that
id (it aliases to NONE in a stock chooser). If the same page bytes are
loaded under DARK REV, they read as DARK's knobs:

| our slot | our name | stock DARK |
|---|---|---|
| 0–5 | DRV…MIX | TIME, SHVG, SHVF, HP, LP, MIX |
| 6 | MODE (0–2) | PRE |
| 7 | TONE | BAL |
| 8 | RATE | MONO |
| 9 | LIM | GATE |

Keep a separate project copy, or re-select effects and save, before going
back to stock.

## Open

- CHAOS voicing: RATE curve and polarity-flip energy
- Whether CRSH should split into separate BRR / SRR knobs

## Current limiter

The shared implementation in `tools/remix/peak_limiter.py` measures both
channels of the current mixed block, then applies one attenuation in a
second pass. This catches the first transient, including at block boundaries.
No makeup gain is applied. Below the ceiling, dry input stays bit-exact
unless a preceding hot block is still releasing. LIM 0 bypasses attenuation
and clears the release state. LIM 1..127 sets a ceiling from about -2.5 to -12 dBFS.
The release is approximately 63 ms at 15 frames per block.

The earlier -18 dB maximum and previous-block gain are superseded. Hardware
reports above describe that earlier implementation. The new limiter awaits
a unit test. Regression renders cover signed transients at block boundaries,
quiet unity gain, stereo balance, and bypass.
