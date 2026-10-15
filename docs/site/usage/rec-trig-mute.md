## What it does

Mutes a track's recorder trigs without deleting them.

## How to use it

Hold [TRACK] and press [NO]: the held tracks' recorder trigs stop firing
— a recording already running finishes — and a toast reads
`REC TRIGS MUTED`. [TRACK] + [YES] brings them back
(`REC TRIGS UNMUTED`).

- Works on any screen, grid recording or not.
- Holds across pattern changes until you unmute.
- Every track starts unmuted at power-on.
- A muted track shows two dots beside its play/stop icon at the screen
  edge.
- MIDI CC 80 on a track's channel: 0 unmutes, 1–127 mutes (AUTO channel =
  the active track), with AUDIO CC IN on. The keys send CC 80 on each
  held track's channel, with AUDIO CC OUT on.
- [TRACK] + [YES] / [NO] used to arm and disarm recorder one-shots; that
  stock gesture is now this instead. [FUNC] + [YES] / [NO] is unchanged.
