# MIDI Loopback / MIDI Scenes bridge

Routes MIDI Scenes' CC output through each source track's
[MIDI Loopback](../midi-loopback/README.md) DEST. It adds no controls.

- EXT sends scene CCs to DIN/USB.
- INT sends them to the internal receiver.
- BOTH sends one copy to each.

The route is read from the Part MIDI Scenes is mixing, not the Part shown
for editing. Scene CCs keep their order before the note-on. Every other
DIN/USB sender is unchanged. CC Feedback (audio-knob CC out) is a separate
path: set **AUDIO CC OUT = INT** when it should stay internal too.

## Composition

The joined selection keeps existing remix configurations compatible. MIDI Scenes
calls Loopback directly for track CCs and supplies the mix context for fader CCs.
The shared DIN/USB sender remains available to other producers.
The linked-image gate exercises both producers for all eight tracks and routes.
