# CMOR / MMOR — sine→saw morph (findings)

Working notes from the CX OSC morph pass (builds **CX 6…15**, 6 Nov 2026).
Code: `poly.s` (`sy_epmix`, `sy_dpw`, `sy_loop`), `machine.s` (`fm_e6_morph`),
`po_setup_cx`. Flash tip at the time of writing: **CX 15**.

## What it is

| Knob | Page | Role |
|------|------|------|
| **CMOR** | PLAYBACK SETUP A | Carrier waveshape morph 0..127 |
| **MMOR** | PLAYBACK SETUP B | Modulator waveshape morph 0..127 (heard through FM; needs **INDX**) |

LFO SETUP PMTR **30 = CMOR**, **31 = MMOR**.

**As of CX 15:**

- **CMOR** — linear mix of table sine ↔ **phase-aligned naive saw** (hard ramp).
- **MMOR** — linear mix of table sine ↔ **DPW bandlimited saw** (continuous).
- Feedback (`S_LASTM` / `m_prev`) is always the **unmorphed modulator sine** so a saw edge never re-enters the fb loop.
- Mix is exact `/127` with a hard replace at amount **127** (no `/128` residual).

## Control path (solved earlier in the same pass)

| Symptom | Cause | Fix |
|---------|--------|-----|
| Edit crashes | `fm_e6_morph` jmp'd into `EDIT6_CLAMP` without the 8 B `SETUP_STEP` pad | `clr.l -(%sp)` ×2 before the jmp |
| Knob does nothing to audio | Morph not in the render path / wrong Part SETUP bytes | `sy_cxparm` + CURVALS SETUP A/B → stack morph long |
| Icons = stock LOOP/SLIC | Descriptor still had LOOP widgets | `po_setup_cx`: names CMOR/MMOR, plain dials, count 128, blank C–F |
| Only 0/1 | Stock SETUP_STEP / few-valued counts | Continuous path (`po_setup_edit` → `fm_e6_morph`), min 0 count 128 |

Stack in `sy_loop` (after fold push): morph long `00 00 CMOR MMOR` (BE).
MMOR = `7(sp)`; after parking mod phase, CMOR = `10(sp)`.

## Waveshape attempts (what failed on the unit)

| Build idea | On-unit result |
|------------|----------------|
| Crossfade sine ↔ **naive saw** (early) | Low amounts already “foldy”; discontinuity leaks through the mix |
| Equal-power mix with `amt>>1` | Only **64** audible steps (“steppy”) |
| Σ sin(nφ)/n harmonic saw | Soft; 127 ≠ saw; noisy |
| **DPW** without −½ offset | “Full saw” stayed unipolar / sine-ish |
| DPW half-scale + **antiphase** to `sy_tab` | **Fundamental notch ~CMOR 100** (“sine gone”), then fund returns toward 127 (“sine back”) — measured: fund energy proxy dips then rises |
| DPW 2× + polarity flip (CX 12) | Uniform morph, but 127 still read as sine (bandlimited, fund-heavy ~60% energy) |
| Naive aligned target for both (CX 13–14) | CMOR brighter at 127; **MMOR chaotic** |

## The MMOR ≠ CMOR rule

Same linear mix on paper is **not** the same in the instrument:

1. **CMOR** shapes the **carrier** sample → a hard saw edge is what you want at 127.
2. **MMOR** shapes the **FM modulator** (× INDX into carrier phase). A naive saw discontinuity there → carrier phase jumps → timbre **explodes** around **MMOR ~46–48**, then wanders up/down.
3. Writing a morphed saw into **`m_prev` / feedback** makes it worse (fb·saw). Feedback must stay sine.

**CX 14 bug (extra):** MMOR mixed sine(`φm+fb`) against saw from **raw `φm`** (and threw away the matching naive saw already in `a4`). CMOR used one phase for both.

**CX 15:** MMOR → DPW from **`φm_eff`**, fb = sine only; CMOR → aligned naive.

## Perception traps (still true on a correct 127)

- A mathematical saw’s strongest partial **is** a sine (~60% energy). “Sine completely gone” at 127 is not the same as “pure Fourier saw” — stripping the fund leaves a thinner buzz.
- **FOLD** defaults **0** (bypass). Fold is a **sine-table** waveshape on the carrier. Testing morph with FOLD up re-injects sine character — open FOLD a little, or set FOLD ≈ 1, when auditioning CMOR.
- **INDX** must be up to hear MMOR; CMOR is audible at INDX 0.

## Implementation map (CX 15)

| Symbol | Role |
|--------|------|
| `sy_epmix` | `d4=sine, d1=saw, d2=amt` → linear `/127`; 0 keeps sine; 127 = saw |
| `sy_dpw` | Välimäki DPW, 2× scale + invert; `d6=φ, d1=Δφ, a4=&z1` → `d2` Q14 (**MMOR only**) |
| `S_DPWM` (+44) | DPW `z1` for modulator |
| `S_LASTM` | Feedback sample = unmorphed mod sine |
| Carrier morph | Inline `16384 − (φc>>17)` then `sy_epmix` |

ColdFire gas notes burned here: `lsr.l #imm` only 1..8; `divs.l #imm` rejected — use a register.

## On-unit check

1. BRAIN → current CX tip. CX OSC track. **FOLD/RATE = 1**, **SYMM = 64**, **DEC = 127**.
2. **CMOR** 0→127, INDX 0: smooth brightening to a hard saw at 127; no hollow spot mid-high.
3. **MMOR** 0→127, INDX ~40, CMOR 0: smooth FM-colour change; **no jump at 46–48**.
4. One morph at a time when comparing.

## Proof status

Port / selftest do not replace hearing. Unit reports in this pass are Ilia’s ear on MKII with remix tags CX 6…15 — not `Proof.HARDWARE` in the manifest sense until he confirms a tip.