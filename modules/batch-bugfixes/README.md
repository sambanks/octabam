# `batch-bugfixes` -- BATCH_BUGFIXES

Three fixes to stock 1.40C behaviour as one module: MIDI Plays-Free trig (a Plays-Free MIDI track with trig quantize DIRECT and pattern scale PER TRACK stalled after its first step), empty-pattern LED (a pattern holding only parameter locks showed as unused under `[PTN]`, and a bank holding only trigless locks with a locked parameter under `[BANK]`), Part-change carryover (stale per-track state from the old Part after a pattern-triggered Part change).

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `2cd3109`). `Kind.CF_PATCH`. Three ROM caves: `patch_trigscale.s` (62 B, one 18-byte splice at `0x4009b6f2`), `patch_pattern_led.s` (318 B, a detour at `0x4009a464`; the `[BANK]` grid's calls from `0x4000fd78` get stock's test, then only the steps set in the trigless-lock masks `TRAC+0x10` / `MTRA+0x10` have their 32 lock bytes read, at most 16 steps a call), `patch_partreapply.s` (402 B, detours at `0x40062216` and `0x400621da`).
`upstream/octabam-modules/batch-bugfixes/README.md` is the full description, with what was measured and what was inferred.

## Notes

- A remix takes all three or none.
- With OCTAKIT, the Part-change carryover fix stays idle: Octakit replaces the "select Part" handler from its entry (`0x400621a6`) and rejoins stock only at its end, so the fix's two hooks inside it never run. No effect and no crash; the other two fixes are unaffected. Whether the carryover bugs occur on an Octakit Kit change is untested.
