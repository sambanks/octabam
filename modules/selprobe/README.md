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
3. **GAIN is the readout.** Its own value picks which of the six page-2
   slots is shown — 0–20 is slot 0, then 21 per slot up to slot 5 — and the
   number printed is `slot * 256 + the byte`, so the slot is always visible
   beside the value and a mis-set knob cannot be mistaken for a wrong
   formula. `-` means no project is loaded.
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

## Verified locally

Rendered through the booted firmware's own formatter path: with no project
it prints `-`, and with a Part mapped it prints `0`, `256` and `1280` for
GAIN 0, 30 and 127 — slots 0, 1 and 5 of a zeroed array. That proves the
cave runs, decodes the knob and reads the address it computes. What it
cannot prove locally is the only thing it exists for: which byte that is.
