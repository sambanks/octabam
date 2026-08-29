# Streamz

A Mutable-Instruments-Streams-flavoured **lowpass gate**: the track's own
level drives an envelope follower, and that envelope opens a filter and an
amplifier *together* — the Buchla vactrol behaviour. Quiet material is dark
**and** quiet; loud transients are bright **and** loud. There is nothing like
it in the stock effects.

Per-track insert, no buffer, so it stacks with the other inserts.

## Knobs

| slot | name | what |
|---|---|---|
| p0 | SENS | follower drive; 64 is unity (a full-scale peak opens it fully) |
| p1 | FALL | release, T60 20 ms–700 ms; short is plucky, long is a slow vactrol |
| p2 | COLR | how open the filter stays when the gate is *shut*; 0 is a true gate |
| p3 | MIX  | dry/wet; 0 = exact passthrough |
| p7 | MODE | LPG (filter+amp) / VCF (filter only) / VCA (amp only) |

Attack is fixed and fast on purpose — the rectified input *is* the attack, so
only the release is on a knob. An LPG whose attack you can slow down stops
sounding like an LPG and becomes a swell pedal.

## Status

Assembles (255 words), disassembly-audited, rendered locally:

- MIX=0 **bit-exact** passthrough.
- **Release tracks the design** across the whole knob: measured T60
  26 / 52 / 139 / 479 / 731 ms at FALL 0 / 32 / 64 / 96 / 127, against a
  design of 20 / 46 / 134 / 458 / 700 ms.
- **The vactrol coupling is real and measured**: identical noise at two
  levels comes out with spectral centroids of 9,880 Hz (loud) and 2,620 Hz
  (quiet). That single number is the whole point of the module.

The release knob is spent on the decay *rate* with a cubic taper, because a
release coefficient is hyperbolic in decay time — spending the knob linearly
on the coefficient crams every useful value into the last few steps, which is
the flaw `rungs`' DAMP still has.

**Not yet flashed** — knob publishes and the MODE select ride the standing
on-unit reconfirm.
