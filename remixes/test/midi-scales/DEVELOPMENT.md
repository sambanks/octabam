# MIDI Scales Test Remix

Selects MIDI SCALES and all fourteen stock effects, with fallback NONE.
It adds seven-mode KEY selection to native MIDI ARP SETUP. It does not
select Follow, Harmony, Loopback or any replacement effect.

```sh
make check REMIX=midi-scales
make reach RUN=1 KEEP=1 TESTS=1
.venv/bin/python tools/verify/verify_midi_scales_stock.py --project /path/to/project
```

The linked-code gate checks 84 key/mode combinations over 128 notes,
installed encoder/output hooks and formatter bounds. The project-backed
test checks cold load and native save across candidate, stock 1.40C and
candidate again on a disposable virtual card. Stock clamps extended KEY
values to B Minor when loaded and loses them when the bank is saved.

See [MIDI Scales](../../../modules/midi-scales/README.md) for controls,
source provenance, compatibility and evidence boundaries. Emulator screenshots
show BUILD=91.

## Hardware evidence

On 16 October 2026, OCTABAMS1 at source `9c30ec46` was tested on Octatrack
MKII. The tester confirmed scale playback, Part Reload, project save/load
and power-cycle checks passed. No MIDI event capture or timing measurement
was supplied.

The physical S1 → stock 1.40C → S1 round trip also passed. Stock saved
Part 1/T1 C Dorian and Part 1/T8 D Mixolydian as B Minor; Part 2/T8 C Major
remained unchanged. Both bank01.work and bank01.strd were read back from
the device card to verify those values. After returning to S1, the tester
confirmed the converted settings persisted and an untouched reference
project restored its original extended modes.

The [hardware report](https://github.com/sambanks/octabam/pull/739#issuecomment-6223792844)
records package hashes and the test scope. MKI, MIDI timing, exhaustive
physical key/mode coverage, encoder-feel and arp stress tests, and
Follow/Harmony integration remain unverified on hardware.
