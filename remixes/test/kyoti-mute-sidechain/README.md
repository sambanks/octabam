# `kyoti-mute-sidechain` -- MUTE_MODES with SIDECHAIN_COMPRESSOR

Two modules by Zac Kyoti and the stock effects, less SPRING REV.

## What is in it

- **MUTE_MODES** -- [`modules/mute-modes/README.md`](../../../modules/mute-modes/README.md). Beside SIDECHAIN_COMPRESSOR it builds its SC_KEY variant: a muted KEY track keeps feeding the compressor.
- **SIDECHAIN_COMPRESSOR** -- [`modules/sidechain-compressor/README.md`](../../../modules/sidechain-compressor/README.md). Work in progress.
- 13 of the 14 stock FX2 effects. SPRING REV gives up its words for SIDECHAIN_COMPRESSOR's DSP section.

## Status

Each ColdFire unit's bytes are the author's: `reference` re-links them at the author's addresses every build and compares (MUTE_MODES' SC_KEY variant against the KYOTI V1.0 image). Those images ran on the author's MKI. This remix as a whole has not been flashed.

## Build

```bash
make image REMIX=kyoti-mute-sidechain BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=kyoti-mute-sidechain` runs every gate first.
