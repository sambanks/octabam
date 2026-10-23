# `trackpatterns-core` -- TRACK PATTERNS on octabam-core

TRACK PATTERNS with every module of `octabam-core` (KITS, DIRECT_JUMP_KYOTI, RELOAD_FROM_PROJECT, BRAIN, STORE, PLOCKS P2 and the rest) and the 14 stock effects, for running the module beside the modules that share its handlers.

## What is in it

- **TRACK PATTERNS** -- [`modules/trackpatterns/README.md`](../../../modules/trackpatterns/README.md).
- the `octabam-core` selection ([`remixes/octabam-core/README.md`](../../octabam-core/README.md)), with its USB and MUTE_MODES settings.

## Status

`make check REMIX=trackpatterns-core`. Under the ColdFire port the gesture, MIDI and global-change run and the trig LEDs behave as with TRACK PATTERNS alone (`modules/trackpatterns/TESTING.md`). On the contributor's MKII, 22 Oct 2026 (`OCTABAM8`): the gesture on T1 and M1, a global change, save and power cycle passed; KITS' and DIRECT JUMP's own actions were not tried. That report predates this remix's EDIT EVENTS integration.

## Build

```bash
make image REMIX=trackpatterns-core BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=trackpatterns-core` runs every gate first.
