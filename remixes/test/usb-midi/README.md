# `usb-midi` — USB MIDI on the stock effects

The stock chooser plus USB MIDI on the OT's own USB port. The unit appears to a host as card storage + a class-compliant MIDI port that mirrors the DIN ports.

## What is in it

- **USB MIDI** (markandrus, [octemu](https://github.com/markandrus/octemu), MIT) — MIDI in and out over USB. Incoming messages take the same path as DIN MIDI IN; everything the unit sends on DIN is also sent over USB. [`USB`](../../../modules/usb/README.md#usb-midi).
- the 14 stock FX2 effects.

USB's audio halves are built on its MIDI composite descriptor and ISR shim, and each audio layout has its own remix under `remixes/test/usb-out-*` and `usb-io-*`.

## Build and flash

1. Set up the repository and the stock OS: [BUILDING.md](../../../docs/guide/BUILDING.md) sections 0–2 (what to install first, then `make setup`, `make emu-setup`, `make os`, `make recon`).
2. Build:

   ```bash
   make image REMIX=usb-midi BUILD=1
   ```

   Optional first: `make emu-cf` then `make check REMIX=usb-midi`. `verify_usb` enumerates the image under the emulator.
3. Back up the card and flash from it: [BUILDING.md](../../../docs/guide/BUILDING.md) sections 4–5. Recovery: section 7.

OS upgrades still need DIN MIDI or the card. They do not work over USB MIDI.

## Using it (macOS)

1. Connect the unit to the computer over USB.
2. **Audio MIDI Setup** lists "Elektron Octatrack DPS-1" with a MIDI port. If it does not show: `system_profiler SPUSBDataType | grep -A12 Octatrack`.
