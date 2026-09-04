# SELECT PROBE — settling the select-array formula on hardware

`docs/MAINMENU.md` §9c-ii decoded where a page-2 SELECT's value lives:

```
DB + part*6322 + 0x8f04a + track*30 + page*6 + slot
```

and drove the firmware's own two-phase editor into writing that array. But
every local attempt to confirm the **track, page and slot terms** landed the
write at offset zero, because the emulator boots with no CF card and the
project database is empty. Three reads hit that same wall.

This probe settles it from the other side, on a real unit with a real
project, and **writes nothing**.

## The measurement

1. Build and flash `REMIX=selprobe make image`. Load a project.
2. Put **HELLO WORLD** on any track's FX2 and open that page.
3. **GAIN is the readout.** Its value picks BOTH the page and the slot —
   `slot = value mod 6`, `page = value div 6` — so one knob reads the whole
   parameter space:

   | GAIN | page |
   |---|---|
   | 0–5 | 0 |
   | 6–11 | 1 |
   | 12–17 | 2 |
   | **18–23** | **3 — FX1** |
   | **24–29** | **4 — FX2** |
   | 30+ | pinned to page 4, slot 5 |

   The number printed is `page * 4096 + slot * 256 + the byte`, so the row
   being read is always visible beside the value. `-` means no project.
4. On the **same track**, open page 2 of its FX2 effect and turn a select.
5. Go back to HELLO WORLD's GAIN and read it again.

## What the answer means

| what you see | what it says |
|---|---|
| the low byte follows the select you turned | ✅ the formula is right, and a screen can address a select directly |
| it never changes | the track or page term is wrong — the byte we address is not the one the panel writes |
| it changes when you turn a select on a DIFFERENT track | the `track*30` term is wrong, and by how many tracks the offset is out |
| it changes for the wrong slot | the `page*6 + slot` term is wrong; the slot shown says which byte moved |

Page is fixed at 4, which §9c measured as FX2 from the page-1 writer's own
arithmetic. If nothing on FX2 moves the number, try the same turn on FX1 to
tell "wrong page" from "wrong array".

## Why it only reads

A formatter runs inside a redraw, and the firmware's select editor **ends in
redraw calls**. A probe that invoked the editor would re-enter the drawing
code from inside it. This one calls nothing and stores nothing but the
caller's sprintf buffer.

⚠️ Mutually exclusive with `modules/cfprobe`: both register on HELLO WORLD's
GAIN. `remixes/selprobe.py` carries this one alone.

## What the unit has already said (4 Sep 2026, build 80)

The first build read FX2's page only, and shipped in an image that hides
every effect having an FX2 page-2 select — so there was nothing to turn.
It still returned a result, from two tracks read at the same slot:

| track | printed | slot | byte |
|---|---|---|---|
| T3 | 1281 | 5 | 1 |
| T4 | 1344 | 5 | 64 |

✅ **Different tracks give different bytes, so the `track*30` term is
LIVE.** Had the track offset been ignored — which is exactly what happened
in the emulator, where every write landed at offset zero — both tracks would
have read the same byte. That was the single most doubtful term in the
formula, and it is now the one with evidence behind it.

Still unconfirmed: the `page*6 + slot` terms, which is what the page-walking
build above is for.

## Verified locally

Rendered through the booted firmware's own formatter path: with no project
it prints `-`, and with a Part mapped it prints `0`, `256` and `1280` for
GAIN 0, 30 and 127 — slots 0, 1 and 5 of a zeroed array. That proves the
cave runs, decodes the knob and reads the address it computes. What it
cannot prove locally is the only thing it exists for: which byte that is.
