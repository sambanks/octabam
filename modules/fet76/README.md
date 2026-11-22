# `fet76` — FET76

A per-track insert modelled on the UREI 1176LN FET limiting amplifier
(1967), built from its manual (block diagram, schematic, specifications).
Its author uses it on the master track as the last stage of the chain.

Author: MaMarko (Marko Brajković, [braikomarko-hub](https://github.com/braikomarko-hub)): the idea, the listening and the tests on the unit.
**The code was written by Claude (Anthropic)**: model, calibration, DSP code and gates.

UREI, Universal Audio and 1176 are trademarks of their owners. This module
is not affiliated with or endorsed by Universal Audio; the names below only
say which unit it is modelled on. No text, artwork or logo of the original
is reproduced: the README describes the circuit in its own words, and the
model takes part values and published specifications only (`THIRD_PARTY.md`).

## What is modelled

| the 1176LN (manual) | FET76 |
|---|---|
| INPUT attenuator before a FIXED threshold | INPT: gain before the gain cell; no threshold knob |
| Q1, a FET as the lower leg of a divider with R5 | G = 1 / (1 + u), u the gate voltage the detector holds |
| FEEDBACK: the side chain reads the stage's output | the detector reads the output, the loop solved inside the sample (stable at 20 µs) |
| ratio buttons set side-chain level and diode bias | per button a side-chain gain S and a bias T: 4, 8, 12, 20:1 averaged over the first 10 dB of gain reduction |
| ATTACK R55 charging C27 (0.022 µF): 20 … 800 µs | ATK 127 … 1; ATK 0 = OFF (the attack pot's click), no limiting |
| C22 (0.22 µF) behind C27, RELEASE R56 + R57: 50 ms … 1.1 s | two capacitors: a short peak only fills C27 and lets go fast, held limiting fills C22 and lets go at the knob's time (program-dependent release) |
| "LN": the FET linearised | the FET's square-law residue, an even harmonic that grows with gain reduction; REV BLUE = the earlier units, more of it |
| class-A output stage, +22 dBm | z − 0.02 z³ (0.5 % THD at full scale) |
| ALL BUTTONS IN | the four side-chain gains together, the bias of a 16:1, attack three times slower, the residue ×8 |

Assumed (not in the sources): the coupling resistor between the two
capacitors (220 k), the buttons' thresholds at INPT 64 (4:1 −20, 8:1 −17,
12:1 −15, 20:1 −13 dBFS peak), ALL's numbers, the residue's size, the side
chain's rail (it keeps ATK audible on a big step).

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | INPT | bipolar, default 64 | INPUT: −30 … +30 dB into the fixed threshold |
| 1 | 1 | OUTP | bipolar, default 64 | OUTPUT: −30 … +30 dB |
| 1 | 2 | ATK | 0–127, default 100 | ATTACK: 1 = 800 µs … 127 = 20 µs; 0 = OFF |
| 1 | 3 | REL | 0–127, default 64 | RELEASE: 0 = 1.1 s … 127 = 50 ms (after held limiting) |
| 1 | 4 | RATI | 4:1, 8:1, 12:1, 20:1, ALL | the ratio buttons |
| 1 | 5 | MIX | 0–127, default 127 | dry/wet: 127 = the 1176 alone, 0 = an exact passthrough |
| 2 | 6 | REV | LN / BLUE | the revision: LN, or the earlier units' stronger 2nd harmonic |

Stereo-linked as the 1176 SA: the larger of |L| and |R| drives one gain.

## Beside the other dynamics in this tree

Stock COMPRESSOR, SIDECHAIN_COMPRESSOR (stock COMPRESSOR with a side-chain
key) and CHARACTER's COMP and GLUE are feed-forward compressors with a
threshold knob. FET76 is a feedback peak limiter with a fixed threshold that
INPT drives into, a 20 µs attack, a two-capacitor release that follows the
programme, the four ratio buttons and ALL, and the FET's even harmonic: the
1176's way of working, not a compressor's threshold and ratio.

## DSP

No buffer and nothing outside its r7 block. Two 24-step divisions per
sample (the loop's linearised solve and the FET's 1/(1 + u)); everything
else branchless. The fixed-point model is `fet76_ref.fixed()`; the float
model `fet76_ref.FET76` (the same file) is what the numbers above were
measured on.

Eight FET76 on one core (FX1 and FX2 on four tracks) are 2,480 cycles a
sample by the same static count, under the 3,120 the build budgets for
modules (`cycle_count.py`); no guard is needed for the instance count.

| what | before the audit | now | how it was measured |
|---|---|---|---|
| code | 406 words | 401 words | `dsp_asm` at P:$800 (`tools/build/dsp_forms.py` `assemble_words`) |
| P table | 143 words | 143 words | `len(MODULE.dsp.ptable)` |
| sample loop | 311 cycles a sample | 310 cycles a sample | `REMIX=test/fet76 python3 tools/build/cycle_count.py` (a static floor: the word span of the loop, the two calls priced at their 40 words) |

For comparison, stock COMPRESSOR: 103.1 cycles a sample in the cycle model
(`docs/contributing/CYCLE_SCAN.md`, `interlock_scan.py`, a different
instrument from `cycle_count.py`) and 2.18 % of a core on a unit
(`docs/contributing/COSTS.md`). FET76's figure in the cycle model is not yet
taken: `interlock_scan.py` needs a built tree.

## DSP audit

Checked against `docs/contributing/DSP_AUDIT.md`, checklist version 4
(T01 to T34). Every change taken is bit-identical: the gate's own cases
(`verify_fet76.run_gates`, against `fet76_ref.fixed()`) pass before and
after each commit.

| row | site | status |
|---|---|---|
| T31 | four `move #>$XX0000,D` literals (init, two per block, one in the sample loop) | taken: the one-word `move #$XX,D`; −4 words, −1 cycle a sample |
| T31 | the generated `@NAME@` constants (`@EMAX8@` in the loop is `$600000`) | not taken: the template's constants stay the generator's (as DISTORX's DX1) |
| T34 | `add #>$1,b` in `f76_exp` (twice a block) | taken: `add #$1,b`; −1 word |
| T11 | three reads of uA8 while it is in `a` or `x0` | taken: register moves; same words, the displaced access's cycle (cycle model, not measured here) |
| T11 | aL and aR stored and read back for the peak | not taken: needs a register the loop does not have free |
| T14 | state displaced from r7 in the loop | not taken: walking it is a re-laid state block, a design change |
| T16, T09 | parallel moves | none: the loop's moves are displaced `x:(r7+d)`, which is never a parallel move |
| T25, T26, T33 | stalls | not taken: they need the cycle model (`interlock_scan.py`, a built tree) to price; the per-block table reads keep their `nop`s (two moves between an address write and its use) |
| T28, T30 | P reads | none in the sample loop: the table is read once a block |
| T29 | the two `do #$18` divisions in the loop | not taken: unrolling is 24 words a division for about 5 cycles, a trade |
| T01, T05, T12, T19, T21 | frame advance, hoisting, `lua`, displacement range | already in the cheap form: post-step stores, `n0` set above the loop, no `move r7,rN`, every displacement under `$40` |

## Gates

`tools/verify/verify_fet76.py`: the dump against `fixed()` bit for bit
(26 knob sets × three signals, a split block, LFO-dirty page words), MIX 0
an exact passthrough, silence to zeros, and the manual on the fixed model:
the four ratios, ATK OFF, THD < 0.5 % with limiting at the slowest release,
release fast after a 5 ms peak and at the knob's time after one second;
and at ATK 0 with INPT and OUTP up, a clip, never a wrap (OUTPUT's gain is
applied in two normf steps, at most 7 bits each, inside the accumulator's guard bits).

## On the unit

The author's MKI, by his report of 22 Nov 2026: FET76 has been in his own
images (aCiDtRacK) since ACIDV82 (2 Nov 2026), the first with FET76, mainly
on the master track and sometimes on single tracks, with no defect noticed.
By ear, not a measurement. The DSP source that ran is the one this module
was added with; the audit's three commits after it are bit-identical in the
emulator and not flashed. `test/fet76` itself has not run on a unit.
