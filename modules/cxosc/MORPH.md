# CMOR / MMOR — sine→saw→square (+ WIDTH)

Working notes from the CX OSC morph pass. Code: `poly.s` (`sy_wshape`,
`sy_wlean`, `sy_dpw`, `sy_dpw_pulse`, `sy_loop`), `machine.s`
(`fm_e6_morph`), `po_setup_cx`.

## What it is

| Knob | Page | Role |
|------|------|------|
| **CMOR** | PLAYBACK SETUP A | Carrier waveshape 0..127; **FUNC** snaps 0 / 64 / 127 |
| **MMOR** | PLAYBACK SETUP B | Modulator waveshape 0..127 (heard through FM; needs **INDX**); **FUNC** snaps 0 / 64 / 127 |
| **WIDTH** | PLAYBACK SETUP F | Cycle lean (**64** = neutral): sine lean / saw ramp-balance / square duty (**64** = 50%; knob maps 0..127 → peak/duty 16..110) |

Morph map (both oscillators):

| Amount | Shape |
|--------|--------|
| **0** | sine |
| **64** | saw |
| **127** | square |

0..63 linear sine→saw; 64..127 linear saw→square (both `/63`). MMOR always
builds the DPW pulse (no dummy-square below 64 — that stepped at the landmark).

LFO SETUP PMTR **30 = CMOR**, **31 = MMOR**. WIDTH is panel-only (not an LFO dest).

## WIDTH through the morph

| Morph region | What WIDTH does |
|--------------|-----------------|
| sine | soft half-cycle lean (`sy_wlean`) — odd harmonics |
| saw | phase-based ramp-balance (`sy_wramp` from φ, not the saw sample) |
| square | pulse duty (**64** ≈ 50%; MMOR = DPW pulse) |

Saw WIDTH used to treat the saw sample as phase — that warped DPW/naive and
sounded wrong. MMOR WIDTH used to reprime `S_DPWC` on every Q8 duty step and
froze `S_LASTP` for the whole slew (zipper). Reprime only on `|Δduty| ≥ 1<<24`.

Old Parts that saved the F byte as “PWM” load as WIDTH (same slot — no remap).

## Targets (why CMOR ≠ MMOR)

| Range | **CMOR** (carrier) | **MMOR** (FM modulator) |
|-------|--------------------|-------------------------|
| → saw | phase-aligned **naive** ramp | **DPW** bandlimited saw |
| → square | **hard** pulse (`sy_sq_phi` + WIDTH map) | **DPW pulse** = ½(saw(φ)−saw(φ+duty)), same WIDTH→duty map |

Hard edges on the modulator explode carrier phase (naive saw did at ~46–48).
Feedback (`S_LASTM`) stays the **clean modulator sine**. **MIX** crossfades
to the **heard** MMOR morph (sine/saw/square), so MIX 127 solos the mod
the same way MIX 0 solos the carrier.

## Control path

| Piece | Role |
|-------|------|
| `sy_cxparm` | FOLD SYMM CMOR MMOR |
| `sy_cxpwm` | SETUP F WIDTH per track |
| `sy_wlean` | WIDTH lean on sine |
| `sy_wramp` | WIDTH ramp-balance on saw (uniform φ) |
| `sy_wshape` | `d4=sine, d1=saw, d0=square, d2=amt` → morph |
| `sy_dpw` / `S_DPWM` | MMOR saw |
| `sy_dpw_pulse` / `S_DPWC` / `S_DUTY` | MMOR square; large-jump reprime only |
| `fm_e6_morph` | FUNC → landmark snap 0/64/127 on CMOR/MMOR |

Stack in `sy_loop`: `0=MIX_Q8, 4=FOLD_Q8, 8=WIDTH, 12=SYMM, 16=morph (00 00 CMOR MMOR)`.

## On-unit check

1. FOLD ≈ 0, SYMM 64, DEC 127, WIDTH 64.
2. **CMOR** 0→64→127, INDX 0: sine → hard saw → WIDTH square.
3. **FUNC + CMOR/MMOR**: lands on 0 / 64 / 127 only.
4. **WIDTH** with CMOR 0: sine colour moves; with CMOR 64: ramp lean (not “sample as phase”); with CMOR 127: duty, 64 ≈ 50%.
5. **WIDTH** with MIX 127, MMOR 64 / 127: saw lean + square duty should slew without zipper (CX 59 froze the pulse).
6. **MMOR** 0→127, INDX ~40, CMOR 0: smooth FM colour; no jump mid-travel.
7. **MIX 127**, INDX 0, MMOR 0→64→127: hear mod sine → DPW saw → DPW square.
8. One morph at a time when comparing.

## Proof status

Port / selftest do not replace hearing. Do not mark `Proof.HARDWARE` for
WIDTH lean / FUNC morph snaps until Ilia confirms a tip on the unit.
