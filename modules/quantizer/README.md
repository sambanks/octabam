# `quantizer` — SCALE QUANTIZER

The PTCH knob and the chromatic trig keys snap to a scale built on a root
(since 2.13 the MIDI tracks' NOTE knob, NOTE locks and MIDI CHROMATIC
keyboard too), and the synth gets a glide time: a SCALE row, a ROOT row and a GLIDE row in
PROJECT > CONTROL > SEQUENCER, built from
[timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules)
(submodule `upstream/`, pinned to `v2.14` (`39dc5d8`)). `Kind.CF_PATCH`: one
DRAM unit (`quantizer.s`), a 192-byte ROM core (`core.s`) and two pinned
ROM stubs (`keys.s`, `scale.s`), detours, pokes and a `TableGrow` for the
menu rows. No DSP code, no FX2 row.

SCALE (OFF, then 24 scales): the PTCH knob on the PLAYBACK page of a
STATIC / FLEX / PICKUP track steps to the next scale degree, on the Part's
value and on a step's lock; a [TRIG] key in CHROMATIC trig mode snaps to the
nearest degree before it becomes the pitch the voice, the recorded lock and
the screen see. ROOT (C .. B, since 2.9, the row under SCALE): the scale is
built on the root -- the knob, the locks, the keys and the synth's chord
snap all read one root-rotated mask -- key 1 of the CHROMATIC keyboard
sounds the root (the number beside the keyboard reads the root's name, "A
0"), and a sample track's keyboard plays the one complete root-to-root
octave the stock range holds (the other keyboard position is the partial
octave on the side that clamps fewer keys). ROOT C is 2.8's behaviour byte
for byte; SCALE OFF ignores ROOT. GLIDE (OFF, 1..127): the slide time of
the synth's and a sample track's legato (the LEG box on every audio track's
AMP SETUP page is the legato switch: OFF / MONO on a sample track, OFF /
MONO / POLY on a synth track); polyphonic chromatic keys on a synth track
whose VOIC is 2..4. Live recording on a synth track writes the played note
length as an AMP HOLD lock and hands every recorded key to the synth
engine, which records fingered chords. SCALE, GLIDE and ROOT are
battery-RAM bytes (`0x100b14ec` / `0x100b14ed` / `0x100b14ee`), so they
survive a power cycle like the stock project settings; ROOT is saved as
`#SEQUENCER_ROOT` after the SCALE line. Since 2.10 a track with FM SYNTH
chosen in SYNTH MACHINE's machine list is a synth track for the PTCH knob
and the CHROMATIC keys, as a marker-file track is; since 2.11 a SY DRUM
track is one too (semitone PTCH, the keys, MIDI), mono, its legato keys
reaching the engine -- assembled only when SY DRUM is in the remix, so
without it the unit is 2.10's. `upstream/quantizer/README.md` is the full
description, with what was measured and what was inferred.

## MIDI tracks (2.13)

With a scale on, SCALE and ROOT act on the MIDI tracks as on the sample
tracks: the NOTE knob (the Part's value) steps to the next scale note in the
turn direction instead of one semitone; NOTE locks do the same (a [TRIG]
key held in GRID RECORDING, and the lock a NOTE turn writes in LIVE
RECORDING); the MIDI CHROMATIC keyboard plays the scale from ROOT (key 1 =
the root, each key its note plus ROOT snapped to the nearest scale note,
the lower on a tie; the readout beside the keyboard reads "A 3" where stock
reads "3"). The note-on, the arpeggiator fed by the keys, the note-off and
LIVE RECORDING carry the snapped note, and a key's note-off is the note its
press sent, so a SCALE or ROOT change with keys held leaves nothing hanging.
Not snapped in this version: NOT2..4 (semitone offsets from NOTE), TRAN,
the arpeggiator's own notes, MIDI IN (thru and the auto channel), scene locks
and the LFOs. An option for the chords, TRAN and the arpeggiator to follow
the scale is planned for a later version, together with a per-track switch
that exempts a MIDI track from the scale; until then a drum track is
programmed with SCALE OFF, and stored notes are never changed. The track's
stock ARP SETUP > KEY still forces everything a track plays into a key.
SCALE OFF is stock (every new detour replays what it displaced); no project
or Part format change.

Three new hooks: `0x40055382` (the knob handler's clamp to the max, one step
before the store `0x4005538a`, which stays stock), `0x40050b98` (the MIDI
p-lock editor's store) and `0x400436a8` (the MIDI CHROMATIC key press).
The knob's hook sits before the store because octabam's MIDI SCENES detours
the store itself (`scn_pwrite` at `0x4005538a`): with the hook where it is
the two compose (this module decides the value, MIDI SCENES' detour stores
it and runs its mix), and the ledger accepts SCALE QUANTIZER with MIDI
SCENES; a pre-release head that hooked the store itself was refused
(`hook site: quantizer and midi-scenes both claim 0x4005538a`). A MIDI SCENES
scene lock on NOTE (set with a scene key held) is not snapped.

**The MIDI CHROMATIC freeze, fixed (Modwerk #264).** From 2.9 to 2.12 the
keyboard drawer's octave number was hooked at `0x400449b8`, but stock's MIDI
branch jumps to `0x400449be`, inside the hook's pad, so on a MIDI track the
octave was never pushed and entering CHROMATIC froze the unit (every public
tag 2.9 .. 2.12, `octatrick` included). The Modwerk contributors found it
([repeat98/modwerk](https://github.com/repeat98/modwerk) #264, MIT) and
moved the hook to the common push `0x400449be`; 2.13 takes that form.

## Measured

- At `v9.1`, remixes `octatrick` and `octatrick-usb` built byte-identical
  with the module sources as a plain `modules/<name>/` directory and as this
  wrapper over the submodule (same base, same build reports), and
  byte-identical to the OCTATRICK9 images Tim flashed (built on
  upstream `0e93543`; upstream's changes since touch modules these
  remixes do not carry).
- In the ColdFire port through the virtual panel, per feature
  (`upstream/quantizer/README.md` "Measured" and "ROOT, and the move into
  DRAM"): the knob and the keys under each scale, ROOT on synth and sample
  tracks (both keyboard positions, the readout), SCALE OFF stock, the SAVE
  lines and the warm boot of the three bytes.
- 2.10 / 2.11 (8 - 9 Oct 2026, the port): the CHROMATIC keys on a track
  that chose FM SYNTH or SY DRUM in the machine list, as on a marker-file
  track (`upstream/synth/README.md`, the machine-list sections, and
  `upstream/sy-drum/README.md`).
- 2.13 (12 Oct 2026, the pinned `ot_emu`, the `octatrick` selection on
  `063a426`; `upstream/quantizer/README.md` "MIDI tracks (2.13)"): the NOTE
  knob in 8 SCALE / ROOT settings x 8 start values x 1..3 clicks either way,
  384 of 384 as a model of the rules, NOTE locks 20 of 20; 240 MIDI CHROMATIC
  key presses, every note-on as the model and with its note-off; SCALE OFF:
  the MIDI events of the stock OS; the sequencer (chord notes, TRAN, ARP SETUP
  KEY, the arpeggiator) and MIDI IN: the same MIDI as 2.12 under four
  settings; the audio tracks equal to 2.12 value for value; 2.12's image
  freezes on MIDI CHROMATIC, 2.13 draws the keyboard and plays. With MIDI
  SCENES (a scratch remix of this module, SYNTH MACHINE, MIDI SCENES and STORE
  on `6e4aeb76`): the knob gate 409 of 409, the LIVE RECORDING lock, and
  MIDI SCENES' scene locks writing the same lock table and sending the same
  MIDI with and without this module. Cost (emulator instruction counts, not a
  hardware share): a MIDI CHROMATIC press 6 with SCALE OFF (stock 2), 49..77
  with a scale on; a NOTE knob turn 10 with SCALE OFF (stock 5), 104..278 for
  1..3 clicks; a NOTE lock turn 8 (stock 2), 117..302; the sequencer tick is
  not hooked. The DRAM unit grows 3,576 -> 3,952 B; the ROM units are
  unchanged.

## On the unit

- 26 Sep 2026: `OCTATRICK9` (remix `octatrick-usb`) on Tim's Octatrack MKI.
- Every test build since, 2.3 .. 2.8, flashed on the same MKI from Tim's
  own tree ([timhastie/octatrick](https://github.com/timhastie/octatrick),
  the same wrappers over the same submodule), and the 2.9 line up to the
  build before its last two fixes (ROOT and the DRAM unit included). The
  last two 2.9 fixes (the synth's sequencer trigs and index ramp) are
  emulator-verified on `octatrick` (`make check` on this tree).
- 2.10 / 2.11's machine-list reads: emulator-verified (the sources are the
  same at `v2.11` and `v2.12`).
- 13 Oct 2026, reported by the author on the same MKI: 2.13's MIDI tracks
  and the #264 form (the sources are the same at `v2.13` and `v2.14`) in
  Modwerk's FM Synth 0.1.5 (the 2.13 quantizer bundled; MAIN OS SHA-256
  `37661aee...`, not an octabam build): the NOTE knob and NOTE locks step
  through the scale, the CHROMATIC keys follow ROOT, chords and the
  arpeggiator as before, CHROMATIC on a MIDI track no longer freezes,
  SCALE OFF as before, SCALE and ROOT kept over a power-cycle; and in
  OCTATRICK 2.14 (`octatrick` at `v2.14`, built by his own tree from
  octabam `6e4aeb76`; MAIN OS SHA-256 `c367d8bc...`, byte for byte this
  tree's `octatrick` bus), its test sheet. MIDI gear and play time were
  not recorded.

## How it is built

Source: `upstream/` is Tim's repository (submodule, pinned to `v2.14`
(`39dc5d8`)). Nothing inside `upstream/` is edited here. The manifest here
(`manifest.py`) executes `upstream/quantizer/manifest.py` from the source on
disk and re-exports its `MODULE`; that manifest derives its source paths
from its own directory, so the same file builds at `modules/quantizer/` in
Tim's tree and at `modules/quantizer/upstream/quantizer/` here. Since 2.9
the quantizer is a DRAM unit of the platform runtime (`quantizer.s`,
`Linked(dram=True)`, linked with the synth's engine and depacked at boot
into the arena reserve, `docs/contributing/PLACEMENT.md`); the OS image keeps
`core.s` (192 B: the boot clamps, the defaults and the root-rotated scale
mask, in ROM so the pinned trampoline can name it at link time and so the
three bytes are sane whether or not a runtime was depacked) and the two
pinned stubs, the key trampoline and the scale trampoline (`KEYS_AT`,
`SCALE_AT`), that SYNTH MACHINE's engine reads. The boot order was checked
under the port: the loader runs from the boot redirect before `.data` and
`main`, and both detour sites of the DRAM unit run from `main`. The SCALE,
GLIDE and ROOT bytes are battery-backed RAM (`GLIDE_AT` and its
neighbours), clamped by two `jsr` detours where stock sanitises its own
settings block. The ROM footprint went from 3,319 B at 2.8 (3,268 + 45 + 6)
to 243 B (192 + 45 + 6), so the zero run holds DIRECT JUMP's cave beside
CF METER's descriptor clone again.

## Updating

Bump the submodule pin and rebuild; SYNTH MACHINE reads the pinned
addresses, so a pin that moves them needs both modules bumped together.
