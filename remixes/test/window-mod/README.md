# `window-mod` -- MODULATION in the shared P window

CORE with LOAD METER, MODULATION and the stock effects except CHORUS (MODULATION takes its id) and the three reverbs (their words hold LOAD METER's DSP half and the CORE modules). MODULATION's code is one 1,561-word copy (including the 148-word table) at P:0x36300, in payload A's half of the shared window, reached from both cores. `window-ctl` is the same set with MODULATION in internal P.

## What is in it

- CORE and LOAD METER, as in `octabam`.
- MODULATION at P:0x36300 (`Remix.window`).
- FILTER, EQUALIZER, DJ EQ, PHASER, FLANGER, SPATIALIZER, COMB FILTER, COMPRESSOR, LO-FI, DELAY.

## Build

```bash
make check REMIX=window-mod
```
