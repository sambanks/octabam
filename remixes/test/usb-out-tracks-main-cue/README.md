# `usb-out-tracks-main-cue` — USB on the stock effects

The stock chooser plus USB at LAYOUT TRACKS MAIN CUE, for testing the twenty-channel USB stream on a unit that runs stock projects: no FX1 stations, no chooser changes, no project stamping. Bryan T's test remix.

## What is in it

- **USB** (markandrus, [octemu](https://github.com/markandrus/octemu), MIT) — MIDI in and out over USB, mirroring DIN; at LAYOUT TRACKS MAIN CUE: at USB high speed, track N's post-FX, pre-fader L/R on channels 2N−1/2N, MAIN on 17–18, CUE on 19–20, 44.1 kHz, 24-bit. At full speed, the stereo sum of the tracks. Track LEVEL, the crossfader and MAIN volume are not in channels 1–16. [`modules/usb/README.md`](../../../modules/usb/README.md).
- the 14 stock FX2 effects.

## Build

```bash
make image REMIX=usb-out-tracks-main-cue BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=usb-out-tracks-main-cue` runs every gate first. OS upgrades still need DIN MIDI or the card.

## Using it (macOS)

1. Connect the unit to the computer over USB.
2. **Audio MIDI Setup** lists "Elektron Octatrack DPS-1": a 20-channel 44.1 kHz input and a MIDI port. If it does not show: `system_profiler SPUSBDataType | grep -A12 Octatrack`.
3. In a DAW, select that device as the input. Channels 1–2 are track 1, 3–4 track 2, … 15–16 track 8, 17–18 MAIN, 19–20 CUE.
4. Record from the command line, 60 s, all twenty channels:

   ```bash
   sox -t coreaudio "Elektron Octatrack DPS-1" -c 20 -r 44100 -b 24 take.wav trim 0 60
   ```

5. Device counters: `brew install libusb`, install `pyusb`, then `tools/hw/usb_counters.py --watch 1`. The Mac-specific Python setup is in the script's header. `python3 tools/harness/click_scan.py take.wav` lists discontinuities per channel.
