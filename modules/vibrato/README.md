# `vibrato` — VIBRATO

A pitch vibrato on FX1 or FX2: sine, triangle, a square trill or stepped
random pitch, with the depth set in cents.

One modulated delay per channel, wet only, MIX blending it with the dry. DEP
is a pitch depth: it holds as SPD moves, because the delay swing is scaled by
1/rate (and capped by the 1,024-word lines, so very slow and very deep runs
out of line first). Each shape is a pitch trajectory and the delay is its
integral: SQR is a true two-note trill (a triangle in delay), TRI a triangle
in pitch, RND a new random pitch every half cycle, the square's step rate.
SLEW rounds whatever shape is selected; WID leads R by up to half a cycle,
and on RND decorrelates R's random stream instead.

**FX1 or FX2.** It runs on either slot, chosen when the remix is built by
the SLOTS setting (store `octabam.vibrato`), the same setting SPECTRUM,
CHARACTER and MODULATION carry (`tools/remix/stations.py`):

- `FX1` (the default): VIBRATO is on the FX1 chooser; an FX2 instance is a
  dry pass that writes nothing (`Claims(fx1_only=True)`). This is the
  setting for a remix with the bus servers, whose tanks own the FX2 slots.
- `FX1+FX2`: VIBRATO is on both choosers and runs live on both, for a remix
  without a server: `settings={("octabam.vibrato", "SLOTS"): Pin("FX1+FX2")}`
  (`remixes/test/vibrato-fx2`). An FX2 instance renders exactly what an FX1
  instance does; on one track FX2 follows FX1, so both slots is a vibrato on
  a vibrato. Eight instances on a core (FX1 and FX2 of its four tracks) are
  about 36 % of a frame at the measured 4.5 % a slot.

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

SPD and DEP glide: each knob word runs through two one-poles in a row, each
1/32 of the way a block (11.6 ms on the unit; together -0.7 dB and 32° of lag
at 4 Hz, -2.5 dB at 8 Hz), snapped onto the knob within one LFO-fraction LSB,
so a held knob reads exactly. Two, because one alone has a corner in its
velocity at every knob step, and the centre's velocity is pitch. A hand
twist, a p-lock and an LFO on either all pass through it; an LFO on SPD or
DEP faster than a few Hz is softened, and a square LFO's edge is rounded.

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
  samples. H follows SPD's and DEP's glided words at once: gliding the words,
  not H, keeps the rate and the swing consistent (the depth stays DEP's
  through an SPD move). Taken at once, each step of a twist resized H and
  moved the centre 2 + H in one block, and the walk chased it at its limit:
  30 cents block to block on an SPD twist, 175 on DEP (5 Nov 2026, heard on
  the unit; gate 8e). With the glide: 5.8 at most.
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
  modulo rings (every FX1 and FX2 base is 1024-aligned, the shared window's
  included); the r7 block's $00..$1f; a 103-word table (INC, PERW, DEV8,
  33 words each, and the four FAC words). Code 563 words.

## Load

No selectable configuration of VIBRATO alone can overload a core: its
worst, eight instances on one core (SLOTS = FX1+FX2), measured 63.0 % of a
frame at peak against the 95 % limit. Beside other effects the remix's bound
is COSTS.md's: base + 4 x (dearest FX1 effect) + 4 x (dearest FX2 effect),
with VIBRATO at 4.5 % a slot.

## Open

- The glide's cost on the slot: 75 instructions a block more in dsp_host's
  block meter (1,840 to 1,915 at SINE, one instance, 16 frames, 5 Nov 2026;
  two calls of 38), about 4 %; the 4.5 % a
  slot and 63.0 % for eight instances above were measured before it.
- The slot cost on a unit.
- Whether the swing cap (500 samples) should be traded for the lines' whole
  3,072-word slot (1,536 a channel needs the linear-plus-mask idiom).
- An onset fade (depth rising after a trig) needs the trig on the DSP side.
