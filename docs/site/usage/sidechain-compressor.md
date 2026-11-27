This module extends the stock COMPRESSOR with an external side-chain input and
a base-width key filter. Any of tracks 1–8 can drive the detector so that one
track ducks another. Page 2 adds a monitor switch to audition the filtered
key, a key source selector, a key gain control, and a high-pass and low-pass
filter pair that defines the frequency band the detector hears.

The base-width filter isolates the part of the key signal you want the
compressor to react to, such as a kick drum's fundamental with sub-sonic
rumble filtered out. This reduces distortion and keeps compression smooth even
at fast attack and release settings.

## Access

Select a track, press FX2 (or FX1), and pick **COMPRESSOR** from the chooser.
There is no separate effect to load; COMPRESSOR itself becomes the side-chain
compressor, and the new controls appear on its SETUP page (page 2).

The side-chain engine loads into the audio processor whenever a track uses
COMPRESSOR. Immediately after selecting COMPRESSOR, before the side-chain
finishes loading, COMPRESSOR operates as stock, **KEY** displays `--`, and the
screen shows `SC KEY OFF`. In Octabam, the same happens whenever DARK REV on
track 4's FX2 (or another loaded effect) occupies the memory block used by the
side-chain. This module is not included in Octabam Bus.

![FX2 SETUP with COMPRESSOR selected, showing RMS, MON, KEY (here T2), KGN, KBAS and KWID.](../../img/sidechain-compressor/chooser.png)

*FX2 SETUP with COMPRESSOR selected, showing RMS, MON, KEY (here T2), KGN, KBAS and KWID.*

## Operation

- **KEY** selects what drives the detector: `OFF` (the track's own signal, as
  on stock firmware) or `T1`–`T8`. While the side-chain is not loaded (right
  after choosing COMPRESSOR, or while a reverb holds its memory block and
  `SC KEY OFF` is shown), KEY reads `--` and COMPRESSOR works as stock. Your
  KEY setting is preserved and resumes as soon as the side-chain becomes
  available. KEY is drawn as a nine-position switch (`OFF` on the left through
  `T8` on the right) and steps one position per detent even with the encoder
  pressed. Selecting the compressor's own track keys it from its own signal
  routed through the key filter.
- **KBAS** sets the key filter's base frequency (an 18 dB/oct high-pass filter
  from `OFF`, or 20 Hz to 19.6 kHz, displayed in Hz such as `1.2k` for
  1.2 kHz).
- **KWID** sets the filter's width (bracketed with KBAS on screen): a 12 dB/oct
  low-pass filter placed 0.5 to 9.9 octaves above KBAS, or `OFF`. When KBAS is
  `OFF`, KWID counts upward from 20 Hz and acts as a standalone low-pass
  filter.
- KBAS and KWID cannot cross; raising KBAS shifts the entire passband upward.
- As a starting point for ducking from a kick drum, try KBAS around 30–40 Hz
  and KWID around 1.2–1.5.
- **KGN** adjusts key gain from roughly -24 to +24 dB.
- **MON** lets you audition the filtered key signal in place of the track's
  audio (`OFF` on the left, `ON` on the right). Toggling MON or changing KEY
  while MON is active crossfades over about 6 ms to avoid clicks.
- Any track can key any other track across both groups of four. Keying from an
  earlier track in the same group (T1 keying T2–T4, or T5 keying T6–T8)
  reaches the detector with zero latency, so simultaneous trigs on both tracks
  click less at fast attack settings than when keying across groups.
- A COMPRESSOR saved on stock firmware loads with MON `OFF`, KEY `OFF`, KGN
  centred, and both key filters `OFF`. One saved with an earlier version of
  this module loads with MON `OFF`.
- With [mute modes](mute-modes.md), a muted key track continues feeding the
  side-chain detector, matching stock mute behavior.

## Parameters

| Page | Knob | What it does |
|---|---|---|
| 1 | stock COMPRESSOR | as stock |
| 2 | RMS | stock's |
| 2 | MON | hear the processed key |
| 2 | KEY | OFF or T1-T8 |
| 2 | KGN | key gain, about -24 to +24 dB |
| 2 | KBAS | key high-pass, 18 dB/oct: OFF, 20 Hz to 19.6 kHz (Hz) |
| 2 | KWID | key low-pass, 12 dB/oct, this many octaves above KBAS: 0.5 to 9.9, OFF |
