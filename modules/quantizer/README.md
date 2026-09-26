# SCALE QUANTIZER

A SCALE row and a GLIDE row in PROJECT > CONTROL > SEQUENCER, built from
[timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules)
(submodule `upstream/`, pinned to `v9.1`). `Kind.CF_PATCH`: four ROM units
(`glide.s`, `keys.s`, `quantizer.s`, `scale.s`), detours, pokes and a
`TableGrow` for the menu rows. No DSP code, no FX2 row.

## What it does

SCALE (OFF, then 24 scales): the PTCH knob on the PLAYBACK page of a
STATIC / FLEX / PICKUP track steps to the next scale degree, on the Part's
value and on a step's lock; a [TRIG] key in CHROMATIC trig mode snaps to the
nearest degree before it becomes the pitch the voice, the recorded lock and
the screen see. GLIDE (OFF, 1..127): the synth's glide time and 303-style
legato on the chromatic keys; polyphonic chromatic keys on a synth track
whose VOIC is 2..4. Live recording on a synth track writes the played note
length as an AMP HOLD lock. `upstream/quantizer/README.md` is the full
description, with what was measured and what was inferred.

## How it is built

Source: `upstream/` is Tim's repository (submodule, pinned to `v9.1`).
Nothing inside `upstream/` is edited here. The manifest here
(`manifest.py`) executes `upstream/quantizer/manifest.py` from the source on
disk and re-exports its `MODULE`; that manifest derives its source paths
from its own directory, so the same file builds at `modules/quantizer/` in
Tim's tree and at `modules/quantizer/upstream/quantizer/` here. The glide
byte, the key trampoline and the scale trampoline are at pinned addresses
(`GLIDE_AT`, `KEYS_AT`, `SCALE_AT`) that SYNTH MACHINE's engine reads; the
main unit floats.

## Measured

- Remixes `octatrick` and `octatrick-usb` build byte-identical with the
  module sources as a plain `modules/<name>/` directory and as this
  wrapper over the submodule (same base, same build reports), and
  byte-identical to the OCTATRICK9 images Tim flashed (built on
  upstream `0e93543`; upstream's changes since touch modules these
  remixes do not carry).
- **On hardware 26 Sep 2026** as `OCTATRICK9` (remix `octatrick-usb`) on
  Tim's Octatrack MKI.

## Updating

Bump the submodule pin and rebuild; SYNTH MACHINE reads the three pinned
addresses, so a pin that moves them needs both modules bumped together.
