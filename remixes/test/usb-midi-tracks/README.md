# `usb-midi-tracks` -- audio-track trigs as USB MIDI

Stock effects + USB MIDI + USB MIDI TRACKS. Smallest image that carries the module.

- **USB MIDI TRACKS** -- the trig-page knobs as CC 16..21, scene morph included, and a note per sample slot on each track's TRIG CHANNEL, USB only. SEND is pinned to NOTES+CC here (the module's default is OFF), so the gate sees both. [`modules/usb-midi-tracks/README.md`](../../../modules/usb-midi-tracks/README.md).
- **USB MIDI** -- the transmit queue it calls.
- the 14 stock FX2 effects.

## Status

The module's own gate (`verify_usbmidi_tracks`) passed under the port on this
build, 16 Nov 2026: TRIG CHANNEL, order, gate length and the stuck-note sweep.
The whole-remix `make check` runs in CI on the PR. The PR's first build (channel = track,
always on) was seen working on an MKII on 15 Nov 2026 (owner report); this
build has not been flashed.

```bash
make check REMIX=usb-midi-tracks
```
