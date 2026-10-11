# `midi-scenes` — MIDI SCENES alone

One module. The smallest image with a real mod on the DRAM platform.

## What is in it

- **MIDI SCENES** (bkkbrls-del, [midisc](https://github.com/bkkbrls-del/midisc); rewritten here, phase 1) — scene locks for the MIDI tracks: a second lock table the panel never had; scene hold, readout, unlock, XF morph and the scene clear/copy/paste rows. RAM only. One unit in DRAM, 21 detours, 2 pokes inside the OS.

## Status

`verify_scenes` runs the panel scenarios on this image and on MIDISC2.1's under the port and compares MIDI out, the lock table, the track records and the screen. Not flashed.

## Build

```bash
make image REMIX=midi-scenes BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=midi-scenes` runs every gate first.
