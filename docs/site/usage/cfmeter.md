A probe. It measures, on the unit, how long the ColdFire's frame interrupt
takes and how much time main's idle loop gets (with CF Meter Idle), and,
on core 0, how long the DSP waits for each frame, whether the ESAI
underran or overran, and the frame period. It prints the numbers as audio
on track 8. It is the instrument for pricing ColdFire voice engines such as
SYNTH MACHINE, and for reading the DSP's load during normal play.

## Access

An effect on track 8 only: select T8, press FX2, and pick **CF Meter**.
T8's audio is replaced by the readout (its machine still runs). Not in an
official remix; build the test remix `cfmeter`. That image takes DARK REV
off the chooser, because the readout uses its DSP words.

## Operation

1. Build and flash the test remix, then power-cycle. Make a new project
   and load a silent 4 s `SYNTH.wav` into FLEX slot 1.
2. Put CF Meter on T8's FX2, with BURN and DBRN at 0.
3. Connect USB. The readout is on USB audio, T8 on channels 15 and 16
   (post-FX, pre-fader, so LEVL and MAIN do not matter).
4. Record about 12 s per state, then decode the capture with `cfmeter.py`.
   A cycle is 2 s and the decoder needs two of its sync edges, so a take
   is 6 s at least.
- Read the ISR mean and max, not idle percentage: task-level work below
  the UI's priority reads as busy while the panel stays responsive.
- BURN, MEM, SRC, SPAN and DBRN are read on track 8 only.
- A late frame shows as slot 9 jumping by a whole frame's polls.

## Parameters

| Page | Knob | Range | What it does |
|---|---|---|---|
| 1 | BURN | 0-127, default 0 | 2 us of busy-wait per step at the start of every frame interrupt |
| 1 | MEM | 0-127, default 0 | MEM KB read after the burn, timed into slot 7 |
| 1 | DBRN | 0-127, default 0 | 24 x DBRN DSP cycles per sample, burnt by the insert before its sample loop |
| 1 | SPAN | 0-127, default 0 | what slot 7 prints: BURN or the walk; the HC poll loops' time; the eDMA handler's time inside the frame interrupt; all of that handler's time |
| 1 | SRC | 0-127, default 0 | the region MEM walks: 0 cached SDRAM, 1 uncached alias, 2 on-chip SRAM |

Under the port, BURN 20 added 40.0 us to the interrupt mean (2 us x 20).
The port's durations are its own clock's, not the unit's; the unit's
numbers are not measured.
