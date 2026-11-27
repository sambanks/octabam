CHARACTER is a channel strip effect that processes audio in the order fold, saturate, tilt, compress, width, and mix, placing distortion before dynamics. At its default settings, the signal passes through unchanged.

## Access

Press FX1 or FX2 on a track; CHARACTER appears in the effect chooser alongside the stock effects.

## Operation

- SAT on page 2 selects the saturation model: TAPE, TUBE, or INFL. DRV controls saturation drive and adds up to +12 dB of input gain at 127 on top of each model's transfer curve.
- FOLD controls the wavefolder, introducing stronger overtones as you turn it up.
- COMP compresses the signal after the distortion stage. On the master track (T8), it automatically uses a slower, soft-knee glue response; on tracks T1–T7, it uses a faster response. There is no knob to switch between them.
- KEY on page 2 selects the compressor's sidechain key. SELF uses the track's own input; when no external key source is present, T1 also behaves as SELF.
- TONE tilts the tonal balance: 64 (center) is flat, higher values brighten the signal, and lower values darken it.
- WDTH adjusts stereo width: 64 leaves stereo unchanged, 0 sums to mono, and 127 doubles the side signal. MIX at 127 is 100% wet.
- With CHARACTER loaded on all eight tracks, DSP load sits at about 29% at default settings and rises up to 83% at maximum settings (compared to about 24% for an empty project). Exceeding 100% stalls the unit until you power-cycle it.

## Parameters

| Page | Knob | Range | Default | What it does |
|---|---|---|---|---|
| 1 | DRV | 0–127 | 0 | Saturation drive; 0 bypasses the stage |
| 1 | FOLD | 0–127 | 0 | Wavefolder amount |
| 1 | WDTH | bipolar | 64 | Mid/side width: 64 unchanged, 0 mono, 127 double sides |
| 1 | COMP | 0–127 | 0 | Compression amount; 0 bypasses the stage |
| 1 | TONE | bipolar | 64 | Tilt EQ: +3.5 dB above and -6 dB below 1.2 kHz at 127, mirrored at 0; 64 is flat |
| 1 | MIX | 0–127 | 127 | Dry/wet blend |
| 2 | SAT | TAPE / TUBE / INFL | — | Saturation model |
| 2 | KEY | SELF / T1–T8 | — | Compressor key: this track's input, or another track's level. T1–T8 come from KEYBUS in remixes that include it (`octabam`, `octabam-verbs`); without KEYBUS, T1 comes from the bus delay host (`octabam-bus`) and T2–T8 behave as SELF |
| 2 | KLVL | 0–127 | 64 | Scales the keyed track's level; 64 is unity |
