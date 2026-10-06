# `core` — the rig with CORE

bottleservice's selection without FX2 LOCK, plus CORE: card-wide knob
defaults read from `OCTABAM/card.work` at each project load.

## What is in it

- Everything in [bottleservice](../../bottleservice/README.md) except FX2
  LOCK, so the FX2 chooser can change T2's effect for the gate.
- **CORE** — `modules/core/README.md`.

## Status

`tools/verify/verify_core.py` under the port. Not run on hardware.

## Build

```bash
make image REMIX=core BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```
