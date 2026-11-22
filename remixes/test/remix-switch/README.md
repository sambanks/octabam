# `remix-switch` — boot another OS image from the card

BRAIN, REMIX SWITCH and the stock effects. For anyone who wants to move between builds, or back to stock, without reflashing.

## What is in it

- **BRAIN** — the settings store; its MAIN MENU pane carries REMIX SWITCH's list. `modules/brain/README.md`.
- **REMIX SWITCH** — MAIN MENU > BRAIN lists the `.RMX` files (raw OS images: `make rmx`, `make rmx-stock`) in `/BRAIN/REMIXES/` and boots the one picked. Nothing is written to the flash; a power-cycle comes back to this image. `modules/remix-switch/README.md`.
- the 14 stock FX2 effects, listed so the chooser is stock's (REMIX SWITCH's DSP park is in dead interrupt vectors and takes no effect's words).

## Build

```bash
make image REMIX=remix-switch BUILD=1    # -> out/OCTATRACK_OCTABAM1.bin: flash this once
make rmx-stock                        # -> out/STOCK140.RMX
make rmx REMIX=remix-switch RMX=HOME     # -> out/HOME.RMX: this image as a target (the retention check)
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=remix-switch` runs every gate first.
