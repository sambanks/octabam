# Building a remix, step by step

From a fresh machine to a flashed unit, and back to stock. Every image is
built on your own computer from your own copy of Octatrack OS 1.40C.

> **This is not official Elektron firmware.** Flashing a modified OS can
> leave the unit unusable until you recover it (section 7), and puts your warranty
> in question. Nothing here is endorsed by, supported by, or affiliated
> with Elektron. You flash at your own risk.
>
> **Do not share a built image.** A built `.bin` or `.syx` contains
> Elektron's OS.

Pick a remix from [the remix index](../../remixes/README.md). The commands below use `ok-ms`
(Octakit + MIDI SCENES on the stock effects, the smallest remix that has
run on a unit); substitute any remix name.

## 0. What you need

- A Mac with the Xcode Command Line Tools (`xcode-select --install`:
  `git`, `make`, a C compiler) and [Homebrew](https://brew.sh), or Linux /
  WSL2 (section 1a below).
- `python3` (3.10+; the build is stdlib only).
- `cmake` and [uv](https://docs.astral.sh/uv/): `brew install cmake uv`.
  uv provisions `.venv` (`make emu-setup`: `unicorn`, `textual`,
  `sounddevice`) for `make remix` and the label gates in `make check`.
- An Octatrack MKI or MKII on OS 1.40C. Elektron's MKI and MKII download
  pages serve the byte-identical file (compared 19 Aug 2026). octabam's own
  effects have only been tested on an MKII; the DRAM platform has run on
  both (MKI: octalab, 11 Sep 2026; MKII: OKMS1, 14 Sep 2026). octabam
  images keep 1.40C's internal version code 0178, which the updater's
  "MK1 not allowed" check (error −5, against "0156") accepts.
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
(`modules/octakit/upstream`, `modules/midi-scenes/upstream`, and
`timhastie/octatrick-modules` under `modules/synth`, `modules/quantizer`,
`modules/direct-jump` and `modules/tuner`) at the pinned commits. If you cloned without
it: `git submodule update --init`.

`make setup` installs `binwalk`, `radare2` and `m68k-elf-gcc` with
Homebrew, checks out three pinned vendored tools (`vendor/`), applies the
local patches and builds them. Re-running it is safe. It ends with
`setup complete`. `make emu-setup` runs `uv sync --extra emu` into
`.venv`.

### 1a. Linux and WSL2

The build is bash + Makefile + CMake and does not run on native Windows;
it runs inside WSL2 (WSL 2, not WSL 1: [Microsoft's install
guide](https://learn.microsoft.com/windows/wsl/install)). What is written
here was verified on Ubuntu 26.04.1 under WSL2 on 3 Sep 2026 and re-read
against the tree of 28 Sep 2026; the last paragraph says what has not been
verified since.

Clone into the Linux filesystem, not `/mnt/c`: over the 9p bridge the
CMake build is slow, and a Windows-side clone loses the exec bit and can
carry CRLF endings bash chokes on. Reach the tree from Windows at
`\\wsl$\Ubuntu\home\<user>\octabam` (to play rendered wavs, or to copy a
built image to the card from Explorer). VS Code: the **WSL** extension.

Inside the shell, before `make setup`:

```bash
sudo apt update
sudo apt install -y build-essential cmake git curl unzip xxd binutils \
                    binutils-m68k-linux-gnu \
                    python3 python3-numpy binwalk radare2 pulseaudio-utils
sudo ln -sf "$(command -v m68k-linux-gnu-objdump)" /usr/local/bin/m68k-elf-objdump
curl -LsSf https://astral.sh/uv/install.sh | sh     # for make emu-setup / make remix
source $HOME/.local/bin/env
```

- `binwalk` and `radare2` go in first: `scripts/setup.sh` installs them
  with Homebrew when they are missing, and with them on PATH it skips
  that branch.
- `binutils-m68k-linux-gnu` provides the only correct ColdFire
  disassembler here under a different name, hence the symlink.
  `scripts/disasm.sh emac` shells out to `m68k-elf-objdump`; without it
  the only decoder left is radare2, which silently invents code on this
  CPU (`docs/contributing/TOOLING.md` section 3). Check it:
  `scripts/disasm.sh emac 0x40003664 8` must print `msacl`, not
  `invalid`. The symlink goes in `/usr/local/bin`: `~/.local/bin` is on
  PATH only in login shells, and `wsl.exe -d Ubuntu -- bash script.sh`
  from Windows is not one (observed 10 Sep 2026).
- `make remix` wants a real terminal: run it from Windows Terminal on the
  Ubuntu profile. Its playback is `afplay` (macOS only); `docs/guide/REMIXER.md`
  has the two-line wrapper that points it at WSLg's PulseAudio.

**The m68k cross-toolchain.** The build needs `m68k-elf-gcc`, `as`,
`ld`, `objcopy` and `nm`: every remix with linked ColdFire units (Octakit,
MIDI SCENES, the USB modules, every DRAM module) refuses without them, and
`scripts/setup.sh` adds `m68k-elf-gcc` to its Homebrew list when it's
missing, so on a machine without Homebrew `make setup` stops at `brew:
command not found`.

**Build the bare-metal toolchain (recommended).** Upstream's authors use
Homebrew's `m68k-elf-binutils` and `m68k-elf-gcc`. The same toolchain
builds from GNU's sources on Linux, with the formulae's configure flags:
binutils 2.47 (Homebrew's current) and GCC 16.1.0 (the version Octakit's
recipe pins; Homebrew is on 16.2.0). Measured on Ubuntu 26.04 under WSL2,
28 Sep 2026; about an hour with two compile jobs:

```bash
sudo apt install -y libgmp-dev libmpfr-dev libmpc-dev libisl-dev zlib1g-dev libzstd-dev pkgconf texinfo
# binutils-2.47.tar.xz and gcc-16.1.0.tar.xz from https://ftp.gnu.org/gnu/, each checked:
#   gpgv --keyring ./gnu-keyring.gpg <file>.sig <file>
mkdir build-binutils && cd build-binutils
../binutils-2.47/configure --target=m68k-elf --prefix=/opt/m68k-elf --with-system-zlib --with-zstd --disable-nls
make -j2 && sudo make install && cd ..
export PATH=/opt/m68k-elf/bin:$PATH
mkdir build-gcc && cd build-gcc
../gcc-16.1.0/configure --target=m68k-elf --prefix=/opt/m68k-elf --disable-nls --without-headers \
  --with-as=/opt/m68k-elf/bin/m68k-elf-as --with-ld=/opt/m68k-elf/bin/m68k-elf-ld \
  --enable-languages=c --with-system-zlib --with-zstd
make -j2 all-gcc && sudo make install-gcc
make -j2 all-target-libgcc && sudo make install-target-libgcc
for f in /opt/m68k-elf/bin/m68k-elf-*; do sudo ln -sf "$f" /usr/local/bin/; done
```

- `pkgconf` is needed: without `pkg-config`, binutils' configure stops on
  `--with-zstd was given, but pkgconfig/libzstd.pc is not found`.
- ✅ Octakit's runtime rebuilds to its author's bytes: "rebuilt runtime,
  packed runtime and append all match the recipe" (`make bus REMIX=ok-ms`).
- ✅ USB MIDI's linked unit matches its author's build at `0x400d24f0`,
  1,124 bytes (`make bus REMIX=octatrick-usb`).
- ✅ This repository's pinned ColdFire bytes still match
  (`tools/build/label_fmt.py`), and `scripts/disasm.sh emac 0x40003664 8`
  still prints `msacl`.
- ✅ A module that isn't checked against an author's bytes can change: the
  bare-metal assembler reads a same-section global PC-relative, where
  Ubuntu's keeps an absolute address. STEM REC's runtime came out 48 bytes
  shorter, and its gates pass on both (`docs/firmware/STEM_REC.md` 15.5).
- On a VM with 3.8 GB, never compile beside a port run: on 28 Sep 2026 an
  8-job port build there set off the kernel's OOM killer, which killed the
  verifier.

**The older route: Ubuntu's Linux-target tools.** Ubuntu's packages ship
the tools under another prefix. This route was run with them, measured on
Ubuntu 26.04 under WSL2 (10 and 27 Sep 2026, on branch `stem-rec-v2`):

```bash
sudo apt install -y gcc-m68k-linux-gnu      # GCC 15.2.0; binutils 2.46 comes with it
for t in as ld objcopy nm objdump gcc; do
  sudo ln -sf "$(command -v m68k-linux-gnu-$t)" /usr/local/bin/m68k-elf-$t
done
```

- ✅ With these on PATH, `make setup` runs without Homebrew: binwalk,
  radare2 and `m68k-elf-gcc` are all present, so step 1 has nothing to
  install.
- ✅ They produce this repository's own pinned ColdFire bytes:
  `tools/build/label_fmt.py` re-assembles its twelve caves and matches,
  `tools/build/mode_names.py` passes, and the DRAM loader they build boots
  under the port (`verify_dram_boot`: it ran once and never reached
  `fatal`).
- ❌ They can't build Octakit's runtime. Its `firmware.json` pins
  `m68k-elf-gcc` 16.1.0, and binutils 2.46 refuses `runtime.S:438`
  (`bne.s` to a `.global` label more than 127 bytes into the section: it
  emits an `R_68K_PC8` relocation that overflows). The same loop with a
  local label assembles at any offset.
- ❌ USB MIDI's linked unit links to 1,130 bytes that aren't its author's
  (sha256 `b49af01e…`, not `6291d91e…`), so the build refuses it.
- ✅ Both refusals are the toolchain: the bare-metal toolchain above
  builds both to their authors' bytes from the same trees (28 Sep 2026).
  This line was inferred until then.

With these tools `make check` passes, and the every-remix sweeps skip the
remixes the machine can't build, by name, with the reason
(`tools/remix/prereq.py`). `make accept` doesn't pass with them: it
refuses any `[SKIP]`, so its `check_shared` stage fails for every remix.
Use the bare-metal toolchain instead. ❌ Retracted: this paragraph said
until 28 Sep 2026 that the symlinked tools had "not been tried" and that
`make check` on Linux was unverified.

Flashing from a Windows host hasn't been done: the card copy is a plain
file copy, and the MIDI path needs a SysEx app on the host.

## 2. Get the stock OS

```bash
make os
make recon
```

`make os` downloads `OCTATRACK_OS1.40C_dist.zip` from Elektron's site into
`downloads/` and prints its SHA256 (expected
`370c55a3dad3996b8e4b46400a205066fdaf185ad4d0255a3a3f835060573ff0`).
`make recon` unpacks it to `out/raw/section_3_MAIN_OS.bin`, the file every
build reads. Both directories are gitignored.

## 3. Build the image

```bash
make image REMIX=ok-ms BUILD=1
```

Output:

```
out/OCTATRACK_OCTABAM1.bin            the card image
out/OCTATRACK_OS1.40C_OCTABAM1.syx    the MIDI image
```

`BUILD` is a one- or two-digit number of your choosing. It becomes the
unit's OS version string (`OCTABAM1`) and the suffix on any octabam
effect's name, so a unit can always be traced to the build it runs. Bump
it every time you flash. `VERSION=<up to 10 chars>` overrides the version
string (`OKMS1` was built that way).

The build prints what it did: every module placed, every hook wired,
every identity checked against the author's own build, and the byte
count changed. It refuses, with the reason, rather than write an image it
cannot prove.

### Optional: run the gates

```bash
make emu-cf                 # builds the local ColdFire emulator (cmake) and boots stock in it once
make check REMIX=ok-ms      # build + every gate + boot under the emulator
```

`make check` is two halves: `make check-shared` (the gates that do not
depend on the remix: the ledger selftest, the stock-id audit that builds
every remix, the docs, the knob census, the module gates that build their
own image) and `make check-remix` (the selected remix's build, cycles and
its own gates). [docs/contributing/TESTING.md](../contributing/TESTING.md) says what
each step proves. Measured on one machine, 27 Sep 2026, over the 25
remixes of the day: 475 s for the shared half, 223 s per remix on average
(`lofi-amf-fix` 51 s, `bottleservice` 1,143 s). Without `make emu-setup`
(the `.venv`) the label gates (`verify_labels`, `verify_modenames`,
`verify_hidden`) report `[SKIP]`; without `make emu-cf` the set gates do;
without a project in `OT_PROJECT` the set gates do too.

## 4. Back up

Flashing the OS does not touch the CF card. Back it up anyway (USB DISK
MODE, copy everything). Any remix carrying **Octakit** migrates Parts into
Kits on project load; going back to stock can lose Kit data (Em's
warning).

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
   that port. If the unit loses sync, re-enter the Startup Menu and send
   again slower (`--ms 60`, or 100–300 ms between messages in a SysEx app).
5. Wait through PREPARING FLASH → UPDATING FLASH. Do not power off or
   disconnect during either.
6. The unit may update its bootstrap. Let it finish booting, then
   power-cycle (section 5 step 5).

## 6. After the flash

1. **The version.** The boot screen and **SYSTEM STATUS → OS VERSION** read
   `OCTABAM1`. If it still says `1.40C`, the stock OS is running.
2. **Stamp old projects** after flashing a remix that changes an effect's
   parameter layout (the bus engines, the rig's hosts):

   ```bash
   python3 tools/hw/ot_project.py stamp-defaults "<card>/<set>/<project>" <remix>
   ```

   A part saved under an older layout feeds the new one its old bytes; a
   select whose stored value is outside its count is used as an index and
   the sequencer stalls on the first play. Re-selecting the effect on one
   track is not enough: the sequencer runs every track of the part. A
   project made on the unit after the flash needs no stamp.
3. **The bus engines** (bottleservice): the delay runs on tracks 1–4, the
   reverb on tracks 5–8; a host on the wrong half falls back to a SEND
   (`stamp-defaults` warns per part). SEND's `DEL` and `REV` knobs are the
   two sends; each engine's wet comes out on the track that hosts it.

If the unit misbehaves, [FAILURE_MODES.md](../contributing/FAILURE_MODES.md)
is the register of what has gone wrong on a unit and why.

## 7. If it goes wrong

The Startup Menu is the bootloader and lives in flash the OS upgrade never
touches, so the unit can always be returned to stock, even with a corrupt
OS ("Z" screen, no boot, a hang):

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

Composing your own remix: [REMIXER.md](REMIXER.md).
