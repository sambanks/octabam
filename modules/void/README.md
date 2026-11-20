# `void` — VOID

Replaces **COMB FILTER** (FX2 id `0x13`, `replaces="COMB FILTER"`). In any remix
that carries VOID, COMB is off the FX chooser; a Part saved with stock COMB
opens without that effect (re-pick VOID or stamp defaults). Code sits in
harvested **PLATE REV** words.

Grit: this track’s input blended with white noise (shape with COLR/HPF; WID
for stereo), amplitude-modulated by an audio-rate LFO or (SETUP **SRC=NBR**)
the previous track’s KEYBUS level. HPF/COLR/DRV/FDBK/AM hit the **noise**
only; dry is unfiltered. Always wet — no dry/wet MIX.

r7 `$40..$4f` stays reserved for a longer FEED delay later.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | BAL | 0–127 | dry↔noise (**0 = exact dry**, 127 = pure noise) |
| 1 | 1 | RATE | 0–127 | LFO rate; idle when SRC=NBR |
| 1 | 2 | COLR | 0–127 | noise low-pass ~30 Hz..16 kHz; 127 = open |
| 1 | 3 | HPF | 0–127 | noise high-pass before COLR; **0 = bypass** |
| 1 | 4 | DRV | 0–127 | soft-clip on **noise** only; 0 = bypass |
| 1 | 5 | FDBK | 0–127 | one-sample AC feedback on **noise** only |
| 2 | 6 | SHPE | SIN / SQR / SAW | LFO shape; idle when SRC=NBR |
| 2 | 7 | DPTH | 0–127 | AM depth on **noise** only (LFO or nbr uni) |
| 2 | 8 | WID | 0–127 | mono → stereo grit (2nd noise, same HPF/COLR/DRV) |
| 2 | 9 | SRC | LFO / NBR | AM source (NBR = previous track keybus) |

**SRC=NBR:** noise opens from the previous track’s KEYBUS level and stops
when that goes quiet (no LFO free-run). Default **SRC=LFO** keeps RATE/SHPE
on any track. On **track 1**, abs track and FX2 position are both 0, so NBR
reads `X:$37f60`, KEYBUS’s word for T1. Tracks 2–8 read the previous track.
Every remix containing VOID must include KEYBUS. If SIDECHAIN_COMPRESSOR is also
selected, the remix must include SC KEYBUS BRIDGE.
AM and DRV/FDBK hit **noise only**:
`wet = (1−BAL)·dry + BAL·noise''`. BAL=0 is always exact dry; BAL=127 =
AM’d noise. SETUP **WID**: 0 = mono; >0 = second white → same HPF/COLR/DRV
(no FDBK) → same AM; `L/R = mid ± (w/2)·side` (mono sum keeps mid/LFO).

Noise peaks around −6 dB at BAL=127. High FDBK + DRV screams (AC feedback —
a raw one-sample loop was railing to DC / silence past ~FDBK 50 with drive).

SETUP: SHPE · DPTH · WID / SRC · · .

## Storage and stock firmware

The page descriptor is cloned from **DARK REV** (`donor_desc=0x400d58b8`).
VOID keeps COMB's id (`0x13`) but not COMB's knob layout — page bytes from a
COMB Part will not match VOID's names.

If the same page bytes are loaded under DARK REV, they read as DARK's knobs:

| our slot | our name | stock DARK |
|---|---|---|
| 0 | BAL | TIME |
| 1 | RATE | SHVG |
| 2 | COLR | SHVF |
| 3 | HPF | HP |
| 4 | DRV | LP |
| 5 | FDBK | MIX |
| 6 | SHPE (0–2) | PRE |
| 7 | DPTH | BAL |
| 8 | WID | MONO |
| 9 | SRC (0–1) | (blank) |
| 10 | (blank) | (blank) |
| 11 | (blank) | MIXF |

Saving on stock with DARK selected writes DARK's names into those slots; the
bytes are the same width. Keep a separate project copy, or re-select effects
and save, before going back to stock.

## Measured

- **19 Nov 2026, the stall pass** (bit-identical: `verify_ident.py` with the
  wider matrix of sambanks/octabam#1172 (the module's own slot, payload B,
  16-sample blocks, a 2 s run, a knob ramp, stereo, the split call, the
  manifest's `dear` settings, and the r7 state after every block), IDENTICAL
  after each commit; 31 renders). Cycles a sample from
  `tools/build/interlock_scan.py` (the core manual's cycle table and stalls: a
  model, on average 3.0 % above the unit, `docs/contributing/CYCLE_SCAN.md`
  section 1), at `dear`: **503.9 → 493.8** (11.1 % → 10.9 % of a frame), every
  shape. Words 513 → 502 (`dsp_asm` at P:$800). Not measured on the unit. The
  frame advance (`#>$2,n0` / step / `#>$1,n0`) is one `lua (r0+$2),r0`, n0
  staying 1; a word stored to $25 and read back at once comes from its
  register; seven constants load as one-word short immediates.

- `verify_void.py`: passthrough; AM / FDBK vs `void_ref.py`; WID mono/stereo
  + 0→1 continuity + L/R anti-corr at full; COLR closed vs open; FDBK+DRV
  not DC-silent; max-knob true 3 s rail budget; two FX2 instances; SRC=LFO
  RATE moves / SRC=NBR RATE idle; quiet NBR ≈ silence; BAL0 ignores
  DRV/FDBK/DPTH/WID.
- Hardware **LATEST NP** / **VRCS VJ** (22 Oct 2026, Ilia's MKII): current
  layout — SRC LFO|NBR; COLR/HPF main; SHPE/DPTH SETUP; mid±(w/2) WID;
  DPTH default 127. See test-remix README.
- Earlier: **VOID V9** (COLR/HPF tables); **V215 N7** (Y-direct nbr, pre-SRC);
  **LATEST NN** (noise-only path, pre-SRC WID). Superseded by NP/VJ.
