# Remixes

A remix is a named selection of modules; `make image REMIX=<name> BUILD=<n>` builds it into a card-flashable image from your own OS 1.40C. Each remix is a directory here: `remix.py` is the selection, `README.md` says what is in it, where it has run and how to flash it. This index is rendered from the selections (`make docs`).

- What to install first (the Xcode Command Line Tools, Homebrew, Python 3.10+, `cmake`, `uv`) and every step to a flashed unit: [BUILDING.md](../docs/guide/BUILDING.md).
- Composing your own: [COMPOSING.md](../docs/guide/COMPOSING.md).
- The remixes that carry one module for its gates: [test/](test/README.md).

## The delay and reverb bus

| remix | contains | proof |
|---|---|---|
| [`octabam-bus`](octabam-bus/README.md) | CORE + the delay and reverb bus (BusDelay on T1's FX2, BusVerb on T5's FX2, SEND on every other track's FX2, the stock DELAY on T8) + SPECTRUM, CHARACTER and MODULATION and ten stock effects on FX1. | `make check` |

## Firmware mods on the stock effects

| remix | contains | proof |
|---|---|---|
| [`cxosc-core`](cxosc-core/README.md) | CORE + REMIX SWITCH + CX OSC on the 14 stock effects. | `make check`: unit handoff: CORE + CX OSC; marker-less machine list, mono, stock LFOs |
| [`octabam`](octabam/README.md) | The core ColdFire modules and every other ColdFire module that fits, all 14 stock effects, and SPECTRUM, CHARACTER, MODULATION and TRANSIENT, loaded on demand. | `make check` |

Never share a built image: it contains Elektron's OS.
