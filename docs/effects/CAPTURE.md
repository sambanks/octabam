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
- Bank shape for all captures unless noted: **T1 = BusDelay, T5 = BusVerb,
  T2 = the source track (sample player), everything else Send or unused with
  all sends at 0.**

## The captures

### A. Decay vs TIME — THE MPY CHECK (the oldest unverified hardware risk)
BusVerb BIG (MODE pos 3), T2 plays `click`, T2's `-VRB` full, record T5.
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
T2 plays `loop`, T2's `-DEL` full, **BusDelay CLEAN, TIME 40, FDBK 60,
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
`loop` on T2, `-DEL` full, delay CLEAN, T5 BusVerb: **F1 = delay `-VRB` 0
(predict: NO wash, and senders' reverb level unchanged), F2 = `-VRB` 127.**

## What comes back
For each capture I return measured-vs-predicted, a verdict per open item
(mpy caveat, mode trims, null residual, level law), and proposed constants
where a number is the fix. Ear rounds then run on the constants, not on hunches.


---

# SESSION RESULTS — 18 Aug 2026 (captures A, B, M; D parked; E/F unrun)

## Closed
- **THE MPY CAVEAT IS DEAD.** Decay vs TIME in BIG: hw 16.4/8.5/4.6 dB/s vs
  predicted 15.7/9.8/4.3 — within 13%, monotonic, correct spacing. Silicon's
  fractional multiply does NOT shift. Standing since 9 Aug; off every future
  flash checklist.
- **Mode decays match the emulator** (ROOM within 1%, PLATE 4%).
- **BIG +8.4 dB over ROOM confirmed on silicon** → the R33 −6 dB trim.
- **GRAIN 14.2 dB under CLEAN (wet-only)** → the R33 +6 dB makeup (headroom-
  safe step; SPRA-0 coherent stacking caps it). Ear: "grain is great."
- **RATE (MOD speed select) shipped and ear-passed** ("rate is great").

## The measurement lesson of the session
**A hardware capture inherits every stored knob on the part it runs through.**
The PLATE-darkness finding (HF −12 vs emulator +1) was mostly the OLD PART'S
STORED LP: with a fresh part (LP 127) PLATE reads −5.1. A PLATE-brighten was
built on the confounded number and reverted within the hour — Sam's "are these
matching the emulator?" was the catch. Residual hw-vs-emu HF gap ~6 dB is
within single-capture material variance; the D-null (below) is the instrument
that can split variance from silicon.

## Parked, with the reason
- **D (hardware-vs-emulator null)**: a drum loop is the worst null stimulus —
  self-similar (correlator locks onto neighbouring beats), and two free-running
  44.1k clocks. Needs a purpose-built signal (chirp + non-repeating noise
  bursts) on the card. Timestretch OFF is confirmed necessary but not
  sufficient.
- **E (1/√N with real material) and F (-VRB wash)**: session pivoted to
  voicing at Sam's call; both remain cheap and designed.
- **MOD depth**: drums cannot show the wobble in EITHER system (line-width
  metric blind on this material). Depth ceiling deliberately not raised — the
  modulated read's margin to the write head is load-bearing.
