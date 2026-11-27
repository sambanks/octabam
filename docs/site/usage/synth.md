This module adds a two-operator FM synthesizer machine for FLEX tracks with
one to four paraphonic voices and chord playback. The voice engine runs on the
ColdFire CPU and controls the track's AMP envelope, while the DSP shapes and
processes the output as a normal sample.

## Access

Any FLEX track using a sample named `FMSYNTH*.wav` becomes a synth track (the
older `SYNTH*.wav` prefix is still accepted). A silent 4 s marker file is
sufficient, and the marker's length never cuts off notes. This module is not
included in the official remixes, though several standalone remixes include it.
It is built from timhastie/octatrick-modules (v2.9).

## Operation

- The PLAYBACK page shows PTCH, RATO, INDX, FINE, FDBK, and DEC under the title
  FM SYNTH. PTCH adjusts pitch in semitones and FINE adjusts it in cents.
- On the LFO page, VOIC selects 1 (mono) or 2 to 4 (paraphonic) voices, and
  CHRD selects one of 32 chord shapes in Syntakt order, each with three
  inversions across the knob range. CHRD can be parameter-locked per step and
  snaps to SCALE QUANTIZER's scale and root.
- GLIDE sits on the quantizer's row.
- MIDI IN plays a synth track the same way as the CHROMATIC keys: each incoming
  note takes one voice up to VOIC, and note-off releases it.
- Playing a chord on the keys or over MIDI during live recording records PTCH,
  CHRD, and VOIC parameter locks. Notes pressed within a rolling 150 ms window
  are grouped into the same chord.
- LEG on every audio track's AMP SETUP page switches legato mode: OFF or MONO
  on a sample track, and OFF, MONO, or POLY on a synth track. A FLEX or STATIC
  track with LEG set to MONO slides every pitch change using GLIDE.
- In GRID RECORDING, holding a trig and pressing FUNC + DOWN or FUNC + UP
  shifts its PTCH lock by an octave.
- ATK, HOLD, and REL are read from the AMP page (including parameter locks,
  scenes, and LFOs) and applied inside the synth engine so voices are never cut
  off abruptly. Retriggering continues the sounding oscillator from its current
  level, and every release lasts at least 1 ms.
- Chord output level scales down by the square root of VOIC; a 4-note chord
  peaks around -10 dBFS.
- FINE resets to 0c as soon as a track becomes a synth track.
- Known limitation: changing the track MACHINE while a note with REL set to INF
  is sounding leaves that note playing until the next key press.
