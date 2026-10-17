Records stems to the card while the sequencer plays: every track after its
fader, the main mix (MAIN), the cue mix (CUE) and the four inputs, in 16
or 24 bits. The take is written while it records, up to 60 minutes. Each
source lands as its own WAV file at 44,100 Hz under
`AUDIO/STEMS/<project>/YYMMDD-HHMM/`: `T1.wav` to `T8.wav`, `MAIN.wav`,
`CUE.wav`, and the inputs as `AB.wav` and `CD.wav` (stereo) or `A.wav` to
`D.wav` (mono). `<project>` is the loaded project's name, or `UNTITLED`
when none is loaded.

A track's file is its share of MAIN: the track's audio times the gain the
mix gives it, so the level, MAIN LEVEL, the scenes and the crossfader are
in it.

## Access

Hold **UP** and press **REC** (UP first). The same chord closes STEMS. REC
alone stays stock grid recording, and MAIN MENU is unchanged. Not in an
official remix; build the test remix `stems`. On a MKII it ran STEMS1 to
STEMS3; the card writer and menu are measured under the port.

## Operation

The rows, top to bottom (YES acts on each):

| Row | Shows | YES |
|---|---|---|
| 1 | `REC`; `CANCEL` while armed; `STOP` while recording; `SAVING` | arms, cancels or stops the take |
| 2 | status: `READY`, `ARMED`, `REC 01:23`, `SAVING`, `DONE 01:23`, `NO CARD`, or an error | skipped by the cursor |
| 3-10 | `T1 [X]` to `T8 [X]` | turns the track on or off |
| 11-14 | `MAIN`, `CUE`, `AB`, `CD` | turns the source on or off |
| 15-16 | `AB STEREO`, `CD STEREO` | one stereo file or two mono files |
| 17 | `24 BIT` | 16-bit or 24-bit files |
| 18 | `PEAK 12%`: the take's highest ring fill | not reachable |

1. Choose the sources and the format. At boot the eight tracks are on,
   MAIN, CUE and the inputs off, both pairs stereo, 16 bits. Nothing is
   saved, and rows 3 to 17 are locked while a take records or saves.
2. Press **REC**. With the sequencer stopped it arms and starts on the
   first frame the sequencer plays (press again to cancel); with it running
   it starts at once.
3. The take stops when the sequencer stops, when you press STOP, after 60
   minutes, or when the ring fills. You can close the menu while it
   records.
4. **Pull the card or power off only when the status reads `DONE`.** The
   folder appears when the take starts, so it is not a signal.

The status updates when you press a key; open the menu or press UP or DOWN
to refresh it. Error names: `RING FULL` (the card fell behind; the files
still play), `SAME MINUTE` (a take already exists for this minute),
`WRITE FAILED`, `OPEN FAILED`, `PATH FAILED`, `SEEK FAILED`,
`CLOSE FAILED`, `TASK FAILED`.

- With MASTER TRACK on, T8 is the master bus: its row reads `T8 MASTER`, a
  take leaves T8 out, and MAIN is T8 alone. T1 to T7 and CUE are 32
  samples (0.73 ms) early against MAIN in that mode, and the track files do
  not sum to MAIN.
- Each take's folder also holds a `STATS.TXT`.
