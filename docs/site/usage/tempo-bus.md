In Octabam Bus, use the TEMPO window to view and edit the shared delay and
reverb controls.

## Controls

Press [TEMPO] to open a menu-sized window containing two boxes, DELAY and
REVERB, listing each engine's parameters with the same values shown on their
host pages.

| Control | Does |
|---|---|
| UP / DOWN | move the cursor a row in the focused box (the box scrolls, five rows visible) |
| A | edits the selected parameter on the host track (×7 while A is pushed is the stock fast turn) |
| B | the same as A |
| LEFT / RIGHT | focus DELAY / REVERB; each box keeps its own cursor |
| LEVEL | BPM in whole steps (×7 while LEVEL is pushed) |
| FUNC + LEVEL | BPM in 0.1 steps |
| FUNC + REC | copies the values of both boxes |
| FUNC + STOP | pastes the copy; FUNC + STOP again undoes the paste |
| scene A or B held + A or B | sets the held scene's lock on the selected parameter |
| scene A or B held + press A or B | removes the held scene's lock on the selected parameter |
| [TEMPO], [YES], [NO] | close |

## Copy and paste

FUNC + REC copies every parameter in both boxes, including MODE for both the
delay and the reverb. FUNC + STOP pastes those values onto the delay and reverb
host tracks of the current Part, so you can copy settings from one Part to
another. Pressing FUNC + STOP a second time undoes the paste; turning any knob
in the window clears the undo state. A toast confirms each action (BUS COPIED,
BUS PASTED, UNDO). The copied settings stay in memory until power-off. If
either engine is not assigned to any track in the current Part, its box is
skipped. When scene A or B is held, FUNC + REC and FUNC + STOP have no effect.

## Scene locks

Hold scene A or B and turn A or B to lock the selected delay or reverb
parameter to that scene. The crossfader then moves the parameter between
the two scenes' values, just as it does for knobs on the parameter pages.
While the scene is held, the boxes display that scene's locks. Pressing and
releasing A or B without turning removes the lock on the selected row.
You can open the window before or after pressing the scene key.

Page-2 parameters (MODE, TIME, TONE, and the rest of slots 6–11) use the
[page-2 scene locks](scenes-p2.md), which hold up to eight locks per scene
across all tracks.

The header displays the tempo as `TEMPO 121.2`, or `PTN 121.2` while pattern
tempo is active.

See the [delay's knobs](busdelay.md) and the [reverb's knobs](busverb.md) for
the full list of parameters shown in the boxes.
