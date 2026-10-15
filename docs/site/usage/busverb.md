## What it does

The bus's reverb engine, hosted on track 5's FX2 (locked; the FX2 chooser
cannot change it). An eight-line reverb with ROOM, PLATE and BIG modes,
modulated taps, a shimmer, a gate and mid/side width. Every track's REV
send, plus the delay's repeats through its DLY knob, feeds it; its tail
comes out on track 5 under that track's dry.

## Where to find it

Track 5's FX2 page draws only DEL and REV. Every other knob is in the
TEMPO window: press [TEMPO], then LEFT / RIGHT to focus the REVERB box.

## How to use it

- DEL on track 5 sends track 5's own dry into the delay; REV sends it into
  the reverb.
- Tails: ROOM 0.87–3.9 s, PLATE 0.9–4.4 s, BIG 1.6–11.7 s across TIME
  0–127.
- TONE is LO and HI on one knob: 0–64 = low-pass, 64–127 = high-pass, 64
  flat.
- SHMR is the shimmer amount; SHFT its interval (-12, +5, +7, +12, +19,
  +24).
- GATE: 0 off; above 0 the wet shuts 52 ms (GATE 1) to 784 ms (GATE 127)
  after the tank input falls quiet — the 1980s gated-reverb cut.
- DLY is the delay's repeats into the reverb: 0 puts the two engines in
  parallel, up feeds more of the delay into the tail.

## Knobs

| page | knob | default | what it does |
|---|---|---|---|
| 1 | DEL | 0 | this track's dry into the delay |
| 1 | REV | 0 | this track's dry into the reverb |
| 1 | SIZE | 100 | scales the taps within the mode |
| 1 | SHMR | 0 | shimmer amount; 0 off |
| 1 | SHFT | +12 | shimmer interval: -12 / +5 / +7 / +12 / +19 / +24 |
| 1 | WET | 127 | wet level over the chain input |
| 2 | MODE | PLATE | ROOM / PLATE / BIG |
| 2 | TONE | 64 | 0–64 = low-pass, 64–127 = high-pass; 64 flat |
| 2 | DIFF | 80 | diffusion (allpass smear) |
| 2 | GATE | 0 | gated cut after the input falls quiet: 52–784 ms; 0 off |
| 2 | DLY | 127 | the delay's repeats into the reverb; 0 = the two engines in parallel |
| 2 | TIME | 64 | tail length |

## Screens

![The BUSVERB page on track 5](../../img/busverb/main.png)
