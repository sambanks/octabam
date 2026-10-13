# `direct-jump` — DIRECT JUMP

A pattern change lands at the next step instead of at the pattern's end,
the Analog Four / Rytm direct jump: CHAIN AFTER's unused value 1 becomes
DIRECT. Built from
[timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules)
(submodule `upstream/`, pinned to `v2.14` (`39dc5d8`)). `Kind.CF_PATCH`: one floating ROM
cave on the pattern-queue setter and the tick handler, four fixed pokes (step and label table entries, the menu setter, the project loader). No DSP code, no menu row of its
own (the option appears in PROJECT > CONTROL > SEQUENCER > CHAIN AFTER as
option 2, between PAT.LEN and 2/16).

A pattern chosen while the sequencer runs ([PATTERN] + [TRIG], [BANK] +
[TRIG], MIDI program change) takes over at the next step boundary, at the
step count the old pattern had reached, instead of at the old pattern's end
or after its CHAIN AFTER length -- the Analog Four / Analog Rytm direct
jump. Off by default: DIRECT is a position of a setting every project
already stores, so a project that never selects it plays exactly as stock.
`upstream/direct-jump/README.md` is the full description, with what was
measured (audio-measured hand-over timing, 26 Sep 2026) and what was
inferred.

## Measured

- At `v9.1`, remixes `octatrick` and `octatrick-usb` built byte-identical
  with the module sources as a plain `modules/<name>/` directory and as this
  wrapper over the submodule (same base, same build reports), and
  byte-identical to the OCTATRICK9 images Tim flashed (built on
  upstream `0e93543`; upstream's changes since touch modules these
  remixes do not carry).
- `v2.9` (29 Sep 2026) leaves this module's sources as they were at `v9.1`
  (the cave links to the same 358 bytes); the quantizer's move into DRAM at
  2.9 frees the ROM zero run, so the cave fits beside SCALE QUANTIZER and
  CF METER's descriptor clone again (at 2.8 it did not).
- `v2.10`, `v2.11`, `v2.12`, `v2.13` and `v2.14` (8 - 13 Oct 2026) leave
  the sources as they were at `v9.1` too.

## On the unit

- 26 Sep 2026: `OCTATRICK9` (remix `octatrick-usb`) on Tim's Octatrack MKI.
- Every test build since, 2.3 .. 2.8, flashed on the same MKI from Tim's
  own tree ([timhastie/octatrick](https://github.com/timhastie/octatrick),
  the same wrappers over the same submodule), and the 2.9 line up to the
  build before its last two fixes. The 2.9 image with the last two fixes is
  emulator-verified on `octatrick` (`make check` on this tree).

## How it is built

Source: `upstream/` is Tim's repository (submodule, pinned to `v2.14` (`39dc5d8`)).
Nothing inside `upstream/` is edited here. The manifest here
(`manifest.py`) executes `upstream/direct-jump/manifest.py` from the source
on disk and re-exports its `MODULE`; that manifest derives its source paths
from its own directory, so the same file builds at `modules/direct-jump/`
in Tim's tree and at `modules/direct-jump/upstream/direct-jump/` here. The
cave's ratified bytes (`pinned`) are re-linked from `direct_jump.s` and
compared on every build.

## Updating

Bump the submodule pin; the pinned bytes either re-link or the build
refuses.
