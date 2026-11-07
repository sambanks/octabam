# `wavecf` — WAVE (ColdFire)

A 4-voice wavetable voice that runs on the Octatrack MKI's ColdFire, one per track, as a machine of its
own: **WAVE**, a row of the track's machine list. It needs no sample. The voice is a fixed-point reduction of
[CHOMPI WAVE](https://github.com/CHOMPI-Club/CHOMPI)'s: the wavetable oscillator and the attack / release
envelope. The filter, the LFOs and the 33-frame table are not carried over; the Octatrack has its own FILTER effect,
SPECTRUM and its LFOs.

Author: sambanks. **The code was written by Claude (Anthropic)**. Not affiliated with or endorsed by CHOMPI
Club or Chase Bliss; CHOMPI is CHOMPI Club's trademark (their `TRADEMARKS.md`), used here only to say where
the code comes from. A DSP effect with the same voice, played by a sine carrier on FX2 (`wave`, on the unit as image 93), was removed
on 7 Nov 2026 in favour of this machine (`git show 755a02ac:modules/wave/README.md`).

Markers as in `CHIP.md`: ✅ measured, 🟡 inferred.

## Limit: two machines in a Part

One limit covers every machine: a Part holds at most **two** machines of any kind (OCTA-303 and WAVE together).
Choosing a third shows `MAX 2 MACHINES` and the track becomes plain FLEX. A Part loaded with more has its first
two signed tracks kept and the rest unsigned by the Part validator. The count is HOOKS's (`MC_LIMIT`,
`mc_sig_table`: every present machine's three signature bytes). ANALOG BD and CX OSC are counted by it, but their
own choose-a-machine code is a submodule's and does not enforce it.

## Using it

1. Double-tap the track key (the machine list), choose **WAVE**, **YES**. FUNC + SRC opens the same list.
2. Sequence it like any track. The CHROMATIC keys play semitones. The track's AMP page (ATK, HOLD, REL) shapes the
   notes, and WAVE applies it itself: the DSP's own AMP envelope restarts from zero at every START, which with any
   attack but 0 drops the level to silence and fades back in on a tone that is still sounding (measured under the port:
   the output fell to 0 within one sample at each START; heard on the unit as a click on every note). So, as
   SYNTH MACHINE does, the DSP is left at ATK 0 / HOLD INF / REL INF, where its restart is invisible, and the engine
   runs the AMP page's values with the DSP's measured laws (Tim Hastie, `modules/cxosc/poly.s`): ATK a linear ramp to
   full in 3.85 ms x 2^(ATK / 8.53) with a floor of 16 frames (5.8 ms); HOLD a timer from the START in 1/128 steps
   (frames a step timed from the sequencer); REL exponential, tau 0.295 ms x 2^(REL / 8.53) floored at 1 ms, 127 =
   INF. A START on a sounding track continues from its level. A finished note stops the engine's voices. A track newly
   chosen as WAVE gets AMP ATK 0, HOLD 40, REL 56: the stock page (HOLD INF, REL INF) holds a note forever
   (measured on the unit, 7 Nov 2026: with REL left at full the tones never stopped).
3. Notes follow SCALE QUANTIZER's scale when one is set: each chord note moves to the nearest degree, ties down
   (a MAJ shape in a minor scale comes out MIN), as SYNTH MACHINE and CX OSC do through the quantizer's pinned
   accessor. Without the quantizer in the image, or with SCALE OFF, notes play as they are.

### PLAYBACK page

| slot | name | range | what it does |
|---|---|---|---|
| 0 | TUNE | C1..C5 (raw 40..88) | semitones, shown as note names; raw 64 = C3 |
| 1 | FRAM | 0..127 | position in the table: sine, triangle, saw, square, pulses 1/4, 1/8, 1/16, 1/32; morphs between neighbours |
| 2 | CHRD | 0..31 | one of 32 chord shapes (UNI OCT PWR MAJ MIN SUS2 SUS4 DIM AUG MAJ7 MIN7 DOM7 DIM7 M7B5 MAJ6 MIN6 ADD9 MADD9 ADD11 QRT 5TH OPEN SPRD LYD DOR MIX PNT PNTM 6/9 M9 M6/9 STCK) |
| 3 | VOIC | 1..4 | how many notes of the chord sound; in POLY, the size of the voice pool |
| 4 | SPRD | 0..127 | voicing spread: 0 close; each 32 steps lifts the next upper note of the chord an octave (the 2nd, then the 3rd, then the 4th); chord mode only |
| 5 | GLID | 0..127 | pitch glide: 0 is about 3 ms (it removes the click of a pitch step), up to a time constant of about 0.23 s |

A new WAVE track starts at TUNE C3, FRAM 0, CHRD MAJ, VOIC 3, SPRD 0, GLID 0 (a chord). The engine's own attack
(1.5 ms) and release (13 ms) are fixed: its voices run from the first START and the AMP page does the shaping. CHRD and VOIC are lockable per step
like any PLAYBACK parameter.

### SETUP page (WAVE's own, from CHOMPI WAVE's controls)

| slot | name | range | CHOMPI control | what it does |
|---|---|---|---|---|
| 6 | VIBR | 0..127 | pitch LFO depth | vibrato, up to +-2 semitones, a triangle LFO |
| 7 | VRAT | 0..127 | pitch LFO rate | 0.14 Hz .. 65 Hz, CHOMPI's rate law |
| 8 | OCT | -1, 0, +1 | octave offset | read at each START |
| 9 | DETN | 0..127 | | detune spread between the voices, centred (four voices: -26, -9, +8, +25 cents at 127; one voice: none), read at each START |
| 10 | COMP | 0..127 | final comp | 0 off; above it a drive into a cubic soft clip with makeup (its saturation half: CHOMPI's compressor half is not ported) |
| 11 | MODE | CHORD, POLY | | CHORD: a trig plays the chord and replaces the last one. POLY: each trig takes the next of the VOIC voices, one note (CHRD ignored); older notes keep sounding until the track's AMP closes them |

Defaults VIBR 0, VRAT 40, OCT 0, DETN 0, COMP 0, MODE CHORD. COMP and the others sit in the bytes where FLEX keeps
LOOP SLIC LEN RATE TSTR TSNS (OCTA-303 does the same with FINE SLID DRIV); the Part validator's clamp is undone for
a signed track. 🟡 COMP is in FLEX's TSTR byte: values 1..3 are stock time-stretch modes and 4 is VARISPEED's on a
track that has one; OCTA-303's DRIV is in the same place and has not been seen to matter.

CHOMPI's global pitch is not carried over as a fine tune (the OCTATRACK's LFO moves TUNE by fractions of a semitone). CHOMPI controls not carried over: the filter (cutoff, resonance, filter LFO), gain and pan (the AMP page's VOL and
BAL), the delay / reverb macro (DELAY and the reverbs), table select (one generated table).

## How it works

- **Audio.** The FLEX entry of the renderer kind table (`0x400d6438`) points at `wc_render`. On a WAVE track it
  lets the stock renderer write the header (PTCH / RATE neutralised, the carrier's positions pinned) and then
  writes the engine's samples into it (`modules/octa303/octa303.s` has the call's contract); every other track
  is stock.
- **The engine** (`engine.c`): 4 voices, 1,024-sample frames, linear interpolation in the frame and between
  two neighbouring frames, an attack / release one-pole per voice. Q27 samples, the EMAC's fractional multiply.
- **The note layer** (`wcf.c`): pitch from a 2^(k/384) table (1/32 semitone) with interpolation, the chord shapes,
  the knob laws. `tables.py` generates `tables.s` (the frames) and `wcf_data.c`.
- **The machine row** is the scaffold of `octa303`, copied (`wavecf.s`; signature `'W','V',1` in the Part,
  `Part + 0x3c + 30·track`). Beside OCTA303 the shared sites go through HOOKS (`machine_rows`, `chrom_pitch`).
- `generate.py` compiles the C into the block of `wavecf.s` between its GENERATED ENGINE markers;
  `--check` refuses a stale one.

## Measured

- ✅ `test_wavecf.py`: the Python model (`ref_wavecf.py`), the host build and the ColdFire build under Unicorn
  give the same samples on three command streams (engine, 35,200 samples; note layer, 38,400; AMP, 51,200); the AMP laws against Tim's measurements (ATK 0: 16 frames; ATK 70: 1.19 s against 1.14 s; HOLD 32: 777 frames = 282 ms); a voice on frame 0
  is a 440 Hz sine at gain × table amplitude; frame 3 is the square; a released voice ends in exact zero;
  `wcf_inc` is within 0.002 cent of 2^(p/12) from C3 over −48..+48 semitones; SETUP and AMP behaviour on the model: OCT, DETN's spread, COMP's harmonics, VIBR's pitch spread, POLY's round-robin, scale snapping.
- ✅ Instructions under Unicorn (not cycles): `eng_render` 316.9 per sample at the worst block of the engine stream and 330.4 with vibrato and COMP on (four
  voices); `wcf_note` 168 per START; `wcf_knobs` 39 per call.
- ✅ Under the port (`tools/verify/verify_wavecf_port.py`, a WAVE track on T1, trigs on steps 1, 5, 9, 13):
  TUNE 64 gives 130.6 Hz (C3 130.8), TUNE 68 164.7 Hz (E3 164.8), CHRD MAJ with VOIC 3 gives 130.6, 164.7 and
  196.0 Hz.
- ✅ Under the port (`tools/verify/verify_wavecf_ui.py`, on an image of remix `wavecf-octa303`): choosing WAVE from the list, the signature and the
  defaults in the Part, its shadow and the live lane, unsigning, the limit with WAVE and OCTA303 counted together
  (a third pick refused, a loaded Part's third track unsigned).
- ✅ `verify_hooks.py`: the row type, names, commits and the SRC SETUP name table through the chain for OCTA303 +
  WAVE CF, ANALOG BD + WAVE CF and all three.

## Inferred

- 🟡 ColdFire cost: 311.8 instructions per sample is 48 % of the stock `waveload` engine's 646.2 worst path
  (69.2 µs of the 362.8 µs frame on the unit, image 92); at that ratio about 33 µs, 9 % of the frame, for four
  voices sounding. Falsified by CF METER on the unit with a WAVE track playing.
- 🟡 The stock Part validator clamps none of the six PLAYBACK values WAVE stores (poked 70 127 31 3 127 127: unchanged
  on an unsigned track too). It does clamp SETUP bytes to FLEX's ranges, which the hook undoes.

## Open

- Not flashed. The load with two machines playing, and with a stream open, is not measured.
- CHROMATIC keys on a WAVE track follow OCTA303's law (`raw = 52 + key index`); not exercised under the port.
- No LFO-destination names and no UP / DOWN octave. A note's own hold is the AMP page's: the engine's voices are not gated
  by it, so a WAVE track keeps the engine running (its cost) after the note has faded.
- Clicks on key presses and on SRC, reported on the unit with the first build (W1): not explained. With W1 the SETUP
  page was FLEX's (TSTR AUTO) and AMP held forever.

## Credits and sources

- **CHOMPI Club**, CHOMPI WAVE (https://github.com/CHOMPI-Club/CHOMPI, `a73d732`, MIT, Copyright (c) 2026 CHOMPI
  Club): the oscillator and envelope this reduces. The notice is `LICENSE-CHOMPI`.
- **MaMarko**, `octa303`: the machine scaffold copied here.
- **repeat98**, `analog-bassdrum`: the machine-list seams that scaffold uses.
- **Tim Hastie**, SYNTH MACHINE 2.9 (https://github.com/timhastie/octatrick-modules, MIT): the FLEX renderer
  integration.

## Gates

`python3 modules/wavecf/test_wavecf.py`; `tools/verify/verify_wavecf_ui.py` and `verify_wavecf_port.py` (an
image of remix `wavecf` or `wavecf-octa303`, `OT_PROJECT` set).
