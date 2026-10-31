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
randomizes grain starts around the scan point. `PTCH` spans approximately
0.5x to 1.5x grain playback speed.

The linked-code gate exercises mono/stereo 16-/24-bit reads across synthetic
pool pages, descriptor layout, and grain scheduling under Unicorn. Its
instruction counts are not hardware cycles; hardware CPU headroom and
hardware behavior remain unverified. The stock pool walker is called directly
at `0x4009499c`; sample formats are read from the stock pool's 44-byte slot
record.

## Reproduce

```bash
python3 modules/granular/generate.py --check
.venv/bin/python3 tools/verify/verify_granular.py
make bus REMIX=granular
```

No firmware image or sample data is committed. Hardware testing remains open.
