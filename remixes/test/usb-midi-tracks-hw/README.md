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
`verify_dram_boot` and `verify_remote` pass on this image. On the owner's
MKII, 16 Nov 2026, switched to through REMIX SWITCH as `UMT-HW 1` (and
`UMT-OLD 1`, the same composition at 94c95f79): `tools/hw/ot_usbtracks.py`
runs new2 and old2, no stall in 60 s of INF retrig, longest frame interrupt
about 310 us on both; results in
[`modules/usb-midi-tracks/README.md`](../../../modules/usb-midi-tracks/README.md).

```bash
python3 tools/hw/ot_usbtracks.py build
make check REMIX=test/usb-midi-tracks-hw
```
