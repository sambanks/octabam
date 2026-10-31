Play a FLEX sample as a cloud of four overlapping grains.

## Access

Name a stereo or mono 16- or 24-bit sample so its file name begins `GRAN` (for example `GRAN-PAD.wav`), load it into a FLEX slot, and play it on a FLEX track. The track's playback page becomes GRANULAR. Not in `octabam` or `octabam-bus` yet: only the `granular` test remix carries it, and it cannot share an image with SYNTH, OCTA303, BLACKPYRAMIDS_303, ANALOG BD or CX OSC.

## Operation

| knob | does |
|---|---|
| PTCH | pitch of each grain |
| SCAN | where in the sample grains start |
| SIZE | grain length |
| SPEED | how fast the start position moves; 0 holds it still |
| DENS | how many grains overlap, up to four |
| SCAT | random scatter of each grain's start |

Trigs, parameter locks, LFOs and scenes work as on any FLEX page. A trig restarts the scan. Grains keep starting while the FLEX voice plays, and the grains already started finish after it stops.

A new project holds zeros in these knobs, so set SIZE, SPEED and DENS before you listen.

## Limits

- Measured only under the ColdFire port, not on an Octatrack.
- Four grains per track; the sample is read from the already loaded FLEX pool.
- It costs more ColdFire time than a normal sample: 38.1k against 25.6k emulator instructions per frame, one track. Several GRAN tracks at once are unmeasured.
