A reverb for rooms, plates and halls, with a gate that works like a desk
gate on a reverb return: set GATE and the wash falls away quickly when the
input goes quiet, instead of a slow decay. It replaces GATE VERB, and a Part
that used GATE VERB opens with STUDIO VERB. The reverb is the reverb stage of Mutable
Instruments Clouds; the gate is new. Dry stays dry.

## Access

An effect on a track: select the track, press FX2, and pick STUDIO VERB from
the chooser. It is not in an official remix: build `octabam-verbs` (octabam with STUDIO VERB in place of
the stock reverbs) or the test remix `studioverb`.

![FX2 SETUP with Studio Verb selected: SIZE, LCUT, MOD, RATE and PRE on its page 2.](../../img/studioverb/setup.png)

*FX2 SETUP with Studio Verb selected: SIZE, LCUT, MOD, RATE and PRE on its page 2.*

## Operation

For the classic 1980s gated sound: TIME and DIFF high, GAIN up, AMNT up,
then raise GATE until the wash cuts the way you want.

GATE 0 is a normal (ungated) reverb. Above 0, the wet holds while the input
is loud; when it falls quiet, the wet holds for 52 ms (GATE 1) to 784 ms
(GATE 127) and then fades out the way a mixing-desk gate releases: down 60 dB
in about a third of a second. Once the gate has shut the reverb is emptied,
so every hit starts fresh and a backbeat sounds the same on every snare.
Hits closer together than the hold plus the fade keep the gate open, and
then the reverb carries on from one hit to the next.

## Parameters

| Knob | Default | What it does |
|---|---|---|
| AMNT | 45 | dry/wet. 0 is fully dry; up mixes in the reverb |
| GAIN | 51 | level into the reverb |
| TIME | 82 | how long the tail rings (0.35 to 0.98 loop gain) |
| DIFF | 100 | how smeared the tail is |
| TONE | 90 | damping: lower is darker, up is brighter |
| GATE | 0 | 0 is off. Up: after the input falls quiet, hold the wet for 52–784 ms, then fade it out like a desk gate |
| MODE | PLATE | page 2, first knob. A voicing: ROOM, PLATE, HALL or GATED. Turning it sets the other knobs to that voicing; adjust them from there |
| LCUT | 20 | page 2. Low cut inside the reverb: up thins the tail's low end so it sits in a mix; 0 is off |
| MOD | 64 | page 2. How much the tail is modulated: 0 is static, up is more chorus-like |
| RATE | 64 | page 2. How fast the modulation moves: 0 frozen, 127 twice the original |
| SIZE | 127 | page 2. The size of the space: down for a smaller room and a shorter, denser tail; 127 is the original |
| PRE | 0 | page 2, last knob, beside SIZE. Predelay, up to 92 ms, using the room SIZE leaves: none at SIZE 127, about 22 ms at 90, 40 ms at 60. Turn SIZE down to make room for it |

A Part saved with STUDIO VERB before page 2 existed opens with SIZE, MOD and RATE at 0, a small, static
room. Re-select the effect to get the defaults back.
