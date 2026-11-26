VERBERATION is a room, plate, and hall reverb with a built-in gate modeled on
a mixing-desk gate placed on a reverb return. Raising GATE makes the reverb
tail cut off quickly once the input falls quiet rather than decaying slowly.
The reverb stage is based on Mutable Instruments Clouds, paired with a new gate
stage; the dry signal is unaffected by the gate.

## Access

Select a track, press FX2, and choose VERBERATION from the chooser. It is
included in [Octabam Verbs](../../remix-octabam-verbs.md), replacing the three
stock reverbs.

VERBERATION has four modes (ROOM, PLATE, HALL, and 80S), selected with MODE on
page 2. Each mode changes the reverb algorithm, and switching MODE also loads
default values for the other knobs:

- **ROOM** adds early reflections: a dense, wide burst in the first 20 ms ahead
  of the tail, giving the impression of nearby walls.
- **PLATE** is the standard plate reverb.
- **HALL** modulates two of the reverb's delay lines against each other so long
  tails drift and spread.
- **80S** produces a 1980s gated snare sound. Its gate triggers on each hit
  rather than overall loudness, giving every hit a single burst of reverb that
  then cuts off even over a continuous loop or held pad.

GATE works in every mode. In ROOM, PLATE, and HALL, it opens whenever the input
is loud.

Projects saved with stock reverbs open automatically on VERBERATION: PLATE REV
maps to PLATE mode, SPRING REV maps to ROOM mode, and DARK REV maps to HALL
mode, each loaded with that mode's default knob settings. A Part converts when
it is loaded or played, and saving the project keeps the converted settings.

![FX2 SETUP with Verberation selected: MODE (here PLAT), LCUT, MOD, RATE, SIZE and PRE on its page 2.](../../img/verberation/setup.png)

*FX2 SETUP with Verberation selected: MODE (here PLAT), LCUT, MOD, RATE, SIZE and PRE on its page 2.*

## Operation

For a classic 1980s gated reverb, turn MODE to 80S, or set it up manually by
turning TIME and DIFF high, raising GAIN and AMNT, and adjusting GATE until the
tail cuts off where you want.

Up to 64, AMNT keeps the dry signal at full level while bringing in the reverb,
so both are at full level at 64. Past 64, the dry signal fades out until 127
leaves only the reverb. GAIN controls how hard the input drives the reverb,
acting as a second wet level control.

Pressing STOP twice (stop and rewind) clears the tail just like the stock
reverbs, returning the track to dry and emptying the reverb buffer so nothing
rings out when playback resumes.

At GATE 0, the reverb runs ungated. Above 0, the wet signal stays open while
the input is loud; once the input goes quiet, the wet signal holds for 52 ms
(GATE 1) to 784 ms (GATE 127) and then fades out by 60 dB over about a third of
a second, like a mixing-desk gate release. Once the gate shuts, the reverb
buffer is emptied so every hit starts clean and repeated backbeat snares sound
consistent. Hits spaced closer together than the hold plus fade time keep the
gate open, allowing the reverb to carry from one hit to the next.

## Parameters

| Knob | Default | What it does |
|---|---|---|
| AMNT | 35 | Wet/dry mix. 0 is fully dry. Up to 64, the reverb blends in under the full-level dry signal; above 64, the dry fades out until 127 is reverb only |
| GAIN | 51 | Input level sent into the reverb |
| TIME | 82 | Tail decay length (0.35 to 0.98 loop gain) |
| DIFF | 100 | Diffusion (how smeared the tail is) |
| TONE | 90 | Damping: lower is darker, higher is brighter |
| GATE | 0 | Gate hold time. 0 is off; above 0, holds the wet signal for 52–784 ms after the input falls quiet, then fades out like a desk gate |
| MODE | PLATE | Page 2, first knob: ROOM, PLATE, HALL, or 80S (see above). Changing it also loads default values for the other knobs |
| LCUT | 20 | Page 2. Low-cut filter inside the reverb; raising it thins the low end so the tail sits in a mix (0 is off) |
| MOD | 64 | Page 2. Tail modulation depth: 0 is static, 64 adds gentle movement to prevent metallic ringing, and 127 is about four times deeper for noticeable detune on long tails |
| RATE | 64 | Page 2. Modulation speed: 0 is frozen, 64 is slow (under 1 Hz), and 127 is about four times faster |
| SIZE | 127 | Page 2. Space size: lower for a smaller room and shorter, denser tail; 127 is the full original size |
| PRE | 0 | Page 2, last knob (beside SIZE). Predelay from 0 to 69 ms at any SIZE. At large SIZE settings, long predelay slightly shortens the tail because it shares memory with the reverb |

A Part saved with VERBERATION before page 2 existed opens with SIZE, MOD, and
RATE at 0, producing a small, static room. Re-select the effect to restore the
current defaults.
