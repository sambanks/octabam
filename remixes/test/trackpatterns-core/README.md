# `trackpatterns-core` -- TRACK PATTERNS on the core modules

TRACK PATTERNS with every core module (KITS, DIRECT_JUMP_KYOTI, RELOAD_FROM_PROJECT, BRAIN, STORE, PLOCKS P2 and the rest) and the 14 stock effects, for running the module beside the modules that share its handlers.

## What is in it

- **TRACK PATTERNS** -- [`modules/trackpatterns/README.md`](../../../modules/trackpatterns/README.md).
- the core module selection of [`octabam`](../../octabam/README.md) without LOAD METER and its effects, with its USB and MUTE_MODES settings.

## Build

```bash
make image REMIX=trackpatterns-core BUILD=1
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=trackpatterns-core` runs every gate first.
