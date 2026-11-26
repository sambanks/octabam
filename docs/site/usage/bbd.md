BBD DELAY is a bucket-brigade delay effect for FX2 that replaces SPRING REV and PLATE REV. It sums the track input to mono and processes it through a modeled BBD chip consisting of a 2:1 compander, clock-tracking anti-alias and reconstruction filters, and a clocked line of 1,023 or 4,095 buckets with nonlinear charge transfer and bucket noise. TIME controls the bucket clock with built-in glide, so parameter locks and LFOs on TIME bend the pitch of the repeats.

## Access

Select a track, press FX2, and choose BBD DELAY from the effect list. SPRING REV and PLATE REV are removed from the chooser, while DARK REV remains available. BBD DELAY is only available in FX2 because the delay line requires the FX2 slot's memory.

This module is not included in the standard remixes; build the `bbd` remix to use it.

![FX2 SETUP with BBD selected.](../../img/bbd/setup.png)

*FX2 SETUP with BBD selected.*

## Operation

- TIME ranges from 50 to 200 ms when STGS is set to 1024, and from 200 to 800 ms when STGS is set to 4096. It is free-running rather than tempo-synced.
- MIX at 0 passes the dry signal unchanged. From 0 to 64, the wet signal rises to unity while the dry signal stays at full level; from 64 to 127, the dry signal fades out.
- With TONE centered, increasing FDBK lengthens the repeats up to 127 without self-oscillating. With TONE turned toward either extreme, the loop self-oscillates starting around FDBK 40, with LIM controlling the maximum level.
- Turning TONE right of center brightens the repeats by boosting treble and cutting bass. Turning TONE left of center adds a resonant peak whose frequency is set by FREQ. FREQ has no effect when TONE is centered or turned to the right.
- LIM defaults to its maximum setting of 127, where the feedback governor reins in loud repeats early so self-oscillation stays quiet. Lowering LIM allows louder repeats to retain more feedback, making delays build up harder and self-oscillation louder and more aggressive. Setting LIM to 0 disables the governor completely. Quiet echoes sound identical at any LIM setting.
- FRZ fades out the delay input and extends the feedback tail; at 127, the delay line loops its current contents indefinitely.
- Changing STGS fades out the wet signal, clears the delay line, and fades back in.
- Pressing STOP three times cuts the BBD tail just as it cuts stock reverb tails, leaving the track dry until it is triggered again.
- The wet signal is mono, while the dry signal remains stereo.

## Parameters

![BBD main page.](../../img/bbd/main.png)

*BBD main page.*

| Page | Knob | Range | What it does |
|---|---|---|---|
| 1 | TIME | 0-127 | Bucket clock controlling delay time, with glide |
| 1 | FDBK | 0-127 | Wet signal fed back through TONE |
| 1 | FRZ | 0-127 | Freeze control; 127 loops the delay line |
| 1 | TONE | -64-63 | Feedback tilt (±9 dB): right brightens, left adds a resonant peak at FREQ |
| 1 | FREQ | 0-127 | Center frequency for TONE's left-hand peak (400 Hz to 2 kHz); inactive when TONE is centered or right |
| 1 | MIX | 0-127 | Dry/wet blend; 0 is dry only |
| 2 | STGS | 1024, 4096 | Bucket stage count, setting the delay time range |
| 2 | LIM | 0-127 | Feedback governor (default 127); lower values allow louder repeats and self-oscillation; 0 turns it off |
| 2 | HPF | 0-127 | Input high-pass filter (20 to 400 Hz); 0 is off |
