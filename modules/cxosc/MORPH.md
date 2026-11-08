# CMOR / MMOR — sine→saw→square (+ PWM)

Working notes from the CX OSC morph pass. Code: `poly.s` (`sy_wshape`,
`sy_dpw`, `sy_dpw_pulse`, `sy_pulse`, `sy_loop`), `machine.s`
(`fm_e6_morph`), `po_setup_cx`.

## What it is

| Knob | Page | Role |
|------|------|------|
| **CMOR** | PLAYBACK SETUP A | Carrier waveshape 0..127 |
| **MMOR** | PLAYBACK SETUP B | Modulator waveshape 0..127 (heard through FM; needs **INDX**) |
| **PWM** | PLAYBACK SETUP F | Pulse width for the square end (**64** ≈ 50%) |

Morph map (both oscillators):

| Amount | Shape |
|--------|--------|
| **0** | sine |
| **64** | saw |
| **127** | square |

0..63 linear sine→saw; 64..127 linear saw→square. Exact `/127` endpoints.

LFO SETUP PMTR **30 = CMOR**, **31 = MMOR**. PWM is panel-only (not an LFO dest).

## Targets (why CMOR ≠ MMOR)

| Range | **CMOR** (carrier) | **MMOR** (FM modulator) |
|-------|--------------------|-------------------------|
| → saw | phase-aligned **naive** ramp | **DPW** bandlimited saw |
| → square | **hard** pulse (`sy_pulse` + PWM) | **DPW pulse** = ½(saw(φ)−saw(φ+duty)) |

Hard edges on the modulator explode carrier phase (naive saw did at ~46–48).
Feedback (`S_LASTM`) stays the **unmorphed modulator sine**.

## Control path

| Piece | Role |
|-------|------|
| `sy_cxparm` | FOLD SYMM CMOR MMOR |
| `sy_cxpwm` | SETUP F per track |
| `sy_wshape` | `d4=sine, d1=saw, d0=square, d2=amt` → morph |
| `sy_dpw` / `S_DPWM` | MMOR saw |
| `sy_dpw_pulse` / `S_DPWC` | MMOR square (second differentiator) |
| `sy_pulse` | CMOR square |

Stack in `sy_loop`: `0=MIX_Q8, 4=FOLD_Q8, 8=PWM, 12=SYMM, 16=morph (00 00 CMOR MMOR)`.

## On-unit check

1. FOLD ≈ 0, SYMM 64, DEC 127, PWM 64.
2. **CMOR** 0→64→127, INDX 0: sine → hard saw → PWM square.
3. **PWM** with CMOR 127: duty moves; 64 ≈ 50%.
4. **MMOR** 0→127, INDX ~40, CMOR 0: smooth FM colour; no jump mid-travel.
5. One morph at a time when comparing.

## Proof status

Port / selftest do not replace hearing. Do not mark `Proof.HARDWARE` for
square/PWM until Ilia confirms a tip on the unit.
