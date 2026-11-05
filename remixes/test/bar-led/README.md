# `bar-led` -- BAR LED

One ColdFire module by Nathan Groth and the stock effects: the remix
`verify_bar_led` runs on.

## What is in it

- **BAR LED** -- [`modules/bar-led/README.md`](../../../modules/bar-led/README.md).
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

Not flashed as such. The module's `unit.s` ran on the author's MKI inside a
private remix through REMIX SWITCH (2 Nov 2026) and loaded over USB by
Modwerk's loader (4 Nov 2026); `modules/bar-led/README.md` has both.

## Build

```bash
make image REMIX=bar-led BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `OT_PROJECT=<dir> make check REMIX=bar-led` runs every gate first.
