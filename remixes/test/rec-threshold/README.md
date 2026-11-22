# `rec-threshold` — REC THRESHOLD on the stock effects

One ColdFire module and the stock effects. For anyone who wants a recorder to start by itself when the input gets loud, like the Digitakt 2's threshold recording.

## What is in it

- **REC THRESHOLD** — a fourth recorder TRIG value, `THR`. TRACK + REC on an idle recorder arms it; the take starts on the first frame where any of inputs A–D passes the track's LEV. A second press while armed cancels; a press while recording stops it. On a THR track RECORDING SETUP 2 shows **LEV** (the threshold, −60 to 0 dB, in QREC's cell, saved with the Part; −40 when TRIG is first set to THR) and **IN** (the live input level, in QPL's cell). [`modules/rec-threshold/README.md`](../../../modules/rec-threshold/README.md).
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Build

```bash
make image REMIX=rec-threshold BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=rec-threshold` runs every gate first.
