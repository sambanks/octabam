# MODULATION

The third BamSep26 station: one modulated line, seven modes, **FX1 only**,
replacing stock CHORUS (id 0x12). Design page:
https://claude.ai/code/artifact/1f1bfff2-9d4e-41b6-b0a7-91a3c8989aaf

| page 1 | RATE · DPTH · FDBK · MIX · →DEL · →VRB |
|---|---|
| page 2 | DLY · MODE (CHOR FLNG PHSR COMB TREM VIB PAN) · TONE · SHPE (TRI SIN SQR SAW) · WID · STGS (2P 4P 6P 8P) |

Three sample loops, chosen once per block — the Ripple pattern, which
`cycle_count` prices as "worst of N mode loops"; a dispatch *inside* a sample
loop cannot be priced at all.

- **LINE** (CHOR, FLNG, COMB, VIB): one interpolated tap with feedback and a
  one-pole damping inside the loop. The modes differ only in per-block
  coefficients — centre delay, sweep depth, feedback.
- **PHSR**: four one-pole allpass stages swept by the LFO, tapped after 1–4
  stages by four per-block weights, so STGS costs no branch.
- **AMP** (TREM, PAN): the LFO on amplitude, together or opposite, which is
  one per-block polarity word.

Every mode outputs the **wet only** and MIX blends, so MIX 0 is an exact
passthrough in all seven and 127 is vibrato or tremolo outright. The LFO runs
**per sample** (a per-block LFO steps at 2.9 kHz, which a chorus hears as
zipper), with two shaped copies — L and its WID-offset partner.

## FX1 only, and it enforces that itself

It needs a per-track line, and beside the servers the only free per-track
buffer is the FX1 slot: every FX2 instance buffer is BusVerb's tank on core
0 or BusDelay's line on tracks 3–4. It reads its base from the host's bump
allocator **at init and only there** (`docs/firmware/DSP.md` §10), and a base ≥ 0x4000
sets a flag that sends proc down the dry path, which writes nothing to Y.
`Claims(fx1_only=True, buffer_words=2048)` is that promise to the ledger, and
the first three gates below are what it rests on.

Two lines of 1,024 words (23 ms each) of the 3,072 an FX1 slot gives. The
read offset is masked, not the address, so nothing depends on where the
allocator put us.

## Measured (3 Sep 2026, local)

- **1,133 words** (payload A, 1,166 on B), **402 cycles/sample** (the LINE
  loop is the worst of the four; PHSR is 354, AMP 193, dry 20).
- `tools/verify/verify_modulation.py`, **9 gates, all PASS**:
  - MIX=0 is a bit-exact passthrough in all seven modes;
  - **an FX2 instance is a bit-exact dry pass in all seven modes at any
    setting**, and `dsp_host -guard` reports "nothing written over a loaded
    module" — the FX1-only claim, proven;
  - the LFO is square-law in RATE (0.5 → 3.0 cycles in 0.68 s at RATE 20 vs
    110), measured in TREM **on a DC input**, where the output *is* the LFO;
  - VIB reads the line: an impulse comes back **473 samples** later, which is
    the centre delay the knob asks for;
  - PHSR is unity magnitude (+0.01 dB against the dry);
  - TREM modulates the amplitude, PAN drives the channels 3.3 M apart;
  - every knob at both extremes renders.

## What the gates cost to get right

- **An hour was spent on a stale audition dump.** The scratch image is cached
  against the newest mtime under `modules/`, and a stale hit does not fail —
  it silently measures the STOCK effect whose id this module replaces. Every
  mode read as a dry pass, the LFO looked dead, and the emulator eventually
  died on `MACRI`, an instruction stock code uses and it does not implement.
  The three station gates now delete and rebuild their dump first.
- **The delay decode shifted an already-scaled product**, pinning every line
  mode at its 8-sample floor: an 8-sample chorus, measured as an impulse
  returning 7 samples late instead of 473.
- **The feedback's one-pole accumulated instead of tracking** (`s += c*tap`
  rather than `s += c*(tap − s)`), which walks the state to the rail.
- **The allpass was not an allpass**: `y = x − c·s` instead of `y = −c·x + s`
  measured 19.6 dB down where an allpass must be 0.0.
- **The LFO topped out at 51 Hz** — audio rate, not an LFO.
- Two gates measured the wrong signal before they measured the right one: an
  envelope follower on a 438 Hz tone tracks the tone, not the sweep.

## Measured laws (12 Sep 2026, `tools/harness/station_laws.py --probe lfo|impulse|noise`)

| knob | law | readout |
|---|---|---|
| RATE | squared, ~0.05 → 8 Hz (kept: chorus rates in the bottom half, tremolo/vibrato in the top) | 32 → 0.64 Hz, 48 → 1.24, 64 → 2.1, 80 → 3.3, 96 → 4.6, 112 → 6.3, 127 → 8.0 |
| DLY | linear, ≈1 ms + 0.18 ms per detent; **the read is clamped to the 1,024-word line** (centre ≤ 1,000 samples, depth ≤ min(centre − 8, 1,015 − centre)) | 16 → 3.9 ms, 64 → 12.3, 96 → 18.0, 127 → 22.7 (it was 0.18 ms: CHOR's 40-sample floor pushed 127 past the line and the mask wrapped it) |
| FDBK (FLNG) | linear | a 4-sample comb decaying −9.6 / −5.6 / −3.5 dB per pass at 64 / 100 / 127 |
| DPTH (TREM, PAN) | | 5 / 10 / 17 / 38 dB at 32 / 64 / 96 / 127 |
| COMB | DLY = the pitch; FDBK the ring | resonance peaks +8..+12 dB, bw 20–40 Hz |
| PHSR | **rewritten**: the allpass coefficient was multiplied `mpy x1,y1` — the order that ENCODES AS MPYSU — so a negative `c` (half of every LFO cycle) read as a large positive one and the chain measured +34 dB at Nyquist and +6 dB across the band; the sweep had no centre (DLY unused) and the RES knob reached nothing. Now: `c = centre + DPTH·0.75·lfo`, centre `0.94 − 1.24·DLY/128` (first notch ≈ 1 kHz at DLY 0 → 15 kHz at 127), the sweep clamped per block so `c` stays inside ±0.95, RES = negative feedback of the chain's output (capped 0.9·knob; positive fed back at DC) | unity peaks, notches −55 dB, one more notch per STGS step; RES 64 +3 dB resonance between the notches |

Cost: the phaser loop 464 (it was cheaper broken); the line loop 386.

Kits for the ear in `out/ab/mod_*` (`tools/harness/abkit.py`): the seven
modes, CHOR depth, FLNG feedback, PHSR stages and resonance, COMB pitch,
TREM rate.

## Open

- Voicing (ear pass, 12 Sep 2026, kits in `out/ab/mod_*`): the seven modes
  all distinct. CHOR depth 16–127 "sounds good". FLNG had a **crackle** on the
  loop (not on a 440 Hz sine): the tap's linear interpolation blended toward
  the NEWER neighbour, so a delay of i + f read as i − f and jumped two
  samples at every integer crossing of the sweep — every LINE mode, shipped
  on flash 4 and 7 unheard. Fixed (blend toward the older sample): off-tone
  energy on a 5 kHz sine −48.7 → −89.5 dB max; "gone" by ear. Still to hear:
  PHSR (stages, RES), COMB, TREM.
- SAW is a real shape since 3 Sep 2026 (`modulation.asm`).
- On hardware since flash 4 (tag 79) as T5's FX1; the FX1-only dry pass is
  emulator-proven; none of the 12 Sep changes are flashed.
