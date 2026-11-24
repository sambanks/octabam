In Octabam Bus, use the TEMPO window to view and edit the shared delay and
reverb controls.

## Controls

Press [TEMPO]: the window opens at the menu window's size, with two boxes,
DELAY and REVERB, listing each engine's knobs with the values the host
page would show.

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

FUNC + REC copies every parameter in both boxes: the delay's and the
reverb's, including MODE. FUNC + STOP writes them back to the delay and
reverb host tracks of the current Part, so a copy made in one Part pastes
into another. A second FUNC + STOP undoes the paste; turning a knob in the
window ends the undo. A toast confirms each (BUS COPIED, BUS PASTED, UNDO).
The copy is kept until power-off. A box whose engine
is on no track of the Part is skipped. With scene A or B held, FUNC + REC and
FUNC + STOP do nothing.

## Scene locks

Hold scene A or B and turn A or B to lock the selected delay or reverb
parameter to that scene. The crossfader then moves the parameter between
the two scenes' values, as it does for the knobs on the parameter pages.
While the scene is held, the boxes show that scene's locks. Pressing and
releasing A or B without turning removes the lock on the selected row.
You can open the window before or after pressing the scene.

Page-2 parameters (MODE, TIME, TONE and the rest of slots 6–11) use the
[page-2 scene locks](scenes-p2.md): a scene holds eight of them across
all tracks.

The header prints the tempo as `TEMPO 121.2`, or `PTN 121.2` while the
pattern tempo is on.

The [delay's knobs](busdelay.md) and the [reverb's knobs](busverb.md) list
what the boxes show.
