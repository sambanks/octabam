# `octa303-seam` — the hybrid OCTA-303

OCTA303 with [OCTA303 SEAM](../../../modules/octa303-seam/README.md): the ColdFire keeps the knobs, the sequencer,
the envelopes, the accent, the slide and the VCO; the DSP renders FM, the filter, the VCA, MUFF, DIST and the output
stage at the track's source. With [dEVILish](../../../modules/devilish/README.md) for the Devil Fish knobs.

## What is in it

- **OCTA303**, **OCTA303 SEAM**, **DEVILISH**.
- the stock effects but DJ EQ (the seam's tables live in its curve bank), COMPRESSOR and LO-FI (their P words hold
  the seam's code) and PHASER (dEVILish takes its id).

Put one OCTA-303 track in T1–T4 and one in T5–T8: each DSP core renders the voices of its own four tracks.

## Build

```bash
make image REMIX=test/octa303-seam BUILD=1
```

`make check REMIX=test/octa303-seam` runs every gate first.
