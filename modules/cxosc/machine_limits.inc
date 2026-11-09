| CX OSC -- selection guard limits (from synth 2.15). Values only.
| MKII CX-CF 69 (author, 9 Nov 2026), CF METER over USB: baseline idle 44.7 % /
| ISR 125 us; 4x CX idle 21.8 % / 272 us; 6x idle ~12 % / 309 us (max past the
| 363 us frame); 7x idle 0 % / ISR mean 355 us max 446 us — wall. Cap at 6.
        .set    ML_FM_MAX, 6             | measured headroom on MKII (see comment)
        .set    ML_SY_MAX, 2             | unused (HAVE_SYDRUM 0)
        .set    ML_SY_WITH_FM, 1         | unused
