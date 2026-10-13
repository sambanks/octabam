# `sy-drum` — SY DRUM

A drum machine in the track's machine list (the row after FM SYNTH), built
from [timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules)
(submodule `upstream/`, pinned to `v2.14` (`39dc5d8`)). `Kind.CF_PATCH`: one
DRAM unit (`sydrum.s`, on SYNTH MACHINE's engine: `requires=("SYNTH
MACHINE",)`), a 2 MiB `DramRegion` for the step locks, 53 detours. No ROM
cave, no DSP code, no FX2 row.

SY DRUM is modelled on the 1979 Pearl Syncussion SY-1, written from a study
of that unit's circuit. It is not affiliated with or endorsed by Pearl or
Behringer. Syncussion is a trademark of its owner.

One voice a track: two oscillators, a sweep, a two-pole low-pass filter
opened by the decay envelope, six modes. Choose it in SELECT MACHINE TYPE
(the track key twice, `<< MACHINE`, DOWN to `SY DRUM`: the seventh row, the
window scrolls) or in SRC SETUP (FUNC + PLAYBACK); no sample and no marker
file. The PLAYBACK page reads PTCH MODE WDTH SWEP SPED DEC (the FLEX
PLAYBACK bytes, so stock p-locks, the three LFOs and scenes reach them); the
PLAYBACK SETUP page holds a dedicated LFO / S&H (LSPD LDEP WAVE S&H), each
control lockable per step in GRID and LIVE RECORDING. The locks follow copy /
paste / clear / shift and are saved in `sylockNN.work` / `.strd` beside the
project's banks, only for banks that hold a lock. Since 2.14 the working
files (`.work`) are also written while the sequencer plays (at most once
every 60 UI ticks, and only while a lock edit is unwritten), so a power-off
without SAVE PROJECT keeps the step locks as it keeps stock's, but for an
edit made less than about 1.2 s before it; and they are read whenever a
project loads, also when one of its stock bank files is missing or
damaged. The track is stored as
FLEX with `S`, `Y`, 1 in its NEIGHBOR column (SYNTH MACHINE's machine-list
mechanism); a build without SY DRUM reads it as a silent FLEX track. The
quantizer treats a SY DRUM track as a synth track (semitone PTCH, the
CHROMATIC keys, MIDI), mono. Since 2.12 (SYNTH MACHINE's `machine.s`) a
machine change to or from SY DRUM resets the track's machine parameters
(PLAYBACK, PLAYBACK SETUP, AMP, LFO and their SETUP pages) to the new
machine's init; step and scene locks, SY DRUM's lock rows and FX slots are
kept, as stock keeps its locks. `upstream/sy-drum/README.md` is the full
description (the controls, the locks, how it works, what was measured and
the limits).

## Measured

All on the ColdFire port (the pinned `ot_emu`, 8 - 9 Oct 2026), in the
author's tree and in octabam's `octatrick` remix with SY DRUM; emulator
instruction counts, never hardware percentages
(`upstream/sy-drum/README.md`, "Measured"):

- Sound: batch renders against the author's development build (its
  on-board SY engine), three tracks at once and single tracks: sample for
  sample identical over the whole capture; a project the development build
  saved with a step lock plays identically on both.
- Step locks: one lock changes only its own track's step; GRID and LIVE
  RECORDING, shift, a held trig's clear, a page's copy / paste / undo and
  clear / undo, with the same key presses on this module and on the
  development build: every lock row the same, every screen pixel-identical
  but the machine's name. Not exercised: a held trig's copy / paste, a
  track's or a pattern's copy / paste, a page's duplication.
- Card files: SAVE writes the `sylock` pair of each bank with a lock; a cold
  load, PROJECT > RELOAD and SAVE TO NEW bring them back as the development
  build does; a Part SAVE / RELOAD leaves them alone. EXPORT and DELETE ran
  on the Mac against an in-memory card only.
- Cost: `sd_tick` 588 instructions a frame with no SY DRUM track in the
  Part, 1,620 with one SY DRUM track and a trig on every step, 1,645 with a
  lock on every step; DRAM: the unit 135,715 B (136,061 B at 2.14) and the
  lock table 2 MiB in the platform reserve.

- 2.12 (10 - 11 Oct 2026): `sydrum.s` is the same as at `v2.11`; the
  machine-change init (in SYNTH MACHINE) on every route, the values a new
  project gives a track, SY DRUM's lock rows kept across SY DRUM -> FM
  SYNTH -> SY DRUM, SAVE and a cold boot; five SY DRUM renders identical to
  2.11's sample for sample.
- 2.14 (12 - 13 Oct 2026; octabam's emulator with the battery-backed memory
  carried over the power-off and the unit's power-on load; three SY DRUM
  tracks with Flex samples loaded, new PLAYBACK and PLAYBACK SETUP locks
  on two steps of two of them, no SAVE after the edits): before 2.14, a power-off
  after 10 s of playing, or 0.3 s after STOP, brought back the PLAYBACK
  locks as at the power-off but the PLAYBACK SETUP locks as they were
  before the edits; with
  2.14 every case -- 10 s and 30 s of playing, a pattern change while
  playing, 0.3 s and 2 s after STOP, edits while stopped -- brings both
  back as they were at the power-off (9 of 9). The residue: stopped, a
  power-off 0.3 s after the last edit lost that one edit. A stock bank
  file removed, cut short or damaged: stock's own message, the same before
  and with 2.14; answered NO, the project loads and with 2.14 the step
  locks of every bank load with it (before: none). Cadence: 40 lock edits
  over 12 s of playing wrote WORK ten times, 1.2 s apart, then nothing
  while playing on and nothing at STOP. SAVE / cold load / RELOAD (17 of
  17), the machine-change walks (21 of 21), the LIVE RECORDING and paste
  walks (every lock row and screen as at 2.13) and the lock files' round
  trip (46 of 46): unchanged.

## On the unit

- 10 Oct 2026: the 2.11 module on Tim's MKI in a Modwerk test image with
  FM SYNTH (MAIN OS SHA-256 `b9b65cd9...`), not in an octabam build: "I
  dont see any issues with Modwerk SY DRUM, other than what i mentioned
  before about switching machines and initing parameters" -- the
  machine-change init that 2.12 adds.
- 12 Oct 2026: the module as at `v2.12` / `v2.13` (`sy-drum/` is the same
  at both) in a Modwerk test image (MAIN OS SHA-256 `d0dab5fe...`), not in
  an octabam build: PLAYBACK SETUP locks were sometimes missing after a
  power-off without SAVE PROJECT, while the PLAYBACK locks always came
  back; with SAVE PROJECT every lock came back.
  This is 2.14's first fix.
- 12 Oct 2026, later: `octatrick` built by octabam (`6e4aeb76`, from Tim's
  own tree) with that first fix (the WORK write while playing; MAIN OS
  SHA-256 `05f0e015...`): locks set while playing and a power-off while
  playing, no SAVE: "It saved the LFO parameter locks"; a STATIC track
  streaming from the card while locks were edited: no crackling heard.
- 13 Oct 2026, reported by the author on the same MKI: SY DRUM 0.1.0 with
  FM Synth 0.1.5 in a Modwerk test image (this module at `v2.14`; MAIN OS
  SHA-256 `27c213b2...`, not an octabam build): both rows in both machine
  lists, SY DRUM -> FM SYNTH -> SY DRUM to init with the PLAYBACK SETUP
  locks kept (2.12's init), a held note with the metronome on, a power-off
  without SAVE while playing with the locks kept, two locked tracks through
  a power-cycle after SAVE, a STATIC track streaming while locks were
  edited with no crackle; and OCTATRICK 2.14 (`octatrick` at `v2.14`, built
  by his own tree from octabam `6e4aeb76`; MAIN OS SHA-256 `c367d8bc...`,
  byte for byte this tree's `octatrick` bus), its test sheet (the same
  power-off and STATIC-track checks). Play time and track counts were not
  recorded, nor whether the last edit before an immediate power-off came
  back (the known limit).
- 2.14's second fix (the stock bank file case): emulator only. `sydrum.s` is the same from `v2.11` to `v2.14`; 2.14 changes
  the card code it includes (`locks_io.inc.s`, generated from
  `tools/locks_io.c`).

## How it is built

Source: `upstream/` is Tim's repository (submodule, pinned to `v2.14`
(`39dc5d8`)). Nothing inside `upstream/` is edited here. The manifest here
(`manifest.py`) executes `upstream/sy-drum/manifest.py` from the source on
disk and re-exports its `MODULE`; that manifest derives its source paths
from its own directory and reads SYNTH MACHINE's `synth/engine_abi.inc`
from its sibling, so the same file builds at `modules/sy-drum/` in Tim's
tree and at `modules/sy-drum/upstream/sy-drum/` here. The unit is
`Linked(dram=True)`; its `remix.inc` is generated per remix with SYNTH
MACHINE's shared equates, and SYNTH MACHINE assembles its calls into this
unit and adds the `SY DRUM` row when SY DRUM is in the remix (without it,
SYNTH MACHINE is byte for byte the FM-only engine).

## Collisions

Declared, so the ledger refuses each pair by name: KITS and PLOCKS P2 (the
same card-job, clipboard, lock-queue and held-encoder sites) and STEM REC
(the lock table and STEM REC's buffers are both DRAM regions at the top of
the platform reserve and do not fit it together). It requires SYNTH
MACHINE, which declares the conflict with ANALOG BD (the same machine-list
sites).

## Updating

Bump the submodule pin (the same commit as the other Octatrick wrappers)
and rebuild; the hook sites are read from the image and the build refuses
on a difference.
