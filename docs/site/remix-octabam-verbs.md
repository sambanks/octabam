# Octabam Verbs v0.5

Octabam Verbs is [Octabam](remix-octabam.md) with VERBERATION in place of the three stock
reverbs, and three more effects in the memory the reverbs gave up. The
[Octabam Manual](reference/manual/index.md) has a page for every feature; this page says what
is different here.

!!! warning "Not flashed"
    This remix has been tested only in software. Its reverbs, and the three effects beside
    them, have not run together on a unit. Octabam is the remix that has.

## The reverbs

PLATE REV, SPRING REV and DARK REV are off both effect menus. FX2 lists
[VERBERATION](reference/manual/effects/verberation.md), which goes from rooms to halls and has
a desk-style gate, and three rows that start it in a mode:

| FX2 row | What it is |
|---|---|
| [VERBERATION](reference/manual/effects/verberation.md) | rooms to halls with a desk-style gate; MODE (ROOM, PLATE, HALL, GATED), LCUT, MOD, RATE, SIZE, PRE on page 2 |
| [VERB PLATE](reference/manual/effects/verberation.md#verb-plate) | VERBERATION starting in PLATE mode, on PLATE REV's row |
| [VERB ROOM](reference/manual/effects/verberation.md#verb-room) | VERBERATION starting in ROOM mode, on SPRING REV's row |
| [VERB HALL](reference/manual/effects/verberation.md#verb-hall) | VERBERATION starting in HALL mode, on DARK REV's row |

A Part saved with a stock reverb opens on that reverb's row, with the row's defaults on its
FX2 pages. Octabam's choosers refuse a stock reverb beside a loaded effect; here there is no
such guard, and VERBERATION can sit on any track's FX2 beside any loaded effect.

## Three more effects

Always loaded, like a stock effect.

| Effect | Menus | What it is |
|---|---|---|
| [VIBRATO](reference/manual/effects/vibrato.md) | FX1, FX2 | pitch vibrato: sine, triangle, square trill, random |
| [TRANSIENT](reference/manual/effects/transient.md) | FX1, FX2 | transient shaper |
| [RESONATOR](reference/manual/effects/resonator.md) | FX1 | four resonant band-passes |

## The rest

SPECTRUM, CHARACTER, MODULATION, SHATTER and COMPRESSOR's side-chain are loaded on demand,
as in Octabam, and the rest of [what Octabam adds](remix-octabam.md#what-else-you-get) is here,
except SCOPE and the WAVE machine. Where Octabam keeps every stock effect as stock has it,
this remix does not.

## Install

1. **Back up the card.** KITS writes `kits.work` into each project it loads.
2. [Build and Install](web-builder.md): choose **octabam-verbs** in the builder.
3. Follow [Install the image](web-builder.md#install-the-image).
4. A project made on the unit after installing needs no preparation.
5. To restore stock OS, follow [Safety and Recovery](safety.md).

## Everything in the image

??? note "Full list of features and authors"

    --8<-- "reference/_remix-octabam-verbs.md"
