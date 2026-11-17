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

## Measured

- On 8thmyth's MKI (personal build T9, boot METALFNGRZ, 2026-11-17): a take near 73.5 BPM chopped by hand three times read `BPM 73 (146)`, `73 (147)` and `74 (148)`, each within 1%; each popup followed the count and closed on the next key.
- Offline, on 27 takes with a known tempo (2026-11-16): the first number was within about 1 BPM on 18 and the bracket on 3 more (21 of 27, 78%).
- Under the port (`tools/verify/verify_chop_tempo.py`): all 46 recorded cases produce the line from `chop_tempo_int.py`; one reading costs at most 6.2 million instructions (median 3.1 million, test/chop-tempo; interrupts counted, so an upper bound). A real chop shows `8 SLICES` then `BPM 150 (75)`, still up 3 s later, with the slices unchanged.

## Inferred / open

- Takes chopped at the player's own pace have no tempo in their spacing; the popup then shows the best fit, which can be wrong.
- Swung material and chops made with ZERO SNAP on were not measured.
- No unit run of the final integer build; the evidence level is EMULATOR until that is done.
