# `core` — the rig with CORE

bottleservice's selection plus CORE: card-wide knob defaults read from
`OCTABAM/card.work` at each project load, and SAVE AS DEFAULT / CLEAR
DEFAULT in the OCTABAM category of the MAIN MENU.

## What is in it

- Everything in [bottleservice](../../bottleservice/README.md).
- **CORE** — `modules/core/README.md`. On the panel: PROJ, the OCTABAM
  category (fifth), its heading (the remix and build tag), SAVE AS
  DEFAULT, CLEAR DEFAULT. Open it over an FX1 or FX2 page of an audio
  track: the page in view is the one saved or cleared.

## Status

`tools/verify/verify_core.py` under the port. Not run on hardware.

## Build

```bash
make image REMIX=core BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```
