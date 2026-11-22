# `busverb` — REVERB SERVER

An eight-line FDN reverb with ROOM/PLATE/BIG modes, modulated taps, a
shimmer, a gate and mid/side width.

The reverb stage of the bus ([`send`](../send/README.md)): every track's
REV send, plus the delay's repeats × DLY, feed it, and it prints its tail
under its own host's dry. Hosted on T5's FX2 (RIG HOSTS), on payload A
(core 0), which serves tracks 5–8 (measured; test it on track 5). Source
`reverb_server.asm`, manifest `manifest.py` (the MODE rows), built by
`tools/build/build_bus.py`. The development record (the four-line engine,
the 32K re-layout, the crackle, the voicing rounds up to 16 Sep 2026) is
`REVERB.md` and `VOICING.md` under `docs/history/` in git history
(`git show 3ceba41:docs/history/<name>`); this page's own earlier form is
`git show 666b6154:docs/effects/REVERB.md`. ✅ measured on the unit, 🟡
harness only.

## Knobs

Since 26 Sep 2026 the host page draws DEL and REV only (the remix's
`host_slots`); every other knob is on the TEMPO window
([`tempo-bus`](../tempo-bus/README.md)).

| page | slot | name | reads | range | what it does |
|---|---|---|---|---|---|
| 1 | 0 | DEL | `r6+$0` | 0–127, default 0 | this host's own dry into the delay's aux |
| 1 | 1 | REV | `r6+$1` | 0–127, default 0 | this host's own dry into the REV accumulator (3-bit headroom, counted through `Y:0x981`, `0x941` until 22 Sep 2026; slot 0 until 26 Sep 2026). Default 0: a non-zero default registers an idle host as a client and dilutes the real senders |
| 1 | 2 | SIZE ⌐ | `r6+$2` | 0–127, default 100 | scales all eight taps within the mode; floor `f = 0.4` (~1,810 samples, 24 Hz mode spacing); glided 1/64 per block since 20 Sep 2026 (state `y:$09f3`, zeroed at init, clamped to f's range) |
| 1 | 3 | SHMR | `r6+$3` | 0–127, default 0 | shimmer amount, 0 off (bit-identical to no shimmer) |
| 1 | 4 | SHFT ⌐ | `r6+$4` | 6 steps, default +12 | shimmer interval −12 / +5 / +7 / +12 / +19 / +24; drawn linked to SHMR; the first stepped select on a page 1 (✅ image 29: draws its words) |
| 1 | 5 | WET | `r6+$5` | 0–127, default 127 | `out = in + 2 × wet × WET`, `in` the chain input at unity; 0 passes the chain input alone; the ×2 is 16 Sep 2026's makeup ("reverb is still too quiet") |
| 2 | 6 | MODE | `$c` bits 16–23 | ROOM / PLATE / BIG, default PLATE | slot 6 since 4 Sep 2026 (an even slot is one the panel's page-2 editor writes) |
| 2 | 7 | TONE | `$c` bits 8–15 | 0–127, default 64 | LO + HI on one knob: 0..64 = LP 0..127 with HP off, 64..127 = HP 0..126 with LP open; 64 = flat |
| 2 | 8 | DIFF | `$d` bits 16–23 | 0–127, default 80 | allpass coefficient ~0.38–0.80 |
| 2 | 9 | GATE | `$d` bits 8–15 | 0–127, default 0 | gated reverb: 0 off; hold `2048 + GATE×256` samples = 52 ms (1) .. 784 ms (127) before the wet shuts; envelope keyed on the tank input (`$1b`), fast attack, ~20 ms eased release, per-sample multiply on the wet |
| 2 | 10 | DLY | `$e` bits 16–23 | 0–127, default 127 | the delay's repeats into the reverb; published to `Y:0x982` every block, read by the delay, which writes `wet × DLY` into the chain; 0 = the two engines in parallel |
| 2 | 11 | TIME | `$e` bits 8–15 | 0–127, default 64 | the tank law `$1e = a − k_mode·(d_min + d_span·(1−t)²)`, per-line gains `G_i = a + r_i·($1e − a)`; page-1 slot 1 until 26 Sep 2026 |

The tank modulation is pinned at MOD 30 / RATE 1× inside the engine since
15 Sep 2026. The 16 Sep 2026 knob pass reordered the page (before it: SEND
TIME SHMR SIZE TONE WET / MODE — DIFF SHFT GATE —); renders at any knob
value by name are bit-identical across the two layouts. The page-2 field
map is `docs/firmware/PARAM_PAGES.md` section 6. Stock DARK reads its pre-delay
from `$c`; BusVerb's `$c` knob field is MODE.

## Open

- Coupling the diffuser g to TIME (~13 words) waits for payload A words.
- A SIZE turn once killed the reverb (R44) and has not been reproduced. If it
  recurs, the diagnostic is whether tracks 5–8 all died.
- The tank modulation depth's range (flattening after ~64 measured; the
  top half may do nothing) — the knob went 15 Sep 2026 and the depth is
  pinned at 30, so this is only reachable by changing the engine.
- An emulator-only divergence between one and two instances under a
  nonzero split.

## Signal path

```
chain in ─► 4 series allpasses ─► ┌─ FDN tank ───────────────┐ ─► shimmer ─► gate ─► width ─► WET
 (REV Σ, + the delay's     (input diffusion,     │ 8 × 4096-word lines       │
  repeats × DLY while       taps 641..1949)      │ interpolated LFO per line │
  it is live)                                    │ 8×8 FWHT (24 butterflies) │
                                                 │ HI damping + LO cut       │
                                                 │ in-loop allpass, lines 0-1│
                                                 └───────────────────────────┘
```

- Input diffusers: four series allpasses, taps 641/1051/1511/1949 (2048-word
  buffers; all modes share them since Round 13). Coefficient = DIFF + the
  mode's offset (`$3f`).
- Tank: eight 4096-word lines (spacing `0x1000`, modulo `0xfff`), an 8×8
  Walsh-Hadamard feedback matrix, decay constants scaled 2/√8. Every read
  is interpolated and LFO-modulated, each line on its own prime-relative
  rate; the input is attenuated 12 dB before the tank (headroom inside the
  loop; the output sum no longer divides, so the level is unchanged).
- In the loop: a one-pole low-pass (HI) and high-pass (LO) per line, one
  shared coefficient per pass; in-loop allpasses on lines 0 and 1, 512
  words, taps 298/446, LFO-modulated at a fixed non-zero depth.
- Out: L/R tap sums before the FWHT, sign patterns `+−+−+−+−` and
  `++−−++−−`; shimmer (a pitch shifter in a 2048-word line; `NOSHIM=1`
  excises it); GATE; mid/side width (pinned wide); the wet high-cut; the
  host print `dry + 2 × wet × GLVL × WET`.
- The 4096-word pre-delay buffer is mapped and cleared by the warm-up,
  never read or written otherwise (PRE retired).

## MODE

Seventeen (r7 slot, value) pairs per mode, copied into the r7 block after
warm-up (`manifest.py` `_MODE_ROWS`; taps as fractions of the 4096-word
line). The r7 slots are the ones before the 27 Sep 2026 slot pass; the
manifest's `_MODE_SLOTS` is the current map.

| lever | r7 | ROOM | PLATE | BIG |
|---|---|---|---|---|
| `k_mode` (TIME law) | `$1e` | 0.5 | 0.4 | 0.25 |
| wet gain/2 | `$20` | 0.988 | 0.988 | 0.703 (−3 dB) |
| lines 0–3 taps | `$74..$77` | 3958/3386/2894/2474 | 3528/3283/3056/2845 | 4050/3403/2860/2403 |
| tap scale | `$6f` | 0.60 | 0.5625 | 1.0 |
| diffusion offset | `$3f` | 0.125 | 0.125 | 0.094 |
| damping scale | `$72` | 0.953 | 0.78 | 0.90 |
| mod depth scale | `$73` | 1.0 | 1.0 | 0.60 |
| wet high-cut | `$7a` | 0.523 | 0.68 | 0.60 (~6.4 kHz) |
| lines 4–7 tap scale (interleave) | `$6c` | 0.71875 | 0.765625 | 0.789 |
| diffuser taps | `$7e..$81` | 641/1051/1511/1949 | same | same |
| LFO rate scale | `$2f` | 1.0 | 1.0 | 1.0 |

The mean tap is 3178 in every mode (tap scale and spread independent). A
HALL mode was cut as indistinguishable from BIG in blind A/B.

## Memory

Buffer base `Y:0x4000` (the bank's whole FX2 allocation), every other
buffer in this core's half of the shared window (`build_bus.py` rewrites
the base literal per payload); 65,536 words per server:

| location | size | what |
|---|---|---|
| `base+0x0000..0x7fff` | 8 × 4096 | tank lines, taps to ~3914 (89 ms) at SIZE max |
| `shared+0x0800..` | 2048 | shimmer line |
| `shared+0x1000..0x1fff` | 4096 | former pre-delay: cleared by the warm-up, never read or written otherwise |
| `shared+0x2000..0x3fff` | 4 × 2048 | input allpasses, taps 641/1051/1511/1949 |
| `shared+0x4000` / `0x4200` | 2 × 512 | in-loop allpasses |
| `shared+0x4500..0x453f` | 8 × 6 + 8 × 2 | tank state table A (tap loop: read offset, fraction, d0 carry, damping state, LO state, output) at `+0x4500`, table B (feedback: weight, gain) at `+0x4530` |
| `shared+0x4800` / `0x5000` | 2 × 2048 | bloom allpasses (output branch), taps 1801/1291 |

`shared+0x0800..0x57FF` is declared as `Claims.dsp_ranges` (payload A:
`Y:0x30800–0x357FF`); the warm-up clears all of it, and `verify_set`
holds the port's shared-window write census to it.

r7 block: `$84+` hangs the DSP; `$82` warm-up counter (`$2c0000 | blocks`,
capped 0x100), `$83` write phase; the asm header is the slot map, from a
census of the source (23 Sep 2026: sixteen slots unreferenced, listed
there). The warm-up zeroes the allocation 128 words a block over 256
blocks and outputs dry until warm. One BusVerb per bank (role lock); a
second instance returns as a passthrough. In the sample loop r0 is the
audio, r1–r3 the line-0..2 pointers (lines 3–7 are addressed from r3 by
stride), r4/r5/r6 walk the u vectors, the feedback tables and the state
table, n0 carries the allpass phase and n2/n3 the aux write/read
pointers; n1 is the line stride, n4–n6 table strides and taps.

## Engine rules

- Interpolation fraction: integer part via `asl #n`, fraction masked with
  `2^(24−n)−1` and shifted by `n−1`, never `n` (a shift by `n` reads
  negative past `0x800000` and the read jumps backwards once per LFO step:
  a fast flutter).
- Offset/fraction pairing: each line's fraction comes from the same LFO as
  its integer offset. Two lines with swapped fractions put a 1-sample
  sawtooth at ~76 Hz on the tail (−29.6 dB): the crackle. The carried
  interpolation partner (−64 dB) and the block-stepped LFO (−62.5 dB, 64
  cycles/sample) were not it.
- The in-loop allpasses' `d0` carry is seeded per block like the tank's
  (28 instructions per block).
- Modulation never reaches zero; rate, not depth, is what reads as
  seasick (pitch shift ∝ d(delay)/dt), and the pinned ~0.4 Hz base was the
  binding cause of the metallic end-ring: base ×8 to ~2.2 Hz with depth
  scales trimmed (Round 13; ROOM's crest 65 → 49).
- An in-loop allpass above ~15% of its line's length disperses (a spring)
  rather than diffuses; the 2048-word versions were cut for this.
- Pack the buffers: taps spanning 2.1:1 in equal power-of-two buffers left
  ~40% of the delay memory unread; ~1.6:1 recovered it.
- Input diffusion smooths the attack, in-loop diffusion thins the modes;
  they are not interchangeable.
- Averaging more tank lines into each output concentrates energy (the
  lines share a matrix); disjoint 2-line pairs per channel.
- Spectral flatness rewards broadband noise (it ranked the flutter builds
  highest); early crest factor is the companion metric; when it and the
  ear disagree, the ear is the measurement. Clipped-sample counts predict
  audibility badly (26,741 clipped on bass inaudible; 6 on the synth
  audible: loop compression, not the output rail).
- Modal prominence (8–11 dB over the local envelope) is monotonic in total
  delay; total delay read at SIZE max is the lever and it is spent.
- Change one thing per flash.
