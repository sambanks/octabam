# `reload-from-project` -- RELOAD_FROM_PROJECT

Reload one track's sequence from the CF card without stopping the transport: `[PTN]` + `[TRACK n]` reloads that track's card-saved sequence with the Part untouched; `[BANK]` + `[TRACK n]` also re-applies the saved Part. A toast confirms.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `223ac58`). `Kind.CF_PATCH`. One DRAM unit (`patch_reload3.s`, `Linked(dram=True)`) and six `jmp` detours. A remix with this module carries the platform loader and its 10 MiB arena reserve, unless another DRAM module already brings them.
`upstream/octabam-modules/reload-from-project/README.md` is the full description, with what was measured and what was inferred.

## Measured

- Every build re-links each cave or unit and compares it with the author's
  own bytes (`reference`); a difference refuses the build.
- `make check REMIX=reload-from-project` (`remixes/test/reload-from-project/`) builds and boots the
  image under the ColdFire port.

## On the unit

- On the author's MKI, including that the sequencer and the internal metronome keep their phase.
- 1 Oct 2026: from DRAM, in an octabam image with all six KYOTI modules (OBKYOTI6), both chords; and (OBKYOTI7) the knobs now show the reloaded Part's values straight after `[BANK]` + `[TRACK n]`.
- 16 Oct 2026 (`223ac58`): `[CUE]` + `[TRACK n]` is stock cue again. It used to reload the track: the `0x40083dc4` detour is `[CUE]`'s held sub-map TRACK handler, not a `[PTN]` overlay, and it now reloads only with `[PTN]` held (the panel row). Fixed by Ilia Murzinov (Zac-Kyoti/octatrack-kyoti-fw#3), on an MKII, standalone image.

## Notes

- All-tracks and whole-bank reload are not implemented.
- Octakit's conflict is dropped: Octakit is not in octabam since 6 Oct 2026 (KITS replaces it and plays through the stock Part slots), so `[BANK]` + `[TRACK n]` calls stock Part RELOAD (`0x4004aab4`) from the unit untouched. The call is not a `Detour`, so the ledger cannot see it; the handoff record is `upstream/reference/handoffs/DIRECTJUMP_OCTAKIT_SCOPE.md`.
