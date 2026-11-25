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

The build adds this bridge to any selection that carries MIDI LOOPBACK and
MIDI SCENES (`Module.joins`). Without it the ledger refuses the pair: MIDI
Scenes replaces stock's CC loop with its own sender, so a track's scene CCs
would bypass Loopback and always go out DIN/USB. It requires USB, whose
sender at `0x40010bc8` it stands in for (`Override`).

## How it works

`lb_scenes_send` replaces USB's detour at the shared MIDI sender. A
three-byte control change whose caller lies in MIDI Scenes' CC loop
(`scn_ccnote`..`scn_clear`) takes the source track's DEST from the Part in
`scn_pbi`/`scn_pp` and goes through Loopback's `lb_packet`. Every other call
continues to USB's `usbmidi_send_shim`. The mixer's crossfader CCs reach
the stock control emitter, where Loopback's `HAVE_SCENES_BRIDGE` path
recognises a caller in `scn_morph`..`scn_invalidate` and calls
`lb_scenes_dest`.

The code is radiohagen's (`upstream/modules/midi-loopback-scenes/bridge.s`,
the MIDI Loopback submodule). The manifest pins octabam's
`modules/midi-scenes/scenes.s` by hash; a change there refuses the build
until the producer boundaries listed in the manifest are re-audited.
`tools/verify/verify_midi_loopback_scenes.py` checks the context offsets and
both producer sites in the linked runtime, then runs both producers for all
eight tracks and each route.
