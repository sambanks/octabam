# Build and flash

From nothing installed to a flashed unit. Every image is built on your own
computer from your own copy of Octatrack OS 1.40C. This page is the short
version of the [detailed build guide](https://github.com/sambanks/octabam/blob/main/docs/guide/BUILDING.md),
which includes Linux/WSL2 setup and toolchain notes.

!!! warning "This is not official Elektron firmware"
    Flashing a modified OS can leave the unit unusable until you recover it
    ([Safety and recovery](safety.md)), and puts your warranty in
    question. You flash at your own risk. **Do not share a built image**: a
    built `.bin` or `.syx` contains Elektron's OS.

## What you need

- A Mac with the Xcode Command Line Tools (`xcode-select --install`) and
  [Homebrew](https://brew.sh), or Linux / WSL2 (WSL 2, not WSL 1).
- `python3` 3.10 or newer.
- `cmake` and [uv](https://docs.astral.sh/uv/): `brew install cmake uv`.
- An Octatrack MKI or MKII on OS 1.40C. Elektron's MKI and MKII download
  pages serve the byte-identical file. octabam's own effects have only
  been tested on an MKII.
- A CompactFlash card in the unit, for the fast flashing path.
- For the MIDI flashing path and recovery: a 5-pin DIN MIDI interface into
  the Octatrack's MIDI IN, and a SysEx app (SysEx Librarian on macOS) or
  `make midi-flash`. The Octatrack's own USB port does not take an OS
  upgrade.
- Stable power. Do not move the unit while it flashes.

## Get the repository and the stock OS

```bash
git clone --recurse-submodules https://github.com/sambanks/octabam
cd octabam
make setup            # installs the toolchain; ends with "setup complete"
make emu-setup        # the emulator's Python environment
make os               # downloads OS 1.40C from Elektron, prints its SHA256
make recon            # unpacks it to out/raw/, the file every build reads
```

`make os` downloads `OCTATRACK_OS1.40C_dist.zip` from Elektron's site and
prints its SHA256; expected
`370c55a3dad3996b8e4b46400a205066fdaf185ad4d0255a3a3f835060573ff0`.
`--recurse-submodules` fetches the module authors' repositories; if you
cloned without it, `git submodule update --init`.

## Build the image

```bash
make image REMIX=octabam-bus BUILD=91
```

Substitute any remix name. Output:

```
out/OCTATRACK_OCTABAM91.bin           the card image
out/OCTATRACK_OS1.40C_OCTABAM91.syx   the MIDI image
```

`BUILD` is a one- or two-character tag of your choosing (digits; past 99 a
letter then a digit: `A0` is 100). It becomes the unit's OS version string
(`OCTABAM91`) and the suffix on any octabam effect's name, so a unit can
always be traced to the build it runs. Bump it every time you flash.

The build prints what it did: every module placed, every hook wired, every
module checked against its author's own build. It refuses, with the
reason, rather than write an image it cannot prove.

Before you flash, run the checks for the remix:

```bash
make check REMIX=octabam-bus
```

This builds the image, runs its gates and boots it under the local emulator.
It is the minimum project check; a successful build alone does not establish
that an image works. `make check` does not replace a hardware run.

## Back up

Flashing the OS does not touch the CF card. Back it up anyway (USB DISK
MODE, copy everything). Any remix carrying KITS writes `kits.work` into
each project it loads; a stock OS ignores that file and plays the Parts as
saved.

## Flash from the card

1. On the unit: PROJECT → SYSTEM → USB DISK MODE → YES. The card mounts on
   the computer.
2. Copy `out/OCTATRACK_OCTABAM91.bin` to the root of the card, not inside
   a folder.
3. Eject the card on the computer, then leave USB DISK MODE on the unit.
   Without the eject, the unit can read a truncated file.
4. PROJECT → SYSTEM → OS UPGRADE → YES and confirm.
5. Wait for the unit to finish and restart, then power-cycle it once more
   before judging anything: an OS upgrade does not clear DSP RAM.

## Flash over MIDI

This path also works on a unit that does not boot.

1. Your interface's MIDI OUT → the Octatrack's MIDI IN (DIN).
2. Power off, hold FUNC, power on → STARTUP MENU.
3. TRIG 3 (MIDI UPGRADE) → "READY TO RECEIVE MIDI UPGRADE".
4. Send `out/OCTATRACK_OS1.40C_OCTABAM91.syx` from a SysEx app, or
   `make midi-flash PORT=<port> SYX=<file.syx>`, which paces the messages
   at the DIN rate. Filter MIDI clock on that port and merge nothing else
   into it: through a Midihub, a blank preset with one pipe flashed where
   a performance preset ended in CHECKSUM ERROR. If the unit loses sync,
   re-enter the Startup Menu and send again slower.
5. Wait through PREPARING FLASH → UPDATING FLASH. Do not power off or
   disconnect during either.
6. Let it finish booting, then power-cycle.

## After the flash

1. The version. The boot screen and SYSTEM STATUS → OS VERSION read
   `OCTABAM91`. If it still says `1.40C`, the stock OS is running.
2. Stamp old projects after flashing a remix that changes an effect's
   parameter layout (the bus engines, and RIG HOSTS' T1/T5 FX2
   assignments):

   ```bash
   python3 tools/hw/ot_project.py stamp-defaults "<card>/<set>/<project>" <remix>
   ```

   A part saved under an older layout feeds the new one its old bytes and
   the sequencer can stall on the first play. A project made on the unit
   after the flash needs no stamp.

If the unit misbehaves, the failure register lists what has gone wrong and
why: https://github.com/sambanks/octabam/blob/main/docs/contributing/FAILURE_MODES.md

Back to stock, always: [Safety and recovery](safety.md).
