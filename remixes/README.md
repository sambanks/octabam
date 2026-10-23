# Remixes

A remix is a named selection of modules; `make image REMIX=<name> BUILD=<n>` builds it into a card-flashable image from your own OS 1.40C. Each remix is a directory here: `remix.py` is the selection, `README.md` says what is in it, where it has run and how to flash it. This index is rendered from the selections (`make docs`).

- What to install first (the Xcode Command Line Tools, Homebrew, Python 3.10+, `cmake`, `uv`) and every step to a flashed unit: [BUILDING.md](../docs/guide/BUILDING.md).
- Composing your own: [REMIXER.md](../docs/guide/REMIXER.md).
- The remixes that carry one module for its gates: [test/](test/README.md).

## The delay and reverb bus

| remix | contains | proof |
|---|---|---|
| [`octabam-bus`](octabam-bus/README.md) | CORE + the delay and reverb bus (BusDelay on T1's FX2, BusVerb on T5's FX2, SEND on every other track's FX2, the stock DELAY on T8) + SPECTRUM, CHARACTER and MODULATION on FX1. | port-gated: cursory testing on Sam's MKII (owner report, 16 Oct 2026); EDIT EVENTS migration: software only, hardware pending; shared EVENTS migration is software-only, not hardware-tested |

## Firmware mods on the stock effects

| remix | contains | proof |
|---|---|---|
| [`cxosc-core`](cxosc-core/README.md) | CORE + REMIX SWITCH + CX OSC on the 14 stock effects. | `make check`: unit handoff: CORE + CX OSC; marker-less machine list, mono, stock LFOs |
| [`octabam-core`](octabam-core/README.md) | The core ColdFire modules on the 14 stock effects, with LOFI AMF FIX. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); EDIT EVENTS held-edit/copy paths on radiohagen's MKII, PLK858 (22 Oct); scoped operator report; shared EVENTS migration is software-only, not hardware-tested |
| [`octabam-inserts`](octabam-inserts/README.md) | CORE + SPECTRUM, CHARACTER, MODULATION, TRANSIENT and EUCLID on FX1 and FX2, LOFI2 (FX2), the stock DELAY and GATE VERB on FX2. | port-gated: EUCLID transport integration: scoped hardware checks ([PR #851](https://github.com/sambanks/octabam/pull/851)); EDIT EVENTS migration of PLOCKS P2: software only on this remix, hardware on octabam-core (Core PLK858, 22 Oct 2026); shared EVENTS migration is software-only, not hardware-tested |

Never share a built image: it contains Elektron's OS.
