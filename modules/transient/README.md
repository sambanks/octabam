# `transient` -- TRANSIENT

A transient shaper: ATCK boosts or softens each onset, SUST lengthens or tightens each tail.

On the unit it is an FX2 effect with five knobs on page 1. Turn ATCK up for more punch on drums and plucks, down to soften them; turn SUST up for more room and ring, down to dry a loop out. It has no threshold: the same setting does the same thing to a quiet hit and a loud one, because the detector measures the shape of the envelope in log2 units, not its level. No lookahead, no buffers. The law and the reasoning behind each choice are in [`DESIGN.md`](DESIGN.md); [`transient_ref.py`](transient_ref.py) is the float reference the DSP is proved against.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | ATCK | -64..+63 | onset gain: up to +12 dB at +63, -12 dB at -64; 0 untouched |
| 1 | 1 | SUST | -64..+63 | tail gain: up to +12 dB at +63, -12 dB at -64; 0 untouched |
| 1 | 2 | TIME | 0-127 | how long an onset counts as the transient: 5 ms at 0, 50 ms at 127 (logarithmic); default 40 |
| 1 | 3 | OUT | -64..+63 | output trim, -12 to +12 dB |
| 1 | 4 | MIX | 0-127 | dry/wet; 0 is an exact passthrough, 127 full wet |

ATCK and SUST together are clamped to ±12 dB; OUT adds up to a further ±12 dB.

## Open

- Voicing beyond one drum loop: the constants (0.5 ms, 50 ms, 500 ms, 10 ms peak release, ±2 bits, the 3 dB onset margin) are first choices.
- Whether 2 bits (12 dB) is the right ATCK/SUST range.
- A gate under the port that measures TRANSIENT's own gain law in a project (today the port proves it loads and passes audio; the law is proved by `dsp_host`).

## Design

[`DESIGN.md`](DESIGN.md): the law, why the peak detector and the S lag cap are there (each fixed a defect the float reference found), the r7 slots, the tables.
