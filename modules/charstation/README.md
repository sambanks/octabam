# CHARACTER STATION

The second BamSep26 station: everything that dirties or tightens a track, in
one insert, **replacing stock LO-FI** (id 0x1c) on both menus and in every
saved part that chose LO-FI. Design page:
https://claude.ai/code/artifact/42670d67-7365-4c7d-bcc7-1786ba4331ce

| page 1 | DRV · FOLD · CRSH · COMP · →DEL · →VRB |
|---|---|
| page 2 | MIX · SAT (TAPE TUBE FUZZ BUS) · RING · CMOD (COMP GLUE TRNS) · WDTH · SRR (OFF /2 /4 /8) |

Chain, fixed: **crush → fold/ring → saturate → compress → width → mix**.
Distortion before dynamics, so the compressor is a tool on a dirty signal
rather than a fader for the dirt.

- **CRSH / SRR** are LO-FI's pair: a bit mask built once per block (0..21 bits
  cleared) and a sample-and-hold of 2, 4 or 8.
- **FOLD / RING** are WarpFold's wavefolder and its parabolic carrier.
- **SAT** is BongDelay's `w − w³/3` with four characters, and since the
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
- **→DEL / →VRB** make it a bus client on the filter station's terms:
  knob-gated registration, and it never housekeeps.

⚠️ **The detector reads `x:(r7+$32)`, the KEY**, which is the station's own
input today. The →KEY bus send on the backlog writes another track's there
and nothing else changes — that is the whole sidechain-ducking path.

## Measured (3 Sep 2026, local)

- **833 words** (payload A, 866 on B), **405 cycles/sample**. ⚠️ The pricer's
  worst case — seven of these on one core beside the reverb — is **331 over**
  the 3,120 + 768 FILTER credit. Sam's layout runs one or two. Trims if it
  must come down: drop RING (~12), a single `chsatur` call by rolling the two
  channels (~13), the TUBE asymmetry (~10 per channel).
- `tools/verify_charstation.py`, **22 gates, all PASS**: defaults bit-exact;
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

- Voicing: nothing has been heard yet. Every law here — the drive taper, the
  four characters' constants, the two compressor timings, the 12 ms transient
  window — is a first guess.
- ⚠️ UNFLASHED.
