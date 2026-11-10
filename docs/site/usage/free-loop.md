## What it does

FREE LOOP turns the Octatrack into a **looper you play with your feet**,
with your hands on a guitar, a synth or a microphone. Each looping track
gets its own pedals on its MIDI channel:

- **REC** (CC 90). Sequencer stopped, nothing recorded yet: the first press
  starts a **free take**, the second ends it. You play the loop's length as
  you feel it, with no click and no count-in. When it ends, FREE LOOP
  chooses the **tempo** that makes it a whole number of bars, sets the
  pattern's length and **starts the sequencer** with the loop on step 1.
  After that, REC **arms an overdub**, which starts at the next loop start,
  and **cuts** it.
- **PLAY/STOP** (CC 91): plays, mutes and unmutes the loop.
- **UNDO** (CC 92): takes the last overdub back, and brings it back again
  (REDO).
- **END** (CC 93): stops the loop at its end, or brings it back at its next
  start.

A few more CCs, on the PROG CH channel, drive the whole machine: PLAY /
STOP, clear every recorder, next / previous pattern, next / previous bank.
A window per track (**TRACK + UP**) sets its role, its time signature, its
tempo range, how it enters each pattern, its UNDO buffer and the big REC
popup.

A track left OFF, the default, stays stock. On a stock Octatrack, a project
made with FREE LOOP opens with plain FLEX tracks and their recordings.

## Where to find it

FREE LOOP is in the `free-loop` test remix. It needs:

- **STORE**: the settings are saved with the project, in `freeloop.work`.
- **RLEN PLEN**: a track's RECORDING SETUP has RLEN = PLEN, so an overdub is
  exactly one loop long, the length the free take set.

It shares an image with REC_TRIG_MUTE and REC THRESHOLD: HOOKS, added by the
build, joins them at the sites they share. It cannot share an image with
MORPH, which uses the same TRACK + UP.

## What you need

- **A MIDI pedalboard** that sends a CC with value 127 at the press and 0 at
  the release (a *momentary* pedal). The long presses (held 1 s) are timed by
  FREE LOOP and need the release. A pedal that sends 127 only works for
  short presses, but it never long-presses. The author uses an XSONIC
  Airstep.
- **The track's MIDI channel.** A track's pedals are sent on that track's
  channel (MIDI CONTROL: by default T1 on channel 1 ... T8 on channel 8).
  AUDIO CC IN is not needed. The transport CCs go to the **PROG CH** channel
  (PROG CH RECEIVE on). On the AUTO channel, CC 90-93 act on the selected
  track.
- **A project set up for looping.** `modules/free-loop/make_template.py`
  writes one, ready to play. The rest of this guide uses it.

## Quick start

1. **Make the template project** with the image you run:
   `python3 modules/free-loop/make_template.py --image out/mainos_bus.bin`
   writes `out/templates/FREE_LOOP`. Copy it into a set on the card and
   load it. What it holds:
   - **T1** guitar loop (FREE) and **T2** guitar layer (GRID), on inputs A B.
   - **T3** synth loop (FREE) and **T4** synth layer (GRID), on inputs C D.
   - T1-T4 are FLEX tracks, each on its own recorder buffer (R1-R4), with
     R5-R8 as their UNDO buffers.
   - **T5-T8** are left free for your samples.
   - The inputs are heard through the mixer's DIR AB / DIR CD.
   - Every track records the input over itself (sound on sound) with
     RLEN = PLEN.
2. **Set your pedal** to CC 90 on channel 1, momentary (127 / 0). It is T1's
   REC.
3. **Play.** Sequencer stopped: press REC and play your phrase. The REC
   popup fills the screen: FIRST LOOP, the seconds taken, and the tempo and
   bars the take would give if you ended it now.

   ![The REC popup during the free take](../../img/free-loop/popup.png)

4. Press REC again **on the downbeat**, where the loop comes round. The
   tempo is set, the pattern takes the loop's length and the sequencer
   starts: your loop plays.
5. Press REC again: the track is **ARMED**. At the next loop start it
   records the input over the loop (**OVERDUB**), pass after pass, until you
   press REC again.

## The pedals

On the track's channel:

| pedal | short press | held 1 s |
|---|---|---|
| **REC** (CC 90) | stopped, nothing recorded: start / end the free take; then: arm / cut the overdub | track playing: UNDO; track muted or sequencer stopped: **clear the loop** |
| **PLAY/STOP** (CC 91) | stopped: PLAY; playing: mute / unmute (MUTE NOW) or END (MUTE END) | END |
| **UNDO** (CC 92) | UNDO, then REDO; during a pass: drop the pass | -- |
| **END** (CC 93) | heard: mute at the loop's end; muted: back at the next loop start; again: cancel | -- |

On the PROG CH channel:

| CC | does |
|---|---|
| 83 | sequencer PLAY / STOP |
| 84 | sequencer stopped: clear R1-R8 (RECORDING CLEARED!) |
| 85 / 86 | next / previous pattern (A16 goes on to B01) |
| 88 / 89 | pattern 1 of the next / previous bank |

CC 83-89 work in MIDI mode too, and on the AUTO channel: you can play a
synth from a MIDI track and still drive the transport from the pedalboard.
Changing the playing bank while the sequencer runs clears R1-R8.

Clearing a loop you hear takes two gestures, so that it never happens by
accident: mute it (PLAY/STOP), then hold REC.

## The REC popup

With **POPUP ON** (the window's last row), the whole screen says what the
track is recording, big enough to read from across the room. It opens when
REC starts a take or arms the track, and closes 0.5 s after the pass ends.
It takes no keys; opening the TRACK + UP window closes it.

| | |
|---|---|
| ![FIRST LOOP](../../img/free-loop/popup.png) | **FIRST LOOP**: the free take. A disc pulses; below, the seconds taken and the tempo and bars the take would give now. |
| ![ARMED](../../img/free-loop/armed.png) | **ARMED**: the overdub waits for the loop start (STARTS AT THE LOOP). The ring blinks. |
| ![OVERDUB](../../img/free-loop/overdub.png) | **OVERDUB**: the pass records. BAR n/N and a bar under it show where you are in the loop, with a mark per bar. |
| ![FINISHING](../../img/free-loop/finishing.png) | **FINISHING**: REC cut the overdub; the pass in progress runs to the loop's end, then stops. |
| ![UNDO](../../img/free-loop/undo.png) | **UNDO**: the loop before the last pass comes back at the next loop start (REDO, UNDONE, NO UNDO in the same place). |

A REPLACE pass (below) shows **REPLACE**, with a holed disc.

## The track's mark

With POPUP OFF, or while the popup is closed, a FREE / GRID track shows what
it does next to its status icon, at the screen's left edge:

- **a ring** blinking at 2 Hz while it is **armed**;
- **a dot** while it **overdubs**;
- the stock `+` while its own recorder runs outside an overdub.

| armed: the ring | overdubbing: the dot |
|---|---|
| ![T2 armed](../../img/free-loop/marks-armed.png) | ![T2 overdubbing](../../img/free-loop/marks-overdub.png) |

Here T2's pedal (CC 90 on channel 2) has armed it; the toast says so. T2's
mark is left of its icon, the second one down.

## The window: TRACK + UP

Hold a track key and press **UP**: that track's window. **UP / DOWN** choose
a row, **LEFT / RIGHT** or any encoder change its value, and **YES / NO**
(or TRACK + UP again) close it. It shows six rows and scrolls.

![The window, top rows](../../img/free-loop/window.png)

| row | values | what it does |
|---|---|---|
| **ROLE** | OFF, GRID, FREE | OFF: stock. GRID: REC arms / cuts overdubs on the grid, never a free take. FREE: as GRID, and its first loop can be a free take that sets the tempo. |
| **SIGN** | 4/4, 3/4, 6/8, 5/4, 7/8, 9/8, 12/8, 2/4 | the bar the free take is counted in (16 steps in 4/4, 12 in 3/4 and 6/8, 20 in 5/4, 14 in 7/8...) |
| **BARS** | AUTO, 1, 2, 4, 8, 16 | the free take's length in bars; AUTO: the fewest bars whose tempo falls in MIN..MAX |
| **MIN BPM / MAX BPM** | 30..300 | the tempo range the free take may give (default 70..160); AUTO wants MAX at least twice MIN |

![ENTRY and PLAY, for the pattern in the header](../../img/free-loop/window-pattern.png)

**ENTRY** and **PLAY** are set **per pattern**: the header names the
pattern they apply to (A01 here). Select another pattern and open the
window again to set its own.

| row | values | when that pattern starts |
|---|---|---|
| **ENTRY** | KEEP, ARM, OFF, REPLACE | KEEP: the track goes on as it was. ARM: it is armed, and overdubs from the pattern's first step. OFF: its overdub is cut. REPLACE: one pass records **the inputs alone** (not the loop), as a new first loop of the new pattern's length; the track is muted during it and heard on the new loop after. |
| **PLAY** | KEEP, MUTE, STOP, PLAY | KEEP: as it was. MUTE: muted. STOP: its trigs dropped (the FX tails ring out). PLAY: heard. |

![The last rows](../../img/free-loop/window-undo.png)

| row | values | what it does |
|---|---|---|
| **UNDO** | OFF, R1..R8 (not its own) | the UNDO buffer: each overdub is recorded into the other buffer, so the last one can be taken back. OFF: overdubs record in place, with no UNDO. |
| **UNDO TO** | LAST, 1..16 | LAST: UNDO goes back one pass. *n*: back to the loop as it was after its *n*-th recording (the take is the 1st); passes after it overdub in place. |
| **MUTE** | NOW, END | what PLAY/STOP's short press does while the track plays: mute at once, or END (at the loop's end) |
| **POPUP** | OFF, ON | the REC popup for this track |

## How the tempo is chosen

The free take is cut, never stretched or padded. FREE LOOP looks for the
slowest tempo, in the firmware's 1/24-BPM steps, at which the track's BARS
of its SIGN are not longer than what you played. With BARS AUTO it tries 1,
2, 4, 8 and 16 bars and keeps the fewest whose tempo falls inside MIN..MAX.

For example, in 4/4 with 70..160, a take of about 4 s gives **2 bars at
118.3 BPM**. At 3 s, the popup was showing 79.8 BPM, 1 bar. If no number of
bars fits the range, the take is refused, with a toast, and nothing is
written. With the Octatrack slaved to MIDI clock (CLOCK RECEIVE on), a free
take is refused (EXT CLOCK: NO FREE), because the tempo is the master's.

The pattern then takes the loop's length: 1X while it fits in 64 steps,
otherwise 1/2X, 1/4X or 1/8X.

## Configurations

**One instrument, one loop.** T1 FREE, a REC pedal on channel 1 and a
PLAY/STOP pedal next to it. Add an UNDO pedal (CC 92) if you have one free.

**Guitar and synth** (the template). T1 FREE and T3 FREE: whichever
instrument starts sets the tempo, and the other's first press then arms an
overdub on the grid. T2 and T4 are GRID layers, so a second part can be
muted or stopped without touching the first. On the author's Airstep:
pedal 3 is the guitar's REC (T1), pedal 4 the synth's (T3).

**A fixed form.** Set BARS to 4 (or 8) and a narrow MIN..MAX around your
song's tempo. The take is always that many bars, even if you end it a beat
early or late.

**Odd meters.** SIGN 7/8 (14 steps a bar), 5/4 (20), 12/8 (24): the take is
counted in those bars.

**A song in parts.** One pattern per part, with ENTRY and PLAY set per
pattern (Tutorial 2), and CC 85 on a pedal to go to the next part.

**Bar-accurate stops.** MUTE END: PLAY/STOP's press stops the loop at its
end, not at the press. END (CC 93) does the same from its own pedal,
whatever MUTE says.

**More recorders for samples.** UNDO OFF on a track frees its UNDO buffer.
Its overdubs then record in place, with no UNDO.

**With REC_TRIG_MUTE.** CC 80 and TRACK + NO / YES keep a track's recorder
trigs muted, beside FREE LOOP: a recorder trig fires only when FREE LOOP
lets it **and** REC_TRIG_MUTE has not muted the track.

## Tutorial 1: your first loop

The template project, a guitar on input A (or A B), three pedals on
channel 1: CC 90 (REC), CC 91 (PLAY/STOP), CC 92 (UNDO), all momentary.

1. **Check T1's window.** Hold T1 and press UP: ROLE FREE, SIGN 4/4, BARS
   AUTO, 70-160 BPM, UNDO R5, POPUP ON. Close with NO.
2. **The free take.** The sequencer is stopped. Count yourself in, press REC
   on your first note and play a phrase. FIRST LOOP is on screen; watch the
   tempo it suggests.
3. **Close the loop.** Press REC exactly where the phrase comes round. The
   sequencer starts and your phrase loops. The tempo is in the TEMPO window,
   and the pattern has the loop's length.
4. **The first overdub.** Press REC: ARMED. Get ready, the overdub starts at
   the loop start: OVERDUB, BAR 1/2... Play a second part over it; it
   records pass after pass, each one over the last.
5. **Cut.** Press REC: FINISHING. The pass in progress runs to the loop's
   end and stops; you hear the loop with everything you played.
6. **Undo.** Not happy with the last pass? Press UNDO: from the next loop
   start, the loop before it plays again. Press UNDO again (REDO) and the
   pass is back.
7. **Mute and unmute.** PLAY/STOP mutes the loop, and pressing it again
   brings it back. The fade avoids the click (with MUTE MODE OT).
8. **Start over.** Mute it, then hold REC 1 s: the loop is cleared. Stop the
   sequencer (CC 83, or STOP): with no loop left on any track, the next REC
   is a new free take, which sets a new tempo.

With the sequencer stopped, CC 84 clears all eight recorders at once.

## Tutorial 2: a song in three parts

An intro (a guitar loop alone), a verse (a second guitar layer added), a
chorus (a new loop replaces the first). The template project, with:

- T1 (FREE) and T2 (GRID) on the guitar;
- pedals on channel 1: CC 90 (T1 REC) and CC 91 (T1 PLAY/STOP);
- a pedal on channel 2: CC 90 (T2 REC);
- a pedal on the PROG CH channel: CC 85 (next pattern).

1. **Plan the patterns.** A01 is the intro, A02 the verse, A03 the chorus.
   They must be as long as the loop: once step 3 has set A01's length, set
   A02 and A03 to the same (FUNC + PAGE, SCALE SETUP).
2. **Set each pattern's entries.** Select A02, hold T2, press UP. Go down to
   ENTRY: **ARM** (T2 starts recording when the verse starts). Close. Select
   A03, open T1's window: ENTRY **REPLACE** (the chorus records a new T1
   loop). In T2's window for A03, PLAY **MUTE** (the layer drops out for the
   chorus). Go back to A01 to start.
3. **Intro.** Sequencer stopped: T1 REC, play the riff, REC on the downbeat.
   The intro loops. Overdub it if you like (REC, REC).
4. **Verse.** Press the CC 85 pedal: A02 comes in at the end of A01, as a
   stock pattern change does. T2 is armed at the verse's first step and
   records your second part (the dot by its icon); press T2's REC to cut it
   when it is right.
5. **Chorus.** CC 85 again: at A03's first step, T1 is muted and records
   one pass of your guitar alone (REPLACE). Then the new loop is heard and
   the verse's layer, T2, is muted. Since T1 has an UNDO buffer, UNDO brings
   the intro's loop back.
6. **Ending.** END (CC 93) on a track, or PLAY/STOP with MUTE END, stops it
   at its loop's end. CC 83 stops everything.

Each pattern remembers its own ENTRY and PLAY per track, and the project
saves them (SAVE PROJECT writes `freeloop.strd`).
