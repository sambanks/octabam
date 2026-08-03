# ChonVerb — the custom reverb

A four-line FDN reverb. It now ships as **ChonVerb**, one of the three effects
on the shared send bus (`BUS.md`), running on the FX2 slot of any track in a
bank. Built by `tools/build_bus.py`; source `dsp/reverb_server.asm`.

> **The old standalone DARK REV replacement is retired.** Earlier builds
> (`dsp/reverb88.asm` via `tools/build_reverb.py`) replaced stock DARK REV in
> place, inheriting its descriptor and knob labels. That is no longer the
> product and is not being maintained — ChonVerb has its own cloned descriptor,
> its own id, and its own knob layout. Where this document still describes the
> old build, it is history; the sections below marked **current** are not.

> **Voicing is placeholder.** The structure below is real and hardware-proven,
> but the parameter defaults were chosen to be obviously audible for debugging,
> not because they sound good. Voicing is the live work — see "Planned design"
> at the end.

For how the DSP subsystem works — boot, payload format, the dispatcher ABI,
the allocator, the memory map — see `DSP.md`. For the bus itself see `BUS.md`.
For the reverse-engineering that got us here, `REVERB_LOG.md` (historical).

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
* **Diffusers** — four series allpasses, g = 0.703, taps 997/853/719/613,
  packed to a 1.6:1 ratio so they nearly fill their 1024-word buffers.
* **Tank** — four delay lines with a 4×4 Hadamard feedback matrix. All four
  reads are **interpolated and LFO-modulated**, with the LFO phases crosswise
  (lines 0 and 2 on the inverse triangle, 1 and 3 on the forward) so lines
  sharing tap factors move in opposition.
* **In the loop** — a one-pole low-pass (HI) and a one-pole high-pass (LO)
  per line, so the decay is shaped per band rather than the output EQ'd.
* **In-loop allpasses** — two, 1024 words each, taps 149/223, on lines 0
  and 1. An allpass in the feedback path multiplies echo density on every
  circulation, which is how a smooth tail comes out of finite memory. Note
  the proportion matters: too long relative to the line and it becomes a
  dispersive element, which is what a spring reverb is.
* **Out** — mid/side width, then wet gain added to the dry.

## Parameters (current)

Twelve are addressable per effect — six on page 1, six on page 2 — and the
page-2 mapping was **measured**, not inferred (`DSP.md` §9; two earlier guesses
were wrong and cost hardware flashes). ChonVerb uses nine and leaves three
free.

| page | slot | label | reads | what it does |
|---|---|---|---|---|
| 1 | 0 | TIME | `r6+$0` | feedback → RT60, ~3.7 s to ~17 s |
| 1 | 1 | MOD | `r6+$1` | modulation depth (rate is fixed and slow — see below) |
| 1 | 2 | SIZE | `r6+$2` | scales all four tap lengths |
| 1 | 3 | HP | `r6+$3` | **LO** — high-pass inside the feedback path |
| 1 | 4 | LP | `r6+$4` | **HI** — high-cut damping inside the feedback path |
| 1 | 5 | MIX | `r6+$5` | wet gain |
| 2 | 6 | WIDTH | `r6+$b` | mid/side, 0 = mono |
| 2 | 8 | -DEL | `r6+$d` | dry send into the DELAY bus (`BUS.md`) |
| 2 | 10 | PRE | `r6+$e` | pre-delay |
| 2 | 7, 9, 11 | — | `$c` bits 8-15, `$d` low, `$e` low | **free**, and they are *selects*, not knobs |

**Page-2 slots pair up**: a knob arrives as `value<<16` so it occupies only
bits 16-22, leaving the low bits of the same word as an independent field.
Even slots carry the knob, odd slots a small select — which is what the three
free slots are, and what a MODE control should use.

**PRE lives on `$e`, not `$c`.** `$c`'s knob field is driven by display slot 6
but our WIDTH already reads that value at `$b`; nothing drives `$c` in a way
PRE could use. Stock DARK reads *its* pre-delay from `$c`, which is why older
builds did — but no page-2 slot reaches `$c` usefully, so PRE was dead until
it moved. Do not "fix" this back.

## Memory layout

Each FX2 instance is given 16,384 words. The reverb uses 0x3809 of them:

| offset | size | what |
|---|---|---|
| `base+0x0000` | 4 × 2048 | tank lines, taps 1979/1693/1447/1237 scaled by SIZE |
| `base+0x2000` | 4 × 1024 | input allpasses, taps 997/853/719/613 |
| `base+0x3000` | 2048 | pre-delay |
| `base+0x3800` | 2 × 1024 | in-loop allpasses |

**All persistent state lives in the r7 block**, which is per-instance and
survives between calls — `$82` is the warm-up counter (tagged
`$2c0000 | count`), `$83` the tank phase, and `$10..$61` the working set
including the four LFO phases and the one-pole states. There is no Y state
block; it was round-tripped needlessly until v74.

## Planned 32K re-layout (not yet done)

`BUS.md` allocates each server **32,768 words**, but the layout above uses only
16,384 — half the allocation is unused. `DSP.md` §7c's high-X region was probed
and is not real, so 32K is the hard ceiling; taking it is the whole remaining
memory gain. Target:

| offset | size | what | changes from now |
|---|---|---|---|
| `base+0x0000` | 4 × 4096 | tank lines | modulo `$7ff` → `$fff`; line bases 0/`$1000`/`$2000`/`$3000` |
| `base+0x4000` | 4 × 2048 | input allpasses | bases `$4000`/`$4800`/`$5000`/`$5800`; `m5` `$3ff` → `$7ff`; every `n5` becomes `2048 - 2*tap` |
| `base+0x6000` | 4096 | pre-delay | `m6` `$7ff` → `$fff`; PRE scale `v*16` → `v*32` (0–93 ms) |
| `base+0x7000` | 2 × 2048 | in-loop allpasses | base `$3800` → `$7000`, spacing `$400` → `$800` |

**The tank tap constants do NOT change.** They are stored as fractions of the
line length (`$3DD800` = 1979/2048), so with 4096-word lines the same fraction
yields 3958 samples — the character scales intact and only the modulo and line
spacing move.

Also required: the warm-up clear covers the whole allocation, so `asl #$6`
(×64) → `asl #$7` (×128) and `do #64` → `do #128`, keeping 256 blocks × 128 =
32,768. And the saved-phase mask (`$7ff`, guarding the two-track freeze) →
`$fff`.

**Care needed:** `$7ff`, `$800` and `$1000` each appear in *several unrelated
roles* in this file — line modulo, pre-delay modulo, line spacing, phase mask.
Blind search-and-replace will silently corrupt it. Change them by role, then
verify with an impulse test that the tail lengthens and stays stable, and check
guard-clean under `-dirty`.

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
python3 tools/build_reverb.py dsp/reverb88.asm      # patches both payloads
EFT_EMIT_CONTAINER=out/elek_v88.bin \
  vendor/elektron-firmware-tool/elektron-firmware-tool \
  -i downloads/extracted/OCTATRACK_OS1.40C.syx -c 3 out/mainos_reverb.bin \
  -V MAXOLYDIAN -o out/OCTATRACK_OS1.40C_V88.syx
python3 tools/make_bin.py out/elek_v88.bin -o out/OCTATRACK_V88.bin
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

**Pack the buffers.** Both the tank lines and the input diffusers were
allocated equal power-of-two buffers but given taps spanning a 2.1:1 and
2.7:1 ratio, so roughly 40% of the delay memory was never read. Tightening
both to ~1.6:1 recovered it for nothing — no cycles, no memory, no loss of
instances — and was worth more than any other single change of the voicing
pass. **When a design allocates equal buffers for unequal contents, check
the utilisation.**

**Input diffusion and in-loop diffusion are not interchangeable.** Moving
input allpasses into the loop (v87) improved mode spacing but doubled the
early crest factor: the input chain smooths the attack, the in-loop chain
thins the modes. Pack both; do not trade one for the other.

**Averaging more tank lines into each output does not help** (v89). The
lines share a feedback matrix, so they are not independent; orthogonal
4-line output taps concentrated energy rather than smoothing it, and gave
no stereo benefit over disjoint 2-line pairs.

**Change one thing per flash.** Between v77 and v83 five things changed and
the result was worse in a way that could not be attributed. The recovery was
to reflash v77, confirm the baseline, and move one variable at a time.

## Planned design (agreed, not yet built)

**One FDN engine with a MODE select**, covering standard characters *and* the
largest space this hardware supports — rather than choosing between them. The
three free page-2 selects exist precisely for this; MODE is the obvious first.

* **Standard characters**: room / plate / hall, in the spirit of a Chase Bliss
  CXM 1978. Comfortably within budget — these want density, not length.
* **Big mode**: **Valhalla-flavoured, not Blackhole.** Deliberate: Blackhole's
  character comes substantially from raw allocation, and 743 ms is the hard
  ceiling (`DSP.md` §7c — the high X region was probed and is not real).
  Valhalla's large spaces get their scale from long feedback, heavy modulation
  and dense diffusion, which is both achievable here and a match for the FDN
  structure already in place. Expect genuinely large and smooth; not infinite.

MODE should reconfigure tap lengths, diffusion depth, damping and modulation
together — not merely rescale SIZE.

**Order of work:**
1. The 32K re-layout above — half the allocation is unused, so this is free
   headroom and tells you by ear how far the hardware actually goes.
2. Measure real cycle cost with both effects live. Every figure taken so far
   has been dominated by warm-up and is meaningless; `DSP.md` §12's rule
   (measure, don't guess) applies.
3. Then design the modes against what steps 1 and 2 reveal.
