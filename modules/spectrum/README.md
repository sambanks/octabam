# SPECTRUM

A filter pedal on stock FILTER's id 0x04. FX1 only: an FX2 instance runs as
a dry pass (`Claims(fx1_only=True)`, `verify_spectrum.py`); the FX2 chooser
hides the row.

| page 1 | FREQ ⌐RES · ENV · LDP ⌐LSP · WDTH |
|---|---|
| page 2 | MODE (LADR SEM BP ISO VOWL) ⌐SHPE · — · — · — · — |

- **LADR** — the linear zero-delay Moog transistor ladder (audiojs/filter
  moogLadder, MIT), 24 dB/oct; RES 127 is the edge of self-oscillation,
  bounded there. The passband sits at 1/(1 + k) (k up to 3.9 at RES 127:
  −13.8 dB), so since 23 Sep 2026 the output carries a RES makeup
  M = min(1 + k/2, 2.3), one per-block word and one multiply per channel
  (Sam: "the vol drop desperately needs it"). Loop RMS against dry at RES
  64 / 127: FREQ 127 −9.4 / −13.5 → −3.5 / −6.3 dB, FREQ 64 −9.1 / −8.6 →
  −3.1 / −1.4. The clamp keeps `verify_spectrum`'s 0.3 FS noise at RES 127
  off the rails (1 + 0.75k railed 4.6 %, 1 + k/2 0.4 %). VOWL's RES 127
  loss (7.5 to 9 dB on the loop, the bands narrowing) is left: a 0.1 FS
  tone at the formant already peaks at −4.7 dBFS through its ×8 makeup,
  and ×12 put it on the rails.
- **SEM / BP** — a driven Oberheim SEM zero-delay SVF (Zavalishin's
  trapezoidal form, audiojs/filter oberheim, MIT); the cutoff ramps per
  sample, 1/128 of the way to the block's cutoff per sample. SEM carries
  SHPE (page 2, slot 7; `---` in every other mode): the SEM's mode pot, 0
  lowpass, 64 notch (LP + HP), 127 highpass, as weights on the SVF's taps
  (kHP = min(1, k/64), kLP = min(1, (127 − k)/63), both exactly 1 at 64).
  BP is its own MODE. (23 Sep 2026; HP had been a sixth MODE for a day.)
- **Ramps** (26 Sep 2026): every coefficient a knob moves (the SVF's c4 d
  kLP kHP, LADR's k/4 d/2 M/4, VOWL's b0 m1 a2 per formant and vg, ISO's
  gn lpBase trim) is a run value the loop steps once per sample, 1/128 of
  the way to the block's target (`fs_rset`, `fs_r3`); a step that rounds to
  0 lands it on the target, and the first block of a mode starts it there.
  VOWL's morph fraction is 21 bits (5 until then). `make verify-knobs`
  measures every knob moved mid-render; a knob at rest renders as before,
  except the cutoff under ENV or the LFO, which now follows them through
  the 1/128 ramp.
- **ISO** — an isolator (Airwindows Capacitor2; `capacitor2_ref.py` is the
  float reference). In ISO FREQ is LOW and RES is COLR, the dielectric colour.
- **VOWL** — a three-formant bank (constant-peak-gain resonators) morphed
  across A E I O U by FREQ; RES (SHRP) narrows the bands. Formants are
  Peterson & Barney (1952) male means; bandwidths 90 / 110 / 170 Hz.

FREQ is exponential, 60 Hz → 15 kHz, an equal step per detent (a 33-word
P table interpolated per block). ENV (a block-peak follower, instant attack,
LSP = release) and LDP (an LFO, LSP = speed ~0.08–9 Hz) both move the
cutoff. WDTH is mid/side width on the output. TAME (the filters' state
saturation, 14 Sep 2026) is gone since 15 Sep 2026 -- Sam: "tame should be
gone"; the removal is bit-identical to TAME 0 and frees the two `div`-fed
per-block words and six 28-word calls per channel pair.

Defaults are a bit-exact passthrough (FREQ 127, RES 0, ENV 64, LDP 0, WDTH
64, MODE 0): the engine detects that block and copies nothing, because every
part that chose FILTER runs this on FX1. A part's stored bytes are stock FILTER's until
`ot_project.py stamp-defaults` writes ours.

Every mpy is `mpy x0,y1`, the audited-signed form, but the VOWL decode's
`mpy x1,y1,b` (R' > 0; `build_bus.MPYSU_AUDITED`); every clip is the store
limiter.

## Measured

- `tools/verify/verify_spectrum.py`: defaults bit-exact on a full-scale
  ramp; LP slope, HP/BP at DC → 0, VOWL A vs I distinct, every knob at both
  extremes renders; an FX2 instance is a bit-exact dry pass.
- `tools/verify/verify_spectrum_ident.py ref/check` (13 settings: every
  MODE with and without ENV/LDP, defaults, zeros, max) and `make verify-ident
  MOD=spectrum` (every MODE at two knob sets, zeros, max): the bit-identity
  gates for a rewrite.
- `verify_dirtystate` (in `make verify`): init zeroes every persistent slot
  the loop reads. Before it did, filter B's frozen HP poles held a stale
  value and put up to a full-scale DC on a station's output, which surfaced
  on hardware as the master compressor collapsing the right channel.
- Cost (pricer words/sample per mode, SVF / VOWL / LADR / ISO): 126 / 216
  / 238 / 292 on 23 Sep 2026 after SHPE and the makeup → 107 / 170 / 198 /
  250 after the loop pass the same day (one `do n7` per MODE, dispatched
  per block; only the selected mode's stream is built; the input peak,
  LADR's Grun and CAP's rotation count in address registers for the loop;
  CAP's amounts ring set up per block and written in read order, its
  four per-block constants in a second ring; the parallel moves stock runs
  in the same shape: `mpy/mac … x:(rN)+,x0`, `x:(rN),x0`, `add … a,x0`,
  `a,y0`, `x0,b`, `x1,b`, `asl a a,x1`, `asl b y0,a`; `max a,b` for the
  peak). Displaced moves (`x:(r7+$nn)`, 3.98 cycles on the chip against 2.00
  for a pointer or register move, probe 57, `docs/firmware/CHIP.md` §2) per
  sample: 49 / 78 / 39 / 88 before the 22 Sep pointer rewrite, 9 / 7 / 10 /
  17 after it, 4 / 0 / 0 / 1 now (SVF's cutoff ramp and its two reads; ISO's
  WDTH). LADR's G' clamp at $7f0000 went: G = g/(1+g) is 0.645 at the
  table's top (0x748894) and the ramp stops at G. Both identity gates
  bit-identical across the pass; hardware cycles unmeasured (a station's
  timer window is pre-empted by whole frames, CHIP.md §2). Program words:
  payload A FREE 848 → 621 (four loops carry their own width block).
- `verify_menu`, `verify_replaces`, `verify_labels` pass on the rig.

On Sam's unit since flash 4; the LADR voicing (PR #254) since image 21.

## Open

- The remaining displaced moves are the SVF's cutoff ramp (g2run += dg,
  read twice per sample) and ISO's WDTH read; the other modes step g2run
  per block by n7·dg (`fs_gramp`), the same end value.
