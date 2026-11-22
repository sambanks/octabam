# `mods` — every ColdFire mod that fits in one image

The firmware modifications that change what the unit does without touching
the effects: the stock FX1/FX2 choosers stay as shipped, so every existing
project plays as it did. Not in it: SCENES P2 (its pool shares MIDI
SCENES' Part-window bytes, `Claims.part_window`), Tim Hastie's DIRECT JUMP
(it declares a conflict with DIRECT_JUMP_KYOTI) and SCALE QUANTIZER (its
2,916-byte ROM unit leaves CC MAP's 724-byte cave no run
in the free ROM; measured). Those are
[`octatrick`](../octatrick/README.md).

## What is in it

Each module's own page has the technical detail and the measurements.

| area | module | what you get |
|---|---|---|
| Kits | [KITS](../../../modules/kits/README.md) | 255 named Kits per project; each pattern plays its Kit through the stock Part slots |
| Scenes | [MIDI SCENES](../../../modules/midi-scenes/README.md) (bkkbrls-del, [midisc](https://github.com/bkkbrls-del/midisc)) | scene locks driven over MIDI: hold, morph, save, reload, clear, copy, paste |
| Patterns | [DIRECT_JUMP_KYOTI](../../../modules/direct-jump-kyoti/README.md), [RELOAD_FROM_PROJECT](../../../modules/reload-from-project/README.md) (Zac Kyoti) | an immediate pattern change ([PTN] + [YES]); reload from the project |
| MIDI | [CC MAP](../../../modules/cc-map/README.md) | CC 102–107 reach the FX2 effect's page-2 knobs, CC 108–111, 14 and 15 the FX1 effect's (stock reaches page 1 only) |
| Recorder | [RECORDER LOOP FIX](../../../modules/recorder-loop-fix/README.md) | the recorder loop click fixed: a fixed-RLEN take is exactly as long as the gap to the next arm, a re-trig on the buffer seeks the voice instead of restarting it, and sound-on-sound repeats the last sample where it played a zero |
|  | [RLEN PLEN](../../../modules/rlen-plen/README.md) | RLEN value PLEN: one loop of the track's pattern, so TRIG ONE + QREC PLEN records the next pass and stops |
| Fixes | [LOFI AMF FIX](../../../modules/lofi-amf-fix/README.md) (Bryan T) | stock LO-FI's AMF knob no longer jumps the pitch backwards |
|  | [BATCH_BUGFIXES](../../../modules/batch-bugfixes/README.md) (Zac Kyoti; DIRECT_JUMP_KYOTI requires it) | three stock fixes: the MIDI Plays-Free trig stall, the empty-pattern LED, the Part-change carryover |
| USB | [USB](../../../modules/usb/README.md) (markandrus, [octemu](https://github.com/markandrus/octemu)) | a class-compliant MIDI port mirroring the DIN ports, and a 20-channel 24-bit audio input on the computer: the tracks, MAIN and CUE |

The fourteen stock FX2 effects are listed, so the chooser is stock's.

## How to flash

```bash
make image REMIX=mods BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a
fresh machine to a flashed unit; `make check REMIX=mods` runs every gate
first. **KITS writes kits.work into each project it loads:** back up the
card first.
