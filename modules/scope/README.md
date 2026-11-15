# `scope` — SCOPE

Full-screen **OSC**, **XY**, or **ALL** (4×2 mini OSC: T1–T4 left column,
T5–T8 right, centre divider; track-pad layout). G/P HUD and clip `!` on
OSC / XY.

**DOWN + TEMPO** opens SCOPE. With TUNER in the build, **UP + TEMPO** opens the tuner.
**UP** / **DOWN** cycle. **RIGHT** help; **LEFT** back.
**Push A** = GAIN default + clear peak. **CUE** release = G/P HUD.

| | A | B | C–F |
|---|---|---|---|
| **OSC** / **XY** / **ALL** | GAIN | TIME | — |

XY is a hotter scale than OSC. ALL cells follow the panel track pad layout
(T1 top-left).

**Earlier hardware result (author MKII):** `LSCOPE BJ` — 24 Oct 2026 — OSC /
XY / ALL (4×2, T1 top), clip `!`, G/P HUD, DOWN+TEMPO and, in that combined
build, UP+TEMPO for TUNER. That image predates the current HOOKS dispatcher.
owner's busy 8-track project + CF METER: ISR mean 291 µs open / 288 µs
closed (TUE 0, ROE 0); several minutes SCOPE ALL, no glitch / missed step
/ UI stall. Earlier smoke: `LSCOPE BH` 23 Oct 2026.
**Builds:** `REMIX=test/scope-alone` and `REMIX=test/scope`. The HOOKS gate
could not run in this environment because the Unicorn runner exited with
`SIGILL`. **Inferred:** emu `live_shots` ring stays quiet without track audio.
