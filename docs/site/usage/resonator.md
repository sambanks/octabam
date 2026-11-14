**Four pitched bandpasses** on the input. A Torso S-4 **RING**-style filter
bank. Wet is the dry pushed through four constant-peak bandpasses. Pitches,
**SCAL**, and **LIM** live on SETUP. **`[FX1]`** only.

![RESONATOR: four BPs sum into SCAL, MIX with dry, then LIM.](../../img/resonator/path.svg)

## Access

Select a track, press **`[FX1]`**, pick **RESONATOR**. The **`[FX2]`**
chooser does not list it.

## Operation

- **GN1-GN4.** Per-band level. Four bands at 64 can overload their summed
  output; lower or mute bands for a cleaner sound.
- **PIT1-PIT4.** Band centres (~40 Hz to ~4 kHz).
- **SCAL.** Overall gain scale. **8 = conservative starting point**, 127 ≈
  hot smash (~×16 at GN 64). The filter-bank sum can distort before **LIM**;
  lower **SCAL** or **GN1–GN4** if that happens.
- **LIM.** Stereo peak limiter after **MIX**. **0** is off. It catches hot
  output peaks, but cannot remove distortion already created by high **SCAL**
  inside the filter bank.
- **DECY.** High = narrower peaks / more ring. Still short.
- **MIX.** 127 = bands only. **0 = exact passthrough** when **LIM** is 0.

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
| LIM | 0..127 | 0 | peak limiter after MIX; 0 off, 1..127 ≈ -2.5..-12 dB |

**LIM** leaves quiet passages at their original level. Higher settings lower
the peak ceiling from about -2.5 to -12 dBFS. It adds no makeup
gain. Hot signals see progressive gain reduction. At LIM max, block peaks cap
at about -12 dBFS.
