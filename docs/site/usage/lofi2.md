## What it does

One modulator — ring mod, or a stereo frequency shifter (SHIFT UP / SHIFT
DOWN) — into sample-rate and bit reduction and a high-shelf cut. An insert
on its own FX2 id, so stock LO-FI stays in the chooser beside it.

The defaults are a passthrough (MIX, FREQ, FDBK, SRR and BRR at 0, AMPH at
its centre, LPF at 127), so a fresh instance changes nothing until you turn
it.

## Where to find it

An effect on a track: select the track, press FX2, and pick LOFI2 from the
chooser. Page 1: FREQ, MIX, FDBK/GAIN, SRR, BRR, LPF. Page 2: RANGE, MODE,
AMPH. In octabam-inserts only.

## How to use it

- MIX is the modulator's depth, not a global wet/dry: SRR and BRR run after
  it and stay live at MIX 0.
- MODE on page 2 picks RING, SHIFT DOWN or SHIFT UP. Changing MODE ducks the
  wet briefly so the switch does not click.
- LPF 127 takes the shelf out of circuit.
- How many fit: SHIFT costs more than RING. Up to four SHIFT instances per
  core (the eight tracks run on two cores); all eight tracks in RING, and
  all eight in SHIFT, have run cleanly. An FX1 effect on the same track
  takes from the same core's budget.

## Knobs

| page | knob | range | what it does |
|---|---|---|---|
| 1 | FREQ | 0..127 | modulator frequency, exponential over six octaves; sweeps are smooth |
| 1 | MIX | 0..127 | modulator depth: crossfades the ring or shift against the dry |
| 1 | FDBK / GAIN | 0..127 | one knob, renamed per MODE. SHIFT: FDBK, the feedback ladder. RING: GAIN on the ring level, 0 dB at 0, +11.9 dB at 127 |
| 1 | SRR | 0..127 | sample-rate reduction (a hold), stock LO-FI's rates: no reduction through 7, 8,018 Hz at 64, 3,564 Hz at 127 |
| 1 | BRR | 0..127 | bit-depth reduction, stock LO-FI's curve: 1 bit at 0 through 3 bits at 16 to 2^20.8 at 127 |
| 1 | LPF | 0..127 | high-shelf cut, -12 dB above a corner swept from 100 Hz at 0 to 16 kHz at 126; 127 takes it out of circuit |
| 2 | RANGE | LOW / HIGH | FREQ's base: RING 2 Hz / 60 Hz, SHIFT 2 Hz / 31.25 Hz |
| 2 | MODE | RING / DOWN / UP | ring mod, or the shifter moving every partial down or up |
| 2 | AMPH | -64..+63 | ring carrier's left/right phase offset, -90 to +88.6 degrees; 0 at the centre. RING only |

## Screens

![The LOFI2 page: the four knob boxes](../../img/lofi2/main.png)

![The routing grid (page 2): source, destination and modulation](../../img/lofi2/setup.png)
