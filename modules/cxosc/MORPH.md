# CMOR / MMOR — sine→saw→square (+ PWM)

Working notes from the CX OSC morph pass. Code: `poly.s` (`sy_wshape`,
`sy_wlean`, `sy_dpw`, `sy_dpw_pulse`, `sy_loop`), `machine.s`
(`fm_e6_morph`), `po_setup_cx`.

## What it is

| Knob | Page | Role |
|------|------|------|
| **CAR** (was CMOR) | PLAYBACK SETUP A | Carrier waveshape 0..127; **FUNC** snaps 0 / 64 / 127 |
| **MOD** (was MMOR) | PLAYBACK SETUP B | Modulator waveshape 0..127 (heard through FM; needs **INDX**); **FUNC** snaps 0 / 64 / 127 |
| **PWM** | PLAYBACK SETUP F | Cycle lean — LCD **−64..+63** (**0** = neutral, byte 64): sine soft lean / saw phase-skew / square duty (**0** ≈ 50%; duty maps byte 0..127 → 16..110) |

Morph map (both oscillators):

| Amount | Shape |
|--------|--------|
| **0** | sine |
| **64** | saw |
| **127** | square |

0..63 linear sine→saw; 64..127 linear saw→square (both `/63`). MMOR always
builds the DPW pulse (no dummy-square below 64 — that stepped at the landmark).

LFO SETUP PMTR **30 = CAR**, **31 = MOD**. PWM is panel-only (not an LFO dest).

## PWM through the morph

| Morph region | What PWM does |
|--------------|-----------------|
| sine | soft half-cycle lean (`sy_wlean`) — odd harmonics |
| saw | phase-skew asymmetric ramp (`sy_wramp`) — one discontinuity; **64** = clean saw |
| square | pulse duty (**64** ≈ 50%; MMOR = DPW pulse) |

Saw PWM is not sine lean (too subtle / wrong shape) and not a triangle
morph. φ is warped **8%..92%** (CX 62’s 25%..75% barely moved on a full
0→127 sweep). MMOR pulse reprimes `S_DPWC` only on `|Δduty| ≥ 1<<24`.

Panel label is **PWM** again (same SETUP F byte as the brief WIDTH name — no remap).

## Targets (why CMOR ≠ MMOR)

| Range | **CMOR** (carrier) | **MMOR** (FM modulator) |
|-------|--------------------|-------------------------|
| → saw | phase-aligned **naive** ramp | **DPW** bandlimited saw |
| → square | **hard** pulse (`sy_sq_phi` + PWM map) | **DPW pulse** = ½(saw(φ)−saw(φ+duty)), same PWM→duty map |

Hard edges on the modulator explode carrier phase (naive saw did at ~46–48).
Feedback (`S_LASTM`) stays the **clean modulator sine**. **MIX** crossfades
to the **heard** MMOR morph (sine/saw/square), so MIX 127 solos the mod
the same way MIX 0 solos the carrier.

## Control path

| Piece | Role |
|-------|------|
| `sy_cxparm` | FOLD SYMM CMOR MMOR |
| `sy_cxpwm` | SETUP F PWM per track |
| `sy_wlean` | PWM lean on sine |
| `sy_wramp` | PWM phase-skew on saw (asymmetric ramp) |
| `sy_wshape` | `d4=sine, d1=saw, d0=square, d2=amt` → morph |
| `sy_dpw` / `S_DPWM` | MMOR saw |
| `sy_dpw_pulse` / `S_DPWC` / `S_DUTY` | MMOR square; large-jump reprime only |
| `fm_e6_morph` | FUNC → landmark snap 0/64/127 on CMOR/MMOR |
| `pg_wid_morph` | SETUP A/B icon: live sine→saw→square outline |

Stack in `sy_loop`: `0=MIX_Q8, 4=FOLD_Q8, 8=PWM, 12=SYMM, 16=morph (00 00 CMOR MMOR)`.

## On-unit check

1. FOLD ≈ 0, SYMM 64, DEC 127, PWM LCD **0** (byte 64).
2. **CMOR** 0→64→127, INDX 0: sine → hard saw → PWM square.
3. **FUNC + CMOR/MMOR**: lands on 0 / 64 / 127 only.
4. **PWM** LCD with CMOR 64: **0** = clean saw; −64 / +63 = steep↔shallow — still a saw.
5. **PWM** with CMOR 0: sine lean; CMOR 127: duty, LCD **0** ≈ 50%.
6. **PWM** with MIX 127, MMOR 64 / 127: saw skew + square duty without zipper.
7. **MMOR** 0→127, INDX ~40, CMOR 0: smooth FM colour; no jump mid-travel.
8. **MIX 127**, INDX 0, MMOR 0→64→127: hear mod sine → DPW saw → DPW square.
9. One morph at a time when comparing.

## Proof status

**CX 63** (author MKII): saw PWM phase-skew 0→127 confirmed on unit
(crest moves, stays saw-family). Port still covers sine lean / square duty /
FUNC snaps / MMOR zipper; those were exercised in the same PWM pass of
tips CX 54–63.
