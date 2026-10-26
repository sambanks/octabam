# MIDI Loopback test remix

MIDI Loopback and STORE native Part access with stock audio effects. Every track defaults
to EXT; the emulator scenarios select Part-scoped INT/BOTH routes.

- Build and check: `make check REMIX=test/midi-loopback`.
- Project-backed routing: `.venv/bin/python tools/verify/verify_midi_loopback.py --project /path/to/project`.
- Add `--controls` for filter CC locks, MIDI LFO and live CC knobs.
- Add `--routing` for eight simultaneous tracks with mixed destinations.
- [Module developer notes](../../../modules/midi-loopback/DEVELOPMENT.md)
  define emulator coverage, scoped MKII results, measured latency and limitations.
