| CX OSC -- selection guard limits (from synth 2.15). Values only.
| The MONO build keeps its six-track cap. POLY uses four; five-track POLY
| measurements and their limits are recorded in modules/cxosc/README.md.
        .if CX_POLY
        .set    ML_FM_MAX, 4             | POLY cap after reported freeze at five tracks
        .else
        .set    ML_FM_MAX, 6             | historical MONO cap (CX-CF 69)
        .endif
        .set    ML_SY_MAX, 2             | unused (HAVE_SYDRUM 0)
        .set    ML_SY_WITH_FM, 1         | unused
