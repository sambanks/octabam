# `buffer-saver` — BUFFER SAVER on the stock effects

One ColdFire module and the stock effects. For anyone who has lost recorder takes by saving the project without saving the buffers.

## What is in it

- **BUFFER SAVER** — SAVE PROJECT (and FUNC + PROJ) asks SAVE SAMPLES? when a recorder buffer holds a take not yet saved. YES saves each to the card under stock's automatic name (`-2`, `-3` … when taken), assigned to itself, then saves the project. NO saves the project as stock. [`modules/buffer-saver/README.md`](../../../modules/buffer-saver/README.md).
- **ATA WRITE GUARD** — closes stock's first-sector card-write race, which hung the gate's project saves under the port when a build shifted the timing (as in the official remixes).
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Build

```bash
make image REMIX=buffer-saver BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=buffer-saver` runs every gate first.
