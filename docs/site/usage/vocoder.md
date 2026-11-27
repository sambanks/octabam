VOCODER is a ten-band channel vocoder modeled after the Roland VP-330. The
track's audio (such as a voice) shapes either a built-in carrier or an external
carrier, producing mono output on both channels. Version 0.2 moves the
performance controls to page 1 so scenes, the crossfader, LFOs, and parameter
locks can modulate them.

## Access

Select a track, press FX2, and choose VOCODER. **It runs on FX2 of tracks 2, 4,
6, and 8 only.** On tracks 1, 3, 5, and 7, and in any FX1 slot, it passes audio
through untouched. Each DSP core can run at most two instances (tracks 1–4
share one core and tracks 5–8 share the other), so the slot restriction prevents
core overruns. Placing it on even-numbered tracks also pairs naturally with a
NEIGHBOR machine (for example, T1 drums routed into T2 NEIGHBOR + VOCODER, T3
into T4, and so on). This module is not included in the official remixes; build
the `vocoder` remix, or `vocoder-usb` to record it over USB.

![FX2 SETUP with VOCODER selected: MODE, SCAL, GLDE, RANG and KEY on its page 2.](../../img/vocoder/chooser.png)

*FX2 SETUP with VOCODER selected: MODE, SCAL, GLDE, RANG and KEY on its page 2.*

## Operation

- In MODE INT, the carrier is built in: two sawtooth oscillators an octave
  apart tuned by NOTE. Turn NOTE or parameter-lock it on steps so a sample or
  live input through a THRU machine plays melodies.
- In MODE EXT, the carrier is the track's right channel (for example, a THRU
  track with a voice on input A and a synth on input B), and the modulator is
  the left channel. In INT mode, the modulator is the average of left and
  right. NOTE, BEND, GLDE, WHSP, and the scale parameters control only the
  built-in carrier and do nothing in EXT mode; GEND works in both modes.
- BEND acts as a pitch wheel, which works well with different values locked on
  opposite scenes of the crossfader. Combining an octave bend with a little
  WHSP and GEND on the same crossfader shifts from a male to a female voice
  character.
- When a scale is chosen with SCAL, NOTE plays the nearest scale note at or
  below the knob's pitch so upward sweeps never step downward. The display
  still shows the knob's unquantized note (for example, C#3 in C MAJ plays
  C3). BEND is not quantised, and GLDE glides smoothly between scale notes.
- GEND, WHSP, DRY, and CONS follow knob changes over 8 ms so scene jumps land
  without clicking.
- There is no level knob; use the track's AMP page to set output level.
- Projects saved under version 0.1 need their defaults re-stamped before
  playback (`tools/hw/ot_project.py stamp-defaults <project> vocoder`): 0.1's
  LEVL maps onto WHSP and turns the voice to noise. Projects with VOCODER on T3
  or T7 now play those tracks dry; move those instances to T4 or T8.
- The VP-330's ensemble chorus is not modeled.

## Parameters

| Page | Knob | Range | What it does |
|---|---|---|---|
| 1 | NOTE | C1..C6 | the built-in carrier's pitch; default C3 |
| 1 | BEND | -64..+63 | pitch bend on NOTE, -12 to +12 semitones at RANG 12ST; default 0 |
| 1 | GEND | -64..+63 | formants: x0.84 (a bigger, male voice) at -64 to x1.41 (a female one) at +63; default 0 |
| 1 | WHSP | 0-127 | whisper: the built-in carrier from the sawtooths (0) to white noise (127); default 0 |
| 1 | DRY | 0-127 | the dry voice mixed in; default 0 |
| 1 | CONS | 0-127 | consonants: the voice above 4 kHz passed through; default 48 |
| 2 | MODE | INT, EXT | the carrier |
| 2 | SCAL | CHRO, MAJ, MIN, DOR, PHRY, MIXO, HMIN, PMAJ, PMIN, BLUE | NOTE's scale; CHRO is every semitone; default CHRO |
| 2 | GLDE | OFF, 30, 80, 200, 500 | glide on NOTE and BEND, in ms; default OFF |
| 2 | RANG | 12ST, 6ST, 24ST | BEND's reach in semitones; default 12ST |
| 2 | KEY | C, C#, D .. B | the scale's root; no effect with CHRO; default C |
