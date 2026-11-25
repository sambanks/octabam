CHORDS FACTORY gives each MIDI track a bank of 16 chords per bank, one per trig key. You can build chords manually or voice them from one another to minimize voice movement. Chords can be played from the trig keys, sequenced in patterns, and routed through the arpeggiator.

## Access

On a MIDI track, press **SRC** a second time while on the MIDI NOTE page to open the CHORDS page. Chords are saved with the project.

With Harmony installed, Factory's absolute chords belong on **HARM OFF** tracks.
Its CHORDS mode and Harmony's CHORD PLAY remain separate menu choices. Factory
refuses live playing/recording and pattern insertion on HARM-enabled tracks with
**CHORDS NEEDS HARM OFF**; the atelier can still audition a chord. Use Harmony
on other tracks for progressions that transpose by scale degree.

## The atelier

Pressing **SRC** again from the MIDI NOTE page opens the CHORDS page, and pressing it once more closes the page. The screen displays the selected slot's four notes, all 16 slots, and six parameters:

- **A ROOT** and **B TYPE** choose the chord's root note and quality. When placed after a slot that already holds a chord, the new chord is automatically voiced from it using VOIX 1 (the smoothest transition).
- **C INV**, **D SPRD**, and **E OCT** set a generated chord's inversion, spread (CLS, DRP2, DRP3, OPEN, BASS, 10E, WIDE, from narrowest to widest), and octave. These fields appear blank on a voiced or manually edited chord; turning any of them rebuilds the chord from scratch.
- **F VOIX** cycles through alternative voicings relative to the preceding chord, ordered from smoothest onward.

Hold a **trig key** to select its slot and audition the chord. Hold **FUNC** to turn the trig keys into a keyboard starting at the slot's octave (trig 1 = C), where pressing a key adds or removes that note. The trig LEDs light green for notes in the chord; when SCALES or MIDI SCALES is active, they also show the track's scale (tonic in yellow, other scale degrees in red). While holding **FUNC**, knobs A–D shift individual voices by a semitone, E toggles whether the bass stays locked to the root, and F steps through the scale's chords (when SCALES or MIDI SCALES is active).

## Playing the chords

Hold the track key and select **CHORDS** in the trig-mode list (FUNC + DOWN). The trig keys then trigger the chord slots, lighting green when populated and yellow while held. The arpeggiator plays the notes of the triggered chord, and the box on the main screen displays the last chord played, its bass note, and how it was built.

To record chords into a pattern, record live (press REC + PLAY and play the trig keys), or hold trigs in GRID RECORDING and press **UP** to select a chord from the list (use UP and DOWN to audition each slot, then press **YES**). With either scale provider, sequenced chord steps play as written regardless of the KEY setting.

All chords are saved with the project in `chords.work`.
