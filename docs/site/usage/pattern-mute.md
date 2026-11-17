Mute tracks per pattern as well as globally, as on the Digitakt II.

## Access

Double-press FUNC to switch the layer the next mute edit changes. A toast reads `GLOBAL MUTE` or `PATTERN MUTE`. Only two FUNC presses with no other key between them switch it: FUNC + track or FUNC + trig pressed twice in quick succession does not.

## Operation

| layer | a mute set here applies | saved |
|---|---|---|
| GLOBAL | in every pattern | with the project |
| PATTERN | in the pattern it was set in | with the project, in `pmute.work` beside the bank files |

A track is muted when either layer mutes it. Mute edits are the stock ones: FUNC + track key, the MIXER trig keys, MIDI. The layer survives power-off, and so do PATTERN-layer mutes not yet saved.

While the PATTERN layer is active the current track's key also holds its second colour lit.

## Limits

- Only the current track's key shows the layer.
- An edit in one layer cannot unmute a track the other layer mutes.
- A copied pattern does not take its PATTERN-layer mutes with it.
- Projects saved with octabam 0.4 bring no PATTERN-layer mutes. In 0.4 the PATTERN layer shared storage with one-shot trigs on steps 1 and 2, so a one-shot there muted its track and a PATTERN-layer unmute deleted it. Those one-shots load as one-shots.
