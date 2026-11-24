# TRIG MUTE

Author: [Hteah](https://github.com/Hteah). PR preparation, test remix and gate by 8thmyth.
Original module by [Hteah](https://github.com/Hteah), from [Hteah/ot-mods](https://github.com/Hteah/ot-mods). Copyright (c) 2026 Hteah. Licensed under MIT: the copyright and permission notice is in [LICENSE](LICENSE).

Mute single trigs, as on the newer Elektron boxes. A muted trig stays on the
grid with its locks and its condition, but does not play.

- In GRID RECORDING on an audio track, hold a step key and press FUNC: its
  trig is muted (TRIG MUTED). Again: unmuted (TRIG UNMUTED). Several held
  steps toggle together.
- A muted trig's red LED blinks.
- Holding an empty step and pressing FUNC places a muted trig.
- The trig's condition still shows and edits as usual (step + LEVEL).
- Removing the trig removes the mute; placing a trig starts unmuted.
- 7:8 and 8:8 trigs cannot be muted (CAN'T MUTE 7:8 8:8).

The mute is kept in the pattern itself, in the trig's condition value:
stock uses 0..64, and a muted trig holds its condition + 65. So it is saved
with the bank, copied and pasted with the trig or pattern, and kept over a
power cycle (the battery copy of the bank), with nothing of its own on the
card or in battery RAM.

**Don't open a project with muted trigs in an image without TRIG MUTE.**
Stock firmware, and any remix without this module (also through REMIX
SWITCH), checks each pattern after a load and turns a condition above 64
into 64. Every muted trig becomes an unmuted **8:8** trig that plays, and
its own condition is gone. Saving the project there makes that permanent.

Hooks (1.40C): the step handler's condition test (a muted trig fails it,
as a failed condition does: no trig, no locks; recorder trigs still run),
the condition label and edit, the lock-flash pass (the blink), and the
trig-held layer's key rows (stock's plus FUNC).

Not done: MIDI tracks (FUNC there is stock's).
