# `stuttr` — STUTTR

A per-track **chance grain repeater**. Input always writes into the stock FX
instance ring. On each RATE tick, CHNC may grab the last SIZE grain and
HOLD-loop it; miss stays dry. While holding, MODE sets playback rate and
REV rolls reverse per grain wrap. MIX 0 is bit-exact dry.

Re-select the effect after a flash if an old Part still has stale page
bytes (e.g. leftover JITR/FDBK/DECY from the prior topology).

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | SIZE | 0–127 | grain length; **(kn+1)²** words (≈ 0.1–180 ms on FX2) |
| 1 | 1 | RATE | 0–127 | how often CHNC may attempt a grab (slow→fast) |
| 1 | 2 | CHNC | 0–127 | 0 = never; 127 = always grab on tick; miss = stay dry |
| 1 | 3 | HOLD | 0–127 | after a hit: how long to keep repeating before dry |
| 1 | 4 | REV | 0–127 | per-**repeat** reverse probability (0 = always forward) |
| 1 | 5 | MIX | 0–127 | dry/wet of the stutter vs live |
| 2 | 6 | MODE | FWD / HALF / QUART / RND | 1× / ½× / ¼× / per-repeat random rate |
| 2 | 7 | SYNC | FREE / 16 / 8 / 4 | divisions of the RATE attempt clock |

## Behaviour

```
dry ──RATE tick──► CHNC roll ──miss──► dry
                      │
                     hit
                      ▼
              grab SIZE grain
                      ▼
         HOLD-loop (MODE rate, REV rolls)
                      ▼
                     dry
```

- **SIZE** words = `(kn+1)²` (min 8, even, clamp to maxlen). Same quadratic
  map as before so mid dial is useful.
- **HOLD** duration = `(kn+1)² × 16` samples (at least one full grain). Wet
  stays full until HOLD expires, then a ~64-sample (~1.5 ms) linear fade
  back to dry. Engage uses the same length fade-in.
- **HALF / QUART** hold each stereo frame for 2 / 4 samples (pitched-down feel).
- **RND** picks FWD / HALF / QUART on each grab and each grain wrap.
- Grab start is always the last SIZE behind the write head (no JITR).

## Ring length (SIDECHAIN window)

`Claims.buffer_words = 15862` — same ceiling as VERBERATION (GATE VERB until 6 Nov 2026) / WAVE / BBD
(`+$3DFD`, #785). The last `$202` words of the T3/T7 FX2 slots are
SIDECHAIN_COMPRESSOR's cross-core keybus; a 16,384-word ring would write
into them. Init sets maxlen to 15,862 on FX2 (3,072 on FX1).

## Cost / instances per core

Measured `make check REMIX=stuttr`: **426 cycles/sample**. Four FX2 slots
share a core → worst-core **1704** against ~3120 usable after stock
(~1415). So **4 instances per core** fit the FX2 slot map and the cycle
budget; a fifth is not offered by the panel.

## Storage and stock firmware

The page descriptor is cloned from **DARK REV**; the FX id is **MULTIBCOMP**
(`0x19`, `replaces=` — stock null stub, not a free-pool id). A Part saved
with STUTTR keeps that id and the eight page bytes. Stock 1.40C runs
MULTIBCOMP (null stub) on that id. If the same page bytes are loaded under
DARK REV, they read as DARK's knobs:

| our slot | our name | stock DARK |
|---|---|---|
| 0–5 | SIZE…MIX | TIME, SHVG, SHVF, HP, LP, MIX |
| 6 | MODE (0–3) | PRE |
| 7 | SYNC (0–3) | BAL |

Keep a separate project copy, or re-select effects and save, before going
back to stock.

## Measured

Local render gates (`verify_stuttr`): MIX 0 bit-exact; CHNC 0 stays dry;
CHNC 127 + HOLD engages; SIZE loop gaps; HALF lengthens gaps vs FWD;
REV 127 reverses; every named knob renders; max-knob (all 127, each MODE,
~3 s / 0.5 FS) hits **0 rail samples**; two FX2 instances each have energy;
CHNC 8 sits between dry and always-on; REV 64 is neither always-fwd nor
always-rev (LFSR); grab onsets spread at CHNC 127; MODE RND varies gaps.

## Defaults

SIZE / RATE / HOLD mid (64); CHNC 0 (dry until raised); REV 0; MIX 127;
MODE FWD; SYNC **8**.

## On the unit

Ilia's MKII, **STUT NS.RMX** (latest−SHATTER via BRAIN; 21 Oct 2026): empty
project sequencer advances; every page-1/page-2 knob, MODE/SYNC, trig
splits, two instances per core, engage/release fades heard click-free.
(Prior G4 was the old always-loop topology.)

## Conflicts

**SHATTER** — `Module.conflicts`. Empty-project play stalls when both are
in one image. Proven on Ilia's MKII:

- **STUTTR S8** (`latest` + both) — stall, 21 Oct 2026
- **STUT SH** (pair + stock only; no STEM/SC/CORE extras) — stall, 22 Oct 2026

Bisect: NS / NH / NB / C8 each run. So the pair alone is enough; not a
`latest`-only interaction. Cause open (not SHATTER buffer overlap — r7
scratch only). Build refuses the combo until fixed.

## Open

- Project-BPM tempo sync
- Root cause of the SHATTER+STUTTR empty-play stall


## Gates

`tools/verify/verify_stuttr.py` (manifest `Gate`).
