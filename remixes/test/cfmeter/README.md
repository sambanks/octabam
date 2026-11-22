# `cfmeter` — the ColdFire's spare time with SYNTH MACHINE running

`octatrick` without TUNER and USB AUDIO IN (SYNTH MACHINE, SCALE QUANTIZER,
DIRECT JUMP, USB MIDI, USB AUDIO OUT TRACKS MAIN CUE, the stock effects) plus [CF METER](../../../modules/cfmeter/README.md)
and [CF METER IDLE](../../../modules/cfmeter-idle/README.md). DARK REV is off
the chooser: its DSP words hold the readout insert. The readout comes over
USB AUDIO, T8 on channels 15/16 (post-FX, pre-fader, so LEVEL and MAIN do
not matter).

## Procedure

1. `make image REMIX=cfmeter BUILD=N`, flash, power-cycle.
2. A new project. Copy a silent 4 s WAV named `SYNTH.wav` to the set's
   audio pool and load it into FLEX slot 1.
3. T8: FX2 = **CF Meter** (T8's audio is replaced by the readout; its
   machine still runs). BURN (FX2 page 1, first knob) and DBRN (third
   knob) at 0.
4. USB to the Mac. Each state below: `tools/hw/rec 12 <name>.wav Octatrack`,
   then `python3 tools/harness/cfmeter.py <name>.wav`. A cycle is 2 s
   and the decoder needs two of its sync edges, so 12 s gives four or
   five rows.

| take | state |
|---|---|
| `idle` | transport stopped, nothing assigned |
| `play` | transport running, all tracks stock, no trigs |
| `synthN-v1` | N = 1…8 tracks: FLEX, slot 1 (SYNTH.wav), a trig on every step, VOIC 1 |
| `synth8-v4` | 8 tracks, VOIC 4, CHRD OCT3 (four voices per track) |
| `burnB` | the `synth8-v1` state, BURN = 20, 40, 60, … until the unit misbehaves (note the value and what happened) |
| `dbrnD` | the `play` state, DBRN = 20, 40, 60, …: spin min must fall by 24 × D × 16 cycles per frame; the value at which spin max jumps by a frame's worth or TUE counts is core 0's wall |
| `spanS` | the `play` and `synth8-v1` states, SPAN = 1, 2, 3: slot 7 is the HC polls' time, the eDMA handler's time inside the frame interrupt, and all of it, per frame; ISR mean less SPAN 1 and SPAN 2 is the interrupt's own work |
| `memK-sS` | the `idle` state, SRC = S (0 cached SDRAM, 1 uncached alias, 2 SRAM), MEM = K (8, 16, 32, 64; 31 at most for S = 2), with and without a host stream open: slot 7 × 4 × 7.58 ns / (K × 64) is one line's cost in that memory (`modules/cfmeter/README.md` "Line fills") |

Put BURN, MEM and DBRN back to 0 before saving or switching projects: they
are stored in the Part like any knob. A freeze at a high BURN, MEM or DBRN
is cleared by a power-cycle.

The period column should read 362.8 µs; if it does not, DTIM3 is not at
132 MHz and every µs figure scales by 362.8 / period. The DSP period
columns (slots 13/14) should read 362.8 µs too; they are timer 0 at
CLK/2 = 99.95 MHz (`docs/firmware/CHIP.md` section 2).

The `dbrnD` takes give a poll's cost: (spin min at 0 − spin min at D) ×
cost = 24 × D × 16 cycles; with it, slot 8 × cost is core 0's spare per
frame during normal play, which the burn sweep could only read by
breaking the unit.
