# DSP data tables: what the ColdFire uploads at boot

The ColdFire ships a set of X and Y data modules to both DSPs at boot:
lookup tables for waveforms, knob warps and filter coefficients. They are
resident in every build; any effect can read them.

Provenance: the catalogue is Bryan T's, read
from the payload module records with a Q23 signed decode; rows marked 
were re-derived here. Shapes are inferred from that decode (an integer or
unsigned table has a different shape); stride findings are statistical;
segment boundaries inside the big containers come from a discontinuity
detector and are approximate (a disassembly found two sub-tables it
missed). Attribution is absent unless a disassembly established it: look
up the effect's `P:` range in `DSP.md`'s dispatch table and disassemble
that span.

The addresses below are payload A's. The X data blocks are not at the same
addresses in payload B: the curve bank is `X:0x438` in A and `X:0x42b` in
B, and the Y tables shift by 16 ("Payload-relative addresses" below). A module is one
source assembled into both payloads, so a bare stock-table literal is
right on tracks 5-8 and wrong on 1-4; declare stock table addresses
(`DspSection.ptable` for a module's own tables) or read through a
build-supplied base.

## Waveforms

| address | words | contents |
|---|---|---|
| `X:0x06c00` | 1,024 | sine, `0x3ff` modulo addressing |
| `X:0x07000` | 1,024 | single-cycle ramp/saw (0 → −1, wrap to +1, → 0) |

 The sine is exact to 1.75e-7 (Q23 quantisation) and sits at the same
address in both payloads. `x:0x6c00` with `m = 1023` is a free-wrapping
oscillator for 2-3 instructions.

## Curve banks

| address | words | layout | contents |
|---|---|---|---|
| `X:0x04840` | 4,096 | 32 × 128, knob-indexed 0-127 | mostly one-pole coefficient pairs: a near-1.0 falling curve beside a small rising one (pole radius, complementary gain). Eleven of the 32 are near-linear; 12-15, 17, 19, 21, 29 and 31 are curved. The build parks module P tables here (`ptable`) |
| `X:0x08b70` | 384 | 3 × 128 | saturating-exp curves |
| `X:0x088a2` | 258 | 2 × 128, `0x7f` mask | saturating-exp lowpass warp (COMB LP, CHORUS FBLP) |

## Interleaved coefficient tables

| address | words | layout | shape |
|---|---|---|---|
| `X:0x085a2` | 384 | 64 × 6 | five columns rising to ~0.65, one negative falling to −0.65 |
| `X:0x08722` | 384 | 64 × 6 | six decaying exponentials from 1.0 at different rates: a damping family against a 0-63 control |
| `X:0x089a4` | 72 | 18 × 4 | two near-flat columns (~0.3-0.5), two rising from negative |
| `X:0x089ec` | 72 | 18 × 4 | same structure, different values |
| `X:0x08a34` | 72 | 18 × 4 | same again |
| `Y:0x00290` | 1,024 | 128 × 8 | eight smooth rising curves 0.14-0.34, converging at exactly 0.5 |
| `X:0x08d4b` | 25 | 5 × 5 | ≈ 0.25-scaled identity |

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
| `X:0x00438` | 6,305 | ~8 concatenated large curves: sigmoid plateaus rolling 1 → 0, one 1 → −1 transition, two bell shapes, a 128-word linear micro-ramp. Detected starts (`0x438, 0x720, 0xac9, 0xdb1, 0x105a, 0x15c7, 0x1890, 0x1c59`) are approximate; disassembly found real sub-tables at `0x13c7` and `0x1bd9` |
| `X:0x06c00` | 3,730 | fully segmented, below |

`X:0x06c00` internally:

| sub-address | words | contents |
|---|---|---|
| `0x6c00` | 1,024 | sine |
| `0x7000` | 1,024 | saw |
| `0x7400` | 1,024 | 2^x exponential mantissa, −1.0…−0.5 (LO-FI AMF/DIST/AMD) |
| `0x7800` | 17 | small hook curve |
| `0x7811` | 128 | exponential decay 0.00109…0.1885 |
| `0x7891` | 128 | exponential decay, ~18-20× smaller |
| `0x7911` | 129 | all zero |
| `0x7992` | 256 | saturating rise 0.854 → 0.999 |

## The one confirmed attribution

EQUALIZER (`P:0x00bad`-`0x00cc7`), by disassembly:

| parameter | index | table | shape |
|---|---|---|---|
| GN1/GN2 | raw 0-127 | `X:0x01bd9` | saturating exponential 0.0039 → 0.958 |
| GN1/GN2 trim | same | `X:0x01c59` | ~1e-5 correction term |
| FRQ1/FRQ2 | raw × 4 (`asr #$e`) | `X:0x015c7` | large S-curve, +1.0 rolling to ≈ −0.996 |
| FRQ1/FRQ2 trim | same ×4 | `X:0x013c7` | ~3e-5 correction term |

FRQ reads its table with 4× a normal knob's index resolution (two extra
bits, unexplained).

## Use to our modules

A table read costs ~5 instructions and an AGU register; `k²` costs three
instructions and no register. Measured against his catalogue
(correction to it: the curve at `X:0x01bd9` is GN1/GN2, not FRQ1; FRQ
reads `X:0x015c7` with a ×4 index):

- Knob tapers: the best fit of any of the 32 curves (with reversals and
  inversions) to `k²` or `(1−k)³` is 0.040 RMS.
- BusVerb: its cost is memory access (tank lines, allpasses, MACs); its
  eight LFOs are per-block triangles (~5 cycles/sample for all eight).
- The bus path: `send_client` is sum-and-accumulate with no function
  evaluation; the delay's 1/√N table is in its own P table.
- BusDelay's `smoothw` (`s = g²(3−2g)`) at the wow/flutter LFO sites could
  read the sine (`2·s(triangle) − 1` approximates it), saving ~28 of 2,338
  cycles at the cost of an address and a modulo register in the module
  with the tightest register pressure; the GRAIN window sites cannot (they
  need `s(g) + s(1−g) = 1` exactly; best stock complementarity error 0.24).
- A carrier read from the 1,024-point sine at `X:0x06c00` was built and
  measured for BodeShift (removed;
  `git show 8e934a57^:modules/bodeshift/`): 344 → 328 cycles, and two
  phase-quantisation products at −72.5 dB (3,860 Hz and 5,249 Hz) that a
  sideband gate cannot see. A linearly interpolated read reaches −107 dB
  at ~22 instructions.

## Payload-relative addresses (Bryan T)

The payloads are linked separately:

| block | payload A | payload B | words | content |
|---|---|---|---|---|
| curve bank | `X:0x438` | `X:0x42b` | 6,305 | identical |
| block below it | `X:0x421` | `X:0x421` | 23 on A, 10 on B | the 13-word cause |
| `X:0x4840` | same | same | 4,096 | identical |
| `X:0x6c00` | same | same | 3,730 | identical |
| Y table | `Y:0x290` | `Y:0x2a0` | 1,024 | identical |
| Y tables | `Y:0x690` / `0x710` / `0x715` | `Y:0x6a0` / `0x720` / `0x725` | 128 / 5 / 128 | not compared |

Stock code carries a different extension word per payload (EQUALIZER
`payload_A.asm` `0x000c07` = `0a73ce 0013c7`, `payload_B.asm` `0x0009c7` =
`0a73ce 0013ba`). A module is one source assembled into both, so a bare
literal into the curve bank is right on tracks 5–8 and 13 words off on
1–4; past the end of the relocated table it reads unuploaded memory (his
LOFI2: knobs 125/126 identically dull, 127 fine). `send_probe`'s
single-payload render dumps payload A. Our modules' `#>` immediates in
`0x438..0x1cd8` (156 sites) were read: modulo masks, bus
scratch (`$901`…`$9da`, placed identically on both cores), a tap length
(1407), a decay coefficient (`$755`); none reads a stock table.
`docs/contributing/FAILURE_MODES.md` carries the failure mode. His fix (an `xtables` field on
`DspSection`, immediates rewritten per payload with the delta read from
the image being built) is in his fork, not landed here. Also argued for:
a build flag on undeclared absolute X literals in the relocated range; a
four-character limit on `Formatter.STEPPED` labels (a ten-character label
threw `VEC:04` at `ADDR 4E007890`); a range check on `lua` displacements
(seven-bit signed, `dsp_asm` wraps `lua (r7+$40),r1` to `r7-$40`;
unverified here).
