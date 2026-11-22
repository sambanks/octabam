# `batch-bugfixes` -- BATCH_BUGFIXES

Three fixes to stock 1.40C behaviour as one module: MIDI Plays-Free trig (a Plays-Free MIDI track with trig quantize DIRECT and pattern scale PER TRACK stalled after its first step), empty-pattern LED (a pattern holding only parameter locks showed as unused under `[PTN]`, and a bank holding only trigless locks with a locked parameter under `[BANK]`), Part-change carryover (stale per-track state from the old Part after a pattern-triggered Part change).

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `2cd3109`). `Kind.CF_PATCH`. Three ROM caves: `patch_trigscale.s` (62 B, one 18-byte splice at `0x4009b6f2`), `patch_pattern_led.s` (318 B, a detour at `0x4009a464`; the `[BANK]` grid's calls from `0x4000fd78` get stock's test, then only the steps set in the trigless-lock masks `TRAC+0x10` / `MTRA+0x10` have their 32 lock bytes read, at most 16 steps a call), `patch_partreapply.s` (402 B, detours at `0x40062216` and `0x400621da`).
`upstream/octabam-modules/batch-bugfixes/README.md` is the full description, with what was measured and what was inferred.

## Measured

- Every build re-links each cave or unit and compares it with the author's
  own bytes (`reference`); a difference refuses the build.
- `make check REMIX=batch-bugfixes` (`remixes/test/batch-bugfixes/`) builds and boots the
  image under the ColdFire port.

## On the unit

- Bugs 1 and 3 on the author's MKI; bug 1 on 28 Aug 2026.
- Bug 2: the earlier version on the author's MKI, and the current version's end of the `[BANK]`-held stall; its `[PTN]` answers emulator-verified identical to the earlier version.
- Bug 2's `[BANK]` answer for trigless locks (since `2cd3109`): the author's MKI, 20 Nov 2026, in KYOTI V1.8BC / V1.8C release candidates (`KY18BC RC1`, `KY18C RC1`) and VARISPEED_EMUS `140CVEMRC1`, the same 318 B: the `[PTN]` / `[BANK]` LED checks (audio and MIDI trigless locks with and without a locked value, one removed again, pattern 16) as specified, and `[BANK]` held with the sequencer running stays responsive. This octabam form: not flashed.

## Notes

- A remix takes all three or none.
- With OCTAKIT, the Part-change carryover fix stays idle: Octakit replaces the "select Part" handler from its entry (`0x400621a6`) and rejoins stock only at its end, so the fix's two hooks inside it never run. No effect and no crash; the other two fixes are unaffected. Whether the carryover bugs occur on an Octakit Kit change is untested.
