# Ripple

A Mutable-Instruments-Ripples-flavoured **resonant filter** insert: a
Chamberlin state-variable filter with a drive stage in front, LP/BP/HP
select, and a resonance that reaches Q≈30. The drive clip and the in-loop
limiter on the HP node are deliberate — this is a filter to push.

Per-track insert like WarpFold: no bus role, both payloads, any track,
several instances at once. Ships in the `mutables` remix (and composes with
the other inserts).

## Knobs

| slot | name | what |
|---|---|---|
| p0 | FREQ | cutoff ~24 Hz–7.2 kHz, squared taper (the SVF's stable region) |
| p1 | RES  | resonance; 127 ≈ Q 30, short of self-oscillation |
| p2 | DRV  | input gain 1–4×, clipped at the rail |
| p3 | MIX  | dry/wet; 0 = exact passthrough |
| p7 | MODE | LP / BP / HP |

## Status

Assembles, disassembly-audited (all `mpy` signed), rendered locally through
`dsp_host`: MIX=0 bit-exact, LP/HP slopes and the BP/resonant peak measured
against prediction. **Not yet flashed** — the standing on-unit reconfirm
applies.
