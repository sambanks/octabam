RESONATOR is a four-band pitched bandpass filter bank inspired by the Torso
S-4 **RING** effect. The wet signal runs the input through four constant-peak
bandpass filters. **PIT1–PIT4**, **DECY**, and **MIX** are on the main page,
while band gains (**GN1–GN4**), **SCAL**, and **LIM** are on the SETUP page.
It is available in **`[FX1]`** only.

![RESONATOR: four BPs sum into SCAL, MIX with dry, then LIM.](../../img/resonator/path.svg)

## Access

Select a track, press **`[FX1]`**, and choose **RESONATOR**. It is not listed
in the **`[FX2]`** chooser.

## Operation

- **PIT1–PIT4**: Sets the centre frequencies of the four bands (from roughly
  40 Hz to 4 kHz).
- **GN1–GN4**: Sets each band's level on the SETUP page. Running all four
  bands at 64 can overload their summed output, so lower or mute bands for a
  cleaner sound.
- **SCAL**: Sets the overall output gain of the filter bank. **0** mutes the
  bands, while values 1–127 rise smoothly, with 127 matching the gain that 70
  produced on the earlier scale. Four bands at GN 64 can still overload and
  distort the filter-bank sum before **LIM**; lower **SCAL** or **GN1–GN4** if
  that happens.
- **LIM**: A stereo peak limiter placed after **MIX**. **0** turns it off, and
  127 lowers the output ceiling to about -20 dBFS. Because it sits after the
  mix stage, it cannot remove distortion that already occurred inside the
  filter bank.
- **DECY**: Controls resonance and bandwidth, where higher values produce
  narrower peaks and a longer ring. The upper resonance range has finer knob
  resolution, while keeping the strongest resonance and overdrive available.
- **MIX**: Blends dry and wet signals. 127 outputs the filter bands only, and
  **0** is an exact passthrough when **LIM** is 0.

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

**LIM** leaves quiet passages at their original level and applies no makeup
gain. Raising it lowers the peak ceiling progressively from about -2.5 dBFS to
-20 dBFS, so hot signals receive increasing gain reduction and block peaks cap
at roughly -20 dBFS at maximum. Turning **LIM** back to 0 releases any active
attenuation smoothly to unity over about 63 ms, while starting with **LIM** at
0 bypasses attenuation completely.

After updating, check Parts saved with an earlier RESONATOR layout, because
slots 0–3 and 6–9 now control different parameters.
