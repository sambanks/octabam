# `vibrato` — VIBRATO

A pitch vibrato on FX1: sine, triangle, a square trill or stepped random
pitch, with the depth set in cents.

One modulated delay per channel, wet only, MIX blending it with the dry. DEP
is a pitch depth: it holds as SPD moves, because the delay swing is scaled by
1/rate (and capped by the 1,024-word lines, so very slow and very deep runs
out of line first). Each shape is a pitch trajectory and the delay is its
integral: SQR is a true two-note trill (a triangle in delay), TRI a triangle
in pitch, RND a new random pitch every half cycle, the square's step rate.
SLEW rounds whatever shape is selected; WID leads R by up to half a cycle,
and on RND decorrelates R's random stream instead. FX1 only (an FX2
instance is a dry pass).

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | SPD | 0–127, default 80 | rate, 0.25 × 2^(3k/64) Hz: 0.25 Hz at 0, 2 Hz at 64, 3.4 Hz at 80, 5.3 Hz at 94, 15.5 Hz at 127 (21.3 steps an octave) |
| 1 | 1 | DEP | 0–127, default 48 | peak deviation c = 100 (k/127)² cents: 6.3 at 32, 14.3 at 48, 25 at 64, 30 at 70, 100 at 127. The two extremes are exactly 2c apart (a whole-tone trill at 127) |
| 1 | 2 | SLEW | 0–127, default 0 | a one-pole on the delay offset, time constant (k/128)/4 of a cycle: 0 is none, 127 a quarter cycle. Rounds SQR's corners into a glide; also lowers the peak |
| 1 | 3 | WID | 0–127, default 0 | R's LFO lead, (k/128)/2 of a cycle (64 quadrature, 127 antiphase). On RND: R's random pitch is n1 + (k/128)(n2 − n1), so 0 is mono and 127 independent |
| 1 | 5 | MIX | 0–127, default 127 | dry/wet, k/128; 127 = 1.0, the vibrato alone; 0 is an exact passthrough. Glides (1/8 of the way a block, ~3 ms) |
| 2 | 6 | SHP | SINE / TRI / SQR / RND | the pitch shape. A change ducks the wet to dry (16 blocks), switches, and fades back |

SPD, DEP and SLEW read their tables with the knob word's LFO fraction (bits
15–8), so an LFO on them moves smoothly between steps, and an LFO Designer
"fine" offset reaches between them.

## Design

Prototyped in Faust (`vibrato.dsp` beside this file: the listening model,
continuous-time, not the proof). The DSP and `vibrato_ref.py` are
block-based:

- **Per block** (16 samples on the unit, 15 in the gates): decode the knobs,
  advance the LFO phase by n7 inc, evaluate each channel's delay there (a
  knot), and walk the delay to it in a straight line, a 16th of the way a
  sample (modulation's `mo_knot`; the tap is its `mo_tap`, the fraction
  blended toward the older neighbour). A square's corner inside a block is
  cut to the chord.
- **Shapes** as closed-form integrals, normalised to ±1 and scaled by the
  swing H: SINE reads the stock sine at X:0x6c00 (1,024 points, interpolated);
  TRI is ±4u(1−u), u = 2φ mod 1; SQR is 1 − 4|v − ½|, v = φ + ¼. H = dev ·
  per · FAC (1/2π, 1/8, 1/4, 1/4), dev = tanh(c ln2 / 1200), capped at 500
  samples. H follows the knobs at once.
- **The walk's limit**: the delay may move at most 1.5 dev a sample (at
  least 0.006, 10.4 cents). A knob jump (a p-lock, a scene, a fast twist)
  moves H and the centre 2 + H by tens of samples in a block; before the
  limit the walk to the new knot was a pitch spike, 61 % for a moment at an
  SPD 80 -> 120 step, heard on the unit as an occasional pop. No shape's own
  slope exceeds dev, so in steady state the limit never engages (the output
  with no knob moves is identical to before it).
- **RND**: on each block that crosses a half cycle, u = (x + n)/2 with n from
  a 24-bit Galois LFSR (mask 0xE10000, maximal; 16 steps a draw, bit 0 tested
  with `and`/`tne`), then x −= 4u·Δφ each block, so x ends each half cycle
  near −n and stays in ±1 without a leak. The seed is the payload's own odd
  word eor the instance's r7 << 8, so no two RND instances (on either core)
  step in lockstep.
- **The SHP duck** snaps the delay to the new shape's knot on the block it
  switches (unprimed, as at init), while the wet is out: otherwise the walk's
  limit would chase the new centre after the wet came back.
- **SLEW** divides (BBD's `do #$18` / `div` idiom): c = Δφ / q, 1 when Δφ ≥ q.
- **Knots** are clamped to 2..1,016 samples (a shrinking H under a slewed
  offset could otherwise reach under 2).
- **Memory**: two 1,024-word lines (L at the allocator base, R at +$400), AGU
  modulo rings; the r7 block's $00..$1f; a 103-word table (INC, PERW, DEV8,
  33 words each, and the four FAC words). Code 563 words.

## Measured

- ✅ **Render gates, 4 Nov 2026** (`verify_vibrato`, 42 checks, this tree,
  dsp_host): MIX 0 bit-exact in every shape; an FX2 instance bit-exact dry at
  any setting and `-guard` clean on both slots; DEP 0 a pure 2-sample delay
  of a full-scale two-signed sawtooth within 5 LSB; the DSP's delay
  trajectory (read off a ramp input) within 0.014 samples of the reference
  in every shape and setting tried; the swing 2·DEP apart at 1 kHz (SINE and
  SQR at 127: −103.4..+97.6 cents measured vs −102.9..+97.1); SQR a trill,
  99 % of periods on its two pitches; SPD 64/94/120 within 0.1 % of the
  law; SHP switched three times and every continuous knob moved mid-render
  by `-paramfile` with no step steeper than the input's own, matching the
  reference; SPD and DEP stepped in one block (80 -> 120, 120 -> 20, DEP
  127 -> 10) with the delay never moving faster than the walk's limit
  (largest 0.069 samples a sample at the 80 -> 120 step, limit 0.087);
  two RND instances (r7 0x6100, 0x6400) never identical after the first draw,
  each the reference with its own seed; knob words carrying an LFO's
  fraction (`-pword`) moving SPD, DEP, SLEW, WID and MIX by it, and SHP
  masking it.
- ✅ `verify_dirty_state` (−138.5 dBFS from a garbage-filled block),
  `verify_init_regs`, `verify_menu`, `verify_replaces`, `norep`, the
  selftest, `verify_docs`.
- 🟡 **Cost**: 108 cycles a sample on `cycle_count.py`'s static count
  (MODULATION's LINE is 266). Measured slot costs have run 1.36–1.60× the
  static count (`docs/contributing/COSTS.md`), which would put it near 4 % of
  a slot; not read on a unit.
- Built with Ubuntu's m68k binutils in a Linux sandbox (the pinned toolchain
  could not be downloaded there); the DSP side does not use it.

## On the unit

Bryan T's MKII, `_bt_oct` with VIBRATO on FX1 (DJ EQ given up), 4 Nov 2026,
the build before the walk's limit: sounds right; an occasional pop or
cutout, consistent with the knob-jump spike the limit removes (not yet
re-checked). Defaults moved to SPD 80, DEP 48 by ear on the unit.

Still to check: every page-1 knob and SHP's four positions on FX1, a
SHP change while playing, SLEW 0 and 127, WID on SQR and on RND, an FX2
instance (dry), four FX1 instances on one core, and LOAD METER's slot cost.

## Open

- The slot cost on a unit.
- Whether the swing cap (500 samples) should be traded for the lines' whole
  3,072-word slot (1,536 a channel needs the linear-plus-mask idiom).
- An onset fade (depth rising after a trig) needs the trig on the DSP side.

## Gates

`tools/verify/verify_vibrato.py` (the manifest's gate): the list above.
`remixes/test/vibrato` carries it on FX1 for the gates and a check image.
