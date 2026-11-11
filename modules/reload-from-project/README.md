# `reload-from-project` -- RELOAD_FROM_PROJECT

Reload from the CF card without stopping the transport: `[PTN]` + `[TRACK n]` reloads that track's saved sequence; `[BANK]` + `[TRACK n]` also brings back that track's slice of the saved Part (machine, FX, pages, scene locks, LFO designer), leaving every other track alone; `[PTN]` + `[BANK]` + trig reloads a whole pattern and goes to it. While playing, a reload lands on the track's next step, in phase. A toast confirms.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `27ab725`). `Kind.CF_PATCH`. One DRAM unit (`patch_reload3.s`, `Linked(dram=True)`) and eleven `jmp` detours. A remix with this module carries the platform loader and its 10 MiB arena reserve, unless another DRAM module already brings them.
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
- 25 Oct 2026 (`6a2da8d`): on the MIDI tracks both chords reloaded the AUDIO track with the same number. `0x80000012` ("the MIDI tracks are showing") is a long, and it was read as a byte, its always-zero high byte. Both chords now reload the MIDI track there; the Part half (stock `0x4004aab4`, the whole Part) was never affected. Confirmed on the author's MKI with the standalone image; this octabam form: emulator.
- 9 Nov 2026 (`27ab725`): the card reloads. `[BANK]` + `[TRACK n]` brings back the track's slice of the project's saved Part (no longer stock Part RELOAD, the whole Part from SAVE PART); `[PTN]` + `[BANK]` + trig reloads a whole pattern of the playing bank and goes to it. Running, a reload lands on the track's next step, in phase, and its Part settings reach the engine with that step; length and scale changes re-phase every track; several chords before a landing all count. A pattern you are not on is a stock cue (CHAIN AFTER, or DIRECT JUMP's). Confirmed on the author's MKI from DRAM in the KYOTI V1.7 image; this octabam form: emulator.

## Notes

- All-tracks and whole-bank reload are not implemented.
- Octakit's conflict is dropped: Octakit is not in octabam since 6 Oct 2026 (KITS replaces it and plays through the stock Part slots). Since `27ab725` `[BANK]` + `[TRACK n]` no longer calls stock Part RELOAD (`0x4004aab4`); it calls stock's per-track Part apply (`0x40001f18`) and, for a whole pattern, stock's cue (`0x4009a404`, `0x400a1030`). These calls are not `Detour`s, so the ledger cannot see them. KITS also uses `0x400a1030` and `0x4004aab4`; the two have never been run together.
- Beside FREE LOOP, the UI task's tick `0x40056c28` (both detour it) goes through [HOOKS](../hooks/README.md) (`ui_tick`): FREE LOOP's detour stays and jumps to `rl_uitick` where it replayed stock, and this module's own detour there is overridden. On a tick where FREE LOOP shows a toast, RELOAD's UI half runs on the next tick, 1/60 s later.
