# `midi-scenes` — MIDI SCENES alone

MIDI SCENES on the DRAM platform without other ColdFire or DSP modules,
plus **DIRECT JUMP** so the `swd` gate (the follow at a DIRECT pattern
switch) runs. The remix has not been flashed.

## What is in it

- **MIDI SCENES** (bkkbrls-del, [midisc](https://github.com/bkkbrls-del/midisc); rewritten here, phase 1) — scene locks for the MIDI tracks: a second lock table the panel never had; scene hold, readout, unlock, XF morph and the scene clear/copy/paste rows. RAM only. One unit in DRAM, 21 detours, 2 pokes inside the OS.
- **DIRECT JUMP** — CHAIN AFTER's unused index 1 becomes DIRECT. It is a
  gate fixture here, not the module under test: `swd` needs it to make a
  pattern switch mid-pattern, which is the case where the mix must follow
  in the same step.

## Status

`verify_scenes` runs the panel scenarios on this image and on MIDISC2.1's under the port and compares MIDI out, the lock table, the track records and the screen. Not flashed.

## Build

```bash
make image REMIX=midi-scenes BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=midi-scenes` runs every gate first.
