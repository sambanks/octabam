# `wavecf` — WAVE (ColdFire)

A 4-voice wavetable voice that runs on the Octatrack MKI's ColdFire, one per track, as a machine of its
own: **WAVE**, a row of the track's machine list. It needs no sample. The voice is a fixed-point reduction of
[CHOMPI WAVE](https://github.com/CHOMPI-Club/CHOMPI)'s: the wavetable oscillator and the attack / release
envelope. The filter, the LFOs and the 33-frame table are not carried over; the Octatrack has its own FILTER effect,
SPECTRUM and its LFOs.

Author: sambanks. **The code was written by Claude (Anthropic)**. Not affiliated with or endorsed by CHOMPI
Club or Chase Bliss; CHOMPI is CHOMPI Club's trademark (their `TRADEMARKS.md`), used here only to say where
the code comes from. The DSP effect with the same voice is [`wave`](../wave/README.md); this one is on the
ColdFire.

Markers as in `CHIP.md`: ✅ measured, 🟡 inferred.

## Limit: two machines in a Part

One limit covers every machine: a Part holds at most **two** machines of any kind (OCTA-303 and WAVE together).
Choosing a third shows `MAX 2 MACHINES` and the track becomes plain FLEX. A Part loaded with more has its first
two signed tracks kept and the rest unsigned by the Part validator. The count is HOOKS's (`MC_LIMIT`,
`mc_sig_table`: every present machine's three signature bytes). ANALOG BD and CX OSC are counted by it, but their
own choose-a-machine code is a submodule's and does not enforce it.

## Using it

1. Double-tap the track key (the machine list), choose **WAVE**, **YES**. FUNC + SRC opens the same list.
2. Sequence it like any track. The CHROMATIC keys play semitones. The AMP page shapes each note: the voices run
   from the first START and the track's AMP envelope in the DSP gates them (OCTA-303 with GATE OFF).

### PLAYBACK page

| slot | name | range | what it does |
|---|---|---|---|
| 0 | TUNE | C1..C5 (raw 40..88) | semitones, shown as note names; raw 64 = C3 |
| 1 | FRAM | 0..127 | position in the table: sine, triangle, saw, square, pulses 1/4, 1/8, 1/16, 1/32; morphs between neighbours |
| 2 | CHRD | 0..31 | one of 32 chord shapes (UNI OCT PWR MAJ MIN SUS2 SUS4 DIM AUG MAJ7 MIN7 DOM7 DIM7 M7B5 MAJ6 MIN6 ADD9 MADD9 ADD11 QRT 5TH OPEN SPRD LYD DOR MIX PNT PNTM 6/9 M9 M6/9 STCK) |
| 3 | VOIC | 1..4 | how many notes of the chord sound |
| 4 | ATK | 0..127 | the engine's attack, 0.5 ms .. 0.47 s |
| 5 | REL | 0..127 | the engine's release, 0.5 ms .. 0.47 s |

A new WAVE track starts at TUNE C3, FRAM 0, CHRD UNI, VOIC 1, ATK 20, REL 60. SETUP is FLEX's own. A level of
0.8 / VOIC is shared between the voices. LFO SETUP names a WAVE track's destinations as FLEX's (PTCH STRT LEN
RATE RTRG RTIM), not the page's names.

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
  give the same samples on two command streams (engine, 35,200 samples; note layer, 38,400); a voice on frame 0
  is a 440 Hz sine at gain × table amplitude; frame 3 is the square; a released voice ends in exact zero;
  `wcf_inc` is within 0.002 cent of 2^(p/12) from C3 over −48..+48 semitones.
- ✅ Instructions under Unicorn (not cycles): `eng_render` 303.8 to 311.8 per sample at the worst block with four
  voices (279.0 mean over the engine stream); `wcf_note` 240 per START; `wcf_knobs` 39 per call.
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
- 🟡 The stock Part validator clamps none of the six PLAYBACK values WAVE stores (the gate's validate scenario
  poked 70 127 31 3 127 127 and they came back unchanged on an unsigned track too).

## Open

- Not flashed. The load with two machines playing, and with a stream open, is not measured.
- CHROMATIC keys on a WAVE track follow OCTA303's law (`raw = 52 + key index`); not exercised under the port.
- No LFO-destination names, no UP / DOWN octave and no SETUP page of its own.

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
