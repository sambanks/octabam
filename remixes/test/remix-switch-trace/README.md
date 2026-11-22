# `remix-switch-trace` — REMIX SWITCH with a boot trace on MIDI OUT

`remix-switch` plus BOOT TRACE, for the hardware bring-up of REMIX SWITCH. Every boot sends MIDI notes on MIDI OUT as it passes each stage, the DSP upload's record echoes, and a report if the upload stalls; `modules/boot-trace/trace.s` has the table.

## Build

```bash
make image REMIX=remix-switch-trace BUILD=4
make rmx REMIX=remix-switch-trace RMX=HOME
```

Record MIDI OUT with a MIDI monitor through a DIN interface: a power-on first (the baseline), then a switch.
