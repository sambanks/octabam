Mute tracks per pattern as well as globally, as on the Digitakt II.

## Access

Double-press FUNC to switch the layer the next mute edit changes. A toast reads `GLOBAL MUTE` or `PATTERN MUTE`. In `octabam-core`, `octabam-inserts` and `octabam-bus`.

## Operation

| layer | a mute set here applies | saved |
|---|---|---|
| GLOBAL | in every pattern | with the project |
| PATTERN | in the pattern it was set in | with the pattern |

A track is muted when either layer mutes it. Mute edits are the stock ones: FUNC + track key, the MIXER trig keys, MIDI. The layer survives power-off.

While the PATTERN layer is active the current track's key also holds its second colour lit.

## Limits

- Only the current track's key shows the layer.
- An edit in one layer cannot unmute a track the other layer mutes.
