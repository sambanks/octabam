# BongDelay

A multi-mode delay — CLEAN, PITCH (a once-per-repeat harmoniser), GRAIN (a
granular cloud) and REVERSE — with tape-style wow/flutter (DPTH/RATE), drive
(DRV, doubling as GRAIN's scatter depth) and a FREEZE hold available in
**every** mode. Its wet can be sent on into ChonVerb over the bus (`-VRB`),
which is the series topology the stock firmware has no path for.

Hosted on payload B (core 1), which serves **tracks 1–4**.

MODE still counts five positions; the retired TAPE slot aliases CLEAN now
that the tape character is global.

TIME is a free dial with a sticky snap: near a division it snaps, holds that
division through tempo changes, and lets go when the knob moves. The panel
label comes from the [`tempo-sync`](../tempo-sync/) module's formatter cave.

## Local rendering

`dsp_host` cannot boot payload B, so this module renders only through the DEV
hatch (`make render-delay`), which places it out of region in payload A.
`DFRZAT=n` engages FREEZE after n blocks so a render can catch it mid-flight.

## Open

- GRAIN's density gate only subtracts energy, so sparse always costs level.
  It needs makeup gain on the surviving grains, which does not exist yet.
- The delay return is ~4 dB quieter than the reverb at equal send.
