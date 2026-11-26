# `cxosc` — CX OSC

Buchla-style **complex oscillator** as a track machine: two-operator FM,
sine wavefolder, modulator feedback, sine→saw morphs. West Coast timbre
path — fold and index, not a filter. Local fork of Tim Hastie's FM SYNTH
ColdFire engine (not an edit of `modules/synth`). Provenance: `NOTICE`,
`LICENSE-TIM`, `THIRD_PARTY.md`.

Human manual (params + shots): [`docs/site/usage/cxosc.md`](../../docs/site/usage/cxosc.md).

## Select

Same sixth list row (**CX OSC**, under PICKUP). No marker file. Stored as
FLEX with Part signature `"CX", 1`. No marker-file select; Part signature `"CX", 1`.

- Double-tap the track key → machine list → **CX OSC** → YES
- **FUNC + SRC** → **SELECT MACHINE TYPE** → **CX OSC** → YES
- From **SRC SETUP**’s left machine list → **CX OSC** → YES

On a sample track, **FUNC + SRC** may open the sample list first — **LEFT**
reaches the machines.

## PLAYBACK — carrier, mod, fold

| Knob | Name | What it does |
|------|------|----------------|
| A | PTCH | Semitones (−64..+63); **FUNC** snaps to …/−12/0/+12…; one unit a detent |
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
| A | CAR | Carrier morph 0..127 (**0** sine → **64** saw → **127** square); icon tracks the shape; **FUNC** snaps |
| B | MOD | Modulator morph 0..127 (same; needs **INDX**); icon tracks the shape; **FUNC** snaps |
| C | DEC | Index decay time constant: **0 = instant**; **1–32 = 1 ms/step**, then the steps widen to **5.061 s** at 126; **127 = HOLD** |
| D | SYMM | Fold half-wave skew (**64** = even) |
| E | FDBK | Modulator feedback (default **0** = off) |
| F | PWM | Cycle lean — LCD **−64..+63** (**0** = neutral; byte 64): sine soft lean; saw phase-skew (8%..92%); square duty (**0** ≈ 50%). Does **not** move the CAR/MOD icons. |

On every sequencer trig, DEC starts from full INDX for that frame, then begins
decaying, even while AMP HOLD keeps the oscillator sounding. Live legato notes
keep the running envelope. DEC reaches zero rather than leaving a residual tail.

LFO SETUP PMTR lists the PLAYBACK names (**PTCH RATO INDX FINE FOLD MIX**)
plus AMP / stock FX, then **30 = CAR**, **31 = MOD**, **32 = SYMM**,
**33 = FDBK**, **34 = PWM**. PTCH LFO depth matches FLEX (÷5). DEC is not an LFO destination. Mono only — AMP HOLD
owns note length (**HOLD INF** = until STOP); select seeds ATK 0 / HOLD INF /
REL 0 / LEG MONO. Beside OCTA303, HOOKS `machine_rows` bridges the LFO
PMTR name site (`0x4003bff0`): each machine names its own track.

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

One mono voice under Unicorn: mean **1881** instructions/frame (peak **1920**;
`verify_cxosc`, base knobs). The morphs, PWM and FOLD add to that:

| Setting (one voice, Unicorn instructions/frame) | before | now |
|---|---:|---:|
| MOD 0, PWM centre, FOLD 0 | 2376 | 1954 |
| MOD 32, PWM 30, FDBK 60 | 6151 | 3215 |
| MOD 32, CAR 40, PWM 30, FDBK 60, INDX 100, DEC 40, FOLD 60 | 8614 | 4502 |
| MOD 100, CAR 100, PWM 100, FDBK 90, INDX 127, DEC 20, FOLD 100, MIX 64 | 8688 | 4700 |

"Before" is the renderer as of #1263. The sample loop now computes the knob
constants (PWM lean and skew, pulse duty, morph weights, FOLD target) once
per call, runs the DPW saw, skew and lean inline with no per-sample divide,
and skips work the output does not hear. Its output is within 9 LSB (Q14) of
the old renderer. PWM is the largest extra cost after MOD morph: PWM at
centre takes about a fifth off the third row.

`verify_cxosc` also compares INDX 0 and 96 at CAR sine, saw, and square. The
rendered samples differ for all three shapes. This is emulator evidence, not
a hardware measurement. On `CXSEQ CV.RMX` (BUILD 79, 20 Nov 2026), Ilia
confirmed on a unit that INDX changes the saw and triangle carrier waveforms.
That report covers those two shapes only.

Selection guard **`ML_FM_MAX = 6`** (Part popup `CX OSC: 6 MAX`). The cap of six
was measured with **MOD morph at 0** on every CX OSC track (the tables below;
the longest ISR there already reaches past the frame). With the morphs, PWM,
FDBK, INDX, DEC and FOLD all engaged, use **four**. The guard counts tracks
and cannot see the knobs.

On CX B1 (this renderer) with MOD, CAR, PWM, FDBK, INDX, DEC and FOLD engaged
(LOAD METER over USB, 26 Nov 2026, Ilia's MKII):

| CX tracks sounding | CF share mean | CF share max | longest ISR |
|---|---:|---:|---:|
| 4 | 72.6% | 73.8% | 356.0 µs |
| 5 | 79.7% | 80.1% | 387.2 µs, past the 362.8 µs frame |

The previous renderer (CX A2) read 89.6% and 91.2% mean with four tracks on
the same setup, longest ISR 498.8 and 422.2 µs: over the frame.

Earlier MKII measurements used `cx-cf` + CF METER (USB decode, 9 Nov 2026,
`CX-CF 69`):

| CX tracks sounding | idle % | ISR mean | ISR max | notes |
|---|---:|---:|---:|---|
| 0 (baseline) | 44.7 | 125 µs | 212 µs | |
| 4 | 21.8 | 272 µs | 325 µs | comfortable |
| 6 | ~12 | 309 µs | 376 µs | max past the 363 µs frame |
| 7 | 0 | 355 µs | 446 µs | wall — MAIN clipped; do not ship as a cap |

On CX A2 with six tracks and MOD morph at 0 (LOAD METER over USB, 25 Nov
2026), CF share averaged **71.4%** and reached **73.6%**; the longest ISR was
**376.5 µs** against the 362.8 µs frame. This is the current six-track,
MOD-zero test. Eight tracks were not safe. [#852](https://github.com/sambanks/octabam/issues/852).

## Build

```bash
make check REMIX=cxosc
```
