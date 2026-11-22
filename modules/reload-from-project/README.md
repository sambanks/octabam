# `reload-from-project` -- RELOAD_FROM_PROJECT

Reload from the CF card without stopping the transport: `[PTN]` + `[TRACK n]` reloads that track's saved sequence; `[BANK]` + `[TRACK n]` also brings back that track's slice of the saved Part (machine, FX, pages, scene locks, LFO designer), leaving every other track alone; `[PTN]` + `[BANK]` + trig reloads a whole pattern and goes to it. While playing, a reload lands on the track's next step, in phase, and that step already plays it; trig conditions carry on as if the saved sequence had always played. A toast confirms.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `dd1ad1e`). `Kind.CF_PATCH`. One DRAM unit (`patch_reload3.s`, `Linked(dram=True)`, 51,620 B) and twelve `jmp` detours. A remix with this module carries the platform loader and its 10 MiB arena reserve, unless another DRAM module already brings them.
`upstream/octabam-modules/reload-from-project/README.md` is the full description, with what was measured and what was inferred.

## Notes

- All-tracks and whole-bank reload are not implemented.
- Octakit's conflict is dropped: Octakit is not in octabam since 6 Oct 2026 (KITS replaces it and plays through the stock Part slots). Since `27ab725` `[BANK]` + `[TRACK n]` no longer calls stock Part RELOAD (`0x4004aab4`); it calls stock's per-track Part apply (`0x40001f18`) and, for a whole pattern, stock's cue (`0x4009a404`, `0x400a1030`). These calls are not `Detour`s, so the ledger cannot see them. KITS also uses `0x400a1030` and `0x4004aab4`; the two have never been run together.
- Since `dd1ad1e` this module detours COND_RESET's entry (`0x400a539c`, an 8-byte span, `lea -12(%sp),%sp ; movem.l %d2/%a2-%a3,(%sp)`) to note when every track's trig conditions start again; no other module detours it. DIRECT_JUMP_KYOTI does not call COND_RESET at a jump (since its V7.0.2), so beside it a jump is not a restart; it sets every track's conditions where a run that had played the new pattern since the last restart would have them, and since its V7.3 (`cd788e9`) it takes that restart from the same COND_RESET(-1) call in stock's pattern switch (its detour at `0x400a4850` tail-jumps COND_RESET, so this module's detour still sees that caller and its -1). A reload after a jump therefore stays in step, as in the author's KYOTI V1.8 image.
- Beside FREE LOOP, the UI task's tick `0x40056c28` (both detour it) goes through [HOOKS](../hooks/README.md) (`ui_tick`): FREE LOOP's detour stays and jumps to `rl_uitick` where it replayed stock, and this module's own detour there is overridden. On a tick where FREE LOOP shows a toast, RELOAD's UI half runs on the next tick, 1/60 s later.
