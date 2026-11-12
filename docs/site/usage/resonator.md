**Four pitched bandpasses** on the input. A Torso S-4 **RING**-style filter
bank. Wet is the dry pushed through four constant-peak bandpasses. Pitches
and a makeup scale live on SETUP. **`[FX1]`** only.

![RESONATOR: four BPs sum into SCAL, then MIX with dry.](../../img/resonator/path.svg)

## Access

Select a track, press **`[FX1]`**, pick **RESONATOR**.

## Operation

- **GN1-GN4.** Per-band level (64 = unity when **SCAL** is 8).
- **PIT1-PIT4.** Band centres (~40 Hz to ~4 kHz).
- **SCAL.** Overall gain scale. **8 = tame**, 127 ≈ hot smash (~×16 at
  GN 64). **SCAL** 127 hard-clips ordinary input. Stay near 8 unless you
  want that.
- **DECY.** High = narrower peaks / more ring. Still short.
- **MIX.** 127 = bands only. **0 = exact passthrough**.

## Parameters

| Knob | Range | Default | What it does |
|---|---|---|---|
| GN1 | 0..127 | 64 | band 1 level |
| GN2 | 0..127 | 64 | band 2 level |
| GN3 | 0..127 | 64 | band 3 level |
| GN4 | 0..127 | 64 | band 4 level |
| DECY | 0..127 | 127 | resonance / bandwidth |
| MIX | 0..127 | 127 | dry/wet; 127 = bands only |
| PIT1 | 0..127 | 32 | band 1 centre |
| PIT2 | 0..127 | 48 | band 2 centre |
| PIT3 | 0..127 | 64 | band 3 centre |
| PIT4 | 0..127 | 80 | band 4 centre |
| SCAL | 0..127 | 8 | gain scale; 8=tame, 127≈smash |
