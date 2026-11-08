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
| F | MIX | Folder **input** crossfade carrier↔mod (**0** = carrier only). Not the fold amount. |

Signal path: **mod → FM → carrier → MIX (fold input) → FOLD → out**.
See [`docs/site/usage/cxosc.md`](../../docs/site/usage/cxosc.md) for the diagrams.

## SETUP — morph, index env, feedback

**FUNC + PLAYBACK** (LCD header **SRC SETUP**). Slot F blank.

| Knob | Name | What it does |
|------|------|----------------|
| A | CMOR | Carrier morph 0..127 (sine → saw) |
| B | MMOR | Modulator morph 0..127 (sine → saw) |
| C | DEC | Index envelope; **127 = HOLD** |
| D | SYMM | Fold half-wave skew (**64** = even) |
| E | FDBK | Modulator feedback (default **0** = off) |

LFO PMTR **30 = CMOR**, **31 = MMOR**, **32 = SYMM**, **33 = FDBK**.
DEC is not an LFO destination. Mono only — AMP HOLD owns note length
(**HOLD INF** = until STOP); select seeds ATK 0 / HOLD INF / REL 0 / LEG MONO.

CMOR/MMOR saw targets and traps: [`MORPH.md`](MORPH.md).

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

## Build

```bash
make check REMIX=cxosc
```
