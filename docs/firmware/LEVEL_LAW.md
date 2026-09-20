# The level law: why 127 is not unity

OS 1.40C. A level parameter of 127 does not give unity gain: the raw
0..127 integer is handed to the DSP unscaled, squared there, and evaluated
against an implicit denominator of 128 — `gain = (L/128)²`, which at 127
is `(127/128)² = 0.98443603515625` = **-0.1362 dB**. Every level stage a
signal passes through costs another one. This is what "127" means, not a
calibration constant or a table.

Read out of the binary and off hardware by Bryan T (21 Sep 2026,
`EXTERNAL.md` §13; hardware captures his). Nothing below has been run
under the port.

Status key as `CHIP.md`: ✅ measured (hardware or read off the firmware) ·
🟡 inferred.

## 1. What was measured ✅

T1 playing a steady tone, T1 MAIN = 127, T1 CUE = 127, MAIN OUT = 127; MAIN
fed T2's record buffer, CUE fed T3's, T1 fed T4's directly (no level
stage — the unity reference). 24-bit WAV, bit-exact, no converters:

| path | coefficient | dB | level stages |
|---|---|---|---|
| direct track tap | 1.0 | 0 | 0 |
| CUE | 0.984436035 (32258/32768) | -0.1362 | 1 |
| MAIN | 0.968964 (31751/32768) | -0.2738 | 2 |

MAIN carries two stages (T1's MAIN level, then MAIN OUT); CUE carries one.
Both buses are pure scalars: `out[n] = round(in[n]·k) + c` reproduces the
captures to 1-2 LSB with no filtering or drift, and every `k` is an exact
multiple of 256 in 24-bit terms.

Sweeping CUE confirms the square law against `(L/128)²`, exact at 96 and
127 (2 LSB of a 15-bit scale high at 32 and 64 — open, §3).

## 2. The code path

**ColdFire: the raw integer crosses untouched ✅.** The per-frame
dispatcher at `0x4000d2a0` reads two bytes (`0x8000005e`, `0x8000005f`),
sign-extends and stores them into the per-track DSP record at `X:0x080`
words `0x32`/`0x33` — `0x4000d2c6`-`0x4000d2da`. No scaling. The encoder
handlers at `0x40066b64`/`0x40066ba8` clamp 0..127 and mirror to
`0x100b14be`/`0x100b14bf` for persistence. Which byte is MAIN and which is
CUE is 🟡 unresolved.

**DSP: shift and square ✅.** In the summing mixdown (`P:0x292`-`0x3a0`,
module record at `P:0x2bf`), immediately before the coefficient loop
(`P:0x2f4`-`0x2fb`): each of `x:(r0+$32)` and `x:(r0+$33)` is shifted left
16 (`L/128` as a fraction) and squared against itself (`mpy x0,x0`), giving
`x1`/`y1` — one coefficient per bus, applied by the 16-sample loop at
`P:0x2ff`-`0x30a` to two separate stereo destinations. 🟡 `mpy` in
fractional mode yields `2(L/128)²` in the accumulator; a scale-down
transfer to `x1` would give exactly `(L/128)²` as measured, but the status
register bits were not checked, so this is the leading explanation rather
than an established one.

## 3. Open

- Which of `0x8000005e`/`0x8000005f` is MAIN and which is CUE.
- The +1/32 excess at CUE 32 and 64 (absent at 96, 127): candidates are the
  loop's other term (`seed + x1·y0`, `y0` from `Y:0x280`, neither read) or
  sweep-direction state (a first capture at 127 landed low, later ones
  exact) — untested.
- MAIN measures 3 counts under two stacked CUE stages (31751 vs 31754),
  plausibly the same cause.
- The pan table at `X:0x6c00` (128-entry quarter sine, read forwards and
  backwards with a one-index offset for constant-power pan — not level)
  is asymmetric at centre by -0.1079 dB; unrelated to the level law, not
  confirmed by measurement.

## 4. Consequences

The control is far more aggressive at the bottom of its range than a
linear reading suggests: 64 is a quarter amplitude, not a half. For
feedback/sound-on-sound work, a loop closed through one level stage at 127
decays by 0.1362 dB per pass — if a loop is growing, the gain above unity
is elsewhere in the chain. `tools/harness/mixer.py`'s per-track LEVEL
(`docs/remixer/HARNESS.md`) is the same `(L/128)²` law measured under the
port; this note is the first measurement of MAIN/CUE, which that harness
does not model.

## 5. No gain table ✅

All four measured coefficients, and the underlying linear values `T[64] =
16392`/`T[32] = 8200`, were searched for across the whole image (six
encodings, five strides) and directly in the DSP data blocks at `X:0x438`,
`X:0x1cd9`, `X:0x4840`, `X:0x6c00`. Nothing. The coefficient is computed.

## 6. Reference

| thing | address |
|---|---|
| level bytes (MAIN/CUE, one per stage) | `0x8000005e`, `0x8000005f` |
| SRAM mirrors | `0x100b14be`, `0x100b14bf` |
| encoder handlers writing them | `0x40066b64`, `0x40066ba8` |
| dispatcher copying them into the DSP record | `0x4000d2c6`-`0x4000d2da` |
| DSP record words they land in | `X:0x080` record, `0x32`/`0x33` |
| the squaring | DSP `P:0x2f4`-`0x2fb` |
| coefficient loop consuming `x1`/`y1` | DSP `P:0x2ff`-`0x30a` |
| summing mixdown function | DSP `P:0x292`-`0x3a0` |
| constant-power pan table | DSP `X:0x6c00` (and `X:0x6d02`, reversed) |
