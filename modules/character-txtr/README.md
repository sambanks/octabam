# `character-txtr` — CHARACTER TXTR

[Character](../character/README.md) with a texture stage: fold → **texture** →
saturate → tilt → compress → width → mix. The source is `character.asm` as
of `0ab4e46c` with the TXTR block (`chtx2`, its per-block decode and its
P tables); everything else, knobs included, is Character's. On DJ EQ's id
`0x0d` (Character keeps LO-FI's `0x1c`; the registry allows one module per
id), drawn CHRT / CharTxtr:
[`remixes/test/character-txtr`](../../remixes/test/character-txtr/README.md)
is bottleservice with this station in Character's place.

Why a separate module: TXTR costs 163 of the station's 403 cycles per sample
and four of them beside the reverb price a core at 2,751 against the 3,120
usable (the pricer reads the reverb ~270 low, so ~3,020; the measured die
point is 3,119, the design ceiling 3,000). No hardware has run that load.
bottleservice keeps the plain station (244) until a unit has.

## The knob

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 2 | 9 | TXTR | 0–127, default 0 | Airwindows Pockey2 after FOLD: mu-law encode, quantise to 2^(16 − 12·k/128) steps (16 → 4.1 bits), decode, a hold of floor((k/128)³·32) samples (0 → 31) on one countdown for both channels, and Pockey2's blur (out = held·blur + previous held·(1 − blur), blur = 0.618 − \|coded − previous dry\| floored at 0). One knob drives both of Pockey2's sliders (A = k/128, B = 1 − k/128), wet = 1. 0 skips the stage, bit-exact |

Pages 1 and 2 otherwise as Character's: DRV FOLD WDTH COMP TONE MIX / SAT
KEY KLVL TXTR.

## Measured

- Against `pockey2_ref.py` (a float transcription of `Pockey2Proc.cpp`):
  mean |err| 0.00003–0.0034 at TXTR 8/43/64/100/127 and 0.25/0.8 FS, level
  within 0.03 dB, L == R; TXTR 0 bit-exact (`verify_character_txtr.py`).
- Cost (pricer `cycle_count.py`): 403 cycles per sample in INFL (TAPE 399,
  TUBE 366); TXTR 163 of it: two `chtx2` calls (the codec by two 257-point
  tables, interpolated; the quantiser's two multiplies and a mask; the hold
  and blur) and the shared countdown. 1,093 words per payload; its tables
  are 546 P words, parked in the stock curve bank by the build. Pockey
  (the first version, 13–22 Sep 2026 in Character) priced 277.
- Cursory testing on Sam's MKII (owner report, 16 Oct 2026). 22 Sep 2026's squeal on the master, which removed the
  first TXTR, was never reproduced on the harness and is not addressed here.
- **19 Nov 2026, the constants pass** (bit-identical: `verify_ident.py` with
  the wider matrix of sambanks/octabam#1172 (the module's own slot, payload B,
  16-sample blocks, a 2 s run, a knob ramp, stereo, the split call, the
  manifest's `dear` settings, and the r7 state after every block), IDENTICAL
  after each commit; 49 renders). Cycles a sample from
  `tools/build/interlock_scan.py` (the core manual's cycle table and stalls: a
  model, on average 3.0 % above the unit, `docs/contributing/CYCLE_SCAN.md`
  section 1): SAT=TUBE at its maximum 697.9 → 696.3. Words 1,097 → 1,087
  (`dsp_asm` at P:$800). Not measured on the unit. Three constants load as
  one-word short immediates (the three CHARACTER took), and seven small ones
  in `add`, `sub`, `cmp` and `and` (0 to 63) as one-word 6-bit immediates (the
  `cmp #>$1,b` stays: stock has no 6-bit `cmp` on b). `chtx2`'s 30 cycles a
  sample of one-cycle waits stay: it is one serial chain a channel, and its
  local reorders trade each wait for an address-register wait.

## Gates

`verify_character_txtr.py` and `verify_charkey_txtr.py` (the manifest's:
Character's two gates run on this module), `verify_dirty_state`, and the
test remix's `make check`.

## Sources

| stage | source | the law |
|---|---|---|
| TXTR | Airwindows Pockey2 (Chris Johnson, MIT, 2022; `Pockey2Proc.cpp`) | mu-law encode, `floor(y·R)/R` toward zero with `R = (int)2^(4+12B)`, mu-law decode, a hold of `floor(A³·32)` samples, blur `0.618 − \|x − lastDry\|` ≥ 0 between the held sample and the previous one. Here the codec is two 257-point tables interpolated, R is built per block from a 32-word mantissa table, and `pockey2_ref.py` is the transcription the gate measures against |

The other stages are Character's (its README, Sources). Licences in
`THIRD_PARTY.md`.
