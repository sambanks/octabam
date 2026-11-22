A stereo reverb for FX2, in place of DARK REV: a smooth, diffuse tail
built from four feedback branches with two allpass diffusers each and
four input diffusers. The input is folded to mono and the tank generates
the stereo.

## Access

An effect on a track: select the track, press FX2, and pick MINIVERB from
the chooser, where DARK REV was. Not in an official remix; build the test
remix `miniverb`.

![FX2 SETUP with Mini Verb selected.](../../img/miniverb/chooser.png)

*FX2 SETUP with Mini Verb selected.*

## Operation

- The default settings give about 4.6 seconds of decay (RT60, measured on
  the harness from an impulse).
- DAMP darkens the tail as it rises.
- MOD and RATE move two of the in-loop diffusers; RATE runs 0.34 to 2.69 Hz
  in eight steps.
- MIX 0 is an exact dry passthrough. The room is fixed: there is no
  predelay, freeze or colour mode.
- After the effect starts the audio passes dry for about 45 ms while the
  delay memory clears.
- Four instances fit per DSP core, eight in all.

## Parameters

| Page | Knob | Range | Default | What it does |
|---|---|---|---|---|
| 1 | DECAY | 0-127 | 104 | decay length |
| 1 | DAMP | 0-127 | 70 | damping; higher is darker |
| 1 | MIX | 0-127 | 40 | dry/wet; 127 is wet only |
| 1 | MOD | 0-127 | 80 | modulation depth |
| 1 | RATE | 8 steps | 2 | modulation speed |
