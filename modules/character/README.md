# CHARACTER

The second BamSep26 station: everything that dirties or tightens a track, in
one insert, **replacing stock LO-FI** (id 0x1c) on both menus and in every
saved part that chose LO-FI. Design page:
https://claude.ai/code/artifact/42670d67-7365-4c7d-bcc7-1786ba4331ce

| page 1 | DRV · FOLD · CRSH · COMP · — · — |
|---|---|
| page 2 | MIX · SAT (TAPE TUBE FUZZ BUS) · RING · CMOD (COMP GLUE TRNS) · WDTH · SRR (OFF /2 /4 /8) |

Chain, fixed: **crush → fold/ring → saturate → compress → width → mix**.
Distortion before dynamics, so the compressor is a tool on a dirty signal
rather than a fader for the dirt.

- **CRSH / SRR** are LO-FI's pair: a bit mask built once per block (0..21 bits
  cleared) and a sample-and-hold of 2, 4 or 8.
- **FOLD / RING** are WarpFold's wavefolder and its parabolic carrier.
- **SAT** is BusDelay's `w − w³/3` with four characters, and since the
  branchless pass they are **four per-block coefficients** — `neg` (TUBE's
  asymmetry: the negative half scaled 0.75 before the curve), `pre`/`post`
  (BUS drives at half and doubles back — the gentlest knee, for a master) and
  a symmetric `clip` (FUZZ at ±0.6; 1.0 elsewhere never bites, since
  |sat(w)| ≤ 2/3).
- **COMP / CMOD** is one feedforward detector on the mono key with a gain
  applied to both channels, so it cannot pump the image. COMP is fast 4:1,
  GLUE slow and soft-kneed (the master setting), TRNS a transient shaper —
  and the gain is **one branchless expression**, because TRNS sets the
  compressor's threshold to 1.0 and the other modes set the boost flag to 0.
- **WDTH** is mid/side: 64 untouched, 0 mono, 127 double sides. With BUS +
  GLUE + WDTH this is the master chain on T8's FX1.
- **SAT = BUS is also the RETURN** (3 Sep 2026, one return since the one-aux
  rig of 7 Sep: `docs/effects/BUS.md` "The one aux bus"). On a master chain
  CRSH is a knob nobody turns, so BUS repurposes it as **RET**, the return
  level (RING is inert in BUS mode) — the panel and the remixer print that
  name (`mode_views`), the crush and ring stages go neutral, and the
  station adds the LAST LIVE STAGE's output (the reverb's if it runs, else
  the delay's; stereo, four deep, two buffers back) at that level. While
  RET is up it stamps both hosts quiet, so the wet arrives once, here, on
  T8 — the return is pinned to track 8 and returns nothing elsewhere.
- **833 words** (payload A, 866 on B), **405 cycles/sample**. ⚠️ The pricer's
  worst case since the station went FX1-only (12 Sep 2026) is FOUR of these
  beside the delay: 3,567 on the counter (`make cycles`), 447 over the flat
  3,120 and 321 under the FILTER-credited 3,888 — which line is real is the
  burn sweep's to say (`tools/harness/pressure.py`). Sam's layout runs one
  or two. Trims if it must come down: drop RING (~12), a single `chsatur`
  call by rolling the two channels (~13), the TUBE asymmetry (~10 per
  channel).
## Measured laws (12 Sep 2026, `tools/harness/station_laws.py --probe sine|burst`)

At the unit's level: a −6 dBFS source enters the chain at 0.127 FS (AMP VOL
64, the mixer model). Every stage below was first measured against that
level; three were sized for the old harness's 0.5 FS and were inert or a
fader there, and are re-ranged.

| stage | law now | readout (−6 dBFS sine unless said) |
|---|---|---|
| DRV | 1 → 16× into the curve (was 1 → 4×), post × 1/√(1+15·DRV/128) from the module's P table (`DspSection.ptable`, 17 words) | TAPE THD 1 / 3 / 8 / 13 / 17 % at 16/32/64/96/127, gain +4..+7 dB across the dial |
| the curve | **tanh(driven)** from a 33-pair P table (value, slope; interpolated per sample, `(r1)+n1`) — never flat. Was `w − w³/3` with a hard clip at |w| = 1: at DRV 96+ the top of a drum loop sat on that flat and read as "digital, clippy" (ear, 12 Sep 2026; the cubic's THD was 14 / 25 / 31 % at 64/96/127) | H2 −119 dB (odd symmetry exact) |
| post low-pass | one pole after the curve, `kl = 0.6·DRV/128` in **TAPE / TUBE** only (0 = bit-exact elsewhere): tape darkens as it drives | corner 16.7 k / 8.4 k / 5.4 k / 3.3 kHz at DRV 32/64/96/127 |
| SAT | TAPE the curve + the low-pass (dark, odd); TUBE neg 0.5 — the negative half driven at half — with the DC blocker and **no** low-pass (bright, even = odd at DRV 80, −22 dB each; at neg 0.75 TUBE was TAPE by ear); FUZZ hard clip ±0.6 **on the curve's output, before post**, with the low-pass at half strength (the clip's fizz off the top — heard better; the aliasing under it needs oversampling, unaffordable at payload A FREE 30); BUS pre 0.5 / post 2 — the return mode, not a colour | |
| DC blocker | `y = x − k·x1 + R·y1`, R 0.999 (~7 Hz), **on in TUBE and FUZZ only** (k = R = 0 elsewhere: bit-exact) | TUBE's DC leak −30 dBFS → −68 |
| FOLD | 1 → 32× into the fold (was 1 → 8×) | 4 % at 16, 16 % at 32, full folding (THD > 100 %) from 64 |
| COMP / GLUE | block-max detector; per block `gr = (thr + over·invR)/env` by a real division; COMP scales the reduction and adds makeup 1 + 0.5·COMP; attack/release slew the GAIN per sample | COMP (thr 0.05, invR 0.125, 1 ms/100 ms) at 127: quiet +3.5 dB, loud −3 dB, release 85 ms. GLUE (0.03, 0.35, 10 ms/400 ms): +2.6 / −2.4 dB. The first compressor measured **inert** (thr 0.2/0.1 FS, a gain law linear in amplitude, a release coefficient of 0.004 that reset the envelope every sample, an attack never read) |
| TRNS | `gr/2 += 4·(blockmax − slow)⁺·COMP`, capped at gr 2.0, 0.5 ms / 30 ms, no makeup | onset +6 dB max |
| CRSH / SRR / WDTH | unchanged; the gates cover them | |

Cost 436 → 414 cycles/sample (the dead send taps and registration went with
the sends; the new compressor is cheaper in the loop than the old one).

Kits for the ear in `out/ab/char_*` (`tools/harness/abkit.py`): TAPE
drive, the four characters at DRV 80, FOLD, COMP, GLUE, TRNS, CRSH+SRR, RING.

- `tools/verify/verify_character.py`, **22 gates, all PASS**: defaults bit-exact;
  MIX=0 bit-exact with every stage driven; CRSH=110 collapses a ramp to 144
  wet levels against 4,500; SRR holds the wet exactly 2/4/8 samples; all four
  SAT characters unity small-signal at DRV=0 and bounded at DRV=127; FOLD
  folds a monotonic ramp; RING at DC has ~zero mean; COMP reduces the loud
  signal 6.1 dB more than the quiet one and is exactly unity at 0; TRNS
  boosts an onset 8% above the steady state; WDTH 0 is mono and 64 is exact.
- Menu: `verify_menu`, `verify_replaces` (it took LO-FI's FX1 page and the
  composed chooser lists the clone) and `verify_labels` (all three selects
  print their words on the emulated firmware) pass on `stations`.

## What the gates cost to get right (all four were real bugs)

- **A patch batch that aborted before writing** left five arithmetic fixes
  unapplied while a sixth had landed, so the compressor stored a full-scale
  gain that the multiply site doubled: **every knob read +6 dB**. Found by
  measuring a DC input through an identity chain — ratio 1.951 — not by
  reading.
- **The transient shaper took `max` with the fast follower**, so the slow one
  could never lag and the difference was identically zero. The knob did
  nothing, and the gate that would have caught it was comparing two bypass
  renders.
- **Two gates were measuring the wrong thing**: the crush cannot be read off
  the output word (the cubic refills the low bits, and the mix carries 1/128
  of the un-quantised dry), and SRR holds the *wet*, not the output.
- **`ch_sat` is a prefix of `ch_satr`**, so every branch resolved to garbage —
  `dsp_asm` matches labels by prefix (CLAUDE.md). Labels here are `chsatur`,
  `chsatr1`, `chsatr2`, none a prefix of another.

## Open

- Voicing (ear pass, 12 Sep 2026, kits in `out/ab/char_*`): TAPE drive —
  scaling even, but the cubic's top was "digital, clippy" → the tanh curve
  and the drive-keyed low-pass (heard: better). The four characters at DRV
  80: TAPE / TUBE / BUS were alike → TUBE bright and harder-asymmetric,
  "more distinct and useful"; FUZZ "awesome" with fizz on top → half
  low-pass, "a bit better". Still to hear: FOLD, COMP, GLUE, TRNS,
  CRSH+SRR, RING.
- On hardware since flash 4 (tag 79); the return (SAT=BUS on T8) confirmed
  on flash 7 (tag 21). **FX1 only** since 12 Sep 2026: an FX2 instance runs
  as a dry pass (`Claims(fx1_only=True)`, `verify_character.py`), the FX2
  chooser hides the row; emulator-proven, not yet flashed. The sends went
  with the one-aux rig: page-1 slots 4-5 are blank, and BUS mode carries ONE
  return, RET (the CRSH knob).
