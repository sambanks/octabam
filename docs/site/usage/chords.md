CHORDS FACTORY gives a MIDI track a bank of sixteen chords per bank, one
per trig key, built by hand or voiced from one another so the voices move
as little as possible. The chords play from the trig keys, from the
sequencer and through the arpeggiator.

## Access

Not in an official remix; build the test remix `chords` (with SCALES) or
`chords-alone`. Needs STORE (the chords are saved with the project) and
PAGES.

## The atelier

On a MIDI track, press **SRC** again on the MIDI NOTE page: the CHORDS page
opens; press it again to close it. The page shows the slot's four notes,
the sixteen slots and six settings:

- **A ROOT**, **B TYPE**: the chord. After a slot that holds a chord, the
  new chord is voiced from it (VOIX 1, the smoothest).
- **C INV**, **D SPRD**, **E OCT**: a built chord's inversion, spread (CLS,
  DRP2, DRP3, OPEN, BASS, 10E, WIDE: each wider than the last) and octave.
  On a voiced or edited chord these cells are empty; turning one builds
  the chord again.
- **F VOIX**: the next voicing from the chord before, best first.

Hold a **trig key** to choose its slot and hear it. Hold **FUNC** and the
trig keys become a keyboard from the slot's octave (trig 1 = C): a key adds
or removes its note. The keys show the chord's notes green and, with
SCALES, the track's scale (tonic yellow, scale red). With FUNC held, A-D
move one voice a semitone, E keeps the bass on the root or frees it, and F
steps through the scale's chords (with SCALES).

## Playing the chords

Hold the track key and choose **CHORDS** in the trig-mode list (FUNC +
DOWN). The trig keys play the slots: green when a slot holds a chord,
yellow while held. The arpeggiator plays the chord's notes. The box on the
main screen shows the last chord, its bass and how it was made.

To put chords in a pattern: record live (REC + PLAY, play the trig keys),
or in GRID RECORDING hold the trigs and press **UP**: choose a chord in the
list (UP / DOWN, each heard) and press **YES**. With SCALES, a chord step
plays as written, whatever the KEY.

The chords are saved with the project (`chords.work`).
