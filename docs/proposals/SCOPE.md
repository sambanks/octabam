# SCOPE — live waveform popup (proposal)

Guitar-tuner–shaped ColdFire window that plots the current track’s
post-FX pre-fader audio. Target feel: the **LOADING / boot banner**
smoothness, not TUNER’s ~7 Hz needle update.

Status: shipped as `modules/scope` (OSC + XY + ALL 4×2). Spec/bars ideas
below are parked. Port-proven (`Proof.CHECK`); local unit tips are not a
merge-gate hardware claim.

## Why the loading banner feels fast

Measured (PANEL.md section 8, Tim Hastie):

| Clock | Rate | Role |
|---|---|---|
| DTIM1 | **120 Hz** | LED/key scan |
| UI queue post | **60 Hz** | every second DTIM1 tick → UI task |
| TUNER `UPDATE_FRAMES` | **~7 Hz** | 400 audio blocks ≈ 145 ms — throttled because McLeod is ~1M instr |

The banner / boot logo rides the **60 Hz UI path** (and boot’s tight
redraw+UART drain). TUNER hooks the same UI loop head (`0x40056c72`) but
only redraws when a heavy `tu_analyse` is due.

**SCOPE can redraw every UI tick (or every 2nd = 30 Hz)** because plotting
is cheap: no pitch detector. Same hooks as TUNER; drop the analysis budget.

Audio still fills a ring in `frame_isr` (~2756 blocks/s, 16 samples each).
UI samples that ring at 30–60 Hz — plenty for a 128×64 1-bit panel.

## Shared skeleton (all options)

Steal TUNER’s three-detour shape:

| Hook | Site | SCOPE |
|---|---|---|
| Chord open | `0x40059ef0` (TEMPO opener) | **DOWN+TEMPO** (leave UP+TEMPO = TUNER) |
| Ring fill | `0x4000d99a` | same arena `0x80003190`, track @ `0x80000000` |
| UI tick | `0x40056c72` | redraw every 1–2 UI posts when open; closed = 2 instr |

Window: **full LCD, not a TEMPO popup.** SETUP-shaped
`WCREATE(128, 64, 0, 0, class=1, closed)` (stock SETUP uses 115×64 class 1;
we take the full 128×64 surface). Class 1 = menu/SETUP family (evicts with
menus), **not** TEMPO class 5 — no 96×56 chrome, plot uses the whole panel.
Primitives already used by TUNER / SETUP drawers (`PANEL.md` section 3):

- `CLEAR` `0x40035624`, `TEXT` `0x40012bd8`, `RULE` `0x40011910`
- `VLINE` `0x40011b94`, `BOX` `0x40012254`
- pixel line `0x40012004`, dotted hline `0x40011a58`

Ring: 2048–4096 × int16 mono (same as TUNER). DRAM only; no DSP.

Gate redraw with `SCRDIRTY` like TUNER’s close path.

---

## Visualisation options

Plot area ≈ **128×56 px** (full width; thin header strip for `SCOPE` +
track #), or **128×64** with track # overlaid in a corner. All options
assume auto-gain from peak in the visible window (hold 200–500 ms) so
quiet tracks still fill the height.

### A — Column min/max envelope (recommended v1)

For each screen column `x`, scan the samples that map into that column,
draw one `VLINE` from min→max (classic “digital scope” / DAW overview).

| | |
|---|---|
| Feel | Dense, continuous, works on drums and noise |
| FPS | **60 easy** — 128 VLINEs + CLEAR + thin header |
| Pros | No trigger needed; always something to see |
| Cons | Loses single-cycle shape on pure tones |

**v1 pick.** Closest to “banner smooth” with least risk.

### B — Polyline waveform (triggered)

Find a rising zero-crossing near the ring write cursor (or absolute max),
then walk N samples drawing `0x40012004` or successive `VLINE` stubs
between consecutive `(x,y)` points.

| | |
|---|---|
| Feel | Classic oscilloscope of a stable tone |
| FPS | **30–60** if N ≤ ~200 segments |
| Pros | Shows waveshape / duty / clipping |
| Cons | Drums / inharmonics jitter; needs trigger hysteresis |

Encoder: TIME (samples/div), maybe LEVEL. Optional hold-off.

### C — Peak-hold bars (spectrum-ish, no FFT)

8–16 vertical bars: RMS or peak in log-spaced bands via cheap boxcar /
half-band cascades (no full FFT). Animate like a meter bridge.

| | |
|---|---|
| Feel | Club meter / loading-bar cousin |
| FPS | **60** |
| Pros | Very cheap; readable on drums |
| Cons | Not a true spectrum; not a scope |

Good as a **mode** next to A, not the only view.

### D — Scrolling waterfall strip

Each UI frame: shift the plot area left 1–2 px (`BOX` clear + redraw),
append a new min/max column on the right (history of ~1–2 s).

| | |
|---|---|
| Feel | Strip-chart / tape scrub |
| FPS | **30–60** if we only draw the new column + scroll blit |
| Pros | Shows transient timing vs the beat |
| Cons | Harder blit on 1-bit surface (may redraw full area each frame — still OK at 30 Hz) |

### E — Lissajous (L vs R)

Map L→X, R→Y from stereo arena (skip mono sum). Plot dots/`BOX` 1×1 for
a block of samples.

| | |
|---|---|
| Feel | Phase / width toy |
| FPS | **30+** with decimation |
| Pros | Unique on OT; stereo cue |
| Cons | Needs stereo; small plot area; niche |

### F — Hybrid with TUNER

Same window: top = note/cents (run analyse every ~7 Hz), bottom = mode A
envelope at 60 Hz. One chord, two jobs.

| | |
|---|---|
| Pros | No second module / chord war |
| Cons | Shares UP+TEMPO; heavier; couples two features |

Prefer **separate SCOPE + DOWN+TEMPO** so TUNER stays Tim’s.

---

## Refresh budget (back of envelope)

266 MHz V4e, UI at 60 Hz → **~4.4M instr/frame** available before audio
feels it (much less is polite).

| Work | Rough cost |
|---|---|
| CLEAR 96×56 | small |
| 88 × VLINE (mode A) | ~few k instr |
| 200 × pixel line (mode B) | still ≪ TUNER’s 1M analyse |
| TUNER analyse | ~1.0M — why it sits at 7 Hz |

So **30–60 FPS is the right target** for A/C/D; B at 30 FPS with a short
trace. Match the banner by redrawing on the UI tick, not on
`UPDATE_FRAMES=400`.

Throttle only if `cfstatus` / PROCESSOR LOAD shows pain while open:
drop to 30 Hz (every 2nd UI post) before reducing columns.

## Interaction sketch

| Key | Action |
|---|---|
| DOWN + TEMPO | toggle SCOPE (UP + TEMPO stays TUNER) |
| TEMPO / YES / NO | close |
| Encoder A | TIME / zoom (samples per width) |
| Encoder B | MODE: envelope / waveform / bars (A/B/C) |
| Encoder C | GAIN freeze / auto |
| Track keys | follow current audio track (as TUNER) |

## Conflicts / placement

- Detour sites overlap TUNER’s — **different chord**, same sites only if
  one module owns both (F). Two modules both detouring `0x40059ef0` /
  `0x4000d99a` / `0x40056c72` **conflict** — SCOPE must either share one
  unit with TUNER or chain carefully (one owner stubs both).
- Practical plan: **one DRAM module `scope`** that optionally cohabits
  with TUNER by replacing TUNER’s chord stub with a 2-way (UP→tuner,
  DOWN→scope) *or* ship SCOPE alone on a tip remix that already has TUNER
  and merge the openers into one linked unit later.
- Class 5 window: opens → stock TEMPO / TUNER evict each other as today.

## Suggested spike order

1. **Mode A @ 60 Hz** on DOWN+TEMPO, ring+draw only, no encoders — prove
   FPS on hardware next to the loading banner feel.
2. Add TIME zoom + auto-gain.
3. Mode B trigger as second page/mode.
4. Mode C bars if wanted.
5. Decide TUNER coexistence (shared opener vs tip without double-detour).

## Out of scope (v1)

- DSP-side plot (ColdFire arena is enough and matches TUNER).
- True FFT / spectrogram (CPU + DRAM; revisit after A feels good).
- Writing pixels into the panel UART path directly (use stock surface +
  SCRDIRTY like TUNER).
