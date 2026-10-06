# `input-hold` — INPUT HOLD alone

One ROM-cave unit, nine detours. No DSP code, no menu row.

## What is in it

- **INPUT HOLD** (dougdoesmusic, [README](../../../modules/input-hold/README.md)) — stock mutes the inputs for the length of a project load (the settings reset makes DIR 0 live), plays Part A meanwhile, and drops a THRU or PICKUP carrying the inputs until the new bank is read. Here the output settings, the tempo and the current Part stay as they are until the new project's own values (its input levels included) arrive.

## Status

`verify_input_hold` under the port: a reload, stock vs this image (the module README's table). On the author's MKII in an image with the 14 stock effects (6 Oct 2026); this one-module remix, whose FX2 chooser lists only NONE, is for the gates and has not been flashed.

## Build

```bash
make image REMIX=input-hold BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=input-hold` runs every gate first.
