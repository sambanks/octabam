# `os-switch-trace` — OS SWITCH with a boot trace on MIDI OUT

`os-switch` plus BOOT TRACE, for the hardware bring-up of OS SWITCH. Every boot sends MIDI notes on MIDI OUT as it passes each stage, the DSP upload's record echoes, and a report if the upload stalls; `modules/boot-trace/trace.s` has the table.

## Status

On an MKII, 29 Sep 2026: builds 4-14 found why the boot stopped after a switch (the DSP, three layers: `docs/contributing/FAILURE_MODES.md`); OCTABAM14 switched to its own image and to stock 1.40C with audio and play working. The notes are checked under the port (`verify_boottrace`).

## Build

```bash
make image REMIX=os-switch-trace BUILD=4
make obi REMIX=os-switch-trace OBI=HOME
```

Record MIDI OUT with a MIDI monitor through a DIN interface: a power-on first (the baseline), then a switch.
