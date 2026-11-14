## What it does

Jump from a step straight to its slice in the audio editor. In grid recording, hold a trig and press [BANK]: the editor opens on the sample that step plays, with the step's slice selected and the whole slice on screen, ready to edit.

## How to use it

1. Turn on grid recording ([REC]).
2. Hold the trig of the step you want and press **[BANK]**.
3. The audio editor opens on the SLICE page, on that step's sample (its sample lock, or the track's own sample) and on the slice the step plays.
4. While you hold the trig, the encoders edit that slice: A start, B loop, C end, D waveform height, E pan, F zoom. Release the trig and edit on as usual.

## Which slice it opens

- **SLIC on:** the slice the step's STRT picks, exactly the one the sequencer plays.
- **SLIC off:** the slice that starts where the step starts playing.
- **A sample without slices:** the view is centred on where the step starts playing.
- With no STRT lock on the step, the track's own STRT is used.

## Notes

- [BANK] on its own, and [TRIG] + [BANK] outside grid recording, work as usual.
- Without slices, STRT can only start the sample at 128 evenly spaced points, so a step may start a little after a hit. Slice the sample (with lazy-chop.md, say) to start exactly on the hits.
