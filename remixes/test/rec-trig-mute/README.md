# `rec-trig-mute` -- REC_TRIG_MUTE

One ColdFire module by Zac Kyoti and the stock effects.

## What is in it

- **REC_TRIG_MUTE** -- [`modules/rec-trig-mute/README.md`](../../../modules/rec-trig-mute/README.md).
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

The module's bytes are the author's: `reference` re-links the unit at his address every build and compares. The same source ran on the author's MKI, 2 and 3 Oct 2026 (standalone and inside KYOTI V1.0). This remix as a whole has not been flashed.

## Build

```bash
make image REMIX=rec-trig-mute BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=rec-trig-mute` runs every gate first.
