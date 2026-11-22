# `wavecf` — the WAVE machine

One ColdFire module and the stock effects.

## What is in it

- **WAVE CF** — a row of the track's machine list, **WAVE**: a 4-voice wavetable voice (PLAYBACK: TUNE FRAM
  CHRD VOIC SPRD GLID). `modules/wavecf/README.md`.
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Build

```bash
make image REMIX=wavecf BUILD=1    # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit.
