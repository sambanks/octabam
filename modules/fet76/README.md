# `fet76` — FET76

A per-track limiter modelled on the UREI 1176LN FET limiting amplifier
(1967), built from its manual (block diagram, schematic, specifications).
There is no threshold knob, as on the original: INPT drives the signal into
a fixed threshold, the ratio buttons set how hard it limits, and the release
follows the music. It suits the master track as the last stage of a chain.

Author: MaMarko (Marko Brajković, [braikomarko-hub](https://github.com/braikomarko-hub)): the idea, the listening and the tests on the unit.
**The code was written by Claude (Anthropic)**: model, calibration, DSP code and gates.

UREI, Universal Audio and 1176 are trademarks of their owners. This module
is not affiliated with or endorsed by Universal Audio; the names below only
say which unit it is modelled on. No text, artwork or logo of the original
is reproduced: the README describes the circuit in its own words, and the
model takes part values and published specifications only (`THIRD_PARTY.md`).

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

## How it works

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

Not in the sources, so chosen here: the coupling resistor between the two
capacitors (220 k), the buttons' thresholds at INPT 64 (4:1 −20, 8:1 −17,
12:1 −15, 20:1 −13 dBFS peak), ALL's numbers, the residue's size, and the
side chain's rail (it keeps ATK audible on a big step).

Stereo-linked as the 1176 SA: the larger of |L| and |R| drives one gain.
The ratios come out near 4, 8, 12 and 20:1 a few dB over the threshold; the
distortion with 10 dB of limiting at the slowest release is about 0.3 % at
1 kHz; after a 5 ms peak the gain comes back in about 10 ms, after a second
of limiting in about 0.3 s at REL 64.

## Beside the other dynamics in this tree

Stock COMPRESSOR, SIDECHAIN_COMPRESSOR (stock COMPRESSOR with a side-chain
key) and CHARACTER's COMP and GLUE are feed-forward compressors with a
threshold knob. FET76 is a feedback peak limiter with a fixed threshold that
INPT drives into, a 20 µs attack, a two-capacitor release that follows the
programme, the four ratio buttons and ALL, and the FET's even harmonic: the
1176's way of working, not a compressor's threshold and ratio.

## DSP

No buffer and nothing outside its r7 block. Two 24-step divisions a sample
(the loop's linearised solve and the FET's 1/(1 + u)); everything else is
branchless. The fixed-point model is `fet76_ref.fixed()`, the float model
`fet76_ref.FET76`; `generate_asm.py` writes `fet76.asm` from
`fet76.tmpl.asm` and the manifest's constants.

## Cost

401 words of code and 143 of table. The sample loop is 310 cycles a sample
by `cycle_count.py`'s static count; eight FET76 on one core (FX1 and FX2 on
four tracks) are 2,480, under the 3,120 the build budgets for modules, so no
guard is needed for the instance count.

## Gate

`tools/verify/verify_fet76.py`: the module against `fet76_ref.fixed()` bit
for bit (knob sets across every control, three signals with L ≠ R, a split
block, LFO-dirty page words), MIX 0 an exact passthrough, silence to zeros,
no wrap at full gain, and the manual's ratios, ATK OFF, distortion and
release on the fixed model.

## Limits

- The numbers listed under "How it works" as chosen here are not in the
  1176LN's sources.
