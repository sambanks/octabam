# `os-switch` — boot another OS image from the card

One ColdFire module and the stock effects. For anyone who wants to move between builds, or back to stock, without reflashing.

## What is in it

- **OS SWITCH** — MAIN MENU > CONTROL > OS SWITCH boots a `.OBI` (a raw OS image: `make obi`, `make obi-stock`) from the card root. Nothing is written to the flash; a power-cycle comes back to this image. `modules/os-switch/README.md`.
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

Measured under the ColdFire port (`python3 tools/verify/verify_osswitch.py os-switch`): the menu row, the load, the reset sequence, the chainload of the staged image, every refusal. Not yet run on a unit. The reset, SDRAM across it and the DSP after it are the hardware checks, listed in the module README.

## Build

```bash
make image REMIX=os-switch BUILD=1    # -> out/OCTATRACK_OCTABAM1.bin: flash this once
make obi-stock                        # -> out/STOCK140.OBI
make obi REMIX=os-switch OBI=HOME     # -> out/HOME.OBI: this image as a target (the retention check)
```

[BUILDING.md](../../../docs/remixes/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=os-switch` runs every gate first.
