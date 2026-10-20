# `void` — VOID

Replaces **COMB FILTER** (FX2 id `0x13`). Code sits in harvested **PLATE REV**
words. A Part saved under stock COMB knobs will not match VOID's layout —
re-pick VOID or stamp defaults after flashing.

Grit: track input blended with white / pink / brown noise,
amplitude-modulated by an audio-rate LFO, then a mild HP/LP body and a soft
clip. **FDBK** recirculates the post-clip sample into the drive (one-sample
loop). Always wet — there is no dry/wet MIX.

r7 `$40..$4f` stays reserved for a longer FEED delay later.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | BAL | 0–127 | input↔noise; **0 = full input (default)**, 127 = full noise |
| 1 | 1 | RATE | 0–127 | LFO rate, expo 2 Hz … 200 Hz |
| 1 | 2 | SHPE | SIN / SQR / SAW | LFO shape |
| 1 | 3 | DPTH | 0–127 | AM depth; 0 = source alone |
| 1 | 4 | DRV | 0–127 | soft-clip after AM+body+FDBK; 0 = bypass |
| 1 | 5 | FDBK | 0–127 | one-sample feedback into DRV; 0 = off |
| 2 | 6 | COLR | 0–127 | body low-pass; 127 = open — **turn down to darken** |
| 2 | 7 | HPF | 0–127 | high-pass before COLR; **0 = bypass, turn up to thin** |
| 2 | 8 | NTYP | WHT / PINK / BRWN | noise colour (as BAL rises) |

Noise peaks around −6 dB at BAL=127. High FDBK + DRV screams (AC feedback —
a raw one-sample loop was railing to DC / silence past ~FDBK 50 with drive).

SETUP top row: COLR · HPF · NTYP.

## Measured

- `verify_void.py`: passthrough; AM / FDBK vs `void_ref.py`; NTYP pink/brown
  diverge from white; COLR closed vs open; FDBK+DRV not DC-silent; max-knob
  ~3 s bounded; two FX2 instances.
- Hardware (MKII, BRAIN **VOID V7**, 20 Oct 2026): BAL default full input,
  SETUP COLR/HPF/NTYP, FDBK+DRV AC feedback.

## Sources

- Carrier: WarpFold-style parabola (LOFI2 RING family).
- Pink: Paul Kellet economy; brown: one-pole leaky integrator.
