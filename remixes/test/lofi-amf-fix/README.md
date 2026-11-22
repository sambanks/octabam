# `lofi-amf-fix` — The LO-FI AMF fix alone

Two DSP words. No cave, no menu row.

## What is in it

- **LOFI AMF FIX** (Bryan T, [octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt)) — stock LO-FI's AMF knob jumps the pitch backwards at some settings because its coefficient multiply is `mpysu` (signed × unsigned) where both operands are magnitudes; two DSP words become `mpyuu`.

## Build

```bash
make image REMIX=lofi-amf-fix BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=lofi-amf-fix` runs every gate first.
