# SPECTRUM

The first BamSep26 station: two filters, four routings, one modulation and
two bus sends in one insert, **replacing stock FILTER** (id 0x04) on both
menus and in every saved part that chose FILTER. Design page:
https://claude.ai/code/artifact/42670d67-7365-4c7d-bcc7-1786ba4331ce

| page 1 | FREQ · RES · BASE · WDTH · →DEL · →VRB |
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
- `tools/verify_spectrum.py` (needs the audition dump): defaults
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

## Open

- Voicing: nothing has been heard yet. The coefficient laws (cutoff taper,
  base/width corners, LFO rate range, release times, FM depth 0.25) are
  first guesses.
- Cycles: 339 is dear. Candidates if it must come down: drop RING (~10),
  a single-pole base/width (~40), block-rate FM.
- The layout alphabet lists this station under both `1` and `L` (stock
  FILTER's letter) because both map to id 0x04 — harmless, cosmetic.
- ⚠️ UNFLASHED. The FX1-participant bus case is flash 4's claim (v).

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
the silent-mis-encode trap (`docs/DSP.md`) live on every new parallel move.
`dsp_asm` DOES encode the legal parallel forms correctly (probed 4 Sep 2026;
`mpy x0,y1,a x:(r3)+,x0 y:(r4)+,y1` round-trips), so the trap is only the
illegal ones — but disassemble every one.

**The gate is ready:** `tools/verify_spectrum_ident.py ref` captured 26 hashes
across every MODE × ROUT, every SRC, defaults, zeros and maxima; a rewrite
must `check` bit-identical. Do the relayout only when four grains (or a
tighter card) actually needs the cycles — today both cores have margin at two
grains, so there is no consumer.
