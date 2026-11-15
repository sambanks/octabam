Full-screen track audio on the LCD: **OSC** (mono polyline), **XY**
(L×R Lissajous), or **ALL** (4×2 mini OSC. T1-T4 left, T5-T8 right,
centre divider. T1 top-left, same layout as the track pads). Gain /
peak HUD and a clip `!` sit on OSC and XY.

**`[DOWN]` + `[TEMPO]`** opens SCOPE. In builds with TUNER,
**`[UP]` + `[TEMPO]`** opens the tuner.
**`[UP]`** / **`[DOWN]`** cycle the three modes. **A** GAIN, **B** TIME.
**`[CUE]`** release toggles the G/P HUD on OSC / XY (ALL has none).
Push **A** resets GAIN and clears the peak.

In the `octabam` remix, SCOPE and TUNER share the TEMPO key dispatcher.
**`[DOWN]`** + **`[TEMPO]`** opens SCOPE; **`[UP]`** + **`[TEMPO]`** opens the tuner.
Their source modules have no dependency on each other.

**Hardware (author MKII, `LSCOPE BJ`, 24 Oct 2026):** busy 8-track play +
CF METER. SCOPE open ISR mean 291 µs / closed 288 µs, TUE 0 / ROE 0.
Several minutes ALL open with no glitch.

**Loader comparison (S2 build, 15 Nov 2026):** 30 transitions with SCOPE closed
and 30 with it open. Both runs had zero bad records and a 340 ms median audio
gap. Median transition-window CF peak was 537.36 µs closed and 544.96 µs open;
median steady CF was 355.77 and 359.37 µs. Median DSP window maximum was 49%
closed and 48% open; median steady DSP maximum was 49% and 48%. The closed
run's maximum gap was 1,480 ms, compared with 360 ms open. This single comparison
does not cover other images, workloads, or longer sessions.
