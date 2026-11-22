# `varispeed` -- VARISPEED

STATIC and FLEX `TSTR` get a fifth position, VARI: the sample plays dry, tape-style, at
(project BPM × p) / (sample BPM × q), exact in integers, with an octave fold above 2×; RATE
still applies, and AUTO plays a sample whose ATTR TIMESTRETCH is VARI the same way. On a VARI
track `PTCH` becomes `QUAN` (the ratio p/q: 1/2 to 2/1). Nothing is emulated: the DSP is stock
and SPRING REV stays.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `9b2e35a`). `Kind.CF_PATCH`:
- the linked unit `vari_cf` (`varispeed.s`; DRAM or a ROM cave by the `PLACE` setting,
  default DRAM). It is VARISPEED_EMUS's source with its switch at 0, read from
  `../varispeed-emus/` in the same checkout, so the two modules assemble one source, with
  QUAN's rotary switch (`tools/ui_switch.s`, shared with SIDECHAIN_COMPRESSOR) inlined;
- 16 detours, four pokes and six symbol refs on the STATIC / FLEX descriptors;
- a STORE client (`vari_store`, `varispeed_store.s`; requires STORE): the PART menu's CLEAR is
  STORE's site (`0x4004a9d0`), so VARISPEED holds its per-track state on `partclear` and lets
  it go on the `partsaved` that ends the clear (stock Part Clear tail-jumps into Part Save).
  The standalone image keeps its own detour there.

`upstream/octabam-modules/varispeed/README.md` is the full description.
