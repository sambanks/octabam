| CX OSC -- selection guard limits (from synth 2.15). Values only.
| Six CX OSC tracks are safe only with SETUP MOD morph at 0 on every CX track.
| Nonzero MOD morph costs more ColdFire time; no six-track allowance there.
        .set    ML_FM_MAX, 6             | hardware-qualified cap when MOD morph is 0
        .set    ML_SY_MAX, 2             | unused (HAVE_SYDRUM 0)
        .set    ML_SY_WITH_FM, 1         | unused
