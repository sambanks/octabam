# `usb-out-master` — USB AUDIO OUT MASTER on the stock effects

The stock chooser plus USB MIDI and USB AUDIO OUT MASTER, for testing the two-channel stream on a unit that runs stock projects: no FX1 stations, no chooser changes, no project stamping.

## What is in it

- **USB MIDI** and **USB AUDIO OUT MASTER**: USB-MIDI mirroring DIN; track 8's L/R, post-FX, pre-fader, on channels 1/2 at both USB speeds. [`modules/usb-audio-out`](../../../modules/usb-audio-out/README.md#master).
- the 14 stock FX2 effects.

## Status

Port only (`verify_usb`). Not on a unit in this form: high speed polls every 250 µs since 28 Sep 2026 (1 ms before, the form bottleservice ran as image 88).

## Build

```bash
make image REMIX=usb-out-master BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=usb-out-master` runs every gate first.
