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

## Controls and precision

| Control | Mapping |
|---|---|
| PTCH | Stock FLEX pitch: five raw units per semitone, raw 64 neutral, raw 4/124 one octave down/up; 0.5x to 2x |
| SCAN | Initial position at the next trigger, 0 to the latest full-grain start |
| SIZE | 64 to 8192 samples, about 1.45 to 185.76 ms at 44.1 kHz |
| SPEED | Forward scan rate, raw 0 frozen, 64 unity, 127 about 1.98x |
| DENS | One to four overlapping grains; hop = grain length / density |
| SCAT | Bounded random offset, up to one eighth of the sample length either side |

The renderer accepts the stock pool's mono/stereo 16-bit and 24-bit sample
formats and reads across pool-page boundaries. **24-bit samples are reduced
to signed 16-bit before interpolation**; accepting their pool layout is not
a 24-bit precision claim. Pitch coefficients use Q16 with fractional carry;
positions/interpolation use Q8. SCAN is read when a trigger starts the
stream. SIZE, SPEED and DENS update at the render boundary; PTCH and SCAT
affect newly spawned grains, not grains already playing.

The addressable source window is the first 16,777,215 frames (about 6 minutes
20 seconds at 44.1 kHz); larger pool samples are cropped to that window.
FLEX recorder buffers and CF-backed STATIC streaming are not supported.
The source uses no DSP grain buffers, but still pays for the ordinary FLEX
renderer and the ColdFire grain loop. The code has not run on an Octatrack.

## Measured under the ColdFire port (not hardware)

`tools/verify/verify_granular_port.py` generates a project through the
firmware, stages private synthetic WAVs and runs the actual FLEX pool,
sequencer, both DSP cores and MAIN L/R. It checks the loaded pool flags, not
just the WAV header. Unequal stereo channels prevent a duplicated-left
implementation from passing. The stub-based gate had missed the original
cursor/header bug: capture the stock cursor pointer before calling stock;
read its sample count from header byte 3.

Clean frozen grains from a 300 Hz source measured 150.0000 Hz at -12
semitones, 300.0000 Hz at unity, 600.0001 Hz at +12 and 317.8387 Hz at +1.
The gate allows at most one cent of error. **Retracted:** the earlier
approximately 0.5x-1.5x mapping was linear, and raw 76 was incorrectly
called "+12"; its roughly 337 Hz output was not an octave-up test.

Pitch locks return from 300 to 600 to 300 Hz on unlocked steps. Scene
endpoints reach 300/600 Hz; the pitch LFO publishes 20 distinct grain rates
in the fixture. Those are control-specific measurements, not a proof of
every lock, scene or LFO destination.

An ordinary unequal-stereo FLEX sample's **transported source and post-FX
DSP readback are bit-identical** with the granular hooks enabled or restored
privately to stock. **Retracted:** this is not raw MAIN capture identity;
the port's right serial channel can differ by one sample of capture phase.
Both MAIN channels are separately checked for audio and correct pitch.

The registered gate also checks scan position/rate, size/density/scatter
audio changes, end-of-sample saturation, pattern retrigger, bounded MIDI
Stop, ordinary/granular coexistence, multiple tracks and active effects.
Dry fixtures must not clip MAIN. The unscattered two-/four-track references
also require the intended left/right tones with at most 1% relative RMS
residual, rather than accepting any nonzero output.
The effects comparison isolates FX1 with identical FX2 settings; the bus
comparison isolates sends first, then CHARACTER with the sends unchanged.
Transported source stays bit-identical. Demand-loaded effects must have
checksum-published entries and their built code words on both cores, not
merely an armed CPU loader flag or audio changed by stock DELAY/reverb.
It retains each command, WAV, pool/state dump and JSON report under
`out/granular/port-gate/run-*/`. A failure stops the gate; earlier results
remain in its partial report.

**Retracted:** an earlier four-default-track pass only established nonzero
audio and completed frames; its MAIN output was clipped and corrupted.
Paired stereo pool reads and skipping unused interpolation neighbors
remove redundant work without changing source PCM. The corrected render
passes the strengthened MAIN assertions; those assertions reject the old
capture. This is not a hardware admission limit or proof of every
track-count, density and effect combination.

The track state, descriptor and ready flag are explicitly zero-initialized
in the serialized DRAM payload. Implicit C globals had landed in unshipped
`.bss`, hidden by the port's zero-filled memory. Both the linked gate and
the actual loader boot gate now reject missing initialization.

### Reference load envelope

The initialized standalone image's 27-case run measured these **average
emulator instructions per 16-sample frame**, not chip cycles or deadlines:

| Fixture | Instructions/frame | Clipped MAIN samples, L/R |
|---|---:|---|
| One ordinary FLEX, granular hooks enabled | 23,276 | 0 / 0 |
| One scanning reference cloud | 28,884 | 0 / 0 |
| Pitch LFO, one track | 33,719 | 0 / 0 |
| Two reference clouds, T1/T5 | 36,771 | 0 / 0 |
| Two dense/scattered tracks, T1/T5 | 41,332 | 0 / 0 |
| Four ordinary FLEX tracks | 30,287 | 0 / 0 |
| Four reference clouds, T1/T2/T5/T6 | 52,754 | 0 / 0 |

Reference clouds explicitly use raw `64, 0, 48, 64, 80, 0`; DENS 80
means three overlapping grains. The dense fixture uses raw
`69, 0, 0, 127, 127, 127`: four grains, 64-frame size and maximum
scatter/scan speed. Its source ends during the capture, so that average
is **not a sustained or peak-load bound**. Four-reference MAIN tone
residuals are about 0.000028 relative RMS on each channel.

These are tested fixtures, not admission guarantees. Four maximum-density
tracks, eight-track use, live inputs and arbitrary effect combinations are
not qualified. No density was reduced to obtain the corrected results.

## Gate

```bash
python3 modules/granular/generate.py --check
make bus REMIX=granular
.venv/bin/python3 tools/verify/module_gates.py --shared granular --modules GRANULAR
REMIX=granular .venv/bin/python3 tools/verify/verify_dram_boot.py --existing-image
.venv/bin/python3 tools/verify/module_gates.py granular --stage image --modules GRANULAR
```

The linked-code gate checks descriptor retention and handlers, all pitch
coefficients, exact fractional advancement, mono/stereo pool boundaries and
the longest supported sample's position guard under Unicorn. It builds the
smallest registered GRANULAR fixture first, so another gate's runtime in
`out/` cannot be mistaken for its input; an optional remix argument checks a
specific candidate instead. Its maximum
observed 6,348 instructions/call is **not ColdFire cycles**; the earlier
10,403 count preceded the sample-read optimization.

The firmware gate's default path needs only the user's stock image and the
worktree's port, not a mounted card or project input. `--case` selects a
bounded subset and automatically adds the comparison case for audio-change
tests. `main.wav` in each case directory is a private stereo audition file.
No firmware image, project or sample data is committed.

## Composition

The optional presets `granular-octabam` and `granular-bus` derive from
upstream `octabam` and `octabam-bus`; the standard presets are unchanged.
See their READMEs under `remixes/test/` for exact selections and qualification.
GRANULAR cannot coexist with SYNTH MACHINE, OCTA303, BLACKPYRAMIDS_303,
ANALOG BD or CX OSC: they share the FLEX renderer/page hooks. Replacing
OCTA303 is necessary for the standard bundle; the bus bundle needs no source
machine removed.

Against upstream `99170b16`, both candidate builds, their selected-module
ledgers and 14-case firmware subsets pass. Both also pass serialized
initialization, actual boot, menu and USB enumeration/settings gates.
The standard fixture proves MODULATION/SPECTRUM checksum publication on
both cores and isolates their FX1 audio from unchanged stock FX2; the bus
fixture isolates sends and then CHARACTER. Every tested MAIN capture is
unclipped. Four-reference averages are 54,590 instructions/frame for the
standard candidate and 53,596 for the bus candidate, not hardware bounds.

Newer fetched upstream `b5da2db2` is not integrated in this qualification.
It adds CX OSC to standard octabam; that module would also need removal
when adapting the standard GRANULAR preset to the newer base. DRAM
placement does not remove their shared FLEX renderer/page-hook conflict.

The registry/ledger, image gates and emulator renders prove different
things. None measures the unit's CPU cache, DMA deadlines or hardware
headroom; a successful build or port run is not hardware qualification.
