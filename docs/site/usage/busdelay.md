## What it does

The bus's delay engine, hosted on track 1's FX2 (locked; the FX2 chooser
cannot change it). Three modes: CLEAN, GRAIN (a pitched granular cloud over
the delay lines) and REVERSE, with a tape wow on the loop tap in every
mode. The repeats come out on track 1; the reverb also hears them through
its DLY knob. The delay follows the project tempo.

## Where to find it

Track 1's FX2 page draws only DEL and REV. Every other knob is in the
TEMPO window: press [TEMPO], then LEFT / RIGHT to focus the DELAY box.

## How to use it

- DEL on track 1 sends track 1's own dry into the delay; REV sends it into
  the reverb.
- TIME is the delay time, a free dial that sticky-snaps to tempo divisions.
- FDBK is feedback, TONE the loop tone, PING the ping-pong bounce, WET the
  wet level.
- MODE: CLEAN, GRAIN or REVRS. GRAIN: SCTR is how far apart the grains
  read, DENS the density (level-flat), SIZE the grain length (GLEN 46 / 93
  / 23 ms, XTRM 186 ms), PTCH the pitch ±2 octaves (64 = unison; a held
  MIDI note overrides it). REVERSE: SIZE is the segment length (SLEN, XTRM
  = 371 ms); the output is mono and PING is forced off.

## Knobs

| page | knob | what it does |
|---|---|---|
| 1 | DEL | this track's dry into the delay |
| 1 | REV | this track's dry into the reverb |
| 1 | FDBK | feedback |
| 1 | TONE | loop tone |
| 1 | PING | ping-pong; forced off in REVERSE |
| 1 | WET | wet level |
| 2 | MODE | CLEAN / GRAIN / REVRS |
| 2 | SCTR | GRAIN: how far apart the grains read |
| 2 | DENS | GRAIN: density, level-flat |
| 2 | SIZE | GRAIN: grain length 46 / 93 / 23 ms, XTRM 186 ms. REVERSE: segment length, XTRM 371 ms |
| 2 | PTCH | GRAIN: ±2 octaves, 64 = unison |
| 2 | TIME | delay time; sticky-snaps to tempo divisions |

## Screens

![The BUSDELAY page on track 1](../../img/busdelay/main.png)
