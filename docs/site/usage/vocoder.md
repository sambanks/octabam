A ten-band channel vocoder after the Roland VP-330: the track's audio (a
voice) shapes a carrier, built in or external. The output is mono on both
channels. Version 0.2 puts the performance controls on page 1, where
scenes, the crossfader, LFOs and parameter locks reach them.

## Access

An effect on a track: select the track, press FX2, and pick VOCODER.
**It runs on FX2 of tracks 2, 4, 6 and 8 only.** On tracks 1, 3, 5 and 7,
and on any FX1 slot, it passes audio through untouched. Two VOCODERs per
DSP core play (tracks 1-4 share one core, 5-8 the other); a third on a core
would overrun it, so the limit is built in. The even tracks pair with a
NEIGHBOR machine: T1 drums into T2 NEIGHBOR + VOCODER, T3 into T4, and so
on. Not in an official remix; build the test remix `vocoder`, or
`vocoder-usb` to record it over USB.

![FX2 SETUP with VOCODER selected: MODE, SCAL, GLDE, RANG and KEY on its page 2.](../../img/vocoder/chooser.png)

*FX2 SETUP with VOCODER selected: MODE, SCAL, GLDE, RANG and KEY on its page 2.*

## Operation

- MODE INT: the carrier is built in, two sawtooths an octave apart at
  NOTE. Turn NOTE, or parameter-lock it on the steps, and the vocoded voice
  plays a melody. Play a voice, sample or live input through a THRU
  machine.
- MODE EXT: the carrier is the track's right channel, for example a THRU
  track with the voice on input A and a synth on input B. The modulator is
  the left channel; in INT it is left and right averaged. NOTE, BEND, GLDE,
  WHSP and the scale shape the built-in carrier, so in EXT they do nothing;
  GEND works in both modes.
- BEND is a pitch wheel: put a scene on each side of the crossfader with
  different BEND values. With BEND an octave up and a little WHSP, GEND on
  the same fader goes from a male to a female voice.
- With a scale chosen (SCAL), NOTE plays the nearest scale note at or below
  the knob's note, so a sweep up never goes down. The display still shows
  the knob's own note (C#3 in C MAJ plays C3). BEND is not quantised, and
  GLDE glides between the scale notes.
- GEND, WHSP, DRY and CONS follow their knobs over 8 ms, so a scene jump
  lands without a click.
- There is no level knob: the track's AMP page sets the level.
- A project saved under 0.1 needs its defaults re-stamped before it plays
  (`tools/hw/ot_project.py stamp-defaults <project> vocoder`): 0.1's LEVL
  lands on WHSP and the voice turns to noise. A project with VOCODER on T3
  or T7 now plays those tracks dry; move it to T4 or T8.
- The VP-330's ensemble chorus is not modelled.

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
