# LAZY CHOP TEMPO

After LAZY CHOP's [YES] and its slice-count popup, a second popup says the tempo the chops point to, for example `BPM 115 (58)`. The first number is the best-supported reading; the bracket holds a plausible neighbour (4:3, 3:2, half or double time). It stays until the next key, and that key still does its own job. Nothing is written to the sample.

Author: [8thmyth](https://github.com/8thmyth). ColdFire only, one linked DRAM unit (`choptempo.s`). Requires LAZY CHOP: the hook is LAZY CHOP's `lc_finish` under `LC_TEMPO`, built when this module is selected.

## How

The slice starts held by the slot record give the gaps between chops. `choptempo.s` scores them against every tempo from 60.0 to 200.0 BPM on a 16th / triplet grid, with a prior around 120 BPM, the take's length when it is a loop, and a plainer-neighbour check. The whole-number reference is `tools/hw/chop_tempo_int.py`; the float prototype it matches is `tools/hw/chop_tempo.py`. The UI task's popup countdown at `0x40056C30` is detoured so the reading happens once, when the count popup ends. `ct_inc` in the manifest builds the cos, prior and loop-agreement tables at build time.

## Guards

- One reading per [YES], at the end of LAZY CHOP's count popup; the next key closes the tempo popup and is not swallowed.
- At most 64 slice starts are read; a take with fewer than two chops produces no reading.
- The popup writes only the screen; the slice table, sample and project are untouched.
- The module cannot be selected without LAZY CHOP (`requires=("LAZY CHOP",)`).
