# `varispeed` -- VARISPEED

STATIC and FLEX `TSTR` get a fifth position, VARI: the sample plays dry, tape-style, at
(project BPM × p) / (sample BPM × q), exact in integers, with an octave fold above 2×; RATE
still applies, and AUTO plays a sample whose ATTR TIMESTRETCH is VARI the same way. On a VARI
track `PTCH` becomes `QUAN` (the ratio p/q: 1/2 to 2/1). Nothing is emulated: the DSP is stock
and SPRING REV stays.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `b7b6a0f`). `Kind.CF_PATCH`:
- one linked unit (`varispeed.s`; DRAM or a ROM cave by the `PLACE` setting, default DRAM). It
  is VARISPEED_EMUS's source with its switch at 0, read from `../varispeed-emus/` in the same
  checkout, so the two modules assemble one source;
- 17 detours, four pokes and six symbol refs on the STATIC / FLEX descriptors.

`upstream/octabam-modules/varispeed/README.md` is the full description.

## Measured

- Every build re-links the unit and compares it with the author's own bytes (`reference`); a
  difference refuses the build.
- `make check REMIX=varispeed` (`remixes/test/varispeed/`) builds and boots the image under the
  ColdFire port.

## On the unit

- On the author's MKI, 15 Oct 2026: the standalone image (`140C_VARI1`).
