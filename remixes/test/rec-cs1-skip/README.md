# `rec-cs1-skip` -- REC CS1 SKIP

One ColdFire module by Bryan Tysinger and the stock effects.

## What is in it

- **REC CS1 SKIP** -- [`modules/rec-cs1-skip/README.md`](../../../modules/rec-cs1-skip/README.md).
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

`verify_rec_cs1_skip` runs the module's routine against stock's under unicorn every check. The module ran on Bryan T's MKII in test builds with other modules (1-2 Nov 2026). This remix as a whole has not been flashed.

## Build

```bash
make image REMIX=rec-cs1-skip BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=rec-cs1-skip` runs every gate first.
