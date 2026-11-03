# MIDI SRAM

Provides 16,384 bytes of retained storage for MIDI modules. Select **MIDI SRAM**
with **STORE native Part access**. It adds no panel controls and does not alter audio-step fields.

The pool uses protected bytes in the current bank's MIDI step records in SRAM.
Those bytes are excluded from native bank files and clipboards. Clients own
their allocation, checksum and checkpoint publication; this is not a project
file format or a replacement for saving.

Harmony's **MIDI TRACK** layout uses the full pool for its 8,192 steps and
track metadata. PLOCKS and MIDI Scenes retain their own separate allocations.
A reset that clears SRAM invalidates retained state; clients recover from
their validated project companions.

[Allocation contract, implementation and verification](https://github.com/radiohagen/octatrack-modules/blob/cb11475731eab5dc35f1ec6a93a497e6dcaaf77b/modules/midi-sram/DEVELOPMENT.md).

## Verification boundary

This integration is checked in software; it has not been flashed on an Octatrack.
The MIDI-only copy/clear guards and retained pool are exercised by
`verify_midi_sram.py`; audio-step fields retain their stock behavior.
