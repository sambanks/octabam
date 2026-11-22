# `rig` — octabam-bus's bus and FX1 stations, for the gates

The fixture `verify_cc_map`, `verify_ccfeedback`, `verify_character` and `verify_one_bus` build (`registry.fixture`: the smallest remix carrying their modules, and for the CC MAP gates one without a DRAM runtime, since they run under unicorn). Not a remix to flash: `octabam-bus` is the one that ships.

## What is in it

[`octabam-bus`](../../octabam-bus/README.md) without USB AUDIO, USB MIDI, Octakit and the scene modules: the bus (BusVerb + BusDelay, hosted and locked on T1 and T5), SEND on every other FX2, SPECTRUM, CHARACTER and MODULATION on FX1, TEMPO SYNC, CC MAP, MODE DEFAULTS, RIG HOSTS.

Until the `usb` remix was this selection plus USB MIDI, and these gates built it.

## Build

```bash
make check REMIX=rig
```
