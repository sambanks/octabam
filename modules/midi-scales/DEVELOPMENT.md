# midi-scales implementation and verification

Extends the existing **KEY** control at the bottom right of MIDI ARP SETUP
(FUNC + AMP), without moving controls or replacing the graph.

## Controls

Press F to enable or bypass KEY; turn F to select any of the 12 keys in Major, Dorian, Phrygian, Lydian,
Mixolydian, natural Minor or Locrian. Encoder order groups modes by key.
The stock values 1–24 still mean exactly the original Major/Minor pairs;
25–84 append the other five modes. OFF remains zero. The existing Part
byte, working mirror, dirty flags, save/reload and Part copy store the choice.
It is therefore a **Part setting**, not a new per-pattern project field.

## Composition

Select `MIDI SCALES` in the remix. This module works independently. It extends stock sequencer/arp output
quantization; it does not generate chords. Existing Major/Minor playback
keeps stock quantization. Added modes use nearest scale notes, ties downward.
The MIDI Follow composition has linked-code and full-firmware emulator coverage,
plus targeted MKII USB MIDI tests of four-note output, releases and sustained
load. Those hardware tests do not cover every scale choice. A full Harmony
composition is not qualified by this module's checks.

No audio tracks or Scale Quantizer settings are involved. On a cold project
load, stock 1.40C clamps saved KEY values 25–84 to 24 (**B Minor**). Saving
that bank on stock writes the normalized value, losing the extended mode.
Other bank files are not rewritten merely by loading the project. Before
returning to stock, select OFF or an original Major/Minor choice and save,
or keep a separate backup of the extended-mode project.

## First playing workflow

Set a track's output channel and program a few notes. Open MIDI ARP SETUP
with FUNC + AMP, then press F to enable KEY and turn F to choose C Dorian. The sequencer's scale
correction uses C, D, Eb, F, G, A and Bb. KEY OFF removes scale correction.

## Pinned author source

The adapter pins [author commit 0ebe11e7](https://github.com/radiohagen/octatrack-modules/commit/0ebe11e7f19fd6c48bf0109544d5da84326db86d)
from `upstream/` and loads its MIDI Scales manifest and assembly. The original
source snapshot was `9d31ce2ff977205bdd3c17a58e55f86bc11376ac`; `ffc10885`
was the earlier standalone review pin. The source manifest resolves its path
relative to itself. Octabam owns the gate and machine harness.

For selections without MIDI Follow or MIDI Harmony, the adapter retains the
fixed `Linked.reference` for the 870-byte standalone author runtime at
`0x40a955e0` (SHA-256
`e265a08d11b72cc6806c6ac5212969b828c28e2c34681ae088c686e51db8c806`).
This reference was measured from the native source in integration commit
`8f8e00d061d17a890a3b01d5f340492f912712e2`. Native and pinned-adapter
standalone images were byte-identical at BUILD=79.

Follow and Harmony compositions select additional author code and import final
runtime addresses, so they cannot use that standalone hash. The image gate
`tools/verify/verify_midi_scales_reference.py` freshly assembles the pinned author
unit with the selected module options, then links it at its installed address
using the final imported symbols. It reads the actual image's loader table,
checks and unpacks the runtime payload, and compares the installed MIDI Scales
unit's complete size and bytes with that fresh author build. The gate runs for
standalone and composed selections; the fixed standalone reference remains an
additional check.

Run it against the current build with, for example:

```sh
.venv/bin/python tools/verify/verify_midi_scales_reference.py midi-follow-events
```

This proves author-source, option and linking fidelity. Musical behavior is
checked separately by `verify_midi_scales.py` and the selected composition's
gates; matching author bytes alone does not qualify a full remix or hardware.
