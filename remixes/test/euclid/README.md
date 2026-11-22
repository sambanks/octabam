# `euclid` — EUCLID on both choosers

Jannik Aßfalg's (repeat98) Euclidean modulation effect with the stock effects that do not allocate an instance buffer.

## What is in it

- **EUCLID** — a 1–64-step Euclidean rhythm on the transport's grid (track speed and swing followed) driving one of five destinations: 12 dB/octave low-pass, band-pass, high-pass, notch, or amplitude; envelope, gate, random and loop controls. On FX1 and FX2. `modules/euclid/README.md`.
- FILTER, EQUALIZER, DJ EQ, PHASER, COMPRESSOR, LO-FI on both choosers; PLATE, SPRING and DARK REV on FX2. SPATIALIZER, FLANGER, CHORUS and COMB FILTER are given up.

## Build

```bash
make image REMIX=euclid BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=euclid` runs every gate first.
