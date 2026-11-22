# octabam-verbs

[`octabam`](../octabam/README.md) with [VERBERATION](../../modules/verberation/README.md) in place of the three
stock reverbs. Everything else is octabam's: the core ColdFire modules, every other ColdFire module that fits,
the 11 other stock effects, and SPECTRUM, CHARACTER, MODULATION, SHATTER and COMPRESSOR's side-chain loaded on
demand into the DSP's shared window. VIBRATO, TRANSIENT and RESONATOR are resident in the reverbs' words. Where octabam promises that every stock effect stays and works as stock,
this remix does not.

## The reverbs

| row | FX1 | FX2 | id | |
|---|---|---|---|---|
| VERBERATION | | ✓ | 0x1a | rooms to halls with a desk-style gate; MODE (ROOM, PLATE, HALL, GATED), LCUT, MOD, RATE, SIZE, PRE on page 2 |
| VERB PLATE | | ✓ | 0x14 (PLATE REV's) | VERBERATION with MODE set to PLATE: a second row, not a second reverb |
| VERB ROOM | | ✓ | 0x15 (SPRING REV's) | VERBERATION with MODE set to ROOM |
| VERB HALL | | ✓ | 0x16 (DARK REV's) | VERBERATION with MODE set to HALL |

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

## Three more effects, resident

The stock reverbs' harvested words (2,724 a payload) hold more than VERBERATION. Three effects sit beside it there,
always in the upload and reached by id like a stock effect, so the demand loader and its window layout are octabam's
unchanged. With them, 559 words are free on payload A and 588 on payload B (`make bus`). octabam keeps every stock
effect and has no such words; octabam-bus's internal P is 584 words short of VIBRATO alone.

| effect | FX1 | FX2 | words | cost a slot | |
|---|---|---|---|---|---|
| [VIBRATO](../../modules/vibrato/README.md) | ✓ | ✓ | 593 + 103 table | 4.5 % (Bryan T's MKII) | pitch vibrato: sine, triangle, square trill, random; `SLOTS` at `FX1+FX2` |
| [TRANSIENT](../../modules/transient/README.md) | ✓ | ✓ | 258 + 99 table | 5.3 % (`slot_costs.json`) | transient shaper |
| [RESONATOR](../../modules/resonator/README.md) | ✓ | | 373 + 66 table | not measured | four resonant band-passes; FX1 only |

FX1 lists SPECTRUM, CHARACTER, MODULATION, VIBRATO, TRANSIENT, RESONATOR, then the stock effects (17 rows).
Not read together with VERBERATION on a unit.

The demand loader, the core modules and the ColdFire modules are octabam's; its README describes them. SCALES,
CHORDS FACTORY with PAGES, SCREEN, SLOW LFO, BAR LED and REC CS1 SKIP are here as in octabam.

## Where it has run

Sam's MKII, 22 Nov 2026, `OCTABAM-VRB 05` built from `main` at `382a478b` plus the v0.5 release commit and booted by REMIX SWITCH
from the flashed image (not flashed itself): `pre-meter`, `pre-transport`, `pre-usb` and `dsp-watch` pass; 32 program changes between
MODULATION FX2 dear, SPECTRUM FX2 dear and BASE: 0 unapplied, longest silence 340 ms, longest ColdFire run 515 us, and 32 bad DSP records
(1 per transition, at the load of the `dear` layouts, which run the DSP at 84 % and 75 %; `octabam`'s MODULATION dear logs the same).
On the earlier BUILD 05 (`5b991c85`) `fx01` to `fx04` (VERBERATION in each MODE, VERB PLATE, ROOM and HALL), `loader01` and `loader02`,
`kits-identity`, `scenes-sweep`, `scenes-latency` and `djump-off` ran. Not run: `djump-on`, `djump-burst` and `mix-soak`. The DARK REV
stall of `octabam` needs the stock DARK REV, which this remix does not carry; it was not run here to confirm.

`make check REMIX=octabam-verbs` in CI. Under the port: `verify_verb_parts` (old Parts convert),
`verify_dlload`'s no-guard checks (MODULATION loads in its first home with DARK's id or VERBERATION on its block's
track, no toast; on a generated empty project, which the gate otherwise skips: 2 of its other checks fail there, as
it documents for such projects).
