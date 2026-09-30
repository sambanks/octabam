# `stems`: STEM REC alone

One ColdFire module and nothing else. For recording what the tracks play to the card, while the sequencer runs, as one file per track.

## What is in it

- **STEM REC.** MAIN MENU > STEMS, a fifth category: REC arms a take, or starts one if the sequencer is running. STOP ends it, and so does stopping the sequencer or reaching 60 minutes. T1 to T8 turn tracks on and off (all eight at boot), a status row shows the take's time, `DONE` or an error by name, and PEAK the ring's highest fill. Each enabled track is a 16-bit stereo file, `<set>/AUDIO/YYMMDD-HHMM/T<n>.wav`. `modules/stems/README.md`.

## Status

Never flashed. Measured under the ColdFire port: `python3 tools/verify/verify_stems.py stems` records takes and checks every sample against the track's own audio, and `python3 tools/verify/verify_stems_menu.py stems` presses the menu's keys on the MKII and MKI panels, a take included. Crosscheck's flash plan is carried as a record in `modules/stems/FLASH.md`; flash A gets its own. The stock facts STEM REC stands on are in `docs/firmware/STEM_REC.md`.

## Build

```bash
make image REMIX=stems BUILD=1    # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../docs/guide/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=stems` runs every gate first.
