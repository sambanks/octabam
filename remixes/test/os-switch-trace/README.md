# `os-switch-trace` — OS SWITCH with a boot trace on MIDI OUT

`os-switch` plus BOOT TRACE, for the hardware bring-up of OS SWITCH. Every boot sends MIDI notes 1..6 on MIDI OUT as it passes each stage; `modules/boot-trace/trace.s` has the table.

## Status

A probe; the notes are checked under the port (`verify_boottrace`). Built to find where the boot stops after a switch on an MKII (build 3: the OCTABAM screen, dim keys).

## Build

```bash
make image REMIX=os-switch-trace BUILD=4
make obi REMIX=os-switch-trace OBI=HOME
```

Record MIDI OUT with a MIDI monitor through a DIN interface: a power-on first (the baseline), then a switch.
