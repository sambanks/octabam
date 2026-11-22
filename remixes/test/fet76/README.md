# test/fet76

FET76 (`modules/fet76`, modelled on the UREI 1176LN FET limiting amplifier) on FX1 and FX2, beside the stock
effects; CHORUS, SPATIALIZER, PLATE REV and SPRING REV are left out for its words.

`make check REMIX=test/fet76`. Gate: `tools/verify/verify_fet76.py` (dsp_host, bit-exact against
`modules/fet76/fet76_ref.fixed()`). This remix has not run on a unit.
