# `sidechain-compressor` -- SIDECHAIN_COMPRESSOR

Stock COMPRESSOR with a side-chain KEY: any of T1-T8 can drive its detector. Page 2 adds KEY (OFF or T1-T8), KFLT (the key's filter: 64 bypass, below low-pass, above high-pass), KGN (the key's gain, about -24..+24 dB) and MON (hear the processed key instead), beside stock's RMS.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `7c2fe04`). `Kind.DSP_EFFECT` with `MenuEntry(replaces="COMPRESSOR", stock_dsp=True)`: the row is COMPRESSOR's and its dispatch entry stays stock's. One ROM unit (`patch_sidechain.s`, 134 B: KEY's and KFLT's formatters, KEY's list widget); page-2 slots 8-11 as raw descriptor words; three per-payload `DspHook`s (`sctap`, `scdet`, `moncommit`); the per-core values as `DspSection.subst`; the 48 table words as one `ptable`.
`upstream/octabam-modules/sidechain-compressor/README.md` is the full description, with what was measured and what was inferred.

## Work in progress

Built and gated; not run on a unit in this form.

## Measured

- Every build re-links `sc_cf` and compares it with the author's own bytes (`reference`); a difference refuses the build.
- The cloned COMPRESSOR descriptor equals the author's standalone image's, except the three words that point into `sc_cf`.
- On both payloads the placed DSP code is the standalone's instruction for instruction, except the two table loads (the KEY FLT load is `lua (r1+$10),r1` + `nop` from the one `ptable` base); the 48 table words are identical.
- `make check REMIX=sidechain-compressor` (`remixes/test/sidechain-compressor/`) and `make check REMIX=kyoti-mute-sidechain` build and boot the image under the ColdFire port.

## On the unit

- The author's standalone image and the KYOTI V1.0 combined image, on the author's MKI: KEY ducking, MON, and a muted KEY with MUTE MODE. Not yet on a unit: cross-core KEY both ways, a reverb on T7 beside it, the first kick after PLAY with a muted key. The octabam form has not run on a unit.

## Notes

- Its DSP section needs donor words: the test remixes give up SPRING REV, as the standalone build does.
- Not with BusDelay or BusVerb: its keybus (core-private `Y:$7f0-$9ff`) and cross-core window (the last `$202` words of each core's half of the shared window) overlap theirs, and the ledger refuses the pair. A later version is planned to move both.
- `Param()` does not keep a donor slot drawn: the build writes the enable bitmap from `active`, so slots 0-6 (stock's ATK..MIX and RMS) are declared active under stock's own names.
