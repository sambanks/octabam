# `waveload` — what a 4-voice wave track costs the ColdFire

Stock effects plus [CF METER](../../../modules/cfmeter/README.md),
[CF METER IDLE](../../../modules/cfmeter-idle/README.md) and
[WAVE LOAD](../../../modules/waveload/README.md), with USB MIDI and USB
AUDIO OUT TRACKS MAIN CUE for the readout. DARK REV is off the chooser: its
DSP words hold the readout insert. With WAVE LOAD in the remix, CF METER's
BURN knob is K: the frame interrupt renders K 4-voice wave engines
(output discarded) where it would busy-wait. The readout comes over USB
AUDIO, T8 on channels 15/16.

## Procedure

1. `make image REMIX=waveload BUILD=N`, flash, power-cycle.
2. Load a project that plays the way you play (trigs on the tracks you
   use). T8 is the readout: its FX2 = **CF Meter**, which replaces T8's
   audio. BURN (FX2 page 1, first knob) at 0.
3. USB to the Mac. Each take: `tools/hw/rec 12 <name>.wav Octatrack`, then
   `python3 tools/harness/cfmeter.py <name>.wav`.

| take | state |
|---|---|
| `stop-k0` | transport stopped, BURN 0 |
| `play-k0` | transport running, BURN 0 |
| `play-kK` | transport running, BURN = K: 1, 2, 3, … one step at a time until the unit misbehaves (note K and what happened) |

Per 4-voice engine: (isr mean at K − isr mean at 0) / K, in µs, from the
`isr mean us` column; the frame period is 362.8 µs. The last K that plays
clean is how many 4-voice wave tracks fit beside that project.

Put BURN back to 0 before saving or switching projects: it is stored in
the Part like any knob. A freeze at a high K is cleared by a power-cycle.

The period column should read 362.8 µs; if it does not, DTIM3 is not at
132 MHz and every µs figure scales by 362.8 / period.
