A TB-303 voice as a track machine, shown as BLKPYRAMD: on the DSP in 24-bit
fixed point with its filter 4× oversampled at 176.4 kHz, adapted from Robin
Schmidt's Open303 and recalibrated on the TB-303's own circuit against
recordings of a real 303. One voice per DSP core (one on T1–T4, one on
T5–T8), ahead of the track's stock AMP, FX1 and FX2.

## Access

BLKPYRAMD is the sixth row of a track's machine list: double-tap the track,
or [FUNC] + [SRC] > MACHINE.

![SRC SETUP with BLKPYRAMD: WAVE, TUNE, SLID, GATE, VOL.](../../img/blackpyramids-303/setup.png)

## Controls

![BLKPYRAMD source controls: PTCH, CUT, RES, ENV, DEC, ACC.](../../img/blackpyramids-303/source.png)

The brackets above the knobs pair CUT with RES and DEC with ACC, the knobs
that shape the filter sweep together.

| Page | Knob | What it does |
|---|---|---|
| SRC | PTCH | the note, C0–C8 by name; [FUNC] + turn steps by octaves |
| SRC | CUT | filter cutoff: 0–100 the real 303's whole range, evenly; 101–127 one octave beyond (to about 3.2 kHz), where the top of RES is eased |
| SRC | RES | filter resonance, the real 303's range; every step adds as much |
| SRC | ENV | filter envelope amount (env mod), the real 303's range |
| SRC | DEC | filter envelope decay, 50 ms to 2 s |
| SRC | ACC | the accent scale for the steps you accent: 127 = each lock's amount (the real 303's full accent), 0 = no accents; every step adds as much |
| SETUP | WAVE | saw (0) to square (127), a continuous blend at equal loudness |
| SETUP | TUNE | A4 = 400–480 Hz; 64 is 440 Hz |
| SETUP | SLID | slide time, 0–198 ms; the default 73 is the 303's slide |
| SETUP | GATE | note length, (GATE + 1)/128 of a step; the default 74 is the 303's gate |
| SETUP | VOL | 0 off; 1–64 clean; 65–127 driven into a soft clip, rising smoothly to about +7 dB (the default 99: about +5 dB) |

## Playing it

- A trig plays a note with the knobs at that step. P-lock PTCH for a
  melody and ACC for an accent.
- A slide trig glides to its note without a retrigger. Trigless locks and
  trigless trigs right after a note tie it.
- Accents in a row stack into the 303's rising sweep.
- A note tied to the end of a pattern holds on through ties at the start of
  the next pattern.
- At a pattern or Part change the voice carries on, as a stock machine's
  sound does, until the track's own first trig in the new pattern: the last
  step plays and rings over the change. A BLKPYRAMD on another track of the
  same core in the new Part takes the voice at its first trig.
- Live: the track key, the chromatic keys (four octaves of absolute notes,
  [PAGE] the 17th) and MIDI notes play while held. TRIG + YES previews a
  step.
- SLOTS and SLICES have nothing to play here: their LEDs stay dark.

## Notes

- The track is a FLEX track underneath: a stock OS opens the project with
  it as FLEX, and FLEX's own values come back when the track leaves the
  machine.
- Like any machine, BLKPYRAMD keeps its knobs when the track switches to
  another machine and back. On another machine's track, its row in
  [FUNC] + [SRC] shows and edits those kept SETUP values.
- One BLKPYRAMD per DSP core, wherever it would arrive: the machine list,
  TRACK PASTE and an SRC page paste refuse a second one on a core with ONE
  303 PER CORE!, and nothing changes. A project saved with two on a core
  keeps the lower-numbered one; the other goes back to FLEX.
- Copying a BLKPYRAMD's SRC page copies the machine: pasted onto another
  track, it makes that track a BLKPYRAMD with the same knobs. A FLEX or
  STATIC page pasted onto a BLKPYRAMD makes it that machine with the pasted
  values; choosing BLKPYRAMD again brings its knobs back.
- The voice takes SPRING REV's place on the DSP, so SPRING REV is not in a
  remix with it. A Part that still names SPRING REV shows its page and
  passes audio through.
- Beside SCALE QUANTIZER, a BLKPYRAMD track keeps its four chromatic octaves
  and its keyboard picture; every other track's keys follow the quantizer.
  That pairing has not been flashed.
