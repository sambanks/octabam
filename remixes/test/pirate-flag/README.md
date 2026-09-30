# `pirate-flag` — the boot animation as a Jolly Roger

`base` plus one ColdFire module: the gate's remix for PIRATE FLAG.

## What is in it

- **PIRATE FLAG** — the OS's own 2.8 s boot animation replaced by a waving
  Jolly Roger. The bootstrap's logo before it is NOR's and stays.
  `modules/pirate-flag/README.md`.
- OS SWITCH, and the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

Measured under the ColdFire port (`tools/verify/verify_pirateflag.py`,
30 Sep 2026): the detour runs every frame, and frame 280 is the flag bit for
bit. Not on a unit.

## Build

```bash
make obi REMIX=pirate-flag OBI=PIRATE    # -> out/PIRATE.OBI: switch to it to see the flag
```
