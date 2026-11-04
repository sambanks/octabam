A track's scene morph, played by itself. The track moves from scene A to
scene B and back on its own, in time with the pattern, while the other
tracks keep the crossfader. Each track has its own cycle length and mode,
and several can morph at once. Inspired by the Korg Electribe's Motion
Sequence.

## Access

Hold a TRACK key and press UP: the MORPH window opens for the held tracks
and arms them. Turn A, B and C to set them, then release the TRACK key: the
window closes and the morph starts from scene A on the next step. Hold the
TRACK key and press DOWN to stop it. It saves through STORE.

## Operation

- The morph runs A → B → A once every STEPS × x steps (16 × 8 = 128 by
  default). It counts the sequencer's steps, so it never drifts from the
  pattern.
- TRACK + UP on a track that is already morphing opens the window over it:
  changes apply at once and the morph goes on.
- TRACK + DOWN lets the cycle finish on scene A, then the track stays
  parked on A. It follows the crossfader again once the crossfader reaches
  its A end, so nothing jumps.
- STOP holds the morph where it is; PLAY carries on.
- The settings of every track, and which tracks morph, are saved with the
  project (SAVE PROJECT keeps a copy that RELOAD brings back). After a project load or a
  power-up, the tracks that were morphing start from A on the first step
  after PLAY.
- MIDI tracks keep the crossfader. Select parameters jump at the middle of
  the morph, as with the crossfader.

## Controls

| Control | Does |
|---|---|
| TRACK + UP | open the window for the held tracks and arm them |
| release TRACK | close the window; armed tracks start on the next step |
| TRACK + DOWN | finish the cycle on A and park there |
| A | STEPS: TRK (the track's length) or 1..64 |
| B | x: 1..16 |
| C | MODE: SMOOTH (moves every frame) or HOLD (one value a step) |
| DOWN (in the window) | stop, as TRACK + DOWN |
| NO, UP (in the window) | close |

The bottom row shows the cycle (CYCLE 128 STEPS), or the step while the
morph runs (STEP 12 / 128). The MORPH row shows ARM (in the window), WAIT
(starting on the next step), ON, STOP (finishing on A) or PARK.

![MORPH window](../../img/morph/window.png)

![STEPS 8, x 2](../../img/morph/settings.png)
