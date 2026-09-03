# DSP data tables — what the ColdFire uploads at boot

The ColdFire ships a set of X and Y data modules to both DSPs at boot. They
are lookup tables: waveforms, knob warps, filter coefficients. **They cost us
nothing** — they are resident in every build, we do not place them, and any
effect can read them.

**Provenance.** The catalogue is **Bryan T's** (`docs/EXTERNAL.md`), read from
the payload module records with Q23 decode. It is deliberately **shape-only**:
it says what the numbers look like, not which effect reads them, except where
prior work established it. Rows marked ✅ are ones we re-derived here.

**Read this first, or you will misuse it:**

- **Shapes are inferred from a Q23 signed decode.** If a table is really
  integer or unsigned its shape is different. Smooth all-positive curves are
  insensitive to this; the bipolar ones are not.
- **Stride findings are statistical.** They say how the data is *organised*,
  which only suggests how it is *read*.
- **Segment boundaries inside the big containers come from a discontinuity
  detector**, so smoothly-joined tables merge into one. Bryan's own
  disassembly proved the detector wrong in one place — treat every boundary
  as approximate until a disassembly confirms it.
- **Attribution is mostly absent, on purpose.** "This looks like a damping
  curve" is not "this is the damping curve". To settle one, look up the
  effect's `P:` range in `DSP.md`'s dispatch table and disassemble that span.

---

## Waveforms

| address | words | contents |
|---|---|---|
| `X:0x06c00` | 1,024 | **sine**, `0x3ff` modulo addressing (prior work) |
| `X:0x07000` | 1,024 | **single-cycle ramp/saw** (0 → −1, wrap to +1, → 0) |

✅ **Verified here (31 Aug 2026):** the sine is exact to **1.75e-7** — Q23
quantisation — and sits at **the same address in both payloads**, which is what
an insert needs, since an insert is placed in both. `x:0x6c00` with `m = 1023`
gives a free-wrapping oscillator for 2–3 instructions.

Together these read as an LFO/oscillator waveform bank.

## Curve banks

| address | words | layout | contents |
|---|---|---|---|
| `X:0x04840` | 4,096 | **32 × 128**, clean grid, knob-indexed 0–127 | see below |
| `X:0x08b70` | 384 | 3 × 128 | saturating-exp curves (prior) |
| `X:0x088a2` | 258 | 2 × 128, `0x7f` mask | saturating-exp lowpass warp (prior: COMB LP, CHORUS FBLP) |

✅ **What the 32 × 128 bank actually is (verified here):** mostly **one-pole
coefficient PAIRS** — a near-1.0 *falling* curve beside a small *rising* one,
i.e. (pole radius, complementary gain) indexed by a knob. That is the shape
you want for sweeping a one-pole filter from a control, and it is **not** a
bank of knob warps as the name suggests. Eleven of the 32 are near-linear;
curves 12–15, 17, 19, 21, 29 and 31 are the genuinely curved ones.

## Interleaved coefficient tables

| address | words | layout | shape |
|---|---|---|---|
| `X:0x085a2` | 384 | 64 × 6 | five columns rising to ~0.65, one negative falling to −0.65 |
| `X:0x08722` | 384 | 64 × 6 | six decaying exponentials, different rates, all from 1.0 — a damping-curve family against a 0–63 control |
| `X:0x089a4` | 72 | 18 × 4 | two near-flat columns (~0.3–0.5), two rising from negative |
| `X:0x089ec` | 72 | 18 × 4 | same structure, different values |
| `X:0x08a34` | 72 | 18 × 4 | same again — three related banks |
| `Y:0x00290` | 1,024 | 128 × 8 | eight smooth rising curves 0.14–0.34, converging at exactly 0.5 |
| `X:0x08d4b` | 25 | 5 × 5 | ≈ 0.25-scaled identity — mixing/feedback-matrix shaped |

## Single curves

| address | words | shape |
|---|---|---|
| `X:0x08a7c` | 128 | smooth monotone decrease 0.97 → 0.02 |
| `X:0x08afc` | 116 | bipolar S-curve −0.94 → +0.99, zero crossing ≈ index 80 |
| `X:0x08d0b` | 64 | gentle monotone rise 0.625 → 0.715 |
| `Y:0x00690` | 128 | smooth exponential rise 0.07 → 0.97 |
| `Y:0x00715` | 128 | smooth exponential rise 0.06 → 0.89 |

## The large containers

| address | words | contents |
|---|---|---|
| `X:0x00438` | 6,305 | ~8 concatenated large curves: sigmoid plateaus rolling 1 → 0, one 1 → −1 transition, two bell shapes, ending in a 128-word linear micro-ramp. ⚠️ Detected starts (`0x438, 0x720, 0xac9, 0xdb1, 0x105a, 0x15c7, 0x1890, 0x1c59`) are **approximate and known wrong in one place** — disassembly found real sub-tables at `0x13c7` and `0x1bd9` that the detector missed |
| `X:0x06c00` | 3,730 | container, fully segmented — see below |

`X:0x06c00` internally:

| sub-address | words | contents |
|---|---|---|
| `0x6c00` | 1,024 | sine (above) |
| `0x7000` | 1,024 | saw (above) |
| `0x7400` | 1,024 | 2^x exponential mantissa, −1.0…−0.5 (prior: LO-FI AMF/DIST/AMD) |
| `0x7800` | 17 | small hook curve |
| `0x7811` | 128 | exponential decay 0.00109…0.1885 (prior) |
| `0x7891` | 128 | exponential decay, ~18–20× smaller (prior) |
| `0x7911` | 129 | all zero (padding/scratch) |
| `0x7992` | 256 | saturating rise 0.854 → 0.999 |

## The one confirmed attribution

**EQUALIZER** (`P:0x00bad`–`0x00cc7`), by disassembly rather than shape:

| parameter | index | table | shape |
|---|---|---|---|
| GN1/GN2 | raw 0–127 | `X:0x01bd9` | saturating exponential 0.0039 → 0.958 |
| GN1/GN2 trim | same | `X:0x01c59` | ~1e-5 correction term |
| FRQ1/FRQ2 | raw **× 4** (`asr #$e`) | `X:0x015c7` | large S-curve, +1.0 rolling to ≈ −0.996 |
| FRQ1/FRQ2 trim | same ×4 | `X:0x013c7` | ~3e-5 correction term |

Two things fell out of it: `X:0x01bd9` had previously been guessed as FRQ1's
curve and is actually GN's; and **FRQ reads its table with 4× the index
resolution of a normal knob**, two extra bits, unexplained.

---

## Are they useful to us? — evaluated, mostly no

✅ Measured 31 Aug 2026. Full working in `docs/EXTERNAL.md` §4.

**A table only pays when the shape is expensive to compute.** A read costs
~5 instructions *and* an AGU register; `k²` costs three instructions and no
register. So:

- ❌ **Not for our knob tapers.** Fitting all 32 curves (plus reversals and
  inversions) against the shapes our modules compute by hand: best match for
  `k²` is 0.040 RMS, for `(1−k)³` also 0.040 — rough enough to feel different,
  and more expensive than the arithmetic they would replace.
- ❌ **Nothing for BusVerb.** Its cost is tank lines, allpasses and MACs —
  memory access, not function evaluation. Its eight LFOs are triangles
  generated **per block** (~5 cycles/sample for all eight); a table read
  would cost more than the three instructions they take.
- ❌ **Nothing in the bus path.** `send_client` is 19 instructions a sample
  of sum-and-accumulate with no function evaluation at all, and the delay's
  1/√N table is eight immediates written per block (~1 cycle/sample).
- ⚠️ **BusDelay: two of five, and not worth it.** `smoothw` (`s = g²(3−2g)`,
  18 instructions, ~24 cycles a call) has **five call sites**, and they are
  not the same kind of thing:

  | site | what it windows | tableable? |
  |---|---|---|
  | 1589, 1611 | TAPE **wow / flutter LFOs** | ✅ yes — free-running modulators, no constraint. `2·s(triangle) − 1` is a cheap sine approximation, and the stock sine is the real thing |
  | 2264 | **GRAIN** window | ❌ no |
  | 2586, 2607 | **PITCH** head windows | ❌ no |

  The three windows must satisfy `s(g) + s(1−g) = 1` **exactly** — that is
  what makes `g0 + g1 == 1` at every age, which bounds the loop gain and gives
  PITCH its stability. No stock table is close (best complementarity error
  0.24), and an approximate one trades a proved bound for a few cycles.

  The two TAPE LFOs genuinely could use the sine table, and TAPE is global so
  they are paid on every path. But the saving is **~28 cycles of 2,338 (1.2%)**
  after the read's own cost, the sonic difference between a smoothstepped
  triangle and a true sine at ~1 Hz is negligible, and **BusDelay has the
  tightest register pressure of any module** (r7 `$00..$83` full, r0–r5 in
  use). Spending an address and a modulo register for 1.2% is a poor trade.
  Logged so it is not rediscovered; not recommended.
- ❌ **BodeShift's carrier: BUILT, MEASURED, REJECTED.** This was the one
  recommendation, and building it retired it. See below.


---

## The one swap we actually built — and rejected

BodeShift builds its carrier from a refined parabola (`sb_sin`, 21
instructions, called twice a sample, max error 1.09e-3 ≈ −59 dB). Replacing
it with a read from `X:0x06c00` was the only table opportunity the evaluation
found. **It was implemented and measured on 31 Aug 2026, and then reverted.**

**The implementation**, for whoever reconsiders this — twelve instructions,
because `p` is Q23 spanning −1..1 for −π..π and the table spans a full turn,
so the index is `p·512`:

```
sb_sin:                         ; in: a = p    out: a = sin(pi*p)
        asr     #$e,a,a         ; -> integer index, signed
        move    a1,x0
        move    x0,a            ; A2-clean (asr is fine, the `and` is not)
        and     #>$3ff,a        ; wrap to 0..1023
        move    a1,x0
        move    x0,a
        move    #>$6c00,x0      ; table base, and it IS 1024-aligned
        add     x0,a
        move    a,r1
        move    #>$ffffff,m1
        move    x:(r1),a
        rts
```

**What it bought:** 344 → **328 cycles** (−4.6 %) and 391 → 382 words.
MIX=0 stayed bit-exact, shift accuracy stayed at 0.00 Hz error at every knob
position, feedback stayed stable at maximum, and sideband suppression was
**identical** — 41.5 / 29.6 / 18.7 dB at 440 Hz / 1 kHz / 5 kHz.

**What it cost, and how nearly we missed it.** Every gate above passed. A full
spectrum scan — rather than the two bins the sideband test looks at — found
**two new components at −72.5 dB** (3,860 Hz and 5,249 Hz), phase-quantisation
products of the 1,024-point table. A/B against the parabola build confirmed
they are new: the reference has nothing above −75 dB but the wanted sideband,
the unwanted one and carrier leak. ⚠️ **The existing gate could not see them,
because it only measures where signal is expected.** Same family as the THD
metric that could not see an inharmonic spur.

**Why rejected.** Not because −72.5 dB is audible — it is 60 dB down and
almost certainly is not. Because **the 16 cycles buy nothing**: `mutables`
worst-core is 1,376 against 3,120 usable, i.e. 1,744 cycles of headroom. The
trade is a permanent, measurable cleanliness regression for savings we have no
use for. Revisit only if BodeShift ever lands on a card that is genuinely
tight.

**Two claims this retired**, both of which had been written down here as
argument for the swap:

- ❌ *"It drops oscillator distortion below the Hilbert pair's residual."*
  It was **already** below it — the parabola is −59 dB against a pair limiting
  at 18.7–41.5 dB. There was never an accuracy gain to win.
- ❌ *"An interpolated table would be cheaper and more accurate."* Linear
  interpolation reaches −107 dB but costs ~22 instructions against the
  parabola's 21, so it saves nothing. The cheap variant is the only one with a
  saving and it is the one that adds spurs.
