# `processor-load` — PROCESSOR LOAD

The ColdFire's audio-interrupt load in the stock TEMPO popup, built from
[timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules)
(submodule `upstream/`, pinned to `v2.14` (`39dc5d8`)). `Kind.CF_PATCH`: one
DRAM unit (`loadmeter.s`), four detours and one poke. No ROM cave, no DSP
code, no FX2 row. Standalone: it needs no other module and nothing on a
computer.

Press TEMPO: the popup's top left corner shows `47%`, the mean share of real
time spent in the audio frame interrupt over the last quarter second, timed
on DMA timer 3 at CF METER's two frame-interrupt sites; `!` from 70 %,
`--%` without a fresh reading; with FUNC held `W112`, the longest single
block of the quarter second in % of one block's 362.8 us. The TEMPO header
sits two pixels lower to leave the number its band; the BPM, tap tempo and
the keys are stock. It runs its own UI tick and arms itself from the stock
startup flag. What it measures, the window, what the number means and what
it cannot see (the DSPs, the UI, the card, USB):
`upstream/processor-load/README.md`.

## Measured

On the ColdFire port (the pinned `ot_emu`, 8 Oct 2026), alone on the stock
effects and in `octatrick`; emulator readings and instruction counts, not
what a unit reads (`upstream/processor-load/README.md`, "Tests and
measurements"):

- It arms in the audio block after the stock startup flag (1.7 samples
  later) and reads from its second window on; `36%` stopped and `42%`
  playing on the author's project; FUNC held while playing
  `W56`; `--%` / `W--` within three quarters of a second when no block is
  counted (a fault forced in emulator memory).
- The UI loop reaches the meter's site 60 times a second, stopped and
  playing, as on the stock OS.
- Cost: 12 + 17 instructions an audio block (the entry and exit stamps),
  plus its UI tick.
- The plain module directory and this wrapper + `upstream/` layout build
  the same image byte for byte; the ledger refuses it beside CF METER and
  beside TEMPO BUS by name.

## On the unit

- 10 Oct 2026: on Tim's MKI in a Modwerk test image (MAIN OS SHA-256
  `f3ebd1c5...`; `loadmeter.s` byte-identical to `v2.11`'s, the same at
  `v2.12`, `v2.13` and `v2.14`), not in an octabam build: "I dont see any issue with the load
  module. it looks like its working."
- In an octabam build: OCTATRICK 2.14 (`octatrick` at `v2.14`, built by
  his own tree from octabam `6e4aeb76`; MAIN OS SHA-256 `c367d8bc...`,
  byte for byte this tree's `octatrick` bus) on his MKI, 13 Oct 2026: its
  test sheet (which carries the 2.13 sheet's PROCESSOR LOAD item: TEMPO
  shows a percentage) reported working as a whole; no readings were
  recorded.

## How it is built

Source: `upstream/` is Tim's repository (submodule, pinned to `v2.14`
(`39dc5d8`)). Nothing inside `upstream/` is edited here. The manifest here
(`manifest.py`) executes `upstream/processor-load/manifest.py` from the
source on disk and re-exports its `MODULE`; that manifest derives its
source paths from its own directory, so the same file builds at
`modules/processor-load/` in Tim's tree and at
`modules/processor-load/upstream/processor-load/` here. The unit is
`Linked(dram=True)`. The detours: the frame vector's install (an entry
stamp in front of the stock handler), the frame interrupt's epilogue (the
exit stamp), the UI task's type-1 message path (the meter's tick) and the
TEMPO popup's draw (the overlay); the poke moves the header down.

## Collisions

Declared, so the ledger refuses each pair by name: CF METER (the same two
frame-interrupt sites: one timer at a time) and TEMPO BUS (both draw the
TEMPO popup). LOAD METER (main, since 11 Oct) detours the same frame
interrupt epilogue (`0x4000d9a6`); the ledger refuses that pair on the
site.

## Updating

Bump the submodule pin (the same commit as the other Octatrick wrappers)
and rebuild; the hook sites are read from the image and the build refuses
on a difference.
