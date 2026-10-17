# `bbd` -- BBD

BBD beside 12 stock effects (all but SPRING REV and PLATE REV, whose words it takes).

## What is in it

- **BBD** -- [`modules/bbd/README.md`](../../../modules/bbd/README.md).
- the stock effects but SPRING REV and PLATE REV, listed so the chooser is otherwise stock's. DARK REV stays: BBD is placed clear of the SPRING REV words it calls.

## Status

Flashed as BBDOB4 (`make image REMIX=bbd BUILD=4`) on JamCones' MKII, 17 Oct 2026: DARK REV, BBD on T1 and T5 behind FILTER and PHASER, LFOs, SETUP, the stop kill, save, reload and a power cycle (`modules/bbd/README.md`).

## Build

```bash
make check REMIX=bbd
```
