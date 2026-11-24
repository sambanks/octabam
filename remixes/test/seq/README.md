# `seq`

STORE + SEQ and the stock effects.

## What is in it

- **STORE** -- required: SEQ persists settings in `seq.work`.
- **PLOCKS P2** -- required: SEQ page-2 destinations use its storage and playback table.
- **SEQ** -- [`modules/seq/README.md`](../../../modules/seq/README.md).
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Build

```bash
make check REMIX=seq
```
