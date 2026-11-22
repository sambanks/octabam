# EVENTS clients

A focused fixture for the shared EVENTS migration: EUCLID consumes transport
notifications and PLOCKS P2 consumes held edits and copy notifications. Both
clients are selected together, installing 25 event hooks. FILTER and COMPRESSOR
provide stock controls; PLATE REV supplies the page-2 fallback used by the
editor gates.

USB presents MAIN and CUE only (four channels), so the hardware stress runner's
first stereo pair observes MAIN. LOAD METER supplies frame-interrupt and DSP
readings. This is a dedicated integration-test selection.

Run `make check REMIX=events-clients` with `OT_PROJECT` pointing to a disposable
project. For a unit, follow [HARDWARE_TESTING](../../../docs/contributing/HARDWARE_TESTING.md):
generate a fresh project and the stimulus layouts, qualify the exact image,
then run the focused EUCLID layouts and transport sequence. BASE has no effects;
it still carries both event subscribers. Zero-subscriber omission is verified
separately by `events-empty`.

The standard stress generator covers START/STOP but not CONTINUE. Resume needs
an explicit sequence or the panel. Panel operations have emulator coverage; physical panel timing and a real
save/power-cycle check need the operator. USB capture does not validate the
analog outputs.
