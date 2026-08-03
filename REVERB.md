# The custom reverb

A four-line FDN reverb that replaces DARK REV on the Octatrack's DSPs. It
runs on **all eight tracks simultaneously**.

Current build: **`dsp/reverb84.asm`** → `out/OCTATRACK_V84.bin`.
341 cycles/sample, 1098 words of program memory.

> **Voicing is in progress and is the live work.** The structure below is
> settled; the tuning is not. See "Tuning: what is known" at the end — it
> records several results that cost hardware flashes to learn and are not
> obvious from the code.

For how the DSP subsystem works — boot, payload format, the dispatcher ABI,
the allocator, the memory map — see `DSP.md`. For the reverse-engineering
that got us here, see `REVERB_LOG.md` (historical).

---

## Signal path

```
in ─► pre-delay ─► 4 series allpasses ─► ┌─ FDN tank ──────────┐ ─► width ─► mix ─► out
        (PRE)        (input diffusion)   │ 4 lines, modulated  │
                                         │ 4x4 Hadamard        │
                                         │ HI damping          │  all inside the
                                         │ LO cut              │  feedback loop
                                         │ 2 in-loop allpasses │
                                         └─────────────────────┘
```

* **Pre-delay** — up to 2048 samples (46 ms), modulo buffer on r6.
* **Diffusers** — four series allpasses, g = 0.703, taps 907/673/487/331
  (20.6/15.3/11.0/7.5 ms). Deliberately long: density has to come from
  diffusion because four tank lines alone read as discrete echoes.
* **Tank** — four delay lines with a 4×4 Hadamard feedback matrix. All four
  reads are **interpolated and LFO-modulated**, with the LFO phases crosswise
  (lines 0 and 2 on the inverse triangle, 1 and 3 on the forward) so lines
  sharing tap factors move in opposition.
* **In the loop** — a one-pole low-pass (HI) and a one-pole high-pass (LO)
  per line, so the decay is shaped per band rather than the output EQ'd.
* **In-loop allpasses** — two, 1024 words each, taps 401/601, on lines 0
  and 1. An allpass in the feedback path multiplies echo density on every
  circulation, which is how a smooth tail comes out of finite memory. Note
  the proportion matters: too long relative to the line and it becomes a
  dispersive element, which is what a spring reverb is.
* **Out** — mid/side width, then wet gain added to the dry.

## Parameters

The UI labels are DARK REV's, inherited with its descriptor. Several do not
describe what we do with the slot — the mapping below is what matters.

| slot | UI label | what it does |
|---|---|---|
| `$0` | TIME | feedback → RT60, measured ~3.7 s to ~17 s |
| `$1` | MOD | **MOD** — modulation depth only (rate is fixed, see below) |
| `$2` | SIZE | **SIZE** — scales all four tap lengths, 627–1543 samples |
| `$3` | HP | **LO** — high-pass inside the feedback path |
| `$4` | LP | **HI** — high-cut damping inside the feedback path |
| `$5` | MIX | wet gain |
| `$b` | BAL | **WIDTH** — mid/side, 0 = mono |
| `$c` | PRE | pre-delay, 0–46 ms |
| `$d` | MONO | **DEAD.** Confirmed on hardware: this knob does nothing. `$d` is host-side, not a parameter. Not read. |
| `$e` | MIXF | **unused** — a host-owned boolean, not a continuous control |

Page-1 names are rewritten by `build_reverb.py` (the descriptor's name
strings are plain data). Page 2 is deliberately NOT renamed: its descriptor
order conflicts with the probed `r6` mapping, and renaming against a mapping
known to be wrong would put right names on wrong knobs.

**Stock's own reads are the authority on what a slot means.** Reading PRE from
`$e` (a flag word stock only `btst`s) cost a hardware flash; `$c` is stock's
real pre-delay slot.

## Memory layout

Each FX2 instance is given 16,384 words. The reverb uses 0x3809 of them:

| offset | size | what |
|---|---|---|
| `base+0x0000` | 4 × 2048 | tank lines, taps 1567/1249/977/733 scaled by SIZE |
| `base+0x2000` | 4 × 1024 | allpasses, taps 907/673/487/331 |
| `base+0x3000` | 2048 | pre-delay |
| `base+0x3800` | 2 × 1024 | in-loop allpasses |

**All persistent state lives in the r7 block**, which is per-instance and
survives between calls — `$82` is the warm-up counter (tagged
`$2c0000 | count`), `$83` the tank phase, and `$10..$61` the working set
including the four LFO phases and the one-pole states. There is no Y state
block; it was round-tripped needlessly until v74.

## Register map inside the sample loop

Every address register is committed; this is the constraint any change works
against.

| reg | use | modulo |
|---|---|---|
| r0 / n0 | audio buffer, stereo stride | linear |
| r1–r4 / n1–n4 | tank line pointers; nK = read offset | m1–m4 = `$7ff` |
| r5 / n5 | allpass pointer; n5 = 1024−tap, rewritten per allpass | m5 = `$3ff` |
| r6 / n6 | pre-delay pointer and offset | m6 = `$7ff` |
| r7 | state block | — |
| n7 | frame count, from the dispatcher | — |

## Build, verify, flash

```sh
python3 tools/build_reverb.py dsp/reverb84.asm      # patches both payloads
EFT_EMIT_CONTAINER=out/elek_v84.bin \
  vendor/elektron-firmware-tool/elektron-firmware-tool \
  -i downloads/extracted/OCTATRACK_OS1.40C.syx -c 3 out/mainos_reverb.bin \
  -V MAXOLYDIAN -o out/OCTATRACK_OS1.40C_V84.syx
python3 tools/make_bin.py out/elek_v84.bin -o out/OCTATRACK_V84.bin
```

Then copy the `.bin` to the **root** of the CF card (one only), and on the
device: PROJECT → OS UPGRADE → YES.

Before flashing, always run the emulator check — two instances, poisoned
state words, dirty memory, and a nonzero split:

```sh
dsp_host -mem <payload_A.mem> -init 1252 -proc 126d -inst 2 -r7 2,5 \
         -guard 16384 -dirty 0xBEEF -split 5 -blocks 600 -in imp.raw
```

It must report **guard clean** and no hang. For a pure optimization, also
diff the output against the previous build: it should be **bit-identical**,
and any difference is a bug. See `DSP.md` §6b for the harness reference and
its traps.

## What it takes to run on all eight tracks

Two things, both of which were once believed impossible:

* **The external memory region.** Eight tracks need eight 16K FX2 slots;
  internal Y supplies only four. The other four live at `Y:0x30000–0x3FFFF`,
  64K of external SRAM shared between the two DSPs and partitioned between
  the payloads. An effect that refuses those bases silently gives up half
  the machine.
* **Fitting four instances per DSP inside the cycle budget.** The engine was
  432 cycles/sample and four instances froze the chip; a density pass took it
  to 297. Most of the win was letting the AGU do address arithmetic instead
  of doing it by hand.

## Known limits and open work

**The tank rings**, and this is a memory limit rather than a bug. An FDN
sounds smooth when its modes overlap — mode spacing is `sr / total_delay`,
mode bandwidth is `2.2 / RT60`. At SIZE max the tank holds 4,493 samples, so
spacing is 9.8 Hz against a bandwidth of 0.55 Hz at a 4-second decay: an
overlap of 0.06, roughly 20× too sparse. A 4-second decay would want ~1.8 s
of delay memory; an instance is given 0.37 s.

Measured confirmation: spectral flatness rises monotonically with SIZE
(0.0014 → 0.0066 from SIZE 32 to 127) and with shorter decay. Modulation
smears the modes and is the only structural fix at this budget — worth ~9×
flatness — but it saturates.

**Practical consequence: run SIZE high.** It is not just a bigger space, it
is a measurably smoother one.

Two levers exist for going further, and they are independent:

1. **Spend freed cycles on more delay lines.** The density pass left
   headroom that did not exist before; v84 uses 341 of it.
2. **Patch the allocator table at `X:0x255`** — it is loaded data, editable
   exactly like the dispatch tables `build_reverb.py` already writes — to
   trade instance count for tank size: 8 modest, 4 large (2 × 32K per DSP),
   or 2 very large (1 × 45K, also taking the FX1 region). Doubling the delay
   is worth roughly 3× the smoothness. Repoint the sacrificed slots at the
   dead region above `0xC000`, where writes are discarded, so a stray effect
   is silent rather than destructive.

Smaller items: SHVG's range wants calibrating by ear; MIXF (`$e`) is dead and
likely to stay so; and there is an unexplained emulator-only divergence
between one and two instances under a nonzero split.


## Tuning: what is known

Several of these cost a hardware flash each and none are obvious from the
code. The measurements come from a spectral-flatness harness (see below for
its limits).

**Seasickness is RATE, not depth.** Pitch shift is `-d(delay)/dt`, so it
depends on how fast the delay moves, not how far. 63 samples at 2.84 Hz is
~28 cents of vibrato and sounds seasick; the same 63 samples at 0.25 Hz is
~2.5 cents and is inaudible. Depth is what smears the modes. Coupling MOD
to both — which v64 did as a workaround for an inaudible control — means
turning it up adds wobble faster than it adds smearing. **Keep the rate
slow and fixed; let MOD move depth alone.**

**Small SIZE is inherently bad.** At the original floor the whole tank was
566 samples: a mode spacing of 78 Hz, which is a comb, not a reverb. The
floor is now `f = 0.4` so the bottom of the knob is ~1,810 samples at 24 Hz.
Confirmed by ear ("smallest size sounds worst") before it was fixed.

**Modulation must never reach zero.** A completely static tank rings — its
modes are audible as pitched resonance. Some residual sweep is needed at
MOD=0.

**The interpolation fraction rule:** integer part via `asl #n`, fraction
masked with `2^(24-n)-1` and shifted by **n-1**, never by `n`. Shifting by
`n` pushes the top half past `0x800000`, where a 24-bit fractional reads
NEGATIVE, and the interpolation jumps backwards once per integer LFO step —
heard as a fast flutter. This bug was live from v72 to v79.

**That bug was also doing something useful**, which is the uncomfortable
part: it is a noise source, and interpolation dither is a real technique for
breaking up delay-line artifacts. Every build the user liked had it. Fixing
it was correct and immediately exposed ringing that had been masked. If the
tail needs more smearing than slow deep modulation provides, *deliberate*
randomisation is the principled replacement.

**Spectral flatness cannot tell diffusion from distortion.** It rewards
broadband noise, so it ranked the flutter builds highly and dropped when the
flutter was fixed. It is useful for comparing structural changes, and
misleading for anything that adds noise. **When it and the ear disagree, the
ear is the measurement.** Early crest factor is the better companion metric.

**In-loop allpass proportion matters.** An allpass inside the feedback loop
is a dispersive element — the mechanism spring reverbs are built on. At 15%
of the line it feeds it is diffusion; ours ran 26–64% and were suspected of
producing a spring/plate ring. Removing them was tested (v82/v83) but
bundled with other changes, so the result is not clean.

**Change one thing per flash.** Between v77 and v83 five things changed and
the result was worse in a way that could not be attributed. The recovery was
to reflash v77, confirm the baseline, and move one variable at a time.
