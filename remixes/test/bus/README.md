# `bus` — the plain two-server image, for the bus gates

The fixture `verify_two_core` and `scripts/refhash.sh` build: BusVerb + BusDelay + SEND + TEMPO SYNC with nothing hidden or locked, so the DEV one-core hatch and the SPEC two-core build run the same code paths (a hidden engine's host guard would pass the delay dry in the hatch). Not a remix to flash: `bottleservice` is the bus as it ships.

BusVerb + BusDelay + Send + tempo sync. The build's bit-identity subject.

## What is in it

- **BusVerb** — an eight-line FDN reverb (ROOM / PLATE / BIG, shimmer, gate, DLY, TONE, DIFF) that serves all eight tracks over a cross-core bus. Hosted on one of tracks 5–8.
- **BusDelay** — a multi-mode delay (CLEAN / pitched GRAIN cloud / REVERSE; page 2: MODE SCTR DENS SIZE PTCH TIME) serving all eight tracks. Hosted on one of tracks 1–4. TIME reads as a tempo division (TEMPO SYNC).
- **Send** — the FX2 effect every other track runs: DEL into the delay and REV into the reverb (page 1, slots 0 and 1). The fallback for any unassigned track.
- **TEMPO SYNC** (Sam Banks) — two ColdFire caves: the held MIDI note reaches the DSP (a note-only cave since image 24), and BusDelay's TIME draws as a division (1/8, 1/4 …) instead of milliseconds. On the unit.

## Build

```bash
make image REMIX=bus BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=bus` runs every gate first.

## Before you flash

- After flashing, stamp every project you will play before pressing play: `python3 tools/hw/ot_project.py stamp-defaults <project> bus`. A part saved under another layout feeds the stations its old bytes and the sequencer stalls.
- Judge BusVerb on track 5 (payload A serves tracks 5–8), BusDelay on track 1.
