# `apply-scene` — APPLY SCENE

Turns a scene into the Part's own values, into step locks, or into another scene:

| gesture | where | what it writes |
|---|---|---|
| SCENE A + YES, SCENE B + YES | any page, not recording | that scene's locks become the edited Part's values, as if each knob were turned to them, and those parameters leave the two assigned scenes (the commit) |
| SCENE A + SCENE B + YES | the same | the crossfader's blend of the two scenes becomes the Part's values, and those parameters leave both scenes |
| trig keys held, SCENE A (or B, or both) | GRID RECORDING | the same values as step locks on the held steps of the edited track; the trigs stay |
| SCENE A + SCENE B + trig k | any page | the blend saved into scene k |

Credit: Nathaniel Pavel ([npp1993](https://github.com/npp1993)) designed Apply Scene for Modwerk
([repeat98/modwerk](https://github.com/repeat98/modwerk) `sdk/octatrack/modules/apply-scene`, MIT): SCENE + YES
into the Part, both scenes for the blend, held trigs + SCENE as step locks. This module reimplements that
behaviour from its description; no source is copied or linked. The commit, saving the blend into a scene, page 2
and the TRACKS setting are added here.

## Using it

- **Which values.** Page 1 of the eight audio tracks: SRC, LFO, AMP, FX1 and FX2; with
  [SCENES P2](../scenes-p2/README.md) in the image, FX1's and FX2's page 2 too (its locks, made with a scene
  held on an FX SETUP page). A scene writes only the parameters it locks. The blend writes every parameter locked in A or B; where only one scene locks it, the
  other side is the Part's own value, as the crossfader plays it. The blend follows XF CURVE and MORPH, and a
  scene muted with FUNC + SCENE is left out of it. On page 2 a select (a MODE-like setting) takes A's value
  from the fader's middle up and B's below it, as SCENES P2 plays it.
- **The commit.** Every parameter an apply writes is unlocked in the scenes assigned to A and B, so the
  Part's new value is what plays wherever the crossfader is. The other 14 scenes keep their locks. Two paths,
  then: scenes and the fader to play, SCENE + YES to commit. To keep a fader position as a scene instead, save
  the blend (below) and assign that scene.
- **What stays.** XVOL (the scene level) stays a scene lock, and the commit leaves it. Step locks and LFOs are not
  folded into the Part.
- **Undo.** FUNC + CUE reloads the Part (with KITS, the Kit), which also drops any other unsaved edit.
- **A Kit from a scene.** PTN + FUNC + RIGHT copies the pattern and its Kit to the next empty ones (KITS), then
  SCENE + YES on the new pattern writes the scene into the copy; the original Kit is left as it was.
- **TRACKS** in PROJ > BRAIN > SETTINGS: ACTIVE (the edited track, the default) or ALL (every audio track,
  each with its own scene locks). It applies to SCENE + YES. Grid recording
  writes the edited track's held steps, and saving the blend writes the whole scene.
- **Saving the blend.** With both scene keys held a trig key saves instead of assigning: stock assigns the
  trig to the scene key pressed last. Scene k gets every parameter locked in A or B at the blend; XVOL only
  when both lock it. Page 2 the same, up to the eight locks a scene holds (SCENES P2): any past the eighth are
  left out. With nothing locked in A or B, scene k is left as it was.
- `NOTHING TO APPLY` when nothing would change: no scene assigned, or no lock in it.
- MIDI mode, and the MIDI tracks, keep stock's keys. With MASTER TRACK on, track 8's SRC and AMP are left
  alone.

## How it works

No detours and no code in the sequencer tick or the frame: everything runs in the UI task, in key handlers,
where stock's own handlers and toasts run.

- **The keys.** Holding a scene key pushes its input layer (SCENE A `0x400bb2a2`, SCENE B `0x400bb2b6`, one
  each for both models). `keys_inc` builds each layer a table of its own from the user's 1.40C: stock's
  encoder and REC/STOP/PLAY records copied, the sixteen trig records wrapped (`aps_trig_a`, `aps_trig_b`:
  stock's assign `0x40052a18` / `0x40052944` unless both scene keys are held) and a YES record added
  (`aps_yes`, press and release; no repeat, as stock's YES). Two SymbolRefs point the layers' keys fields at the tables.
  YES without a scene key, or in MIDI mode, goes to the base layer's own YES record (found from the layer list
  `0x460d165c`), so ARM ALL and anything that detours it are unchanged. CUE with a scene key held is stock's.
- **The press.** The four base SCENE records' press (MKII `0x400c051a`, `0x400c0534`, MKI `0x400bff36`,
  `0x400bff50`) goes through `aps_scene_press`, which writes the step locks in GRID RECORDING when trig keys
  are held (`0x460d174a`) and then calls stock's press `0x4004348c`.
- **The Part.** Values go through stock's page-1 writer `0x40054cd8(track, flat, value)` (the Part, its
  battery copy, the live lane, the range), then the Part's unsaved bits, the edited flags and the redraw.
- **Page 2.** SCENES P2 keeps a scene's page-2 locks as eight cells shared by its tracks, in bytes 30-31 of
  its 32-byte rows (key `track<<4 | fx1<<3 | slot`, value). Values go to the Part (`+0x8f07e + t·30`, FX2's
  at `+0x8f084`), its battery copy and the live lane `0x80000842 + t·72`, the stores of stock's page-2
  editors (`docs/firmware/MAINMENU.md` section 7). A cell is emptied first, then given its value, then its
  key, since SCENES P2's frame pass reads the key first; then `p2s_changed` drops its cache. Which page-2
  slots are selects comes from the effect's descriptor (fewer than 128 values), FX2's table the remix's.
  Without SCENES P2 (`APS_P2` 0) page 2 is never read or written.
- **The commit.** The scene bytes in the Part and their battery copy, the flag `0x460c80f0`
  reset as stock's scene write `0x40025b40` does, then `0x40002df4(bank, Part, scene, side)` for each side showing a
  changed scene. It copies all 32 bytes, unlocked ones included, into the morph's working copy `0x80000ed4`
  for each track playing this bank and Part, so a parameter the commit unlocked stops following the fader at once.
- **The blend.** `(A·wA + B·wB + 0x4000) >> 15` with the track's weights at `0x80003c60`, which the frame
  builder uses, so the result is what the fader plays, rounded to a whole step.
- **Step locks.** The lock bytes and their battery copy (`STEP_LOCKS.md`), then the lock editor's own closing
  sequence, so a held trig released afterwards keeps its trig (`modules/plocks-p2/DEVELOPMENT.md`).
- **A saved scene.** The 8 × 32 bytes go to the Part's scene and its battery copy the same way, and to the
  engine when k is the A or B scene.

The engine (`apply.c`) is C, tested on the host by `verify.py`; `generate.py` builds `apply_unit.s` from it,
`adapter.c` and `hooks.s`. `tools/verify/verify_apply_scene.py` drives the panel under the port. Under a live
script no track plays a Part, so the gate reads the scenes in the Part, not the working copy; that the commit
reaches the engine rests on reading `0x40002df4`.

## Limits

- Page 2 goes to the Part and into scenes, not to steps: grid recording writes page 1 only
  (PLOCKS P2 keeps page-2 step locks in a table of its own).
- Grid recording writes step locks and never removes scene locks.
- No live recording: while LIVE RECORDING plays, SCENE + YES does nothing (stock's page-1 writer would
  record the values on the trig being played instead of the Part). Stop first, then apply.
- A trig in GRID RECORDING takes the values when the SCENE key is pressed: pressing the other scene key
  afterwards writes the blend over them.
