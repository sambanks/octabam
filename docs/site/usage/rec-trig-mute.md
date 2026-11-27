REC TRIG MUTE lets you mute a track's recorder trigs without deleting them.

## Operation

Hold [TRACK] and press [REC] to mute that track's recorder trigs. Any
recording already in progress finishes normally, and a toast displays
`REC TRIGS MUTED`. Press the same combination again to unmute them
(`REC TRIGS UNMUTED`).

- Each track keeps its own mute state. If you hold several track keys at once,
  each track toggles independently, and the toast reads `REC TRIGS TOGGLED`
  when they end up in mixed states.
- The toast stays visible while you hold the track key (for up to 1 second)
  and closes when you release it.
- While a track key is held, [REC] does not toggle grid recording. Pressed on
  its own, [REC] works as on stock firmware.
- The shortcut works from any screen.
- Mute states persist across pattern changes until you unmute them.
- Every track starts unmuted at power-on.
- A muted track's tab at the screen edge shows two vertical dots beside its
  machine letter on the inner side (to the right of the letter on tracks 1–4,
  and to the left on tracks 5–8). The play/stop icon below stays as on stock.
- With AUDIO CC IN enabled, MIDI CC 80 on a track's channel unmutes on 0 and
  mutes on 1–127 (the AUTO channel targets the active track). With AUDIO CC
  OUT enabled, the panel keys send CC 80 on each held track's channel (1 for
  muted, 0 for unmuted).
- [TRACK] + [YES] / [NO] and [FUNC] + [YES] / [NO] still arm and disarm
  one-shot trigs as on stock firmware.
