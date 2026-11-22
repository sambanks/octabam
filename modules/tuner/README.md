# `tuner` — TUNER

A guitar-tuner window for the current audio track, built from
[timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules)
(submodule `upstream/`, pinned to `v2.9` (`525f4b1`)). `Kind.CF_PATCH`: one DRAM unit
(`tuner.s`) and three detours. No ROM cave, no pokes, no DSP code, no FX2
row.

Hold **UP** and press **TEMPO**: a window the size of the stock TEMPO
window opens over the page with the track number, the note name and
octave, a +-50 cent needle, the cents and the frequency in Hz, about seven
readings a second, from the track's post-FX pre-fader audio (the read-back
arena the USB audio producer streams too). Below -54 dBFS or without a confident lobe
the last reading stays with HOLD. TEMPO, YES, NO or UP + TEMPO again close
it; TEMPO alone, FUNC + TEMPO (tap tempo) and UP alone stay stock (UP first,
then TEMPO). `upstream/tuner/README.md` is the full description (the
detector, what was measured and what is open).

## How it is built

Source: `upstream/` is Tim's repository (submodule, pinned to `v2.9` (`525f4b1`)).
Nothing inside `upstream/` is edited here. The manifest here
(`manifest.py`) executes `upstream/tuner/manifest.py` from the source on
disk and re-exports its `MODULE`; that manifest derives its source paths
from its own directory, so the same file builds at `modules/tuner/` in
Tim's tree and at `modules/tuner/upstream/tuner/` here. The unit is
`Linked(dram=True)`: linked into the platform runtime with the other DRAM
units and depacked at boot into the arena reserve
(`docs/contributing/PLACEMENT.md`). The detours sit on the TEMPO opener's first
instruction (`0x40059ef0`), frame_isr's tail (`0x4000d99a`, the instruction
before USB's audio producer's site) and the UI task's loop head (`0x40056c72`); each
stub replays what it displaced. The detector is integer only (no EMAC), so
it keeps no accumulator state across a task switch.

## Collisions

None known. It shares the platform reserve with the other DRAM modules
(SYNTH MACHINE's engine, USB, MIDI SCENES) inside one
runtime; `remixes/test/octatrick/` carries it beside the other two,
SYNTH MACHINE and MIDI SCENES, with USB at TRACKS MAIN CUE and ABCD.

## Updating

Bump the submodule pin and rebuild; the hook sites are read from the image
and the build refuses on a difference.
