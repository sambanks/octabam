# `kits` — KITS

255 Kits per project on the stock effects.

## What is in it

- **KITS** (sambanks) — a library of 255 Parts per project; each pattern plays its Kit through the stock Part slots. PART = LOAD KIT, FUNC+PART = SAVE KIT (MKI: FUNC+MIDI, then FUNC+BANK).

## Build

```bash
make image REMIX=kits BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=kits` runs every gate first.
