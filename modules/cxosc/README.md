# `cxosc` — CX OSC

Buchla-style **complex oscillator** as a track machine: two-operator FM,
sine wavefolder, modulator feedback, sine→saw morphs. West Coast timbre
path — fold and index, not a filter. Local fork of Tim Hastie's FM SYNTH
ColdFire engine (not an edit of `modules/synth`). Provenance: `NOTICE`,
`LICENSE-TIM`, `THIRD_PARTY.md`.

Human manual (params + shots): [`docs/site/usage/cxosc.md`](../../docs/site/usage/cxosc.md).

## Select

Same sixth list row (**CX OSC**, under PICKUP). No marker file. Stored as
FLEX with Part signature `"CX", 1`. At most **four CX OSC tracks per Part**
(`ml_guard` / `ML_FM_MAX 4`).

- Double-tap the track key → machine list → **CX OSC** → YES
- **FUNC + SRC** → **SELECT MACHINE TYPE** → **CX OSC** → YES
- From **SRC SETUP**’s left machine list → **CX OSC** → YES

On a sample track, **FUNC + SRC** may open the sample list first — **LEFT**
reaches the machines.

## PLAYBACK — carrier, mod, fold

| Knob | Name | What it does |
|------|------|----------------|
| A | PTCH | Semitones (−32..+32); **FUNC** snaps −32 / 0 / +32 |
| B | RATO | Mod∶carrier ratio, free 0.25..4; **FUNC** snaps the classic table |
| C | INDX | FM depth (default **0**) |
| D | FINE | Cents (−64..+63; raw **64** = 0c) |
| E | FOLD | Wavefolder dry/wet after MIX (default **0** = bypass) |
| F | MIX | Folder **input** crossfade carrier↔**MMOR morph** (**0** = carrier, **127** = mod solo). Not the fold amount. |

Signal path: **mod → FM → carrier → MIX (fold input) → FOLD → out**.
See [`docs/site/usage/cxosc.md`](../../docs/site/usage/cxosc.md) for the diagrams.

## SETUP — morph, index env, feedback

**FUNC + PLAYBACK** (LCD header **SRC SETUP**).

| Knob | Name | What it does |
|------|------|----------------|
| A | CMOR | Carrier morph 0..127 (**0** sine → **64** saw → **127** square); **FUNC** snaps |
| B | MMOR | Modulator morph 0..127 (same; needs **INDX**); **FUNC** snaps |
| C | DEC | Index envelope; **127 = HOLD** |
| D | SYMM | Fold half-wave skew (**64** = even) |
| E | FDBK | Modulator feedback (default **0** = off) |
| F | WIDTH | Cycle lean (**64** = neutral): sine soft lean; saw phase-skew (8%..92% φ warp); square duty (**64** ≈ 50%) |

LFO PMTR **30 = CMOR**, **31 = MMOR**, **32 = SYMM**, **33 = FDBK**.
DEC/WIDTH are not LFO destinations. Mono only — AMP HOLD owns note length
(**HOLD INF** = until STOP); select seeds ATK 0 / HOLD INF / REL 0 / LEG MONO.

CMOR/MMOR targets and traps: [`MORPH.md`](MORPH.md).

## Icons (SETUP LCD) — do not invert

Stock blit `0x400128a8` column longs: **bit 31 = bottom row**, bit 19 = top
(mask `0xfff80000`, 13 rows). `pg_vline` row `0` is the bottom; higher row
indices climb the screen.

| Shift on a column long | Content moves |
|------------------------|---------------|
| `lsll #k` | **DOWN** (toward bit 31) |
| `lsrl #k` | **UP** |

FDBK nudge after Tim art + loop OR: **`lsll #1`**. DEC HOLD is a **single**
hollow line at row **h=10** (h=11 clips on SETUP; a filled box reads as a
white square). See `docs/contributing/TRAPS.md#trap-icon-bit31`.

## Saved Parts

Seeds (`fm_defaults`: FINE 0c, FOLD/MIX/INDX/FDBK 0, DEC HOLD, SYMM 64) are
written **only when CX OSC is chosen**. A project / Part reload / paste keeps
the bytes that were saved — no remap.

PLAYBACK D/E/F moved since the VRCS-CX VS layout (then FOLD / SYMM / DEC):

| Saved under VS (D/E/F) | Loads on this tip as |
|---|---|
| FOLD | **FINE** (raw; 64 = 0c) |
| SYMM | **FOLD** |
| DEC | **MIX** |

Example: VS defaults FOLD 40 / SYMM 64 / DEC 127 → FINE raw 40 (−24c), FOLD
64, MIX 127. Re-choose CX OSC on the track to re-seed, or edit the knobs.

Earlier still: slot F was once FDBK and SYMM’s even centre was 0 — a Part
saved with FDBK 0 / SYMM 0 under that layout loaded as DEC 0 / SYMM 0 when
DEC lived on PLAYBACK F (#1001 note).

## Conflicts

Cannot share an image with **SYNTH MACHINE** (same FLEX/STATIC renderers /
page cave / machine-list sites) or **BLACKPYRAMIDS_303** (shared ColdFire
ROM hooks, e.g. MIDI note-on). Not an FX2 id — machine signature `"CX", 1`.

## Cost

One mono voice under Unicorn: about **2035** instructions/frame (peak ~2074;
`verify_cxosc`). Up to **four** CX OSC tracks per Part by `ml_guard`.
ColdFire headroom on a loaded Part on the unit is still **open**
([#852](https://github.com/sambanks/octabam/issues/852)).

## Build

```bash
make check REMIX=cxosc
```
