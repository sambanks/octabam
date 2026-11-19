### About Octabam Bus

Octabam Bus turns the eight FX2 slots into one **delay and reverb bus**. Track 1 hosts the
delay and track 5 the reverb; every other track's FX2 is a SEND with two knobs, DEL and REV,
that set how much of the track goes to each. The delay's repeats also feed the reverb. FX1
lists SPECTRUM, CHARACTER and MODULATION. Around the bus are Octabam's core features: BRAIN,
Kits, page-2 locks and scenes, MIDI and USB, the sequencing and recording features, and
OCTA-303. This is version 0.5.

### The bus

| track | FX2 | knobs |
|---|---|---|
| 1 | **DELAY** (locked) | page 1: DEL · REV · FDBK · TONE · PING · WET; page 2: MODE · SCTR · DENS · SIZE · PTCH · TIME |
| 5 | **REVERB** (locked) | page 1: DEL · REV · SIZE · SHMR · SHFT · WET; page 2: MODE · TONE · DIFF · GATE · DLY · TIME |
| 2–4, 6–7 | **SEND** | DEL · REV |
| 8 (master) | stock **DELAY** | stock's, for its beat repeat |

The FX2 menu cannot change a track's effect ([FX2 lock](utilities/fx2-lock.md)). A new
project starts wired this way, and the delay follows the project tempo. See
[Bus delay](effects/busdelay.md), [Bus reverb](effects/busverb.md) and [Send](effects/send.md).

!!! warning "Tracks 1 and 5"
    Keep tracks 1 and 5 as THRU tracks with no trigs of their own. That is the only setup
    the bus has been tested in. Sounds programmed on track 1 made the delay pop and click.

### What the bus costs

The 13 stock effects other than DELAY give up their audio-processor code to the bus: FX1 lists
NONE, SPECTRUM, CHARACTER and MODULATION, and the stock reverbs have no row. SCOPE, the WAVE
machine and SHATTER are not in this image.

### Status

This remix has not been flashed in this form. It passes every build and emulator check that
CI runs. An earlier form of the bus ran on an MKII in October 2026; the bus running beside
the stock effects and the ColdFire features has not run on a unit.

### Before you install

Back up the CF card first. Kits write a file into each project they load.
A project made on the unit after installing is wired for the bus. A project made before
installing needs two preparation steps on a computer (`ot_project.py host` and
`stamp-defaults`), described in the
[remix's README](https://github.com/sambanks/octabam/blob/main/remixes/octabam-bus/README.md#how-to-flash).
To return to stock OS, follow [Safety and Recovery](../../../safety.md).
