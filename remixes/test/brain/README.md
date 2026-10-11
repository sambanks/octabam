# `brain` — the rig with BRAIN

bottleservice's selection plus BRAIN: card-wide knob defaults read from
`BRAIN/card.work` at each project load, and SAVE AS DEFAULT / CLEAR
DEFAULT in the BRAIN category of the MAIN MENU.

## What is in it

- Everything in [bottleservice](../../bottleservice/README.md).
- **BRAIN** — `modules/brain/README.md`. On the panel: PROJ, the BRAIN
  category (fifth), its heading (the remix and build tag), SAVE AS
  DEFAULT, CLEAR DEFAULT. Open it over an FX1 or FX2 page of an audio
  track: the page in view is the one saved or cleared.

## Status

`tools/verify/verify_brain.py` under the port. Not run on hardware.

## Build

```bash
make image REMIX=brain BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```
