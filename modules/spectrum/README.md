# `spectrum` — SPECTRUM

A filter pedal: a Moog ladder, an Oberheim SEM state-variable filter, an
isolator and a formant bank, with an envelope and an LFO on the cutoff.

On id 0x0f (stock FILTER keeps 0x04), FX1 only: an FX2 instance runs as a dry pass
(`Claims(fx1_only=True)`, `verify_spectrum.py`); the FX2 chooser hides the
row. The filter laws are from [audiojs/filter](https://github.com/audiojs/filter)
(MIT) and Airwindows Capacitor2 (MIT), re-derived here (Sources, below).

**SLOTS** (build setting, store `octabam.spectrum`): `FX1` (default) or `FX1+FX2`. With `FX1+FX2` an FX2 instance runs the station live and the FX2 chooser lists it; a remix pins it (`settings={("octabam.spectrum", "SLOTS"): Pin("FX1+FX2")}`). `tools/verify/verify_stations_fx2.py` renders the FX2 instance against the FX1 instance, bit for bit (`remixes/test/stations-fx2`). A remix with the bus keeps the default: its cycle budget is priced with the stations on FX1.
Defaults are a bit-exact passthrough (FREQ 127, RES 0, ENV 64, LDP 0, WDTH
64, MODE 0): the engine detects that block and copies nothing, because
every part that chose SPECTRUM runs this on FX1. A part's stored bytes are
the descriptor's defaults until `ot_project.py stamp-defaults` writes ours.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | FREQ | 0–127, default 127 | the cutoff, exponential, 60 Hz → 15 kHz, an equal step per detent (a 33-word P table interpolated per block); LOW in ISO; the vowel morph A E I O U in VOWL |
| 1 | 1 | RES ⌐ | 0–127, default 0 | resonance; COLR (the dielectric colour) in ISO; SHRP (narrows the bands) in VOWL |
| 1 | 2 | ENV | bipolar, default 64 | a block-peak follower onto the cutoff, instant attack, LSP = release |
| 1 | 3 | LDP | 0–127, default 0 | an LFO onto the cutoff |
| 1 | 4 | LSP ⌐ | 0–127, default 64 | the LFO's speed ~0.08–9 Hz; ENV's release |
| 1 | 5 | WDTH | bipolar, default 64 | mid/side width on the output |
| 2 | 6 | MODE | LADR / SEM / ISO / VOWL | the filter (Modes, below) |
| 2 | 7 | SHPE | 0–127, default 0 | SEM only (`---` in every other mode): LP → BP → HP |

TAME (the filters' state saturation, 14 Sep 2026) is gone since 15 Sep 2026
-- Sam: "tame should be gone"; the removal is bit-identical to TAME 0 and
frees the two `div`-fed per-block words and six 28-word calls per channel
pair.

Saved parts: MODE's values moved on 27 Sep 2026 (BP 2 → SEM 1, ISO 3 → 2,
VOWL 4 → 3); SHPE keeps its stored value, so a part that was on BP comes
back as SEM at whatever SHPE it held. Once per project, before play:
`python3 tools/hw/ot_project.py remap-slot <project> SPECTRUM MODE 2:1,3:2,4:3`.

## Open

- VOWL went silent once on the unit with RES up
  (`docs/contributing/FAILURE_MODES.md`, seen once, not reproduced).
- The remaining displaced moves are the SVF's cutoff ramp (g2run += dg,
  read twice per sample) and ISO's WDTH read; the other modes step g2run
  per block by n7·dg (`fs_gramp`), the same end value.

## Modes

- **LADR** — the linear zero-delay Moog transistor ladder (audiojs/filter
  moogLadder, MIT), 24 dB/oct; RES 127 is the edge of self-oscillation,
  bounded there. The passband sits at 1/(1 + k) (k up to 3.9 at RES 127:
  −13.8 dB), so since 23 Sep 2026 the output carries a RES makeup
  M = min(1 + k/2, 2.3), one per-block word and one multiply per channel
  (Sam: "the vol drop desperately needs it"). VOWL's RES 127 loss (7.5 to 9
  dB on the loop, the bands narrowing) is left: a 0.1 FS tone at the
  formant already peaks at −4.7 dBFS through its ×8 makeup, and ×12 put it
  on the rails.
- **SEM** — a driven Oberheim SEM zero-delay SVF (Zavalishin's
  trapezoidal form, audiojs/filter oberheim, MIT); the cutoff ramps per
  sample, 1/128 of the way to the block's cutoff per sample. SHPE (page 2,
  slot 7) sweeps LP → BP → HP: 0 lowpass, 64 bandpass, 127 highpass, an
  equal-power crossfade between neighbours on the SVF's taps (27 Sep 2026;
  BP was its own MODE and SHPE's middle was a notch from 23 Sep). With
  d = (k − 64)/64 below 64 and (k − 64)/63 above, kHP = max(0, s(d)),
  kLP = max(0, −s(d)), kBP = s(1 − |d|), where s(x) = x(A − Bx²) is a
  quarter sine (`fs_qs`: within 0.006 of sin(πx/2), s(x)² + s(1 − x)²
  within 0.05 dB of 1, s(1) = 1.00001 so a store limits it onto 1). Each
  weight is exactly 1 at its own stop and 0 at the others. The panel prints
  SHPE as LP / BP / HP at 0 / 64 / 127 and the number elsewhere
  (`shpe_fmt.s`, below). Equal power because at the cutoff the three taps
  are equal in size and LP/BP, BP/HP are in quadrature, so an equal-power
  fade holds a tone at fc level across the sweep; a linear one dips 3 dB at
  SHPE 32 and 96 (float model of the same SVF). Away from fc the level
  follows the passband that is fading in, as it does between any two
  filter types.
- **ISO** — an isolator (Airwindows Capacitor2; `capacitor2_ref.py` is the
  float reference). FREQ is LOW and RES is COLR.
- **VOWL** — a three-formant bank (constant-peak-gain resonators) morphed
  across A E I O U by FREQ; RES (SHRP) narrows the bands. Formants are
  Peterson & Barney (1952) male means; bandwidths 90 / 110 / 170 Hz.
- **Ramps** (26 Sep 2026): every coefficient a knob moves (the SVF's c4 d
  kLP kHP, LADR's k/4 d/2 M/4, VOWL's b0 m1 a2 per formant and vg, ISO's
  gn lpBase trim) is a run value the loop steps once per sample, 1/128 of
  the way to the block's target (`fs_rset`, `fs_r3`); a step that rounds to
  0 lands it on the target, and the first block of a mode starts it there.
  VOWL's morph fraction is 21 bits (5 until then). A knob at rest renders
  as before, except the cutoff under ENV or the LFO, which now follows them
  through the 1/128 ramp.

Every mpy is `mpy x0,y1` or `fs_qs`'s `mpy y0,x0`, the audited-signed
forms, but the VOWL decode's `mpy x1,y1,b` (R' > 0;
`build_bus.MPYSU_AUDITED`); every clip is the store limiter.

## SHPE's display

`shpe_fmt.s`, a ColdFire formatter cave (89 B) registered as page-2 slot
7's formatter (`fmt(buf, value)` → sprintf): "LP" at 0, "BP" at 64, "HP" at
127, `%d` elsewhere; the stored and delivered value stays 0..127. In LADR,
ISO and VOWL, whose MODE rename names the slot `---`, it prints the number:
it reads slot 7's name from the clone (`CLONE_SPECTRUM` + 0x40, a build
export), so its bytes depend on the clone's address and the source is the
only truth (a build without the m68k toolchain refuses). It is pinned at
`0x400c45b0`, the 338 B zero run (`docs/contributing/PLACEMENT.md`): the clone
window had 18 B left and the overflow run none, and floating it there
pushed MODULATION's 454 B label formatter out of both (the build refused).
midisc's own build used that run on hardware; in the remixer its
`enc_unlock` is DRAM.

## Sources

The laws; licences in `THIRD_PARTY.md`:

| mode | source | the law |
|---|---|---|
| SEM | audiojs/filter `oberheim` (Zavalishin's zero-delay form) | per block `g = tan(π fc/fs)`, `R = 1 − res`, `d = 1/(1 + 2Rg + g²)`; per sample `hp = (x − (2R+g)s0 − s1)·d`, `bp = g·hp + s0`, `s0 = bp + g·hp`, `lp = g·bp + s1`, `s1 = lp + g·bp`; notch = hp + lp. The state tanh (`s0 = tanh(s0)`, `s1 = tanh(s1)`, the SEM warmth) as two lookups per channel + a 33-pair table was TAME, removed 15 Sep 2026 |
| LADR | audiojs/filter `moogLadder` | ZDF 4-pole, `G = g/(1+g)`, `u = (x − k·S)·d`, four trapezoidal stages; the linear form (no `tanh(u·drive)`) |
| VOWL | Peterson & Barney (1952) | three parallel constant-peak resonators `y = b0 x + b2 x2 − a1 y1 − a2 y2`, `R = e^(−π bw/fs)`, `a1 = −2R cos w0`, `a2 = R²`, `b0 = (1−R²)/2`; /a/ = 730/1090/2440 Hz, bw 90/110/170, gains 1/0.5/0.3; 5 vowels × 3 formants × (a1, a2, b0) = 45 words of table with the FREQ morph; RES scales the bandwidths |
| ISO | Airwindows Capacitor2 | `capacitor2_ref.py` |

The SVF it replaced had `f` capped at 0.977 (a ~7.2 kHz cutoff ceiling if
`f = 2 sin(π fc/fs)`, inferred, not measured on the unit). Not ported: the
diode ladder (303; four state tanh + two tridiagonal solves per sample), an
8-stage tilt, a 2-shelf TILT (250 Hz / 2.5 kHz), Korg35, a lone resonator,
the RBJ core.
