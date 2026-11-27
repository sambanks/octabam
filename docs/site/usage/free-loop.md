## What it does

FREE LOOP turns the Octatrack into a **foot-controlled looper** so you can keep
your hands on a guitar, synth, or microphone. Each looping track receives its
own pedal commands on its MIDI channel:

- **REC** (CC 90): When the sequencer is stopped and nothing is recorded yet,
  the first press starts a **free take** and the second ends it. You play the
  loop at whatever length feels right, with no click or count-in. When you end
  the take, FREE LOOP calculates a **tempo** that makes the recording a whole
  number of bars, sets the pattern length to match, and **starts the
  sequencer** with your loop playing from step 1. Once running, pressing REC
  **arms an overdub** starting at the next loop boundary, and pressing REC
  again **stops** it.
- **PLAY/STOP** (CC 91): Starts playback when stopped, or mutes and unmutes the
  loop while running.
- **UNDO** (CC 92): Reverts the last overdub, and pressing it again restores it
  (REDO).
- **END** (CC 93): Stops the loop at its end, or brings it back in at the next
  loop start.

Additional CCs on the PROG CH channel control global functions: PLAY/STOP,
clearing all recorders, next and previous pattern, and next and previous bank.
Each track also has a settings window (**TRACK + UP**) to configure its role,
time signature, tempo range, per-pattern entry behavior, UNDO buffer, and
full-screen REC popup.

Tracks left OFF (the default) behave normally. A project created with FREE LOOP
opens on a stock Octatrack as ordinary FLEX tracks with their recorded buffers.

## Where to find it

FREE LOOP is included in the `free-loop` test remix. It requires:

- **STORE**: Saves FREE LOOP settings with the project in `freeloop.work`.
- **RLEN PLEN**: Adds `RLEN = PLEN` to RECORDING SETUP so overdubs always match
  the exact pattern length set by your free take.

FREE LOOP works alongside REC_TRIG_MUTE and REC THRESHOLD (the build adds HOOKS
automatically so they share hook sites). It cannot be combined with MORPH,
which uses the same TRACK + UP shortcut.

## What you need

- **A MIDI pedalboard** configured for *momentary* CCs that send value 127 on
  press and 0 on release. FREE LOOP measures long presses (held 1 s) using the
  release message; a pedal that only sends 127 works for short presses but
  cannot trigger long presses. The author uses an XSONIC Airstep.
- **Per-track MIDI channels.** Send each track's pedal CCs on that track's MIDI
  channel (configured under MIDI CONTROL; defaults are T1 on channel 1 through
  T8 on channel 8). AUDIO CC IN does not need to be enabled. Send global
  transport CCs on the **PROG CH** channel with PROG CH RECEIVE enabled. On the
  AUTO channel, CC 90–93 control whichever track is currently selected.
- **A looping project template.** Run `modules/free-loop/make_template.py` to
  generate a ready-to-play template project. The steps below assume you are
  using it.

## Quick start

1. **Generate the template project** using your built OS image:
   `python3 modules/free-loop/make_template.py --image out/mainos_bus.bin`
   This creates `out/templates/FREE_LOOP`. Copy it into a Set on your CF card
   and load it. The template sets up:
   - **T1** as a guitar loop (FREE) and **T2** as a guitar layer (GRID), fed
     from inputs A B.
   - **T3** as a synth loop (FREE) and **T4** as a synth layer (GRID), fed from
     inputs C D.
   - T1–T4 as FLEX tracks assigned to recorder buffers R1–R4, using R5–R8 as
     their UNDO buffers.
   - **T5–T8** left free for your own samples.
   - Direct input monitoring via the mixer's DIR AB / DIR CD settings.
   - Sound-on-sound overdubbing on each track with `RLEN = PLEN`.
2. **Assign a pedal** to momentary CC 90 (127 / 0) on MIDI channel 1 for T1's
   REC control.
3. **Record a free take.** With the sequencer stopped, press REC and play your
   phrase. The full-screen REC popup opens showing `FIRST LOOP`, the elapsed
   seconds, and the tempo and bar count the loop would receive if closed now.

   ![The REC popup during the free take](../../img/free-loop/popup.png)

4. Press REC again **on the downbeat** where the loop restarts. FREE LOOP sets
   the tempo and pattern length and starts the sequencer playing your loop.
5. Press REC once more to mark the track **ARMED**. At the next loop start, it
   switches to **OVERDUB** and records your input over the loop pass after pass
   until you press REC again.

## The pedals

On a track's MIDI channel:

| pedal | short press | held 1 s |
|---|---|---|
| **REC** (CC 90) | When stopped with nothing recorded: start or end a free take. Once running: arm or stop an overdub | While playing: UNDO. While muted or stopped: **clear the loop** |
| **PLAY/STOP** (CC 91) | While stopped: PLAY. While playing: mute/unmute (`MUTE NOW`) or queue END (`MUTE END`) | END |
| **UNDO** (CC 92) | UNDO, then REDO; during an overdub pass, discards the current pass | -- |
| **END** (CC 93) | While audible: mute at the end of the loop. While muted: unmute at the next loop start. Press again to cancel | -- |

On the PROG CH channel:

| CC | does |
|---|---|
| 83 | Sequencer PLAY / STOP |
| 84 | While sequencer is stopped: clear R1–R8 (`RECORDING CLEARED!`) |
| 85 / 86 | Next / previous pattern (A16 advances to B01) |
| 88 / 89 | Pattern 1 of the next / previous bank |

CC 83–89 also work in MIDI mode and on the AUTO channel, so you can play a
synth from a MIDI track while still controlling the transport from your
pedalboard. Changing banks while the sequencer is running clears R1–R8.

Clearing an audible loop requires two steps to prevent accidents: mute it with
PLAY/STOP first, then hold REC for 1 second.

## The REC popup

When **POPUP** is ON (the bottom row of the track window), a full-screen status
overlay shows the track's recording state in large text readable from across
the room. It opens automatically when REC starts a take or arms the track, and
closes 0.5 s after the pass finishes. It does not capture button presses, and
opening the TRACK + UP window dismisses it.

| | |
|---|---|
| ![FIRST LOOP](../../img/free-loop/popup.png) | **FIRST LOOP**: Recording the initial free take. A pulsing disc appears above the elapsed time and the candidate tempo and bar count. |
| ![ARMED](../../img/free-loop/armed.png) | **ARMED**: An overdub is queued for the next loop start (`STARTS AT THE LOOP`), with a blinking ring. |
| ![OVERDUB](../../img/free-loop/overdub.png) | **OVERDUB**: Actively recording an overdub pass. Displays `BAR n/N` and a progress bar with markers for each bar. |
| ![FINISHING](../../img/free-loop/finishing.png) | **FINISHING**: REC was pressed to end the overdub; the current pass finishes at the end of the loop and then stops. |
| ![UNDO](../../img/free-loop/undo.png) | **UNDO**: Restores the loop from before the last pass at the next loop start (`REDO`, `UNDONE`, and `NO UNDO` appear in the same spot). |

A REPLACE pass (described below) displays **REPLACE** with a hollow disc.

## The track's mark

When POPUP is OFF, or whenever the popup is closed, a FREE or GRID track shows
its recording status next to its track icon at the left edge of the screen:

- **A blinking ring** (2 Hz) while **armed**
- **A solid dot** while **overdubbing**
- The stock `+` while its recorder runs outside an overdub

| armed: the ring | overdubbing: the dot |
|---|---|
| ![T2 armed](../../img/free-loop/marks-armed.png) | ![T2 overdubbing](../../img/free-loop/marks-overdub.png) |

In the example above, T2's pedal (CC 90 on channel 2) armed T2 and triggered a
confirmation toast. T2's mark appears to the left of its icon, second from the
top.

## The window: TRACK + UP

Hold a track key and press **UP** to open that track's FREE LOOP settings
window. Use **UP / DOWN** to select a row, **LEFT / RIGHT** or any encoder to
change its value, and **YES**, **NO**, or **TRACK + UP** again to close it. The
window displays six rows at a time and scrolls.

![The window, top rows](../../img/free-loop/window.png)

| row | values | what it does |
|---|---|---|
| **ROLE** | OFF, GRID, FREE | OFF: stock track. GRID: REC arms and stops grid-synced overdubs, never a free take. FREE: works like GRID, and its first recording can be a tempo-setting free take. |
| **SIGN** | 4/4, 3/4, 6/8, 5/4, 7/8, 9/8, 12/8, 2/4 | Time signature used to count the free take (16 steps in 4/4, 12 in 3/4 and 6/8, 20 in 5/4, 14 in 7/8, and so on). |
| **BARS** | AUTO, 1, 2, 4, 8, 16 | Bar length of the free take. AUTO picks the fewest bars whose calculated tempo falls within MIN..MAX. |
| **MIN BPM / MAX BPM** | 30..300 | Allowed tempo range for a free take (default 70..160). For AUTO to cover every length, set MAX to at least twice MIN. |

![ENTRY and PLAY, for the pattern in the header](../../img/free-loop/window-pattern.png)

**ENTRY** and **PLAY** are configured **per pattern**; the header shows which
pattern you are editing (`A01` in the screenshot). Switch to another pattern
and reopen the window to edit its settings.

| row | values | when that pattern starts |
|---|---|---|
| **ENTRY** | KEEP, ARM, OFF, REPLACE | KEEP: continues the track's current recording state. ARM: arms the track to overdub from step 1 of the pattern. OFF: stops any active overdub. REPLACE: records one pass of **the inputs alone** (without the existing loop) as a new first loop matching the new pattern's length; the track stays muted during the pass and unmutes once recorded. |
| **PLAY** | KEEP, MUTE, STOP, PLAY | KEEP: unchanged. MUTE: mutes the track. STOP: stops playback by dropping trigs (letting FX tails ring out). PLAY: unmutes the track. |

![The last rows](../../img/free-loop/window-undo.png)

| row | values | what it does |
|---|---|---|
| **UNDO** | OFF, R1..R8 (excluding its own) | Assigns a secondary recorder buffer so each overdub records into the alternate buffer, enabling UNDO. OFF records overdubs in place with no UNDO. |
| **UNDO TO** | LAST, 1..16 | LAST reverts one pass. Setting a number *n* reverts to the loop as it sounded after its *n*-th recording (the initial take is 1), with later passes overdubbing in place. |
| **MUTE** | NOW, END | Sets what a short press of PLAY/STOP does while playing: mute immediately (NOW) or mute at the end of the loop (END). |
| **POPUP** | OFF, ON | Enables or disables the full-screen REC popup for this track. |

## How the tempo is chosen

A free take is trimmed to fit rather than time-stretched or padded. FREE LOOP
finds the slowest tempo (in the firmware's 1/24-BPM increments) at which the
configured number of bars in the track's time signature is no longer than your
recording. With BARS set to AUTO, it checks 1, 2, 4, 8, and 16 bars in order
and chooses the smallest bar count whose tempo falls between MIN BPM and MAX
BPM.

For example, in 4/4 with a range of 70–160 BPM, a take lasting about 4 seconds
becomes **2 bars at 118.3 BPM** (at 3 seconds, the popup showed 1 bar at 79.8
BPM). If no bar count produces a tempo inside the allowed range, the take is
rejected with a toast message and nothing is written. If the Octatrack is
following external MIDI clock (CLOCK RECEIVE on), free takes are blocked with
`EXT CLOCK: NO FREE` because the master clock owns the tempo.

The pattern length is then set to match the loop, using 1X scale if it fits in
64 steps, or 1/2X, 1/4X, or 1/8X otherwise.

## Configurations

**One instrument, one loop.** Set T1 to FREE and assign a REC pedal and a
PLAY/STOP pedal on channel 1. Add an UNDO pedal (CC 92) if you have a third
switch free.

**Guitar and synth (the template).** Both T1 and T3 are set to FREE, so
whichever instrument records first establishes the tempo; the other
instrument's first REC press then arms a grid-synced overdub. T2 and T4 act as
GRID layers that you can mute or stop independently of the main loops. On the
author's Airstep, pedal 3 controls guitar REC (T1) and pedal 4 controls synth
REC (T3).

**A fixed form.** Set BARS to 4 (or 8) and narrow MIN..MAX around your target
tempo so every free take lands on that exact bar count even if you close the
loop slightly early or late.

**Odd meters.** Set SIGN to 7/8 (14 steps per bar), 5/4 (20 steps), or 12/8 (24
steps) to count free takes in those meters.

**A song in parts.** Use one pattern per song section with ENTRY and PLAY
configured per pattern (see Tutorial 2), and assign CC 85 to a pedal to step to
the next section.

**Bar-accurate stops.** Set MUTE to END so pressing PLAY/STOP queues a stop at
the end of the loop rather than muting immediately. The dedicated END pedal (CC
93) always queues a loop-end stop regardless of the MUTE setting.

**More recorders for samples.** Set UNDO to OFF on a track to free up its UNDO
recorder buffer. Overdubs then record in place without UNDO.

**With REC_TRIG_MUTE.** CC 80 and TRACK + NO / YES continue to mute a track's
recorder trigs alongside FREE LOOP. A recorder trig only fires when both FREE
LOOP allows it **and** REC_TRIG_MUTE has not muted that track.

## Tutorial 1: your first loop

Start with the template project, a guitar connected to input A (or A B), and
three momentary pedals on channel 1: CC 90 (REC), CC 91 (PLAY/STOP), and CC 92
(UNDO).

1. **Check T1's window.** Hold T1 and press UP to verify ROLE is FREE, SIGN is
   4/4, BARS is AUTO, range is 70–160 BPM, UNDO is R5, and POPUP is ON. Close
   the window with NO.
2. **Record the free take.** With the sequencer stopped, count yourself in,
   press REC on your first note, and play a phrase. Watch `FIRST LOOP` on
   screen as it updates the suggested tempo.
3. **Close the loop.** Press REC right on the downbeat where your phrase
   repeats. The sequencer starts and your phrase loops automatically, with the
   new tempo shown in the TEMPO window and the pattern sized to match.
4. **Record the first overdub.** Press REC to switch to `ARMED`. Overdubbing
   starts at the next loop boundary (`OVERDUB`, `BAR 1/2`, and so on). Play a
   second part over the loop; it continues layering pass after pass.
5. **Stop overdubbing.** Press REC again to show `FINISHING`. The current pass
   completes at the end of the loop and stops, leaving your layered recording
   playing back.
6. **Undo.** If you dislike the last pass, press UNDO to revert to the previous
   loop at the next loop start. Press UNDO again (REDO) to restore it.
7. **Mute and unmute.** Press PLAY/STOP to mute the loop, and press it again to
   bring it back. With MUTE MODE OT, a brief fade prevents clicks.
8. **Start over.** Mute the loop, then hold REC for 1 second to clear it. Stop
   the sequencer with CC 83 or STOP. Once no loops remain on any track, the
   next REC press starts a fresh free take and sets a new tempo.

While the sequencer is stopped, sending CC 84 clears all eight recorder buffers
at once.

## Tutorial 2: a song in three parts

This walkthrough builds a three-part song: an intro (a single guitar loop), a
verse (adding a second guitar layer), and a chorus (replacing the first loop
with a new one). Use the template project with:

- T1 (FREE) and T2 (GRID) on the guitar inputs
- Pedals on channel 1 for CC 90 (T1 REC) and CC 91 (T1 PLAY/STOP)
- A pedal on channel 2 for CC 90 (T2 REC)
- A pedal on the PROG CH channel for CC 85 (next pattern)

1. **Plan the patterns.** Use A01 for the intro, A02 for the verse, and A03 for
   the chorus. All three patterns must share the loop's length: after step 3
   sets A01's length, set A02 and A03 to the same length under FUNC + PAGE
   (SCALE SETUP).
2. **Configure per-pattern entry settings.** Select A02, hold T2, press UP, and
   set ENTRY to **ARM** so T2 begins overdubbing when the verse starts, then
   close the window. Select A03, open T1's window, and set ENTRY to **REPLACE**
   so the chorus records a new loop on T1. Still on A03, open T2's window and
   set PLAY to **MUTE** so the verse layer drops out during the chorus. Return
   to A01 to begin.
3. **Play the intro.** With the sequencer stopped, press T1 REC, play your
   riff, and press T1 REC on the downbeat to loop it. Overdub extra passes with
   REC if you like.
4. **Move to the verse.** Press the CC 85 pedal to queue A02 at the end of A01
   like a normal pattern change. T2 arms automatically on step 1 of the verse
   and starts recording your second part (indicated by the dot beside its
   icon); press T2 REC when you want to stop overdubbing.
5. **Move to the chorus.** Press CC 85 again. On step 1 of A03, T1 mutes and
   records one clean pass of your guitar (`REPLACE`), while T2 mutes for the
   chorus. After that pass, the new T1 loop plays back. Because T1 has an UNDO
   buffer assigned, pressing UNDO can still bring back the intro loop.
6. **End the song.** Press END (CC 93) on a track (or PLAY/STOP if MUTE is set
   to END) to stop it cleanly at the end of its loop. Send CC 83 to stop the
   entire sequencer.

Each pattern stores its own ENTRY and PLAY settings per track, and SAVE PROJECT
writes them to `freeloop.strd`.
