# `varispeed` -- VARISPEED

STATIC and FLEX `TSTR` get a fifth position, VARI: the sample plays dry, tape-style, at
(project BPM × p) / (sample BPM × q), exact in integers, with an octave fold above 2×; RATE
still applies, and AUTO plays a sample whose ATTR TIMESTRETCH is VARI the same way. On a VARI
track `PTCH` becomes `QUAN` (the ratio p/q: 1/2 to 2/1). Entering VARI, `QUAN` starts at 1/1, or
at the `QUAN` the track had when it last left VARI. A VARI note held over a Part switch keeps its
speed until its own next trig. Nothing is emulated: the DSP is stock and SPRING REV stays.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `2cd3109`). `Kind.CF_PATCH`:
- the linked unit `vari_cf` (`varispeed.s`; DRAM or a ROM cave by the `PLACE` setting,
  default DRAM). It is VARISPEED_EMUS's source with its switch at 0, read from
  `../varispeed-emus/` in the same checkout, so the two modules assemble one source, with
  QUAN's rotary switch (`tools/ui_switch.s`, shared with SIDECHAIN_COMPRESSOR) inlined;
- 16 detours, four pokes and six symbol refs on the STATIC / FLEX descriptors;
- a STORE client (`vari_store`, `varispeed_store.s`; requires STORE): the PART menu's CLEAR is
  STORE's site (`0x4004a9d0`), so VARISPEED holds its per-track state on `partclear` and lets
  it go on the `partsaved` that ends the clear (stock Part Clear tail-jumps into Part Save).
  The standalone image keeps its own detour there.
- four bytes of every track in the Part window (claimed): THRU page 1 slots 2 and 5 (STATIC's
  and FLEX's PTCH while on VARI) and THRU's and NEIGHBOR's slot bytes (the `QUAN` each machine
  remembers off VARI). Stock never edits or shows them. An older build kept its PTCH in
  NEIGHBOR's `---` bytes; it is moved in the first time the track is seen.

`upstream/octabam-modules/varispeed/README.md` is the full description.

## Measured

- Every build re-links the unit and compares it with the author's own bytes (`reference`); a
  difference refuses the build.
- `make check REMIX=varispeed` (`remixes/test/varispeed/`, with STORE) builds and boots the
  image under the ColdFire port.

## On the unit

- On the author's MKI, 15 Oct 2026: the standalone image (`140C_VARI1`).
- 20 Nov 2026, this source in KYOTI V1.8BC / V1.8C release candidates and VARISPEED_EMUS
  (`140CVEMRC1`): `QUAN` 1/1 on entering VARI, its memory across a save, a project saved with an
  earlier build, a held VARI note's speed through a Part switch. This octabam form: not flashed.
