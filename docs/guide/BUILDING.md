# Building a remix, step by step

From a fresh machine to a flashed unit, and back to stock. Every image is
built on your own computer from your own copy of Octatrack OS 1.40C.

**To install a released remix you do not need this guide.** The manual's
[Build and Install](https://sambanks.github.io/octabam/web-builder.html) page builds
Octabam, Octabam Verbs or Octabam Bus (the release in `tools/site/release.py`)
in the browser from your own 1.40C, with nothing uploaded, and has the same
install steps as sections 5 and 5b here; [Safety and
Recovery](https://sambanks.github.io/octabam/safety.html) is section 7's. This
guide is for building any remix from source: a test or community remix, your
own selection ([COMPOSING.md](COMPOSING.md)), a branch, or main ahead of the
release.

> **This is not official Elektron firmware.** Flashing a modified OS can
> leave the unit unusable until you recover it (section 7), and puts your warranty
> in question. Nothing here is endorsed by, supported by, or affiliated
> with Elektron. You flash at your own risk.
>
> **Do not share a built image.** A built `.bin` or `.syx` contains
> Elektron's OS.

Pick a remix from [the remix index](../../remixes/README.md). The commands below use `octabam`
([its README](../../remixes/octabam/README.md)); substitute any
remix name.

## 0. What you need

- A Mac with the Xcode Command Line Tools (`xcode-select --install`:
  `git`, `make`, a C compiler) and [Homebrew](https://brew.sh), or Linux /
  WSL2 (section 1a below).
- `python3` (3.10+; the build is stdlib only).
- `cmake` and [uv](https://docs.astral.sh/uv/): `make setup-mac` installs both; `make setup-linux` installs cmake, and uv has an install line in section 1a.
  uv provisions `.venv` (`make emu-setup`: `unicorn`, `textual`,
  `sounddevice`) for the label gates in `make check`.
- An Octatrack MKI or MKII on OS 1.40C. Elektron's MKI and MKII download
  pages serve the same OS file, and octabam images install on both.
- A CompactFlash card in the unit (the fast flashing path).
- For recovery and the MIDI flashing path: a 5-pin DIN MIDI interface into
  the Octatrack's MIDI IN and an app that sends `.syx` files (SysEx
  Librarian on macOS), or `make midi-flash`. The OT's own USB port does not
  take an OS upgrade.
- Stable power. Do not move the unit while it flashes.

## 1. Get the repository and the toolchain

```bash
git clone --recurse-submodules https://github.com/sambanks/octabam
cd octabam
make setup
make emu-setup
```

`--recurse-submodules` fetches the module authors' repositories
(`timhastie/octatrick-modules` under `modules/synth`, `modules/quantizer`,
`modules/direct-jump` and `modules/tuner`) at the pinned commits. If you cloned without
it: `git submodule update --init`.

`make setup-mac` (Homebrew: `binwalk`, `radare2`, `m68k-elf-gcc`, `cmake`,
`uv`) or `make setup-linux` (apt packages and `scripts/m68k-toolchain.sh`,
section 1a) installs the system tools and then runs `make setup`;
`make setup-windows` points at WSL2. `make setup` alone requires
`m68k-elf-gcc` on PATH, checks out three pinned vendored tools (`vendor/`), applies the
local patches and builds them. Re-running it is safe. It ends with
`setup complete`. `make emu-setup` runs `uv sync --extra emu` into
`.venv`.

### 1a. Linux and WSL2

The build uses Bash, Make, and CMake. It runs on macOS and Linux, including
WSL2; it does not run in native Windows. See [Microsoft's WSL install
guide](https://learn.microsoft.com/windows/wsl/install) to install WSL2.
The commands below are for Ubuntu, including Ubuntu under WSL2.

Clone into the Linux filesystem, not `/mnt/c`: over the 9p bridge the
CMake build is slow, and a Windows-side clone loses the exec bit and can
carry CRLF endings bash chokes on. Reach the tree from Windows at
`\\wsl$\Ubuntu\home\<user>\octabam` (to play rendered wavs, or to copy a
built image to the card from Explorer). VS Code: the **WSL** extension.

`make setup-linux` runs the apt install and the toolchain build below, then `make setup`. The steps by hand, before `make setup`:

```bash
sudo apt update
sudo apt install -y build-essential cmake git curl unzip xxd binutils \
                    binutils-m68k-linux-gnu \
                    python3 python3-numpy binwalk radare2 pulseaudio-utils
sudo ln -sf "$(command -v m68k-linux-gnu-objdump)" /usr/local/bin/m68k-elf-objdump
curl -LsSf https://astral.sh/uv/install.sh | sh     # for make emu-setup
source $HOME/.local/bin/env
```

- `binwalk` and `radare2` are optional: `scripts/setup.sh` reports them
  when missing and continues.
- `binutils-m68k-linux-gnu` provides the only correct ColdFire
  disassembler here under a different name, hence the symlink.
  `scripts/disasm.sh emac` shells out to `m68k-elf-objdump`; without it
  the only decoder left is radare2, which silently invents code on this
  CPU (`docs/contributing/TOOLING.md` section 3). Check it:
  `scripts/disasm.sh emac 0x40003664 8` must print `msacl`, not
  `invalid`. The symlink goes in `/usr/local/bin`: `~/.local/bin` is on
  PATH only in login shells, and `wsl.exe -d Ubuntu -- bash script.sh`
  from Windows is not one.

**The m68k cross-toolchain.** The build needs `m68k-elf-gcc`, `as`,
`ld`, `objcopy` and `nm`: every remix with linked ColdFire units (KITS,
MIDI SCENES, the USB modules, every DRAM module) refuses without them, and
`scripts/setup.sh` stops when `m68k-elf-gcc` is not on PATH.

**Build the bare-metal toolchain (recommended).** Module authors use
`m68k-elf-binutils` and `m68k-elf-gcc` built from GNU's sources with
binutils 2.47 and GCC 16.2.0. `scripts/m68k-toolchain.sh [PREFIX]` builds
both (source hashes pinned; default PREFIX `$HOME/.local/m68k-elf`) and
exits at once when PREFIX already has that gcc. Allow about an hour on two
compile jobs, and limit parallel jobs on a machine with under 4 GB of memory:

```bash
sudo apt install -y libgmp-dev libmpfr-dev libmpc-dev libisl-dev zlib1g-dev libzstd-dev pkgconf texinfo
scripts/m68k-toolchain.sh /opt/m68k-elf
export PATH=/opt/m68k-elf/bin:$PATH
```

`pkgconf` is needed: without `pkg-config`, binutils' configure stops on
`--with-zstd was given, but pkgconfig/libzstd.pc is not found`.

**Or Ubuntu's Linux-target tools**, which are quicker to install but do not
build every remix. They ship under another prefix:

```bash
sudo apt install -y gcc-m68k-linux-gnu      # GCC 15.2.0; binutils 2.46 comes with it
for t in as ld objcopy nm objdump gcc; do
  sudo ln -sf "$(command -v m68k-linux-gnu-$t)" /usr/local/bin/m68k-elf-$t
done
```

Their assembler encodes some branches differently, so USB's `usbmidi` unit
does not match its author's build and the build refuses it. Remixes these
tools cannot build report `[SKIP]` with the reason (`tools/remix/prereq.py`);
`make accept` fails on a skip. Use the bare-metal toolchain to build every
remix.

## 2. Get the stock OS

```bash
make os
make recon
```

`make os` downloads `OCTATRACK_OS1.40C_dist.zip` from Elektron's site into
`downloads/`, unpacks it, and checks the firmware's SHA256: `OCTATRACK_OS1.40C.bin`
`34695b606eb00e1b4dded5fd0c4b66f3a460522a632e47d7416dbd220599e1ad`,
`OCTATRACK_OS1.40C.syx`
`0a8d2d2b35c2cc78fa338576adc1af0cbc094cef973255103165c73edd87f2b6`. The zip's own
hash is printed but not checked, because the zip carries an `Elektron
EULA.txt` stamped at download time.
`make recon` unpacks it to `out/raw/section_3_MAIN_OS.bin`, the file every
build reads. Both directories are gitignored.

## 3. Build the image

```bash
make image REMIX=octabam BUILD=1
```

Output:

```
out/OCTATRACK_OCTABAM1.bin            the card image
out/OCTATRACK_OS1.40C_OCTABAM1.syx    the MIDI image
out/<REMIX> <BUILD>.RMX               REMIX SWITCH: boots from the card without flashing (section 5c)
```

`BUILD` is a one- or two-character tag of your choosing (digits; past
image 99 a letter then a digit: `A0` is 100, `A1`..`A9`, `B0` is 110,
since `Modulation` + three digits overfills the 12-character name
field). It becomes the
unit's OS version string (`OCTABAM1`) and the suffix on any octabam
effect's name, so a unit can always be traced to the build it runs. Bump
it every time you flash. `VERSION=<up to 10 chars>` overrides the version
string.

The build prints what it did: every module placed, every hook wired,
every identity checked against the author's own build, and the byte
count changed. It refuses, with the reason, rather than write an image it
cannot prove.

### Optional: run the gates

```bash
make emu-cf                 # builds the local ColdFire emulator (cmake) and boots stock in it once
make check REMIX=octabam          # build + every gate + boot under the emulator
```

`make check` is two halves: `make check-shared` (the gates that do not
depend on the remix: the ledger selftest, the stock-id audit that builds
every remix, the docs, the knob census, the module gates that build their
own image) and `make check-remix` (the selected remix's build, cycles and
its own gates). [docs/contributing/TESTING.md](../contributing/TESTING.md) says what
each step proves. Expect several minutes for the shared half and a few
minutes per remix. Without `make emu-setup`
(the `.venv`) the label gates (`verify_labels`, `verify_mode_names`,
`verify_hidden`) report `[SKIP]`; without `make emu-cf` the set gates do;
without a project in `OT_PROJECT` the set gates do too.

## 4. Back up

Flashing the OS does not touch the CF card. Back it up anyway (USB DISK
MODE, copy everything). Any remix carrying **KITS** writes `kits.work`
into each project it loads (the Parts become Kits); a stock OS ignores
that file and plays the Parts as saved.

## 5. Flash from the card

1. On the unit: **PROJECT → SYSTEM → USB DISK MODE → YES**. The card mounts
   on the computer.
2. Copy `out/OCTATRACK_OCTABAM1.bin` to the **root** of the card, not
   inside a folder.
3. Eject the card on the computer, then leave USB DISK MODE on the unit.
   Without the eject the copy can still be in the computer's cache and the
   unit reads a truncated file.
4. **PROJECT → SYSTEM → OS UPGRADE → YES** and confirm. The active project
   is synced to the card first.
5. Wait for the unit to finish and restart, then **power-cycle it once
   more before judging anything**. An OS upgrade does not clear DSP RAM:
   twice the first boot played garbled audio that a reboot cleared
   (inferred mechanism: an engine's warm-up tag, BusVerb `$2c0000` at
   `r7+$82` or BusDelay `$2e0000`, survives and the engine skips its
   warm-up).

This path needs a unit that boots; otherwise section 5b.

`tools/build/make_bin.py` builds the `.bin`; `tools/build/bin_decode.py`
decodes the official file, validates its checksum and round-trips ours.

### 5b. Flash over MIDI

1. Your interface's MIDI OUT → the Octatrack's **MIDI IN** (DIN).
2. On the Octatrack: power off, hold **FUNC**, power on → **STARTUP MENU**.
3. **TRIG 3** (MIDI UPGRADE) → "READY TO RECEIVE MIDI UPGRADE".
4. Send `out/OCTATRACK_OS1.40C_OCTABAM1.syx`: from a SysEx app, or
   `make midi-flash PORT=<port> SYX=<file.syx>` (`tools/hw/midi_flash.py`),
   which paces the ~7,460 messages at the DIN rate. Filter MIDI clock on
   that port, and merge nothing else into it (on a MIDI router, use a blank
   preset with one pipe from the computer to the Octatrack). If the unit loses sync, re-enter the Startup Menu and send
   again slower (`--ms 60`, or 100–300 ms between messages in a SysEx app).
5. Wait through PREPARING FLASH → UPDATING FLASH. Do not power off or
   disconnect during either.
6. The unit may update its bootstrap. Let it finish booting, then
   power-cycle (section 5 step 5).

### 5c. Boot from the card without flashing (REMIX SWITCH)

On a unit already running an octabam image, BRAIN can boot another image
from the card without writing the flash:

1. Copy the `.RMX` file into `/BRAIN/REMIXES/` on the card (create the
   folders if they are missing).
2. On the unit: **PROJ → BRAIN → REMIXES**, select its name, YES at
   `BOOT <NAME>?`. The choice is kept across reboots; the name under the
   FLASHED separator returns to the flashed image.

`make rmx REMIX=<name> BUILD=<nn>` writes only the `.RMX` (`RMX=<NAME>` names
it, 15 characters); `make rmx-stock` writes `STOCK 1.40C.RMX`, which switches
back to stock without a flash. [REMIX SWITCH](../../modules/remix-switch/README.md)
is the module.

## 6. After the flash

1. **The version.** The boot screen and **SYSTEM STATUS → OS VERSION** read
   `OCTABAM1`. If it still says `1.40C`, the stock OS is running.
2. **Stamp old projects** after flashing a remix that changes an effect's
   parameter layout (the bus engines, and RIG HOSTS' T1/T5 FX2 assignments):

   ```bash
   python3 tools/hw/ot_project.py stamp-defaults "<card>/<set>/<project>" <remix>
   ```

   A part saved under an older layout feeds the new one its old bytes; a
   select whose stored value is outside its count is used as an index and
   the sequencer stalls on the first play. Re-selecting the effect on one
   track is not enough: the sequencer runs every track of the part. A
   project made on the unit after the flash needs no stamp.
3. **The bus engines** (octabam-bus): the delay runs on tracks 1–4, the
   reverb on tracks 5–8; a host on the wrong half falls back to a SEND
   (`stamp-defaults` warns per part). SEND's `DEL` and `REV` knobs are the
   two sends; each engine's wet comes out on the track that hosts it.

If the unit misbehaves, [FAILURE_MODES.md](../contributing/FAILURE_MODES.md)
lists known faults and what to do about each.

## 7. If it goes wrong

The Startup Menu is stored separately from the operating system. If it is
available, it can install stock OS when the modified OS will not boot
(including a "Z" screen or a hang):

1. Power off. Hold **FUNC** and power on → **STARTUP MENU**.
2. **TRIG 3 → MIDI UPGRADE** → "READY TO RECEIVE MIDI UPGRADE".
3. Send `downloads/extracted/OCTATRACK_OS1.40C.syx` (the stock OS, from
   `make os`) over DIN MIDI, from a SysEx app or
   `make midi-flash PORT=<port> SYX=downloads/extracted/OCTATRACK_OS1.40C.syx`.
4. Wait through PREPARING FLASH → UPDATING FLASH. Do not power off.

`TRIG 2 → EMPTY RESET` clears battery-backed RAM and settings, not the
card.

## 8. Back to stock, or another remix

- **Stock:** flash `downloads/extracted/OCTATRACK_OS1.40C.syx` over MIDI
  (section 7), or copy the official `.bin` from Elektron's zip to the card and
  flash it as in section 5. The card and projects are not touched.
- **Another remix:** build and flash it the same way, then stamp projects
  as in section 6.

Composing your own remix: [COMPOSING.md](COMPOSING.md).
