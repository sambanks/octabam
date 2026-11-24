# TRIG MUTE

Module author: [Hteah](https://github.com/Hteah). PR preparation and gate by 8thmyth.

Mute single trigs, as on the newer Elektron boxes. A muted trig stays on the
grid with its locks and its condition, but does not play.

## Access

In GRID RECORDING on an audio track, hold a step key and press FUNC. Not in an
official remix; build the test remix `trig-mute`.

## Operation

- The toast shows TRIG MUTED; the same combo again shows TRIG UNMUTED. Several
  held steps toggle together.
- A muted trig's red LED blinks.
- Holding an empty step and pressing FUNC places a muted trig.
- The trig's condition still shows and edits as usual.
- 7:8 and 8:8 trigs cannot be muted (CAN'T MUTE 7:8 8:8).
- The mute is saved with the pattern and copied and pasted with it.

!!! warning "Open these projects only in an image with TRIG MUTE"
    Stock firmware, and any remix without TRIG MUTE (also through REMIX
    SWITCH), turns every muted trig into an unmuted **8:8** trig when it loads
    the project, and the trig's own condition is gone. Saving the project there
    makes that permanent.
