Each track can play its own pattern of the playing bank, clip style. A
change lands at the end of that track's own loop, so it stays in time;
the other tracks, the global pattern and the Part carry on.

## Operation

| Action | Keys |
|---|---|
| Play pattern k on track n | Hold [TRACK n], hold [PATTERN], press [TRIG k] |
| Track n back to the global pattern | The same, with the global pattern's trig |
| Every track back | Any global pattern change (PATTERN + TRIG without a TRACK key, a chain, a bank change) |

Press [TRACK n] first, then [PATTERN]. A popup names the change
(`T1 > A03`, `T1 FOLLOWS`). In MIDI mode the TRACK keys address M1–M8.
While playing, the change lands when the track wraps to its first step;
while stopped, it applies at once and PLAY starts it from step 1.

## What you see

- With [TRACK n] and [PATTERN] held, the pattern trig keys light the
  pattern T_n plays as the current one, and a change it has queued as a
  queued one.
- When the current track plays its own pattern, outside GRID REC its
  trig keys blink that pattern's trigs slowly over the running light,
  from the 16 steps its playhead is in. In
  GRID REC the trigs shown are still the global pattern's (the ones the
  keys edit), and they blink slowly as a warning that this track does not
  play them.

## Limits

- The track loops at its own pattern's length under SCALE MODE PER
  TRACK, inside the global pattern's MASTER LENGTH; under NORMAL every
  track wraps at the global pattern's length. Tempo, track speed and the
  sound stay the playing pattern's and Part's.
- Editing and recording address the global pattern.
- Not saved: after a reload or a power cycle every track follows the
  global pattern again.
- Beside Kits and Direct Jump (Kyoti) (`trackpatterns-core`): on an MKII
  the gesture, a global change and a save and power cycle passed; Kits' and
  Direct Jump's own actions have not been tried beside it. This report
  predates the remix's EDIT EVENTS integration.
