# `scope` — SCOPE

Full-screen **OSC**, **XY**, or **ALL** (4×2 mini OSC: T1–T4 left column,
T5–T8 right, centre divider; track-pad layout). G/P HUD and clip `!` on
OSC / XY.

**[DOWN]** + **[TEMPO]** opens SCOPE. With TUNER in the build,
**[UP]** + **[TEMPO]** opens the tuner. **[UP]** / **[DOWN]** cycle modes.
**[RIGHT]** shows help; **[LEFT]** returns. Push DATA ENTRY **A** to reset GAIN
and clear the peak. Release **[CUE]** to toggle the G/P HUD.

| | A | B | C–F |
|---|---|---|---|
| **OSC** / **XY** / **ALL** | GAIN | TIME | — |

XY is a hotter scale than OSC. ALL cells follow the panel track pad layout
(T1 top-left).

**Earlier hardware result (author MKII):** `LSCOPE BJ`, 24 Oct 2026. OSC /
XY / ALL (4×2, T1 top), clip `!`, G/P HUD and **[DOWN]** + **[TEMPO]** worked.
In that combined build, **[UP]** + **[TEMPO]** opened TUNER. That image predates
the current HOOKS dispatcher.
owner's busy 8-track project + CF METER: ISR mean 291 µs open / 288 µs
closed (TUE 0, ROE 0); several minutes SCOPE ALL, no glitch / missed step
/ UI stall. Earlier smoke: `LSCOPE BH` 23 Oct 2026.

## Loader comparison on OCTA S2

The flashed `OCTA S2` image was tested on 15 Nov 2026, with SCOPE closed and
open for the same 30 transitions on `SFX_01`. The hardware model was not
recorded. The set covered BASE, PLATE REV, SPRING REV and DARK REV switching to
MODULATION, SPECTRUM and SIDECHAIN_COMPRESSOR, plus each demand effect switching
back to BASE, the three reverbs and the other demand effects. USB MIDI used
`Elektron Octatrack DPS-1`; audio used `Octatrack`. SCOPE opened with **[DOWN]**
+ **[TEMPO]**.

Values below are median (maximum) across the 30 transitions. DSP busy fractions
are shown as percentages.

| Measurement | SCOPE closed | SCOPE open |
|---|---:|---:|
| ColdFire longest run in transition window, µs | 537.36 (577.33) | 544.96 (569.01) |
| ColdFire longest steady run, µs | 355.77 (556.88) | 359.37 (508.80) |
| DSP busy, transition window | 48.87% (57.84%) | 48.24% (57.95%) |
| DSP busy, steady | 48.91% (60.24%) | 48.19% (55.27%) |
| Longest audio gap, ms | 340 (1,480) | 340 (360) |
| Bad DSP records | 0 | 0 |

All transitions carried the harness's 40 ms `GAP` flag because the loader
silence is about 340 ms. `SPIKE_CF` appeared on 21 closed and 24 open
transitions; `SPIKE_DSP` appeared on 1 and 2. Both runs had zero bad records.
The comparison covers this image, project and transition set only. The reports
are in the local captures `out/hw/matrix/scope-loader-closed/report.json` and
`out/hw/matrix/scope-loader-open/report.json`.

**Builds:** `REMIX=test/scope-alone` and `REMIX=test/scope`. The HOOKS gate
could not run in this environment because the Unicorn runner exited with
`SIGILL`. **Inferred:** emu `live_shots` ring stays quiet without track audio.
