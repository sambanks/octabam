# `cxosc` — CX OSC

Buchla-style **complex oscillator** as a track machine: two-operator FM,
sine wavefolder, modulator feedback, and sine→saw morphs. Local fork of
Tim Hastie's FM SYNTH ColdFire engine. Provenance: `NOTICE`,
`LICENSE-TIM`, `THIRD_PARTY.md`.

Human manual (params + shots): [`docs/site/usage/cxosc.md`](../../docs/site/usage/cxosc.md).

## Select

Sixth machine-list row (**CX OSC**, under PICKUP). CX OSC uses a FLEX
track with the Part signature "CX", 1.

- Double-tap **[TRACK]** → machine list → **CX OSC** → **[YES]**
- **[FUNC] + [SRC]** → **SELECT MACHINE TYPE** → **CX OSC** → **[YES]**
- From **SRC SETUP**’s left machine list → **CX OSC** → **[YES]**

On a sample track, **[FUNC] + [SRC]** may open the sample list first. **[LEFT]**
reaches the machines.

## PLAYBACK — carrier, mod, fold

| Knob | Name | What it does |
|------|------|----------------|
| A | PTCH | Semitones (−64..+63); **[FUNC]** snaps to …/−12/0/+12…; one unit a detent |
| B | RATO | Mod∶carrier ratio, free 0.25..4; **[FUNC]** snaps the classic table |
| C | INDX | FM depth (default **0**) |
| D | FINE | Cents (−64..+63; raw **64** = 0c) |
| E | FOLD | Wavefolder dry/wet after MIX (default **0** = bypass) |
| F | MIX | Folder **input** crossfade carrier↔**MMOR morph** (**0** = carrier, **127** = mod solo). Not the fold amount. |

Signal path: **mod → FM → carrier → MIX (fold input) → FOLD → out**.
See [`docs/site/usage/cxosc.md`](../../docs/site/usage/cxosc.md) for the diagrams.

## SETUP — morph, index env, feedback

**[FUNC] + [PLAYBACK]** (LCD header **SRC SETUP**).

| Knob | Name | What it does |
|------|------|----------------|
| A | CAR | Carrier morph 0..127 (**0** sine → **64** saw → **127** square); icon tracks the shape; **[FUNC]** snaps |
| B | MOD | Modulator morph 0..127 (same; needs **INDX**); icon tracks the shape; **[FUNC]** snaps |
| C | DEC | Index envelope; **127 = HOLD** |
| D | SYMM | Fold half-wave skew (**64** = even) |
| E | FDBK | Modulator feedback (default **0** = off) |
| F | PWM | Cycle lean — LCD **−64..+63** (**0** = neutral; byte 64): sine soft lean; saw phase-skew (8%..92%); square duty (**0** ≈ 50%). Does **not** move the CAR/MOD icons. |

LFO SETUP PMTR lists the PLAYBACK names (**PTCH RATO INDX FINE FOLD MIX**) plus AMP and stock FX, then **CAR MOD SYMM FDBK PWM**. DEC stays on its knob. PTCH LFO depth matches FLEX.

**VOICES** is a build setting. **MONO** is the default and keeps last-note mono. **POLY** enables Tim **VOIC 1..4**, **CHRD**, and the **LEG** choices **OFF / MONO / POLY**. VOIC and CHRD use the LFO 3 rate and depth slots, so those two LFO 3 controls are unavailable on CX OSC in the poly build. AMP **HOLD** owns note length. CX selection seeds ATK 0 / HOLD INF / REL 0 / LEG MONO.

In **POLY**, LFO 3 is muted. LFO SETUP **PMTR** adds **VOIC** and **CHRD** after the CX OSC destinations. LFO 1 or 2 can modulate them; each new note uses the current values.

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

## Cost / how many CX tracks

One mono voice under Unicorn: about **2035** instructions/frame (peak ~2074;
`verify_cxosc`).

In **MONO**, the selection guard is **`ML_FM_MAX = 6`** (Part popup
`CX OSC: 6 MAX`). Measured on the author's MKII with remix `cx-cf` + CF METER
(USB decode, 9 Nov 2026, tip `CX-CF 69`):

| CX tracks sounding | idle % | ISR mean | ISR max | notes |
|---|---:|---:|---:|---|
| 0 (baseline) | 44.7 | 125 µs | 212 µs | |
| 4 | 21.8 | 272 µs | 325 µs | comfortable |
| 6 | ~12 | 309 µs | 376 µs | cap; max past the 363 µs frame |
| 7 | 0 | 355 µs | 446 µs | wall — MAIN clipped; do not ship as a cap |

The seven-track MONO run clipped MAIN, so the guard rejects a seventh. In
**POLY**, the selector cap is **four** (`CX OSC: 4 MAX`). On 16 Nov 2026, the
author ran five POLY tracks with CF METER on `CPMTR84`. Three 20-second USB
captures decoded 23 cycles. Idle was 9.36–10.39%, ISR mean was 309.1–313.9 µs,
and the longest ISR reading in each cycle was 415.2–463.8 µs against a
362.8–362.9 µs frame. DSP TUE and ROE stayed at zero, with 5,520 frames in
each two-second window. The author reported a freeze during the five-track
test.

At four POLY tracks, a 20-second USB capture decoded nine cycles. Idle was
16.39–16.69%, ISR mean was 294.3–294.8 µs, and the longest ISR reading was
314.4–337.7 µs against a 362.8–362.9 µs frame. DSP TUE and ROE stayed at zero,
with 5,520 frames in every window. On 16 Nov 2026, the author confirmed the
four-track setup was stable and still running after the capture. The POLY
selector cap is four. The MONO cap remains six. The run's exact RMX tag was
not confirmed. [#852](https://github.com/sambanks/octabam/issues/852).

## Build

```bash
make check REMIX=cxosc
```
