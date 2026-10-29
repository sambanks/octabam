# MIDI Follow with EVENTS clients

Test selection combining MIDI Follow, EUCLID, PLOCKS P2, MIDI Scales and MIDI
Loopback. Follow keeps its own rhythm and register while EUCLID processes audio.

Build and check with `make check REMIX=midi-follow-events`. The module gates
check shared hook ownership, Follow history and note releases, EUCLID audio
and controls, and editor event contracts. Project-based checks require a
fixture. Functional and project-backed checks have run in the emulator;
[developer notes](../../../modules/midi-follow/DEVELOPMENT.md#octabam-composition-and-full-firmware-captures)
record the pressure-qualification limit. Hardware testing of this combination
remains outstanding.
