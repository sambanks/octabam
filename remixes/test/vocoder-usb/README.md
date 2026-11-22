# `vocoder-usb` -- VOCODER with USB audio out

The [`vocoder`](../vocoder/README.md) remix plus USB (TRACKS PRE, MAIN, CUE; IN OFF), for recording a VOCODER performance over USB: each track post-FX and pre-fader on channels 1-16 (a vocoded track on its own pair), MAIN on 17-18 (after the track levels, the crossfader and the scenes), CUE on 19-20.

## What is in it

- **VOCODER** -- [`modules/vocoder/README.md`](../../../modules/vocoder/README.md), with the same stock effects as the `vocoder` remix (all but PLATE REV and DJ EQ).
- **USB**, TRACKS PRE, MAIN and CUE on, IN OFF -- [`modules/usb/README.md`](../../../modules/usb/README.md). USB MIDI and the audio out, ColdFire code in DRAM: no DSP words, no DSP cycles.

## Build

```bash
make check REMIX=vocoder-usb
make image REMIX=vocoder-usb BUILD=<n>
```
