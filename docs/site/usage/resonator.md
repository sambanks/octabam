**Four pitched bandpasses** on the input. A Torso S-4 **RING**-style filter
bank. Wet is the dry pushed through four constant-peak bandpasses. **PIT1–PIT4**
are on the main page. Band gains, **SCAL**, and **LIM** live on SETUP.
**`[FX1]`** only.

![RESONATOR: four BPs sum into SCAL, MIX with dry, then LIM.](../../img/resonator/path.svg)

## Access

Select a track, press **`[FX1]`**, pick **RESONATOR**. The **`[FX2]`**
chooser does not list it.

## Operation

- **PIT1-PIT4.** Band centres (~40 Hz to ~4 kHz).
- **GN1-GN4.** Per-band level on SETUP. Four bands at 64 can overload their
  summed output; lower or mute bands for a cleaner sound.
- **SCAL.** Overall gain scale. **0** mutes the bands. Values 1–127 rise
  smoothly, and 127 reaches the gain that the old scale reached at 70. Four
  bands at GN 64 can still overload. The filter-bank sum can distort before
  **LIM**; lower **SCAL** or **GN1–GN4** if that happens.
- **LIM.** Stereo peak limiter after **MIX**. **0** is off. At 127 the output
  ceiling is about -20 dBFS. It cannot remove distortion already created
  inside the filter bank.
- **DECY.** High = narrower peaks / more ring. The upper resonance range has
  more knob travel. The strongest resonance and its overdrive remain available.
- **MIX.** 127 = bands only. **0 = exact passthrough** when **LIM** is 0.

## Parameters

| Knob | Range | Default | What it does |
|---|---|---|---|
| PIT1 | 0..127 | 32 | band 1 centre |
| PIT2 | 0..127 | 48 | band 2 centre |
| PIT3 | 0..127 | 64 | band 3 centre |
| PIT4 | 0..127 | 80 | band 4 centre |
| DECY | 0..127 | 127 | resonance / bandwidth |
| MIX | 0..127 | 127 | dry/wet; 127 = bands only |
| GN1 | 0..127 | 64 | band 1 level, SETUP |
| GN2 | 0..127 | 64 | band 2, SETUP |
| GN3 | 0..127 | 64 | band 3, SETUP |
| GN4 | 0..127 | 64 | band 4, SETUP |
| SCAL | 0..127 | 1 | smooth gain scale; 0=mute, 127=former SCAL 70 maximum |
| LIM | 0..127 | 0 | peak limiter after MIX; 0 off, max ≈ -20 dB |

**LIM** leaves quiet passages at their original level. Higher settings lower
the peak ceiling from about -2.5 to -20 dBFS. It adds no makeup gain. Hot
signals see progressive gain reduction. At LIM max, block peaks cap at about
-20 dBFS. Turning **LIM** to 0 releases any active attenuation back to unity
over about 63 ms. Starting at 0 skips limiter attenuation.

After updating, check Parts saved with an earlier RESONATOR layout. The
values in slots 0–3 and 6–9 now control different parameters.
