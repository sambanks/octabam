# `usb-out-tracks-post` — USB LAYOUT TRACKS POST on the stock effects

The stock chooser plus USB at LAYOUT TRACKS POST, for testing the post-fader stems on a unit that runs stock projects: no FX1 stations, no chooser changes, no project stamping.

## What is in it

- **USB** at LAYOUT TRACKS POST: sixteen 24-bit channels, track N's L/R on 2N−1/2N, each after that track's own MAIN gain (LEVEL, mute, solo, XLV; MAIN_LEVEL left out); the stems' stereo sum at full speed. [`USB`](../../../modules/usb/README.md#tracks-post).
- the 14 stock FX2 effects.

## Build

```bash
make image REMIX=usb-out-tracks-post BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=usb-out-tracks-post` runs every gate first.
