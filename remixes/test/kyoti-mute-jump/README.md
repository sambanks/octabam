# `kyoti-mute-jump` -- MUTE_MODES, DIRECT_JUMP_KYOTI, BATCH_BUGFIXES

3 ColdFire modules by Zac Kyoti and the stock effects.

## What is in it

- **MUTE_MODES** -- [`modules/mute-modes/README.md`](../../../modules/mute-modes/README.md).
- **DIRECT_JUMP_KYOTI** -- [`modules/direct-jump-kyoti/README.md`](../../../modules/direct-jump-kyoti/README.md).
- **BATCH_BUGFIXES** -- [`modules/batch-bugfixes/README.md`](../../../modules/batch-bugfixes/README.md). DIRECT_JUMP_KYOTI requires it.
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Build

```bash
make image REMIX=kyoti-mute-jump BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=kyoti-mute-jump` runs every gate first.
