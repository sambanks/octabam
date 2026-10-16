A Euclidean fill for sample trigs. Hold a TRACK key and press PAGE, and a
window opens (title and target tracks, STEPS, PULSE, ROT, RAND VEL, RAND
PTCH, and a live pattern bar). YES writes the rhythm onto the held tracks'
sample-trig mask, with optional AMP VOL and in-scale PLAYBACK PTCH locks.
CUE places a random k-subset with density PULSE.

This edits sequencer trigs; it is not the DSP EUCLID effect, which
modulates filter or amplitude. It leaves PROJECT > CONTROL > SEQUENCER
alone, so it coexists with SCALE QUANTIZER.

## Access

Hold a TRACK key and press PAGE. Targets are the track keys held when the
window opened; with none held, the current audio track. TRACK + PAGE again
closes it, as does NO. FUNC + PAGE (SCALE SETUP) and PAGE alone stay stock.
Not in an official remix; build the test remix `euclid-fill`.
Hardware: author on CF, 16 Oct 2026 (YES/CUE with RAND PTCH>0 on sample /
FM / SY, SCALE on/off); also cursory testing on Sam's MKII (owner report,
16 Oct 2026).

## Operation

- STEPS is the pattern length (with PER TRACK, the first target track's
  length). It is shown, not edited.
- PULSE defaults to 5; ROT, RAND VEL and RAND PTCH default to 0; they are
  not saved.
- RAND VEL (0..100%) writes AMP VOL locks relative to the track's Part
  AMP VOL (never louder than the Part). At 0% no VOL lock is written.
- RAND PTCH (0..100%) is the range of random in-scale PTCH on every hit,
  centered on Part PLAYBACK PTCH. 100% is ±24 semitones on FM/SY, ±12 on
  sample tracks. With SCALE OFF or no quantizer, no PTCH locks.
- CUE keeps PULSE as density and randomizes which steps are on. Editing
  PULSE leaves free mode and returns to Euclidean.
- YES writes the current bar and locks on the targets, NO closes.

## Controls

| Control | Does |
|---|---|
| TRACK + PAGE | open / close |
| UP / DOWN | move the cursor (invert bar on the focused row) |
| LEFT / RIGHT | step the focused value by 1 |
| A | PULSE |
| B | ROT |
| C | RAND VEL |
| D | RAND PTCH |
| LEVEL | turn the focused value |
| CUE | random placement of exactly PULSE hits |
| YES | write the trigs and locks on the targets |
| NO | close |

![Euclidean fill window](../../img/euclid-fill/fill.png)
