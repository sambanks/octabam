# `waveload` — WAVE LOAD

A probe: K instances of a fixed-point port of CHOMPI WAVE's voice engine
(4 voices each) rendered inside the ColdFire's frame interrupt, output
discarded, so [CF METER](../cfmeter/README.md) reads what a 4-voice
wavetable track costs on the unit and how many fit.

The engine is a port of the voice in
[CHOMPI-Club/CHOMPI](https://github.com/CHOMPI-Club/CHOMPI)'s WAVE firmware
(`firmware/chompi-wave/code/src` at `a73d732`: `subtractiveEngine.h`,
`WavetableManager.h`, `DJFilter.h`, `BasicMMF.h`), MIT, Copyright (c) 2026
CHOMPI Club; the full notice is in [LICENSE-CHOMPI](LICENSE-CHOMPI).  Not affiliated with or endorsed by CHOMPI Club or Chase Bliss, and not an official CHOMPI Club release; CHOMPI is CHOMPI Club's trademark (their `TRADEMARKS.md`), used here only to say where the code comes from. WAVE
LOAD is a measurement, not a playable machine.

## Knobs

CF METER's BURN (T8 FX2 page 1 slot 0) is K, 0–12, when WAVE LOAD is in
the remix (CF METER's `remix.inc` sets `WAVE_LOAD`); above 12 it renders 12.

## Open

- A 4-voice voice on the DSP: its cycle cost, and where two 2,048-word
  frames per track live (per-core free private memory is ~616 X words
  and ~2,155 Y words).

## Design

- `engine.c`: every voice shares the cutoff, the LFOs, the resonance and
  the frame crossfade in CHOMPI (`setMasterCutoff`, `setCycle`,
  `setMasterResonance` set all voices alike), so the slews, the feedback
  `res + res / (1 − f)` (one Newton step a sample from the last
  reciprocal) and both LFOs run once a sample. DjFilter's `hp_ > .8`
  branch is absent: `hp_` is clamped to at most .9³ = .729.
- `load.c`: twelve engine states and a scratch output in `.data` (the
  platform runtime is the linked image's bytes); the tables are 1 MB above
  them in the arena reserve, never in the image. With the 1,622,016 B of
  tables in `.data` the loader's hash of the runtime held the PC inside
  64 bytes for over 2 M instructions, which the port's stall check
  (`machine.cpp`, 4 bursts of 500,000) stops as a spin.
- `wrap.s`: `cl_load`, called from CF METER's `m_isr` before the stock
  handler saves anything, saves MACSR, ACC0 and ACCext01 the way the
  handler does (MACSR to 0 before the accumulator moves), sets MACSR
  0x20, renders, restores.
