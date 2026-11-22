# `usb-out-master` — USB LAYOUT MASTER on the stock effects

The stock chooser plus USB at LAYOUT MASTER, for testing the two-channel stream on a unit that runs stock projects: no FX1 stations, no chooser changes, no project stamping.

## What is in it

- **USB** at LAYOUT MASTER: USB-MIDI mirroring DIN; track 8's L/R, post-FX, pre-fader, on channels 1/2 at both USB speeds. [`USB`](../../../modules/usb/README.md#master).
- the 14 stock FX2 effects.

## Build

```bash
make image REMIX=usb-out-master BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=usb-out-master` runs every gate first.
