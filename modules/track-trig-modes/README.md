# `track-trig-modes` — TRACK TRIG MODES

Each track, T1–T8 and M1–M8, remembers its trig mode. Pick CHROMATIC on
T1 and SLICES on T2, and moving between them brings each one's mode back:
no FUNC + UP / DOWN on every track change. Crossing [MIDI] does the same
for the MIDI tracks.

- **Every mode is per track:** TRACKS, CHROMATIC, SLOTS (CHORDS on the
  MIDI tracks with CHORDS FACTORY), SLICES, QUICK MUTE, DELAY CTRL.
- **RAM only:** every track starts in TRACKS at power-up; nothing is saved
  to the project.

By 8thmyth. Works beside LAZY CHOP and CHORDS FACTORY: it stores the raw
mode number, so SLICES and CHORDS come back as they were.

## Hooks (OS 1.40C)

| site | kind | symbol | what |
|---|---|---|---|
| `0x40051f1e`, `0x40051f8e` | jsr | `ttm_set` | the list's two setters (`0x40051ee4`, `0x40051f54`), after `move.l (a0),0x460d16f0`: store the mode for the current track, then stock's box redraw `0x400359ac` |
| `0x40083c2e` | jmp, 12 bytes | `ttm_sel` | the track select `0x40083bf8`, its two track stores: replayed, then the track's mode, before stock's restage and redraw |
| `0x400555de` | jmp | `ttm_midi` | the [MIDI] key `0x40055548`, after stock's mode stash (`0x400c0aec`) and side / track swap: the new track's mode, before stock's page switch and redraw |

State: `ttm_mem`, 16 bytes (T1–T8, M1–M8, index `track + 8 × MIDI`),
in the DRAM runtime, zeroed at boot.

## Gates

- `tools/verify/verify_track_trig_modes.py [remix]` (MKI, port): ten panel
  scripts on a fresh project: track change, back again, [MIDI] both ways,
  QUICK MUTE and DELAY CTRL kept per track (audio and MIDI), the same track pressed again.
  It checks the trig mode and all sixteen slots.

## On the unit

Not yet.
