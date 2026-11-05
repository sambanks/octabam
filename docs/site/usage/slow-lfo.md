Stock LFO MULT goes no lower than 1X, so the slowest an LFO can go is SPD 1 at 1X.
This adds three values after 64X: 1/2X, 1/4X and 1/8X, a half, a quarter
and an eighth of 1X. They work on every LFO of the audio and MIDI tracks,
follow the tempo, and are saved in the Part like any MULT value.

## Operation

1. On a track, open LFO SETUP and turn MULT past 64X to 1/2X, 1/4X or 1/8X.
2. Set SPD as usual: the LFO takes 2, 4 or 8 times longer than at 1X, still
   in time with the tempo.
3. Turn MULT back to 1X–64X for stock rates.

## Notes

- 1X to 64X behave as stock, so existing projects load the same.
- A Part saved with 1/2X, 1/4X or 1/8X and opened on an image without this
  feature reads those values as very fast rates.
