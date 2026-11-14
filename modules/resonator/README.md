# `resonator` — RESONATOR

FX1 station: **4 pitched bandpasses** (Torso S-4 RING filterbank idea, not
a modal / Rings body). Wet is the input through four constant-peak bandpass
peaks. Per-band **GN** levels sit on page 1; pitches, **SCAL** (gain scale),
and **LIM** (post-MIX peak limiter) live on FX SETUP. SCAL 8 is the tame
default (GN 64 = 0 dB); SCAL 127 restores build-TN smash headroom. LIM 0 is
off; raise it to catch smash peaks. DECY narrows the bands.

Buffer-free (state in r7). `Claims(fx1_only=True)`: FX2 instances dry-pass;
the FX2 chooser hides the row. FX id **`0x1e`**.

The page descriptor is cloned from **DARK REV**.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | GN1 | 0–127 | band 1 level; 64=unity at SCAL 8 |
| 1 | 1 | GN2 | 0–127 | band 2 |
| 1 | 2 | GN3 | 0–127 | band 3 |
| 1 | 3 | GN4 | 0–127 | band 4 |
| 1 | 4 | DECY | 0–127 | high = longer ring / less drive |
| 1 | 5 | MIX | 0–127 | dry/wet; 127 = bands only |
| 2 | 6 | PIT1 | 0–127 | band 1 centre ~40 Hz … ~4 kHz |
| 2 | 7 | PIT2 | 0–127 | band 2 centre |
| 2 | 8 | PIT3 | 0–127 | band 3 centre |
| 2 | 9 | PIT4 | 0–127 | band 4 centre |
| 2 | 10 | SCAL | 0–127 | gain scale; 8=tame, 127≈smash |
| 2 | 11 | LIM | 0–127 | peak limiter after MIX; 0 off |

## Stock 1.40C and a saved Part

Slots are DARK REV's layout under these names. A Part saved with RESONATOR
and loaded on stock 1.40C shows **DARK REV** with:

| slot | RESONATOR | stock DARK REV reads |
|---|---|---|
| 0 | GN1 | TIME |
| 1 | GN2 | SHVG |
| 2 | GN3 | SHVF |
| 3 | GN4 | HP |
| 4 | DECY | LP |
| 5 | MIX | MIX |
| 6 | PIT1 | PRE |
| 7 | PIT2 | BAL |
| 8 | PIT3 | MONO |
| 9 | PIT4 | (blank on stock) |
| 10 | SCAL | (blank on stock) |
| 11 | LIM | MIXF |

Saving that bank on stock writes those DARK REV values back; keep a
separate project copy if you need to return to stock without rewriting
the Part.

## Measured

- Render gates in `tools/verify/verify_resonator.py` (SCAL 8 max-knob rail
  fraction < 5%, SCAL 127 + LIM 127 peak under ~0.76 FS with rail fraction
  < 5%, no-runaway, two FX1 instances).
- LIM curve: ceiling `0.75 - LIM*0.5/128` (≈ -2.5..-12 dB).
  Same as SHATTER. LIM 0 bypasses attenuation so MIX 0 stays bit-exact dry.
- Earlier hardware (pre-LIM): Ilia's MKII, tip of PR #806 as **`RESON RR`**
  / BUILD RR, 19 Oct 2026. Page-1 GN1–4, DECY low and high, MIX; page-2
  PIT1–4; SCAL 8 and 127; FX2 dry-pass; two FX1 instances. This tip is
  Proof.CHECK until LIM is confirmed on a unit.

## Gates

`tools/verify/verify_resonator.py` (manifest `Gate`).

## Sources

- Torso S-4 RING — behaviour target (filterbank, not modal reverb).
- JOS two-zero constant-peak bandpass / Spectrum VOWL form (MIT).

## Current limiter

The shared implementation in `tools/remix/peak_limiter.py` measures both
channels of the current mixed block, then applies one attenuation in a
second pass. This catches the first transient, including at block boundaries.
No makeup gain is applied. Below the ceiling, dry input stays bit-exact
unless a preceding hot block is still releasing. LIM 0 bypasses attenuation
and clears the release state. LIM 1..127 sets a ceiling from about -2.5 to -12 dBFS.
The release is approximately 63 ms at 15 frames per block.

The earlier -18 dB maximum and previous-block gain are superseded. Hardware
reports above describe that earlier implementation. The new limiter awaits
a unit test. Regression renders cover signed transients at block boundaries,
quiet unity gain, stereo balance, and bypass.
