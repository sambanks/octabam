**Scrape / grit on FX2** — dry input blended with shaped noise that an
audio-rate LFO (or a neighbour track’s envelope) chops open. Think vinyl
crackle and AM dirt that rides the beat, not a reverb or a filter on the
dry. Replaces **COMB FILTER** (id `0x13`); DSP words sit in harvested
**PLATE REV**.

Noise gets HPF → COLR → DRV → FDBK → AM. Dry stays clean. **BAL** is the
blend (there is no separate dry/wet MIX). SETUP **SRC** picks what opens
the noise:

![VOID SRC=LFO: RATE/SHPE LFO amplitude-modulates the noise.](../../img/void/path.svg)

![VOID SRC=NBR: prev-track keybus envelope opens the noise (not neighbour audio); dry still this track.](../../img/void/nbr.svg)

## Access

Select a track, press FX2, pick **VOID**.

- Page 1: BAL, RATE, COLR, HPF, DRV, FDBK
- Page 2 (SETUP): SHPE, DPTH, WID; **SRC** bottom left

## Operation

- **BAL** — dry↔noise (**0 = exact dry**, **127 = pure noise**). AM, DRV
  and FDBK never touch the dry.
- **COLR** / **HPF** — darken or thin the **noise** only. COLR 127 = open;
  HPF 0 = bypass.
- **SRC** (SETUP): **LFO** (default) uses RATE/SHPE; **NBR** replaces that
  LFO with the previous track’s **keybus envelope** (level only — no
  neighbour audio into VOID). Quiet neighbour → noise stops. Dry/BAL is
  still this track. On track 1, NBR reads T1’s own keybus (`Y:$800`).
- **DPTH** — how hard the modulator opens the noise (both SRC modes).
- **WID** — stereo grit from a second noise through the same HPF/COLR/DRV
  (no FDBK); **0 = mono**.
- **FDBK** + **DRV** screams; feedback is AC-coupled so it keeps scraping
  instead of railing to silence.

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
