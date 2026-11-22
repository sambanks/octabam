# `direct-jump-kyoti` -- DIRECT_JUMP_KYOTI, BATCH_BUGFIXES

Two ColdFire modules by Zac Kyoti and the stock effects.

## What is in it

- **DIRECT_JUMP_KYOTI** -- [`modules/direct-jump-kyoti/README.md`](../../../modules/direct-jump-kyoti/README.md).
- **BATCH_BUGFIXES** -- [`modules/batch-bugfixes/README.md`](../../../modules/batch-bugfixes/README.md). DIRECT_JUMP_KYOTI requires it.
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Build

```bash
make image REMIX=direct-jump-kyoti BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=direct-jump-kyoti` runs every gate first.
