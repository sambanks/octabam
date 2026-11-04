A filter: a Moog ladder, an Oberheim SEM
state-variable filter, an isolator and a formant bank, with an envelope and
an LFO on the cutoff. The defaults are an exact passthrough: it does nothing until you turn it.

## Access

Press FX1 or FX2 on a track; SPECTRUM is in the chooser with the stock effects.

## Operation

- MODE on page 2 picks the filter:
  - **LADR** — a 24 dB/oct Moog transistor ladder. RES 127 is the edge of
    self-oscillation; the passband level drops as RES rises, so the output
    carries a makeup that keeps it close.
  - **SEM** — a driven Oberheim state-variable filter. SHPE (page 2)
    sweeps it low-pass (0) → band-pass (64) → high-pass (127) with an
    equal-power crossfade.
  - **ISO** — an isolator. FREQ is the low band's cutoff, RES is COLR.
  - **VOWL** — a three-formant bank that morphs A → E → I → O → U as FREQ
    turns; RES (SHRP) narrows the bands.
- ENV is a peak follower onto the cutoff: instant attack, release on LSP.
  LDP is an LFO onto the cutoff; LSP sets its speed (~0.08–9 Hz).
- WDTH is mid/side width on the output; the centre (64) is untouched.
- Load: with SPECTRUM on all eight tracks, the effects processor runs at about 28 % at the defaults and up to 78 % at its most demanding settings (an empty project reads about 24 %). Past 100 % the unit stalls until you switch it off and on.

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
