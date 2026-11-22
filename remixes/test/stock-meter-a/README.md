# `stock-meter-a` -- LOAD METER with the stock effects

CORE (as `octabam`) with LOAD METER and the stock effects except PHASER, whose 207 words (13 free after the meter's 194 on payload A) hold the meter's DSP half. `stock-meter-a` and `stock-meter-b` together list all 14 stock effects with the meter, so each stock effect's slot cost can be read on a unit (`tools/hw/ot_matrix.py`, on `hw/usb-standalone-transport`).

## What is in it

- CORE and LOAD METER, as in `octabam`.
- 13 stock effects, FX1 chooser listed explicitly (a remix that names no FX1 effects keeps every stock FX1 effect and nothing is harvested).

## Build

```bash
make check REMIX=stock-meter-a
```
