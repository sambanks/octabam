# Testing a remix on a unit

A walk-through for running the one-cable rig on your own Octatrack: build and
flash an image, put a generated project on the card, run the layout matrix or a
stress sequence, read the result, recover from a failure. The reference for the
matrix itself (flags, limits, measured results) is
[HARDWARE_MATRIX.md](HARDWARE_MATRIX.md); what has gone wrong on a unit is in
[FAILURE_MODES.md](FAILURE_MODES.md).

The rig needs one USB cable between the Mac and the unit. It sends USB MIDI
(program change, START, a host clock, CCs), captures the unit's USB audio, and
reads LOAD METER over a USB vendor request (`0xc0/0x57`). No audio interface,
MIDI interface or second device is involved.

## What you need

- A Mac. `tools/hw/ot_midi.py` and the tools that use it drive the unit over
  CoreMIDI; a Linux or Windows host has not been tried.
- An Octatrack MKI or MKII with the user's own 1.40C OS, and a CF card.
- `.venv/bin/python3 -m pip install pyusb libusb-package sounddevice numpy`, and
  `brew install portaudio` for `sounddevice`.
- A fresh project made on the unit (PROJECT > NEW), copied off the card to your
  machine. `python3 tools/hw/ot_matrix.py audit <dir>` must find nothing. A
  project that descends from a working project fails the audit and is refused
  by `--clean`. Without a unit,
  `python3 tools/hw/ot_fresh.py --remix <remix>` makes one under the port.
- Nothing from Elektron goes in the repository: no image, slice or `.syx`.
  Generated projects and reports stay under `out/` or in your own folders.

## Which image carries what

| remix | LOAD METER | what a run measures |
|---|---|---|
| `octabam-inserts`, `octabam-bus` | yes | audio, DSP busy per core, each effect slot's cost, ColdFire share, dropped frames |
| `octabam-core` | no | audio only |

On an image without LOAD METER, `0xc0/0x57` answers with a STALL (`Pipe error`).
`ot_matrix.py run` and `ot_fuzz.py run` detect that, print "the image has no
LOAD METER" and run audio-only. In a stress run the health checks are then the
MIDI destination and the audio level. The USB audio channel count follows the
image's USB settings (TRACKS, MAIN, CUE): an image with TRACKS OFF presents
MAIN and CUE (4 channels), one with TRACKS PRE presents the 16 track channels
first.

## One session

1. **Build the image.** `make image REMIX=<remix> BUILD=<tag>` writes
   `out/OCTATRACK_OCTABAM<tag>.bin`. Use a tag that is new for each image you
   flash ([BUILDING.md](../guide/BUILDING.md) section 5).
2. **Generate the project.**
   `python3 tools/hw/ot_matrix.py plan <remix>` lists the layouts;
   `python3 tools/hw/ot_matrix.py proj <fresh> <dest-prefix> <remix> --clean --stimuli hits,pink,two_tones,sweep`
   writes `<dest-prefix>_01`, `_02`, ... of up to 31 layouts plus BASE.
3. **Put them on the card.** One `.bin` on the card root and nothing else with
   that name pattern (the upgrade took the first by name when there were
   several). Copy the project folder into `PRESETS/`, then on macOS
   `dot_clean -m <folder>` (the copy leaves `._*` metadata files), `sync`, and
   `diff -r <source> <card copy>`. When the card is mounted on the Mac, unmount
   it (not eject) before leaving DISK MODE on the unit.
4. **Flash and load.** PROJECT > SYSTEM > OS UPGRADE, then load the project on
   the unit.
5. **Check the unit before a run.** `python3 tools/hw/load_meter.py --for 10`
   (an image with LOAD METER); `python3 tools/hw/usb_transport_probe.py` for
   START and STOP over USB.
6. **Run.** `python3 tools/hw/ot_matrix.py run <project> <label> [--only 0,5-9]`
   for the matrix, or a stress sequence (below). A matrix run holds each layout
   for 12 s of play and 3 s of tail; projects of 23 to 28 layouts took about
   10 minutes.
7. **Read the result.** `out/hw/matrix/<label>/report.json` has the flags, the
   audio metrics and LOAD METER's series per layout;
   `python3 tools/hw/ot_matrix.py report <report.json> ...` prints a Markdown
   table. The flags are explained in [HARDWARE_MATRIX.md](HARDWARE_MATRIX.md).

## Measuring a module's processor cost

**Static, no unit.** `make cycles REMIX=<remix>` counts each module's per-sample
loop in DSP cycles (`tools/build/cycle_count.py`). It is a floor: memory
contention is not modelled, and a hook-only section is not priced.
`dsp_host -meter FILE` writes per-block instruction counts per core from a
render. Use both to decide whether a module is worth flashing; neither gives the
unit's busy figure.

**On the unit** (an image with LOAD METER: `octabam-inserts`, `octabam-bus`).
`ot_matrix.py plan <remix>` lists a single-effect layout per module and
setting, `<MODULE> FX1 def`, `<MODULE> FX2 def`, `dear`, and each mode. Each puts
that effect on all eight tracks in one slot, so each core carries four
instances. Run them and compare with BASE (no effect):

```
cost per slot  =  (DSP busy of the layout - DSP busy of BASE) / 4        per core
```

`ot_matrix.py run` prints `dsp <core 0>/<core 1>` for every layout. Worked
example, stock DJ EQ: BASE 22.5 / 14.9 %, `DJ EQ FX2 def` 51.7 / 44.1 %,
so (51.7 - 22.5) / 4 = 7.30 % per slot on core 0 and (44.1 - 14.9) / 4 = 7.30 %
on core 1. Readings are to 0.1 point of busy, so a per-slot figure is good to
about 0.03 point.

- **Budget.** A core has eight effect slots (four tracks, FX1 and FX2). At the 95 %
  limit an effect that may sit in every slot has `(95 - BASE) / 8` per slot:
  9.07 % on core 0 and 10.0 % on core 1 with BASE at 22.4 / 14.9 %.
- **Which numbers to compare.** The same effect costs the same on core 0 and core 1
  and in FX1 or FX2 to 0.1 point; a difference larger than that is a finding.
- **Each setting separately.** An effect with modes costs differently per mode, and a
  `dear` setting can cost more than the default. Run every mode with and
  without `dear`.
- **Per-slot counts.** `report.json` has `load.slots`: `mean_counts` per slot in
  timer-0 counts (36,256 to a frame). An empty slot reads about 76 counts, which is
  the hook's own cost.
- **Combinations.** `ot_matrix.py predict` adds the single-slot costs to rank pair
  and split layouts (see [HARDWARE_MATRIX.md](HARDWARE_MATRIX.md), "Predicting the
  combinations"); run the heaviest on the unit before relying on the sum, and not
  one predicted at 100 % or more.
- **What it does not show.** The ColdFire's share is the frame interrupt's
  (`cf` in the run output). An effect that runs on the ColdFire, like stock DELAY,
  reads 0 on the DSP and is not priced here.
- **Results so far.** The stock effects' per-slot costs are in
  [HARDWARE_MATRIX.md](HARDWARE_MATRIX.md), "Tests not yet run", item 1.

**ColdFire cost of a ColdFire module.** `tools/hw/ot_cfmatrix.py` writes a project of
layouts whose cost is ColdFire work: OCTA-303 voices (a `TB303` sample name, or a signed
machine), trig density, PTCH locks, VARISPEED (TSTR = VARI) and stations on FX1.
`plan` lists a set (`--set cost` or `--set diag`), `proj SRC DEST` writes it
(`--only-layout N` fills every slot with one layout, for the port, which plays A01), and
`run DEST LABEL` steps the layouts over USB MIDI and records only LOAD METER's ColdFire
share, longest run and both DSP cores. It needs no USB audio device.
`ot_matrix.py run` on the same project adds the audio detectors but needs the device.
The ColdFire share depends on whether a host is reading the unit's USB audio:
BASE (8 FLEX tracks, a hit on step 1) read 29.9 % with nothing reading the stream and
67.7 % with a capture open, TRACKS PRE, on one MKII (2 Nov 2026). Compare layouts
within one state.

## Stress sequences

`python3 tools/hw/ot_fuzz.py gen <seed> <out.json> --profile mix --minutes 10 --layouts <n>`
writes a seeded sequence of program changes, START and STOP, tempo moves, the
crossfader, scene select, mutes, levels and FX knobs;
`python3 tools/hw/ot_fuzz.py run <seq.json> <label>` plays it against a loaded
generated project and checks the unit every 0.5 s. `--layouts` is the number of
layouts in the project, BASE included. `ot_fuzz.py port <remix> <project> <label>`
replays sequences under the ColdFire port with no unit.

- Load the project fresh for each run. CCs (knobs, mutes, levels, the crossfader)
  change the unit's in-memory Part and survive a pattern change, so a second
  run on the same load starts from the first run's state. The unit also writes
  its state back to the card when the project is replaced: copy the pristine
  project folder over the card's copy (step 3) before loading it again.
- A project with no samples is silent: `--no-silence-check` skips the -80 dB check.
- MIDI SCENES: `python3 tools/hw/ot_scenes.py stamp <project> [--all-scenes]` writes MIDI track 1 (channel 11,
  CC1..CC10 on, scene A = 1, scene B = 9), MIDI trigs, CC 1 locks and the run settings (clock and transport receive
  on) into a copy of a fresh project; `show` prints the locks. Use profile `scenes` (scene select over 0..15, the
  range the unit takes) with `--all-scenes`. Record the track output with
  `python3 tools/hw/ot_midi.py -p "Elektron Octatrack DPS-1" listen <seconds>` alongside the run.
  `python3 tools/hw/ot_xflag.py` times a crossfader step to the lock CC (stopped, playing, with a CC flood).
- DIRECT_JUMP_KYOTI: stamp with `--pattern-steps 2=1,2,4,7,8,11,13`, turn the toggle on by hand ([PTN] + [YES]; OFF
  at every power-on, so after any restart), then `python3 tools/hw/ot_djump.py` prints the landing step and the
  position pattern 2 plays from for each of a series of program changes. Run it once with the toggle off for the
  control (landing at the pattern end).
- The audio check needs at least three unmuted tracks, counted from the
  sequence's own mute operations, and assumes every track starts unmuted.
- A 56-minute run crosses the 50.7-minute mark after power-up, which is where
  an unfixed frame counter stopped the unit (FAILURE_MODES.md).

## When it fails

- `ot_fuzz.py run` stops on the first failure and writes
  `out/hw/fuzz/<label>/failure.json` with the operation index, the last 40
  operations and the unit's state. `run <seq.json> <label> --until <index>`
  replays up to it. Power-cycle the unit after a failure.
- A freeze that comes at random: `freeze_watch.py` beside the unit for as long
  as it takes, with CLOCK SEND and TRANSPORT SEND on in the project. It adds
  nothing to the image: `probe` shows what the unit answers (GET_STATUS, LOAD
  METER when the image has it, USB audio's counters) and which triggers that
  arms. At a trigger it samples `--post` seconds more and writes
  `out/hw/freeze/freeze_<time>.json`: the `--pre` seconds before, the seconds
  after, and which part stopped (the sequencer alone, the audio engine, or the
  whole unit with USB). A reboot, USB DISK MODE or a STOP is logged, not
  counted. `--when` adds a trigger of your own; `--audio` keeps the unit's
  USB audio for the window (it starts USB audio's producer: a cost to the
  frame interrupt). Run `freeze_watch.py selftest` after changing it.
- Read LOAD METER after a stop before concluding the unit froze: a stopped
  count (`load_meter.healthy()`) is a frozen frame engine; a healthy count with
  silent audio is a different cause.
- Layouts predicted at 100 % DSP busy or more stall the DSP until a power-cycle.
  `ot_matrix.py predict` ranks pair and split layouts from the single-effect
  runs and leaves them out unless you ask for them.
- Add what you find to FAILURE_MODES.md when it is seen, with the image, the
  project, the commands and what was and was not established.

## Facts that cost time

- A program change during play takes effect at the end of the pattern: 8.0 s at
  120 BPM (64 steps), 7.68 s at 125 BPM.
- MIDI START alone does not play the unit's sequencer from the rig; the tools
  send a host clock with it (`ot_fuzz.ClockGen`). For a hand capture, press PLAY
  on the unit.
- A select knob (an effect's MODE, a probe's GO) is stored in the Part as its raw
  index, not as 0 to 127: stamp `{slot: index}`.
- The stimuli projects play on all eight tracks; the track-to-core mapping is
  inverted (tracks 5 to 8 are core A, 1 to 4 are core B).

## In a PR

The template's Hardware section: the unit (MKI or MKII), the image tag, the
project folder name, the commands, and the `report.json` figures. "Not flashed"
is an accepted answer. Do not attach images or `.syx`; reports stay in `out/`.
