Turns a scene into the Part's own sound, into step locks, or into a new scene.

## Apply a scene to the Part

Hold **SCENE A** (or **SCENE B**) and press **YES**. Every parameter that scene locks takes the scene's
value in the Part, as if you had turned each knob there yourself, and leaves the scenes assigned to A and B.
The Part's new value is then what plays, wherever the crossfader is. The other 14 scenes keep their locks.

**The commit is destructive.** The applied locks are gone from both scenes. Only **FUNC + CUE** (reloading the
Part) brings them back, and that also drops every other unsaved edit to the Part.

Hold **SCENE A** and **SCENE B** together and press **YES** to keep what the crossfader plays now: every
parameter locked in either scene takes its blended value. Where only one scene locks a parameter, the other
side of the blend is the Part's own value. Those parameters leave both scenes.

Scenes and the crossfader are for playing; **SCENE + YES** commits. To keep a fader position as a scene
instead, [save the blend](#save-the-blend-as-a-scene) and assign that scene.

Also:

- **TRACKS** in **PROJ > BRAIN > SETTINGS** chooses the tracks: **ACTIVE** (the active track, the default) or
  **ALL** (every audio track, each with its own scene locks).
- With [SCENES P2](scenes-p2.md) in the image, FX1's and FX2's page-2 locks are applied too. In a blend a
  page-2 select (a mode or on/off setting) takes A's value from the fader's middle up and B's below it.
- XVOL stays a scene lock, and the apply leaves it.
- **FUNC + CUE** undoes it, together with any other unsaved edit to the Part.
- `NOTHING TO APPLY` means no scene is assigned, or it has no locks.
- While **LIVE RECORDING** plays, **SCENE + YES** does nothing. Stop first, then apply.

## Step locks from a scene

In **GRID RECORDING**, hold one or more trig keys and press **SCENE A**, **SCENE B** or both. The held steps
of the active track lock every parameter the scene locks, at the scene's (or the blend's) value. Their other
locks stay.

Grid recording writes step locks only; it never removes scene locks, and it writes page 1 only.

## Save the blend as a scene

Hold **SCENE A** and **SCENE B** and press a trig key: that scene now holds the blend of every parameter
locked in A or B, page 2 included up to the eight page-2 locks a scene holds. This replaces stock's assign
while both scene keys are held. The scenes assigned to A and B
and the crossfader stay as they are.

## A new Kit from a scene

With [KITS](kits.md), **PTN + FUNC + RIGHT** copies the pattern and its Kit to the next empty ones. Then
**SCENE + YES** on the new pattern writes the scene into the copy, and the original Kit stays as it was. The new
Kit's A and B scenes lose those parameters, so it opens sounding like the scene.

- MIDI tracks keep the stock keys.
- With MASTER TRACK on, track 8's SRC and AMP are left alone.
