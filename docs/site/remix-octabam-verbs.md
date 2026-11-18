# Octabam Verbs v0.5

Octabam Verbs is [Octabam](remix-octabam.md) with VERBERATION in place of the three stock
reverbs, and three more effects in the words the reverbs gave up. The
[Octabam Verbs Remix Manual](reference/manual/octabam-verbs/index.md) has a page for every
feature.

!!! warning "Not flashed"
    This remix passes every build and emulator check CI runs, but it has not run on a unit.
    Octabam is the remix that has.

## The reverbs

PLATE REV, SPRING REV and DARK REV are off both effect menus. FX2 lists VERBERATION and
three rows that start it in a mode. A Part saved with a stock reverb opens on that reverb's
row.

| Effect | What it is |
|---|---|
| [VERBERATION](reference/manual/octabam-verbs/effects/verberation.md) | rooms to halls with a desk-style gate; MODE (ROOM, PLATE, HALL, GATED), LCUT, MOD, RATE, SIZE, PRE on page 2 |
| [VERB PLATE](reference/manual/octabam-verbs/effects/verberation-plate.md) | VERBERATION starting in PLATE mode, on PLATE REV's row |
| [VERB ROOM](reference/manual/octabam-verbs/effects/verberation-room.md) | VERBERATION starting in ROOM mode, on SPRING REV's row |
| [VERB HALL](reference/manual/octabam-verbs/effects/verberation-hall.md) | VERBERATION starting in HALL mode, on DARK REV's row |

## Three more effects

Always loaded, like a stock effect.

| Effect | Menus | What it is |
|---|---|---|
| [VIBRATO](reference/manual/octabam-verbs/effects/vibrato.md) | FX1, FX2 | pitch vibrato: sine, triangle, square trill, random |
| [TRANSIENT](reference/manual/octabam-verbs/effects/transient.md) | FX1, FX2 | transient shaper |
| [RESONATOR](reference/manual/octabam-verbs/effects/resonator.md) | FX1 | four resonant band-passes |

SPECTRUM, CHARACTER, MODULATION, SHATTER and COMPRESSOR's side-chain are loaded on demand,
as in Octabam. SCOPE and the WAVE machine are not in this image; the rest of
[what Octabam adds](remix-octabam.md#what-else-you-get) is.

## Install

1. **Back up the card.** KITS writes `kits.work` into each project it loads.
2. [Build and Install](web-builder.md): choose **octabam-verbs** in the builder.
3. Follow [Install the image](web-builder.md#install-the-image).
4. To restore stock OS, follow [Safety and Recovery](safety.md).

## Everything in the image

??? note "Full list of features and authors"

    --8<-- "reference/_remix-octabam-verbs.md"
