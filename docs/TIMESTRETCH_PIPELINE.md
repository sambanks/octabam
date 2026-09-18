# Octatrack Timestretch Pipeline — Verified from Assembly

**Date:** 2026-07-31
**Source:** ColdFire MCF5445x disassembly of `Voice::PlaybackProcess` @ 0x40007d2c

## Retracted (18 Sep 2026)

**Every address in this document is 0x400 low.** This analysis assumed the
MAIN OS loads at `0x40000000`; it loads at `0x40000400`
(`docs/firmware/REPITCH.md`). Add `0x400` to any address here before using
it. Also retracted: voice `+0x18` below, called `channel_count`, is not a
channel count -- it is the resolved TSTR value (`docs/firmware/REPITCH.md`'s
TSTR resolution section). `docs/firmware/REPITCH.md` is the current,
✅-marked source for REPITCH; treat this document as superseded by it.

## Architecture

The timestretch is implemented as a **phase accumulator** in `Voice::PlaybackProcess`. The ColdFire computes stretched audio positions and sends them to the DSP. The DSP receives already-stretched audio — timestretch is ColdFire-side.

## Voice Structure (accessed via A2 register)

| Offset | Size | Name | Role |
|--------|------|------|------|
| +0x00 | 1 | state | Voice state (0=inactive) |
| +0x03 | 1 | overflow_flag | Overflow indicator |
| +0x06 | 1 | sample_format | Sample format |
| +0x07 | 1 | stereo_flag | Stereo flag |
| +0x14 | 1 | mode | Playback mode (0x01=active, 0x04=flex) |
| +0x15 | 1 | direction | Direction flag (-1=backward) |
| +0x17 | 1 | loop_mode | 0=once, 1=fwd loop, 2=pingpong |
| +0x18 | 1 | channel_count | Channel count (0=mono path, nonzero=stereo/timestretch) |
| +0x19 | 1 | prev_direction | Previous direction value (triggers phase re-init on change) |
| +0x1a | 1 | playback_state | 0=idle, 1=playing, negative=stereo processing |
| +0x1b | 1 | safety_check | Safety boundary check flag |
| +0x1c | 1 | overflow_pending | Overflow pending flag |
| +0x1d | 1 | frame_complete | Frame completion marker (0xff = initial) |
| +0x1e | 1 | format_index | Sample format jumptable selector (0–3) |
| +0x20 | 1 | flags_b | Signed flags byte (checked for < 0 to select param source) |
| +0x24 | 2 | direction_value | 1 or -1 (abs used in pitch computation) |
| +0x30 | 4 | loop_end | Loop end position |
| +0x34 | 4 | loop_start | Loop start position |
| +0x3c | 4 | loop_end_alt | Alternate loop end (for pingpong) |
| +0x40 | 4 | position | Current playback position |
| +0x44 | 4 | position_accum | **Phase accumulator (position)** — incremented by phase overflow |
| +0x48 | 4 | read_ptr | Read pointer |
| +0x4c | 4 | write_ptr | Write pointer |
| +0x50 | 4 | buffer_size | Buffer size |
| +0x60 | 4 | safety_limit | Safety boundary check value |
| +0x78/0x7c | 8 | phase | **64-bit phase accumulator** — decremented by pitch_ratio per sample |
| +0x80/0x84 | 8 | pitch_ratio | **64-bit pitch ratio — CONTROLS SPEED** — written at 0x40007c7e |
| +0x88/0x8c | 8 | modulo | **64-bit phase wrap modulo** — written at 0x40007ca8 |
| +0x90 | 4 | frame_count | Frame counter |
| +0x94 | 4 | frame_start_copy | Copy of frame start pointer |
| +0x98 | 4 | frame_end_copy | Copy of frame end pointer |
| +0x9c | 4 | read_limit | Read boundary limit |
| +0xa0 | 4 | read_base | Read base pointer (read_ptr + 0xa00) |
| +0xa4 | 4 | status_word | Status/flags (0xffffffff = initial, 0 = reset) |

## Phase Accumulator (verified at 0x4000848e)

The phase accumulator is a 64-bit signed value (voice+0x78/0x7c) that drives sample
position advancement. Per output sample, it is decremented by the 64-bit pitch ratio.
When the result goes negative, the integer position advances and the modulo is added
back. The inner loop (`0x40008498–0x400084a2`) repeats the modulo addition until the
phase is non-negative, supporting pitch ratios larger than the modulo (faster playback).

```asm
; Voice::PlaybackProcess @ 0x4000848e — forward direction phase accumulator
4000848e: bra.b  skip_entry        ; skip first iteration test
40008490: sub.l  (0x84,A2), D1    ; phase_lo -= pitch_ratio_lo
40008494: subx.l D2, D0          ; phase_hi -= borrow
40008496: bge.b  skip             ; if phase >= 0, skip
40008498: addq.l #1,(0x44,A2)    ; position++
4000849c: add.l  (0x8c,A2), D1    ; phase_lo += modulo_lo
400084a0: addx.l D3, D0          ; phase_hi += carry
400084a2: blt.b  loop             ; while phase < 0, add modulo again
400084a4: subq.l #1, D4          ; sample_count--
400084a6: bge.b  loop             ; loop for all output samples
```

The backward direction path (at `0x40008a42`) uses the same structure but decrements
position (`addq.l #-1`) instead of incrementing.

### Speed encoding

| Speed | pitch_ratio (hi:lo) | modulo (hi:lo) | Behavior |
|-------|---------------------|----------------|----------|
| 1.0x  | `0x00000000:0x00000001` | `0x00000000:0x00000001` | Phase wraps every sample |
| 0.5x  | `0x00000000:0x00000001` | `0x00000000:0x00000002` | Phase wraps every 2 samples |
| 2.0x  | `0x00000000:0x00000002` | `0x00000000:0x00000001` | Phase wraps twice per sample (inner loop) |
| 1.5x  | `0x00000000:0x00000003` | `0x00000000:0x00000002` | Phase wraps 1.5× per sample |

For case 0 of the switch (fixed ratio), modulo = 0x4000 (16384), so the default
1.0x pitch ratio yields 1/16384 position advances per output sample — this is the
timestretch base rate before the DSP-side time-to-frequency mapping scales it.

## Data Flow (Verified)

```
g_b_voice_trk (0x800065bc)          voice+0x14 (mode)
         │                                │
         └──────────┬─────────────────────┘
                    │
                    v
         Mode selector D3 (0–4)
                    │
                    v
         Switch table @ 0x40007bac
         ┌──────────┼──────────────────┐
         │ case 0   │ case 1  ...case 4│
         │ D2=0x4000│ D2=param<<14     │
         │ A0=1     │ A0=base_pitch    │
         │ A1=1     │ A1=dir×base      │
         └──────────┼──────────────────┘
                    │
                    v
         32×32→64 multiply @ 0x40007c5c
         D0 = A1 (pitch factor) × D1 = abs(dir) × base_pitch
         result >>= 1
                    │
                    v
         voice+0x80/0x84 = pitch_ratio (64-bit fixed-point)
                    │
                    v
         Phase accumulator loop (per output sample):
           phase -= pitch_ratio
           if phase < 0:
               position++        ; voice+0x44
               phase += modulo   ; voice+0x88/0x8c
                    │
                    v
         Read pointer = position + interpolation
                    │
                    v
         Sample format dispatch (jumptable @ 0x40008352/0x400083b6)
         Index = voice+0x1e (0–3)
         Converts raw sample to 32-bit stereo output
                    │
                    v
         Sample output -> DSP via FIFO
```

## Pitch Ratio Computation (Verified 2026-07-31)

### Where the ratio is written

**Function:** `Voice::PitchRatioCompute` @ `0x400079da` (call chain: caller → Voice::PitchRatioCompute → Voice::PlaybackProcess)

| Write | Address | Instruction | Target |
|-------|---------|-------------|--------|
| pitch_ratio_hi | `0x40007c7e` | `move.l D0, (0x80,A2)` | voice+0x80 |
| pitch_ratio_lo | `0x40007c82` | `move.l D1, (0x84,A2)` | voice+0x84 |
| modulo_hi | `0x40007ca8` | `move.l D1, (0x88,A2)` | voice+0x88 |
| modulo_lo | `0x40007cac` | `move.l D2, (0x8c,A2)` | voice+0x8c |

### Mono path (voice+0x18 == 0)

When `channel_count` is 0, the function sets identity values directly:
```c
voice+0x80 = 0;  voice+0x84 = 1;  // pitch_ratio = (0, 1) = 1.0x
voice+0x78 = 0;  voice+0x7c = 0;  // phase = 0
voice+0x88 = 0;  voice+0x8c = 1;  // modulo = (0, 1)
```
Then jumps straight to Voice::PlaybackProcess (phase accumulator consumer).

### Stereo/timestretch path (voice+0x18 != 0)

#### Step 1: Mode selector (D3) computation

The mode selector is NOT a direct TSMODE parameter read. It's computed from `g_b_voice_trk` (global at `0x800065bc`) and voice state:

| Condition | D3 value | Source |
|-----------|----------|--------|
| `g_b_voice_trk >= 0` | `3 - (track == g_b_voice_trk ? 1 : 0)` | Global track assignment |
| `g_b_voice_trk < 0`, voice+0x14 == 4 (flex) | `0` or complex flex lookup | Flex track config at `0x80004f1c` |
| `g_b_voice_trk < 0`, D3 == 1, param+0x11c != 0 | `-1` (i.e., `SNE` → `NEG`) | Effect parameter flag |
| `g_b_voice_trk < 0`, D3 == 2, param+0x120 != 0 | `2` (masked) | Effect parameter flag |

#### Step 2: Switch dispatch on D3 (5 cases)

Switch table at `0x40007bac`, indexed by D3 (0–4, default for ≥5):

| Case | D2 (modulo factor) | A0 (modulo source) | A1 (pitch factor) | Description |
|------|--------------------|--------------------|--------------------|-------------|
| **0** | `0x4000` | `1` | `1` | Fixed ratio, power-of-2 modulo |
| **1** | `param+0x114 << 14` | base_pitch | dir × base_pitch | Effect param 0x114 scales modulo |
| **2** | `param+0x11c << 8` | `0x09B0A000` | dir × base_pitch | Effect param 0x11c, external modulo base |
| **3** | `param+0x120 << 8` | `0x09B0A000` | dir × base_pitch | Effect param 0x120, external modulo base |
| **4** | Per-track flex config | Per-track flex config | Per-track flex config | Complex flex/slice lookup |
| **default** | `1` | `1` | `1` | Identity (1:1 ratio) |

Where:
- `base_pitch` = value at stack offset `-0x50` (computed earlier in the caller)
- `dir` = `abs(voice+0x24)` = |direction| (1 or -1, abs taken)
- `param` = voice params structure at stack `-0x4c`

#### Step 3: 32×32→64 multiply (final ratio computation)

At `0x40007c5c`:
```asm
40007c5c: move.l  A1, D0         ; D0 = pitch factor (from switch)
40007c5e: mac.l   D0, D1, ACC0   ; ACC0 += D0 × D1 (accumulated)
40007c76: mulu.l  D0, D1         ; D0:D1 = D0 × D1 (unsigned 32→64)
40007c7c: asr.l   #0x1, D0       ; D0 >>= 1 (arithmetic shift)
40007c7e: move.l  D0, (0x80,A2)  ; voice+0x80 = pitch_ratio_hi
40007c82: move.l  D1, (0x84,A2)  ; voice+0x84 = pitch_ratio_lo
```

Then the modulo is computed similarly at `0x40007c86`:
```asm
40007c86: move.l  A0, D1         ; D1 = modulo source (from switch)
40007ca0: mulu.l  D1, D2         ; D1:D2 = D1 × D2 (unsigned 32→64)
40007ca6: asr.l   #0x1, D1       ; D1 >>= 1
40007ca8: move.l  D1, (0x88,A2)  ; voice+0x88 = modulo_hi
40007cac: move.l  D2, (0x8c,A2)  ; voice+0x8c = modulo_lo
```

### Phase accumulator initialization (direction change)

When `voice+0x19` (previous direction) differs from D3, the phase is re-initialized at `0x40007cc0`:
```asm
40007cc2: move.l  D2, (0x7c,A2)  ; voice+0x7c = phase_lo
40007cc8: move.l  D1, (0x78,A2)  ; voice+0x78 = phase_hi
40007ccc: move.b  D3, (0x19,A2)  ; voice+0x19 = new direction
```

### Sample format dispatch jumptables

Two PC-relative bra tables inside Voice::PlaybackProcess, indexed by `voice+0x1e` (format_index):

| Table | Base | Direction | Entries |
|-------|------|-----------|---------|
| Forward | `0x40008352` | voice+0x15 ≥ 0 | 4 entries (0–3) |
| Backward | `0x400083b6` | voice+0x15 < 0 | 4 entries (0–3) |

Each entry is a bra target implementing a sample format conversion loop:
- **0**: 24-bit mono → 32-bit stereo (read 3 bytes, clear byte, write 32-bit × 2)
- **1**: 16-bit → 32-bit stereo (read 16-bit, swap, write 32-bit × 2)
- **2**: 16-bit → 16-bit stereo (read 16-bit, write 16-bit × 2)
- **3**: 16-bit → 32-bit stereo (read 16-bit, clear byte, write 32-bit × 2)

### DAT_400aad08 — Pitch scaling table

Referenced at `0x400082f8` in the position-reset path:
```c
uVar8 = (uVar8 & 0xffff) *
        *(ushort *)(&DAT_400aad08 + ((**(ushort **)(stack - 0x48) + 0x80) >> 8) * 2)
        >> 0xe;
```
This is a 256-entry × 2-byte (uint16) lookup table indexed by `(voice_config_word + 0x80) >> 8`.
It scales the pitch by a per-voice coefficient before the final ratio computation.

### Audio::PitchConvert — CONFIRMED DEAD CODE

- **Address:** `0x40020624` (body: 4 bytes — just `lea (-0xc,SP),SP`)
- **Callers:** None (0 xrefs to code or data)
- **What it does:** Clamps a frequency parameter to [720, 7200] Hz, then computes a ratio with 32-bit fixed-point multiply/divide by constant `0x4D85` (19845).
- **Status:** Dead code. The pitch ratio is computed entirely in `Voice::PitchRatioCompute` using the switch table. `Audio::PitchConvert` may be a leftover from an earlier firmware version or an unused API.

### Jumptable at 0x400d1cd0 — Resolution

This is NOT a jumptable of function pointers. The address contains regular ColdFire instructions (moveq, bmi.b, etc.) that are part of a different function's code body. The decompiler incorrectly identified it as an indirect call target due to the expression:
```c
(**(code **)(iVar11 + 0x400d1cd0 + iVar10))()
```
The actual indirect calls in the backward playback path use the same PC-relative bra tables at `0x4000892c` and `0x4000898c` (analogous to the forward tables at `0x40008352`/`0x400083b6`).

## What's Still Unknown

1. ~~Where the pitch ratio lookup table is~~ ✅ **Solved:** Switch table at `0x40007bac` in Voice::PitchRatioCompute
2. ~~How pitch setting (semitones) converts to ratio~~ ✅ **Solved:** 32×32→64 multiply with direction, base_pitch, and effect params
3. The interpolation method (linear? cubic?) — likely in the sample format dispatch loops
4. Whether the DSP does any additional processing on the stretched audio — DSP is separate FIR filter, not involved in timestretch
5. The exact mapping of D3 values 0–4 to TSMODE names (PIPO/NORM/BEAT/ANLG/RTRG) — needs parameter trace

## Files

- `TIMESTRETCH_PIPELINE.md` — This document
- `DSP56300_ANALYSIS.md` — DSP program analysis
- `DSP_FINAL_REPORT.md` — Corrected DSP findings
- `EFFECT_RECORD_STRUCTURE.md` — Effect record layout
