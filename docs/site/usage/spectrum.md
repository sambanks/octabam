SPECTRUM is a multimode filter offering four models (a Moog ladder, an
Oberheim SEM state-variable filter, an isolator, and a formant bank) along
with an envelope follower and an LFO modulating the cutoff. At its default
settings it is an exact passthrough and leaves the signal unchanged until you
adjust a control.

## Access

Press FX1 or FX2 on a track and select **SPECTRUM** from the effect chooser.

## Operation

- **MODE** (page 2) selects the filter model:
  - **LADR**: A 24 dB/oct Moog transistor ladder filter. **RES** at 127 sits
    right at the edge of self-oscillation. Automatic makeup gain compensates
    for the passband level drop as resonance increases.
  - **SEM**: A driven Oberheim state-variable filter. **SHPE** (page 2) sweeps
    smoothly from low-pass (0) through band-pass (64) to high-pass (127) with
    an equal-power crossfade.
  - **ISO**: A frequency isolator where **FREQ** sets the low-band cutoff and
    **RES** controls **COLR**.
  - **VOWL**: A three-formant vowel filter that morphs A → E → I → O → U as
    you turn **FREQ**, while **RES** (**SHRP**) narrows the formant bands.
- **ENV** routes a peak envelope follower to the cutoff, with instant attack
  and release time controlled by **LSP**. **LDP** routes an LFO to the cutoff,
  with speed set by **LSP** (~0.08–9 Hz).
- **WDTH** adjusts stereo mid/side width at the output; centre (64) leaves the
  stereo image unchanged.
- **DSP load**: With SPECTRUM loaded on all eight tracks, the effects
  processor runs at roughly 28% at default settings and up to 78% at its most
  demanding settings (an empty project uses about 24%). Exceeding 100% stalls
  the unit until you power-cycle it.

## Parameters

| Page | Knob | Range | Default | What it does |
|---|---|---|---|---|
| 1 | FREQ | 0–127 | 127 | the cutoff, exponential, 60 Hz → 15 kHz; LOW in ISO; the vowel morph in VOWL |
| 1 | RES | 0–127 | 0 | resonance; COLR in ISO; SHRP (band narrowing) in VOWL |
| 1 | ENV | bipolar | 64 | envelope onto the cutoff: instant attack, LSP is the release |
| 1 | LDP | 0–127 | 0 | LFO onto the cutoff |
| 1 | LSP | 0–127 | 64 | LFO speed ~0.08–9 Hz; ENV's release |
| 1 | WDTH | bipolar | 64 | mid/side width on the output |
| 2 | MODE | LADR / SEM / ISO / VOWL | — | Selects the filter model. |
| 2 | SHPE | 0–127 | 0 | SEM only (blank in other modes): LP → BP → HP |
