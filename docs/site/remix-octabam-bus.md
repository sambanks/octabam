# Octabam Bus v0.5

Octabam Bus turns the eight FX2 slots into one delay and reverb bus, with a send from every
track, and keeps Octabam's core features around it. The
[Octabam Bus Remix Manual](reference/manual/octabam-bus/index.md) has a page for every
feature.

!!! warning "Not flashed in this form"
    This remix passes every build and emulator check CI runs. An earlier form of the bus ran
    on an MKII in October 2026; this one, with the stock effects and the ColdFire features
    beside the bus, has not run on a unit.

## The bus

Track 1 hosts the delay and track 5 the reverb. Every other track's FX2 is a SEND with two
knobs, DEL and REV. The delay's repeats also feed the reverb, and the delay follows the
project tempo. The FX2 menu cannot change a track's effect, and a new project starts wired
this way.

| Track | FX2 |
|---|---|
| 1 | [Bus delay](reference/manual/octabam-bus/effects/busdelay.md) (locked) |
| 5 | [Bus reverb](reference/manual/octabam-bus/effects/busverb.md) (locked) |
| 2–4, 6–7 | [SEND](reference/manual/octabam-bus/effects/send.md): DEL · REV |
| 8 (master) | stock DELAY, for its beat repeat |

Keep tracks 1 and 5 as THRU tracks with no trigs of their own: that is the only setup the
bus has been tested in.

## FX1

FX1 lists NONE, [SPECTRUM](reference/manual/octabam-bus/effects/spectrum.md),
[CHARACTER](reference/manual/octabam-bus/effects/character.md) and
[MODULATION](reference/manual/octabam-bus/effects/modulation.md). The 13 stock effects
other than DELAY give up their audio-processor code to the bus. SCOPE, the WAVE machine and
SHATTER are not in this image.

## Install

1. **Back up the card.** KITS writes `kits.work` into each project it loads.
2. [Build and Install](web-builder.md): choose **octabam-bus** in the builder.
3. Follow [Install the image](web-builder.md#install-the-image).
4. A project made before installing needs two preparation steps on a computer, in the
   [remix's README](https://github.com/sambanks/octabam/blob/main/remixes/octabam-bus/README.md#how-to-flash).
5. To restore stock OS, follow [Safety and Recovery](safety.md).

## Everything in the image

??? note "Full list of features and authors"

    --8<-- "reference/_remix-octabam-bus.md"
