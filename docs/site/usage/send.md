SEND is the bus client effect. It provides two knobs that route the track's
audio to the shared bus effects: **DEL** sets the send level to the delay on
track 1, and **REV** sets the send level to the reverb on track 5. Each
engine's wet output plays on the track hosting that engine. With both DEL and
REV at 0, the track passes through unchanged.

## Open Send

On every track except tracks 1, 5, and 8, FX2 is pre-assigned to SEND in new
Parts and cannot be changed in the FX2 chooser. Page 1 displays the two send
knobs.

## Set the sends

- Raise **DEL** to feed the track into the bus delay repeats, and raise
  **REV** to feed it into the reverb tail.
- The reverb can also receive the delay's repeats via the reverb's **DLY**
  knob (in the TEMPO window); raising DLY washes the delayed signal into the
  reverb tail.
- Track 1 and track 5 show these same two knobs on their FX2 pages: DEL feeds
  the delay and REV feeds the reverb.
- The delay follows the project tempo, and its **TIME** knob snaps to tempo
  divisions.

## Parameters

| Knob | Range | Default | Function |
|---|---|---|---|
| DEL | 0–127 | 0 | this track's level into the delay |
| REV | 0–127 | 0 | this track's level into the reverb |
