# Building a remix, step by step

This guide walks through setting up a build machine, building a firmware image
from your own copy of Octatrack OS 1.40C, flashing it to your unit, and
returning to stock OS if needed.

**You do not need this guide to install a released remix.** The manual's
[Build and Install](https://sambanks.github.io/octabam/web-builder.html) page
builds Octabam, Octabam Verbs, or Octabam Bus (matching the release in
`tools/site/release.py`) directly in your browser from your local OS 1.40C file
without uploading anything, and covers the same installation steps as sections 5
and 5b below. [Safety and Recovery](https://sambanks.github.io/octabam/safety.html)
covers the recovery steps from section 7. Use this guide when building from
source—for a test or community remix, your own module selection
([COMPOSING.md](COMPOSING.md)), a development branch, or `main` ahead of a
release.

> **This is not official Elektron firmware.** Flashing modified firmware can
> leave your unit unable to boot until you recover it (section 7), and may
> affect your warranty. This project is not endorsed by, supported by, or
> affiliated with Elektron. Flash at your own risk.
>
> **Do not share built images.** A built `.bin` or `.syx` file contains
> Elektron's OS.

Choose a remix from [the remix index](../../remixes/README.md). The commands
below use `octabam` ([its README](../../remixes/octabam/README.md)); replace it
with any other remix name as needed.

## 0. What you need

- A Mac with Xcode Command Line Tools (`xcode-select --install`, providing
  `git`, `make`, and a C compiler) and [Homebrew](https://brew.sh), or Linux /
  WSL2 (see section 1a).
- `python3` (3.10 or newer; the core build uses only the standard library).
- `cmake` and [uv](https://docs.astral.sh/uv/). `make setup-mac` installs both;
  `make setup-linux` installs `cmake`, and section 1a shows how to install `uv`.
  `uv` creates `.venv` (`make emu-setup`, installing `unicorn`, `textual`, and
  `sounddevice`) for the label verification gates in `make check`.
- An Octatrack MKI or MKII running OS 1.40C. Elektron distributes the same OS
  file for both MKI and MKII, and octabam images work on both models.
- A CompactFlash card in the Octatrack (for the faster CF card install path).
- For recovery or MIDI flashing: a 5-pin DIN MIDI interface connected to the
  Octatrack's MIDI IN and a SysEx sender (such as SysEx Librarian on macOS), or
  `make midi-flash`. The Octatrack's USB port cannot be used for OS upgrades.
- Reliable power. Do not unplug or disturb the unit while flashing.

## 1. Get the repository and the toolchain

```bash
git clone --recurse-submodules https://github.com/sambanks/octabam
cd octabam
make setup
make emu-setup
```

`--recurse-submodules` fetches upstream module repositories (such as
`timhastie/octatrick-modules` under `modules/synth`, `modules/quantizer`,
`modules/direct-jump`, and `modules/tuner`) at their pinned commits. If you
already cloned without it, run `git submodule update --init`.

Run `make setup-mac` (installs `binwalk`, `radare2`, `m68k-elf-gcc`, `cmake`,
and `uv` via Homebrew) or `make setup-linux` (installs apt packages and runs
`scripts/m68k-toolchain.sh`, see section 1a) to install system dependencies and
then run `make setup`. `make setup-windows` prints WSL2 instructions. Running
`make setup` by itself expects `m68k-elf-gcc` on your `PATH`, checks out three
pinned vendored tools under `vendor/`, applies local patches, and builds them.
It is safe to re-run and prints `setup complete` when finished. `make emu-setup`
runs `uv sync --extra emu` to populate `.venv`.

### 1a. Linux and WSL2

The build requires Bash, Make, and CMake. It works on macOS and Linux, including
WSL2, but not native Windows. Follow
[Microsoft's WSL install guide](https://learn.microsoft.com/windows/wsl/install)
to set up WSL2. The instructions below assume Ubuntu (including Ubuntu on WSL2).

Clone the repository inside the Linux filesystem rather than `/mnt/c`. Building
over the 9p mount is slow, and Windows-side checkouts can lose executable bits
or introduce CRLF line endings that break shell scripts. You can still access
files from Windows Explorer at `\\wsl$\Ubuntu\home\<user>\octabam` (to play
rendered WAVs or copy built images to your CF card). In VS Code, use the **WSL**
extension.

`make setup-linux` runs the apt installation and toolchain build below, then
calls `make setup`. To run the prerequisite steps manually before `make setup`:

```bash
sudo apt update
sudo apt install -y build-essential cmake git curl unzip xxd binutils \
                    binutils-m68k-linux-gnu \
                    python3 python3-numpy binwalk radare2 pulseaudio-utils
sudo ln -sf "$(command -v m68k-linux-gnu-objdump)" /usr/local/bin/m68k-elf-objdump
curl -LsSf https://astral.sh/uv/install.sh | sh     # for make emu-setup
source $HOME/.local/bin/env
```

- `binwalk` and `radare2` are optional; `scripts/setup.sh` warns if they are
  missing and continues.
- `binutils-m68k-linux-gnu` provides an accurate ColdFire disassembler under a
  different binary name, which is why the symlink is needed.
  `scripts/disasm.sh emac` invokes `m68k-elf-objdump`; without it, the fallback
  is `radare2`, which mis-decodes ColdFire instructions
  (`docs/contributing/TOOLING.md` section 3). Verify the symlink with
  `scripts/disasm.sh emac 0x40003664 8`, which should print `msacl` rather than
  `invalid`. Place the symlink in `/usr/local/bin` rather than `~/.local/bin`,
  since non-login shells such as `wsl.exe -d Ubuntu -- bash script.sh` do not
  put `~/.local/bin` on `PATH`.

**The m68k cross-toolchain.** Building any remix with linked ColdFire modules
(KITS, MIDI SCENES, USB, or any DRAM module) requires `m68k-elf-gcc`, `as`,
`ld`, `objcopy`, and `nm`. `scripts/setup.sh` exits with an error if
`m68k-elf-gcc` is not on `PATH`.

**Build the bare-metal toolchain (recommended).** Module authors build with
`m68k-elf-binutils` 2.47 and `m68k-elf-gcc` 16.2.0 from GNU sources.
`scripts/m68k-toolchain.sh [PREFIX]` builds both with pinned source hashes
(defaulting to `$HOME/.local/m68k-elf`) and exits immediately if that GCC
version is already installed in `PREFIX`. Expect roughly an hour with two
compile jobs; limit parallelism if your machine has less than 4 GB of RAM:

```bash
sudo apt install -y libgmp-dev libmpfr-dev libmpc-dev libisl-dev zlib1g-dev libzstd-dev pkgconf texinfo
scripts/m68k-toolchain.sh /opt/m68k-elf
export PATH=/opt/m68k-elf/bin:$PATH
```

`pkgconf` is required; without `pkg-config`, binutils' configure script fails
with `--with-zstd was given, but pkgconfig/libzstd.pc is not found`.

**Alternative: Ubuntu's Linux-target tools.** These install much faster but
cannot build every remix. They also use a different binary prefix:

```bash
sudo apt install -y gcc-m68k-linux-gnu      # GCC 15.2.0; includes binutils 2.46
for t in as ld objcopy nm objdump gcc; do
  sudo ln -sf "$(command -v m68k-linux-gnu-$t)" /usr/local/bin/m68k-elf-$t
done
```

Because this assembler encodes certain branches differently, the `usbmidi` unit
in USB does not match the author's reference build and fails verification.
Remixes that cannot be built with these tools print `[SKIP]` with an explanation
(`tools/remix/prereq.py`), and `make accept` treats skips as failures. Build the
bare-metal toolchain if you need to build every remix.

## 2. Get the stock OS

```bash
make os
make recon
```

`make os` downloads `OCTATRACK_OS1.40C_dist.zip` from Elektron's website into
`downloads/`, unpacks it, and verifies the firmware SHA256 hashes:

- `OCTATRACK_OS1.40C.bin`: `34695b606eb00e1b4dded5fd0c4b66f3a460522a632e47d7416dbd220599e1ad`
- `OCTATRACK_OS1.40C.syx`: `0a8d2d2b35c2cc78fa338576adc1af0cbc094cef973255103165c73edd87f2b6`

The zip file's own hash is printed but not enforced because Elektron stamps
`Elektron EULA.txt` at download time. `make recon` extracts
`out/raw/section_3_MAIN_OS.bin`, which all builds read as input. Both
`downloads/` and `out/` are gitignored.

## 3. Build the image

```bash
make image REMIX=octabam BUILD=1
```

This produces three files:

```
out/OCTATRACK_OCTABAM1.bin            CF card firmware image
out/OCTATRACK_OS1.40C_OCTABAM1.syx    MIDI SysEx firmware image
out/<REMIX> <BUILD>.RMX               REMIX SWITCH image to boot from the card without flashing (section 5c)
```

`BUILD` is a one- or two-character tag of your choice (digits 1–99, then a
letter and a digit such as `A0` for 100, `A1`..`A9`, `B0` for 110, because
`Modulation` plus three digits exceeds the 12-character name limit). It appears
in the unit's OS version string (`OCTABAM1`) and as a suffix on octabam effect
names so you can always tell which build is running. Increment `BUILD` each time
you flash. You can also override the version string directly with
`VERSION=<up to 10 chars>`.

During the build, octabam prints every placed module, every wired hook, every
oracle comparison against upstream builds, and the total changed byte count. If
any check fails, the build stops with an error instead of writing an unverified
image.

### Optional: run the gates

```bash
make emu-cf                 # build the local ColdFire emulator (cmake) and boot stock OS once
make check REMIX=octabam    # build the remix, run verification gates, and boot under the emulator
```

`make check` runs in two parts: `make check-shared` (remix-independent checks:
ledger selftest, stock-ID audit across all remixes, docs, knob census, and
self-building module gates) and `make check-remix` (the selected remix's build,
cycle budget, and module gates). See
[docs/contributing/TESTING.md](../contributing/TESTING.md) for details on each
check. Expect several minutes for the shared checks and a few minutes per remix.
If you skipped `make emu-setup`, the label gates (`verify_labels`,
`verify_mode_names`, `verify_hidden`) report `[SKIP]`; if you skipped
`make emu-cf` or did not set `OT_PROJECT`, the project/set gates report `[SKIP]`
as well.

## 4. Back up

Flashing the OS does not modify the CF card, but back up your card anyway using
USB DISK MODE before proceeding. Note that any remix with **KITS** writes a
`kits.work` file into each project it loads (converting Parts into Kits); stock
OS ignores that file and plays the saved Parts normally.

## 5. Flash from the card

1. On the Octatrack, go to **PROJECT → SYSTEM → USB DISK MODE → YES** to mount
   the CF card on your computer.
2. Copy `out/OCTATRACK_OCTABAM1.bin` to the **root** directory of the CF card
   (not inside a subfolder).
3. Safely eject the card from your computer, then exit USB DISK MODE on the
   Octatrack. Skipping the eject can leave buffered writes unfinished and cause
   the unit to read a truncated file.
4. Go to **PROJECT → SYSTEM → OS UPGRADE → YES** and confirm. The Octatrack
   syncs the active project to the card first.
5. Wait for the upgrade to finish and reboot, then **power-cycle the unit one
   more time** before testing. An OS upgrade does not clear DSP RAM, and on rare
   occasions the first boot after flashing can play garbled audio until a cold
   reboot clears it (likely because a warm-up tag such as BusVerb `$2c0000` at
   `r7+$82` or BusDelay `$2e0000` survives across the soft reboot and skips
   initialization).

This method requires a unit that can boot normally; if yours does not, use
section 5b.

`tools/build/make_bin.py` generates the `.bin` container, and
`tools/build/bin_decode.py` validates Elektron's official file checksum and
round-trips generated images.

### 5b. Flash over MIDI

1. Connect your MIDI interface's MIDI OUT to the Octatrack's **MIDI IN** (5-pin
   DIN).
2. Power off the Octatrack, hold **FUNC**, and power on to enter the **STARTUP
   MENU**.
3. Press **TRIG 3** (MIDI UPGRADE) until the screen shows "READY TO RECEIVE MIDI
   UPGRADE".
4. Send `out/OCTATRACK_OS1.40C_OCTABAM1.syx` using a SysEx app or
   `make midi-flash PORT=<port> SYX=<file.syx>` (`tools/hw/midi_flash.py`),
   which paces the ~7,460 SysEx messages for DIN MIDI. Disable MIDI clock on
   that port and do not merge any other MIDI traffic into it (on a MIDI router,
   use a clean single-pipe route from your computer to the Octatrack). If the
   unit loses sync, re-enter the Startup Menu and send more slowly (`--ms 60`,
   or 100–300 ms between messages in a SysEx app).
5. Wait through PREPARING FLASH and UPDATING FLASH. Do not turn off the power or
   unplug the MIDI cable during either stage.
6. The unit may also update its bootstrap. Let it finish booting, then
   power-cycle it once more (section 5, step 5).

### 5c. Boot from the card without flashing (REMIX SWITCH)

If your Octatrack is already running an octabam image, BRAIN can boot another
image directly from the CF card without rewriting flash memory:

1. Copy the `.RMX` file into `/BRAIN/REMIXES/` on the CF card (create the
   directories if they do not exist).
2. On the unit, open **PROJ → BRAIN → REMIXES**, highlight the image, and press
   **YES** at `BOOT <NAME>?`. The selection persists across reboots; pick the
   entry under the FLASHED separator to return to your flashed firmware.

Run `make rmx REMIX=<name> BUILD=<nn>` to generate only the `.RMX` file
(optionally passing `RMX=<NAME>` up to 15 characters), or `make rmx-stock` to
create `STOCK 1.40C.RMX`, which boots stock OS without flashing. See
[REMIX SWITCH](../../modules/remix-switch/README.md) for details.

## 6. After the flash

1. **Check the version.** The boot screen and **SYSTEM STATUS → OS VERSION**
   should display `OCTABAM1`. If it still shows `1.40C`, the stock OS is still
   running.
2. **Stamp existing projects** if you flashed a remix that changes effect
   parameter layouts (such as the bus engines, or RIG HOSTS's T1/T5 FX2
   assignments):

   ```bash
   python3 tools/hw/ot_project.py stamp-defaults "<card>/<set>/<project>" <remix>
   ```

   A Part saved under an older layout passes outdated parameter bytes to the new
   effect; if a selector receives an out-of-range value, the sequencer can stall
   as soon as you press play. Re-selecting an effect on a single track is not
   enough because the sequencer evaluates every track in the Part. Projects
   created on the unit after flashing do not need stamping.
3. **Bus engine placement** (`octabam-bus`): the delay runs on tracks 1–4 and
   the reverb runs on tracks 5–8. Placing a bus host on the wrong half makes it
   fall back to SEND (`stamp-defaults` warns per Part). SEND's `DEL` and `REV`
   knobs control the send levels, and each engine's wet output plays on its host
   track.

If anything goes wrong on hardware, check
[FAILURE_MODES.md](../contributing/FAILURE_MODES.md) for known issues and
recovery steps.

## 7. If it goes wrong

The Octatrack's Startup Menu lives separately from the main OS. As long as it is
accessible, you can restore stock OS even if a modified image fails to boot
(including hangs or a "Z" screen):

1. Power off, hold **FUNC**, and power on to open the **STARTUP MENU**.
2. Press **TRIG 3** (MIDI UPGRADE) and wait for "READY TO RECEIVE MIDI UPGRADE".
3. Send `downloads/extracted/OCTATRACK_OS1.40C.syx` (downloaded earlier by
   `make os`) over DIN MIDI with a SysEx app or
   `make midi-flash PORT=<port> SYX=downloads/extracted/OCTATRACK_OS1.40C.syx`.
4. Wait through PREPARING FLASH and UPDATING FLASH without powering off.

`TRIG 2 → EMPTY RESET` clears battery-backed RAM and settings, leaving the CF
card untouched.

## 8. Back to stock, or another remix

- **Return to stock:** Flash `downloads/extracted/OCTATRACK_OS1.40C.syx` over
  MIDI (section 7), or copy Elektron's official `.bin` to the CF card root and
  upgrade as in section 5. Your CF card and projects are left untouched.
- **Switch to another remix:** Build and flash it the same way, then run
  `stamp-defaults` on existing projects if needed (section 6).

To build your own custom selection of modules, see
[COMPOSING.md](COMPOSING.md).
