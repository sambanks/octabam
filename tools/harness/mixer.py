#!/usr/bin/env python3
"""The unit's gain chain around the DSP -- measured under the ColdFire port.

Every curve here was fitted on the port's own taps (`tools/scratch/mixer_sweep.py`,
12 Sep 2026, COLDFIRE_PORT.md O14): T1 THRU with FX1 = SEND and FX2 = EQUALIZER
flat on Sam's RIG, master track off, one byte of the part changed per run,
the chain INPUT (the 84-word track record's audio), the chain OUTPUT (the
core's read-back slot) and TX0 (the ESAI's main pair) fitted against each
other per 200-sample window with a lag, the median taken. Residuals are
-100 dB and better on every point, so a curve that misses a point by more
than a few thousandths of a dB is the wrong curve, not noise.

    stem (the voice, or the THRU input)
      x (VOL/127)^2                 AMP VOL, pre-FX, on the DSP  (9 points)
      x bal(BAL)                    AMP BAL, pre-FX, on the DSP  (11 points)
      -> FX1 -> FX2                 the chain `dsp_host` runs
      x (LEVEL/128)^2               track LEVEL, post-FX, at the mix (5 points)
      -> sum                        the main out (TX0)

Measured on a THRU track. That the same AMP stage sits in front of a FLEX or
STATIC voice's chain is INFERRED from the DSP receiving the AMP page in the
same per-instance words for every machine (O9d, `00 7f 7f 40 40 7f` at +0..5)
-- falsifier: the O10 kick fixture with AMP VOL 32, expecting -12.0 dB at the
read-back. The main level (SET MAIN LEVEL, the `0x80003c60` table) scales
trigged voices and not THRUs (O9c); it is not modelled -- unity, which O10's
sample-exact kick at `--main-level 64` supports and does not prove.
"""

VOL_DEFAULT, BAL_DEFAULT, LEVEL_DEFAULT = 64, 64, 108   # the part's own defaults


def vol_gain(vol):
    """AMP VOL 0..127 -> linear gain, pre-FX. (64/127)^2 = -11.906 dB is O9d's
    k = 2130129/2^23; 127 -> -0.001 dB; 0 -> silence."""
    v = max(0, min(127, int(vol)))
    return (v / 127.0) ** 2


def bal_gains(bal):
    """AMP BAL 0..127 -> (gain_L, gain_R), pre-FX. A BALANCE, not a pan: the
    near side stays at unity and the far side falls on a cubic that reaches
    exactly zero at the end stop. Measured for the right half (L attenuated,
    d = BAL - 64 = 8..48 and 63); the left half is its MIRROR, inferred
    (falsifier: the same sweep with the tone on the THRU's right input)."""
    b = max(0, min(127, int(bal)))
    if b == 64:
        return 1.0, 1.0
    if b > 64:
        d = b - 64
        return _far(d), 1.0
    d = 64 - b                      # 1..64: BAL 0 is the end stop, silence on R
    return 1.0, (_far(d) if d < 64 else 0.0)


def _far(d):
    return ((63 - d) / 63.0) * ((64 - d) / 64.0) * ((127 + d) / 127.0)


def level_gain(level):
    """Track LEVEL 0..127 -> linear gain, post-FX at the mix. 108 (the default)
    = -2.952 dB, 127 = -0.137 dB = (127/128)^2 exactly."""
    lv = max(0, min(127, int(level)))
    return (lv / 128.0) ** 2


# The measured points (k / 2^23 at the chain output for 1.0 in, TX0 over
# chain-out for the mixer), kept beside the curves so `selftest()` can say
# when a curve drifts from what the port measured.
MEASURED_VOL = {0: 0, 16: 133104, 32: 532512, 48: 1198176, 64: 2130128, 80: 3328320,
                96: 4792800, 112: 6523552, 127: 8387936}
MEASURED_BAL_FAR_Q23 = {64: 2130128, 72: 1729712, 80: 1342080, 88: 980000, 96: 656256,
                        104: 383616, 112: 174880, 127: 192}          # at VOL 64, the L side
MEASURED_LEVEL_DB = {32: -24.083, 64: -12.042, 100: -4.289, 108: -2.952, 127: -0.137}


def selftest(tol_db=0.02):
    import math
    db = lambda x: 20 * math.log10(x) if x > 0 else -200.0
    worst = 0.0
    for v, q in MEASURED_VOL.items():
        if q:
            worst = max(worst, abs(db(vol_gain(v)) - db(q / 8388608.0)))
    for b, q in MEASURED_BAL_FAR_Q23.items():
        if b == 127:
            assert bal_gains(b)[0] == 0.0
            continue
        worst = max(worst, abs(db(bal_gains(b)[0]) - db(q / MEASURED_BAL_FAR_Q23[64])))
    for lv, d in MEASURED_LEVEL_DB.items():
        worst = max(worst, abs(db(level_gain(lv)) - d))
    if worst > tol_db:
        raise AssertionError(f"mixer model drifts {worst:.3f} dB from the port's measurement")
    return worst


if __name__ == "__main__":
    print(f"mixer model within {selftest():.4f} dB of every measured point")
