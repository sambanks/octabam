# `usb-out-tracks-post` — USB AUDIO OUT TRACKS POST on the stock effects

The stock chooser plus USB MIDI and USB AUDIO OUT TRACKS POST, for testing the post-fader stems on a unit that runs stock projects: no FX1 stations, no chooser changes, no project stamping.

## What is in it

- **USB MIDI** and **USB AUDIO OUT** (LAYOUT TRACKS POST): sixteen 24-bit channels, track N's L/R on 2N−1/2N, each after that track's own MAIN gain (LEVEL, mute, solo, XLV; MAIN_LEVEL left out); the stems' stereo sum at full speed. USB AUDIO OUT with LAYOUT TRACKS POST: [`modules/usb-audio-out`](../../../modules/usb-audio-out/README.md#tracks-post).
- the 14 stock FX2 effects.

## Status

Smoke-tested on a MKII as P3 (allmyfriendsaresynths (@clickysteve), 5 Oct 2026): sixteen channels, each track on its pair, LEVEL, mute, solo and the crossfader followed in the stems. The module's gain engine was nulled against MAIN on the same unit in a 20-channel diagnostic build; on 7 Oct 2026 the tracks-to-MAIN offset read 0 samples (through TRACKS MAIN CUE, the same read-back path) and the streaming cost +2.8 µs a frame over OUT TRACKS (CF METER, `cfmeter-post` against `cfmeter-tracks`); MASTER TRACK and the no-host cost have not been tested on a unit ([the module's README](../../../modules/usb-audio-out/README.md#tracks-post), *On the unit*). Gates: `verify_usb`; `verify_usb_post` with a source project.

## Build

```bash
make image REMIX=usb-out-tracks-post BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=usb-out-tracks-post` runs every gate first.
