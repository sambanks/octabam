# `slow-lfo` -- SLOW LFO

One ColdFire module by Nathan Groth and the stock effects: the remix
`verify_slow_lfo` runs on.

## What is in it

- **SLOW LFO** -- [`modules/slow-lfo/README.md`](../../../modules/slow-lfo/README.md).
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Build

```bash
make image REMIX=slow-lfo BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `OT_PROJECT=<dir> make check REMIX=slow-lfo` runs every gate first.
