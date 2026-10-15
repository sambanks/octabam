## What it does

A filter pedal that replaces stock FILTER: a Moog ladder, an Oberheim SEM
state-variable filter, an isolator and a formant bank, with an envelope and
an LFO on the cutoff. The defaults are an exact passthrough, so a part that
chose FILTER sounds the same until you turn it.

## Where to find it

Press FX1 on a track; SPECTRUM is in the chooser in place of FILTER. In
octabam-inserts it is also on FX2; in octabam-bus it is FX1 only.

## How to use it

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

## Knobs

| page | knob | range | default | what it does |
|---|---|---|---|---|
| 1 | FREQ | 0–127 | 127 | the cutoff, exponential, 60 Hz → 15 kHz; LOW in ISO; the vowel morph in VOWL |
| 1 | RES | 0–127 | 0 | resonance; COLR in ISO; SHRP (band narrowing) in VOWL |
| 1 | ENV | bipolar | 64 | envelope onto the cutoff: instant attack, LSP is the release |
| 1 | LDP | 0–127 | 0 | LFO onto the cutoff |
| 1 | LSP | 0–127 | 64 | LFO speed ~0.08–9 Hz; ENV's release |
| 1 | WDTH | bipolar | 64 | mid/side width on the output |
| 2 | MODE | LADR / SEM / ISO / VOWL | | the filter |
| 2 | SHPE | 0–127 | 0 | SEM only (blank in other modes): LP → BP → HP |

## Old projects

MODE's saved values moved on 27 Sep 2026 (BP 2 → SEM 1, ISO 3 → 2, VOWL
4 → 3); SHPE keeps its stored value, so a part saved on BP comes back as
SEM at whatever SHPE it held. Once per project, before play:

```bash
python3 tools/hw/ot_project.py remap-slot <project> SPECTRUM MODE 2:1,3:2,4:3
```

## Screens

![The SPECTRUM page: the four knob boxes](../../img/spectrum/main.png)

![The routing grid (page 2): source, destination and modulation](../../img/spectrum/setup.png)
