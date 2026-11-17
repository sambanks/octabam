# chop-tempo

## What this changes

Adds the LAZY CHOP TEMPO module, which displays a BPM popup after pressing [YES] in LAZY CHOP mode. The popup shows the tempo the chops point to (e.g., `BPM 115 (58)`), follows LAZY CHOP's slice-count popup, and stays until the next keypress (which still performs its own function). No data is written to the sample.

## Modules

- `modules/chop-tempo/` — LAZY CHOP TEMPO BPM display

## Remixes reached

This module is selected via LAZY CHOP's `select` key, which defines `LC_TEMPO`. It carries alongside LAZY CHOP and is selected when LAZY CHOP is active. No separate remix is needed; it activates within any remix that includes LAZY CHOP.

## Measured / inferred

- **On 8thmyth's MKI** (personal build T9, boot name METALFNGRZ, 17 Nov 2026): one sample of about 73.5 BPM chopped by hand three times read `BPM 73 (146)`, `73 (147)` and `74 (148)`, each within 1%; the spread is the player's timing (about 10 ms between takes). Each popup came after the count and closed on the next key, which still acted.
- **Offline, on 27 of 8thmyth's takes with a known tempo** (16 Nov 2026): the first number was within about 1 BPM on 18 and the bracket on 3 more (21 of 27, 78%). The six misses: three takes chopped at the player's own pace rather than the beat, off-beat chops pointing to a neighbour (94 for 134), 175 for 178, and one early take.
- **Under the port** (`tools/verify/verify_chop_tempo.py`): `tempo` feeds all 46 recorded takes through the module's code; every line equals the reference's. One reading costs at most 6.2 million instructions (median 3.1 million, test/chop-tempo; interrupts counted, so an upper bound). `tempopop`: a real 8-tap chop, YES: `8 SLICES`, then `BPM 150 (75)`, still up 3 s later; the slices are untouched.
- **Inferred**: Takes chopped at the player's own pace have no tempo in their spacing; the popup then shows the best fit, which can be wrong. Swung material, and chops with ZERO SNAP on, were not measured.

## Gates (on a tree rebased onto current main)

- `make reach` (quick unless `FULL=1` is chosen)
- `make check REMIX=chop-tempo`:
- `make test-acceptance`:
- `make accept REMIX=chop-tempo …`:
- `scripts/refhash.sh check` (build changes):
- `make verify-docs` (manifest, remix selection or docs changes): passes when `docs/site/usage/chop-tempo.md` is present and `make docs` runs successfully

## Manual site

- [x] `docs/site/usage/chop-tempo.md` added or updated (new module or a user-visible change)
- [ ] Screenshots re-captured when the UI changed, or main changed a screen a capture shows (`docs/contributing/SCREENSHOTS.md`): groups, project and remix run:
- [ ] `mkdocs build --strict --config-file docs/site/mkdocs.yml` passes

## Hardware

- Unit: 8thmyth's MKI, build T9, boot name METALFNGRZ
- Not flashed; OS 1.40C used for build time only

## Checklist

- [x] No Elektron bytes in the diff (no image, slice, `.syx`, or firmware dump)
- [x] Submodule pin changes name the upstream commit and why (N/A — no submodules changed)
- [x] The module README says what was measured and what was inferred
- [x] No selectable configuration (instance count, tracks, parameters, remix combination) crashes or degrades the unit; the guard is named in the module README
- [x] This module does not duplicate the function of an accepted module
- [x] Generated docs are current: `make docs` then `make verify-docs` passes (CI refuses stale READMEs)

---

**Related:** Closes #1099 (linking the new PRs once all five are pushed). Depends on LAZY CHOP being merged first (LAZY CHOP TEMPO calls `lc_finish` → `ct_after_yes` after its count popup).
