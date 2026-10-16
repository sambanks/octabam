# `varispeed` -- VARISPEED

One module by Zac Kyoti and the stock effects.

## What is in it

- **VARISPEED** -- [`modules/varispeed/README.md`](../../../modules/varispeed/README.md). On the author's MKI as a standalone image, 15 Oct 2026.
- All 14 stock FX2 effects, SPRING REV included.

## Status

The ColdFire unit's bytes are the author's: `reference` re-links them at the author's address every build and compares. The author's standalone image ran on the author's MKI. This remix has not been flashed.

## Build

```bash
make image REMIX=varispeed BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=varispeed` runs every gate first.
