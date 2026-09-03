# Rungs

A Mutable-Instruments-Rings-flavoured **modal resonator** insert: the
track's own audio excites a bank of eight two-pole resonators tuned to a
partial series — Rings-as-an-effect. Drums become struck metal; melodies
ring through a bell.

Per-track insert like WarpFold: no bus role, both payloads, any track.
Ships in the `mutables` remix.

## Knobs

| slot | name | what |
|---|---|---|
| p0 | FREQ | fundamental ~55 Hz–1.25 kHz, squared taper |
| p1 | STRC | stretches the partial series sharp, more per higher mode |
| p2 | DAMP | ring time T60 ~0.1-9 s |
| p3 | MIX  | dry/wet; 0 = exact passthrough |
| p7 | MODE | STRING (harmonic) / BELL / GLASS (stretched) |

## Notes

Mode frequencies are computed per block from the knobs; cos comes from a
half-angle polynomial with ~0.2% tuning error at the extremes 🟡 — a
resonator a few cents sharp at the top is character, not a defect. A future
hook: the tempo-sync cave already publishes MIDI note, so FREQ could track
played notes the way note→PITCH does on BusDelay.

## Status

Assembles, disassembly-audited, rendered locally: MIX=0 bit-exact, mode
ring frequencies measured against the ratio tables, decay time tracks DAMP.
**Not yet flashed** — the standing on-unit reconfirm applies.
