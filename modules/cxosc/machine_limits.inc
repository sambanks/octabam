| CX OSC -- selection guard limits (from synth 2.15). Values only.
| The cap of six was measured with SETUP MOD morph at 0. MOD/CAR morph,
| PWM, FDBK, INDX, DEC and FOLD all engaged: four tracks fit, five overrun
| (CX B1, 26 Nov 2026). The guard counts tracks, not knobs.
        .set    ML_FM_MAX, 6             | hardware-qualified cap when MOD morph is 0
        .set    ML_SY_MAX, 2             | unused (HAVE_SYDRUM 0)
        .set    ML_SY_WITH_FM, 1         | unused
