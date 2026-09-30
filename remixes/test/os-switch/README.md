# `os-switch` — boot another OS image from the card

One ColdFire module and the stock effects. For anyone who wants to move between builds, or back to stock, without reflashing.

## What is in it

- **OS SWITCH** — MAIN MENU > CONTROL > OS SWITCH boots a `.OBI` (a raw OS image: `make obi`, `make obi-stock`) from the card root. Nothing is written to the flash; a power-cycle comes back to this image. `modules/os-switch/README.md`.
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

Measured under the ColdFire port (`python3 tools/verify/verify_osswitch.py os-switch`): the menu row, the load, the reset sequence, the chainload of the staged image, every refusal, the DSP park and re-upload. On a unit: the same modules plus BOOT TRACE (`os-switch-trace`, OCTABAM14, an MKII, 29 Sep 2026) switched to its own image and to stock 1.40C, audio and play working. This remix without the trace has not run on a unit; the two differ only by BOOT TRACE's detours.

## Build

```bash
make image REMIX=os-switch BUILD=1    # -> out/OCTATRACK_OCTABAM1.bin: flash this once
make obi-stock                        # -> out/STOCK140.OBI
make obi REMIX=os-switch OBI=HOME     # -> out/HOME.OBI: this image as a target (the retention check)
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=os-switch` runs every gate first.
