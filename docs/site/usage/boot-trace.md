This diagnostic module helps pinpoint where a boot sequence hangs. It transmits a MIDI note on MIDI OUT at each stage of startup, so the last note received by a MIDI monitor identifies the last stage that ran.

## Access

This module has no menu or screen. Connect a MIDI monitor to MIDI OUT before powering on the unit. It is not included in the standard remixes; build the `remix-switch-trace` remix to use it. It was written for REMIX SWITCH hardware bring-up.

## Operation

Each message is a Note On on channel 1 with velocity 127 unless noted otherwise:

| Note | Stage |
|---|---|
| 1 | OS entry reached (sent by the REMIX SWITCH chainloader when present) |
| 2 | DSP upload started |
| 3 | DSP upload returned |
| 4 | Panel link initialization |
| 5 | MKII panel handshake |
| 6 | UI panel report check |
| 7 | First audio frame interrupt entered |
| 8 | First audio frame interrupt returned |
| 9 | Clock check reached; velocity carries the PLL multiplier byte (22 = 264 MHz) |
| 10 | Bootstrap-reprogram branch taken (should never appear) |

The module also sends additional notes for DSP upload record echoes, stalls, and REMIX SWITCH switch stages; see the table in the module's source code for the full list.
