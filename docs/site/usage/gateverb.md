A gated reverb: a dense reverb wash that falls away quickly when the input
goes quiet, the way a desk gate on a reverb return does, instead of a slow
decay. The reverb is the reverb stage of Mutable
Instruments Clouds; the gate is new. Dry stays dry.

## Access

An effect on a track: select the track, press FX2, and pick GATE VERB from
the chooser. It is not in an official remix; build the test remix `gateverb`.

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
| AMNT | 40 | dry/wet. 0 is fully dry; up mixes in the reverb |
| GAIN | 51 | level into the reverb |
| TIME | 64 | how long the tail rings (0.35 to 0.98 loop gain) |
| DIFF | 100 | how smeared the tail is |
| TONE | 90 | damping: lower is darker, up is brighter |
| GATE | 0 | 0 is off. Up: after the input falls quiet, hold the wet for 52–784 ms, then fade it out like a desk gate |
