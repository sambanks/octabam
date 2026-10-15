## What it does

A transient shaper. ATCK boosts or softens each onset; SUST lengthens or
tightens each tail. No threshold: a quiet hit and a loud one are shaped the
same, because the detector reads the shape of the envelope, not its level.

## Where to find it

An effect on a track: select the track, press FX2, and pick TRANSIENT from
the chooser. Five knobs on page 1. In octabam-inserts only.

## How to use it

- ATCK up: more punch on drums and plucks. Down: soften the onset.
- SUST up: more room and ring. Down: dry a loop out.
- TIME sets how long an onset counts as the transient: 5 ms at 0, 50 ms at
  127 (logarithmic).
- OUT trims the output; MIX 0 is an exact passthrough, 127 full wet.

## Knobs

| knob | range | default | what it does |
|---|---|---|---|
| ATCK | -64..+63 | 0 | onset gain: +63 is +12 dB, -64 is -12 dB |
| SUST | -64..+63 | 0 | tail gain: +63 is +12 dB, -64 is -12 dB |
| TIME | 0..127 | 40 | how long an onset counts as the transient (5–50 ms) |
| OUT | -64..+63 | 0 | output trim, -12 to +12 dB |
| MIX | 0..127 | 0 | dry/wet; 0 is an exact passthrough, 127 full wet |

## Screens

![The TRANSIENT page: the four knob boxes](../../img/transient/main.png)

![The routing grid (page 2): source, destination and modulation](../../img/transient/setup.png)
