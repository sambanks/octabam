# Remixes

A remix is a named selection of modules; `make image REMIX=<name> BUILD=<n>` builds it into a card-flashable image from your own OS 1.40C. Each remix is a directory here: `remix.py` is the selection, `README.md` says what is in it, where it has run and how to flash it. This index is rendered from the selections (`make docs`).

- What to install first (the Xcode Command Line Tools, Homebrew, Python 3.10+, `cmake`, `uv`) and every step to a flashed unit: [BUILDING.md](../docs/guide/BUILDING.md).
- Composing your own: [COMPOSING.md](../docs/guide/COMPOSING.md).
- The remixes that carry one module for its gates: [test/](test/README.md).

## The delay and reverb bus

| remix | contains | proof |
|---|---|---|
| [`octabam-bus`](octabam-bus/README.md) | CORE + the extra ColdFire modules of octabam + the delay and reverb bus (BusDelay on T1's FX2, BusVerb on T5's FX2, SEND on every other track's FX2, the stock DELAY on T8) + SPECTRUM, CHARACTER and MODULATION on FX1. | emulator |

## Firmware mods on the stock effects

| remix | contains | proof |
|---|---|---|
| [`cx-poly`](cx-poly/README.md) | CORE + STEM REC + CX OSC (VOICES=POLY, selector cap 4) + SHATTER + VOID + SCOPE + DARK REV + DELAY + COPY PROJECT + stock COMP. | emulator: CX OSC VOICES=POLY + SHATTER + VOID + SCOPE + DARK + COPY; stock DELAY; stock COMP; port/check only until HW. |
| [`cx-poly-meter`](cx-poly-meter/README.md) | cx-poly with CF METER on T8's FX2 and CF METER IDLE for ColdFire performance measurement; DARK REV omitted to free the meter's DSP words. | emulator: CX OSC VOICES=POLY + CF METER + CF METER IDLE; DARK REV omitted for meter DSP space; port/check only until HW. |
| [`cxosc-core`](cxosc-core/README.md) | CORE + REMIX SWITCH + CX OSC on the 14 stock effects. | emulator: unit handoff: CORE + CX OSC; marker-less machine list, mono, stock LFOs |
| [`octabam`](octabam/README.md) | The core ColdFire modules, SCOPE and TUNER, every other ColdFire module that fits, all 14 stock effects, and SPECTRUM, CHARACTER and MODULATION, loaded on demand, with COMPRESSOR's side-chain. | measured on a unit (OCTA S2, 2026-11-15): Flashed S2 image. With SCOPE closed/open, 30 loader transitions per state had zero bad records. Median CF window peak 537.36/544.96 us, steady 355.77/359.37 us; median DSP window max 49/48%, steady max 49/48%; median audio gap 340/340 ms. Maximum gap 1,480/360 ms. The 40 ms GAP flag appeared on all transitions because the loader silence is about 340 ms. These results cover this flashed image and transition set. |
| [`octabam-verbs`](octabam-verbs/README.md) | octabam with VERBERATION and its PLATE, ROOM and HALL rows in place of PLATE REV, SPRING REV and DARK REV: the core ColdFire modules and every other ColdFire module that fits, the 11 other stock effects, and SPECTRUM, CHARACTER, MODULATION, SHATTER and COMPRESSOR's side-chain loaded on demand, with VIBRATO, TRANSIENT and RESONATOR resident in the reverbs' words. | emulator: not flashed; `make check` (CI) |

Never share a built image: it contains Elektron's OS.
