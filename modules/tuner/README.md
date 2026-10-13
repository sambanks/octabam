# `tuner` — TUNER

A guitar-tuner window for the current audio track, built from
[timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules)
(submodule `upstream/`, pinned to `v2.14` (`39dc5d8`)). `Kind.CF_PATCH`: one DRAM unit
(`tuner.s`) and three detours. No ROM cave, no pokes, no DSP code, no FX2
row.

Hold **UP** and press **TEMPO**: a window the size of the stock TEMPO
window opens over the page with the track number, the note name and
octave, a +-50 cent needle, the cents and the frequency in Hz, about seven
readings a second, from the track's post-FX pre-fader audio (the read-back
arena USB AUDIO streams too). Below -54 dBFS or without a confident lobe
the last reading stays with HOLD. TEMPO, YES, NO or UP + TEMPO again close
it; TEMPO alone, FUNC + TEMPO (tap tempo) and UP alone stay stock (UP first,
then TEMPO). `upstream/tuner/README.md` is the full description (the
detector, what was measured and what is open).

## How it is built

Source: `upstream/` is Tim's repository (submodule, pinned to `v2.14` (`39dc5d8`)).
Nothing inside `upstream/` is edited here. The manifest here
(`manifest.py`) executes `upstream/tuner/manifest.py` from the source on
disk and re-exports its `MODULE`; that manifest derives its source paths
from its own directory, so the same file builds at `modules/tuner/` in
Tim's tree and at `modules/tuner/upstream/tuner/` here. The unit is
`Linked(dram=True)`: linked into the platform runtime with the other DRAM
units and depacked at boot into the arena reserve
(`docs/contributing/PLACEMENT.md`). The detours sit on the TEMPO opener's first
instruction (`0x40059ef0`), frame_isr's tail (`0x4000d99a`, the instruction
before USB AUDIO's site) and the UI task's loop head (`0x40056c72`); each
stub replays what it displaced. The detector is integer only (no EMAC), so
it keeps no accumulator state across a task switch.

## Collisions

None known. It shares the platform reserve with the other DRAM modules
(SYNTH MACHINE's engine, SY DRUM, PROCESSOR LOAD, USB MIDI, USB AUDIO,
MIDI SCENES) inside one runtime; `remixes/test/octatrick/` carries it beside
the other five, USB MIDI, USB AUDIO OUT TRACKS MAIN CUE and USB AUDIO IN
ABCD. It shares the UI task with PROCESSOR LOAD (different sites: the
loop head here, the type-1 message path there).

## Measured

- In the ColdFire port (26 Sep 2026, `upstream/tuner/README.md`
  "Measured"): steady tones 55 Hz .. 2 kHz read within 1 cent; the FM
  synth at PTCH -12 .. +12 reads the note the page shows; the chord, the
  closes and the stock TEMPO / tap-tempo paths as listed there; audio
  through the window unchanged.
- `make check REMIX=octatrick` on this tree: builds, boots under
  the port, the DRAM window reads back against the linked image.

## On the unit

- Works on Tim's MKI: UP + TEMPO opens the window and tunes (test build
  3.0 b40 = `octatrick` at BUILD 40, 29 Sep 2026), and in Modwerk's TUNER
  0.1.0 image (the same `tuner.s`; MAIN OS SHA-256 `66489376...`, not an
  octabam build) on 13 Oct 2026: its test sheet reported working (the
  readings were not recorded). The sources are
  unchanged since `v2.8` (`v2.14` included). The hook sites are read
  from the image and the build refuses on a difference; the other three
  modules' hooks in the same remix ran on Tim's MKI (the test builds
  2.3 .. 2.8 and the 2.9 line).

## Updating

Bump the submodule pin and rebuild; the hook sites are read from the image
and the build refuses on a difference.
