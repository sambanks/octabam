# `mute-modes` -- MUTE_MODES

PERSONALIZE > MUTE MODE chooses what a muted or soloed-out audio track does: OT (stock, an instant cut after the FX), OTFX (the dry sound cuts, FX tails ring out, the sequencer keeps running), OTFX-T (as OTFX, new trigs suppressed), DT-T (the sounding note plays out on its amp envelope, new trigs suppressed). Default OT.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `826d23e`). `Kind.CF_PATCH`. Two linked units (`patch_softmute.s`, `patch_mutemode.s`; ROM caves or DRAM by the `PLACE` setting, default CAVE), six `jmp` detours, three `TableGrow`s for the PERSONALIZE label, getter and setter arrays, and four pokes: the row count at `0x40068fb2` (15 to 16 on an MKI, 16 to 17 on an MKII) and the three ANDY restore widenings `pea 0x64` to `pea 0x70`. The tables are grown with `insert_at=2`: MUTE MODE is row 2, after PREVIEW WITHOUT FX, as in the author's standalone build; LED BRIGHTNESS stays the last row, shown on an MKII only.
`upstream/octabam-modules/mute-modes/README.md` is the full description, with what was measured and what was inferred.

## Measured

- Every build re-links each cave or unit and compares it with the author's
  own bytes (`reference`); a difference refuses the build.
- `make check REMIX=mute-modes` (`remixes/test/mute-modes/`) builds and boots the
  image under the ColdFire port.

## On the unit

- On the author's MKI (standalone image, the KYOTI V1.7 combined image, and this octabam form beside SIDECHAIN_COMPRESSOR as OCTABAM37, 1 Nov 2026).

## Notes

- 1 Oct 2026: on the author's MKI in an octabam image with all six KYOTI modules: MUTE MODE at row 2, all four modes, and the setting surviving a power-cycle.
- 26 Oct 2026 (pin `a1e0288`): `pre`'s per-frame SHADOW byte moved from SRAM `0x80006c66` into `mm_softmute` itself. `0x80006924..0x80007873` is the work area of the stock timestretch task (prio 1, entry `0x40098a5c`): its splice search refills it with audio on every grain while tracks play, so OTFX could read back an audio byte and skip a mute's note-off, and the per-frame write landed in the search window. The references changed with it (the plain unit 968 to 970 B, the SC_KEY unit unchanged in size). On the author's MKI: the standalone image, its Bugbuild and the KYOTI V1.6 image, all good. This octabam form has not been flashed.
- 2 Nov 2026 (pin `826d23e`): KEYHOLD, with SIDECHAIN_COMPRESSOR only. A muted track that a COMPRESSOR uses as its KEY plays its trigs, cut after the FX as on stock. When KEY moved to another track, the muted track went back to its MUTE MODE, and DT-T leaves a sounding voice alone, so the note it had started as a KEY was heard to its end (a looping sample: on and on). OTFX-T and OTFX let one frame through. A muted track that has been a KEY now keeps the cut until it is unmuted; its trigs are still dropped. The SC_KEY unit grows 1086 to 1100 B and its reference is now KYOTI V1.7's placement (`ac03f559…` at `0x400d6e54`); the plain unit is unchanged. On the author's MKI: this octabam form (OCTABAM37, octabam `bc144523` with the same `mm_softmute` source) in DT-T, and the KYOTI V1.7 image, all good (reported in #934).
- Beside SIDECHAIN_COMPRESSOR, a muted track that a COMPRESSOR uses as its KEY keeps feeding it, as on stock: `patch_softmute.s` includes the unit's `remix.inc`, which carries `.set SC_KEY,1` only when SIDECHAIN_COMPRESSOR is in the remix, and `reference` names that variant (the KYOTI V1.7 image's bytes at `0x400d6e54`). `make check REMIX=kyoti-mute-sidechain` builds it. On the author's MKI, 4 Oct 2026, in an octabam image with SIDECHAIN_COMPRESSOR: a muted KEY keeps ducking in every MUTE MODE.
