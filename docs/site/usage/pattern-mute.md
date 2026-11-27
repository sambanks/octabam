PATTERN MUTE lets you mute tracks per pattern as well as globally, similar to
the Digitakt II.

## Access

Double-press FUNC to switch which mute layer your edits change. A toast reads
`GLOBAL MUTE` or `PATTERN MUTE`. Only two consecutive FUNC presses with no
other key in between switch the layer; pressing FUNC + track or FUNC + trig
twice in quick succession does not.

## Operation

| layer | a mute set here applies | saved |
|---|---|---|
| GLOBAL | in every pattern | with the project |
| PATTERN | in the pattern it was set in | with the project, in `pmute.work` beside the bank files |

A track is muted whenever either layer mutes it. You toggle mutes using the
standard controls: FUNC + track key, the MIXER trig keys, or MIDI. Both the
active layer and unsaved PATTERN-layer mutes survive a power-off.

While the PATTERN layer is active, the current track's key also lights up in
its second colour.

## Limits

- Only the current track's key indicates the active layer.
- Unmuting a track in one layer does not unmute it if the other layer still
  has it muted.
- Copying a pattern does not copy its PATTERN-layer mutes.
- Projects saved with octabam 0.4 do not retain PATTERN-layer mutes. In 0.4,
  the PATTERN layer shared storage with one-shot trigs on steps 1 and 2, so a
  one-shot there muted its track and a PATTERN-layer unmute deleted it. Those
  one-shots now load normally as one-shots.
