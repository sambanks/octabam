# GRANULAR

A ColdFire source renderer for FLEX samples. A FLEX sample whose filename
basename starts with `GRAN` (case-insensitive) keeps the stock FLEX voice
lifecycle and playback page, but the page is relabeled with six controls:
`PTCH`, `SCAN`, `SIZE`, `SPEED`, `DENS`, and `SCAT`. Other FLEX samples use
the stock renderer and page.

Each trigger starts a grain stream. Up to four overlapping grains read the
selected sample through the stock page-aware pool walker; `PTCH` sets grain
playback rate, `SCAN` chooses the initial scan position, `SPEED` moves that
position independently, `SIZE` sets grain length, `DENS` sets the overlap
rate, and `SCAT` randomizes each grain's start around the scan position.
Grains continue to spawn while the stock FLEX voice is active, and already
started grains finish after that voice ends. The ordinary FLEX parameter
record remains the source for locks, LFOs, and scenes.

The renderer accepts the stock pool's mono/stereo 16-bit and 24-bit sample
formats and reads across pool-page boundaries. Its synthetic gate executes
the linked ColdFire code under Unicorn with generated sample data; it checks
the page descriptor, playback ABI, formats, pool boundaries, and grain
scheduling. That is not a hardware CPU measurement or a claim of hardware
safety. The code has not been run on an Octatrack.

## Gate

```bash
python3 modules/granular/generate.py --check
.venv/bin/python3 tools/verify/verify_granular.py
make bus REMIX=granular
```

The test remix is `remixes/test/granular`. No firmware image or sample data is
committed.
