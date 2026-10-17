A bucket-brigade delay for FX2, in place of SPRING REV and PLATE REV. The
track's mono sum goes through a model of a BBD chip: a 2:1 compander,
anti-alias and reconstruction filters that follow the clock, and a clocked
line of 1,023 or 4,095 buckets with a charge-transfer curve and bucket
noise. TIME is the bucket clock and glides, so locks and LFOs on TIME bend
the pitch of the repeats.

## Access

An effect on a track: select the track, press FX2, and pick BBD DELAY from
the chooser. SPRING REV and PLATE REV are gone from the chooser; DARK REV
stays. FX2 only: the line needs the FX2 slot's memory. Not in an official
remix; build the test remix `bbd`. Hardware: played on the author's MKII,
both DSP cores, with save, reload and a power cycle (17 Oct 2026).

![FX2 SETUP with BBD selected.](../../img/bbd/setup.png)

*FX2 SETUP with BBD selected.*

## Operation

- TIME runs 50 to 200 ms with STGS 1024 and 200 to 800 ms with STGS 4096.
  It is free-running, not tempo-synced.
- MIX 0 is exact dry. Up to 64 the wet rises to unity over the whole dry;
  from 64 to 127 the dry fades out.
- With TONE centred, FDBK rings longer up to 127 but never self-oscillates.
  With TONE at either end the loop rings on from about FDBK 40, and LIM
  sets how loud.
- FRZ fades the input out and lengthens the trails; at 127 the line loops
  its own buckets exactly.
- A STGS change fades the wet out, clears the line and fades back in.
- STOP, STOP, STOP cuts BBD's tail as it cuts the stock reverbs': the track
  plays dry until it triggers again.
- The wet is mono; the dry stays stereo.

## Parameters

![BBD main page.](../../img/bbd/main.png)

*BBD main page.*

| Page | Knob | Range | What it does |
|---|---|---|---|
| 1 | TIME | 0-127 | the bucket clock: delay time, gliding |
| 1 | FDBK | 0-127 | the wet returned through TONE |
| 1 | FRZ | 0-127 | freeze; 127 loops the line |
| 1 | TONE | -64-63 | feedback tilt, ±9 dB: right brightens, left peaks at FREQ |
| 1 | FREQ | 0-127 | TONE's bandpass peak, 400 Hz to 2 kHz |
| 1 | MIX | 0-127 | dry and wet; 0 is exact dry |
| 2 | STGS | 1024, 4096 | bucket count: the delay range |
| 2 | LIM | 0-127 | feedback governor; 0 is off, 127 holds oscillation lowest |
| 2 | HPF | 0-127 | input high-pass, 20 to 400 Hz; 0 is off |
