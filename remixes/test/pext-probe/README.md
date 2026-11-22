# `pext-probe` -- PEXT PROBE

PEXT PROBE on FX1 with USB audio out (TRACKS PRE), beside the stock effects: EQUALIZER's id is the probe's and PLATE REV and SPRING REV give up their words. One measurement run on a unit: where a DSP core can keep code besides its stock P memory (P above `P:0x2000`, and code in the shared window).

## What is in it

- **PEXT PROBE** -- [`modules/pextprobe/README.md`](../../../modules/pextprobe/README.md): the ladder, the results, the procedure.
- **USB** -- TRACKS PRE, no MAIN, CUE or MASTER, IN off: the 16 track channels are what the capture reads.
- the stock effects but EQUALIZER, PLATE REV and SPRING REV.

## Build

```bash
make check REMIX=pext-probe
```
