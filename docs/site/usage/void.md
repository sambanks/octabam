Scrape: blend the track input with internal noise, amplitude-modulate it with an
audio-rate LFO, then a mild HP/LP body and soft drive. **FDBK** recirculates
the post-clip sample into the drive (one-sample loop). Always wet — there is no dry/wet
MIX.

Replaces **COMB FILTER** on FX2 (id `0x13`). DSP words sit in harvested **PLATE REV**.

## Access

Select a track, press FX2, pick **VOID**. Page 1: BAL, RATE, SHPE, DPTH, DRV, FDBK.
Page 2 (SETUP): COLR, HPF, NTYP on the top row.

A Part saved under stock COMB knobs will not match VOID's layout — re-pick VOID or
stamp defaults after flashing.

## Operation

- **BAL** crossfades input ↔ noise. **0 = full input** (default); turn up to bring noise in.
- **NTYP** colours the noise (WHT / PINK / BRWN) as BAL rises.
- **FDBK** with **DRV** screams; past ~50 with drive used to rail to DC silence — feedback
  is AC-coupled now so it keeps scraping.
- **COLR** open (127) is bright; turn down to darken. **HPF** 0 bypasses; turn up to thin.

## Parameters

| Page | Knob | Range | Default | What it does |
|---|---|---|---|---|
| 1 | BAL | 0..127 | 0 | input↔noise; 0 = full input, 127 = full noise |
| 1 | RATE | 0..127 | 72 | LFO rate, expo 2 Hz … 200 Hz |
| 1 | SHPE | SIN / SQR / SAW | SIN | LFO shape |
| 1 | DPTH | 0..127 | 100 | AM depth; 0 = source alone |
| 1 | DRV | 0..127 | 0 | soft-clip after AM+body+FDBK; 0 = bypass |
| 1 | FDBK | 0..127 | 0 | one-sample feedback into DRV |
| 2 | COLR | 0..127 | 64 | body low-pass; 127 = open |
| 2 | HPF | 0..127 | 0 | high-pass before COLR; 0 = bypass |
| 2 | NTYP | WHT / PINK / BRWN | WHT | noise colour |
