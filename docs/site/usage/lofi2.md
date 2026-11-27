LOFI2 chains a ring modulator or stereo frequency shifter (SHIFT UP / SHIFT
DOWN) into sample-rate reduction, bit-depth reduction, and a high-shelf cut. It
uses its own FX2 slot ID so stock LO-FI remains available alongside it.

Its default values pass audio through untouched (MIX, FREQ, FDBK, SRR, and BRR
at 0, AMPH centred, and LPF at 127), so loading a fresh instance does not alter
the signal until you adjust a parameter.

## Access

Select a track, press FX2, and choose LOFI2 from the effect list. Page 1 has
FREQ, MIX, FDBK/GAIN, SRR, BRR, and LPF; Page 2 has RANGE, MODE, and AMPH. It
is not included in the official remixes; build the `lofi2` test remix to use
it.

## Operation

- MIX sets the modulator depth rather than a global dry/wet balance, so SRR and
  BRR remain active even when MIX is 0.
- MODE on page 2 selects RING, SHIFT DOWN, or SHIFT UP. Switching MODE briefly
  ducks the wet signal to avoid clicks.
- Setting LPF to 127 bypasses the high-shelf filter.
- Holding FUNCTION while turning a knob steps through musical presets one click
  at a time instead of jumping to the endpoints:
  - BRR steps through 24, 16, 12, 10, 8, 6, and 4 bits.
  - SRR steps through 22.05k, 16k, 11.025k, 8k, 5.5k, and 4k.
  - LPF steps its corner frequency through 100, 250, and 500 Hz, and 1, 2, 4,
    and 8 kHz.
  - MIX, FDBK/GAIN, and AMPH step in quarters (3 dB steps for GAIN, 45-degree
    steps for AMPH).
  - FREQ steps through C notes from C2 to C7 in RING mode with RANGE HIGH, and
    through octaves in all other combinations.
  - Each step list also includes both ends of the knob range.
- SHIFT uses more DSP than RING. Up to four SHIFT instances fit per core (the
  eight tracks are split across two cores), so all eight tracks can run cleanly
  in either RING or SHIFT mode. Any FX1 effect on the same track draws from the
  same core's budget.

## Parameters

| Page | Knob | Range | What it does |
|---|---|---|---|
| 1 | FREQ | 0..127 | Modulator frequency, exponential over six octaves with smooth sweeps |
| 1 | MIX | 0..127 | Modulator depth; crossfades the ring mod or shifter against the dry signal |
| 1 | FDBK / GAIN | 0..127 | Renamed by MODE: in SHIFT modes, FDBK controls the feedback ladder; in RING mode, GAIN boosts the ring level from 0 dB at 0 to +11.9 dB at 127 |
| 1 | SRR | 0..127 | Sample-rate reduction (sample-and-hold) matching stock LO-FI's rates: none through 7, 8,018 Hz at 64, and 3,564 Hz at 127 |
| 1 | BRR | 0..127 | Bit-depth reduction matching stock LO-FI's curve: 1 bit at 0, 3 bits at 16, up to 2^20.8 at 127 |
| 1 | LPF | 0..127 | High-shelf cut of -12 dB above a corner frequency from 100 Hz (0) to 16 kHz (126); 127 bypasses the filter |
| 2 | RANGE | LOW / HIGH | Base frequency for FREQ: 2 Hz / 60 Hz in RING mode, 2 Hz / 31.25 Hz in SHIFT modes |
| 2 | MODE | RING / DOWN / UP | Ring modulator, or frequency shifter moving partials down or up |
| 2 | AMPH | -64..+63 | Left/right phase offset for the ring carrier (-90 to +88.6 degrees, 0 at centre); RING mode only |
