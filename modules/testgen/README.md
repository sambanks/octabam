# `testgen` -- TESTGEN

A measurement source: TESTGEN replaces its track's audio with a known test signal.

On the unit it is an FX1 effect: a source belongs at the head of a track's chain, and on FX1 it leaves FX2 free for the effect under test. (0.1 was on FX2; a project saved with TESTGEN on FX2 now passes that track's audio through untouched.) Put it on a track's FX1, and that track's output (it runs with the sequencer stopped and no trigs), analogue or a channel of Octabam's USB audio out, carries the signal. Uses: measuring the Octatrack's own path (level, frequency response, distortion, channel mapping), measuring a USB audio stream on a host, and proving other modules' claims by putting a known signal through them. [`DESIGN.md`](DESIGN.md) has the plan for all seven signals; [`testgen_ref.py`](testgen_ref.py) is the float reference and the analysis the gate uses.

Every signal is defined exactly: `testgen_ref.py` reproduces each one as the module computes it, so a capture can be compared against the reference sample by sample, and a sweep can be deconvolved with its own inverse.

## Signals (MODE)

| MODE | signal | at LEVL 127 |
|---|---|---|
| SINE | a sine at FREQ | peak 0 dBFS, RMS -3.01 dBFS |
| SWEP | an exponential sweep, 20 Hz to 20 kHz over LEN, then 1 s of silence, repeating | peak 0 dBFS |
| PINK | pink noise: Kellet's three-pole filter on WHITE, one filter per channel | RMS -14.4 dBFS |
| WHIT | white noise: a 46-bit linear congruential generator (drand48's multiplier), its top 23 bits; one generator per channel, so with CHAN L+R the two sides are independent | peak 0 dBFS, RMS -4.77 dBFS |
| IMPL | a single full-scale sample every LEN/4 seconds | peak 0 dBFS |
| NEDL | a needle pulse train: a single full-scale sample every P samples, P = round(44100 / f) for the frequency f set by FREQ and FINE, so the train is strictly periodic at 44100 / P Hz (1k gives P = 44, 1002.27 Hz; A440 gives 100, 441 Hz; the top steps are coarse: 20k gives 2, 22.05 kHz) | peak 0 dBFS |
| DC | a constant: full scale on every sample, scaled by LEVL (CHAN L-R gives +DC on L and -DC on R) | 0 dBFS |

A change of MODE, FREQ or LEN restarts the signal from its first sample: a sine from phase 0, a sweep from 20 Hz, the noise from its seed, the impulses and the needle train with one at once.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | LEVL | 0-127 | output level: 0 = silent (the default), 1 = -63 dBFS, 127 = 0 dBFS, 0.5 dB a step (115 = -6 dBFS) |
| 1 | 1 | FREQ | select, shown in Hz | SINE and NEEDLE frequency: the 31 ISO third-octave centres, 20 Hz to 20 kHz, and A440, across the knob's whole turn; 1k is the default |
| 1 | 2 | LEN | 0-127 | SWEEP length in whole seconds, LEN/8 + 1 (0 = 1 s, 32 = 5 s, the default, 120 = 16 s); the IMPULSE period is a quarter of it (0.25 s to 4 s) |
| 1 | 3 | FINE | -64..+63 | SINE and NEEDLE fine tune: -200 to +197 cents in 3.125-cent steps, so FREQ and FINE together reach any frequency from 17.8 Hz to 20 kHz; 0 is the FREQ step exactly. Turning it does not restart the tone |
| 2 | 6 | MODE | select, across the knob's whole turn | SINE, SWEP, PINK, WHIT, IMPL, NEDL, DC |
| 2 | 8 | CHAN | select | L+R, L only, R only, L and inverted R (a polarity check), MONO. For the noises, L+R gives independent noise on each side, and MONO the same noise on both |

LEVL starts at 0, so choosing TESTGEN makes no sound until you turn it up: a full-level tone on insert is hard on ears and speakers (reported on the unit with the first image, which defaulted to -6 dBFS). FREQ was a plain 0-127 knob in that image, with the 31 frequencies packed into its first quarter; it is now a select that shows the frequency.

The FREQ steps:

| FREQ | Hz | FREQ | Hz | FREQ | Hz | FREQ | Hz |
|---|---|---|---|---|---|---|---|
| 0 | 20 | 8 | 125 | 16 | 630 | 24 | 4000 |
| 1 | 25 | 9 | 160 | 17 | 800 | 25 | 5000 |
| 2 | 31.5 | 10 | 200 | 18 | 1000 | 26 | 6300 |
| 3 | 40 | 11 | 250 | 19 | 1250 | 27 | 8000 |
| 4 | 50 | 12 | 315 | 20 | 1600 | 28 | 10000 |
| 5 | 63 | 13 | 400 | 21 | 2000 | 29 | 12500 |
| 6 | 80 | 14 | 440 (A) | 22 | 2500 | 30 | 16000 |
| 7 | 100 | 15 | 500 | 23 | 3150 | 31 | 20000 |

## Using it

- **A level or a channel check**: SINE at 1 kHz (FREQ 18, the default), LEVL 127 gives a 0 dBFS peak; step LEVL to find where a path clips, 0.5 dB at a time. CHAN L-R shows whether a path keeps polarity.
- **A frequency response**: record a whole SWEEP period from where you want to measure, then deconvolve it with `testgen_ref.deconvolve(capture, f1=20.0007, T=<LEN/8 + 1>)`: the peak is the path's impulse response, and the harmonic distortion lands before it in time, apart from the linear part. `testgen_ref.sweep_dsp` gives the exact sweep for sample-accurate comparison.
- **A noise floor or a quick response**: PINK into a spectrum analyser, with third-octave bands, reads flat for a flat path.
- **Latency and dropouts**: IMPULSE, then count the samples between the impulses in a capture; a missing or shifted impulse is a dropout.
- **A line spectrum, or an effect's response to transients**: NEEDLE puts equal energy into every harmonic of 44100 / P up to Nyquist, so a capture's spectrum reads the path's magnitude response at those lines.
- **DC coupling, or a bias into the next effect**: DC shows whether a path passes DC, and on FX1 it offsets the signal FX2 receives.
- **On FX1**: TESTGEN there feeds a known signal into the track's FX2, so an FX2 effect, stock or Octabam, can be measured on its own.

⚠️ DC on speakers: whether DC reaches the analogue outputs depends on their coupling, which is not measured yet. If it does, a large offset pushes a speaker's cone off centre and heats its voice coil. Start DC at a low LEVL with monitors connected.

## Open

- How other units measure: the figures above are one MKII through one Scarlett, and do not separate the two.
- Above 19 kHz the response is not resolved by the 1 s sweep and its analysis; a longer sweep, or SINE at 20 kHz, would.
- The USB audio path (Octabam's USB audio out on a host) is not measured yet; TESTGEN is meant for that too.
