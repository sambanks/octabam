# octabam-verbs

[`octabam`](../octabam/README.md) with [VERBERATION](../../modules/verberation/README.md) in place of the three
stock reverbs. Everything else is octabam's: the core ColdFire modules, every other ColdFire module that fits,
the 11 other stock effects, and SPECTRUM, CHARACTER, MODULATION, SHATTER and COMPRESSOR's side-chain loaded on
demand into the DSP's shared window. Where octabam promises that every stock effect stays and works as stock,
this remix does not.

## The reverbs

| effect | FX1 | FX2 | id | |
|---|---|---|---|---|
| VERBERATION | | ✓ | 0x1a | rooms to halls with a desk-style gate; page 2 SIZE, LCUT, MOD, RATE, PRE |
| PLATE REV, SPRING REV, DARK REV | | | 0x14, 0x15, 0x16 | off both choosers; a Part that still selects one plays that slot dry |

- **The stock reverbs are given up.** Off both choosers, their DSP code is harvested: VERBERATION's 644 words go
  over PLATE's code and part of SPRING's, which points those two ids at the firmware's null stub (NONE's).
  DARK REV's code survives, and stock DARK on T3, T4, T7 or T8 writes to slot offset `0x3da2`, over the demand
  homes at `0x3820` and, on T7, DLCOPY; `Remix.dry` points its id at the null stub too. The build report says
  `DARK REV: code untouched, but Remix.dry -- dispatch nulled` and `donor ids (PLATE/SPRING/DARK REV) -> null stub`
  on both payloads.
- **No reverb guard.** In octabam the stock reverbs run behind a guard (`window_guard`, `modules/dlcopy/dlwrap.asm`)
  and the choosers refuse a reverb over loaded code, with a toast. Here nothing reaches the homes: VERBERATION's ring
  ends at slot offset `0x381d` (14,366 words; the tank was shortened by 0.9 for this, 6 Nov 2026), the other stock
  effects stop by `0xbff`, MODULATION's FX2 buffer is 2,048 words. So VERBERATION can sit on any track's FX2 beside
  any loaded effect, and the guard, its trampolines and the reverb toasts are not built.
- **Cost.** VERBERATION counts 247 cycles a sample, an estimated 8.8 % of a core a slot (scaled from GATE VERB's
  unit reading), under the 9.07 % that lets it sit on all eight FX2 slots. Not read on a unit.

The demand loader, the core modules and the ColdFire modules are octabam's; its README describes them.

## Where it has run

Not flashed. `make check REMIX=octabam-verbs` in CI.
