# `octatrick` and `octatrick-usb` — Tim Hastie's three modules on the stock effects

Two remixes built from [timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules) (the submodule under `modules/synth`, `modules/quantizer` and `modules/direct-jump`, pinned to `v9`). No octabam DSP code: the fourteen stock effects are listed with fallback NONE, the `usb-lean` pattern, so both DSP payloads, their dispatch and the effect chooser's rows stay stock and every existing project plays as it did.

| remix | adds | on hardware |
|---|---|---|
| `octatrick` | SYNTH MACHINE, SCALE QUANTIZER, DIRECT JUMP | no (emulator-verified, same modules as below) |
| `octatrick-usb` | the above + USB MIDI + USB AUDIO (markandrus, [octemu](https://github.com/markandrus/octemu)) | ✅ 26 Sep 2026, OCTATRICK9 on Tim's Octatrack MKI |

## What is in it

- **SYNTH MACHINE** — any FLEX track whose sample is named SYNTH*.wav (a silent 4 s marker file will do) plays a two-operator FM voice instead of the sample: PLAYBACK page PTCH RATO INDX RATE FDBK DEC, on the LFO page VOIC (1 = mono, 2..4 = paraphonic) and CHRD (32 chord shapes, lockable per step, snapped onto SCALE). The engine is a DRAM unit in the platform reserve; the page is a pinned ROM cave at the start of the second free gap. [`modules/synth/README.md`](../../modules/synth/README.md).
- **SCALE QUANTIZER** — a SCALE row (OFF, then 24 scales) and a GLIDE row (OFF, 1..127) in the same menu: the PTCH knob, its parameter locks and the CHROMATIC trig keys snap to the scale; GLIDE is the synth's glide time and 303-style legato on the keys. Four ROM units, detours, pokes and a `TableGrow` for the menu rows. [`modules/quantizer/README.md`](../../modules/quantizer/README.md).
- **DIRECT JUMP** — CHAIN AFTER's unused value 1 becomes DIRECT (option 2 of the list in PROJECT > CONTROL > SEQUENCER): a pattern chosen while the sequencer runs takes over at the next step boundary, at the step count the old pattern had reached, the Analog Four / Rytm direct jump. One ROM cave on the pattern-queue setter and the tick handler, four fixed pokes. [`modules/direct-jump/README.md`](../../modules/direct-jump/README.md).
- `octatrick-usb` only: **USB MIDI** and **USB AUDIO**, as in [`usb`](usb.md); the synth's engine and the USB units share one runtime.

## Status

- `octatrick-usb` as OCTATRICK9 on Tim's MKI (26 Sep 2026): the synth, the quantizer and direct jump work; USB audio streams all 20 channels (tracks 1–16, MAIN 17–18, CUE 19–20) — the first MKI run of the USB stream. MAIN/CUE were silent until a full power-off after the OS upgrade; power-cycle after flashing.
- Both remixes: `make check` ALL GATES PASSED; the images built here are byte-identical to the images Tim flashed, and byte-identical whether the module sources sit in `modules/<name>/` directly or under the submodule (the wrapper executes the same manifest).
- Direct jump under PER TRACK scales and across Parts was measured in the emulator (41 jumps; three Parts); the two limits found are in `modules/direct-jump/upstream/direct-jump/README.md`.
- Not carried together with `tempo-bus` (both use the second free ROM gap; the ledger refuses the pair).

## Build and flash

1. Set up the repository and the stock OS: [BUILDING.md](BUILDING.md) §1–2 (`make setup`, `make os`, `make recon`); clone with `--recurse-submodules` or run `git submodule update --init` so `modules/*/upstream` is populated.
2. Build:

   ```bash
   make image REMIX=octatrick-usb BUILD=1    # or REMIX=octatrick
   ```

   Optional first: `make emu-cf` then `make check REMIX=octatrick-usb`.
3. Back up the card and flash from it: [BUILDING.md](BUILDING.md) §4–5. Recovery: §6. Power-cycle the unit fully after the upgrade, and SAVE or SYNC TO CARD after changing project settings (SCALE, GLIDE and DIRECT are project settings).
4. USB on a host: [`usb`](usb.md) — Using it.
