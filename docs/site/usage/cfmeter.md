CF Meter is a performance profiling tool that runs on hardware to measure ColdFire frame interrupt duration, `main` idle loop time (when paired with CF Meter Idle), and core 0 DSP metrics including frame wait time, ESAI underrun/overrun status, and frame period. It encodes these measurements as audio on track 8, providing a way to profile ColdFire voice engines such as SYNTH MACHINE and monitor DSP load during playback.

## Access

CF Meter runs on track 8 only: select T8, press FX2, and choose **CF Meter** from the effect list. Track 8's audio output is replaced by the encoded readout, though its track machine continues running. This module is not included in the standard remixes; build the `cfmeter` remix to use it. That remix removes DARK REV from the chooser because the readout uses its DSP memory.

## Operation

1. Build and flash the `cfmeter` remix, then power-cycle the unit. Create a new project and load a silent 4-second `SYNTH.wav` file into FLEX slot 1.
2. Load CF Meter into T8's FX2 slot with BURN and DBRN set to 0.
3. Connect USB audio. Track 8 outputs the readout on USB channels 15 and 16 (post-FX, pre-fader, so LEVL and MAIN settings do not affect it).
4. Record about 12 seconds per test condition and decode the recording with `cfmeter.py`. Each readout cycle takes 2 seconds and the decoder requires two sync edges, so recordings must be at least 6 seconds long.

Notes:

- Use the frame interrupt mean and max times rather than idle percentage, because task-level work below the UI's priority registers as busy even while the front panel stays responsive.
- BURN, MEM, SRC, SPAN, and DBRN are only read on track 8.
- A late audio frame appears as slot 9 jumping by a full frame's worth of polls.

## Parameters

| Page | Knob | Range | What it does |
|---|---|---|---|
| 1 | BURN | 0-127, default 0 | Adds 2 us of busy-wait per step at the start of every frame interrupt |
| 1 | MEM | 0-127, default 0 | Reads MEM KB of memory after the burn, timed into slot 7 |
| 1 | DBRN | 0-127, default 0 | Burns 24 x DBRN DSP cycles per sample before the insert's sample loop |
| 1 | SPAN | 0-127, default 0 | Selects what slot 7 reports: BURN/memory walk time, HC poll loop time, eDMA handler time within the frame interrupt, or total eDMA handler time |
| 1 | SRC | 0-127, default 0 | Selects the memory region walked by MEM: 0 = cached SDRAM, 1 = uncached alias, 2 = on-chip SRAM |

Under the port, setting BURN to 20 added 40.0 us to the interrupt mean (2 us x 20). Because the port uses its own clock rather than hardware timing, those values do not represent unit measurements, which have not been recorded.
