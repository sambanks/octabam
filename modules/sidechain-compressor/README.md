# `sidechain-compressor` -- SIDECHAIN_COMPRESSOR

Stock COMPRESSOR with a side-chain KEY: any of T1-T8 can drive its detector. Page 2 adds KEY (OFF or T1-T8), KFLT (the key's filter: 64 bypass, below low-pass, above high-pass), KGN (the key's gain, about -24..+24 dB) and MON (hear the processed key instead), beside stock's RMS.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `8e00275`). `Kind.DSP_EFFECT` with `MenuEntry(replaces="COMPRESSOR", stock_dsp=True)`: the row is COMPRESSOR's and its dispatch entry stays stock's. One linked unit (`patch_sidechain.s`, 338 B; ROM cave or DRAM by the `PLACE` setting, default CAVE: KEY's and KFLT's formatters, KEY's list widget, and `sc_norm`, reached by two `jsr` detours at the first instruction of both page-2 copiers, `0x4000cae8` and its twin `0x40003d1c`: a COMPRESSOR saved on stock firmware, whose hidden slots 8-11 hold stock's defaults `0x7f/0/0/0`, comes up with KEY OFF, KFLT and KGN centred and MON OFF); page-2 slots 8-11 as raw descriptor words; three per-payload `DspHook`s (`sctap`, `scdet`, `moncommit`); the per-core values as `DspSection.subst`; the 48 table words as one `ptable`.
`upstream/octabam-modules/sidechain-compressor/README.md` is the full description, with what was measured and what was inferred.

## Measured

- Every build re-links `sc_cf` and compares it with the author's own bytes (`reference`); a difference refuses the build.
- The cloned COMPRESSOR descriptor equals the author's standalone image's, except the three words that point into `sc_cf`.
- On both payloads the placed DSP code is the standalone's instruction for instruction, except the two table loads (the KEY FLT load is `lua (r1+$10),r1` + `nop` from the one `ptable` base) and the keybus/MON addresses (below); the 48 table words are identical.
- The one-pass `sctap` at this manifest's addresses leaves every Y and shared-window word as the two-loop tap of `8b2e3c9` did (`upstream/tools/emu_sc_sctap.py --layout octabam --ref 8b2e3c9`: 0 words differ).
- `make check REMIX=sidechain-compressor` (`remixes/test/sidechain-compressor/`) and `make check REMIX=kyoti-mute-sidechain` build and boot the image under the ColdFire port.

## On the unit

- 4 Oct 2026, on the author's MKI, in an octabam image with all six KYOTI modules, REC_TRIG_MUTE and this module: COMPRESSOR's two pages; KEY ducking on one core and across cores both ways (T1 to T5, T5 to T1); KFLT, KGN and MON; no reverb cross-talk with DARK or PLATE REV on T7; a muted KEY in every MUTE MODE, and the first kick after PLAY with it muted.
- Before that: the author's standalone image and the KYOTI V1.0 combined image, on the author's MKI: KEY ducking, MON, a muted KEY with MUTE MODE.

## Notes

- Its DSP section needs donor words: the test remixes give up SPRING REV, as the standalone build does.
- The keybus and MON words stay at core-private `Y:$7f0-$9ff`, which no FX2 slot reaches. Since `8e00275` the address is a build choice (`@KEYB@`/`@KEYB1@`/`@MONB@`): the author's standalone image puts them in the tail of the first internal FX2 slot, but MINIVERB, GATE VERB and WAVE fill that slot, so this manifest keeps Session 115's layout.
- Not with BusDelay or BusVerb: its cross-core window (the last `$202` words of each core's half of the shared window) overlaps theirs, and the ledger refuses the pair.
- **Open:** the window is also the tail of T7's and T3's FX2 slot, which MINIVERB, GATE VERB (to `+$3EF7`) and WAVE write, and the ledger does not refuse those pairs. In the DSP host, MINIVERB on T7 wrote all 514 window words and GATE VERB 250. Not yet heard on hardware; see #774.
