# `vocoder` -- VOCODER

VOCODER beside the stock effects (all but PLATE REV, whose words it takes, and DJ EQ, so its tables sit in X memory). VOCODER runs on FX2 of tracks 2, 4, 6 and 8 only (two per DSP core, the even tracks, not a core's first track) and passes audio elsewhere.

## What is in it

- **VOCODER** -- [`modules/vocoder/README.md`](../../../modules/vocoder/README.md).
- the stock effects but PLATE REV and DJ EQ, listed so the chooser is otherwise stock's: PLATE REV gives up its words for VOCODER's code, and DJ EQ is left out on both menus so VOCODER's tables sit in the stock curve bank in X memory.

## Build

```bash
make check REMIX=vocoder
```
