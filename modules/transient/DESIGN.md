# TRANSIENT: design note

2026-10-03. Status: DSP56300 implementation in `transient.asm`, render-gated against `transient_ref.py` (`tools/verify/verify_transient.py`), port-gated by `verify_set`, and run on a MKII (image OCTABAM2, 3 Oct 2026; README "On the unit").

## What it does

Two bipolar knobs reshape a sound's envelope without a threshold:

- **ATCK** (attack): positive makes onsets punchier, negative softens them.
- **SUST** (sustain): positive lengthens tails and room, negative tightens them.

Level-independent: the same setting does the same thing to a quiet and a loud hit, because it acts on the *shape* of the envelope, not its level. This is the classic "differential envelope" transient designer.

## The law

All detection happens in the log domain (log2 units, "bits": 1 bit = 6.02 dB), so the followers are dB-linear and the result is level-independent.

1. **Detector**: `d = max(|L|, |R|)` (stereo-linked, so the image does not wander), then a **linear peak detector** (instant attack, 10 ms release) so the log does not dive at every zero crossing, floored at 2^-16 (-96 dBFS). Without it a steady 1 kHz tone pumped by +2.5 dB in the reference (2026-10-03); with it, +0.11 dB.
2. **Log**: `Lg = log2(d)`. On the DSP: `clb` gives the exponent, `normf` the mantissa m in [0.5, 1), and a 33-point interpolated table gives log2(m). Both instructions are in Elektron's own payloads (`clb b,a` / `normf a1,b`, three sites each on A and B; checked 2026-10-03), so the form has run on the chip.
3. **Three one-pole followers on Lg**, each asymmetric (one coefficient rising, another falling, chosen per sample with a Tcc, branch-free):

   | Follower | Attack | Release | Role |
   |---|---|---|---|
   | F (fast) | 0.5 ms | 50 ms | tracks the envelope closely |
   | S (slow attack) | TIME (5-50 ms, knob) | 50 ms | lags behind onsets |
   | H (hold) | 0.5 ms | 500 ms | lags behind decays |

   The linear peak keeps **48 bits** on the DSP, formed as `pk - pk*(1-r)`: with 24 bits each `pk*r` truncated a whole LSB per sample, so the release ran fast below about -80 dBFS and level independence on the DSP was 0.27 dB; with 48 bits, 0.028 dB. H keeps 48 bits for the same reason (a 500 ms coefficient times a small difference rounds to nothing in 24 bits).

   After updating S: **`S = max(S, F - 2 bits)`**. The slow follower may lag the fast one by at most the gain clamp. Without this, after silence S starts at the floor, so a loud hit opens a bigger gap than a quiet one and its boost lasts longer (6.8 dB level dependence in the reference). With it, every onset starts from the same gap. A similar cap on F and H was tried and dropped: it made the gain jump 12 dB in one sample at an onset (a click risk on material rising out of a bed).

   **A new hit starts its own tail (law v3).** When `v > F + 0.5 bit` (the input more than 3 dB above the envelope), `H = min(H, v - 0.5 bit)`.

4. **Shape signals** (bits, clamped at 0):
   - `atk = max(F - S, 0)`: positive for about TIME after each onset.
   - `sus = max(H - max(F, v - 0.5 bit), 0)`: positive while the sound decays, zero at the instant of a new hit.
5. **Gain** (bits): `g = ATCK * kA * atk + SUST * kS * sus`, with ATCK and SUST in -1..+1, then clamped to ±RANGE (2 bits = ±12 dB).
6. **Apply**: `G = 2^g` from a 33-point table over [-2, +2] bits, stored as 2^(g-2) and shifted left 2 on the multiply (the limiting store saturates). `y = x * G` on both channels.
7. **MIX**: `out = x + MIX * (y - x)`; MIX 0 is an exact passthrough.

Per-block (not per-sample): the followers' coefficients from TIME, and the knob scalings. That is where any division or exp happens.

## Knobs (proposal)

| Page | Slot | Name | Range | Default | What |
|---|---|---|---|---|---|
| 1 | 0 | ATCK | -64..+63 | 0 | onset boost/cut; 0 = none |
| 1 | 1 | SUST | -64..+63 | 0 | tail boost/cut; 0 = none |
| 1 | 2 | TIME | 0..127 | 40 | length of the "transient" window, 5-50 ms |
| 1 | 3 | OUT | -64..+63 | 0 | output trim, ±12 dB |
| 1 | 4 | MIX | 0..127 | 127 | dry/wet; 0 = exact passthrough |
| 1 | 5 | (blank) | | | |

Page 2 empty for now. abbr `TRNS`, fullname `Transient`. ATCK = SUST = 0 must be bit-exact passthrough (g = 0, G = 1).

## Cost

Estimated at about 70 cycles/sample before writing the code. **Measured: 166 cycles/sample** (`make cycles REMIX=transient`, branch-free so the word span is the cost). The estimate missed that long immediates and displaced moves cost two cycles each, and the 48-bit states. Still under the ~200 target; four instances on one core price at 664 of 4,535.

## What would falsify the design

- Audible zipper or crackle at fast TIME: the followers are too fast for the 2^g table step. Check with a sine and ATCK at max.
- Level dependence: would mean the floor or the log table is wrong.
- Pumping on sustained material (pads): `atk` should be near 0 there; measure with a steady tone.
