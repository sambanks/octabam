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

## Measured

- **10 Nov 2026, the simplify pass** (bit-identical: `make verify-ident
  MOD=modulation` 13/13; `verify_modulation` 30/30, `verify_stations_fx2`
  PASS, `verify-knobs` 131 cases 0 flagged). Instructions per sample from
  `dsp_host -meter` (LOFI 40, MIX 100, 16-sample blocks, the per-block work
  included; the same figures as the cost pass below on origin/main): JUNO
  212.9 → 206.2, DIM 258.8 → 252.1, FLNG 253.6 → 245.9, COMB 262.5 →
  256.1, PHSR 296.8 → 288.1. `cycle_count.py`: LINE 260 → 252, PHSR 298 →
  290, COMB 255 → 249; the priced worst core (four MODULATION beside the
  reverb and three sends) 2,331 → 2,299. Words 1,413 → 1,318. Not measured
  on the unit. Per sample: the frame advance is one `lua`; the write address
  goes straight into n5; `mo_tap` and `mo_herm` lost their entry reload
  (every caller enters with a0 = 0); LINE's four arm tests are one-word
  `tst`s on a flag the dispatch sets in n4 (+ FLNG, − DIM); LOFI's compare
  and PHSR's ramps carry their moves in parallel slots. Per block: the
  loops' shared registers are set once, before the dispatch; PHSR's two
  channels share `mo_pco`; the mode copy at $0c and reloads of values still
  in registers are gone. The P table is `modulation_ref.TABLE`, the same 148
  words the manifest used to list.
- **25 Oct 2026, the cost pass** (not bit-identical; `verify_modulation` 29/29
  at its original bars, `verify-knobs` 131 cases 0 flagged,
  `verify_stations_fx2` PASS). Instructions per sample from `dsp_host -meter`
  (LOFI 40, MIX 100, 16-sample blocks, the per-block work included): LINE
  JUNO / DIM / FLNG 316.9 → 212.9 / 258.8 / 259.8, COMB 298.5 → 262.5, PHSR
  296.8 (unchanged). `cycle_count.py`: LINE 330 → 266, COMB 291 → 255, PHSR
  298. Words 1,411 → 1,417. On the unit (octabam-inserts, 24 Oct 2026, slot
  cost as a share of a frame) JUNO / DIM / FLNG 10.0 %, COMB 9.5 %, PHSR 8.7 %;
  not measured since this pass. Changes: (1) the swept delays are a straight
  line per block (`mo_knot`) to what the LFO, WDTH, DPTH and DLY give `n7`
  samples on, and the loop adds the slope: the two per-sample triangles and the
  per-sample steps of wid and depth are gone (wid and depth glide per block,
  `mo_glide`); a triangle corner inside a block is cut to the chord, at most
  `slope * n7 / 2` of delay (3.2 samples at RATE 127, DPTH 127, DLY 64), and the first
  block after init or a MODE change starts on the end value; (2) the fixed taps
  (FLNG only) and the highpass and lift's lowpass (DIM only) are branched past
  in the other modes, with their states (`MODEARM` stretches, priced as the
  worst arm by `cycle_count.py`); `bl`, `kc` and `kb` are read from the r7
  block there, and L and R read one copy of `bd ff`; (3) `mo_herm` works from
  the successive differences in registers, 71 → 54 words and one scratch word
  instead of eight (the COMB walk is 9 words, not 17). `modulation_ref.py`
  models the block-linear sweep (`process(exact=True)` was the per-sample LFO
  until 10 Nov 2026; `LineModes.dev` measures the distance from it).
- **25 Oct 2026, on the unit** (I3 = hw/usb-standalone-transport + the pass above,
  MODULATION on all 8 tracks in one slot, per-slot cost = (layout - BASE) / 4, BASE
  22.5 % / 14.9 %; core 0 = core 1, FX1 = FX2): JUNO 7.2 %, DIM 8.76 %, FLNG 9.22 %,
  COMB 7.93 %, PHSR 8.65 %; `dear` costs what its mode costs. Caps at a 95 % limit:
  9.07 % core 0, 10.0 % core 1. FLNG was 0.15 over; its fixed-tap arm was then trimmed
  (the second channel reuses the first's address, the fraction waits in n3, bl is an
  immediate): 259.8 → 253.6 instructions a sample, 1,417 → 1,413 words. I4 (the same
  project and layouts): FLNG 8.95 %, 0.12 under the core-0 cap; the other modes and `dear`
  unchanged (JUNO 7.20, DIM 8.75, COMB 7.93, PHSR 8.65, `dear` 8.65 %).
- **5 Oct 2026, the cycles pass** (bit-identical, `make verify-ident
  MOD=modulation` 13/13): LINE 354 → 330, COMB 329 → 291, PHSR 298.
  The lines run as modulo-1024 rings in the two loops (`m5 = $3ff`, a
  stock modulo; every FX1 allocator base is 1024-aligned, `DSP.md`'s
  table, line R at +1024), so `mo_itap` and `mo_herm` step to the next
  delay with a post-decrement read instead of the add / and / n5 /
  (r5)+n5 / −n5 sequence per point.
- **27 Sep 2026, the cycle pass** (PR: mod-cycles): pricer per loop LINE
  404 → 354, PHSR 394 → 298, COMB 339 → 329 words/sample; the priced
  worst core beside the bus and the other FX1 stations 2,781 → 2,585 (four Characters beside the reverb now bound it;
  four JUNO + reverb + 3 sends 2,781 → 2,581), payload A FREE 87 → 138.
  Exact (13/13 `verify-ident` settings bit-identical): the walk pointers by
  `lua`, `mo_itap`/`mo_herm` read and step back in one move
  (`y:(r5)-n5,b`, a stock form), limited values moved straight into `y1`,
  one fixed-tap split shared by L and R (`n3`, `$44`). Within the bars, not
  bit-identical: LINE's eight one-poles as two products `c x + c' s` (c'
  streamed; the halved-difference form truncated one bit per sample) and
  PHSR's eight mod stages rolled two per trip with the stage inline (no
  limiting reload between the tap weights: one is set, the rest 0). Against
  main's render on the ident matrix the LINE settings differ by at most 6 LSB
  (−123 dBFS) and one PHSR setting by 1 LSB; every other setting is
  bit-identical. `verify_modulation` reference errors unchanged (JUNO
  2.33e-5 → 2.36e-5, PHSR hard 5.55e-5 → 5.53e-5); `make verify-knobs` 0
  flagged, 0 garbage-start flagged. Priced on a scratch edit, not applied:
  LOFI removed −18 words/sample in every loop (its inline hold and mask;
  LINE 336, PHSR 280, COMB 311); PHSR capped at 4 stages −68 (two trips of
  the roll: PHSR 230), which drops 6/8-stage phasing.
- **1,480 words** with the knob ramps (26 Sep 2026; payload A FREE 61
  beside the bus; pricer per loop LINE 404, PHSR 397, COMB 339 words/sample).
  Before them: 1,383 words (`make bus`, 23 Sep 2026; 1,352 on 22 Sep, 1,128 on 20
  Sep, LOFI added 16 Sep 2026: 1,044 before, 1,199 with ENS), payload A FREE
  673 beside the bus; pricer per loop PHSR 393, LINE 372, COMB 321 words/sample
  (489 / 423 / 361 on 22 Sep; 525 / 446 / 359 before the pointer rewrite).
  23 Sep 2026: the allpass stage passes x0 straight through (its entry and
  exit copies went, 20 calls per sample), the LFO, LOFI and MIX bodies are
  inline, the fixed taps' centre is split into i and f per block, c200, the
  COMB period−1 and trim are stream words, and six parallel moves with
  stock precedent; 13 settings (every MODE × two knob sets, zeros, max)
  bit-identical (`make verify-ident MOD=modulation`). The priced worst
  core (four PHSR beside the reverb) went 3,121 → 2,737 against 3,120
  usable. The loops are pointer-addressed since 22 Sep 2026 (PR #378):
  displaced moves per sample LINE 107, PHSR 136, COMB 116 → 0, the block's
  constants streamed at r7+$48 and the states walked from r7+$23; 15
  renders across every MODE bit-identical. A one-word displaced move runs
  3.98 cycles on the chip against 2.00 for a pointer move (probe 57,
  `docs/firmware/CHIP.md` section 2), which the word count cannot show.
- The 14 Sep 2026 build against its reading estimates: words were
  estimated 700..900 and came in 300 higher (the phaser's unrolled tap
  weighting is ~180 words per channel pair, the Hermite read 90); cycles
  were estimated ≈ 200 and came in 270 higher (the LFO shaping — the
  parabola sine is 17 instructions a call, six calls in ENS — and the
  one-poles are the difference). PHSR was retired 13 Sep 2026 at 464
  cycles and brought back on ChowPhaser's law.
- `tools/verify/verify_modulation.py`, **30 checks, all PASS** (10 Nov 2026): MIX 0
  bit-exact in every mode; an FX2 instance a bit-exact dry pass with the
  guard clean; every mode against `modulation_ref.py` on a stereo signal
  (max error ≤ 1e-4 where the law is linear; COMB's ring recirculates its
  rounding, 5.5e-4 against a 3e-3 bar); the Juno's sweep 1.56..5.10 ms and
  0.5 Hz; the through-zero null −138 dB; the phaser unity at FDBK 64; the
  comb's period at three pitches; LOFI against the reference at hold 7 / 24 bits
  (JUNO), hold 32 / 9 bits (PHSR), hold 64 / 5 bits (DIM), hold 40 / 8 bits
  through the ring (COMB) — the hold to the sample, the mask within one quantum.
- The LFO's increment is an integer count of 2^-23 cycles (the mpy keeps
  the integer part); the reference models that (a float increment drifts
  2.5 % at RATE 14).
- Output trims (16 Sep 2026, measured on the pad and the loop stems): each
  mode carries a trim that levels it with JUNO at the views: DIM −8 dB (its
  five weights scaled), FLNG −7 (blend and feedforward scaled; the feedback
  is FDBK's), PHSR −2 (the selected stage weight), COMB −12 (on the parked
  wet, after the line write, so the ring is untouched). After the trims,
  active RMS against JUNO: DIM −1.9 / +2.6 (pad / loop), FLNG −1.9 / +2.8,
  COMB +11.8 / +2.4, PHSR −1.4 / +4.5.
- Heard, 16 Sep 2026, on the emulator (`abkit`, the pad and loop stems,
  level-matched, Sam listening): JUNO "good", DIM "good", FLNG "good" at
  RATE 8 (the view was 14: "slower please"), COMB "sounds like what you
  describe" — kept, PHSR "pretty good". LOFI (same day): two placements
  rendered on JUNO over the loop at 90 — on the wet before MIX, and at the
  line write — Sam: "c please" (the line write).

## On the unit

- Image 88 (Sam's MKII, 27 Sep 2026): a fourth MODULATION beside the reverb
  overran the DSP; three fit. The cycle pass above prices four inside the
  budget, not measured on the unit since.
- Not listened to on the unit.

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

## Gates

`tools/verify/verify_modulation.py` (the manifest's), `make verify-ident
MOD=modulation`, `make verify-knobs`.

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
