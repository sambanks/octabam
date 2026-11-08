# Hardware plan: `octabam`, `octabam-bus` and `octabam-verbs` after #1067

The run sheet for the next unit session, written to be picked up by a person or a coding agent on the Mac with
the unit attached. It says which images to build, what to run in which order, what each result decides, and
where each result is written. The tools are those of [HARDWARE_TESTING.md](HARDWARE_TESTING.md),
[HARDWARE_SUITE.md](HARDWARE_SUITE.md) and [HARDWARE_MANUAL.md](HARDWARE_MANUAL.md); this page adds only what is
particular to these three remixes.

Status, 7 Nov 2026: nothing below has been run. What has run is in "Done without a unit" at the end.

## What is being tested

[#1067](https://github.com/sambanks/octabam/pull/1067) added to the three remixes:

| remix | added | already new and never on a unit |
|---|---|---|
| `octabam` | CHORDS FACTORY + PAGES, SCREEN, SLOW LFO, BAR LED, REC CS1 SKIP | SIDECHAIN_COMPRESSOR, SHATTER (since `OCTABAMR3`) |
| `octabam-bus` | the same five, SCALES, VARISPEED | the whole composition since the ColdFire modules joined it (CHANGELOG) |
| `octabam-verbs` | the same five, SCALES, VIBRATO, TRANSIENT, RESONATOR | everything: VERBERATION, its rows, VERB PARTS, the guardless loader |

Each ColdFire module has run on a unit in its author's images (its README's "where it has run"), none in these
compositions. The question the session answers first: **do the added ColdFire modules raise the number of program
changes left unapplied** ([FAILURE_MODES.md](FAILURE_MODES.md), "Program changes left unapplied in a loader
soak": STEM REC, SCOPE, MIDI SCALES and RND NAME were taken out of `octabam` on that count, and the count rose with
the number of ColdFire modules). SCREEN and CHORDS FACTORY both hook the MIDI path.

## Images

Build every image from one commit (the merge of #1067, or its branch) and give each its own BUILD number. All
of them can be on the card at once as REMIX SWITCH files, so one flash serves the session: flash one image, put
the others' `.RMX` in `/BRAIN/REMIXES/`, switch from BRAIN > REMIXES.

```bash
.venv/bin/python3 tools/hw/remix_variant.py octabam oct-pre --pr1067          # the controls: each remix without #1067's additions
.venv/bin/python3 tools/hw/remix_variant.py octabam-bus bus-pre --pr1067
.venv/bin/python3 tools/hw/remix_variant.py octabam-verbs vrb-pre --pr1067
```

```bash
make image REMIX=octabam BUILD=101
```

```bash
for rb in octabam-bus:102 octabam-verbs:103 _hw-oct-pre:104 _hw-bus-pre:105 _hw-vrb-pre:106; do make rmx REMIX=${rb%:*} BUILD=${rb#*:} || break; done
```

| BUILD | remix | role |
|---|---|---|
| 101 | `octabam` | candidate (flash it: the card's `.bin`) |
| 102 | `octabam-bus` | candidate (`make rmx`) |
| 103 | `octabam-verbs` | candidate (`make rmx`) |
| 104 | `_hw-oct-pre` | control for 101 |
| 105 | `_hw-bus-pre` | control for 102 |
| 106 | `_hw-vrb-pre` | control for 103 |

The numbers are a suggestion; any unused ones will do (CHANGELOG lists the numbers used). `make image` also writes
the `.RMX`. `_hw-*` remixes are flat files under `remixes/`, gitignored and outside the index: `remix_variant.py --list` and `--clean`.
A control differs from its candidate only by #1067's modules (`--pr1067` takes out the list in
`tools/hw/remix_variant.py`); it is not bit-identical to the pre-#1067 build, because the image carries its name.

Never commit or share an image, `.RMX` or `.syx`.

## Projects

From a fresh project made on the unit (`ot_matrix.py audit` finds nothing; [HARDWARE_TESTING.md](HARDWARE_TESTING.md)):

```bash
.venv/bin/python3 tools/hw/ot_suite.py build out/suite/octabam --remix octabam --src <fresh>
```

```bash
.venv/bin/python3 tools/hw/ot_suite.py build out/suite/octabam-bus --remix octabam-bus --src <fresh>
```

```bash
.venv/bin/python3 tools/hw/ot_suite.py build out/suite/octabam-verbs --remix octabam-verbs --src <fresh>
```

```bash
.venv/bin/python3 tools/hw/ot_verbparts.py <fresh> out/suite/VRBPARTS
```

The projects are the candidate's layouts; a control runs its candidate's projects (the control lacks only modules
the projects do not use, except `octabam-verbs`' FX1 layouts of VIBRATO, TRANSIENT and RESONATOR, which do not
appear in the soak). `plan` lists phases and minutes (`octabam` about 163 min, `octabam-bus` 121, `octabam-verbs`
163, plus loads).

## Order of work

### 1. The soak, candidate against control (about 15 min an image)

`pc-soak` is the 32-transition probe of FAILURE_MODES.md as a suite phase (`ot_suite.py`, `soak()`):
A:B, B:A, A:BASE, BASE:A eight times, the program change 2 s after START, USB audio captured, TRACKS PRE.

| remix | project | A, B |
|---|---|---|
| `octabam` | SFX_01 | 15 MODULATION FX2 def, 12 PLATE REV FX2 def: the 1-2 Nov probe, so the counts compare with FAILURE_MODES.md |
| `octabam-verbs` | SFX_01 | 13 MODULATION FX2 dear, 24 SPECTRUM FX2 dear (no reverb in SFX_01; a station's `def` costs too little to see) |
| `octabam-bus` | SFX_01 | 4 SPECTRUM FX1 dear, 12 CHARACTER FX1 dear (no loader; the RIG layouts differ only by the ColdFire DELAY) |

```bash
.venv/bin/python3 tools/hw/ot_suite.py run verbs103 --dest out/suite/octabam-verbs --phase pc-soak
```

Run candidate and control back to back on the same unit, project and USB state; load the project from a pristine
copy before each. A transition is **unapplied** when the DSP busy after it stays at the previous layout's figure.
Record per image: unapplied of 32 (and which), `bad`, the silence, the ColdFire longest run.

What it decides (the 2 Nov runs give the noise: 3, 4 and 5 of 32 on three images one module apart):

- **Candidate within 2 of its control:** the ColdFire additions stay. Go on to 2.
- **Candidate more than 2 above its control:** run it again (one run per image is the weakest point of the 2 Nov
  data). Still above: bisect with `remix_variant.py`, taking out the MIDI-path pair first
  (`--without SCREEN "CHORDS FACTORY" PAGES`), then SLOW LFO and BAR LED, then REC CS1 SKIP, SCALES, VARISPEED.
  The modules that raise the count leave the remix (a commit that edits `remixes/<name>/remix.py` and says why),
  and the FAILURE_MODES.md entry gets the new rows.
- **Unit stops answering USB, or the DSP count stops:** power-cycle, FAILURE_MODES.md, and stop; that image is out.

### 2. The suite, each candidate

`ot_suite.py run <label> --dest out/suite/<remix>` for all phases ([HARDWARE_SUITE.md](HARDWARE_SUITE.md) "Phases"), with `--keep-going`
for the `fx` phases. What is new in each:

- `octabam-verbs`, `fx02`: VERBERATION in each MODE with and without `dear`, VERB PLATE, ROOM and HALL in each
  other MODE (layouts SFX_02 12 to 31). `fx03` and `fx04`: VIBRATO, TRANSIENT on FX2 and FX1, RESONATOR on FX1.
- `octabam-verbs`, `loader02`: SHATTER (slot 6) to and from VERBERATION and each row (12, 20, 24, 28): a demand
  effect beside a reverb with no guard. Expect no refusal, no toast, `bad 0`.
- `octabam-bus`: `fx01` is the bus rig and the stations on FX1; no loader phases.

Then merge the per-slot costs:

```bash
.venv/bin/python3 tools/remix/costs.py import out/hw/matrix/<label>-fx*/report.json
```

```bash
.venv/bin/python3 tools/remix/costs.py check octabam-verbs
```

`check` reads UNKNOWN today: VERBERATION and its rows, VIBRATO, RESONATOR and SIDECHAIN_COMPRESSOR have no figure.
The figures to look at: VERBERATION's (estimated 8.8 % a slot, from GATE VERB's reading scaled by cycles: under
9.07 % is what lets it sit on all eight FX2 slots), RESONATOR's (none yet), and the worst `octabam-verbs` core with
VIBRATO or TRANSIENT on FX1 and VERBERATION on FX2.

### 3. By hand

[HARDWARE_MANUAL.md](HARDWARE_MANUAL.md) for what all three share, then:

| # | remix | step | expected |
|---|---|---|---|
| V.1 | verbs | VERBERATION on T5 FX2 (core A; the track/core trap), MODE through ROOM, PLAT, HALL, GATE while playing | MODE DEFAULTS lands each view (`modules/verberation/manifest.py` `mode_views`); no click |
| V.2 | verbs | GATE: drums, GATE 26 | the hit, then a cut tail (desk-style release, about 320 ms to -60 dB) |
| V.3 | verbs | page 2: SIZE, LCUT, MOD, RATE, PRE end to end | no click; PRE only below SIZE 127 |
| V.4 | verbs | VERBERATION on all eight FX2 slots, LOAD METER | each core under 95 % (the 8.8 % estimate) |
| V.5 | verbs | VERBERATION on the FX2 of a track whose block holds a loaded effect (T3, T4, T7 or T8) | both run; no toast (no guard) |
| V.6 | verbs | `VRBPARTS`: load, read T2, T3, T4, T5 FX2 against `ot_verbparts.py --expect` | T2 VERB HALL's defaults, T4 VERB ROOM's, T3 and T5 as written |
| V.7 | verbs | `VRBPARTS` playing, cue B01 (bank B's Part, applied at the change) | the same values on B01: the pattern-change path (`0x40009e10`), never run under the port |
| V.8 | verbs | VIBRATO, TRANSIENT on FX1 and FX2; RESONATOR on FX1 | each sounds as its README says; RESONATOR is not on the FX2 chooser |
| V.9 | verbs | FX1 chooser | 17 rows: NONE, SPECTRUM, CHARACTER, MODULATION, VIBRATO, TRANSIENT, RESONATOR, then the stock ten; it scrolls |
| C.1 | all | CHORDS FACTORY: MIDI track, SRC pressed again on MIDI NOTE | the atelier page (PAGES); slots on the trig keys play chords ([README](../../modules/chords/README.md)) |
| C.2 | all | SCALES: ARP SETUP's KEY on a MIDI track (FUNC + AMP, encoder F) | the chooser; CHORDS FACTORY's GAMME follows the scale |
| C.3 | all | SCREEN: `screendump` over USB MIDI (`ident=(0x10, 0x00)`), with MIXER and a popup up | the reply is the screen as shown, windows included ([README](../../modules/screen/README.md)); the frame fix has not run on a unit |
| C.4 | all | SLOW LFO: LFO MULT on an audio and a MIDI track | 1/2X, 1/4X, 1/8X listed; the LFO is that much slower |
| C.5 | all | BAR LED: play | the tempo LED green on the pattern's 1, red on the other beats |
| C.6 | all | REC CS1 SKIP: record eight tracks at once through pattern changes, stop and start | recordings intact; the recorder behaves as stock |
| C.7 | bus | VARISPEED as in `octabam` | as its README |

Record PASS, FAIL or NOT RUN with the image tag, the unit (MKI or MKII) and the project.

## Where results go

- The soak counts: FAILURE_MODES.md, the "loader soak" entry (a row per image).
- Each remix's `README.md` "Where it has run", and its `remix.py` `proof` and `proof_note` when a whole suite
  passes (`Proof.HARDWARE` needs the suite on that composition).
- The costs: `tools/remix/slot_costs.json` through `costs.py import`, and the figure in `modules/verberation/README.md`
  (the 8.8 % estimate replaced by the reading).
- HARDWARE_SUITE.md "Results on a unit": a table per remix, as for `OCTABAMR3`.
- CHANGELOG.md: an entry per flashed image.
- A failure: FAILURE_MODES.md first ([HARDWARE_TESTING.md](HARDWARE_TESTING.md) "When it fails").

## Done without a unit (7 Nov 2026)

- `make bus` for all three candidates; `octabam-verbs` leaves 559 / 588 words in the harvested region.
- `tools/remix/selftest.py`: pass.
- `verify_menu` on `octabam-verbs` (the 17-row FX1 list); `verify_vibrato`, `verify_transient`,
  `verify_resonator` (each on its own test remix).
- `verify_chords`, `verify_scales`, `verify_slow_lfo`, `verify_bar_led` on `octabam-bus` and `octabam-verbs`, and
  `verify_verb_parts`, under the port: results in #1067.
- CI's `make check` on the three: #1067's checks.
- The suite plans: `ot_suite.py plan --remix <r>` for the three (the soak pairs above are its output).
