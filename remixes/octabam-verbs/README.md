# octabam-verbs

[`octabam`](../octabam/README.md) with [VERBERATION](../../modules/verberation/README.md) in place of the three
stock reverbs. Everything else is octabam's: the core ColdFire modules, every other ColdFire module that fits,
the 11 other stock effects, and SPECTRUM, CHARACTER, MODULATION, SHATTER and COMPRESSOR's side-chain loaded on
demand into the DSP's shared window. Where octabam promises that every stock effect stays and works as stock,
this remix does not.

## The reverbs

| effect | FX1 | FX2 | id | |
|---|---|---|---|---|
| VERBERATION | | ✓ | 0x1a | rooms to halls with a desk-style gate; MODE (ROOM, PLATE, HALL, GATED), LCUT, MOD, RATE, SIZE, PRE on page 2 |
| VERB PLATE | | ✓ | 0x14 (PLATE REV's) | VERBERATION starting in PLATE mode |
| VERB ROOM | | ✓ | 0x15 (SPRING REV's) | VERBERATION starting in ROOM mode |
| VERB HALL | | ✓ | 0x16 (DARK REV's) | VERBERATION starting in HALL mode |

- **The stock reverbs are given up.** PLATE REV, SPRING REV and DARK REV are off both choosers; their DSP code is
  harvested (VERBERATION's 644 words go over PLATE's and part of SPRING's) and their ids are the three rows,
  which run VERBERATION's one copy of code (`MenuEntry.dsp_of`: the build reports `VERB PLATE id 0x14 ->
  VERBERATION's code` on both payloads, and a dump reads one pair of entry points for 0x14, 0x15, 0x16, 0x1a).
- **Old Parts.** A Part saved with a stock reverb opens on its row: [VERB PARTS](../../modules/verb-parts/README.md)
  rewrites its FX2 pages to the row's defaults as the firmware applies it (`verify_verb_parts` under the port).
- **No reverb guard.** In octabam the stock reverbs run behind a guard (`window_guard`, `modules/dlcopy/dlwrap.asm`)
  and the choosers refuse a reverb over loaded code, with a toast. Here nothing reaches the homes: VERBERATION's ring
  ends at slot offset `0x381d` (14,366 words; the tank was shortened by 0.9 for this, 6 Nov 2026), the other stock
  effects stop by `0xbff`, MODULATION's FX2 buffer is 2,048 words. So VERBERATION can sit on any track's FX2 beside
  any loaded effect, and the guard, its trampolines and the reverb toasts are not built.
- **Cost.** VERBERATION counts 247 cycles a sample, an estimated 8.8 % of a core a slot (scaled from GATE VERB's
  unit reading), under the 9.07 % that lets it sit on all eight FX2 slots. Not read on a unit.

The demand loader, the core modules and the ColdFire modules are octabam's; its README describes them.

## Where it has run

Not flashed. `make check REMIX=octabam-verbs` in CI. Under the port: `verify_verb_parts` (old Parts convert),
`verify_dlload`'s no-guard checks (MODULATION loads in its first home with DARK's id or VERBERATION on its block's
track, no toast; on a generated empty project, which the gate otherwise skips: 2 of its other checks fail there, as
it documents for such projects).
