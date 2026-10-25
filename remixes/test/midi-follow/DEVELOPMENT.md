# MIDI Follow test remix

Selects MIDI Follow, MIDI Part State and EVENTS with stock audio effects. No standard
remix selection is changed. Harmony and Scales are not required or selected.

Run `make check REMIX=midi-follow` for the standalone image gates. The
[module developer notes](../../../modules/midi-follow/DEVELOPMENT.md) describe
routing, register, response and optional project-based emulator checks.

Settings are saved in the native Part. RFOL defaults OFF; when enabled, FIXED
register defaults to octave 3. Other register modes and TRIG/LIVE updates are
available through the FOLLOW window.

Hardware testing remains outstanding. Emulator results do not establish
physical MIDI timing or external-instrument behavior.
