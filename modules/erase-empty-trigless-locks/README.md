# `erase-empty-trigless-locks` -- ERASE_EMPTY_TRIGLESS_LOCKS

A trigless lock whose last remaining lock is erased disappears from the trig row instead of staying lit, on audio and MIDI tracks. A deliberately empty trigless lock placed with `FUNC` + `TRIG` is left alone.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `2cd3109`). `Kind.CF_PATCH`. One linked unit (`patch_triglock.s`, 240 B, position independent) and two `jsr` detours on the LIVE erase workers' per-parameter erase store: `0x40038a5c` (audio, `FUN_40038874`) and `0x400387b8` (MIDI, `FUN_40038668`, the twin that stock's `FUN_40041af4` calls for a MIDI track). Both reach one shared rule: the erased value was a lock, every other byte of the step's lock row is `0xFF`, no trig layer vetoes it, and the trigless-lock flag (`TRAC+0x10` / `MTRA+0x10`) is set: clear it, its mirror and the dirty flags.
`upstream/octabam-modules/erase-empty-trigless-locks/README.md` is the full description, with what was measured and what was inferred.
