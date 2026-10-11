# `usb-out-main-cue` — USB AUDIO OUT MAIN CUE on the stock effects

The stock chooser plus USB MIDI and USB AUDIO OUT MAIN CUE, for testing the four-channel (MAIN + CUE) stream on a unit that runs stock projects: no FX1 stations, no chooser changes, no project stamping.

## What is in it

- **USB MIDI** and **USB AUDIO OUT MAIN CUE** (markandrus/octemu; the MC variant Bryan T's): USB-MIDI mirroring DIN; four 24-bit channels, MAIN L/R + CUE L/R, at the same 250 us cadence as USB AUDIO OUT TRACKS MAIN CUE/FULL (not USB AUDIO OUT MASTER's 1 ms); full speed carries MAIN alone. [`modules/usb-audio-out`](../../../modules/usb-audio-out/README.md#main-cue).
- the 14 stock FX2 effects.

## Status

Port only (`verify_usb`, 27 Sep 2026): four channels in 192-byte packets every 250 us, each carrying only its own source (MAIN L, MAIN R, CUE L, CUE R); full speed sends correctly sized two-channel packets, whose content the gate does not check (as for OUT TRACKS MAIN CUE and OUT TRACKS). Not yet on a unit. The MAIN+CUE-only high-speed stream itself ran on hardware as usbin-test's AUD_IN4 (Bryan T's MKII, 26 Sep 2026), as a slice of the twenty-channel producer rather than this standalone one.

The same stream ran on hardware beside the four-channel USB AUDIO IN in usbin-test's `usb-io` (build 16, 27 Sep 2026); this remix itself has not been flashed. `usb-io-main-cue-abcd` is that pairing on the placed-section path; `usb-io-main-cue-ab` and `-cd` pair it with a stereo return.

## Build

```bash
make image REMIX=usb-out-main-cue BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=usb-out-main-cue` runs every gate first.
