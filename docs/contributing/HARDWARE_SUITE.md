# Hardware suite for the `octabam` remix

`tools/hw/ot_suite.py` builds the projects and runs the phases below over the one-cable rig
([HARDWARE_TESTING.md](HARDWARE_TESTING.md)). Everything the cable cannot reach is in
[HARDWARE_MANUAL.md](HARDWARE_MANUAL.md).

The audio is `ot_stimuli.py`'s synthetic material (hits, pink noise, two tones, sweep, level ladder, impulses)
on FLEX slots of all eight tracks. The only input from Elektron is the user's own fresh project. Projects stay
under `out/suite/`.

## Image

`make image REMIX=octabam BUILD=<tag>`. LOAD METER is in the remix, so every phase has audio and load figures.
The effect list comes from the remix's manifests when `build` runs, and the loader transitions from its
`window_demand` (MODULATION, SPECTRUM, CHARACTER in 0.1). Rebuild
the projects after the remix changes.

## Use

```bash
python3 tools/hw/ot_suite.py plan                          # phases, projects, minutes
python3 tools/hw/ot_suite.py build                         # out/suite/{SFX_01..,SSCN,SDJ,suite.json}
python3 tools/hw/ot_suite.py run <label> [--phase fx01,mix-soak] [--keep-going]
python3 tools/hw/ot_suite.py report <label>
```

`plan --lean` and `build --lean` select the pre-flight checks and the effect layouts only (`pre-*`, `fx*`: no `SSCN`, `SDJ`, loader, KITS, scenes, DIRECT_JUMP or soak phases); `run` follows the `suite.json` the build wrote. `--remix octabam-bus --lean` is 37 layouts + BASE in 2 projects, 5 phases, about 25 min. Run it with `.venv/bin/python` (numpy).

`--src` is a fresh project (`ot_matrix.py audit` finds nothing); default `~/octa/projects/EMPTY`.
`run` prints the load steps when the project changes and waits for Enter; `--yes` skips the waits.
Output: `out/hw/suite/<label>/<phase>.log`, `summary.json`; the tools write their own reports under
`out/hw/matrix/` and `out/hw/fuzz/`. A phase passes when its tool exits 0. A failing phase stops the run
unless `--keep-going`. Power-cycle after a failure and read [FAILURE_MODES.md](FAILURE_MODES.md).

Load each project from a pristine copy ([HARDWARE_TESTING.md](HARDWARE_TESTING.md) step 3); CCs and the unit's
write-back change the Part and the card copy.

## Projects

| project | made by | holds |
|---|---|---|
| `SFX_01..NN` | `ot_matrix.py proj --clean --stimuli hits,pink,two_tones,sweep,ladder,impulses` | BASE + up to 31 layouts each: every effect on all 8 tracks in FX1 and FX2, each MODE with and without `dear`; 74 layouts + BASE in 3 projects on (`octabam` 0.1) |
| `SSCN` | SFX_01 + `ot_scenes.py stamp --banks 1-2 --all-scenes --trigs grid4` | MIDI track 1 on channel 11, CC 1 locked in all 16 scenes, MIDI trigs on steps 4, 8, 12, 16, clock and transport receive on |
| `SDJ` | SFX_01 + `ot_scenes.py stamp --banks 1-2 --pattern-steps 2=1,2,4,7,8,11,13` | pattern 2 notes on steps 1, 2, 4, 7, 8, 11, 13 |

## Phases

| id | project | min | tool | what it measures | fails when |
|---|---|---|---|---|---|
| `pre-meter` | SFX_01 | 1 | `load_meter.py --for 10` | LOAD METER answers, frame count advances | request STALLs, count stopped |
| `pre-transport` | SFX_01 | 1 | `usb_transport_probe.py` | START / STOP / host clock over USB | no transport reaction |
| `pre-usb` | SFX_01 | 1 | `usb_counters.py` | USB audio ring counters | request fails |
| `dsp-watch` | SFX_01 | 6 | `ot_dspwatch.py --audio --continuous-clock --programs 0,1` | the DSP record count (`dsp.seq`, polled at 20 Hz) through 20 cycles of STOP, program change, START with a continuous MIDI clock and the unit's USB audio captured; the recipe that stopped the DSP with CX OSC in the image ([FAILURE_MODES.md](FAILURE_MODES.md)) | the count stops advancing, or a LOAD METER read times out |
| `fxNN` | SFX_NN | 11 each | `ot_matrix.py run` | per layout: CRASH, FREEZE, CLICKS, ROUGH, STATIC, LEVEL, CLIP, DC/RINGS, DROPS, OVERLOAD, LOAD; DSP busy per core, per-slot cost | any flag |
| `loaderNN` | SFX_NN | 2-7 | `ot_matrix.py switch --pairs` | program-change transitions: loaded effect to BASE, to a stock reverb, to another loaded effect (both FX1 and FX2 hosts); gaps, ColdFire longest run, bad records | any flag |
| `pc-soak` | SFX_01 | 11 | `ot_matrix.py switch --pairs` | the loader soak of [FAILURE_MODES.md](FAILURE_MODES.md): A:B, B:A, A:BASE, BASE:A eight times (`ot_suite.py soak()`; in `octabam` MODULATION and PLATE REV) | count transitions whose DSP busy stays at the previous layout's (the tool's exit code does not) |
| `kits-identity` | SFX_01 | 10 | `ot_fuzz.py` profile `pc` | 10 min of program changes (single, burst, back) across 32 patterns; each plays its Kit (firmware-migrated from the stock Parts at the first load) | MIDI destination lost, audio below -80 dB, frame count stopped |
| `scenes-sweep` | SSCN | 11 | `ot_fuzz.py` profile `scenes` | scene A/B select 0..15 and crossfader sweeps | same checks |
| `scenes-latency` | SSCN | 4 | `ot_xflag.py` | crossfader step to lock CC, stopped / playing / flood | tool error |
| `djump-off` | SDJ | 2 | `ot_djump.py` | landing step with the toggle off (control) | tool error |
| `djump-on` | SDJ | 3 | `ot_djump.py` | landing step and position with the toggle on | tool error |
| `djump-burst` | SDJ | 11 | `ot_fuzz.py` profile `pc` | program-change bursts with the toggle on | same checks |
| `mix-soak` | SFX_01 | 60 | `ot_fuzz.py` profile `mix` | 56 min of program changes, START / STOP, tempo, crossfader, scenes, mutes, levels, FX knobs; crosses the 50.7-minute frame-count mark | same checks |

About 135 min of rig time plus loads. Panel steps inside phases: DIRECT_JUMP toggle (`djump-on`, `djump-burst`:
[PTN] + [YES], OFF at every power-on), fresh load for `kits-identity` and `mix-soak`.

`djump-off` and `djump-on` print the landing table; the pass is the tool's exit code, so read the tables against
[HARDWARE_MATRIX.md](HARDWARE_MATRIX.md) "DIRECT_JUMP_KYOTI on a unit" (landing on the first step after the
program change with the toggle on, at the pattern end with it off).

## Results on a unit

 Sam's MKII, image `OCTABAMR3` (`octabam` 0.1: the stations, PATTERN MUTE and the ColdFire modules
OCTA303, MORPH, REC THRESHOLD, BUFFER SAVER, COPY PROJECT, SEQ, FX2 LOCK and TRACK PATTERNS), USB TRACKS PRE, the
projects of `ot_suite.py build` (74 layouts + BASE). Each project loaded from a pristine copy.

| phase | result |
|---|---|
| `pre-meter`, `pre-transport`, `pre-usb` | PASS; `underruns=0 bankdup=0` |
| `dsp-watch` | PASS: 20 cycles, 6,464 polls, 2,756 records a second |
| `fx01`, `fx02`, `fx03` | 32, 32 and 13 layouts ran, no CRASH or stall; 16, 19 and 4 flagged (CLICKS: DJ EQ, LO-FI, MODULATION and SPECTRUM modes; ROUGH, LEVEL, DC, CLIP: MODULATION `dear`; STATIC, LEVEL, CLIP: SPECTRUM and CHARACTER `dear`) |
| `loader01`, `loader02` | 18 + 2 transitions applied, `bad 0`, 340 ms of silence at each, ColdFire longest run in the window 404 to 476 us (steady 303 to 317 us) |
| `kits-identity` | PASS: 603 program changes over 605 s; ColdFire longest run 493 us; 44 bad DSP records |
| `scenes-sweep` | PASS: 2,289 operations over 604 s; longest ColdFire run 483 us; 18 bad DSP records |
| `scenes-latency` | crossfader to lock CC, median / p95 / max ms: stopped 0.83 / 0.99 / 1.01, playing 0.77 / 1.32 / 1.34, flood 0.95 / 1.71 / 2.08 (39 of 40 answered) |
| `djump-off`, `djump-on` | toggle off: landing at step 32 (the pattern end) in 6 usable trials; on: landing 0 to 5 steps after the program change, `since-start` in 11 of 12, the 12th ambiguous |
| `djump-burst` | PASS: 536 operations over 604 s, `bad 0` |
| `mix-soak` | not run on `R3` |

Not run: the manual plan ([HARDWARE_MANUAL.md](HARDWARE_MANUAL.md)). `ot_djump.py` fits 16-step patterns; `build` sets
the two patterns it uses to 16 steps (the stimuli projects' patterns are 64 steps).

Failures found while running the suite on earlier images, and the module sets they led to leaving out of `octabam`:
[FAILURE_MODES.md](FAILURE_MODES.md), "CX OSC in the image" and "Program changes left unapplied in a loader soak".

## What the cable exercises, by module

| module | phase |
|---|---|
| the 14 stock effects, LOFI AMF FIX, MODE DEFAULTS | `fx`, `loader`, `mix-soak` |
| SPECTRUM, CHARACTER, MODULATION (DLPUMP, DLCOPY: load, withdraw, homes, reverb guard, collision) | `fx`, `loader`, `mix-soak` |
| LOAD METER | every phase |
| KITS | `kits-identity`, `loader`, `mix-soak` (pattern change loads the Kit) |
| MIDI SCENES | `scenes-sweep`, `scenes-latency` |
| DIRECT_JUMP_KYOTI | `djump-*` |
| USB (MIDI both ways, TRACKS PRE, MAIN, CUE) | every phase; `pre-usb`, `pre-transport`, `dsp-watch` |
| SEQUENCER EVENTS, STORE | background of the fuzz phases |
| ATA WRITE GUARD | none on the rig (card writes need a project load and save) |

## Open

- CC MAP (CC 102-107, 108-111, 14, 15 onto page 2) and CC FEEDBACK (knob changes out as CC) are observable over USB
  MIDI. No phase: the CC numbers and channels the unit echoes with have not been measured on a unit.
- Kits with a non-identity assignment: `ot_kits.py migrate <project> octabam --rotate 1` needs the port
  (`make emu-cf`); on a unit, let the first load migrate, copy `kits.work` off the card,
  `ot_kits.py rotate 1`, put it back.
- Real material: all audio is synthetic.
- The SFX project list is cut at 31 layouts per project; pair and split layouts need `ot_matrix.py predict`
  ([HARDWARE_MATRIX.md](HARDWARE_MATRIX.md)).

## v0.6 checks (`ot_v06.py`)

`tools/hw/ot_v06.py` runs the v0.6 items that need no panel step, over REMOTE (COMMAND 1 to 4 and PEEK). Not run on
a unit yet.

```bash
.venv/bin/python3 tools/hw/ot_v06_build.py build out/v06b          # three projects + v06.json
.venv/bin/python3 tools/hw/ot_v06.py suite --dest out/v06b         # images, projects, matrix runs, DISK MODE read, boots
```

The images are `OCTABAM T1` (`octabam`), `V06-RIG T1` (`remixes/test/v06-rig`: CX OSC, VCA160, KEYBUS, REMOTE, USB,
REMIX SWITCH), `OCTABAM-VRB T1` (`octabam-verbs`) and `STOCK 1.40C`, built with `make image REMIX=octabam BUILD=T1`
and `make rmx REMIX=<remix> BUILD=T1`. `OCTABAM T1` is flashed; the rest are `.RMX` files in `/BRAIN/REMIXES`.
No shipping remix carries CX OSC or VCA160, and the test remixes lack REMOTE, USB and REMIX SWITCH.

| check | issue | project / image | pass when |
|---|---|---|---|
| boots | #1247, #1233, #1272 | every image change | COMMAND 3 returns within 150 s, the image asked for runs, MB_PARK (`0x41200038`) reads 3, the DSP counts |
| `diskread` | #1264 | any project, CLOCK SEND on | no 64 KB block of one file differs between 6 reads; none starts `0f f8 00 00` in one read only |
| OCTA303 T1+T2 | #1270 | `V06_OCT` / `octabam` | slot plays above -70 dBFS RMS, no flag |
| WAVE T1+T2 | #1232 | `V06_OCT` / `octabam` | as above; no RINGS (tail silent after STOP) |
| CX OSC T1 | #1263 | `V06_RIG` / `V06-RIG` | as above; no CLICKS |
| VCA160 FX1, FX2 (def, dear) | #1219 | `V06_RIG` / `V06-RIG` | no flag |
| VERBERATION FX2 (def, dear, modes 0, 2, 3) | #1234 | `V06_VRB` / `octabam-verbs` | no flag; RINGS is the stop kill |

A machine slot is a FLEX track signed with the machine's Part signature, `Part + 0x3c + 30 * track`; the file offset
(PART_BASE + 9 + 0x3c + 30 * track) is inferred from the port gates' RAM offsets, and a slot that reads silent is
the symptom of a miss. The machines' PLAYBACK and SETUP values are the module's seeds: nothing writes them, so
#1263's FOLD at DEC HOLD is not set by the project. Each pass is only a flag-free matrix run: LEVEL, STATIC and
the other flags compare the slot with BASE, which has stimulus audio and no machine.

A boot that does not return is the boot-screen stop of #1247; the run stops, and the unit needs a power-cycle.
`out/hw/boot_ledger.tsv` has every attempt. Output: `out/hw/v06/<label>/summary.json` and the matrix reports under
`out/hw/matrix/`.

Not reachable over the cable (panel gestures, or no host-visible result): #1246 (AED), #1251 and #1252 (TEMPLATES),
#1250 and #1229 (TEMPO BUS copy, paste and scene locks), #1255 (FRAME GUARD on an MKI with 8 recorders and 8 voices),
#1219's KEY routing (no KEY value is set), #1266 (what MIDI LOOPBACK echoes is not written down).
