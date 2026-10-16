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
Follow and Harmony combinations require their own integration checks.

No audio tracks or Scale Quantizer settings are involved. On a cold project
load, stock 1.40C clamps saved KEY values 25–84 to 24 (**B Minor**). Saving
that bank on stock writes the normalized value, losing the extended mode.
Other bank files are not rewritten merely by loading the project. Before
returning to stock, select OFF or an original Major/Minor choice and save,
or keep a separate backup of the extended-mode project.

## Verification

Run `make check REMIX=midi-scales`; the linked-code gate executes
all 84 combinations over all 128 MIDI notes and checks the formatter bounds.
The installed encoder and output detours are checked, including all eight
tracks, stock Major/Minor continuation, surrounding bytes and registers.
Native Part storage is reused. A separate full-firmware compatibility test
boots candidate, stock 1.40C, then candidate again with a disposable virtual
card and uses native SAVE PROJECT at each stage:

```sh
.venv/bin/python tools/verify/verify_midi_scales_stock.py --project /path/to/project
```

It covers all 256 byte inputs across 16 banks, four working Parts and eight
tracks, comparing loaded RAM, the current bank's saved work/strd fields and
untouched other-bank fields. The candidate preserves 0–84; stock clamps at
24. Receipt: `out/midi-scales-stock/receipt.json`. This cold-load/save test
does not qualify retained-memory startup, physical controls or hardware.
Emulator LCD captures and the repeatable manual capture group are included in the
manual usage page. They demonstrate OFF, C Major, C Dorian and C Mixolydian
on ARP SETUP at BUILD=91. Separate Octatrack MKII testing of OCTABAMS1
(source `9c30ec46`) passed scale playback, Part Reload, project save/load,
power cycles and a stock 1.40C round trip. See the
[remix hardware evidence](../../remixes/test/midi-scales/DEVELOPMENT.md#hardware-evidence)
for the tested modes, saved-file checks and remaining limits.

The extended KEY selector uses the stock movement accumulator at four raw
counts per choice, capped to one choice per report. This keeps nearby scale
choices selectable without changing their saved IDs. Physical feel is untested.

## First playing workflow

Set a track's output channel and program a few notes. Open MIDI ARP SETUP
with FUNC + AMP, then press F to enable KEY and turn F to choose C Dorian. The sequencer's scale
correction uses C, D, Eb, F, G, A and Bb. KEY OFF removes scale correction.


## Pinned author source

The adapter pins [author commit ffc10885](https://github.com/radiohagen/octatrack-modules/commit/ffc10885b6cf61fb55f7998888389864afd0c48c)
(the original source snapshot is `9d31ce2ff977205bdd3c17a58e55f86bc11376ac`;
subsequent changes correct the radiohagen credit and source URL)
from `upstream/`. That review branch contains this module alone. Assembly
SHA-256 matches the completed native implementation; the source manifest now
resolves its path relative to itself. Octabam owns the gate and machine harness.

The adapter's `Linked.reference` checks the 870-byte standalone author runtime
at `0x40a955e0` on every build (SHA-256
`e265a08d11b72cc6806c6ac5212969b828c28e2c34681ae088c686e51db8c806`).
This reference was measured from the native source in integration commit
`8f8e00d061d17a890a3b01d5f340492f912712e2`. Native and pinned-adapter
standalone images are byte-identical at BUILD=79. Future Follow/Harmony
variants need their own references and combination checks.
