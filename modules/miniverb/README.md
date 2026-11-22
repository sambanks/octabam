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
