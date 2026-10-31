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

## Measured under the ColdFire port (not hardware)

A generated project and a synthetic stereo 16-bit WAV (300 Hz for 1 s, then
600 Hz) ran on the real firmware under the port. The stub-based gate had missed
a real bug, now fixed: the renderer must read the stock cursor pointer before
the stock renderer call, and take the sample count from header byte 3.

| Controls | Measured |
|---|---|
| defaults | 300 Hz, then 600 Hz at 1 s (the scan follows the source) |
| SPEED 0 | 296 Hz held (scan frozen) |
| SPEED 0, SCAN max | 591 Hz |
| PTCH +12 | 337 Hz (about 1.14x) |
| SCAT 40 | pitch and level jitter |

A normal sample passes through bit-identically to stock. Average ColdFire
load was 37.8k instructions per frame against about 24.4k for stock (emulator
counts, not hardware timing). The fixture's two-second pattern loop
retriggers the voice and the scan restarts at 300 Hz each time, with a
continuous level over a 5 s run. A MIDI Stop (0xFC) at 2.2 s ended the audio:
RMS fell from 0.061 to 0.055, 0.058 and then to exactly 0, so grains do not
run on after the voice stops (that tail is bounded by the longest grain).
Granular knob values written into a normal sample's FLEX slots change its
length and rate, as for any FLEX control; that is stock behavior, not a fault.
The compatibility with other modules, mono samples on the real firmware and
the load with effects running have not been measured.

## Gate

```bash
python3 modules/granular/generate.py --check
.venv/bin/python3 tools/verify/verify_granular.py
make bus REMIX=granular
```

The test remix is `remixes/test/granular`. No firmware image or sample data is
committed.
