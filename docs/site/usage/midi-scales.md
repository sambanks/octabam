MIDI Scales extends the native MIDI ARP SETUP **KEY** control to seven
diatonic modes in all twelve keys. OFF bypasses scale correction. Major
and natural Minor keep their original saved values and playback behavior;
Dorian, Phrygian, Lydian, Mixolydian and Locrian add five more choices per key.

## How to use it

Select a MIDI track, set its output channel and program some notes. Open
ARP SETUP with **FUNC + AMP**, then press encoder **F** to enable KEY if it is OFF and turn F to select
the key and mode. Press F again to bypass it. Choices are
grouped by key: Major, Dorian, Phrygian, Lydian, Mixolydian, Minor, Locrian.
The screen abbreviates these as MAJ, DOR, PHR, LYD, MIX, MIN and LOC.

For example, **C DOR** corrects outgoing sequencer/arp notes to C, D, Eb,
F, G, A and Bb. Added modes choose the nearest scale note, with ties going
down. It changes note pitches; it does not generate chords.

**C MIX** instead uses C, D, E, F, G, A and Bb.

## Storage and compatibility

KEY is stored in the existing Part setting. Stock 1.40C cold project load
clamps additional mode values to **B Minor**. Saving the bank on stock writes
that value and loses its extended mode. Loading alone does not rewrite every
bank file. Before returning to stock, select OFF or an original Major/Minor
choice and save, or retain a separate project backup. Audio-track Scale
Quantizer is separate.

This module works independently. With MIDI Follow, the follower inherits its
source track's KEY setting.

## Verification limits

These are LCD captures from the emulator using the standalone MIDI Scales
remix (BUILD=91), not photographs of hardware. Linked-code checks cover all
84 key/mode combinations, all 128 note values, the installed hooks and
formatter bounds. Full-firmware emulator checks cover cold project load and
native save across candidate, stock and candidate again.

The MIDI Follow combination also has emulator coverage and targeted MKII
tests of four-note output, releases and sustained MIDI load. Those hardware
checks do not cover every key/mode choice or qualify other module combinations.

Octatrack MKII hardware testing on 16 October 2026 used OCTABAMS1
(source `9c30ec46`). Scale playback, Part Reload, project save/load and
power-cycle checks passed. A stock 1.40C round trip confirmed C Dorian and
D Mixolydian become B Minor when saved on stock and remain B Minor after
returning to S1; C Major and an untouched reference project retained their
settings. Physical encoder-feel stress tests, MIDI timing, exhaustive
key/mode coverage and MKI operation remain unverified.
