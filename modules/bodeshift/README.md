# BodeShift

A Warps-flavoured **Bode frequency shifter**. Not a pitch shifter and not a
ring modulator: every partial moves by the same number of *hertz*, so
harmonic relationships are destroyed rather than preserved. Small shifts give
slow metallic phasing and detune; large ones turn anything into clangorous,
bell-like inharmonic material.

A ring modulator produces **both** sidebands. This cancels one, with a
Hilbert pair of allpass chains — that cancellation is the entire difference
between the two effects, and the entire difficulty.

Per-track insert, no buffer, so it stacks with the other inserts.

## Knobs

| slot | name | what |
|---|---|---|
| p0 | FREQ | shift 0–1000 Hz, squared taper (fine control down low) |
| p1 | FINE | 0–20 Hz added linearly; at ~1 Hz you get the classic slow swirl |
| p2 | FDBK | shifted output back into the input — partials spiral up or down |
| p3 | MIX  | dry/wet; 0 = exact passthrough |
| p7 | MODE | UP / DOWN / WIDE (up on L, down on R) |

## Status

Assembles (391 words), disassembly-audited, rendered locally and measured
against a float model built *first* — which is what caught the sign
convention, since the obvious form produced the wrong sideband while sounding
entirely plausible.

- MIX=0 **bit-exact** passthrough; wanted sideband at **unity** gain.
- **Sideband suppression, measured on the DSP**: 41.5 dB at 440 Hz, 29.6 dB
  at 1 kHz, 18.7 dB at 5 kHz — matching the float model (40.8 / 29.2 / 18.6)
  to within a dB, which is what says the fixed-point implementation is
  faithful rather than merely working.
- **Shift frequency exact**: 0.00 Hz error at FREQ 30 / 60 / 90 / 127, and
  FINE alone measures 20.0 Hz against a 20 Hz design.
- DOWN and WIDE verified by measurement, not assumption: in WIDE the left
  channel carries the upper sideband at −44 dB with the lower at −85, and the
  right channel is the mirror.
- **Feedback is stable at maximum**: 0.95 FS in at FDBK=127 holds a 1.000 FS
  peak for three seconds with no growth. The cap is arithmetic, not taste —
  the loop settles at 0.5/(1−fdbk), so fdbk < 0.5 provably cannot run away.

## Open

- The residual opposite sideband rises with frequency (only ~19 dB down at
  5 kHz). That is the honest cost of an 8-pole Hilbert pair; more sections
  is the fix if it ever matters musically.
- The shifted signal is **mono** (the analytic pair is computed on the mono
  sum). WIDE gets its stereo from the two *directions*, not from two chains.
  True stereo would double the 32 words of allpass state.

**Not yet flashed** — knob publishes and the MODE select ride the standing
on-unit reconfirm.
