TESTGEN is a measurement signal generator that replaces its track's audio with
a known test signal, letting you test the Octatrack's audio path, a USB audio
stream, or another module. It runs even when the sequencer is stopped and no
trigs are active.

## Access

Select a track, press **FX1**, and choose TESTGEN. TESTGEN only operates in the
FX1 slot; an instance in FX2 passes audio through untouched. Placing it in FX1
lets you feed a known signal into the same track's FX2 slot. This module is not
included in the official remixes; build the `testgen` remix to use it.

LEVL starts at 0, so selecting TESTGEN produces no sound until you turn it up.
Start at a low level, as a full-scale test tone can be hard on ears and
speakers.

![FX1 SETUP with TESTGEN selected: the SINE mode and CHAN.](../../img/testgen/chooser.png)

*FX1 SETUP with TESTGEN selected: the SINE mode and CHAN.*

## Operation

MODE on page 2 selects the signal:

| MODE | Signal |
|---|---|
| SINE | a sine at FREQ (with FINE), peak 0 dBFS at LEVL 127 |
| SWEP | an exponential sweep, 20 Hz to 20 kHz over LEN, then 1 s of silence, repeating |
| PINK | pink noise, RMS -14.4 dBFS at LEVL 127 |
| WHIT | white noise, one generator per channel |
| IMPL | one full-scale sample every LEN/4 seconds |
| NEDL | a periodic needle pulse train at FREQ and FINE (a line spectrum) |
| DC | a constant, scaled by LEVL |

- FREQ selects a frequency displayed in Hz across the 31 ISO third-octave
  centres from 20 Hz to 20 kHz, plus A440. FINE adjusts tuning from -200 to
  +197 cents in 3.125-cent steps.
- LEN sets the sweep length in whole seconds using LEN/8 + 1 (for example, 32
  gives 5 s and 120 gives 16 s).
- CHAN selects L+R, L only, R only, L with inverted R (for polarity checks), or
  MONO. In L+R mode, the left and right noise generators are independent; in
  MONO, both channels receive the same noise.
- LEVL steps in 0.5 dB increments, from -63 dBFS at 1 to 0 dBFS at 127.
- Changing MODE, FREQ, or LEN restarts the signal from its first sample.
- When using speakers, start DC at a low LEVL: whether DC reaches the analogue
  outputs has not been measured, and a DC offset pushes a speaker cone off
  centre.

## Using it

- Level or channel check: select SINE at 1 kHz with LEVL at 127, then step LEVL
  to find where a path clips.
- Frequency response: record a full SWEP period and deconvolve it with its
  inverse.
- Noise floor: feed PINK into a third-octave analyser, which reads flat for a
  flat path.
- Dropouts and latency: select IMPL and count samples between impulses in a
  capture.
- Measuring another effect: load TESTGEN on FX1 with the effect under test on
  FX2.

## Parameters

| Page | Knob | Range | What it does |
|---|---|---|---|
| 1 | LEVL | 0-127 | output level; 0 is silent (default) |
| 1 | FREQ | 32 steps | SINE and NEDL frequency, default 1 kHz |
| 1 | LEN | 0-127 | sweep length; impulse spacing is a quarter of it |
| 1 | FINE | -64..+63 | SINE and NEDL fine tune |
| 2 | MODE | 7 signals | SINE, SWEP, PINK, WHIT, IMPL, NEDL, DC |
| 2 | CHAN | 5 | L+R, L, R, L/-R, MONO |

At the main outputs, LEVL steps accurately within 0.002 dB, and 1 kHz THD is
about -94 dB at 0 dBFS.
