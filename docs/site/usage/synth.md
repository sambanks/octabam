A two-operator FM synth machine for FLEX tracks, with one to four
paraphonic voices and chords. The voice engine runs on the ColdFire CPU
and owns the AMP envelope of a synth track; the DSP shapes and effects the
voice as a sample.

## Access

Any FLEX track whose sample is named `FMSYNTH*.wav` becomes a synth. A
silent 4 s marker file will do, and the marker's length never ends the
note (`SYNTH*.wav` is still accepted). Not in an official remix; several
test remixes carry it. Built from timhastie/octatrick-modules (v2.9).

## Operation

- The PLAYBACK page reads PTCH RATO INDX FINE FDBK DEC (title FM SYNTH):
  PTCH in semitones, FINE in cents.
- On the LFO page, VOIC picks 1 (mono) or 2 to 4 (paraphonic), and CHRD
  picks one of 32 chord shapes in Syntakt order, each with three
  inversions on the knob. CHRD can be locked per step, and snaps onto
  SCALE QUANTIZER's scale and root.
- GLIDE is on the quantizer's row.
- MIDI IN plays a synth track like the CHROMATIC keys: one voice per note
  up to VOIC, and a note-off releases it.
- A chord fingered on the keys or over MIDI during live recording is
  recorded as PTCH, CHRD and VOIC locks. Keys within a rolling 150 ms join
  the chord.
- LEG on every audio track's AMP SETUP page is the legato switch: OFF or
  MONO on a sample track, OFF, MONO or POLY on a synth track. A FLEX or
  STATIC track with LEG MONO slides every pitch change over GLIDE.
- In GRID RECORDING, a held trig + FUNC + DOWN or UP moves its PTCH lock an
  octave.
- ATK, HOLD and REL are read from the AMP page (locks, scenes and LFOs
  included) and applied in the engine, so a voice is never cut: a
  re-press continues the sounding oscillator from its level, and a
  release lasts at least 1 ms.
- A chord's level falls with the square root of VOIC; a 4-note chord is
  about -10 dBFS.
- FINE reads 0c the moment a track becomes a synth track.
- Known limit: a MACHINE change while a REL INF note sounds leaves it
  sounding until the next key.
