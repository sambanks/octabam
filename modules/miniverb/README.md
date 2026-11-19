# `miniverb` — MINIVERB

A full-rate stereo reverb for FX2, replacing DARK REV. The current v4 voice
was accepted in the local percussion/pluck listening comparison on
20 September 2026.

The goal is a smooth, diffuse reverb within roughly stock spring's processing
budget. VintageVerb was an initial listening reference, not a cloning target.
An eight-delay v3 experiment measured better than v2 but was still rejected
as metallic/ringy. The accepted version spends the budget on **eight allpass
diffusers inside the feedback tank**, four input diffusers, and wider
interpolated modulation of two in-loop diffusers.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | DECAY | 0–127, default 104 | decay |
| 1 | 1 | DAMP | 0–127, default 70 | damping, higher = darker |
| 1 | 2 | MIX | 0–127, default 40 | dry/wet; wet-only auditions use 127 |
| 1 | 3 | MOD | 0–127, default 80 | modulation depth |
| 1 | 4 | RATE | 8 steps, default 2 | modulation speed, 0.34–2.69 Hz |

Input folds to mono; the tank generates stereo. Room geometry is fixed;
there is no separate predelay, freeze or color mode.

## Measured

### RT60 and echo density

The accepted default's eight-second impulse capture gives approximately
**4.62 seconds RT60**, extrapolated from the -5 to -25 dB energy-decay slope.
The normalized 50–100 ms echo-density diagnostic rose from 0.297 (v2) to
0.880; the raw impulse peak fell from 0.0477 to 0.0102 at similar total wet
energy. These describe a less concentrated early response, not a universal
sound-quality score. Listening decided between the candidates.

### The tap pass, 19 November 2026

Bit-identical: `verify_ident.py` with the wider matrix of
sambanks/octabam#1172 (56 renders on MINIVERB's own slot, payload B, a 2 s
run, a knob ramp, stereo, the r7 state after every block) IDENTICAL after
each commit. Cycles a sample from `tools/build/interlock_scan.py` (the core
manual's cycle table and stalls: a model, `docs/contributing/CYCLE_SCAN.md`;
for MINIVERB it reads 8.2 % above the unit's slot cost), every knob at its
maximum, every RATE: **608.8 → 507.7** (13.4 % → 11.2 % of a frame).
Executed instructions a sample 314.6 → 311.6. Words 459 → 446 (`dsp_asm` at
P:$800, as `dsp_forms.py --census` counts them). Not measured
on the unit.

Every tap loaded its offset into `n5` just before its access, so every access
waited 3 cycles for the address register. Each offset now loads right after the
access before it, and the wait overlaps the work between taps: the same
instructions in another order, with nothing between the old and new place
reading `n5`. Beside that: the write at offset 0 needs no `n5`; two allpasses
keep the gain already in `y1`; the 0.75, 0.625 and 0.5 gains and one mask load
as one-word short immediates.

### DSP load, 20 September 2026

457 assembled words. All multiply/MAC encodings checked in disassembly.
The benchmark executes genuine stock OS 1.40C code, with eight instances on
the two payloads, four per core, at 44.1 kHz and 16-sample blocks. Each load
case runs 4096 blocks (1.486 s). Every active control changes every block,
independently and synchronously; all 16 trigger split positions, spring TYPEs
and plate/dark MIXF settings are exercised.

| Effect | Fixed peak/core/block | Moving controls, unsplit | Worst tested peak/core/block |
|---|---:|---:|---:|
| Stock spring | 16,744 | 16,748 | 20,376 |
| Stock plate | 11,908 | 12,032 | 14,236 |
| Stock dark | 12,620 | 12,636 | 15,780 |
| Mini Verb v4 | 20,132 | 20,132 | 20,296 |

Mini Verb's worst tested instruction peak is **0.4% below spring**. Its
unsplit moving-control cost is **20.2% above spring**: the comparable peak
comes from low split-call overhead, not equal per-sample cost. Four-instance
init costs are spring 380, plate 280, dark 500 and Mini Verb 184 instructions.
The earlier v2 Mini Verb peaked at 14,152; extra diffusion uses the expanded
budget requested after listening.

These are **executed instructions, not hardware cycles or CPU usage**. They
include effect parameter decoding and both split calls, but exclude
ColdFire parameter publication/UI, the dispatcher, voice engines, other
effects and DMA/cache/memory stalls. Hardware eight-track playback/editing
and a burn sweep remain necessary to establish real overload headroom.
The finite sweep is not a proof over every possible parameter combination.

## On the unit

Cursory testing on Sam's MKII (owner report, 16 Oct 2026).

## Gates

```sh
make bus REMIX=miniverb
make check REMIX=miniverb
make benchmark-reverbs
make verify-miniverb
# Optional installed-plugin reference, not required for this voice:
make compare-vintageverb
```

After changing the harness, stage/rebuild it with `make setup`, or copy
`tools/harness/dsp_host/dsp_host.cpp` to the matching vendor directory and
run `cmake --build vendor/dsp56300/build --target dsp_host -j8`.
The emulator requires macOS shared-memory access.

`out/reverb_bench/report.md` and `results.json` contain load results, with
exact commands, automation, block meters and logs retained beside them.
Some local artifacts contain stock firmware; do not redistribute images or
memory dumps. Benchmark builds preserve `out/mainos_bus.bin`.

Regression checks cover eight simultaneous outputs versus isolated outputs
bit-for-bit; one excited slot with seven exactly silent slots; interleaved
cores; dirty scalar blocks and all eight delay buffers; private/shared Y
and loaded P bounds on both split calls; and a positive control that injects
a cross-core write. Audio checks cover exact dry, stereo decay and ordering,
phase/ring wraps, early diffusion, audible modulation, and unclipped decay
with maximum feedback/brightness and both held and changing modulation.
The budget gate compares Mini Verb with spring's peak in the same load run.


Manifest gate: `tools/verify/verify_miniverb.py` (stage `image`).

## Design

Four branches each contain a fixed delay, one-pole damping and two allpass
diffusers. An orthogonal four-way Householder matrix mixes the branch outputs
back into the delay inputs. Diffusion therefore accumulates on every pass,
not only at the input. The input also has DC rejection and four diffusers.

| Branch | Delay | First allpass, g=0.7 | Second allpass, g=0.5 |
|---|---:|---:|---:|
| 1 | 977 | 347 + modulation | 683 |
| 2 | 1429 | 431 | 887 |
| 3 | 1831 | 563 + opposing modulation | 1091 |
| 4 | 2213 | 719 | 1361 |

Lengths are samples at 44.1 kHz. Input diffusers are 113/173/337/449 samples,
with gains 0.75/0.75/0.625/0.625. Modulation reserves 64 samples of excursion
plus an interpolation neighbor in each moving allpass. The default depth
uses approximately 40 samples (0.91 ms); maximum is approximately 64 samples
(1.45 ms). The triangle advances per sample, including split calls. RATE
changes speed without resetting phase. Decay, damping, mix and depth smooth
with a 1/256 coefficient (about 5.8 ms time constant). Feedback stays below
0.968; output makeup sits outside the tank.

## Ownership and initialization

Every instance captures its stock allocator buffer during init and uses only
a 15,870-word Y ring in it and X:(r7+$20..$3f). The ring stops at `+$3DFD`, so the
slot's last `$202` words stay free (octabam's FX2 rule, #785: in T3's and T7's slot
they are SIDECHAIN_COMPRESSOR's cross-core window); until 19 Oct 2026 the ring was
the whole 16K slot. The current layout occupies 13,750 ring positions, including
interpolation slack, so the shorter ring changes no delay or tap. No global writable scratch. Four
instances per DSP core, eight total, include all four shared-window buffers.
The ledger refuses combinations with modules that hardcode those buffers.

Init clears every persistent scalar unconditionally, then clears 128 delay
words per process call, under the ring's own modulus (the last of the 124 calls
wraps 2 words to the start). Audio passes dry until the whole ring is clean
(124 unsplit blocks, about 45 ms; split calls shorten this). MIX=0 from init
is bit-exact dry; changes to MIX settle through the smoother.

The phase is explicitly masked to 17 bits. An earlier prototype mistakenly
used M=0x1ffff, which selects linear addressing because its low 16 bits are
all ones. Its phase escaped and crossed an internal delay segment, producing
a sustained clipped tail. Tests require a bounded phase, actual wraparound
and correct sample advancement; modulo differences alone did not catch it.

## Audition files

Local accepted audition files live in `out/miniverb_v3` (the study directory
also retains the rejected eight-line candidate). **A = original v2;
B = accepted v4**, with a half-second gap:

- `drums_before_after_deep.wav`
- `plucks_before_after_deep.wav`

Both are fully wet, matched by stereo RMS over the first four seconds, with
no limiter. This is not LUFS matching. `comparison.json` records gains,
source hashes and diagnostics; `compare.py` reproduces them from the saved
raw WAVs and requires NumPy. `before/` preserves v2, `rejected_eightline/`
preserves the rejected candidate, and `diffuse_shallow/` preserves the
shallower modulation experiment. These local artifacts are not runtime
requirements. The optional installed-AU comparison remains available in
`out/vintage_study`; it does not measure target DSP cost.
