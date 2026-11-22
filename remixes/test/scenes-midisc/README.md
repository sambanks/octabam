# `scenes-midisc` — MIDI SCENES, KITS, SCENES P2 and PLOCKS P2

MIDI-driven scene locks, Kits, page-2 scene locks and page-2 parameter locks on the stock effects.

## What is in it

- **MIDI SCENES** (bkkbrls-del) — MIDI-driven scene locks.
- **KITS** (sambanks) — 255 Kits per project through the stock Part slots.
- **SCENES P2** (sambanks) — scene locks and the crossfader on FX1/FX2 page 2.
- **PLOCKS P2** (sambanks) — parameter locks on FX1/FX2 page 2: hold trigs and turn a knob on the SETUP page.

## Build

```bash
make image REMIX=scenes-midisc BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=scenes-midisc` runs every gate first.
