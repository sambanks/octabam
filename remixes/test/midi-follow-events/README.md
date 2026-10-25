# MIDI Follow with EVENTS clients

Test selection combining MIDI Follow, EUCLID, PLOCKS P2, MIDI Scales and MIDI
Loopback. Follow keeps its own rhythm and register while EUCLID processes audio.
No standard remix selection is changed.

Build and check with `make check REMIX=midi-follow-events`. The module gates
check shared hook ownership, Follow history and note releases, EUCLID audio
and controls, and editor event contracts. Project-based checks require a
fixture. Hardware testing of this combination remains outstanding.
