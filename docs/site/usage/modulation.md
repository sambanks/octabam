## What it does

A modulation pedal that replaces stock CHORUS: Juno chorus, Dimension,
through-zero flanger, a tuned comb and a phaser, with a LOFI stage on top.
MIX 0 is an exact passthrough; MIX 127 is the wet outright.

## Where to find it

Press FX1 on a track; MODULATION is in the chooser in place of CHORUS. In
octabam-inserts it is also on FX2; in octabam-bus it is FX1 only.

## How to use it

- MODE on page 2 picks the effect: JUNO, DIM, FLNG, COMB, PHSR. Selecting a
  mode re-defaults the knobs to its source's numbers.
- RATE is the LFO speed (0.08–10 Hz). DPTH is the sweep depth around DLY.
- DLY is the centre delay (0.2–23 ms); it becomes MANL in FLNG, the pitch
  in COMB (44 Hz to 5.5 kHz, exponential), and STGS (2/4/6/8 stages) in
  PHSR.
- FDBK is feedback; in PHSR it is the phaser's regen, in COMB its decay
  and polarity.
- LOFI degrades the sound: a sample hold (1–64 samples, down to 690 Hz)
  and bit reduction below 24 bits past 64. Placed on the delay line in
  JUNO/DIM/FLNG/COMB, on the wet in PHSR.
- TONE is a lowpass on the delay line (the BBD proxy); in COMB it is the
  brightness, drawn BRIT.
- WDTH sets the right channel's LFO lag: 0 mono, 64 quadrature, 127
  antiphase.
- How many fit: beside the bus, three run cleanly; a fourth overran the
  DSP on the unit (image 88, 27 Sep 2026).

## Knobs

| page | knob | range | default | what it does |
|---|---|---|---|---|
| 1 | RATE | 0–127 | 26 | LFO speed 0.08–10 Hz (26 = 0.5 Hz); no LFO in COMB |
| 1 | DPTH | 0–127 | 21 | sweep depth; the LFO's reach in PHSR |
| 1 | DLY | 0–127 | 18 | centre delay 0.2–23 ms; MANL in FLNG; pitch in COMB; STGS in PHSR |
| 1 | FDBK | bipolar | 64 | feedback; regen in PHSR; decay and polarity in COMB |
| 1 | LOFI | 0–127 | 0 | sample hold 1–64 samples and bit reduction; 0 is off |
| 1 | MIX | 0–127 | 0 | dry/wet; 127 is the wet outright |
| 2 | MODE | JUNO / DIM / FLNG / COMB / PHSR | | the effect |
| 2 | TONE | 0–127 | 80 | lowpass on the line (127 is an exact bypass); BRIT in COMB |
| 2 | WDTH | 0–127 | 127 | right LFO lag: 0 mono, 64 quadrature, 127 antiphase |

## Old projects

MODE's stored bytes 3–5 (FLNG/COMB/PHSR) mean one lower since ENS went.
Run `stamp-defaults` on the card before play.

## Screens

![The MODULATION page: the four knob boxes](../../img/modulation/main.png)

![The routing grid (page 2): source, destination and modulation](../../img/modulation/setup.png)
