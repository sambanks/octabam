# `mute-modes` -- MUTE_MODES

PERSONALIZE > MUTE MODE chooses what a muted or soloed-out audio track does: OT (stock, an instant cut after the FX), OTFX (the dry sound cuts, FX tails ring out, the sequencer keeps running), OTFX-T (as OTFX, new trigs suppressed), DT-T (the sounding note plays out on its amp envelope, new trigs suppressed). Default OT.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `7c2fe04`). `Kind.CF_PATCH`. Two linked ROM units (`patch_softmute.s`, `patch_mutemode.s`), six `jmp` detours, three `TableGrow`s for the PERSONALIZE label, getter and setter arrays, and four pokes: the row count at `0x40068fb2` (15 to 16 on an MKI, 16 to 17 on an MKII) and the three ANDY restore widenings `pea 0x64` to `pea 0x70`. The tables are grown with `insert_at=2`: MUTE MODE is row 2, after PREVIEW WITHOUT FX, as in the author's standalone build; LED BRIGHTNESS stays the last row, shown on an MKII only.
`upstream/octabam-modules/mute-modes/README.md` is the full description, with what was measured and what was inferred.

## Measured

- Every build re-links each cave or unit and compares it with the author's
  own bytes (`reference`); a difference refuses the build.
- `make check REMIX=mute-modes` (`remixes/test/mute-modes/`) builds and boots the
  image under the ColdFire port.

## On the unit

- On the author's MKI (standalone image and the KYOTI V1.0 combined image).

## Notes

- 1 Oct 2026: on the author's MKI in an octabam image with all six KYOTI modules: MUTE MODE at row 2, all four modes, and the setting surviving a power-cycle.
- Beside SIDECHAIN_COMPRESSOR, a muted track that a COMPRESSOR uses as its KEY keeps feeding it, as on stock: `patch_softmute.s` includes the unit's `remix.inc`, which carries `.set SC_KEY,1` only when SIDECHAIN_COMPRESSOR is in the remix, and `reference` names that variant (the KYOTI V1.0 image's bytes at `0x400d74e4`). `make check REMIX=kyoti-mute-sidechain` builds it.
