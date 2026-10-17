# `blackpyramids-303` -- BLACKPYRAMIDS_303

One machine module by Zac Kyoti and the stock effects, SPRING REV given up.

## What is in it

- **BLACKPYRAMIDS_303** -- [`modules/blackpyramids-303/README.md`](../../../modules/blackpyramids-303/README.md).
- the stock FX2 effects except SPRING REV, whose DSP words are the voice.

## Status

The module's runtime bytes are the author's: `reference` re-links the unit at the author's address every build and compares. Its DSP voice is the author's standalone image's, word for word. The author's standalone images run on their MKI (14–16 Oct 2026). This remix as a whole has not been flashed.

## Build

```bash
make image REMIX=blackpyramids-303 BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=blackpyramids-303` runs every gate first.
