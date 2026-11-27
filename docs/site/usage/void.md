VOID is a noise and grit effect for FX2 that replaces **COMB FILTER**. It
blends the clean dry input with shaped noise gated by an audio-rate LFO or a
neighbour track's envelope, creating vinyl crackle and rhythmic AM texture.

The noise passes through **HPF**, **COLR**, **DRV**, **FDBK**, and amplitude
modulation while the dry signal stays clean. **BAL** controls the balance
between dry and noise (there is no separate **MIX** knob), and **SRC** on the
SETUP page selects what modulates the noise:

![VOID SRC=LFO: RATE/SHPE LFO amplitude-modulates the noise.](../../img/void/path.svg)

![VOID SRC=NBR: prev-track keybus envelope opens the noise, level only, no neighbour audio. Dry still this track.](../../img/void/nbr.svg)

## Access

Select a track, press **`[FX2]`**, and choose **VOID**.

- Page 1: **BAL**, **RATE**, **COLR**, **HPF**, **DRV**, **FDBK**
- Page 2 (SETUP): **SHPE**, **DPTH**, **WID**, and **SRC** (bottom left)

## Operation

- **BAL** crossfades between dry audio and noise (**0** is exact dry; **127**
  is pure noise). AM, **DRV**, and **FDBK** affect only the noise path.
- **COLR** and **HPF** filter the noise path only. **COLR** at 127 leaves the
  low-pass filter open, and **HPF** at 0 bypasses the high-pass filter.
- **SRC** (SETUP) chooses the AM source. **LFO** (default) uses the internal
  LFO controlled by **RATE** and **SHPE**. **NBR** uses the previous track's
  **keybus envelope** (level only, with no neighbour audio entering VOID), so
  the noise stops when the neighbour is silent while dry audio and **BAL**
  still use this track. On track 1, **NBR** reads T1's own keybus. The remix
  must include **KEYBUS** (and **SC KEYBUS BRIDGE** when used alongside
  SIDECHAIN_COMPRESSOR).
- **DPTH** sets how strongly the modulator opens the noise in both **SRC**
  modes.
- **WID** adds stereo grit using a second noise generator routed through the
  same **HPF**, **COLR**, and **DRV** stages (without **FDBK**). At **0**, the
  noise is mono.
- Combining **FDBK** and **DRV** produces intense resonance. The feedback loop
  is AC-coupled so it continues scraping without latching.

## Parameters

| Page | Knob | Range | Default | What it does |
|---|---|---|---|---|
| 1 | BAL | 0..127 | 0 | dry↔noise (0 = exact dry, 127 = pure noise) |
| 1 | RATE | 0..127 | 72 | LFO rate; idle when SRC=NBR |
| 1 | COLR | 0..127 | 64 | noise low-pass; 127 = open |
| 1 | HPF | 0..127 | 0 | noise high-pass; 0 = bypass |
| 1 | DRV | 0..127 | 0 | soft-clip on noise only |
| 1 | FDBK | 0..127 | 0 | one-sample feedback on noise only |
| 2 | SHPE | SIN / SQR / SAW | SIN | LFO shape; idle when SRC=NBR |
| 2 | DPTH | 0..127 | 127 | AM depth on noise only (default max) |
| 2 | WID | 0..127 | 0 | mono → stereo grit |
| 2 | SRC | LFO / NBR | LFO | AM source |
