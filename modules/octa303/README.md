# `octa303` — OCTA303

A circuit-modelled Roland TB-303 voice that runs on the Octatrack MKI's ColdFire, one voice per
track. Since v7.0 it is a machine of its own, **OCTA-303**: row 5 of the track's machine list (row 6,
below ANALOG BD, in an image that carries both; CX OSC then follows it: [HOOKS](../hooks/README.md) `machine_rows`), with
its own PLAYBACK and SETUP pages. It needs no sample. It is calibrated against recordings of a real
TB-303 (Din Sync's x0xb0x reference set, 400 notes with known knob positions) and optionally plays
Robin Whittle's Devil Fish modifications through the companion FX module `devilish`.

Author: MaMarko (Marko Brajković, [braikomarko-hub](https://github.com/braikomarko-hub)): the idea, the listening and the tests on the unit.
**The code was written by Claude (Anthropic)**: engine, calibration, integration and gates. Every number below
comes from the measurements and gates named beside it.

**Another TB-303 for the Octatrack:** Zac Kyoti's
[BLACKPYRAMIDS_303](https://github.com/Zac-Kyoti/octatrack-kyoti-fw) (BLKPYRAMD) adapts Robin
Schmidt's Open303 to the **DSP**: one voice per DSP core (one on T1–T4, one on T5–T8), in SPRING
REV's space, voiced by ear. OCTA303 takes the other road: the voice runs on the **ColdFire**, one
per track (the author plays three at once), gives up no stock effect, and its model is fitted to
measurements of a real TB-303 (Din Sync's set, below) rather than tuned by ear. Both register
their machine row with repeat98's ANALOG BD seams, so they cannot share an image.

Markers as in `CHIP.md`: ✅ measured, 🟡 inferred.

## Using it

1. Double-tap the track key (the machine list), choose **OCTA-303** (below PICKUP), **YES**.
   FUNC + SRC opens the same list, but on a FLEX or STATIC track with a sample it opens the sample
   list first: LEFT reaches the machines (the stock behaviour).
2. Sequence it like any track. **Accent** = an ACC parameter lock. **Slide** = a trigless trig or a
   trigless lock (FUNC + TRIG) on the following step; since v7.1 it gets the note it slides from as
   its TUNE lock the moment it is placed (the previous step with a trig or a trigless step: its TUNE
   lock, or the Part's TUNE), so the slide ties into that note as on the TB-303. Turn TUNE with the
   step held to slide somewhere else. A step that already has a TUNE lock keeps it.
3. The CHROMATIC keys play semitones on an OCTA-303 track.
4. **The TB-303's UP and DOWN** (v7.1): in GRID RECORDING, hold one or more trigs and press UP or
   DOWN: each held step's TUNE goes an octave up or down (a step without a TUNE lock starts from
   the Part's TUNE; a note past C1..C5 stays where it is), and the screen shows the note
   (`C4 +OCT`). On every other track TRIG + UP / DOWN is stock (the sample-lock list).
5. LFO SETUP names an OCTA-303 track's PLAYBACK destinations TUNE CUT RES ENV DEC ACC (v7.1; before,
   FLEX's PTCH STRT LEN RATE RTRG RTIM: the modulation was right, the names were not).

The older form still works and is unchanged: a FLEX track whose sample is named `TB303*.wav`
(`TB303`, `TB303SQ`, `TB303D`, `TB303SQD`, any case) plays the same engine with neutral SETUP values.

### PLAYBACK page (the FLEX playback slots)

| slot | name | range | what it does |
|---|---|---|---|
| 0 | TUNE | C1..C5 (raw 40..88) | semitones, shown as note names; C3 = 0 |
| 1 | CUT | 0..127 | cutoff, the 303's CUTOFF FREQ law |
| 2 | RES | 0..127 | resonance (never self-oscillates without Devil Fish SWP) |
| 3 | ENV | 0..127 | ENV MOD (audio taper, as the Roland service notes) |
| 4 | DEC | 0..127 | DECAY, ~0.13..2.4 s (✅ recovered from the Din Sync set) |
| 5 | ACC | 0..127 | the ACCENT knob, applied on the notes that carry an ACC lock |

A new OCTA-303 track starts at TUNE C3, CUT RES ENV DEC 64, ACC 0.

### SETUP page (the FLEX setup slots)

| slot | name | values | default | what it does |
|---|---|---|---|---|
| 6 | WAVE | SAW, SQR, SAW+D, SQR+D | SAW | waveform; `+D` adds a distortion pedal stage after the VCA |
| 7 | GATE | OFF, 303 | OFF | OFF: the AMP page shapes the note. 303: the 303's own gate, 3.5 of the step's 6 clocks (Whittle), tied into a slide |
| 8 | FINE | −64..+63 | 0 | fine tune, ±½ semitone |
| 9 | SLID | 0..127 | 0 | slide time (0 = the 303's RC; `devilish`'s SLID wins when it is on the track) |
| 10 | DRIV | 0..127 | 0 | drive into the output stage's soft ceiling, up to +18 dB |
| 11 | ACCV | 0..127 | 64 | accent loudness (64 = the calibrated 303) |

## How it works

- **Audio.** The FLEX entry of the renderer kind table (`0x400d6438`) points at `sy_render`. On an
  OCTA303 track it lets the stock renderer write the header (PTCH/RATE neutralised, the carrier's
  positions pinned) and then writes the 303's samples into it; every other track is stock. AMP, FX1
  and FX2 stay stock, after the voice.
- **The engine** (per sample, Q-format integer): PolyBLEP saw / square (duty by pitch), coupling
  high-pass, 4-pole diode ladder with the 303's unequal first stage, feedback through a loop
  high-pass, resonance law `k = K(f) × law(RES) − decay(RES) × KD(f)` solved from a linear
  model of the ladder, MEG / accent-sweep capacitor / VCA envelopes at control rate, RC slide,
  output coupling and a soft output ceiling.
- **The machine row** (v7.0) uses the seams that repeat98 measured for `analog-bassdrum`: the same
  fifteen detours and six pokes, without its engine pool. A track is stored as FLEX and signed
  `'T','B',1` in its NEIGHBOR PLAYBACK bytes (`Part + 0x3c + 30·track`, unused by NEIGHBOR). Its
  page record is a clone of the user's FLEX descriptor, built at run time, published as UI type 5
  (`0x400d5f4c`). The Part validator (`0x40002318`) sees FLEX's defaults in a signed track's twelve
  bytes and gets ours back after. Projects stay ordinary projects.
- **Every table** is generated by `tools/octa303/gen_tables.py` from `o3tables.py`; `make check`
  refuses a stale table.

## Measured

### Against a real TB-303 (✅, simulator, bit-exact engine)

Reference: Din Sync's x0xb0x reference recordings — 25 files, 400 notes at C2 with CUTOFF, RES,
ENV MOD, DECAY and ACCENT at known positions (0/25/50/75/100 %).

| measure | v6.5f | v6.7 | v6.9 |
|---|---|---|---|
| timbre, 16 half-octave bands, 80 ms..1.2 s | 6.02 dB | 0.77 dB | — |
| band energy, all windows 4 ms..1.2 s | — | — | 4.68 dB |
| brightness over time (spectral centroid 2 ms..1 s) | — | — | 0.18 oct (v6.8: 0.30) |
| resonance ring decay at RES 127, 1.2..12 kHz | — | — | 2.0..2.5 dB/ms (303: 2.0..2.6) |

For scale: the same 303 recorded twice at the same settings differs by 0.20 dB in the first metric.

tinyloops "drops" (the resonant ring on each saw reset): ring decay 3.4 / 3.1 / 3.1 dB/ms against the
303's 3.4 / 3.0 / 3.1; frequency error 0.062 octaves. Fitted from sound alone, the calibration places
tinyloops' RES at 112/127; the photo of the knobs reads 85–90 %.

Accent (v6.8, Din Sync set A5, peak / energy in the first 4–40 ms, relative to the plain note):

| ACCENT | TB-303 | OCTA303 |
|---|---|---|
| 25 % | +0.6 / +0.1 dB | +0.4 / +0.4 dB |
| 50 % | +4.9 / +5.8 dB | +6.9 / +5.4 dB |
| 75 % | +15.3 / +13.8 dB | +16.3 / +12.8 dB |
| 100 % | +15.6 / +16.3 dB | +20.1 / +16.8 dB |

### The code (✅)

- `tools/octa303/sim/test_octa303.py`: 108/108 with `modules/devilish` (v7.1; 92/92 before, 89/89 without it:
  three checks read dEVILish's manifest, one checks OCTA303's own `DEVIL_ID`). `octa303.s` executed
  from its source text in a ColdFire simulator equals the Python model `ref303.py` sample for sample:
  both carriers, accents, slides, split frames, extreme knobs, Devil Fish on FX1/FX2 (read from the DSP
  voice record: locks, scenes and LFOs applied), the gate state machine (fuzzed), the SETUP page, the machine registration helpers and
  the validator wrapper.
- No overflow: the VCA input is clamped from the tables so the product fits 32 bits (fuzzed
  over thousands of knob combinations).

**Why `tools/octa303/sim/cfsim.py` exists beside `ot_emu`.** The two answer different questions.
`cfsim.py` (415 lines) interprets the *text* of `octa303.s` and calls the voice's entry points
directly with knob words, frame states and fader positions chosen by the test, so the engine can be
compared with `ref303.py` sample for sample over thousands of fuzzed cases in seconds, with no OS
image, no assembler and no project. It also lints the source against ColdFire encoding limits a
68k-minded author gets wrong (`asr.l #15`, `muls.l #imm`, byte/word ALU ops): the v4 source had one
that m68k-elf-as refused. It is a correctness model, not a timing model, and not an assembler.
`ot_emu` runs the built image as a whole machine: it is what shows that the machine row, the pages,
the validator and the audio path work in the firmware (`verify_octa303_ui`, "Under the port" below),
but driving one engine call per case through the sequencer there would take hours for what the
simulator checks in seconds. Not done: `cfsim.py`'s output has not been compared bit for bit with
the same calls under `ot_emu`; the port gate and the unit are what catch a simulator that reads an
instruction differently from the chip.

### v7.1 (23 Oct 2026): the sites, read from the user's 1.40C

- ✅ The LFO PMTR formatter `0x4003bf64` (LFO page descriptor `0x400d37be`, slot 6's formatter)
  takes a PLAYBACK destination's names from `PB_TABLE[the track's machine]`; the detour at
  `0x4003bff0` hands it OCTA303's machine record on a signed track (Zac Kyoti's BLACKPYRAMIDS_303
  hooks the same site for its own row, MT13: the two modules already conflict).
- ✅ The held-trig layer's key table `0x400becda` sends UP and DOWN to `0x400434d8`, which opens
  the sample-lock list for the first held step on a STATIC or FLEX track; the detour at its entry
  takes the keys on an OCTA-303 track. The TUNE lock is written as the stock knob-lock writer
  (`0x40050e60`) writes it: the bank blob and its battery-backed copy (`0x1001614e + …`), then
  `bank + 0x9b332` and `0x100f8598`, `0x40027e00`, `0x4009da20(track)`.
- ✅ The trig keys go through a dispatcher `0x40060b58(key, event)`: a press to `0x40050f20`
  (FUNC + TRIG sets the trigless lock there: under the port, no write in `0x4005fb44` and the bit
  already set at its entry), a release to `0x4005fb44`. The dispatcher's entry keeps the track's
  trigless masks (+8 trigless trigs, +16 trigless locks) at a press; `0x4005fb44`'s tail before
  `jmp 0x40027de4` (`0x40060b3e`) compares them, and a step that became trigless gets its note.
- ✅ `test_octa303`: the three routines from their source text (octave up and down, the edges, the
  toast's note, the battery-backed copy, the stock path on FLEX and MIDI tracks; the slide's note
  from a trig, a slide, the Part, around the end of the pattern, a step already locked, no new step,
  another track).
- ✅ Under the port, `tools/octa303/port_o3keys.py` (the panel, a project, 23 Oct 2026): TRIG 1 + UP 64 → 76 and the toast `C4 +OCT`; FUNC + TRIG 2 a trigless lock with TUNE 76 at once; TRIG 3 + DOWN 64 → 52; a FLEX track's TRIG + UP opens the stock LOCK list and writes no lock; LFO SETUP shows `PB TUNE`.

### Under the port (✅, `ot_emu`, the user's OS 1.40 image, 19 Oct 2026)

- OCTA-303 appears as row 5; choosing it writes the signature, the defaults, the shadow copy and
  the live lane; choosing another machine clears the signature; reopening highlights OCTA-303.
- SETUP shows WAVE GATE FINE SLID DRIV ACCV, the encoders write the right bytes; WAVE and GATE step
  like stock LOOP and SLIC (same handler, same count).
- PLAYBACK shows TUNE CUT RES ENV DEC ACC; the footer reads `OCTA-303▸OCTA-303`.
- The validator called on a Part with a signed track keeps FINE/SLID/DRIV = 100/90/120; on an
  unsigned FLEX track the same bytes clamp to 1/1/3.
- Audio with an **empty** FLEX slot: C3 at 130.8 Hz; GATE 303 ≈ 58 % of a step; SQR has the odd
  harmonics (H2 −22 dB). With a TB303.wav in the slot, WAVE still decides.

### On the unit

- ✅ v6.3–v6.9 played for hours on the author's MKI (two or three OCTA303 tracks, with `devilish` and
  `distorx`, image `acidtrack`).
- ✅ v7.0 on the author's MKI, image `ACIDV70` (BUILD 87, remix `acidtrack`), 19 Oct 2026: OCTA-303 chosen
  from the machine list with the panel keys; the SETUP page edits as designed; the project saved,
  power-cycled and reloaded with the machine and its SETUP values intact; GATE 303 by ear. A 7.5-minute recording (two OCTA-303 tracks, one with `devilish` and
  `distorx`, one with `devilish` and a filter, `distorx` on claps): peak −2.2 dBFS, level steady at
  about −17 dBFS RMS, no dropouts.
- ✅ v7.1 on the author's MKI, image `O3V71` (BUILD A0, remix `octa303`), 23 Oct 2026, by ear and eye: held trig + UP / DOWN moves the note an octave (several held trigs at once; a note at C5 stays, no toast), `C4 +OCT` on the screen; FUNC + TRIG on the next step makes a slide that ties into the previous note, held and turned to another note it slides there, and + UP lifts it an octave; a FLEX track's TRIG + UP opens the sample list as before; LFO SETUP lists TUNE CUT RES ENV DEC ACC; the locks survive save, power-cycle and reload.
- ✅ ACIDV71 (BUILD 88, same OCTA303), 20 Oct 2026: two OCTA-303 tracks with `devilish`, beside five
  `distorx` (one on T1): no clicks, no slow-downs, by ear.
- Not measured: the ColdFire load (CF METER). The author has run three OCTA303 tracks for hours.

## Inferred

- 🟡 **ColdFire cost.** ~3,200 instructions per 16-sample frame per voice (saw), ~3,500 (square),
  ~4,700 with Devil Fish FM + MUFF (simulator instruction counts). At ~1.77 cycles an instruction
  (`waveload`'s hardware calibration) that is ~6 % of the 363 µs frame per voice, ~10 % with Devil
  Fish. Falsified by CF METER on the unit.
- 🟡 The signature bytes (NEIGHBOR's first three PLAYBACK bytes) are read by no stock code while the
  track is FLEX; `analog-bassdrum` relies on the same assumption. Falsified by a signed track
  losing its signature on a stock path (save, load, copy/paste Part, reload).

## Open

- The ColdFire load on the unit (CF METER).
- `SYNTH MACHINE` and `octa303` cannot share an image (the FLEX renderer and the page resolver).
  `analog-bassdrum` can since 28 Oct 2026, through HOOKS (`machine_rows`: OCTA-303 on row 6 of a
  scrolling list, its renderer after ANALOG BD's): both UI gates pass on the one image under the
  port, not flashed. A project saved on an image without ANALOG BD (OCTA-303 on row 5) opens as
  OCTA-303 on row 6 in one with both: the Part stores FLEX and the `T` `B` 1 signature, never the
  row, and `o3_type` gives the row from the signature (🟡 from the code; not run across two images).
- The first 15–40 ms of an accented note are still ~1 dB further from the 303 than the 303 is from
  itself.

## Credits and sources

- **Din Sync**, *TB-303 reference recordings for x0xb0x* —
  http://www.dinsync.info/2010/02/tb-303-reference-recordings-for-x0xb0x.html — the calibration target.
- **tinyloops**, *Programming the Roland TB-303* — https://tinyloops.com/tb303/index.html — the example
  recordings (the resonant "drops", "saw with only accents") used for the ring decay and the accent.
- **Robin Whittle**, *Devil Fish* manual and "TB-303 unique" notes (Real World Interfaces) — the
  gate length (3.5 of 6 clocks), the accent RC values (47k × 0.033 µF; 47k + 100k with 1 µF), the
  slide RC, the square's duty by pitch, every Devil Fish modification in `devilish`. https://www.firstpr.com.au/rwi/dfish/ ; the
  *User Manual for the Devil Fish mods to the TB-303* (2019) is linked there.
- **Tim Stinchcombe**, analysis of the TB-303 diode ladder ("diode2") — the transfer function the
  low-frequency behaviour was checked against. https://www.timstinchcombe.co.uk/index.php?pge=diode2
- **Roland**, TB-303 service notes — DECAY range, ENV MOD taper, slide capacitor.
- **Tim Hastie**, SYNTH MACHINE 2.9 (https://github.com/timhastie/octatrick-modules, MIT) — the FLEX integration
  this module re-does for one voice (renderer entry, START resolution, PTCH/RATE neutral, pinned
  positions, the clean retrig byte, the PLAYBACK page clone) and the semitone tuning system.
- **repeat98** (https://github.com/repeat98), `analog-bassdrum` (this repository) — the measured machine-list seams the OCTA-303
  row uses.
- **Sam Banks**, octabam — the build, the port, the remixer.

## Gates

`tools/octa303/sim/test_octa303.py` and `tools/verify/verify_octa303_ui.py` (the panel under the
port: select and edit, unsign, the validator; needs `OT_PROJECT`), both in the manifest;
`remixes/test/octa303` carries the module alone. `make check REMIX=octa303` with a project
(`OT_PROJECT`) passed on the author's machine, 21 Oct 2026 (`afa20426`, before its rebase onto
`828edcac`): test_octa303 91/91, verify_octa303_ui (select, unsign, validate), verify_set 0 failures.

The manifest declares it in conflict with SYNTH MACHINE, ANALOG BD and BLACKPYRAMIDS_303 (the same
machine row and FLEX seams); `make modules` shows the matrix. The Devil Fish knobs need the companion
FX module [`devilish`](../devilish/README.md); without it every OCTA303 track is the plain 303. Passed in `make check REMIX=acidtrack` on the
author's tree, 20 Oct 2026.
