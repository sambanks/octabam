# `usb-midi-tracks-hw` -- USB MIDI TRACKS on a unit

The image `tools/hw/ot_usbtracks.py` drives: USB MIDI TRACKS (SEND pinned
NOTES+CC) with USB MIDI, REMOTE, BRAIN and LOAD METER on 13 stock effects
(SPATIALIZER gives its DSP words to LOAD METER). No FRAME GUARD: a late
frame-interrupt entry is what the stress run looks for.
[`usb-midi-tracks-hw-off`](../usb-midi-tracks-hw-off/README.md) is the same
image with SEND pinned OFF.

- REMOTE: PEEK of the module's counters, USB DISK MODE and REMIX SWITCH boots
  from the Mac, so the run needs no hands after the first switch.
- LOAD METER: the frame interrupt's longest run and a DSP that stops.

## Status

Built and booted under the port, 16 Nov 2026: `verify_usbmidi_tracks`,
`verify_dram_boot` and `verify_remote` pass on this image. Not yet run on a
unit.

```bash
python3 tools/hw/ot_usbtracks.py build
make check REMIX=test/usb-midi-tracks-hw
```
