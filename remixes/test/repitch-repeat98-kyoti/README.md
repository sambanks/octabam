# `repitch-repeat98-kyoti` -- REPITCH_REPEAT98_KYOTI

One ColdFire module by Zac Kyoti and the stock effects.

## What is in it

- **REPITCH_REPEAT98_KYOTI** -- [`modules/repitch-repeat98-kyoti/README.md`](../../../modules/repitch-repeat98-kyoti/README.md). The ColdFire half only (work in progress): RPS9 and RPSP's DSP kernel is not declared yet.
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

The module's bytes are the author's: `reference` re-links them at his addresses every build and compares. Those images ran on the author's MKI. This remix as a whole has not been flashed.

## Build

```bash
make image REMIX=repitch-repeat98-kyoti BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=repitch-repeat98-kyoti` runs every gate first.
