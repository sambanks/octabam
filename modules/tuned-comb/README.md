# `tuned-comb` — TUNED COMB

Stock COMB's page, with the pitch held in tune. On the stock COMB, closing LP
pulls the note flat, by up to a semitone and more in settings that still ring,
and FB moves it too. TUNED COMB plays the note PTCH and FINE name at any LP and
FB, so a p-locked or LFO'd LP never needs a matching tuning lock.

A feedback comb with a one-pole lowpass in the loop, stereo, the wet only, MIX
blending it with the dry.

**FX1 or FX2.** It runs on either slot, chosen when the remix is built by the
SLOTS setting (store `octabam.tuned-comb`), the same setting VIBRATO,
SPECTRUM, CHARACTER and MODULATION carry (`tools/remix/stations.py`):

- `FX1` (the default): TUNED COMB is on the FX1 chooser; an FX2 instance is a
  dry pass that writes nothing (`Claims(fx1_only=True)`).
- `FX1+FX2`: TUNED COMB runs live on both, for a remix without a server
  (`remixes/test/tuned-comb-fx2`).

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | PTCH | A#0–A8 (96 notes, stock's names), default C3 | the note |
| 1 | 1 | FINE | 0–127, default 64 | fine tune, (k − 64)/64 semitones: ±1 semitone |
| 1 | 2 | LP | 0–127, default 127 | the lowpass in the loop: 20 kHz · 2^((k − 127)/16), 16 steps an octave, 81 Hz at 0; 127 is the loop unfiltered |
| 1 | 3 | FB | 0–127, default 96 | the decay time, T60 = 0.05 s · 600^d, d = \|k − 64\|/63 (at most 1): 0.05 s next to 64, 30 s at ±63 (0 is −63); the same T60 at every note with LP open. Below 64 the polarity flips and the note sounds an octave down, as on the stock COMB; 64 is no feedback |
| 1 | 5 | MIX | 0–127, default 0 | dry/wet, k/128; 127 = 1.0, the comb alone; 0 is an exact passthrough. Glides (1/8 of the way a block) |

FINE, LP and FB read the knob word's LFO fraction, so an LFO on them, and an
LFO Designer "fine" offset, move smoothly between steps. At A#0, FINE reaches
about 20 cents down: the lines stop at 1,530 samples.

**Decay limits.** The per-pass gain is at most 0.998 (a positive loop near 1
rings at DC), so the longest decays shorten at high notes: about 26 s at C3,
6.6 s at C5, 1.6 s at C7. LP closed shortens the decay further, more at high
notes, as on the stock COMB: the gain is the law's with LP open, so the comb's
DC mode, which LP leaves alone, never rings longer than the note. At C8 and
above, short decays run up to 20 % long (the Hermite's loss is taken on the
unit circle; the ring's pole is just inside it).

## How it stays in tune

The loop is y = b·herm(L) + (1 − b)·y′ (a one-pole, b = 1 − a), s = x + g·y,
with s written back into the line. Stock's loop length is SR/f0 samples; the
lowpass's lag on top of it is what makes the note flat. Here L is solved so
the loop's **pole** sits on the sounding fundamental w (f0, or f0/2 with FB
below 64): z = r·e^{jw} with z^L·(1 − a/z) = g·(1 − a). With ρ = a/r and ψ =
atan2(ρ sin w, 1 − ρ cos w):

- phase: L = P·(1 − k·ψ), P = SR/f0, ψ in cycles, k = 1 (FB above 64) or 2 (below)
- magnitude: log2 r = (log2(|g|·b) − log2|1 − ρ e^{−jw}|) / L

The plain phase-delay correction (r = 1) leaves a damped note flat: a damped
pole lags more than the filter does on the unit circle. The 4-point Hermite
read has a phase error of its own at high notes (several cents at A8); its
phase delay at w, from the four weights at L's fraction, is taken out too.

FB's gain is the law's with LP open: |g| = r^L0 / |S|, r the T60's pole radius
a sample, L0 the loop on the lowpass's circle and S the Hermite read's
response at w (its loss a pass), at most 0.998. With LP open the solve is
closed-form (L = L0). With LP closed the pitch is solved by a damped
fixed-point iteration on log2 r at that gain, lr ← (F(lr) + 0.1·lr)/1.1:

- A large change starts it cold (r = 1) with two steps, within 1.2 cents of
  the settled loop.
- A small change starts it warm, from where it was: one step if only LP
  moved, two if PTCH, FINE or FB did. Small means each knob's move over its
  limit (PTCH 1 semitone, FINE 8, FB and LP 4) sums to at most 1, from a
  block that was iterating, with the polarity unchanged: an LFO or a slide.
- Then one warm step a block for six blocks, and the solve is frozen until
  PTCH, FINE, LP or FB moves again: held knobs cost nothing for it.
- With LP closed, a change after the first block is split over two blocks,
  which halves the peak cost under a moving knob. Its block computes the
  setup and the gain while the loop keeps the last block's b, g and L; the
  next takes the steps and applies b, g and L together, reading no knobs.
  A change lands one block (0.36 ms) later, and under continuous modulation
  the loop updates every other block.

Under a swept LP, FINE or FB the loop stays within 0.01 cent of the settled
loop. A PTCH slide by semitones with LP and FB low (the slowest iteration)
is up to 7 cents off for the block after each step. Every note that rings is
within 0.5 cent of its named pitch, both FB polarities, A#0 to A8.

## FUNC stops

Holding FUNCTION while turning a knob walks it through stops, one a detent, instead of stock COMB's jumps to the ends (LP had none). Without FUNCTION a knob turns as stock: one unit a detent, x7 pushed. The mechanism is LOFI2's (`modules/lofi2/README.md`, "FUNC stops"): `func_stops.s` gives each knob its own P+0x12a handler.

| knob | stops (raw) | what they are |
|---|---|---|
| PTCH | +-12 a detent | an octave, the note's name kept; it stays where the octave would leave A#0 .. A8 |
| FINE | 0 32 64 96 127 | -100, -50, 0, +50, +98 cents |
| LP | 0 10 26 42 58 74 90 106 127 | 81 Hz, then 125, 250, 500 Hz, 1, 2, 4, 8 kHz (each within 0.7 %), open |
| FB | 0 12 19 28 34 41 64 87 94 100 109 116 127 | T60 30, 9.8, 4.8, 1.9, 1.05, 0.52 s; none at 64; the same above (below 64 the octave down) |
| MIX | 0 32 64 96 127 | |

## Design

Prototyped in Faust (`comb.dsp` beside this file: the listening model, solved
exactly per sample, with the same FB decay law; its COMP selector compares the
stock loop, the on-circle correction and the pole solve). The DSP and
`tuned_comb_ref.py` are block-based:

- **Per block, when solving:** the pitch s = PTCH + (FINE − 64)/64 semitones
  above A#0; P and 1/P from E2 (2^−x, 65 entries) and the shift table SH;
  sin and cos of the sounding phase from the stock sine at X:0x6c00; b from
  BLP (33 entries; LP 127 is exactly 1); atan by one div and ATN, log2 by
  clb/normf and LG2, 1/L by one div, 2^y by E2 and a shift. The pitch's
  setup is kept when only LP moved. The delay walks to L in a straight line,
  a 16th of the way a sample.
- **Per sample, both channels inline:** the four taps from a guard-word line
  (below), most read in the parallel slots of other work; the Hermite in Niemitalo's form, worked in eighths; the
  lowpass in double precision (a single-word one-pole has a dead band the
  loop would hold as DC); s = x + g·y, written at the next index and its
  guard twin; out = x + m·(s − x). The Hermite's coefficients and the
  lowpass are rounded (a floor there is a DC bias the feedback holds), and
  the loop's sum s is truncated toward zero: rounded, a loop with g near 1
  holds a limit cycle (a DC level up to about 0.5/(1 − g) LSB); toward zero
  |s| never grows from it, and after a note dies a few LSB remain at most.
- **Memory:** two lines of 1,536 words (L at the allocator base, R at
  +1,536), each 1,533 data words and 3 guard words that mirror words 0..2, so
  the four taps never wrap (FX1 bases are not all 2048-aligned: the lines
  are linear and the write index wraps by compare); the r7 block's $00..$3c;
  a 175-word table (E2 65, LG2, ATN, BLP 33 each, SH
  11). Code 1,142 words: a remix gives it a run of about 1,320 free words
  with its table (PLATE REV and SPRING REV together, or COMPRESSOR, LO-FI, DJ
  EQ and COMB FILTER together), or 1,142 where the table goes to the stock
  curve bank (with DJ EQ out of the remix).

## Load

About 4.5 % of a frame a slot with the knobs held, and about 6 % with a knob
moving every block (an LFO on LP, FB on the crossfader); stock COMB FILTER is
2.7 %. No selectable configuration of TUNED COMB alone can overload a core:
its worst, eight instances on one core (SLOTS = FX1+FX2) with every knob
moving, is about 48 % of a frame above the core's base, under the 95 % limit.
Beside other effects
the remix's bound is COSTS.md's: base + 4 x (dearest FX1 effect) + 4 x
(dearest FX2 effect), with TUNED COMB at 6 % a slot.

The sample loop keeps its carried values in address registers, walks the
lowpass state with a pointer, runs both channels inline and reads most taps
in parallel slots. The per-block solve runs only when a knob moves, and its
cost under modulation is held down by the warm start and the split above.

## Open

- The solve under a moving knob: the gain block and the two-step block cost
  about the same; further cuts are in the law's two Hermite responses and
  the steps' atan. Sixteen-step divides save little and leave the
  reference's bound.
- The code size: 1,142 words needs a larger free run than one stock effect
  other than the reverbs gives.
- The top octave's decay: the Hermite's loss off the unit circle.
