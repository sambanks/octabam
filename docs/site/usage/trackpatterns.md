TRACKPATTERNS lets each track play its own pattern from the active bank,
similar to launching clips. Pattern changes take effect at the end of that
track's loop so playback stays in time, while the other tracks, the global
pattern, and the active Part continue uninterrupted.

## Operation

| Action | Keys |
|---|---|
| Play pattern k on track n | Hold [TRACK n], hold [PATTERN], press [TRIG k] |
| Track n back to the global pattern | The same, with the global pattern's trig |
| Every track back | Any global pattern change (PATTERN + TRIG without a TRACK key, a chain, a bank change) |

Press [TRACK n] first, then [PATTERN]. A popup confirms the change (`T1 > A03`
or `T1 FOLLOWS`). In MIDI mode, the TRACK keys address M1–M8. While playing,
the change takes effect when the track wraps to step 1; while stopped, it
applies immediately and PLAY starts the pattern from step 1.

## What you see

- While [TRACK n] and [PATTERN] are held, the pattern trig keys highlight the
  pattern that track T_n is currently playing, as well as any queued pattern
  change for that track.
- When the current track is playing its own pattern outside GRID REC, its trig
  keys slowly blink that pattern's trigs from the active 16-step page behind
  the running playhead LED. In GRID REC, the trig keys still display the global
  pattern's trigs (the ones the keys edit), blinking slowly as a warning that
  this track is currently playing a different pattern.

## Limits

- Under SCALE MODE PER TRACK, each track loops at its own pattern length within
  the global pattern's MASTER LENGTH. Under NORMAL scale mode, every track
  wraps at the global pattern's length. Tempo, track speed, and sound settings
  stay tied to the active global pattern and Part.
- Editing and recording always apply to the global pattern.
- Per-track pattern assignments are not saved; reloading the project or cycling
  power returns every track to the global pattern.
