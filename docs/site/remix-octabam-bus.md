# Octabam Bus v0.5

Octabam Bus turns the eight FX2 slots into one delay and reverb bus, with a send from every
track, and keeps Octabam's core features around it. The
[Octabam Manual](reference/manual/index.md) has a page for every feature; this page says what
is different here.

## The bus

Track 1 hosts the delay and track 5 the reverb. Every other track's FX2 is a SEND with two
knobs, DEL and REV, that set how much of the track goes to each. The delay's repeats also
feed the reverb, and the delay follows the project tempo. The FX2 menu cannot change a
track's effect, and a new project starts wired this way.

| Track | FX2 |
|---|---|
| 1 | [Bus delay](reference/manual/bus/busdelay.md) (locked) |
| 5 | [Bus reverb](reference/manual/bus/busverb.md) (locked) |
| 2–4, 6–7 | [SEND](reference/manual/bus/send.md): DEL · REV |
| 8 (master) | stock DELAY, for its beat repeat |

Tracks 1 and 5 draw only DEL and REV on their FX2 page, like a SEND. The delay's and the
reverb's own knobs are in the [TEMPO window](reference/manual/bus/tempo-bus.md): press
**[TEMPO]**.

!!! warning "Tracks 1 and 5"
    Keep tracks 1 and 5 as THRU tracks with no trigs of their own. Sounds programmed on track 1
    make the delay pop and click.

## What the bus costs

The 13 stock effects other than DELAY give up their audio-processor code to the bus. FX1 lists
NONE, [SPECTRUM](reference/manual/effects/spectrum.md),
[CHARACTER](reference/manual/effects/character.md) and
[MODULATION](reference/manual/effects/modulation.md); the stock reverbs have no row. SCOPE, the
WAVE machine, SHATTER and the side-chain compressor are not in this image. The rest of
[what Octabam adds](remix-octabam.md#what-else-you-get) is.

## Install

1. **Back up the card.** KITS writes `kits.work` into each project it loads.
2. [Build and Install](web-builder.md): choose **octabam-bus** in the builder.
3. Follow [Install the image](web-builder.md#install-the-image).
4. A project made on the unit after installing is wired for the bus. A project made before
   installing needs two preparation steps on a computer (`ot_project.py host` and
   `stamp-defaults`), in the
   [remix's README](https://github.com/sambanks/octabam/blob/main/remixes/octabam-bus/README.md#how-to-flash).
5. To restore stock OS, follow [Safety and Recovery](safety.md).

## Everything in the image

??? note "Full list of features and authors"

    --8<-- "reference/_remix-octabam-bus.md"
