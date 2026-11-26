# Octabam Verbs v0.5

Octabam Verbs is based on [Octabam](remix-octabam.md), replacing the three stock
reverbs with VERBERATION and using the reclaimed DSP space for three additional
resident effects. Every feature is documented in the
[Octabam Manual](reference/manual/index.md); this page summarizes what differs
from the standard Octabam remix.

## The reverbs

PLATE REV, SPRING REV, and DARK REV are removed from both effect menus and
replaced on FX2 by [VERBERATION](reference/manual/effects/verberation.md), a
single reverb covering rooms through large halls with a desk-style gate. Use
MODE on page 2 to choose ROOM, PLATE, HALL, or 80S, alongside LCUT, MOD, RATE,
SIZE, and PRE.

Existing Parts saved with a stock reverb automatically map to VERBERATION in
the matching mode (PLATE REV becomes PLATE, SPRING REV becomes ROOM, and DARK
REV becomes HALL) using that mode's default settings. Unlike standard Octabam,
where stock reverbs cannot coexist with on-demand effects, VERBERATION has no
such conflict and can run on any track's FX2 alongside any loaded effect.

## Three more effects

These three effects stay loaded in DSP memory at all times, just like stock
effects:

| Effect | Menus | Description |
|---|---|---|
| [VIBRATO](reference/manual/effects/vibrato.md) | FX1, FX2 | Pitch vibrato with sine, triangle, square trill, and random waveforms |
| [TRANSIENT](reference/manual/effects/transient.md) | FX1, FX2 | Attack and sustain transient shaper |
| [RESONATOR](reference/manual/effects/resonator.md) | FX1 | Four-band resonant bandpass filter |

## The rest

SPECTRUM, CHARACTER, MODULATION, SHATTER, and the sidechain compressor load on
demand just like in Octabam. All other features from
[Octabam](remix-octabam.md#what-else-you-get) are included except SCOPE and the
WAVE machine. Unlike standard Octabam, this remix does not keep the three stock
reverbs.

## Install

1. **Back up your CF card.** KITS writes a `kits.work` file into every project
   it loads.
2. Open [Build and Install](web-builder.md) and select **octabam-verbs**.
3. Follow [Install the image](web-builder.md#install-the-image).
4. Projects created on the unit after installation need no extra setup.
5. To return to stock OS, see [Safety and Recovery](safety.md).

## Everything in the image

??? note "Full list of features and authors"

    --8<-- "reference/_remix-octabam-verbs.md"
