# Remixes

A remix is a named selection of modules; `make image REMIX=<name> BUILD=<n>` builds it into a card-flashable image from your own OS 1.40C. Each remix is a directory here: `remix.py` is the selection, `README.md` says what is in it and how to flash it. This index is rendered from the selections (`make docs`).

- What to install first (the Xcode Command Line Tools, Homebrew, Python 3.10+, `cmake`, `uv`) and every step to a flashed unit: [BUILDING.md](../docs/guide/BUILDING.md).
- Composing your own: [COMPOSING.md](../docs/guide/COMPOSING.md).
- The remixes that carry one module for its gates: [test/](test/README.md).
- Contributors' own selections: [community/](community/README.md).

## The delay and reverb bus

| remix | contains |
|---|---|
| [`octabam-bus`](octabam-bus/README.md) | CORE + the extra ColdFire modules of octabam + the delay and reverb bus (BusDelay on T1's FX2, BusVerb on T5's FX2, SEND on every other track's FX2, the stock DELAY on T8) + SPECTRUM, CHARACTER and MODULATION on FX1. |

## Firmware mods on the stock effects

| remix | contains |
|---|---|
| [`octabam`](octabam/README.md) | The core ColdFire modules, SCOPE and TUNER, every other ColdFire module that fits, all 14 stock effects, and SPECTRUM, CHARACTER and MODULATION, loaded on demand, with COMPRESSOR's side-chain. |
| [`octabam-verbs`](octabam-verbs/README.md) | octabam with VERBERATION and its PLATE, ROOM and HALL rows in place of PLATE REV, SPRING REV and DARK REV: the core ColdFire modules and every other ColdFire module that fits, the 11 other stock effects, and SPECTRUM, CHARACTER, MODULATION, SHATTER and COMPRESSOR's side-chain loaded on demand, with VIBRATO, TRANSIENT and RESONATOR resident in the reverbs' words. |

Never share a built image: it contains Elektron's OS.
