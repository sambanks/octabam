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
the sample list first, and [LEFT] reaches the machines. A new WAVE track starts at TUNE C3, FRAM 0, CHRD UNI,
VOIC 1, ATK 20, REL 60.

## Controls

| Page | Knob | What it does |
|---|---|---|
| SRC | TUNE | the note, C1–C5 by name; the CHROMATIC keys play semitones |
| SRC | FRAM | position in the table: sine, triangle, saw, square, pulses 1/4, 1/8, 1/16, 1/32; between two positions it morphs |
| SRC | CHRD | one of 32 chord shapes: UNI OCT PWR MAJ MIN SUS2 SUS4 DIM AUG MAJ7 MIN7 DOM7 DIM7 M7B5 MAJ6 MIN6 ADD9 MADD9 ADD11 QRT 5TH OPEN SPRD LYD DOR MIX PNT PNTM 6/9 M9 M6/9 STCK |
| SRC | VOIC | 1–4: how many notes of the chord sound |
| SRC | ATK | the voice's attack, 0.5 ms to 0.47 s |
| SRC | REL | the voice's release, 0.5 ms to 0.47 s |

The notes start with each trig and keep sounding; the AMP page (ATK, HOLD, REL) shapes how long you hear each
one. SETUP is the stock FLEX page. LFO SETUP names a WAVE track's destinations as a FLEX track's (PTCH STRT LEN
RATE RTRG RTIM), though the knobs they move are the six above.

## Checked

The voice and the chord, pitch and sound under the emulator: TUNE C3 sounds at 130.6 Hz, E3 at 164.7 Hz and a
major chord of three voices at 130.6, 164.7 and 196.0 Hz. Not yet played on a unit, and its load on the
processor is not measured.
