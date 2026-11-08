**Crush insert** — drive into a wavefolder, hard/soft clip, then combined
bit-depth + sample-rate crush, with a feedback loop and tone shelf. MODE
**CHAOS** flips feedback polarity from a free-running ramp so the loop
self-modulates into hash and dropouts. Beside CHARACTER (channel-strip
dirt) and LOFI2 (modulator + SRR/BRR): this one is the self-eating
destroyer. **MIX 0** is exact dry.

![SHATTER: DRV → FOLD → CLIP → CRSH with FDBK loop into MIX.](../../img/shatter/path.svg)

## Access

Select a track, press FX2 (or FX1 in remixes that list it there), pick
**Shatter**.

## Operation

Start with MIX up and everything else at 0. Raise **DRV** into the folder,
**FOLD** for folds, **CLIP** for the brick, **CRSH** for bit/SRR grit.
**FDBK** recirculates the crush path; **TONE** shelves that loop. MODE
**CHAOS** flips FDBK polarity at **RATE**.

DRV 127 clips ordinary input levels — keep it down, or follow with CLIP,
when the source is already hot. MODE/TONE/RATE are easiest with CLIP open
and FDBK up.

## Parameters

| Knob | Default | What it does |
|---|---|---|
| DRV | 0 | pre-gain on dry only (~×9 at 127); 0 is unity |
| FOLD | 0 | wavefolder; 0 skips; 1…127 only increases fold |
| CLIP | 0 | clip threshold (0 open, 127 brick wall) |
| CRSH | 0 | combined bit-depth and sample-rate crush |
| FDBK | 0 | feedback around fold/clip/crush (needed for TONE/RATE/CHAOS) |
| MIX | 127 | dry/wet; 0 is exact passthrough |
| MODE | HARD | HARD / SOFT / CHAOS (CHAOS flips FDBK polarity) |
| TONE | 64 | feedback shelf: 0 dark, 127 bright |
| RATE | 64 | CHAOS polarity flip rate; ignored in HARD/SOFT |
