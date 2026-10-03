# `sidechain-compressor` -- SIDECHAIN_COMPRESSOR

One module by Zac Kyoti and the stock effects, less SPRING REV.

## What is in it

- **SIDECHAIN_COMPRESSOR** -- [`modules/sidechain-compressor/README.md`](../../../modules/sidechain-compressor/README.md), in COMPRESSOR's row. Work in progress.
- 13 of the 14 stock FX2 effects. SPRING REV gives up its words for the module's DSP section, as in the author's standalone build.

## Status

The ColdFire unit's bytes are the author's: `reference` re-links them at the author's address every build and compares. The author's standalone image ran on the author's MKI. This remix as a whole has not been flashed.

## Build

```bash
make image REMIX=sidechain-compressor BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=sidechain-compressor` runs every gate first.
