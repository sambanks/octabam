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
`window_demand` (MODULATION, SPECTRUM, CHARACTER, SIDECHAIN_COMPRESSOR, DISTORX, TRANSIENT on 1 Nov 2026). Rebuild
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
| `SFX_01..NN` | `ot_matrix.py proj --clean --stimuli hits,pink,two_tones,sweep,ladder,impulses` | BASE + up to 31 layouts each: every effect on all 8 tracks in FX1 and FX2, each MODE with and without `dear`; 80 layouts + BASE in 3 projects on 1 Nov 2026 (DISTORX included) |
| `SSCN` | SFX_01 + `ot_scenes.py stamp --banks 1-2 --all-scenes --trigs grid4` | MIDI track 1 on channel 11, CC 1 locked in all 16 scenes, MIDI trigs on steps 4, 8, 12, 16, clock and transport receive on |
| `SDJ` | SFX_01 + `ot_scenes.py stamp --banks 1-2 --pattern-steps 2=1,2,4,7,8,11,13` | pattern 2 notes on steps 1, 2, 4, 7, 8, 11, 13 |

## Phases

| id | project | min | tool | what it measures | fails when |
|---|---|---|---|---|---|
| `pre-meter` | SFX_01 | 1 | `load_meter.py --for 10` | LOAD METER answers, frame count advances | request STALLs, count stopped |
| `pre-transport` | SFX_01 | 1 | `usb_transport_probe.py` | START / STOP / host clock over USB | no transport reaction |
| `pre-usb` | SFX_01 | 1 | `usb_counters.py` | USB audio ring counters | request fails |
| `fxNN` | SFX_NN | 11 each | `ot_matrix.py run` | per layout: CRASH, FREEZE, CLICKS, ROUGH, STATIC, LEVEL, CLIP, DC/RINGS, DROPS, OVERLOAD, LOAD; DSP busy per core, per-slot cost | any flag |
| `loaderNN` | SFX_NN | 2-7 | `ot_matrix.py switch --pairs` | program-change transitions: loaded effect to BASE, to a stock reverb, to another loaded effect (both FX1 and FX2 hosts); gaps, ColdFire longest run, bad records | any flag |
| `kits-identity` | SFX_01 | 10 | `ot_fuzz.py` profile `pc` | 10 min of program changes (single, burst, back) across 32 patterns; each plays its Kit (firmware-migrated from the stock Parts at the first load) | MIDI destination lost, audio below -80 dB, frame count stopped |
| `scenes-sweep` | SSCN | 11 | `ot_fuzz.py` profile `scenes` | scene A/B select 0..15 and crossfader sweeps | same checks |
| `scenes-latency` | SSCN | 4 | `ot_xflag.py` | crossfader step to lock CC, stopped / playing / flood | tool error |
| `djump-off` | SDJ | 2 | `ot_djump.py` | landing step with the toggle off (control) | tool error |
| `djump-on` | SDJ | 3 | `ot_djump.py` | landing step and position with the toggle on | tool error |
| `djump-burst` | SDJ | 11 | `ot_fuzz.py` profile `pc` | program-change bursts with the toggle on | same checks |
| `mix-soak` | SFX_01 | 60 | `ot_fuzz.py` profile `mix` | 56 min of program changes, START / STOP, tempo, crossfader, scenes, mutes, levels, FX knobs; crosses the 50.7-minute frame-count mark | same checks |

About 150 min of rig time plus loads. Panel steps inside phases: DIRECT_JUMP toggle (`djump-on`, `djump-burst`:
[PTN] + [YES], OFF at every power-on), fresh load for `kits-identity` and `mix-soak`.

`djump-off` and `djump-on` print the landing table; the pass is the tool's exit code, so read the tables against
[HARDWARE_MATRIX.md](HARDWARE_MATRIX.md) "DIRECT_JUMP_KYOTI on a unit" (landing on the first step after the
program change with the toggle on, at the pattern end with it off).

## What the cable exercises, by module

| module | phase |
|---|---|
| the 14 stock effects, LOFI AMF FIX, MODE DEFAULTS | `fx`, `loader`, `mix-soak` |
| SPECTRUM, CHARACTER, MODULATION, TRANSIENT, DISTORX, SIDECHAIN_COMPRESSOR (DLPUMP, DLCOPY: load, withdraw, homes, reverb guard, collision) | `fx`, `loader`, `mix-soak` |
| LOAD METER | every phase |
| KITS | `kits-identity`, `loader`, `mix-soak` (pattern change loads the Kit) |
| MIDI SCENES | `scenes-sweep`, `scenes-latency` |
| DIRECT_JUMP_KYOTI | `djump-*` |
| USB (MIDI both ways, TRACKS PRE, MAIN, CUE) | every phase; `pre-usb`, `pre-transport` |
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
