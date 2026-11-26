STEMS records multitrack audio directly to the CF card while the sequencer
plays, capturing every post-fader track, the main mix (MAIN), the cue mix
(CUE), and the four external inputs in 16-bit or 24-bit WAV format at
44,100 Hz. Audio streams to the card as it records, for up to 60 minutes per
take.

Each take is saved in its own folder under `AUDIO/!STEMS/` (sorted first in
the file browser), named `YYMMDD-HHMM`, with each selected source written as a
separate WAV file prefixed by the take name: `YYMMDD-HHMM-T1.wav` through
`-T8.wav`, `-MAIN.wav`, `-CUE.wav`, and inputs as `-AB.wav` / `-CD.wav`
(stereo) or `-A.wav` through `-D.wav` (mono). Additional takes started within
the same minute are numbered `YYMMDD-HHMM-2`, `YYMMDD-HHMM-3`, and so on, so
existing takes are never overwritten. Takes already stored on the card in an
older folder layout remain untouched.

Each track file captures that track's contribution to MAIN, scaled by its mix
gain, so track level, MAIN LEVEL, scenes, and crossfader movements are baked
into the recording.

## Access

Hold **UP** and press **REC** (press UP first) to open STEMS, and press the
same chord again to close it. Pressing REC alone still toggles stock grid
recording, and MAIN MENU is unchanged. This module is not included in the
standard remixes; build the `stems` remix to use it.

## Operation

STEMS uses the same five-row list layout as SYSTEM > PERSONAL SETTINGS, where
each row shows a label and a value. Use UP and DOWN to navigate, YES to toggle
or activate the selected item, and NO to close the menu. The rows, from top to
bottom, are:

| Row | Shows | YES |
|---|---|---|
| 1 | `STEM REC`: `READY`, `ARMED`, the time (`01:23`), `SAVING`, `DONE` or `NO CARD`; a failed take's error stands in for `STEM REC` | arms, cancels or stops the take |
| 2 | `PEAK`: the take's highest ring fill (`12%`) | skipped by the cursor |
| 3-10 | `T1` to `T8`, each with a checkbox | turns the track on or off |
| 11-12 | `MAIN`, `CUE`, each with a checkbox | turns the source on or off |
| 13-14 | the input pairs AB and CD, one row each | toggles the checkbox LEFT and RIGHT picked |
| 15 | `24 BIT` with a checkbox | 16-bit or 24-bit files |

An input pair row displays `AB` and `STEREO` when stereo is enabled (recording
one stereo file), or `A`, `B`, and `STEREO` when stereo is disabled (recording
a separate mono file for each enabled input, so you can record a single input
by itself). Use LEFT and RIGHT to move between checkboxes, just as on the MIDI
SYNC page. The CD row behaves the same way for inputs C and D.

1. Select your sources and bit depth. At boot, only T1 is enabled, bit depth
   is set to 24-bit, and both input pairs are set to stereo. These selections
   are not persisted across reboots, and rows 3 through 15 are locked while a
   take is recording or saving.
2. Press **YES** on `STEM REC`. If the sequencer is stopped, recording arms
   and starts on the first frame of playback (press YES again to cancel). If
   the sequencer is already running, recording starts immediately.
3. Recording stops when the sequencer stops, when you press STOP, after 60
   minutes, or if the write ring buffer fills up. You can close the STEMS menu
   while recording continues in the background.
4. **Do not remove the CF card or power off until the status reads `DONE`.**
   The take folder is created as soon as recording starts, so seeing the
   folder on the card does not mean saving is complete.

The status line updates automatically while STEMS is open. Possible error
messages are `RING FULL` (the card could not keep up, though the recorded
files remain playable), `SAME MINUTE` (99 takes have already been recorded in
the current minute), `WRITE FAILED`, `OPEN FAILED`, `PATH FAILED`,
`SEEK FAILED`, `CLOSE FAILED`, and `TASK FAILED`.

- When MASTER TRACK is enabled, T8 acts as the master bus: its row shows
  `MASTER`, T8 is omitted from the take, and MAIN records T8's output alone.
  In this mode, T1–T7 and CUE lead MAIN by 32 samples (0.73 ms), and the
  individual track files do not sum directly to MAIN.
- Each take also writes a log file to `/BRAIN/STEMS/<take>.TXT` under the
  card's root BRAIN directory.
