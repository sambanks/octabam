## What it does

Class-compliant USB MIDI in and out, and USB audio out, on the
Octatrack's own USB port. The stock USB storage mode still works.

## USB MIDI

MIDI in and out over USB, mirroring the DIN ports. The sequencer follows
USB MIDI clock; time stretch, the LFOs and the FX do not (DIN clock
drives all of them).

## Audio out

The Octatrack as a USB audio input for the computer: UAC2, 44.1 kHz,
24-bit. In the three official remixes the layout is MAIN CUE: four
channels, MAIN L/R and CUE L/R. The Octatrack does not take audio back
from the computer in these remixes (INPUTS is off). At full speed the
device carries MAIN.

LAYOUT and INPUTS are build-time settings: another remix may pin other
values (TRACKS MAIN CUE, TRACKS, MASTER, MAIN CUE, MAIN, TRACKS POST;
inputs AB, CD, ABCD).
