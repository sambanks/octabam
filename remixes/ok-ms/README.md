# `ok-ms` — KITS + MIDI SCENES

The two Part mods together on the stock effects. OKMS1 (14 Sep 2026, on
the unit of midisc's author) was the first image composed of Em's Octakit
and MIDI SCENES; since 6 Oct 2026 KITS takes Octakit's place.

## What is in it

| module | what you get |
|---|---|
| [KITS](../../modules/kits/README.md) | 255 named Kits per project; each pattern plays its Kit through the stock Part slots; old projects migrate on load (Octakit's kits3a/b.work are imported). MKII PART / FUNC + PART open LOAD / SAVE KIT, FUNC + CUE reloads. |
| [MIDI SCENES](../../modules/midi-scenes/README.md) (bkkbrls-del, [midisc](https://github.com/bkkbrls-del/midisc)) | scene locks for the MIDI tracks: a second lock table the panel never had; hold, readout, unlock, XF morph, scene clear / copy / paste. Phase 1 of the rewrite: RAM only, nothing is saved. |

The fourteen stock FX2 effects are listed, so the chooser is stock's.

## Where it has run

With Octakit: midisc's author's unit, 14 Sep 2026 (OKMS1, then OKMS2 with
the KITS RELOAD bridge; the MIDISC2.0 build). With KITS: under the port
(`verify_kits`), not flashed. The rewritten MIDI SCENES is checked against
MIDISC2.1 under the port (`verify_scenes`); it has not run on a unit.

## How to flash

```bash
make image REMIX=ok-ms BUILD=1      # -> out/OCTATRACK_OCTABAM1.bin (card) + out/OCTATRACK_OS1.40C_OCTABAM1.syx (MIDI)
```

[BUILDING.md](../../docs/guide/BUILDING.md) has each step from a fresh
machine (section 0: what to install first, uv included) to a flashed unit (macOS, or Linux/WSL2 in its section 1a) and the
recovery path; `make emu-cf` then `make check REMIX=ok-ms` runs every gate
first. **KITS writes kits.work into each project it loads:** back up the
card first. A stock OS ignores kits.work and plays the Parts as saved.
