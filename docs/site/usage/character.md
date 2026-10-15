## What it does

A channel strip that replaces stock LO-FI: fold → saturate → tilt →
compress → width → mix, distortion before dynamics. The defaults are an
exact passthrough, so a part that chose LO-FI sounds the same until you
turn it.

## Where to find it

Press FX1 on a track; CHARACTER is in the chooser in place of LO-FI. In
octabam-inserts it is also on FX2; in octabam-bus it is FX1 only.

## How to use it

- SAT on page 2 picks the saturation character: TAPE, TUBE or INFL. DRV
  drives it (and adds up to +12 dB of input drive at 127, on top of each
  mode's own law).
- FOLD is a wavefolder: more overtones the further it is turned.
- COMP compresses after the distortion. On the master (T8) it is GLUE by
  position — slow and soft-kneed; on every other track it is fast. No knob
  picks between them.
- KEY on page 2 picks the compressor's key. SELF is the track's own input.
  T1 keys on the bus delay host (track 1's input peak, scaled by KLVL) —
  the bus's delay level ducks the track. In octabam-inserts (no bus) T1
  reads as SELF.
- TONE tilts the spectrum: centre (64) is flat, + is bright, − is dark.
- WDTH: 64 untouched, 0 mono, 127 double sides. MIX 127 is full wet.

## Knobs

| page | knob | range | default | what it does |
|---|---|---|---|---|
| 1 | DRV | 0–127 | 0 | saturation drive; 0 skips the stage |
| 1 | FOLD | 0–127 | 0 | wavefolder amount |
| 1 | WDTH | bipolar | 64 | mid/side width: 64 untouched, 0 mono, 127 double sides |
| 1 | COMP | 0–127 | 0 | compression amount; 0 skips the stage |
| 1 | TONE | bipolar | 64 | tilt: +3.5 dB above / -6 dB below 1.2 kHz at 127, mirrored at 0; 64 is flat |
| 1 | MIX | 0–127 | 127 | dry/wet |
| 2 | SAT | TAPE / TUBE / INFL | | the saturation law |
| 2 | KEY | SELF / T1 | | compressor key: the track's own input, or the bus delay host (track 1) |
| 2 | KLVL | 0–127 | 64 | scales the T1 key level; 64 is unity |

## Screens

![The CHARACTER page: the four knob boxes](../../img/character/main.png)

![The routing grid (page 2): source, destination and modulation](../../img/character/setup.png)
