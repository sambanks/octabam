Play a FLEX sample as a cloud of four overlapping grains.

## Access

Name a stereo or mono 16- or 24-bit sample so its file name begins `GRAN` (for example `GRAN-PAD.wav`), load it into a FLEX slot, and play it on a FLEX track. The track's playback page becomes GRANULAR. The standard `octabam` and `octabam-bus` selections are unchanged; optional test presets are `granular`, `granular-octabam` (OCTA303 replaced), and `granular-bus` (GRANULAR added). It cannot share an image with SYNTH MACHINE, OCTA303, BLACKPYRAMIDS_303, ANALOG BD or CX OSC.

## Operation

| knob | does |
|---|---|
| PTCH | Stock FLEX pitch, -12 to +12 semitones; one octave is exactly half/double the grain rate |
| SCAN | Initial scan position at the next trigger |
| SIZE | Grain length, 64 to 8192 samples |
| SPEED | Forward scan rate; 0 frozen, 64 unity, 127 about 1.98x |
| DENS | One to four overlapping grains |
| SCAT | Random start offset, up to one eighth of sample length either side |

Pitch locks, scene endpoints and pitch LFO delivery are measured through the real firmware under the port. A trig restarts the scan. Grains keep starting while the FLEX voice plays; those already started finish after it stops, with a tail bounded by 8192 samples plus transport latency. SCAN applies at the next trig, and PTCH/SCAT apply to new grains rather than retuning those already playing.

An existing FLEX Part retains its stock control bytes when a GRAN sample is selected; renaming a sample does not stamp new defaults. A useful explicit starting point is raw `PTCH 64, SCAN 0, SIZE 48, SPEED 64, DENS 80, SCAT 0`. Normal samples use the stock FLEX meanings for those same bytes.

Use overlap for smoother clouds: one-grain, frozen or scattered playback can expose grain boundaries.

## Limits

- Measured only under the ColdFire port, not on an Octatrack.
- Four grains per track, read from the already loaded FLEX pool; no live recorder-buffer or STATIC streaming support.
- Mono/stereo 16-/24-bit pool layouts are checked, but interpolation uses signed 16-bit precision.
- The source window is the first 16,777,215 frames (about 6 minutes 20 seconds); larger samples are cropped to that window.
- Two dense tracks and four default clouds are measured under the port. Maximum-density four-track clouds, eight-track use and arbitrary effect combinations are not qualified.
- The standard and bus test presets each pass a 14-case firmware subset, boot/menu/USB enumeration checks and a counted DSP budget against upstream `99170b16`. Standard MODULATION/SPECTRUM code publication and isolated FX1 audio, and bus sends/CHARACTER, are checked on both cores. This does not qualify every utility, USB host streaming or hardware.
- Newer fetched upstream `b5da2db2` is not integrated or qualified here. Its standard preset adds CX OSC; a GRANULAR derivative must remove that conflicting source as well as OCTA303.
- The standalone registered gate passes 27 firmware cases and retains private audio and instruction-load reports under `out/granular/port-gate/`. Emulator instructions are not hardware cycles or a safe track-count limit.
- Earlier four-track evidence only checked completed frames and nonzero audio, missing corrupted MAIN output. The optimized renderer preserves source PCM and passes added clipping/tone-integrity checks; its state also now ships as explicit zero-initialized loader data.
- The earlier "+12 = about 1.14x" and 0.5x-1.5x descriptions were an incorrect raw-unit label and linear mapping; those claims are retracted. Clean one-octave-up audio now measures 600.0001 Hz from a 300 Hz source.
