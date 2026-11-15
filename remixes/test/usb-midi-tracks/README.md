# `usb-midi-tracks` -- audio-track trigs as USB MIDI

Stock effects + USB MIDI + USB MIDI TRACKS. Smallest image that carries the module.

- **USB MIDI TRACKS** -- the trig-page knobs as CC 16..21, scene morph included, and a note per sample slot on channel = track, USB only. [`modules/usb-midi-tracks/README.md`](../../../modules/usb-midi-tracks/README.md).
- **USB MIDI** -- the transmit queue it calls.
- the 14 stock FX2 effects.

## Status

`make check` passed on 3 Nov 2026 on main 320cee9d, before the retrig rework; the rework ran its gate and probes under the port, not `make check`. Never flashed.

```bash
make check REMIX=usb-midi-tracks
```
