# `wavecf-octa303` — WAVE and OCTA-303

Two ColdFire machines in one image: HOOKS gives the track's machine list seven rows, OCTA-303 on row 5 and WAVE
on row 6, and one limit of two machines a Part, counted over both.

## What is in it

- **OCTA303** — the TB-303 machine. `modules/octa303/README.md`.
- **WAVE CF** — the wavetable machine. `modules/wavecf/README.md`.
- the 14 stock FX2 effects.

## Build

```bash
make image REMIX=wavecf-octa303 BUILD=1    # -> out/OCTATRACK_OCTABAM1.bin
```
