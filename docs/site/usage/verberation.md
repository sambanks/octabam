A reverb for rooms, plates and halls, with a gate that works like a desk
gate on a reverb return: set GATE and the wash falls away quickly when the
input goes quiet, instead of a slow decay. The reverb is the reverb stage of Mutable
Instruments Clouds; the gate is new. Dry stays dry.

## Access

An effect on a track: select the track, press FX2, and pick VERBERATION from
the chooser. It is in [Octabam Verbs](../../remix-octabam-verbs.md), in place of the three stock
reverbs.

It is one reverb with four presets: ROOM, PLATE, HALL and 80S, picked with MODE on
page 2. MODE only sets the other knobs; the reverb itself never reads it. 80S is the
1980s desk-gated snare: a big, bright tank with GATE turned up and a short predelay so
the hit stays ahead of the wash. Every preset can use GATE. The chooser also shows VERB PLATE, VERB ROOM and VERB HALL, on the rows the stock
PLATE, SPRING and DARK REV had. They are not other reverbs: each is VERBERATION with MODE
already set. They are there so a project saved with a stock reverb opens on a matching
voicing (below).

![FX2 SETUP with Verberation selected: MODE (here PLAT), LCUT, MOD, RATE, SIZE and PRE on its page 2.](../../img/verberation/setup.png)

*FX2 SETUP with Verberation selected: MODE (here PLAT), LCUT, MOD, RATE, SIZE and PRE on its page 2.*

## Operation

For the classic 1980s gated sound, turn MODE to 80S, or by hand: TIME and DIFF high,
GAIN up, AMNT up, then raise GATE until the wash cuts the way you want.

AMNT keeps the dry at full level while it brings the reverb in: at 64 both are at full
level. Past 64 the dry fades out, and at 127 only the reverb is left. GAIN sets how hard
the input drives the reverb, so it works as a second wet level.

STOP, STOP (stop and rewind) cuts the tail, as it does on the stock reverbs: the track
goes dry and the reverb is emptied, so nothing rings on when it plays again.

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
| AMNT | 35 | the mix. 0 is fully dry. Up to 64 the reverb comes in under the dry, which stays at full level; past 64 the dry fades out, and 127 is reverb only |
| GAIN | 51 | level into the reverb |
| TIME | 82 | how long the tail rings (0.35 to 0.98 loop gain) |
| DIFF | 100 | how smeared the tail is |
| TONE | 90 | damping: lower is darker, up is brighter |
| GATE | 0 | 0 is off. Up: after the input falls quiet, hold the wet for 52–784 ms, then fade it out like a desk gate |
| MODE | PLATE | page 2, first knob. A preset: ROOM, PLATE, HALL or 80S. Turning it sets the other knobs to that preset; adjust them from there |
| LCUT | 20 | page 2. Low cut inside the reverb: up thins the tail's low end so it sits in a mix; 0 is off |
| MOD | 64 | page 2. How much the tail is modulated: 0 is static, 64 a gentle movement that keeps the tail from ringing metallic, 127 about four times that, a clear detune in a long tail |
| RATE | 64 | page 2. How fast the modulation moves: 0 frozen, 64 slow (under 1 Hz), 127 about four times that |
| SIZE | 127 | page 2. The size of the space: down for a smaller room and a shorter, denser tail; 127 is the original |
| PRE | 0 | page 2, last knob, beside SIZE. Predelay, 0 to 69 ms, at any SIZE. At large SIZE settings a long predelay shortens the tail a little, because it takes its memory from the reverb |

A Part saved with VERBERATION before page 2 existed opens with SIZE, MOD and RATE at 0, a small, static
room. Re-select the effect to get the defaults back.
