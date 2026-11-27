EUCLID is a stereo Euclidean modulation effect. An evenly spaced rhythm of 1–64
steps drives one of five destinations: low-pass, band-pass, high-pass, notch,
or amplitude. The rhythm follows the Octatrack transport, track speed, and
swing grid. It continues running across pattern loops, and pressing PLAY resets
its phase.

## Access

Select a track, press FX1 or FX2, and choose EUCLID from the effect list. It is
not included in the official remixes; build the `euclid` test remix to use it.

## Operation

- STEPS sets the cycle length, and PULSE sets how many pulses occur within it
  (capped at STEPS). DEPTH is bipolar: the centre leaves the destination
  static, positive values raise it on a pulse, and negative values lower it.
- TYPE selects LP, BP, HP, AMP, or NOTCH. In AMP mode, the panel renames
  FREQ/RES/DEPTH to LEVEL/--/AMT; switching back to a filter type restores the
  original names.
- OUT selects what each pulse triggers:
  - ENV: retriggers an attack and curved decay (ATK up to one step, DEC up to
    eight steps).
  - GATE: opens the destination for LEN (1/128 to one step), with EDGE
    smoothing both transitions.
  - RAND: chooses and holds a new random level on each pulse, with SLEW
    smoothing the transition up to one step.
  - LOOP: freezes the last random value heard at each step; returning to RAND
    resumes generating new values.
- RATE sets the step rate relative to track speed: 1/32, 1/16, 1/8, 1/4, or
  1/2. At 1/16, one Euclidean step equals one track step.
- ROT shifts the rhythm (along with any captured LOOP values) to the right.
- Setting MIX to 0 gives an exact dry passthrough. Setting PULSE to 0 or
  stopping the sequencer returns the destination to its base cutoff or gain.

## Parameters

| Page | Knob | What it does |
|---|---|---|
| Main | FREQ | Base cutoff (LP/BP/HP/NOTCH) or base gain (AMP) |
| Main | RES | Resonance for the four filters; unused in AMP mode |
| Main | DEPTH | Bipolar pulse depth: positive raises, negative lowers, centre is static |
| Main | DEC / LEN | ENV decay (up to 8 steps) or GATE length |
| Main | STEPS | Rhythm cycle length, 1–64 |
| Main | PULSE | Pulses per cycle, 0–64 (capped at STEPS) |
| Setup | ROT | Shift the rhythm right |
| Setup | RATE | 1/32, 1/16, 1/8, 1/4, or 1/2 of track speed |
| Setup | TYPE | LP, BP, HP, AMP, or NOTCH |
| Setup | ATK / EDGE / SLEW | Depends on OUT mode: ENV attack, GATE edge smoothing, or RAND transition slew |
| Setup | OUT mode | ENV, GATE, RAND, or LOOP |
| Setup | MIX | Dry/wet mix; 0 is an exact dry passthrough |

EVENTS coordinates PLAY and resume notifications with other selected modules.
EUCLID retains its own phase-reset policy.
