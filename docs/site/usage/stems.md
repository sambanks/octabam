Records stems to the card while the sequencer plays: every track after its
fader, the main mix (MAIN), the cue mix (CUE) and the four inputs, in 16
or 24 bits. The take is written while it records, up to 60 minutes. Each
take gets its own folder in `AUDIO/!STEMS/` (first in the file browser),
named after the take, `YYMMDD-HHMM`, and each source lands in it as its
own WAV file at 44,100 Hz. The take's name also starts each file's name:
`YYMMDD-HHMM-T1.wav` to `-T8.wav`, `-MAIN.wav`, `-CUE.wav`, and the inputs
as `-AB.wav` and `-CD.wav` (stereo) or `-A.wav` to `-D.wav` (mono). A
second take in the same minute is `YYMMDD-HHMM-2`, a third
`YYMMDD-HHMM-3`, and so on, so no take overwrites another. Takes already
on a card in an older layout stay where they are.

A track's file is its share of MAIN: the track's audio times the gain the
mix gives it, so the level, MAIN LEVEL, the scenes and the crossfader are
in it.

## Access

Hold **UP** and press **REC** (UP first). The same chord closes STEMS. REC
alone stays stock grid recording, and MAIN MENU is unchanged. Not in an
official remix; build the test remix `stems`.

## Operation

STEMS looks like SYSTEM > PERSONAL SETTINGS: five rows at a time, each a
name and a value. UP and DOWN move, YES changes the value under the
cursor, NO closes STEMS. The rows, top to bottom:

| Row | Shows | YES |
|---|---|---|
| 1 | `STEM REC`: `READY`, `ARMED`, the time (`01:23`), `SAVING`, `DONE` or `NO CARD`; a failed take's error stands in for `STEM REC` | arms, cancels or stops the take |
| 2 | `PEAK`: the take's highest ring fill (`12%`) | skipped by the cursor |
| 3-10 | `T1` to `T8`, each with a checkbox | turns the track on or off |
| 11-12 | `MAIN`, `CUE`, each with a checkbox | turns the source on or off |
| 13-14 | the input pairs AB and CD, one row each | toggles the checkbox LEFT and RIGHT picked |
| 15 | `24 BIT` with a checkbox | 16-bit or 24-bit files |

A pair row reads `AB` and `STEREO` in stereo (one stereo file), or `A`,
`B` and `STEREO` with STEREO off (a mono file for each input that's on, so
one input can record alone). LEFT and RIGHT pick a checkbox, as on MIDI
SYNC. The CD row works the same way with C and D.

1. Choose the sources and the format. At boot T1 alone is on, at 24
   bits, both pairs stereo. Nothing is
   saved, and rows 3 to 15 are locked while a take records or saves.
2. Press **YES** on STEM REC. With the sequencer stopped it arms and starts on the
   first frame the sequencer plays (press again to cancel); with it running
   it starts at once.
3. The take stops when the sequencer stops, when you press STOP, after 60
   minutes, or when the ring fills. You can close the menu while it
   records.
4. **Pull the card or power off only when the status reads `DONE`.** The
   folder appears when the take starts, so it is not a signal.

The status updates by itself while STEMS is open. Error names: `RING
FULL` (the card fell behind; the files still play), `SAME MINUTE` (99
takes in this minute already),
`WRITE FAILED`, `OPEN FAILED`, `PATH FAILED`, `SEEK FAILED`,
`CLOSE FAILED`, `TASK FAILED`.

- With MASTER TRACK on, T8 is the master bus: its value reads `MASTER`, a
  take leaves T8 out, and MAIN is T8 alone. T1 to T7 and CUE are 32
  samples (0.73 ms) early against MAIN in that mode, and the track files do
  not sum to MAIN.
- Each take also writes a log, `/BRAIN/STEMS/<take>.TXT` at the card's
  root, where BRAIN keeps its files.
