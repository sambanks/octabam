# CF PROBE — measuring the ColdFire's headroom

The question: **how much of each audio frame can the ColdFire give to a new
machine** — a Braids port, a Pickup-machine descendant — before the rest of
the firmware starves? Nothing local can answer it. The emulator runs the
EMAC exactly and at no fixed rate, so "it keeps up in Unicorn" is worthless
(same lesson as the DSP burn sweep). This module is the one flash that
answers it, and it answers two numbers:

- **what the per-frame delay routine already costs**, as a fraction of the
  frame, and
- **where the rest of the system gives out** when that routine is made
  heavier, and what gives out first.

## What is in the image

One cave, floated behind the descriptor clones, with two entry points:

| | |
|---|---|
| `+0x000` | hooked from `0x40004b12`, the frame routine's only call site, inside the audio interrupt at IPL 5. The cave calls `0x400031a0` itself, reads DMA timer 3 before and after, runs the burn, replays the displaced `move.w #0x2700,%sr`, returns |
| `+0x100` | a display formatter registered on **HELLO WORLD's GAIN** (`FormatterReg(offset=0x100)`) |

Per frame: `t0 ; routine ; t1 ; burn ; t2`, giving `routine = t1−t0`,
`total = t2−t0`, `period = t0 − last t0`. Frames whose period is implausible
(first frame, a counter reset, a stall) are discarded. Sums run over
1,024-frame windows (~0.37 s) and are published at the end of each, so a
reading is never stale by more than a window and no sum overflows.

The clock is DMA timer 3 at the internal bus clock, free-running 32-bit
(`DTMR3 = 0x000b`, `DTRR3` never written). ✅ Read from the disassembly
(`0x400209c0`); DMA timer 2's one-second reference of 132,000,000 ticks
(`0x40040438`) makes the bus clock **132 MHz** 🟡 inferred — and one
16-sample frame **47,891 ticks**. The PERIOD readout is the check.

The burn is the **crossfader**: `iterations = fader × 128`, a six-instruction
loop, inside the measurement, so the readout reports the burn's true cost.
Fader 0 is a pure measurement. ⚠️ The fader also crossfades scenes: sweep on
a project without scene locks, or expect the sound to change with it.

## The readout — HELLO WORLD's GAIN, by band

| GAIN | prints | meaning |
|---|---|---|
| 96–127 | `t62` | mean **total** busy (routine + burn), % of the period |
| 64–95 | `r25` | mean **routine** busy, burn excluded |
| 32–63 | `x83` | the **worst single frame** in the window, total, % |
| 0–31 | `47891` | mean period in ticks |
| any | `-` | no window published yet |

The panel redraws a label when the knob moves, so **nudge GAIN to refresh**.
GAIN is also HELLO WORLD's gain: bands below 96 attenuate that track (at
64 it is −6 dB). A probe image is not a performance image.

## Procedure

```bash
REMIX=cfprobe make image          # the rig + HELLO WORLD + CF PROBE
.venv/bin/python3 tools/verify_cfprobe.py   # 22 checks, emulator-driven
```

Flash per `docs/FLASHING.md`. Load the rig project (`ot_project.py rigproj`)
or a real set. Put **HELLO WORLD** on any track's FX2 and leave GAIN at 127.

**1. At rest, fader 0.** Read all four bands and write them down.

- PERIOD ≈ **47,891** confirms per-frame at 132 MHz. A clean multiple
  (95,782; 766,256) means the interrupt runs per that many frames — still
  a valid measurement, but the frame is bigger than assumed. Anything else
  falsifies the bus-clock inference; the ratios below stay right.
- `t` = `r` at fader 0 (no burn). If not, the probe is wrong, stop.
- `r` is **the routine's cost today**. `x` is its worst frame; if `x` is far
  above `r`, the routine has an occasional expensive path (DMA reprogramming
  on a time change is the obvious one — move a delay TIME and watch `x`).
- `-` after ten seconds means every frame is being discarded: the hook is
  not running per frame at all. That is a finding, not a fault; the stubbed
  emulator run proves the code, the period guard is 1,048,576 ticks.

**2. The sweep.** Play the full set: eight tracks, stock DELAYs on, a sample
streaming from the card, MIDI clock in, and scroll the UI while it runs.
Raise the fader **8 steps at a time**. At each step nudge GAIN and record
`t`, `x`, and the first symptom, in this order of likelihood:

| symptom | what it says |
|---|---|
| the UI lags or stops redrawing | the RTOS time slice is starved — the probe runs above it |
| a streaming sample stutters or stops | card streaming starved — the field failure that matters |
| MIDI clock drifts, notes late | the level-4 MIDI framer is starved (it sits below IPL 5) |
| audio crackle or dropout | audio DMA is at or below level 5 — every added cycle is paid by audio directly. The most important finding if it comes first |
| a hang | the wall was a cliff; note the fader, power-cycle |

**3. The number.** Headroom for a ColdFire machine, per frame:

```
headroom = t(first symptom) − r(rest)      in % of the period
ticks    = headroom × period               bus-clock ticks per frame
```

Core cycles are ~2× the ticks 🟡 (MCF5445x core clock = 2× internal bus
clock — inferred from the family's clock tree, unmeasured). Braids' heavy
models render a 24-sample block in ~60% of a 72 MHz Cortex-M3's time; that
is the comparison to price against.

## What would falsify what

| claim | falsified by |
|---|---|
| the hook runs once per 16-sample frame | PERIOD not ≈ 47,891 |
| the bus clock is 132 MHz | PERIOD ≈ 47,891 × k for no integer k |
| the routine is cheap and steady | `r` above ~30, or `x` ≫ `r` at rest |
| the RTOS gives before audio | audio crackle before UI lag |
| the counter is never zeroed under us | can't be seen directly; a window with an absurd PERIOD is one that ate a reset |

## What is deliberately not here

- **No per-task attribution.** The probe measures the one routine and what
  the whole system tolerates above it. Which task starves is read off the
  symptom, not a counter.
- **No idle-loop counter.** Instrumenting the scheduler's idle path would
  give whole-CPU headroom, but the hook site would be in the RTOS core and
  the failure mode of getting it wrong is a dead unit. The burn sweep gets
  the same number from the other side.
- **TEMPOCAVE=replay** does not apply: the displaced jsr is pc-relative and
  the build refuses to replay it.
