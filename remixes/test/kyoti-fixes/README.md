# `kyoti-fixes` -- QUANTIZE_LIVE_REC_TOGGLE, ERASE_EMPTY_TRIGLESS_LOCKS, BATCH_BUGFIXES

3 ColdFire modules by Zac Kyoti and the stock effects.

## What is in it

- **QUANTIZE_LIVE_REC_TOGGLE** -- [`modules/quantize-live-rec-toggle/README.md`](../../../modules/quantize-live-rec-toggle/README.md).
- **ERASE_EMPTY_TRIGLESS_LOCKS** -- [`modules/erase-empty-trigless-locks/README.md`](../../../modules/erase-empty-trigless-locks/README.md).
- **BATCH_BUGFIXES** -- [`modules/batch-bugfixes/README.md`](../../../modules/batch-bugfixes/README.md).
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Build

```bash
make image REMIX=kyoti-fixes BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=kyoti-fixes` runs every gate first.
