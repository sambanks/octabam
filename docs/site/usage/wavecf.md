**WAVE** is a 4-voice wavetable synthesizer machine, available per track, that
needs no sample and replaces no stock effect. It plays eight waveforms (sine,
triangle, saw, square, and four pulse widths) with a position knob that morphs
smoothly between adjacent tables, and can play chords of up to four notes from
one trigger. It has no built-in filter, instead feeding directly into the
Octatrack's AMP page and track effects.

## Limit

A Part supports at most two synth machines in total across WAVE and
[OCTA-303](octa303.md). Selecting a third shows `MAX 2 MACHINES` and reverts
the track to a plain FLEX machine; loading a project with more than two
converts the extra tracks to FLEX. Each playing machine takes a significant
share of processor time, and running more than two causes the front panel to
stop responding even while audio continues to play.

## Access

Double-tap a [TRACK] key to open the machine list, select **WAVE** (listed
below OCTA-303 when both are installed; scroll down to reach it), and press
[YES]. [FUNC] + [SRC] opens the same menu; on a track with an assigned sample,
it shows the sample list first and you can press [LEFT] to reach the machine
list. A new WAVE track starts with TUNE C3, FRAM 0, CHRD MAJ, VOIC 3, SPRD 0,
and GLID 0, and its AMP page initialized to ATK 0, HOLD 40, and REL 56 (unlike
stock tracks, whose default AMP settings hold indefinitely). Pressing [STOP]
ends every WAVE note immediately regardless of the AMP settings.

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

If SCALE QUANTIZER has an active scale, every note (including chord notes)
quantizes to the nearest scale tone; ties round down, so a major chord in a
minor scale becomes minor. The AMP page (ATK, HOLD, REL) shapes how long each
note sounds. On the LFO SETUP page, WAVE destinations still display the stock
FLEX labels (PTCH, STRT, LEN, RATE, RTRG, RTIM), though they modulate the six
SRC knobs listed above.

## Checked
