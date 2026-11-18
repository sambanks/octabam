# TRACK TRIG MODE

Each audio track keeps its own trig mode: CHROMATIC, SLOTS or SLICES.

- Hold FUNC and press UP / DOWN to pick a trig mode as usual. A CHROMATIC,
  SLOTS or SLICES pick is kept for the track you are on.
- Change track: the trig keys switch to that track's own mode.
- TRACKS, QUICK MUTE and DELAY CONTROL stay global: picked, they stay on
  whatever track you change to, and they are not kept for a track.
- Stepping out of TRACKS, QUICK MUTE or DELAY CONTROL with FUNC + UP / DOWN
  lands on the track's own mode and never overwrites it (a track with no
  mode yet keeps the pick). Only a step between CHROMATIC, SLOTS and SLICES
  changes a track's mode.
- A track you never picked a mode on takes whatever mode is showing.
- The modes are saved with the project (SAVE PROJECT, and project.work)
  and kept over a power cycle (battery RAM, as stock keeps its settings).
- When a project loads, and at power-up, the current track's own mode shows.

The project stores them as one comment line in `[SETTINGS]`:
`#TRIG_MODES=12300000` (T1..T8: 0 none, 1 CHROMATIC, 2 SLOTS, 3 SLICES).
Stock firmware skips `#` lines, so the project still loads on stock; stock
refuses a project with a key it does not know, which is why it is a comment.

Not done: MIDI tracks (MIDI mode is untouched).

27 Oct 2026, ACCLOOP14 on the MKI: the modes were saved but gone after a
power cycle. A power-up restores the project from battery RAM and never
parses project.work, and the table was in DRAM. It is now 8 bytes of
battery RAM (0x100f85e8).

28 Oct 2026, ACCLOOP16 on the MKI: stepping out of QUICK MUTE wrote the
mode it passed over onto the track (T1's SLICES became CHROMATIC). Fixed
as above in ACCLOOP17. The load hook also moved from the bank-read call
(0x40084d60) to just after it (0x40084d66): KITS tells the power-up's load
by that call's return address.

Measured under the port (`tools/verify/verify_track_trig_mode.py`): track
changes, QUICK MUTE staying global and its exit keeping the track's mode, the saved line, the saved project
parsing on the stock OS, reading it back, a power cycle. ACCLOOP15 on the
MKI: switching, save, reload, power cycle.
