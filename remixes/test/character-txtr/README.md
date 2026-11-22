# `character-txtr` — octabam-bus with Character's texture stage

[`octabam-bus`](../../octabam-bus/README.md) with
[CHARACTER TXTR](../../../modules/character-txtr/README.md) on FX1 in place of
CHARACTER: the same bus, hosts, USB, Octakit and scene modules. The one
difference is page-2 slot 9 of the station, TXTR (Airwindows Pockey2).

This image exists to measure what no local instrument can: whether four
Characters with TXTR beside the reverb fit the core. The pricer says 2,751
cycles per sample against 3,120 usable, ~3,020 with the reverb's known
underread; the measured die point is 3,119. Until a unit has run it,
octabam-bus keeps the plain station.

## Build and flash

```bash
make check REMIX=character-txtr      # the gates, no hardware
make bus REMIX=character-txtr        # -> out/mainos_bus.bin
```

Then the card image as for any remix (`docs/guide/BUILDING.md`). Stamp the
project before play: a part saved under octabam-bus holds a 0 in slot 9,
which is TXTR off, so existing parts play as before; `tools/hw/ot_project.py
stamp-defaults <project> character-txtr` writes the new layout.

## What to test

1. Tracks 5–8 are the reverb's core. Select CHRT on FX1 of T5, T6, T7 and
   T8, set TXTR above 0 on each (any value above 0 costs the same; 127 is
   the full effect), with BusVerb on T5's FX2 as locked.
2. Play a pattern with audio on those tracks. A squeal, a wash or a halt is
   the core over its budget; clean audio through a few minutes of play is
   the result that lets TXTR into octabam-bus.
3. If it fails, repeat with three, then two Characters at TXTR: the count at
   which it plays says what the stage costs on the unit.
4. TXTR on the master (T8) is where 's unreproduced squeal was
   heard with the first texture; note whether it recurs.

Report the image number, the configuration and what was heard on the PR or
to Sam.
