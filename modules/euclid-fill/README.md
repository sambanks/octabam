# `euclid-fill` — EUCLID FILL

Author: [iliamurzinov](https://github.com/iliamurzinov). Rhythm math matches
filter [EUCLID](../euclid/README.md) ([repeat98](https://github.com/repeat98)).

A standalone Euclidean **sample-trig** fill page. Hold a **TRACK** key and
press **PAGE**: a TUNER-style window opens (title + target tracks, STEPS /
PULSE (A) / ROT (B) / RAND VEL (C) / RAND PTCH (D), live pattern bar). STEPS
is the pattern length (PER TRACK: the first target track's length). **YES**
writes the rhythm onto the held track(s)' sample-trig mask (and optional
VOL/PTCH locks); **NO** or TRACK+PAGE again closes.

Not the DSP [EUCLID](../euclid/README.md) effect (filter/amp modulation).
This module only edits sequencer trigs. It does not grow
`PROJECT > CONTROL > SEQUENCER`, so it coexists with SCALE QUANTIZER.

Rhythm names, ranges, and the PULSE default match filter EUCLID; STEPS is
sourced from pattern length instead of a stored knob. Encoders **A**–**D**
turn the matching rows (same input-layer pattern as TEMPO BUS); labels show
the letter in parentheses.

## Controls

| control | does |
|---|---|
| TRACK + PAGE | open / close |
| UP / DOWN | move the cursor (PULSE / ROT / RAND VEL / RAND PTCH) |
| LEFT / RIGHT | step the focused value by 1 |
| A | PULSE (A) (focus follows) |
| B | ROT (B) (focus follows) |
| C | RAND VEL (C) (focus follows) |
| D | RAND PTCH (D) (focus follows) |
| LEVEL | turn the focused value (signed detents) |
| CUE | random placement of exactly PULSE hits (not Euclidean) |
| YES | write the current bar + VOL/PTCH locks on the targets |
| NO | close |

Targets are the track keys held when the window opened. If none were
held, the current audio track is used. **STEPS is the pattern length**
(SCALE SETUP; PER TRACK: first target track's length) — shown, not
edited. PULSE defaults to 5, ROT/RAND VEL/RAND PTCH to 0 (DRAM, not saved).

**CUE** keeps **PULSE** as density and only randomizes *which* steps are
on (uniform k-subset). **ROT** still shifts that mask. Changing **PULSE**
leaves free mode and returns to Euclidean.

**RAND VEL** (0..100) scales random AMP VOL locks on written hits:
`VOL = 64 − (r·pct)/100` with `r` in 0..63 — OT display delta **−63…0**
(never louder than 0). At 0% no VOL lock is written.

**RAND PTCH** (0..100) is the **range** of random in-scale PTCH on every
hit (not a probability — that left most hits on the Part root). 100 =
±24 semitones (±2 octaves) on FM/SY; sample tracks ±12 (PLAYBACK max).
0 = no PTCH lock. Degrees use `(ROOT+st) mod 12` against SCALE QUANTIZER.
Sample: `raw = 64+5·st`; FM/SY (`"FM",1` / `"SY",1`): `raw = 64+st`.
No quantizer / SCALE OFF: no pitch locks.

FUNC + PAGE (SCALE SETUP) and PAGE alone stay stock.

## Measured

- Not yet: the fill writer follows the bank-blob + battery-mirror + dirty
  recipe from ERASE_EMPTY_TRIGLESS_LOCKS; the window stack follows TUNER.
- `make check REMIX=euclid-fill` builds and boots under the ColdFire port.
- `tools/verify/verify_euclid_fill.py` checks the Euclidean bit pattern
  against the same `(i·k) % n < k` law as `modules/euclid/control.c`.

## On the unit

Not hardware-tested.

## Gates

`tools/verify/verify_euclid_fill.py` (stage `image`) — fast, no port:

- Euclidean bit patterns (`(i·k) % n < k`, same as filter EUCLID)
- UI contract on `euclid_fill.s`: STEPS / PULSE (A) / ROT (B) / RAND VEL (C) /
  RAND PTCH (D) labels, layout, PULSE default 5, STEPS locked via `ef_sync_len`,
  key layer (= TEMPO BUS arrow codes), encoders A–D + LEVEL, AMP VOL +
  in-scale PTCH lock writers
