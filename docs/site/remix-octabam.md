# Octabam v0.3

![BRAIN in the main menu, added by Octabam](img/brain/pane.png)

*BRAIN in the main menu, added by Octabam*

Octabam adds the core features to Octatrack OS 1.40C and three effects. All 14
stock effects and both effect menus stay as stock has them, with stock LO-FI's
AMF knob fixed. The [Octabam Remix Manual](reference/manual/octabam/index.md)
has a page for every feature.

## The effects

SPECTRUM, CHARACTER and MODULATION are on FX1 and FX2, beside the stock effects.

| Effect | What it is |
|---|---|
| [SPECTRUM](reference/manual/octabam/effects/spectrum.md) | filter: Moog ladder, SEM, isolator, formants |
| [CHARACTER](reference/manual/octabam/effects/character.md) | fold, saturation, tilt, compressor, width |
| [MODULATION](reference/manual/octabam/effects/modulation.md) | Juno, Dimension, flanger, phaser, comb |

Each is loaded into the audio processor only while a track uses it; a pattern
change that puts one on all eight tracks, or takes it off them, leaves about
0.34 s of silence at the switch.

## What else you get

- [BRAIN](reference/manual/octabam/brain/index.md): templates, settings, defaults, and switching images.
- [Kits](reference/manual/octabam/parts/kits.md): save and recall a Kit for each pattern.
- [Page 2 parameter locks](reference/manual/octabam/parts/plocks-p2.md) and
  [scene locks](reference/manual/octabam/parts/scenes-p2.md): control both effect pages.
- [MIDI scenes](reference/manual/octabam/parts/midi-scenes.md),
  [CC map](reference/manual/octabam/midi-usb/cc-map.md) and
  [CC feedback](reference/manual/octabam/midi-usb/cc-feedback.md).
- [USB](reference/manual/octabam/midi-usb/usb.md): MIDI both ways, plus audio to a computer: the 16 track channels, MAIN and CUE by default.
- [OCTA-303](reference/manual/octabam/machines/octa303.md): a TB-303 voice as a machine.
- [Pattern mute](reference/manual/octabam/sequencer/pattern-mute.md): double-press FUNC to mute tracks per pattern as well as globally.
- Sequencer and recording features, utilities and fixes: see the manual's contents.

## Install

1. **Back up the card.** KITS writes `kits.work` into each project it loads.
2. [Build and Install](web-builder.md) patches your copy of OS 1.40C in the
   browser and gives you the files to install.
3. Follow [Install the image](web-builder.md#install-the-image) and confirm that
   SYSTEM STATUS → OS VERSION shows `OCTABAM` and the build number.
4. To restore stock OS, follow [Safety and Recovery](safety.md).

## Everything in the image

??? note "Full list of features and authors"

    --8<-- "reference/_remix-octabam.md"
