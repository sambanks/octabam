# `modulation` — MODULATION

A modulation pedal: Juno chorus, Dimension, through-zero flanger, a tuned
comb and a phaser, with a LOFI stage.

On id 0x0e (stock CHORUS keeps 0x12), FX1 only. Every mode is a transcription of a
published, permissively licensed source (Modes and Sources, below;
licences in `THIRD_PARTY.md`). Every mode outputs the wet only and MIX
blends, so MIX 0 is an exact passthrough and MIX 127 the wet outright.

**SLOTS** (build setting, store `octabam.modulation`): `FX1` (default) or `FX1+FX2`. With `FX1+FX2` an FX2 instance runs the station live and the FX2 chooser lists it; a remix pins it (`settings={("octabam.modulation", "SLOTS"): Pin("FX1+FX2")}`). `tools/verify/verify_stations_fx2.py` renders the FX2 instance against the FX1 instance, bit for bit (`remixes/test/stations-fx2`). A remix with the bus keeps the default: its cycle budget is priced with the stations on FX1.

## Knobs

| page | slot | name | range | law | in the modes |
|---|---|---|---|---|---|
| 1 | 0 | RATE | 0–127, default 26 | (k/128)² · 0x780 + 0x10 per sample in 2^23rds of a cycle: 0.08..10 Hz; 26 = 0.5 Hz | the LFO in JUNO/DIM/FLNG/PHSR; `---` in COMB (no LFO there) |
| 1 | 1 | DPTH ⌐ | 0–127, default 21 | 480 · k/128 samples either side of DLY, clamped inside the line (≤ DLY − 8, ≤ 1015 − DLY) | the sweep; in PHSR the LFO's reach into the LDR's law (0..1); `---` in COMB |
| 1 | 2 | DLY | 0–127, default 18 | 8 + 992 · k/128 samples (0.2..23 ms), capped 1000 | the centre; MANL in FLNG; the pitch in COMB (a 33-word table, 1000..8 samples exponential = 44 Hz..5.5 kHz); STGS in PHSR (2/4/6/8 by quarters) |
| 1 | 3 | FDBK | bipolar, default 64 | (k − 64)/64 | feedback from the swept tap into the line; the phaser's regen (clamped ±0.95); COMB's decay time (size) and polarity (sign) |
| 1 | 4 | LOFI | 0–127, default 0 | hold 1 + 64·(k/128)² samples (1 at 0, 17 at 64, 64 at 127 = 690 Hz); bits 24 below 64, then 16 12 10 9 8 7 6 5 by eighths of the travel | at the LINE WRITE in JUNO/DIM/FLNG (the taps read through the stairs) and COMB (the ring recirculates it); on the wet in PHSR. One hold counter for both channels. 0 is bit-exact |
| 1 | 5 | MIX | 0–127, default 0 | k/128, 127 = 1.0 | |
| 2 | 6 | MODE | JUNO / DIM / FLNG / COMB / PHSR | | |
| 2 | 7 | TONE | 0–127, default 80 | one-pole 0.25 + 0.75 · k/128, 127 = 1.0 (exact bypass); 0 = 2 kHz | the BBD proxy in AND out of every line (the Juno's ~10 kHz filters at 80); COMB's FIR brightness, drawn BRIT; `---` in PHSR |
| 2 | 8 | WDTH | 0–127, default 127 | the right channel's LFO lag, (k/128)/2 of a cycle: 0 mono, 64 quadrature, 127 antiphase | the Juno's and the Dimension's are antiphase; `---` in COMB |

Each mode's ModeView re-defaults the knobs to its source's numbers (the
Juno's I, the Dimension's mode 1, Dattorro's flanger, ChowPhaser's, Rings
at a mid pitch). MIX 127 and TONE 127 are pinned to 1.0 so the
through-zero null and the flanger's blend are exact (the knob word alone
is 127/128).

Stored parts: MODE bytes 3..5 (FLNG/COMB/PHSR) mean one lower since ENS
went; the page-1 order is RATE DPTH DLY FDBK LOFI MIX, page 2 MODE TONE
WDTH. `stamp-defaults` before play.

## Open

- DIM's amounts are ours; the Juno's own asymmetry (R 1.51..5.40 ms vs L
  1.54..5.15) and the I+II shape ("sine-like") are not modelled.
- The tap read is linear, blended toward the OLDER sample since 12 Sep 2026
  (the crackle fix). A chorus that reads darker at the sweep's extremes is
  the linear interpolation; the BBD proxy filter hides it. The
  alternatives: Dattorro's first-order allpass read ("all-pass
  interpolation for delay modulation becomes critical to the transparency
  of any chorus"; linear = a time-varying lowpass; THD+N: linear −78..−88
  dB, warped allpass −77..−85, unwarped −53..−59; TAL uses it) and
  Airwindows' 3-point read (weights 1−f, 1, f, × 0.5, minus 1/50 of the
  second difference) preceded by an "air" pre-emphasis (3 mul, 8 add a
  channel) that puts back the highs the averaging takes.

## Modes

| mode | source | licence | what it is |
|---|---|---|---|
| JUNO | jpcima `HeraChorus.dsp` + pendragon-andyh's Juno-60 measurements | ISC | two BBD lines on one triangle LFO, R inverted; I 0.513 Hz / II 0.863 Hz over 1.5..5.4 ms; I+II 9.75 Hz mono; dry 0.83 + wet 1.0 |
| DIM | Roland SDD-320 service notes + measurements | laws | antiphase lines, the other side's wet through a highpass, a bass lift on the dry; 0.25 / 0.5 Hz, 5..12 ms. The amounts (0.25 same-side, −1 cross, 0.5 lift, 200 Hz one-poles) are unpublished: **ours** |
| FLNG | Dattorro, *Effect Design Part 2* (JAES 1997), Table 6 | paper | blend 0.7071 of the dry read from a FIXED tap at the sweep's centre, feedforward −0.7071 of the swept tap (through-zero: the sweep crosses the dry and nulls), feedback −0.7071 |
| PHSR | ChowPhaser (Schulte Compact Phasing A) | BSD-3 | two RC allpasses (15 nF) with feedback, then 2/4/6/8 allpasses (25 nF) on one coefficient from the LDR's law (`R = 100k (light/0.1)^-0.75`, light = 20.1 − 20·lfo); the coefficient decoded per block from two 33-word tables and ramped per sample; the feedback closes through one sample; no tanh |
| COMB | Mutable Instruments Rings `string.h/.cc` | MIT | a Hermite-read loop tuned by DLY, a 3-tap FIR damping filter (brightness = TONE), the per-pass gain from a DECAY TIME (rt60 = 0.07 s · 2^(8·lf), lf = d(2−d)) so every pitch rings for the same time; no IIR damping (the MIC_W build's omission), no dispersion. FDBK's sign is the polarity: **ours**. Sam: "works, sounds good", 12 Sep 2026 (the earlier COMB) |

ENS (the Solina, jpcima `string-machine`) was mode 2 until 16 Sep 2026:
Sam heard the 6 Hz component as "super unnatural and dominating" and the
slow-only form as bad, and jpcima's own chorus on the same pad the same
way ("no good, lose it"). It is in history (`git log -- modules/modulation`).
PHSR, TREM, VIB and PAN were retired 13 Sep 2026 (the OT's LFOs do trem and
pan); PHSR came back 14 Sep. PHSR is the last MODE position so that
dropping it would move no other mode's stored byte; Sam kept it 16 Sep 2026
("pretty good").

## Structure

Three sample loops, one chosen per block (the pricer takes the worst): LINE
(JUNO, DIM and FLNG share it — the three differ only in five per-block
mix weights `bl bd ff kc kb`, and in which of the fixed taps (FLNG) and the
highpass and lift (DIM) the sample runs), PHSR, COMB. LOFI's hold + mask is
inline at its three sites per channel (L advances the shared counter and
latches on its compare, R latches on the counter reading 0; the mask keeps
bit 23 so the extension byte stays consistent and the store does not
saturate), as is the MIX. LINE's swept delays come from `mo_knot` once per
block (`mo_dly`: the triangle, depth and centre). Which of LINE's arms run is
a flag the dispatch sets in n4: + FLNG (the fixed taps), − DIM (the highpass
and the lift), 0 JUNO. Straight-line callees: `mo_tap` (the linear read,
blending toward the older sample; the fixed taps use it too since 26 Sep
2026, split per sample from the centre's run value, and R's fixed tap reuses
L's split through `mo_itrd`), `mo_herm` (the 4-point Hermite read from the successive differences,
scaled 1/16 inside), `mo_apst` (one allpass stage, x in and y out in x0 so a chain
passes it straight through; PHSR's eight mod stages carry it inline, two
per trip of a counted loop, since 27 Sep 2026), `mo_para` (the parabola
sine), `mo_pco` (one channel's PHSR coefficient ramps, per block),
`mo_tab` (the table read, per block; the P table is `modulation_ref.TABLE`,
which the manifest loads). The one-poles are
`s' = c x + c' s` with `c' = 1 − c` streamed beside `c`. The PHSR chain runs at half scale for headroom (an
allpass cascade peaks above its input).

Two lines of 1,024 words from the FX1 slot's allocator buffer (23 ms per
channel); an FX2 instance reads its base at init and runs as a dry pass
(`Claims(fx1_only)`, proven by the gates). A change of MODE clears the
per-sample walk (r7+$23..$3f); the write phase, the LFO phase, the LOFI
counter and the lines persist.

## Sources

The source laws each mode was transcribed from (14 Sep 2026 survey; the
departures are in Modes and Open):

- **JUNO** (Juno-60 measured by pendragon-andyh + jpcima ISC): two BBD
  lines, ONE triangle LFO, R's inverted; I = 0.513 Hz, II = 0.863 Hz,
  sweep 1.54→5.15 ms (L) / 1.51→5.40 (R); I+II = 9.75 Hz, 3.22→3.56 ms,
  mono; dry 0.83 + wet 1.0; BBD +2.3 dB; in/out filters ≈ 9.9 / 9.5 kHz
  5th-order (one-pole proxies in the practical ports: 7.2 k in, 10.6 k
  out).
- **DIM** (SDD-320 service notes + measurements, Synthbuilder, Fractal):
  two lines on one triangle LFO in ANTIPHASE (motionless: the mean delay is
  constant); 0.25 Hz (modes 1/2) / 0.5 Hz (3/4); sweep 5→12, 5→10, 6→9 ms;
  each output = bass-boosted dry + a little same-side wet + the OTHER
  side's wet through a HPF, inverted; mode 4 raises same-side. The mix and
  HPF constants are unpublished.
- **FLNG** (Dattorro Table 6/7 + Faust `flanger_mono`): blend =
  feedforward = 0.7071, feedback −0.7071 (max trough); delay 0→10 ms, the
  strong zone the first 1 ms; L/R the SAME phase; through-zero = the dry
  read from a FIXED tap at the sweep's centre, the wet inverted, so the
  sweep crosses it (McCurdy).
- **PHSR** (ChowPhaser BSD-3): Schulte: one feedback biquad (two RC
  allpasses collapsed, C 15 nF, fb ≤ 0.95, three tanh) then N first-order
  allpasses on one shared coefficient (C 25 nF), 3 MAC a stage; LDR: light
  = 20.1 − 20·lfo, R = 100 k·(light/0.1)^−0.75 → the whole coefficient set
  is a P-table on the LFO word; sine LFO 0..16 Hz, skew `2^s`. Departures
  here: the feedback through one sample, no tanh, the coefficient per block
  + ramp.
- **COMB**: departures here: without the IIR damping and dispersion, with
  a polarity sign.

Surveyed and not built:

- **WHITE** (a chorus variant, Dattorro Fig. 36): feedforward 1.0, blend =
  feedback = 0.7071, the feedback tapped at the FIXED centre (never the
  moving tap: modulated feedback pitch-shifts), so the chorus is an
  allpass at the centre; centre 400, width 350, 0.15 Hz, quadrature L/R.
- **PHSR alt.** (Faust `phaser2`, STK-4.3): 4 second-order allpasses, notch
  k at `fratio^(k+1)·θ`, R = e^(−π·width/fs), fb ±0.999, quadrature L/R.
- **VIBE** (Uni-Vibe, laws only: Rakarrack/guitarix, BYOD, Keen): four
  stages, C = 0.015 µ / 0.22 µ / 470 p / 0.0047 µ; LDR 500 kΩ dark → 600 Ω
  lit through a lamp one-pole (10 ms) and a cell with asymmetric TC (85 ms
  dark, 5 ms lit); BJT shaper per stage. No permissive code, every
  constant unproven.
- **VIB** (Airwindows StereoChorus / GalacticVibe, MIT): quadrature dual
  vibrato; GalacticVibe: fixed 0..254 samples, a NEW random rate each LFO
  cycle (0.43..0.70 × drift), Leslie-like; StereoChorus: depth ∝ 1/speed,
  L/R 1.98 rad apart.
- **FLUT** (Airwindows Flutter2, MIT): independent L/R LFOs, a random rate
  0.24..0.98 × per cycle; depth ≤ 90 ± 90 samples.
- **ENS** (jpcima string-machine BSL / Rings ensemble MIT / Haible):
  Solina: three taps on ONE mono line, two 3-phase sine LFOs summed, 0.6
  Hz × 0.5 + 6 Hz × 0.05..0.1; 5 ± 1 ms (TCA350, 185 stages); L = t1 + t2
  − t3, R = t1 − t2 − t3; 12 kHz 2nd-order input LP. Built, then dropped
  (Modes).
- Not portable: Airwindows Ensemble (2..48 taps each with its own sine),
  TakeCare (18 lines ≥ 4,626 words), StereoEnsemble (7,523-sample lines);
  the full Holters-Parker BBD (five complex poles a side); the proxy every
  practical port uses is a one-pole or a biquad each side of the line plus
  a soft clip.
- Not found anywhere permissive: a Uni-Vibe, a Dimension D clone, a
  through-zero flanger plugin, an Airwindows Flanger or Phaser (the 2007
  pages are Kagi-era AU with no source).
