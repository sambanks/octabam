# `scope` — SCOPE

Full-screen **OSC**, **XY**, or **ALL** (4×2 mini OSC: T1–T4 left column,
T5–T8 right, centre divider). Use it to see which tracks are actually
making sound and to catch clipping before it hits the main out.

**DOWN + TEMPO** opens; **UP + TEMPO** = [TUNER](../tuner/README.md).
**UP** / **DOWN** cycle. **RIGHT** help; **LEFT** back.
**Push A** = GAIN default + clear peak. **CUE** release = G/P HUD.

| | A | B | C–F |
|---|---|---|---|
| **OSC** / **XY** / **ALL** | GAIN | TIME | — |

XY is a hotter scale than OSC. ALL cells follow the panel track pad layout
(T1 top-left).

**Measured (hardware, author MKII):** `LSCOPE BJ` — 24 Oct 2026 — OSC /
XY / ALL (4×2, T1 top), clip `!`, G/P HUD, DOWN+TEMPO / UP+TEMPO TUNER;
owner's busy 8-track project + CF METER: ISR mean 291 µs open / 288 µs
closed (TUE 0, ROE 0); several minutes SCOPE ALL, no glitch / missed step
/ UI stall. Earlier smoke: `LSCOPE BH` 23 Oct 2026.
**Measured (port):** `make check REMIX=test/scope`. **Inferred:** emu
`live_shots` ring stays quiet without track audio (like TUNER `--`).
