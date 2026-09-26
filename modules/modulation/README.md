# MODULATION

A modulation pedal on stock CHORUS's id 0x12, FX1 only. Every mode is a
transcription of a published, permissively licensed source; the survey,
licences and laws are in `docs/effects/PORTS.md`.

| page 1 | RATE ⌐DPTH · DLY · FDBK · LOFI · MIX |
|---|---|
| page 2 | MODE (JUNO DIM FLNG COMB PHSR) · TONE · WDTH · — · — · — |

| mode | source | licence | what it is |
|---|---|---|---|
| JUNO | jpcima `HeraChorus.dsp` + pendragon-andyh's Juno-60 measurements | ISC | two BBD lines on one triangle LFO, R inverted; I 0.513 Hz / II 0.863 Hz over 1.5..5.4 ms; I+II 9.75 Hz mono; dry 0.83 + wet 1.0 |
| DIM | Roland SDD-320 service notes + measurements | laws | antiphase lines, the other side's wet through a highpass, a bass lift on the dry; 0.25 / 0.5 Hz, 5..12 ms. The amounts (0.25 same-side, −1 cross, 0.5 lift, 200 Hz one-poles) are unpublished: **ours** |
| FLNG | Dattorro, *Effect Design Part 2* (JAES 1997), Table 6 | paper | blend 0.7071 of the dry read from a FIXED tap at the sweep's centre, feedforward −0.7071 of the swept tap (through-zero: the sweep crosses the dry and nulls), feedback −0.7071 |
| PHSR | ChowPhaser (Schulte Compact Phasing A) | BSD-3 | two RC allpasses (15 nF) with feedback, then 2/4/6/8 allpasses (25 nF) on one coefficient from the LDR's law (`R = 100k (light/0.1)^-0.75`, light = 20.1 − 20·lfo); the coefficient decoded per block from two 33-word tables and ramped per sample; the feedback closes through one sample; no tanh |
| COMB | Mutable Instruments Rings `string.h/.cc` | MIT | a Hermite-read loop tuned by DLY, a 3-tap FIR damping filter (brightness = TONE), the per-pass gain from a DECAY TIME (rt60 = 0.07 s · 2^(8·lf), lf = d(2−d)) so every pitch rings for the same time; no IIR damping (the MIC_W build's omission), no dispersion. FDBK's sign is the polarity: **ours** |

Every mode outputs the wet only and MIX blends, so MIX 0 is an exact
passthrough and MIX 127 the wet outright. Each mode carries an output trim
that levels it with JUNO at the views (16 Sep 2026, measured on the pad and
the loop stems): DIM −8 dB (its five weights scaled), FLNG −7 (blend and
feedforward scaled; the feedback is FDBK's), PHSR −2 (the selected stage
weight), COMB −12 (on the parked wet, after the line write, so the ring is
untouched). After the trims, active RMS against JUNO: DIM −1.9 / +2.6
(pad / loop), FLNG −1.9 / +2.8, COMB +11.8 / +2.4, PHSR −1.4 / +4.5.

ENS (the Solina, jpcima `string-machine`) was mode 2 until 16 Sep 2026:
Sam heard the 6 Hz component as "super unnatural and dominating" and the
slow-only form as bad, and jpcima's own chorus on the same pad the same
way ("no good, lose it"). It is in history (`git log -- modules/modulation`).

## The knobs

| knob | law | in the modes |
|---|---|---|
| RATE | (k/128)² · 0x780 + 0x10 per sample in 2^23rds of a cycle: 0.08..10 Hz; 26 = 0.5 Hz | the LFO in JUNO/DIM/FLNG/PHSR; `---` in COMB (no LFO there) |
| DPTH | 480 · k/128 samples either side of DLY, clamped inside the line (≤ DLY − 8, ≤ 1015 − DLY) | the sweep; in PHSR the LFO's reach into the LDR's law (0..1); `---` in COMB |
| FDBK | bipolar, (k − 64)/64 | feedback from the swept tap into the line; the phaser's regen (clamped ±0.95); COMB's decay time (size) and polarity (sign) |
| MIX | k/128, 127 = 1.0 | |
| TONE | one-pole 0.25 + 0.75 · k/128, 127 = 1.0 (exact bypass); 0 = 2 kHz | the BBD proxy in AND out of every line (the Juno's ~10 kHz filters at 80); COMB's FIR brightness, drawn BRIT; `---` in PHSR |
| WDTH | the right channel's LFO lag, (k/128)/2 of a cycle: 0 mono, 64 quadrature, 127 antiphase | the Juno's and the Dimension's are antiphase; `---` in COMB |
| DLY | 8 + 992 · k/128 samples (0.2..23 ms), capped 1000 | the centre; MANL in FLNG; the pitch in COMB (a 33-word table, 1000..8 samples exponential = 44 Hz..5.5 kHz); STGS in PHSR (2/4/6/8 by quarters) |
| LOFI | hold 1 + 64·(k/128)² samples (1 at 0, 17 at 64, 64 at 127 = 690 Hz); bits 24 below 64, then 16 12 10 9 8 7 6 5 by eighths of the travel | at the LINE WRITE in JUNO/DIM/FLNG (the taps read through the stairs) and COMB (the ring recirculates it); on the wet in PHSR. One hold counter for both channels. 0 is bit-exact |

Each mode's ModeView re-defaults the knobs to its source's numbers (the
Juno's I, the Dimension's mode 1, Dattorro's flanger, ChowPhaser's, Rings
at a mid pitch).

## Structure

Three sample loops, one chosen per block (the pricer takes the worst): LINE
(JUNO, DIM and FLNG share it — the three differ only in five per-block
mix weights `bl bd ff kc kb`), PHSR, COMB. LOFI's hold + mask is inline at
its three sites per channel (L advances the shared counter and latches on
its compare, R latches on the counter reading 0; the mask keeps bit 23 so
the extension byte stays consistent and the store does not saturate), as
are the LFO and the MIX. Straight-line callees: `mo_tap` (the linear read,
blending toward the older sample; the fixed taps use it too since 26 Sep
2026, split per sample from the centre's run value; `mo_itap` is its
second entry), `mo_herm` (the 4-point Hermite read, scaled
1/16 inside), `mo_apst` (one allpass stage, x in and y out in x0 so a chain
passes it straight through), `mo_para` (the parabola sine), `mo_tab` (the
table read, per block). The PHSR chain runs at half scale for headroom (an
allpass cascade peaks above its input).

PHSR is the last MODE position so that dropping it would move no other
mode's stored byte; Sam kept it 16 Sep 2026 ("pretty good").

Two lines of 1,024 words from the FX1 slot's allocator buffer; an FX2
instance reads its base at init and runs as a dry pass (`Claims(fx1_only)`,
proven by the gates). A change of MODE clears the per-sample walk
(r7+$23..$3f); the write phase, the LFO phase, the LOFI counter and the
lines persist.

## Measured

- **1,480 words** with the knob ramps (26 Sep 2026; payload A FREE 61 in
  the rig; pricer per loop LINE 404, PHSR 397, COMB 339 words/sample).
  Before them: 1,383 words (`make bus`, 23 Sep 2026; 1,352 on 22 Sep, 1,128 on 20
  Sep, LOFI added 16 Sep 2026: 1,044 before, 1,199 with ENS), payload A FREE
  673 in the rig; pricer per loop PHSR 393, LINE 372, COMB 321 words/sample
  (489 / 423 / 361 on 22 Sep; 525 / 446 / 359 before the pointer rewrite).
  23 Sep 2026: the allpass stage passes x0 straight through (its entry and
  exit copies went, 20 calls per sample), the LFO, LOFI and MIX bodies are
  inline, the fixed taps' centre is split into i and f per block, c200, the
  COMB period−1 and trim are stream words, and six parallel moves with
  stock precedent; 13 settings (every MODE × two knob sets, zeros, max)
  bit-identical (`make verify-ident MOD=modulation`). The rig's priced worst
  core (four PHSR beside the reverb) went 3,121 → 2,737 against 3,120
  usable. The loops are pointer-addressed since 22 Sep 2026 (PR #378):
  displaced moves per sample LINE 107, PHSR 136, COMB 116 → 0, the block's
  constants streamed at r7+$48 and the states walked from r7+$23; 15
  renders across every MODE bit-identical. A one-word displaced move runs
  3.98 cycles on the chip against 2.00 for a pointer move (probe 57,
  `docs/firmware/CHIP.md` §2), which the word count cannot show.
- `tools/verify/verify_modulation.py`, **29 gates, all PASS**: MIX 0
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
- MIX 127 and TONE 127 are pinned to 1.0 so the through-zero null and the
  flanger's blend are exact (the knob word alone is 127/128).

## Heard

16 Sep 2026, on the emulator (`abkit`, the pad and loop stems, level-matched,
Sam listening): JUNO "good", DIM "good", FLNG "good" at RATE 8 (the view was
14: "slower please"), COMB "sounds like what you describe" — kept, PHSR
"pretty good". LOFI (same day): two placements rendered on JUNO over the
loop at 90 — on the wet before MIX, and at the line write — Sam: "c please"
(the line write). Not yet heard on the unit.

## Open

- DIM's amounts are ours; the Juno's own asymmetry (R 1.51..5.40 ms vs L
  1.54..5.15) and the I+II shape ("sine-like") are not modelled.
- The tap read is linear (Dattorro's allpass or Airwindows' 3-point + air
  are the alternatives, `docs/effects/PORTS.md`).
- Stored parts: MODE bytes 3..5 (FLNG/COMB/PHSR) mean one lower since ENS
  went; the page-1 order is RATE DPTH DLY FDBK LOFI MIX, page 2 MODE TONE
  WDTH. `stamp-defaults` before play.
