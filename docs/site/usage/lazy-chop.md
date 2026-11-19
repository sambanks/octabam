## What it does

Chop a sample by ear: play it and tap the trig keys where you want the cuts. Each tap ends one slice and starts the next, up to 64 slices over four pages. The slices are ordinary Octatrack slices, edited, saved and played like any others.

## How to use it

1. Open the audio editor on the sample: [TRACK] + [BANK] for the track's sample, or [REC AB/CD] + [BANK] for a recorder buffer ([AED] on an MKII).
2. Go to the SLICE page ([AMP]), open the slice menu ([FUNC] + [BANK]) and pick **LAZY CHOP**, the first row.
3. Press **TRIG 1**: the sample plays from its start and slice 1 starts there.
4. Press **TRIG 2**, **TRIG 3** and so on in time with the music: each press cuts at the playhead. After TRIG 16 the page turns and TRIG 1 carries on with slice 17.
5. Press **[YES]** to keep the slices, or **[NO]** to put back the ones you had.

The trig keys light up while you chop: red for the slices made on this page, green for the next key to press.

## While chopping

| key | does |
|---|---|
| a red trig, short press | plays that slice |
| the last red trig, held | removes that slice (undo) |
| the green TRIG 1, held at a page start | goes back to the page before |
| the green trig after listening or undoing | plays from the previous slice, so you can hop back on the beat |
| [SCALE] (MKI) / [PAGE] (MKII) | ZERO SNAP on or off |
| [CUE] | LIVE CHOP or STUDIO CHOP |
| [YES] / [NO] | keep / cancel |

## Listening back and undoing

You don't have to get every cut right first time. While LAZY CHOP is open:

- **Listen to a slice:** a short press on a red trig plays that slice.
- **Undo the last cut:** hold the last red trig for just under a second (0.7 s). The slice is removed and that trig turns green again, ready to cut once more.
- **Undo across a page:** at the start of a new page, hold the green TRIG 1 to go back to the last slice of the page before. Keep holding red trigs to undo further.
- **Carry on:** after listening or undoing, press the green trig. Playback picks up from the start of the previous slice, so you hear the run-up and can hop back on the beat; the next press cuts as usual.

In LIVE CHOP, while the recording runs, red trigs don't play their slices, and holding the last red trig undoes it silently.

## Options

- **ZERO SNAP** moves every cut to the nearest zero crossing, so slices start without a click. It stays as you left it.
- **STUDIO CHOP** chops a sample that is already there. **LIVE CHOP** chops while you record: on a recorder buffer, TRIG 1 starts the recording and every cut lands at the record head. [YES] stops the recording and keeps the slices. Your choice stays across power-off.
- With the sequencer playing, the other tracks keep playing; the track you chop plays straight through.

## Notes

- With timestretch on (TSTR AUTO, NORM or BEAT), the first slice starts a few milliseconds in, because the Octatrack's timestretch needs that run-up to start cleanly.
- To chop a recording as it comes in, use LIVE CHOP: TRIG 1 starts the recording and every cut lands at the record head.
- The slices are kept with the project and with samples saved from the editor, like any slices. See also lock-edit.md, zoom-keep.md and src3-key.md.
