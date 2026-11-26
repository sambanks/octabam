# TRIG MUTE

Module author: [Hteah](https://github.com/Hteah). PR preparation and gate by 8thmyth.

TRIG MUTE lets you mute individual trigs, as on newer Elektron instruments. A
muted trig stays on the grid with its parameter locks and trig condition
intact, but does not play.

## Access

In GRID RECORDING on an audio track, hold a step key and press FUNC. This
module is not included in the official remixes; build the `trig-mute` remix to
use it.

## Operation

- The toast displays TRIG MUTED; repeating the combo displays TRIG UNMUTED.
  Holding multiple step keys toggles all of them together.
- A muted trig's red LED blinks.
- Holding an empty step and pressing FUNC places a muted trig.
- The trig's condition still displays and edits normally.
- 7:8 and 8:8 trigs cannot be muted (CAN'T MUTE 7:8 8:8).
- Trig mutes are saved with the pattern and included when copying and pasting.

!!! warning "Open these projects only in an image with TRIG MUTE"
    Stock firmware and any remix without TRIG MUTE (including when loaded via
    REMIX SWITCH) convert every muted trig into an unmuted **8:8** trig when
    loading the project, discarding the trig's original condition. Saving the
    project from that firmware makes the change permanent.
