# SPECTRUM

The first BamSep26 station: two filters, four routings and one modulation
in one insert, **replacing stock FILTER** (id 0x04) in every saved part that
chose FILTER. **FX1 only** (12 Sep 2026): the id is shared by both menus, so
an FX2 instance runs as a dry pass, decided from the allocator base at init
(`Claims(fx1_only=True)`, proven by `verify_spectrum.py`), and the FX2
chooser hides the row -- the rig's cycle envelope only closes with the
stations on FX1. The bus sends went with the one-aux rig (7 Sep 2026):
page-1 slots 4-5 are blank. Design page:
https://claude.ai/code/artifact/42670d67-7365-4c7d-bcc7-1786ba4331ce

| page 1 | FREQ · RES · BASE · WDTH · — · — |
|---|---|
| page 2 | DRV · MODE (LP BP HP NTCH VOWL) · DPTH · ROUT (SER PAR RING FM) · RATE · SRC (ENV LFO BOTH) |

Filter A is Ripple's driven Chamberlin SVF with NOTCH (lp + hp) and a VOWEL
mode (five formant pairs morphed by FREQ: A's band-pass at F1, filter B as a
band at F2, routing forced PAR). Filter B is the base/width pair: two
cascaded one-poles of HP at BASE and two of LP at WDTH. Routing: SER (A into
B), PAR, RING (2·A·B), FM (B's output modulates A's cutoff multiplicatively,
one sample late). Modulation: one bipolar DPTH onto A's cutoff from a
block-peak envelope follower (instant attack, RATE = release), an LFO
(RATE = ~0.08–9 Hz), or half of each.

**It is a bus client.** The processed mono is sent onto both buses with
SEND's exact writer, registering only when a send is non-zero, and it
**never housekeeps**: the rotation election is the FX2 participants'
business, so an FX1 station on track 5 cannot double-flip the rotation
with its own FX2 (see the engine header for the argument, and the one-block
latency difference it accepts).

**Defaults are a bit-exact passthrough**, because after the flash every
part that ever chose FILTER runs this on FX1. ⚠️ A part's STORED bytes are
stock FILTER's, not these defaults — DEC=64 lands on →VRB — which is what
the project stamper (plan A6) exists to rewrite; the registration gate
below reproduced exactly that scenario by accident (a second instance run
on FILTER's stored values sent at 64 through a closed, resonant filter).

## Measured (3 Sep 2026, local)

- **983 words** (payload A; 1,016 on B with the tracked-rotation body), placed
  by `remixes/stations.py`. **339 cycles/sample** (`make cycles`): every
  r7-indexed access is two words in this assembler, and the loop is ~250
  instructions with two filters, the routing mix, the peak tracker and both
  sends. Stock FILTER is 192 for one filter. Seven of these on one core is
  at the cliff by the pricer; four on FX1 plus three SENDs beside the reverb
  is 1,384 + 1,356 + 60.
- `tools/verify/verify_spectrum.py` (needs the audition dump): defaults
  bit-exact on a full-scale ramp; LP 12.9 dB/oct between 2 and 4 kHz at
  FREQ 30; HP and BP at DC → 0 (−2 / −1 LSB); NOTCH and LP at DC → DC (5
  LSB low); BASE 100 kills DC through the pair (4 LSB); WDTH 30 takes 55 dB
  off 8 kHz; RING at DC = 2·DC² to 5 LSB; VOWEL A vs I differ by 8.7 dB at
  1.1 kHz; every knob at both extremes renders. All PASS.
- **Registration** (`send_probe` on the `stations` bus dump, tone fed to the
  station's track only, `--amp 0.05` so the reverb stays linear):

  ```
  --layout R1  --feed 1  --set 1:-VRB=100                       -24.8 dBFS
  --layout R1L --feed 1L --set 1:-VRB=100 + L neutral, L:-VRB=0  -24.8 dBFS  (silent client: no dilution)
  --layout R1L --feed 1L --set 1:-VRB=100 + L:-VRB=100           -20.6 dBFS  (two senders, +4.2 dB)
  --layout R1  --feed 1  --set 1:-VRB=0                          silence
  ```
- Menu: `verify_menu`, `verify_replaces` (FX1 page taken, composed chooser
  lists the clone) and `verify_labels` (the three selects print their words
  on the emulated firmware) all pass on `stations`.

## Measured laws (12 Sep 2026, `tools/harness/station_laws.py` on noise)

| knob | law | readout |
|---|---|---|
| FREQ (LP) | exponential, 24 Hz → 7.2 kHz, one octave per 16 detents (a 33-word P table, `DspSection.ptable`, interpolated per block) | 48 → 258 Hz, 64 → 528, 80 → 1.1 k, 96 → 2.3 k, 112 → 5.0 k; 127 = the SVF's 7 kHz ceiling |
| RES | `damp = (0.998 − RES·0.587)⁴`: the peak is near-linear in dB | +1 / +5.7 / +12 / +20 / +30 dB at 0 / 32 / 64 / 96 / 127 |
| BASE (HP pair) | `c = BASE²·0.5` | 32 → 54 Hz, 64 → 205, 96 → 560, 127 → 1.27 k |
| WDTH (LP pair) | `c = WDTH²·1.0 + 0.002` — 127 is OPEN (flat within 0.15 dB at 10 kHz) | 96 → 4.0 k, 64 → 1.3 k, 32 → 320 Hz |
| DRV | 1 → 4× into the SVF, the limiter clips | +4.9 / +8 / +10 / +12 dB at 32 / 64 / 96 / 127 |
| NOTCH | depth −42 dB at RES 0, −36 at 64, −12 at 127 (narrower) | |

Two laws were wrong on the meter and are replaced: the FREQ taper was
squared (half the dial above 2 kHz; on the drum loop FREQ 24 → 56 barely
moved the centroid) and WDTH 127 sat at ≈7 kHz per pole, so every live
setting lost 5 dB at 10 kHz and 8 at 15 kHz (only the all-defaults bypass
was flat). RES was hyperbolic in dB (18 of 30 dB in the top quarter).

Known and left for the ear: the SVF's Chamberlin ceiling puts LP 127 at
7 kHz (12 dB/oct above), and HP/BP at the top of the dial lift 10–15 kHz
(+5 / +9 dB at HP 127 — the hp tap's warping at high f). A mode-aware
ceiling (HP/BP capped near FREQ 96's f) would bound the lift at ~+3 dB for
one per-block compare, if it reads as harsh rather than presence.

## Open

- Voicing: the laws are measured (above); nothing has been HEARD yet. Kits in
  `out/ab/spec_*` (`tools/harness/abkit.py`): the taper (squared vs
  exponential), RES, the HP top, VOWEL, FM depth 0.25.
- Cycles: 339 is dear. Candidates if it must come down: drop RING (~10),
  a single-pole base/width (~40), block-rate FM.
- The layout alphabet lists this station under both `1` and `L` (stock
  FILTER's letter) because both map to id 0x04 — harmless, cosmetic.
- On hardware since flash 4 (tag 79) and in every rig flash since; the
  FX1-only dry pass is emulator-proven (12 Sep 2026), not yet flashed.

## Cycle trim — the parallel-move relayout (evaluated 4 Sep 2026, not done)

Spectrum is the light station (341 cycles) and runs up to four times a core,
so it is the highest-leverage place to save cycles — every cycle shaved is
worth ×4 on the delay core. Where the cycles are: the per-sample loop is a
straight sequence of `move x:(r7+$xx),y1 / mpy x0,y1,a`, one memory access per
arithmetic word.

The 56300 can fold an X-read AND a Y-read into the same word as a multiply,
which would roughly halve the loop — a saving of ~80–100 cycles per instance,
enough to bring BusDelay's GRAIN back to four grains on the delay core with a
one-for-one Spectrum trim on each of its four tracks.

**Why it is not a quick pass:** a parallel move's operand must be
register-indirect (`(rn)+`, `(rn+nn)`), and this loop addresses everything as
`x:(r7+displacement)`, which the parallel forms forbid. Realising the saving
needs the classic filter relayout — coefficients contiguous in X, state
contiguous in Y, each walked by a dedicated address register (r3/r4/n3/n4 are
free in the loop; r0/r1/r2/r7 are taken) — which is ~150 lines rewritten with
the silent-mis-encode trap (`docs/firmware/DSP.md`) live on every new parallel move.
`dsp_asm` DOES encode the legal parallel forms correctly (probed 4 Sep 2026;
`mpy x0,y1,a x:(r3)+,x0 y:(r4)+,y1` round-trips), so the trap is only the
illegal ones — but disassemble every one.

**The gate is ready:** `tools/verify/verify_spectrum_ident.py ref` captured 26 hashes
across every MODE × ROUT, every SRC, defaults, zeros and maxima; a rewrite
must `check` bit-identical. Do the relayout only when four grains (or a
tighter card) actually needs the cycles — today both cores have margin at two
grains, so there is no consumer.
