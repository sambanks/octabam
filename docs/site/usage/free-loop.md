A loop pedal per track, for playing an instrument into the Octatrack with
your hands on it. On a FREE track the first loop is played freely, the
sequencer stopped: when it ends, it sets the tempo, the pattern's length
and the loop's end, and the sequencer starts. From then on the same pedal
arms and cuts overdubs on the grid. A second pedal plays, mutes and clears
the loop; UNDO / REDO and END (stop or restart at the loop's end) complete
it.

## Access

Not in an official remix; build the test remix `free-loop`. Needs STORE
(it saves its settings through it) and works best with RLEN PLEN (the
overdubs take the pattern's length). It cannot share an image with
REC_TRIG_MUTE, REC THRESHOLD or MORPH.

Send CCs to a track's MIDI channel (AUDIO CC IN is not needed): a value
above 0 is the press, 0 the release. A pedal that sends 127 / 0 (momentary)
is expected; one that sends 127 only never long-presses.

`python3 modules/free-loop/make_template.py --image out/mainos_bus.bin`
writes a ready project, FREE_LOOP: T1 / T2 a guitar on inputs A B, T3 / T4
a synth on C D, each a FLEX track on its own recorder buffer, R5-R8 their
UNDO buffers, T5-T8 free for samples, the inputs heard through DIR AB /
DIR CD. T1 and T3 are FREE, T2 and T4 GRID.

## Operation

- **The first loop.** Sequencer stopped, nothing recorded: REC on a FREE
  track starts a free recording; REC again ends it. The tempo is chosen so
  the loop is a whole number of bars (the track's SIGN and BARS) inside its
  MIN..MAX BPM, the pattern takes that length, and the sequencer starts
  with the loop on step 1.
- **Overdubs.** REC arms the track: it records from its next loop start,
  and every pass after that, until REC again cuts it (the pass in progress
  ends). The track's mark at the screen edge: a blinking ring while armed,
  a dot while overdubbing.
- **PLAY/STOP.** Stopped: PLAY. Playing: mute / unmute the track (or, with
  MUTE END, at the loop's end). Held 1 s: END (with MUTE NOW, the press's
  mute is undone first). PLAY/STOP never clears.
- **REC held 1 s.** While the track plays: UNDO. With the track muted or
  the sequencer stopped: the track's loop is cleared. Clearing a heard
  loop takes two gestures: mute it, then hold REC.
- **UNDO / REDO.** With an UNDO buffer, each overdub records into the
  other buffer, so the last pass can be taken back from the next loop
  start, and brought back again. UNDO TO goes back further, to the
  n-th recording.
- **Patterns.** Each pattern can say, per track, how it enters it: ENTRY
  (KEEP, ARM, OFF, REPLACE: one pass of the inputs alone, a new first loop)
  and PLAY (KEEP, MUTE, STOP, PLAY).
- **The REC popup.** With POPUP ON, the whole screen shows the track,
  FIRST LOOP / ARMED / OVERDUB and the pass's progress, big enough to read
  from across the room, until the pass is over.
- With the Octatrack slaved to MIDI clock, a free take is refused (EXT
  CLOCK: NO FREE). The settings are saved with the project
  (`freeloop.work`, `freeloop.strd` at SAVE PROJECT); a project without
  them has every track OFF, which is stock.

## Controls

| Control | Does |
|---|---|
| CC 90 (track's channel) | REC: free take, arm / cut the overdub; held 1 s: UNDO (playing) or clear (muted or stopped) |
| CC 91 (track's channel) | PLAY/STOP: play, mute / unmute; held 1 s: END |
| CC 92 (track's channel) | UNDO / REDO |
| CC 93 (track's channel) | END: mute at the loop's end, or back at the next loop start |
| CC 83 (PROG CH channel) | sequencer PLAY / STOP |
| CC 84 (PROG CH channel) | sequencer stopped: clear R1-R8 |
| CC 85 / 86 (PROG CH channel) | next / previous pattern |
| CC 88 / 89 (PROG CH channel) | next / previous bank |
| TRACK + UP | the track's window (again, YES or NO: close) |
| UP / DOWN (window) | the row |
| LEFT / RIGHT, any encoder (window) | the value |

CC 83 to 89 work in MIDI mode as well, on the AUTO channel too: you can
play a synth from a MIDI track and still start and stop the sequencer from
the pedalboard.

| Row | Values |
|---|---|
| ROLE | OFF, GRID, FREE |
| SIGN | 4/4, 3/4, 6/8, 5/4, 7/8, 9/8, 12/8, 2/4 |
| BARS | AUTO, 1, 2, 4, 8, 16 |
| MIN BPM / MAX BPM | 30..300 (AUTO wants MAX at least twice MIN) |
| ENTRY | KEEP, ARM, OFF, REPLACE (for the pattern in the header) |
| PLAY | KEEP, MUTE, STOP, PLAY (for that pattern) |
| UNDO | OFF, R1..R8: the UNDO buffer |
| UNDO TO | LAST, 1..16 |
| MUTE | NOW, END: what PLAY/STOP's press does while playing |
| POPUP | OFF, ON |

![FREE LOOP window](../../img/free-loop/window.png)

![The REC popup during a free take](../../img/free-loop/popup.png)
