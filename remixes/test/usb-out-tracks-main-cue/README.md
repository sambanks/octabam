# `usb-out-tracks-main-cue` — USB on the stock effects

The stock chooser plus USB MIDI and USB AUDIO OUT TRACKS MAIN CUE, for testing the twenty-channel USB stream on a unit that runs stock projects: no FX1 stations, no chooser changes, no project stamping. Bryan T's test remix, 25 Sep 2026.

## What is in it

- **USB MIDI** (markandrus, [octemu](https://github.com/markandrus/octemu), MIT) — MIDI in and out over USB, mirroring DIN. [`modules/usb-midi/README.md`](../../../modules/usb-midi/README.md).
- **USB AUDIO OUT TRACKS MAIN CUE** (markandrus, octemu, MIT) — at USB high speed, track N's post-FX, pre-fader L/R on channels 2N−1/2N, MAIN on 17–18, CUE on 19–20, 44.1 kHz, 24-bit. At full speed, the stereo sum of the tracks. Track LEVEL, the crossfader and MAIN volume are not in channels 1–16. [`modules/usb-audio-out/README.md`](../../../modules/usb-audio-out/README.md).
- the 14 stock FX2 effects.

## Status

- 20 channels on Bryan's MKII as image 90 (25 Sep 2026): MAIN and CUE on their channels, level changes follow.
- The same modules ran beside the bus and the FX1 stations (the `usb-audio` remix, removed 30 Sep 2026) on Sam's MKII:
  - image 64, 16 bits (25 Sep 2026): enumerates on macOS as "Elektron Octatrack DPS-1" (16-channel input + MIDI port). Every channel carried its track. 9.6 minutes recorded with no discontinuities after the first 1.6 s of each stream. Device counters 0 underruns, 0 overruns. USB MIDI in took 7,950 messages/s for 185 s without a stall.
  - image 69, 24 bits (25 Sep 2026): 16 channels, every channel its track's tone, 3 minutes recorded (USBSIG 60 s, USBLOAD 120 s) with no discontinuities after 0.76 s; counters 0 underruns, 0 overruns. The start burst is on the right channels only.
- Also on Tim's MKI inside `octatrick` (then `octatrick-usb`, OCTATRICK9, 26 Sep 2026).
- Open: a burst of reordered samples 0.75–1.5 s after the host opens a stream, on four of five takes (`docs/contributing/FAILURE_MODES.md`).
- `verify_usb_align` runs this remix under the port: MAIN/CUE lag behind the tracks must read 0 samples.
- Not measured: DISK MODE entered with an audio session open, Windows, Linux hosts.

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
