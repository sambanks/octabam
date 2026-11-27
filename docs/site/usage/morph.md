MORPH automates scene morphing independently on individual audio tracks. Each
morphing track sweeps from scene A to scene B and back in sync with the
pattern, while other tracks continue to follow the crossfader. Every track has
its own cycle length and mode, and multiple tracks can morph at once. Once a
track is armed, holding its TRACK key for about a second toggles its morph on
and off, including from the MIXER page. This feature is inspired by the Korg
Electribe's Motion Sequence.

## Access

Hold one or more TRACK keys and press UP to open the MORPH window for those
tracks. Turn encoders A, B, and C to configure the cycle settings; the window
stays open after you release the keys. Press YES to close the window and start
morphing from scene A on the next step, or press NO to close without starting.
Either way, those tracks become armed: hold a TRACK key by itself for about a
second to start its morph, and hold it again to stop. Settings are saved
through STORE.

## Operation

- Each morph completes one A → B → A cycle every STEPS × x steps (16 × 8 =
  128 steps by default, up to 64 × 100). Because it counts sequencer steps,
  it never drifts from the pattern.
- Holding an armed track's TRACK key alone for about a second toggles its
  morph. If the track is idle, it starts from scene A on the next step (toast
  `T2 MORPH ON`). If it is already morphing, it finishes its current cycle on
  scene A and stops there (`T2 MORPH OFF`). This shortcut also works on the
  MIXER page, where the trig keys mute tracks.
- Pressing TRACK + UP on a track that is already morphing opens the MORPH
  window while it runs, and any edits take effect immediately.
- Pressing TRACK + DOWN lets the current cycle finish on scene A and parks
  the track there. The track resumes following the crossfader once the
  crossfader reaches the scene A end, preventing parameter jumps.
- Return controls (added in v1.2) live on encoders D, E, and F:
  - **RET** (D) sets how long the return from B to A takes: SAME (matching
    the rise time), 1/2, 1/4, 1/8, or 1/16 of the rise time, BAR, BEAT, STEP,
    or CUT (instant return to A).
  - **CURV** (E) shapes the motion: LIN is linear, HAND makes the return fast
    at first and gentle at the end (like pulling a fader by hand), RISE makes
    the ramp up slow at first and faster toward B, and BOTH applies both
    curves.
  - **END** (F) sets what happens at the end of a cycle: LOOP repeats
    continuously, ONCE runs a single cycle and parks on A, and STAY ramps up
    to B and holds there (status TOP) for riser effects until you hold TRACK
    for about a second or press TRACK + DOWN, after which it returns to A
    over RET and parks.
  - Choosing SAME, LIN, and LOOP matches the original v1.0 behavior exactly.
- The ramp up from A to B is always half of STEPS × x, so a shorter RET
  shortens the total cycle (for example, 16 × 8 with RET 1/4 gives 64 steps
  up and 16 steps back).
- STOP pauses the morph at its current position, and PLAY resumes it.
- Per-track settings, active morph states, and armed states are saved with
  the project (SAVE PROJECT stores a copy that RELOAD restores). After
  loading a project or powering on, tracks that were morphing start from
  scene A on the first step after PLAY.
- MIDI tracks continue to follow the crossfader. Discrete (select) parameters
  switch at the midpoint of the morph, just as they do with the crossfader.

## Controls

| Control | Does |
|---|---|
| TRACK + UP | open the MORPH window for the held tracks |
| YES (in the window) | close the window and start morphing on the next step |
| NO, UP (in the window) | close the window without starting (tracks remain armed) |
| TRACK held ~1 s | toggle an armed track's morph on or off; while held on B with STAY, return to A |
| TRACK + DOWN | finish the cycle on A and park there; while held on B with STAY, return to A |
| A | STEPS: TRK (matches track length) or 1..64 |
| B | x: 1..100 |
| C | MODE: SMOOTH (updates every frame) or HOLD (updates once per step) |
| D | RET: SAME, 1/2, 1/4, 1/8, 1/16, BAR, BEAT, STEP, CUT |
| E | CURV: LIN, HAND, RISE, BOTH |
| F | END: LOOP, ONCE, STAY |
| DOWN (in the window) | stop, same as TRACK + DOWN |

The title row shows the selected tracks and, on the right, the current state:
ARM (in the window), WAIT (starting on the next step), ON, STOP (finishing on
A), PARK, TOP (held on B), or RET (returning to A). The row below shows the
cycle length (`CYCLE 128`), the current step while running (`STEP 12/128`) or
returning after STAY (`BACK 2/4`), and on the right the two scenes with the
morph's position between them, matching the crossfader indicator in the main
page footer.

![MORPH window](../../img/morph/window.png)

![STEPS 8, x 2](../../img/morph/settings.png)
