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

## Limit: two machines in a Part

A Part holds at most **two** OCTA-303 tracks. Choosing OCTA-303 for a third shows `MAX 2 OCTA-303` and the
track becomes plain FLEX. A Part loaded with more has its first two signed tracks (by track number) kept and
the rest unsigned by the Part validator, so they are FLEX in the Part and on the screen (a file saved
afterwards no longer has those signatures); the render path counts the same way. Measured on one MKII (2 Nov 2026, meter only, fresh start): nothing playing
25.3 % of the ColdFire frame interrupt, 2 machines playing 65.5 %, 4 machines 83.2 %; the model fitted to those
(about 21 points once any machine plays, 9.3 per machine) gives about 102 % for six. Near 98 % the frame
interrupt leaves the panel's task almost no time: the audio keeps playing and the interface stops answering
(`docs/contributing/FAILURE_MODES.md`). A track that starts on a sample named `TB303*` is a second way into the
voice and is not counted.

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
