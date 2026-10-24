Bare full-screen scope — useful to see which tracks are actually making
sound (**ALL**) and to catch clipping before main out (peak / `!`).

**DOWN + TEMPO** opens; **UP + TEMPO** = TUNER.
**OSC** / **XY** / **ALL** via **UP**/**DOWN**. **ALL** is a 4×2 mini OSC
grid (T1–T4 left, T5–T8 right, centre divider; T1 top-left). **A** GAIN,
**B** TIME. **CUE** release toggles G/P HUD on OSC / XY (ALL has none).

**Hardware (author MKII, `LSCOPE BJ`, 24 Oct 2026):** busy 8-track play +
CF METER — SCOPE open ISR mean 291 µs / closed 288 µs, TUE 0 / ROE 0;
several minutes ALL open with no glitch. Emulator captures
(`tools/site/shots/scope.script`). Live waveform needs track audio; under
the port the ring stays quiet (same class as TUNER `--`).

![SCOPE OSC with G/P HUD.](../../img/scope/osc.png)

![RIGHT help: A GAIN, B TIME.](../../img/scope/help.png)
