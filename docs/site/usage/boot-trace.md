A probe for finding where a boot hangs. It sends one MIDI note on MIDI OUT
at each stage of the boot, so a hang on the unit names its stage: the last
note a MIDI monitor receives is the last stage that ran.

## Access

No menu and no screen. Connect a MIDI monitor to MIDI OUT and boot. Not in
an official remix; build the test remix `remix-switch-trace`. It was built
for REMIX SWITCH's hardware bring-up.

## Operation

Each note is Note On, channel 1, velocity 127 unless noted:

| Note | Stage |
|---|---|
| 1 | the OS entry ran (sent by REMIX SWITCH's chainloader when it is in the image) |
| 2 | the DSP upload starts |
| 3 | the DSP upload returned |
| 4 | the panel link's init |
| 5 | the MKII panel handshake |
| 6 | the UI's panel report check |
| 7 | the first audio frame interrupt entered |
| 8 | ... and returned |
| 9 | the clock check reached; velocity is the PLL multiplier byte (22 is 264 MHz) |
| 10 | the bootstrap-reprogram branch taken (must never appear) |

The module also sends notes for the DSP upload's record echoes and any
stall, and for REMIX SWITCH's switch stages; the table in the module's
source lists them.
