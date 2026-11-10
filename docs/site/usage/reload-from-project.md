Reloads a track, or a whole pattern, from the CF card without stopping
the transport.

## Operation

- [PTN] + [TRACK n]: reload that track's sequence from the project.
- [BANK] + [TRACK n]: the same, plus that track's machine, FX, pages,
  scene locks and LFO designer as the project was saved. Every other
  track is left alone.
- [PTN] + [BANK] + trig: reload that pattern of the playing bank, all
  its tracks and its Part. The pattern you are on reloads in place;
  another pattern is a pattern change, so it comes in at CHAIN AFTER or
  the pattern end (or at Direct Jump's next step when that is on).

## Timing

- While playing, a reload lands on the track's next step, in time with
  everything else. A whole pattern lands on the next step its tracks
  share.
- A saved length or scale comes back the same way, with every track
  carried on where the saved pattern would be.
- Several reloads before a landing all count; the latest one for a
  track wins.
- Stopped, a reload applies at once.
- A toast confirms each reload as it lands.
