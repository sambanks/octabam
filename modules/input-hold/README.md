# INPUT HOLD

Useful if you have audio on the inputs and want to load a new project.

Audio through the inputs keeps playing, at its level, while a project loads.
Stock mutes the inputs for the length of LOAD PROJECT, and a THRU or PICKUP
that carries them drops out until the new bank is read.

## What stock does (measured under the port, 1.40C)

LOAD PROJECT (`0x40085336`) calls the empty-project init `0x400909d8` from
`0x4008534c`. In order:

| step | where | what goes live |
|---|---|---|
| the working bank is re-initialised, Parts included | `0x4000fd34` → `0x4000fc78` → `0x40005638` per Part | THRU / PICKUP machines of the current Part gone |
| the settings reset | `0x40025848` | 120 BPM (`0x400258cc`); the factory mixer into the battery-backed copy and live (`0x40025a86`, `memcpy(0x80000020 ← 0x100b1480, 0x4c)`): GAIN 64, DIR AB/CD 0, PHONES_MIX 64, MASTER_TRACK 0, GATE AB/CD 127, INPUT_DELAY_COMPENSATION 0; bank/pattern/Part/track 0 (`0x40025aaa`, then `0x100b14cc → 0x80000000`), so the engine plays Part A |
| (the reset runs twice per load) | | |
| `[SETTINGS]` / `[STATES]` parsed | `0x40087162..0x40087eac` | the new project's levels, tempo, Part |
| the bank reader initialises the working bank again, then reads the file | `0x4008e0e6` → `0x4000fc78` | |
| the current bank's Part applied | `0x400907e4` → `0x40009094` | the Part's machines again |

The frame interrupt sends the live mixer bytes to the DSP every frame (DIR
CD `0x4000d174`, DIR AB `0x4000d1b0`, GAIN `0x4000d18a`/`0x4000d1c6`), and,
while the selected track (`0x461054f8`) is a PICKUP in the current Part,
its input routing (frame words +0x58/+0x5a/+0x5c from the records at
`0x80000c94 + 12·track`, `0x4000d206..0x4000d2a0`); otherwise 8/0/0.

So a project with its inputs up (DIR 127) is silent from the reset to the
parse, and one whose inputs also pass through a THRU or PICKUP in a Part
other than A is ~3 dB down (two paths to one) from the reset to the Part
apply: on the author's unit, from the start of the loading bar to ~75 %.
Tempo-synced effects jump with the 120 BPM.

A normal power-up does not take this path: it restores the saved state
from the battery-backed copy (`0x4001fb78` → `0x40025770`) and reads no
project.work (`--cs1-in` + `--no-post`).

## What INPUT HOLD changes

One ROM-cave unit (`hold.s`, 462 B), nine detours, no DSP code, no menu.

- **The reset** (`0x40025a80`, the `lea` before the memcpy): the live
  output block (`0x8000002e..37`: GAIN CD/AB, DIR CD/AB, PHONES_MIX,
  MAIN_TO_CUE, MASTER_TRACK, MAIN/CUE LEVEL, CUE_STUDIO_MODE;
  `0x80000058..5a`: GATE AB/CD, INPUT_DELAY_COMPENSATION) is written over
  the defaults in the copy first, so the memcpy writes back what is live.
  The current Part is not zeroed (`0x40025aaa`) and 120 BPM is not set
  (`0x400258cc`).
- **The working bank** (`0x4000fcd4`, the live-Part init in `0x4000fc78`):
  from LOAD PROJECT's empty-project init (`0x4008534c` only: CREATE EMPTY
  PROJECT and the other callers are stock) to the Part apply, the live
  block of the Part that was current when the load started is not
  initialised, in either init, so it plays on until the bank file
  replaces it. Every other Part, the saved copies and the patterns are
  initialised as stock.
- **The pickup's input routing** (`0x4000d206`, `0x4000d2a0`): from the
  reset to the Part apply, and after it until stock reads a pickup track
  again (≤ 2,000 frames), the frame words last sent are resent. Ceiling:
  55,000 frames (~20 s) if a load never reaches its Part apply.
- **The parse is stock**: `[SETTINGS]` and `[STATES]` apply the new
  project's input levels, tempo, Part, master track, phones… as stock, once,
  without the load passing through the defaults first. Same levels in both
  projects: nothing moves; different levels: one change, when the project
  is read.
- **When it holds:** from the first reset after boot, which runs as stock
  (empty battery memory: the live block is not yet valid there), or at
  once after a normal power-up (`0x4001fb78`). Latched per load at the
  reset.

## Measured under the port (`verify_input_hold`)

A reload of a project with Part B current, T5 THRU in Part B, inputs on C/D:

| | stock | INPUT HOLD |
|---|---|---|
| current Part | B → A → B | B throughout |
| T5's track record (`0x80000210..`) | rewritten at the reset, back at the Part apply | unchanged |
| DIR CD / MASTER_TRACK / PHONES_MIX | 127→0→127 / 1→0→1 / 0→64→0 | unchanged |
| tempo word | → 0x0b40 → back | unchanged |
| working bank and `0x80000000..15` at the end | — | equal to stock's |

Under the port the main output does not follow the mixer bytes
(`tools/emu/README.md`, the voice-silence entry), so what is checked is what
the frame interrupt sends, not audio.

## On the unit

The author's MKII, 6 Oct 2026, with the 14 stock effects: a reload of a
project whose inputs pass through DIR CD and a THRU in Part B: no dropout,
no level dip, no FX jump.

## Open

- A bank file that fails to load (PARSE ERROR, a missing file) leaves the
  kept Part in the new project instead of an empty one. Don't save over it.
- Placement: ROM cave (462 B of the ~8.4 KB shared), not DRAM, because no
  other part needs the platform runtime and DRAM costs the unit 10 MB of
  sample memory. Movable to `dram=True` with no other change.

## Gates

`make check REMIX=input-hold` with `OT_PROJECT` set: `verify_input_hold`
(stock vs the image, a reload under the port, about 10 minutes; SKIP
without `OT_PROJECT`).
