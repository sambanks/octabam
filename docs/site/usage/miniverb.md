MINIVERB is a stereo reverb for FX2 that replaces DARK REV. It produces a
smooth, diffuse tail using four input diffusers feeding four feedback branches
with two allpass diffusers each. The input is summed to mono and the reverb
tank generates the stereo field.

## Access

MINIVERB is loaded as a track effect: select a track, press FX2, and choose
MINIVERB where DARK REV used to be. It is not included in the standard
remixes; build the `miniverb` remix or include it in a custom remix.

![FX2 SETUP with Mini Verb selected.](../../img/miniverb/chooser.png)

*FX2 SETUP with Mini Verb selected.*

## Operation

- The default settings produce about 4.6 seconds of decay (RT60, measured on
  the harness from an impulse).
- Raising DAMP darkens the reverb tail.
- MOD and RATE modulate two of the in-loop diffusers; RATE runs from 0.34 to
  2.69 Hz in eight steps.
- MIX 0 is an exact dry passthrough. The room character is fixed, with no
  predelay, freeze, or colour mode.
- When the effect starts, audio passes dry for about 45 ms while the delay
  memory clears.
- Up to four instances fit on each DSP core (eight in total).

## Parameters

| Page | Knob | Range | Default | What it does |
|---|---|---|---|---|
| 1 | DECAY | 0-127 | 104 | decay length |
| 1 | DAMP | 0-127 | 70 | damping; higher is darker |
| 1 | MIX | 0-127 | 40 | dry/wet; 127 is wet only |
| 1 | MOD | 0-127 | 80 | modulation depth |
| 1 | RATE | 8 steps | 2 | modulation speed |
