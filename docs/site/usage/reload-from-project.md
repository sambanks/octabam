This module reloads a track or an entire pattern from the CF card without
stopping the transport.

## Operation

- **[PTN] + [TRACK n]**: Reload that track's sequence from the saved project.
- **[BANK] + [TRACK n]**: Reload that track's sequence along with its saved
  machine, FX, parameter pages, scene locks, and LFO designer. Every other
  track is left untouched.
- **[PTN] + [BANK] + trig**: Reload that pattern in the current bank,
  including all of its tracks and its Part. Reloading the currently playing
  pattern happens in place; choosing another pattern queues a pattern change
  that enters at CHAIN AFTER or at the end of the pattern (or on the next step
  when Direct Jump is active).

## Timing

- While the sequencer is playing, a track reload takes effect on that track's
  next step in time with the rest of the pattern, and that step already plays
  the reloaded sequence. A full-pattern reload takes effect on the next step
  shared by all of its tracks.
- With **[BANK] + [TRACK n]**, the track's machine and settings switch on the
  first trig of the reloaded sequence that plays a sample. If there is no such
  trig, they switch on the step where the reload takes effect.
- A saved pattern length or scale is restored the same way, keeping every
  track aligned with where it would be in the saved pattern.
- If you trigger multiple reloads before the change takes effect, all of them
  are queued, and the most recent reload for any given track wins.
- When the transport is stopped, a reload applies immediately.
- A toast notification confirms each reload when it takes effect.

## Trig conditions

- A reloaded track's trig conditions continue as if the saved sequence had
  been playing all along. A:B conditions count from the last time the
  pattern's conditions restarted (at PLAY or a normal pattern change), PRE
  restarts as it would on a pattern change, and FILL state is preserved.
  A Direct Jump (Kyoti) does not reset the condition counter, so a reload
  after a jump stays in step.
