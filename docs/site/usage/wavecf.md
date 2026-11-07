A 4-voice wavetable voice, one per track, as a machine of its own: **WAVE**. It needs no sample and gives up
no stock effect. It plays eight tables (sine, triangle, saw, square and four pulses) with a position knob that
morphs between neighbours, and a chord of up to four notes from one note. There is no filter in it: the
Octatrack's own effects and AMP page follow.

## Limit

A Part holds at most two machines of any kind: WAVE and [OCTA-303](octa303.md) together. Choosing a third shows
`MAX 2 MACHINES` and the track becomes plain FLEX, and a project that has more loses the extra machines when it
loads (they become FLEX). Each playing machine takes a share of the processor, and with more the panel stops
answering while the audio keeps playing.

## Access

Double-tap the [TRACK] key to open the machine list, choose **WAVE** (below OCTA-303 when both are in the
image, and the list scrolls to it), [YES]. [FUNC] + [SRC] opens the same list; on a track with a sample it shows
the sample list first, and [LEFT] reaches the machines. A new WAVE track starts at TUNE C3, FRAM 0, CHRD MAJ,
VOIC 3, SPRD 0, GLID 0, and its AMP page at ATK 0, HOLD 40, REL 56 (the stock AMP page holds a note forever).

## Controls

| Page | Knob | What it does |
|---|---|---|
| SRC | TUNE | the note, C1–C5 by name; the CHROMATIC keys play semitones |
| SRC | FRAM | position in the table: sine, triangle, saw, square, pulses 1/4, 1/8, 1/16, 1/32; between two positions it morphs |
| SRC | CHRD | one of 32 chord shapes: UNI OCT PWR MAJ MIN SUS2 SUS4 DIM AUG MAJ7 MIN7 DOM7 DIM7 M7B5 MAJ6 MIN6 ADD9 MADD9 ADD11 QRT 5TH OPEN SPRD LYD DOR MIX PNT PNTM 6/9 M9 M6/9 STCK |
| SRC | VOIC | 1–4: how many notes of the chord sound |
| SRC | SPRD | voicing spread: 0 close; each step of 32 lifts the next upper note of the chord an octave (chord mode) |
| SRC | GLID | pitch glide: 0 about 3 ms, up to about a quarter of a second |

| SETUP | VIBR | vibrato depth, up to ±2 semitones |
| SETUP | VRAT | vibrato rate, 0.14 Hz to 65 Hz |
| SETUP | OCT | −1, 0 or +1 octave |
| SETUP | DETN | detune spread between the chord's voices, centred: a chord thickens, one note is untouched (up to ±26 cents on four voices) |
| SETUP | COMP | 0 off; above it, a drive into a soft clip (saturation) with makeup |
| SETUP | MODE | CHORD: a trig plays the chord and replaces the last. POLY: each trig takes the next of the VOIC voices and plays one note; older notes keep sounding until the AMP page closes them |

If SCALE QUANTIZER has a scale set, every note, chord notes included, moves to the nearest note of the scale (ties
go down, so a major chord in a minor scale comes out minor). The AMP page (ATK, HOLD, REL) shapes how long you hear
each note. LFO SETUP names a WAVE track's destinations as a FLEX track's (PTCH STRT LEN RATE RTRG RTIM), though the
knobs they move are the six above.

## Checked

The voice and the chord, pitch and sound under the emulator: TUNE C3 sounds at 130.6 Hz, E3 at 164.7 Hz and a
major chord of three voices at 130.6, 164.7 and 196.0 Hz. Not yet played on a unit, and its load on the
processor is not measured.
