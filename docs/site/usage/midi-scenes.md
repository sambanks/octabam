MIDI SCENES adds scene locks for the eight MIDI tracks, matching how stock
firmware handles scenes on audio tracks. Each scene can lock any knob on a
MIDI track's pages (NOTE, LFO, ARP, CTRL1, CTRL2), and the crossfader
interpolates between scene A and scene B for those parameters.

## Operation

In MIDI mode (MIDI SEQUENCER), while holding scene A or B:

- Turn a knob to assign a lock to the held scene for the displayed track.
- While the scene is held, the knob readout shows that scene's locked value.
- Press a knob's encoder to clear its lock.
- The lock LEDs and grey cells indicate MIDI locks, and a scene pad lights up
  whenever its scene contains a lock for any track.
- Move the crossfader (on the front panel or via CC 48) to morph each locked
  parameter between A and B; MIDI CCs are sent whenever a value changes.
- When neither active scene locks a CC any longer, it returns to the Part's
  value and sends that value. (MIDISC 2.1 left the last locked value in place;
  this behavior is changed in octabam.)

CLEAR, COPY, and PASTE SCENE act on the entire scene, including both its MIDI
locks and its audio locks, regardless of whether audio or MIDI tracks are
currently displayed. The two sets of locks remain separate: a MIDI lock never
affects an audio track, and an audio lock never affects a MIDI track.

## Notes

- A track's locks affect only that track.
- Locks are saved with the project when you run SAVE PROJECT, and the current
  bank's working copy survives a power-off.
- Kits do not include a Part's MIDI locks.
- Page 2 of FX1 and FX2 has its own scene locks (SCENES P2).
- Holding a scene button while pressing MIDI shows that scene's locks for the
  tracks you switch to, just as if you had pressed the scene button after
  switching (stock firmware does not display them when switching from MIDI to
  audio tracks).
