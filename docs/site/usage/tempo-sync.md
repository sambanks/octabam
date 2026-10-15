## What it does

A held MIDI note feeds BusDelay's TIME knob, and the knob draws as a
tempo division while the DSP's sticky snap holds one. The tempo itself is
stock's.

## How to use it

No menu: it runs wherever BusDelay runs. Send a MIDI note into the delay
host's track channel and hold it: TIME becomes that note's tempo
division. Release the note (or send note-off): TIME reads 0.

## Notes

- The division names come from the knob's own sticky snap; with no snap
  held the knob draws milliseconds.
