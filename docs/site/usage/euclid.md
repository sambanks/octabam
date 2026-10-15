## What it does

A stereo Euclidean modulation effect. A rhythm of 1–64 steps (evenly spaced
in the cycle) drives one of five destinations: low-pass, band-pass,
high-pass, notch, or amplitude. The rhythm follows the Octatrack transport,
track speed and swing grid, keeps rolling across pattern loops, and PLAY
resets its phase.

## Where to find it

An effect on a track: select the track, press FX1 or FX2, and pick EUCLID
from the chooser. In octabam-inserts only.

## How to use it

- STEPS is the cycle length, PULSE how many pulses land in it (limited to
  STEPS). DEPTH is bipolar: centre leaves the destination static, positive
  values raise it on a pulse, negative lower it.
- TYPE picks LP, BP, HP, AMP or NOTCH. In AMP the panel renames
  FREQ/RES/DEPTH to LEVEL/--/AMT; the filter types restore the original
  names.
- OUT selects what a pulse does:
  - ENV: retriggers an attack and curved decay (ATK up to one step, DEC up
    to eight).
  - GATE: opens the destination for LEN (1/128 to one step), with EDGE
    smoothing both transitions.
  - RAND: each pulse chooses and holds a new level; SLEW controls the
    transition, up to one step.
  - LOOP: freezes the last random value heard at every position; returning
    to RAND resumes generation.
- RATE is relative to track speed: 1/32, 1/16, 1/8, 1/4 or 1/2. 1/16 is one
  track step.
- ROT shifts the rhythm (and any captured values) right.
- MIX 0 is an exact dry passthrough. Zero pulses and STOP return to the base
  cutoff or gain.

## Knobs

| page | knob | what it does |
|---|---|---|
| Main | FREQ | base cutoff (LP/BP/HP/NOTCH); base gain (AMP) |
| Main | RES | resonance for the four filters; inert for AMP |
| Main | DEPTH | bipolar pulse depth: + up, - down, centre static |
| Main | DEC / LEN | ENV decay (up to 8 steps) / GATE length |
| Main | STEPS | rhythm cycle length, 1–64 |
| Main | PULSE | pulses per cycle, 0–64 (limited to STEPS) |
| Setup | ROT | shift the rhythm right |
| Setup | RATE | 1/32, 1/16, 1/8, 1/4, 1/2 of track speed |
| Setup | TYPE | LP, BP, HP, AMP, NOTCH |
| Setup | ATK / EDGE / SLEW | per OUT mode: ENV attack, GATE edge smoothing, RAND transition |
| Setup | OUT mode | ENV, GATE, RAND, LOOP |
| Setup | MIX | dry/wet; 0 is an exact dry passthrough |

## Screens

![The EUCLID page: the four knob boxes](../../img/euclid/main.png)

![The routing grid (page 2): source, destination and modulation](../../img/euclid/setup.png)
