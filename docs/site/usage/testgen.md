A measurement source: TESTGEN replaces its track's audio with a known test
signal, so you can measure the Octatrack's own path, a USB audio stream, or
another module. It runs with the sequencer stopped and no trigs.

## Access

An effect on a track: select the track, press **FX1**, and pick TESTGEN.
FX1 is the only working slot; an instance on FX2 passes audio through
untouched. Put on FX1, it feeds a known signal into the same track's FX2.
Not in an official remix; build the test remix `testgen`.

LEVL starts at 0, so choosing TESTGEN makes no sound until you turn it up.
Start low: a full-level tone is hard on ears and speakers.

![FX1 SETUP with TESTGEN selected: the SINE mode and CHAN.](../../img/testgen/chooser.png)

*FX1 SETUP with TESTGEN selected: the SINE mode and CHAN.*

## Operation

MODE on page 2 picks the signal:

| MODE | Signal |
|---|---|
| SINE | a sine at FREQ (with FINE), peak 0 dBFS at LEVL 127 |
| SWEP | an exponential sweep, 20 Hz to 20 kHz over LEN, then 1 s of silence, repeating |
| PINK | pink noise, RMS -14.4 dBFS at LEVL 127 |
| WHIT | white noise, one generator per channel |
| IMPL | one full-scale sample every LEN/4 seconds |
| NEDL | a periodic needle pulse train at FREQ and FINE (a line spectrum) |
| DC | a constant, scaled by LEVL |

- FREQ is a select that shows Hz: the 31 ISO third-octave centres from 20 Hz
  to 20 kHz plus A440. FINE tunes -200 to +197 cents in 3.125-cent steps.
- LEN is the sweep length in whole seconds, LEN/8 + 1 (32 gives 5 s, 120
  gives 16 s).
- CHAN: L+R, L only, R only, L with inverted R (a polarity check), or MONO.
  With L+R the two noises are independent; MONO gives the same noise on
  both.
- LEVL steps are 0.5 dB, with 1 at -63 dBFS and 127 at 0 dBFS.
- Changing MODE, FREQ or LEN restarts the signal from its first sample.
- On speakers, start DC at a low LEVL: whether DC reaches the analogue
  outputs is not measured, and an offset pushes a speaker cone off centre.

## Using it

- Level or channel check: SINE at 1 kHz, LEVL 127, then step LEVL to find
  where a path clips.
- Frequency response: record a whole SWEP period and deconvolve it with
  its inverse.
- Noise floor: PINK into a third-octave analyser reads flat for a flat
  path.
- Dropouts and latency: IMPL, then count samples between impulses in a
  capture.
- Measuring another effect: TESTGEN on FX1 with the effect under test on
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

At the main out, LEVL steps within 0.002 dB, and THD at 1 kHz is about
-94 dB at 0 dBFS.
