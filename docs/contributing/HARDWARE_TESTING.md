# Testing a remix on a unit

A walk-through for running the one-cable rig on your own Octatrack: build and
flash an image, put a generated project on the card, run the layout matrix or a
stress sequence, read the result, recover from a failure. The reference for the
matrix itself (flags, limits, measured results) is
[HARDWARE_MATRIX.md](HARDWARE_MATRIX.md); what has gone wrong on a unit is in
[FAILURE_MODES.md](FAILURE_MODES.md).

Four documents cover testing on a unit: this walk-through; [HARDWARE_MATRIX.md](HARDWARE_MATRIX.md), the reference for the
matrix, the stress sequences, MIDI SCENES and DIRECT_JUMP_KYOTI runs, the flags and the limits;
[HARDWARE_SUITE.md](HARDWARE_SUITE.md), the `octabam` remix's phases and results; [HARDWARE_MANUAL.md](HARDWARE_MANUAL.md), the plan
for what the cable cannot reach.

The rig needs one USB cable between the Mac and the unit. It sends USB MIDI
(program change, START, a host clock, CCs), captures the unit's USB audio, and
reads LOAD METER over a USB vendor request (`0xc0/0x57`). No audio interface,
MIDI interface or second device is involved.

## What you need

- A Mac. `tools/hw/ot_midi.py` and the tools that use it drive the unit over
  CoreMIDI. On Linux they use ALSA raw MIDI instead (`tools/hw/ot_midi_alsa.py`).
  `ot_djump.py` and `ot_xflag.py` call CoreMIDI directly and stay macOS-only. A
  native Windows host has not been tried. On Linux or WSL2:
  - On Windows, for WSL2: `winget install usbipd`, then in an admin terminal
    `usbipd list` and `usbipd bind --busid <id>` once. Then
    `usbipd attach --wsl --busid <id> --auto-attach` (no admin), left running:
    it attaches the unit again after each power-cycle. WSL2 shuts down when no
    WSL session is open, and the unit detaches with it; keep a terminal or a
    `wsl.exe -- sleep 86400` open for the whole session. The bus id changes
    with the USB port.
  - `sudo apt install libportaudio2 libusb-1.0-0 usbutils alsa-utils`, and
    `sudo modprobe snd-usb-audio` if `/dev/snd` has no `midiC*` once the unit
    is attached.
  - Your user in the `audio` group, for `/dev/snd`, and a udev rule for LOAD
    METER's vendor request:
    `SUBSYSTEM=="usb", ATTR{idVendor}=="1935", MODE="0666"` in
    `/etc/udev/rules.d/99-elektron.rules` (a name that sorts after
    `50-udev-default.rules`, which otherwise resets the mode to 0664).
  - What ran, 8 Nov 2026 (Yves's MKII, WSL2 on Windows 11, usbipd-win 5.3.0):
    `ot_matrix.py switch` (3 runs and a 32-transition run), `ot_dspwatch.py`
    (100 cycles, with and without `--audio`, polling at 20 and 400 a second),
    `load_meter.py` (313 to 433 reads a second, 0 read errors), `ot_suite.py
    build` and `ot_matrix.py audit`. MIDI, transport and LOAD METER worked. The
    USB audio capture did not keep up: over usbip it delivered about a quarter
    of the frames (1.27 s of audio in 5 s, no PortAudio status flag), so every
    measure that reads the audio (`switch`'s silence, `run`'s CRASH, FREEZE,
    CLICKS and the rest) is not usable on this host.
- An Octatrack MKI or MKII with the user's own 1.40C OS, and a CF card.
- `.venv/bin/python3 -m pip install pyusb libusb-package sounddevice numpy`, and, on a Mac,
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

## Reading events on a unit

An image with REMOTE (`octabam`, `octabam-bus`, `octabam-verbs`) keeps a ring of timestamped records (project
load and save events, PLAYING, BANK, PATTERN, the queued pair, a COMMAND having run) and the last 512 frame
interrupts' interrupted PCs, read over USB (`modules/remote/README.md`). Run on an MKII on 15 Nov 2026.

```
python3 tools/hw/ot_events.py                          # every record the ring holds
python3 tools/hw/ot_events.py --follow                 # then each new one
python3 tools/hw/ot_events.py --wait PATTERN --arg 3 --timeout 20   # exit 0 when it arrives, 1 at the timeout
```

In a script, `Events.wait_for(kind, arg, timeout)` returns the first record that matches and raises
`TimeoutError` otherwise; `Events.lost` counts records overwritten before they were read. `trace` and `peek`
read the PC samples and memory; `command` enters and leaves USB DISK MODE, `boot` starts a `.RMX` of
REMIX SWITCH's list (`remixes` lists it as the unit holds it). On an image without REMOTE every request
STALLs. The stamps are DMA timer 3's count (132 MHz, wrapping every 32.5 s).

After a MIDI START the PLAYING 1 record arrives in 7 to 8 ms. A MIDI STOP writes PLAYING 2 and nothing when
the sequencer was already stopped, so a stop is waited for through the playing byte, not a record
(`ot_events.wait_stopped(remote, fallback)`: the old sleep without REMOTE, else PEEK of `0x800065bb` until it
leaves 1, within the same `fallback`). `ot_events.connect()` gives the `Remote` or None. A program change while
playing writes QPATTERN at once and PATTERN at the pattern's end (7.9 and 8.0 s at 120 BPM); with the sequencer
stopped both arrive 4.5 to 5.9 ms after the send. A program change sent stopped is waited for through the
bank and pattern bytes (`ot_events.wait_pattern(remote, program, fallback)`: PEEK of `0x800065bd` and `0x800065be`
until they are bank `p // 16`, pattern `p % 16`; a change to the current pattern writes no record). `ot_matrix.py`
(run, switch) and `ot_ladder.py` (through `Clock.stop_wait` and `Clock.pc_wait`) wait for stops and stopped
program changes this way, each with the old sleep as the fallback; the program changes sent while playing
(`ot_matrix.py` switch) are timed by the run. Every other `time.sleep` in `ot_matrix.py`, `ot_stall.py` and
`ot_ladder.py` carries a comment naming what it waits for. `ot_suite.py` has none.

## Without the panel: image and project over USB

With an image that carries REMOTE, STORE and USB (`octabam`, `octabam-bus`, `octabam-verbs`), `tools/hw/ot_card.py`
does the card and the image switch. Run on an MKII on 18 Nov 2026 with the three BUILD 05 images.

```
python3 tools/hw/ot_card.py copy "OCTABAM-VRB 05.RMX" ...     # files into /BRAIN/REMIXES/, then COMMAND 4; no file: rescan only
python3 tools/hw/ot_card.py boot "OCTABAM-VRB 05.RMX"         # COMMAND 3, waits for the unit to leave and return
python3 tools/hw/ot_card.py load out/suite/octabam/SFX_01     # project onto the card, unit reloads it
python3 tools/hw/ot_card.py fingerprint                       # which image is running
python3 tools/hw/ot_suite.py run <label> --dest out/suite/<remix> --auto --phase pre-meter,pre-transport,pre-usb,pc-soak
```

- `load` enters DISK MODE (COMMAND 1), replaces `PRESETS/<name>` with the project (default `RMT_SFX_01`), removes
  the `._*` files, compares every file, unmounts and leaves (COMMAND 2). Leaving reloads the project the unit has
  loaded, so `<name>` must be that project: load it from the panel once, then every later load is this command.
  The record that follows is NEWPROJ or LOADMASK.
- `boot` needs the name in REMIX SWITCH's list; a fresh image's list is empty until a scan, which `boot` sends.
- Nothing over USB carries the running image's name. `fingerprint` prints the ring header's three linked addresses
  (RMT_TRACE, REMIX SWITCH's name list and count); they differ per image. 18 Nov 2026, BUILD 05: `octabam`
  `0x40b34f44 0x40af0238 0x40af0188`, `octabam-verbs` `0x40b22a84 0x40ae7fb8 0x40ae7f08`, `octabam-bus`
  `0x40b20a84 0x40ae7520 0x40ae7470`. The boot screen shows the flashed image's name, not the running one's.
- Leave DISK MODE with `diskutil unmount` and then `diskutil eject`, not unmount alone: after an unmount alone the Mac
  keeps `diskN` and no later DISK MODE mounts the card (FAILURE_MODES.md). After COMMAND 1 the Mac did not always mount
  the card; `ot_card.py` runs `diskutil mount` on the OCTATRACK partition after 8 s and repeats COMMAND 1 up to 4 times.
- `load` and `boot` return when LOAD METER's health rule holds (the DSP's frame count advances); 0.4 s after the
  reload record on 18 Nov 2026.
- `ot_matrix.py switch` prints the transitions left unapplied (`unapplied`: the DSP busy from 2.5 s after the switch
  is nearer the previous layout's figure than the new one's) and puts none of that in its exit code, which is 1 when
  any row carries a flag (`GAP` is on every transition: the 340 ms silence is the load).

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
- MIDI SCENES and DIRECT_JUMP_KYOTI runs (`ot_scenes.py`, `ot_xflag.py`, `ot_djump.py`, the `scenes` profile, the toggle set by hand): [HARDWARE_MATRIX.md](HARDWARE_MATRIX.md), "MIDI SCENES on a unit" and "DIRECT_JUMP_KYOTI on a unit".
- The audio check's rule (three unmuted tracks, every track starting unmuted) is in [HARDWARE_MATRIX.md](HARDWARE_MATRIX.md), "Stress sequences".
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
