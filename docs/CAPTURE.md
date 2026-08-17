# Hardware capture session — protocol, predictions, and analysis contract

Written 18 Aug 2026, against **R32 (tag 51)**. The division of labour: Sam's
ear owns character; these captures own the questions where NUMBERS decide, or
where the emulator is structurally blind (single core, its own mpy semantics,
its own truncation). Every prediction below was computed and committed BEFORE
the first capture, so the hardware confirms or falsifies — never "explains".

## Recording rules (once, for the whole session)

- Flash **R32** first (R30/R31 are broken — see PLAN) and power-cycle.
- Main outs → interface, **44.1 kHz / 24-bit**, interface gain FIXED for the
  whole session, no master FX on the OT, track levels at 100 unless a capture
  says otherwise, and note anything you had to change.
- Name files exactly `hw_<ID>.wav` (e.g. `hw_A2.wav`) into one folder.
- Source material: `out/test_audio/click.wav` and `loop.wav` on the card as
  static samples (copied alongside the firmware). Trig the sample once per
  capture unless noted; let tails ring fully.
- Bank shape for all captures unless noted: **T1 = BongDelay, T5 = ChonVerb,
  T2 = the source track (sample player), everything else Send or unused with
  all sends at 0.**

## The captures

### A. Decay vs TIME — THE MPY CHECK (the oldest unverified hardware risk)
ChonVerb BIG (MODE pos 3), T2 plays `click`, T2's `-VRB` full, record T5.
One capture per TIME: **A1 = TIME 0, A2 = TIME 64, A3 = TIME 127.** ~8 s each.

| capture | predicted decay |
|---|---|
| A1 TIME 0 | **17.5 dB/s** |
| A2 TIME 64 | **11.4 dB/s** |
| A3 TIME 127 | **5.6 dB/s** |

Falsifier: if silicon's fractional `mpy` shifts left where the emulator's does
not, every decay constant is ~2× off — rates would land wildly off this table
(or BIG self-oscillates). Anything within ~±20% closes the caveat for good.

### B. Mode trims — the §1.4 numbers
`click`, TIME 64, full send, record T5. **B1 = ROOM, B2 = PLATE, B3 = BIG.**

Predicted (early tail level / decay per second):
ROOM −51.4 dBFS / 23.7 dB · PLATE −52.3 / 30.0 · BIG −52.2 / 11.7.
Output: I return per-mode trim constants as numbers; you ear-ratify.

### C. SHMR + GATE on-unit ticks (the two knobs never explicitly confirmed)
**C1**: any tone-ish sample, TIME 100, capture ~10 s: first half SHMR 0, then
SHMR 100 (turn it mid-capture, note the time). Predicted: octave-vs-fundamental
in the tail grows ~+34 dB (−41.3 → −7.1).
**C2** (ear only, no capture needed): GATE up with drums, all three modes —
tail chops after the hold in each.

### D. Hardware-vs-emulator null — the delay
T2 plays `loop`, T2's `-DEL` full, **BongDelay CLEAN, TIME 40, FDBK 60,
TONE 127, PING knob position 1, IN 0, -VRB 0**, record T1 ~10 s.
Reference: `out/hw/ref_delay_clean_loop.wav` (already rendered, peak 0.939 FS).
I align and subtract; the residual spectrum is everything silicon does that
the emulator doesn't. This is the capture most likely to teach us something
nobody predicted.

### E. The level laws with REAL material (the case the harness cannot make)
Different loops on T2/T3/T4 (uncorrelated — the point), all `-VRB` full,
record T5: **E1 = T2 only, E2 = T2+T3, E3 = T2+T3+T4.**
Predicted: level roughly CONSTANT across E1→E3 (1/√N holds uncorrelated
material flat). The old 1/N law would have shown −3 dB per step — that's what
you heard and reported; this is its formal close-out.

### F. -VRB wash sanity (new knob, first hardware outing)
`loop` on T2, `-DEL` full, delay CLEAN, T5 ChonVerb: **F1 = delay `-VRB` 0
(predict: NO wash, and senders' reverb level unchanged), F2 = `-VRB` 127.**

## What comes back
For each capture I return measured-vs-predicted, a verdict per open item
(mpy caveat, mode trims, null residual, level law), and proposed constants
where a number is the fix. Ear rounds then run on the constants, not on hunches.
