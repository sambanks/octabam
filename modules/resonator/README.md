# `resonator` — RESONATOR

FX1 station: **4 pitched bandpasses** (Torso S-4 RING filterbank idea, not
a modal / Rings body). Wet is the input through four constant-peak bandpass
peaks. **PIT1–PIT4** are on the main page for live tuning. Per-band **GN**
levels, **SCAL** (gain scale), and **LIM** (post-MIX peak limiter) live on FX
SETUP. The upper part of **DECY** spreads resonance over more knob travel;
the strongest resonance and its overdrive remain available. The filter-bank sum can still
distort before LIM. Lower SCAL or GN1–GN4 to avoid pre-limiter distortion.

Buffer-free (state in r7). `Claims(fx1_only=True)`: FX2 instances dry-pass;
the FX2 chooser hides the row. FX id **`0x1e`**.

The page descriptor is cloned from **DARK REV**.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | PIT1 | 0–127 | band 1 centre ~40 Hz … ~4 kHz |
| 1 | 1 | PIT2 | 0–127 | band 2 centre |
| 1 | 2 | PIT3 | 0–127 | band 3 centre |
| 1 | 3 | PIT4 | 0–127 | band 4 centre |
| 1 | 4 | DECY | 0–127 | high = longer ring / less drive |
| 1 | 5 | MIX | 0–127 | dry/wet; 127 = bands only |
| 2 | 6 | GN1 | 0–127 | band 1 level |
| 2 | 7 | GN2 | 0–127 | band 2 |
| 2 | 8 | GN3 | 0–127 | band 3 |
| 2 | 9 | GN4 | 0–127 | band 4 |
| 2 | 10 | SCAL | 0–127 | gain scale; 1=low-gain default, 127≈smash |
| 2 | 11 | LIM | 0–127 | peak limiter after MIX; 0 off, max ≈ -20 dBFS |

## Stock 1.40C and a saved Part

Slots are DARK REV's layout under these names. A Part saved with RESONATOR
and loaded on stock 1.40C shows **DARK REV** with:

| slot | RESONATOR | stock DARK REV reads |
|---|---|---|
| 0 | PIT1 | TIME |
| 1 | PIT2 | SHVG |
| 2 | PIT3 | SHVF |
| 3 | PIT4 | HP |
| 4 | DECY | LP |
| 5 | MIX | MIX |
| 6 | GN1 | PRE |
| 7 | GN2 | BAL |
| 8 | GN3 | MONO |
| 9 | GN4 | (blank on stock) |
| 10 | SCAL | (blank on stock) |
| 11 | LIM | MIXF |

Saving that bank on stock writes those DARK REV values back; keep a
separate project copy if you need to return to stock without rewriting
the Part.

## Sources

- Torso S-4 RING — behaviour target (filterbank, not modal reverb).
- JOS two-zero constant-peak bandpass / Spectrum VOWL form (MIT).

## Current limiter

The shared implementation in `tools/remix/peak_limiter.py` measures both
channels of the current mixed block, then applies one attenuation in a
second pass. This catches the first transient, including at block boundaries.
No makeup gain is applied. Below the ceiling, dry input stays bit-exact
unless a preceding hot block is still releasing. LIM 0 bypasses attenuation
and clears the release state. LIM 1..127 sets a ceiling from about -2.5 to -20 dBFS.
The release is approximately 63 ms at 15 frames per block.

The page move changes the meaning of saved RESONATOR slots 0–3 and 6–9.
Recheck Parts saved with an earlier RESONATOR build and save the updated
settings into a new Part.

Regression renders cover signed transients at block boundaries, quiet unity
gain, stereo balance, and bypass. The LM4 hardware check confirms the limiter
works in the tested RESONATOR setup; it does not measure its exact ceiling.
