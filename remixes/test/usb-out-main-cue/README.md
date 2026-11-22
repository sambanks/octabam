# `usb-out-main-cue` — USB LAYOUT MAIN CUE on the stock effects

The stock chooser plus USB at LAYOUT MAIN CUE, for testing the four-channel (MAIN + CUE) stream on a unit that runs stock projects: no FX1 stations, no chooser changes, no project stamping.

## What is in it

- **USB** at LAYOUT MAIN CUE (markandrus/octemu; the MC variant Bryan T's): USB-MIDI mirroring DIN; four 24-bit channels, MAIN L/R + CUE L/R, at the same 250 us cadence as the other layouts; full speed carries MAIN alone. [`USB`](../../../modules/usb/README.md#main-cue).
- the 14 stock FX2 effects.

## Build

```bash
make image REMIX=usb-out-main-cue BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=usb-out-main-cue` runs every gate first.
