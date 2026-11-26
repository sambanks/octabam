# Octabam Bus v0.5

Octabam Bus turns the eight FX2 slots into a shared delay and reverb send bus
accessible from every track, while keeping Octabam's core workflow features.
Every feature is documented in the [Octabam Manual](reference/manual/index.md);
this page summarizes what differs from the standard Octabam remix.

## The bus

Track 1 hosts the shared delay and track 5 hosts the shared reverb. Every other
track's FX2 slot acts as a SEND with DEL and REV knobs controlling how much
signal goes to each bus effect. The delay repeats can also feed into the reverb,
and the delay locks to the project tempo. FX2 assignments are locked so the FX2
menu cannot overwrite them, and new projects start pre-wired with this layout:

| Track | FX2 |
|---|---|
| 1 | [Bus delay](reference/manual/bus/busdelay.md) (locked) |
| 5 | [Bus reverb](reference/manual/bus/busverb.md) (locked) |
| 2–4, 6–7 | [SEND](reference/manual/bus/send.md): DEL · REV |
| 8 (master) | Stock DELAY (kept for beat repeat) |

On tracks 1 and 5, the FX2 page shows only DEL and REV, just like SEND tracks.
To edit the delay and reverb parameters themselves, press **[TEMPO]** to open
the [TEMPO window](reference/manual/bus/tempo-bus.md).

!!! warning "Tracks 1 and 5"
    Keep tracks 1 and 5 configured as THRU tracks with no trigs of their own.
    Triggering audio directly on track 1 causes the bus delay to pop and click.

## What the bus costs

To make room in DSP memory for the bus engines, the 13 stock effects other than
DELAY are removed. FX1 provides NONE,
[SPECTRUM](reference/manual/effects/spectrum.md),
[CHARACTER](reference/manual/effects/character.md), and
[MODULATION](reference/manual/effects/modulation.md), and the stock reverbs are
not available. SCOPE, the WAVE machine, SHATTER, and the sidechain compressor
are also omitted. All other features listed under
[Octabam](remix-octabam.md#what-else-you-get) are included.

## Install

1. **Back up your CF card.** KITS writes a `kits.work` file into every project
   it loads.
2. Open [Build and Install](web-builder.md) and select **octabam-bus**.
3. Follow [Install the image](web-builder.md#install-the-image).
4. New projects created after installation are already wired for the bus.
   Existing projects created beforehand need two preparation commands on a
   computer (`ot_project.py host` and `stamp-defaults`); see the
   [octabam-bus README](https://github.com/sambanks/octabam/blob/main/remixes/octabam-bus/README.md#how-to-flash).
5. To return to stock OS, see [Safety and Recovery](safety.md).

## Everything in the image

??? note "Full list of features and authors"

    --8<-- "reference/_remix-octabam-bus.md"
