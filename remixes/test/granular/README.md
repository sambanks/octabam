# Granular source gate

This test remix carries the optional `GRANULAR` FLEX source engine and the
stock effects. Assign a FLEX sample whose filename begins `GRAN` (case
insensitive) to a track. The playback page then exposes `PTCH`, `SCAN`,
`SIZE`, `SPEED`, `DENS`, and `SCAT`; all other FLEX samples keep the stock
renderer and page.

The engine starts a grain stream on each sequencer trigger and continues
spawning while the stock FLEX voice is alive. Existing parameter locks, LFOs,
and scenes feed the playback record used by FLEX. `SCAN` chooses the initial
scan point; `SPEED` moves the scan cursor independently from `PTCH`; `SIZE`
sets grain length; `DENS` selects one through four overlapping grains; `SCAT`
randomizes grain starts around the scan point. `PTCH` retains stock FLEX's
five raw units per semitone: raw 64 unity, 4/124 one octave down/up, 0.5x
to 2x. The old linear 0.5x-1.5x claim is retracted.

The linked-code gate exercises mono/stereo 16-/24-bit reads across synthetic
pool pages, descriptor layout, and grain scheduling under Unicorn. Its
instruction counts are not hardware cycles; hardware CPU headroom and
hardware behavior remain unverified. The stock pool walker is called directly
at `0x4009499c`; sample formats are read from the stock pool's 44-byte slot
record. Loaded 24-bit samples are reduced to 16-bit before interpolation.
The registered firmware gate uses a firmware-generated project and synthetic
WAVs, with actual pool reads, sequencer, both DSP cores and MAIN L/R.
See [the module](../../../modules/granular/README.md) for measured pitch,
control, lifecycle, clipping/tone-integrity and capture-phase qualifications.
The mutable C state is serialized as explicit zero-initialized data; the
linked and loader gates reject missing boot bytes.

The final registered image gate passes all 27 firmware cases locally.
Its image is bit-identical to the initialized 26-case run; the added
stock-FX2 baseline qualifies the final verifier's isolated FX1 comparison.
Every captured MAIN channel is unclipped. This is port qualification,
not a full-remix `make check`, remote CI result or hardware qualification.

## Reproduce

```bash
python3 modules/granular/generate.py --check
make bus REMIX=granular
.venv/bin/python3 tools/verify/module_gates.py --shared granular --modules GRANULAR
REMIX=granular .venv/bin/python3 tools/verify/verify_dram_boot.py --existing-image
.venv/bin/python3 tools/verify/module_gates.py granular --stage image --modules GRANULAR
```

No firmware image or sample data is committed. Hardware testing remains open.
