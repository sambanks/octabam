## What it does

A gated reverb: a dense reverb wash that cuts off sharply when the input
falls quiet, instead of decaying. The reverb is the reverb stage of Mutable
Instruments Clouds; the gate is new. Dry stays dry.

## Where to find it

An effect on a track: select the track, press FX2, and pick GATE VERB from
the chooser. In octabam-inserts only.

## How to use it

For the classic 1980s gated sound: TIME and DIFF high, GAIN up, AMNT up,
then raise GATE until the wash cuts the way you want.

GATE 0 is a normal (ungated) reverb. Above 0, the wet holds while the input
is loud; when it falls quiet, the wet holds for 52 ms (GATE 1) to 784 ms
(GATE 127) and then closes over about 3 ms. Only the wet is gated: the tail
keeps ringing underneath, so the next hit reopens it.

## Knobs

| knob | default | what it does |
|---|---|---|
| AMNT | 40 | dry/wet. 0 is fully dry; up mixes in the reverb |
| GAIN | 51 | level into the reverb |
| TIME | 64 | how long the tail rings (0.35 to 0.98 loop gain) |
| DIFF | 100 | how smeared the tail is |
| TONE | 90 | damping: up is more damping, a darker tail |
| GATE | 0 | 0 is off. Up: after the input falls quiet, hold the wet for 52–784 ms, then cut it sharply |

## Screens

![The GATE VERB page: the four knob boxes](../../img/gateverb/main.png)

![The routing grid (page 2): source, destination and modulation](../../img/gateverb/setup.png)
