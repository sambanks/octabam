# `buffer-saver` — BUFFER SAVER on the stock effects

One ColdFire module and the stock effects. For anyone who has lost recorder takes by saving the project without saving the buffers.

## What is in it

- **BUFFER SAVER** — SAVE PROJECT (and FUNC + PROJ) asks SAVE SAMPLES? when a recorder buffer holds a take not yet saved. YES saves each to the card under stock's automatic name (`-2`, `-3` … when taken), assigned to itself, then saves the project. NO saves the project as stock. [`modules/buffer-saver/README.md`](../../../modules/buffer-saver/README.md).
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

Working on an MKII (Chupitnik's, 15-16 Oct 2026): images AUTOSAVE1 and AUTOSAVE2 from this remix under the module's first name, flashed from the card. Measured under the ColdFire port by `tools/verify/verify_buffer_saver.py` (in `make check`). Also on the MKII (16 Oct): a save while a pattern plays, and a full card (stock's CARD FULL error, no freeze). Not yet tried: an MKI. `CHANGELOG.md` has each image.

## Build

```bash
make image REMIX=buffer-saver BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=buffer-saver` runs every gate first.
