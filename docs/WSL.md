# Getting started on WSL

The build is bash + Makefile + CMake and does not run on native Windows. It
runs unchanged inside WSL2. Verified on Ubuntu 26.04.1, 3 Sep 2026.

## Dependencies

A working **WSL2** Ubuntu shell ([install
guide](https://learn.microsoft.com/windows/wsl/install)) — WSL 2, not WSL 1.
Then, inside it:

```bash
sudo apt update
sudo apt install -y build-essential cmake git curl unzip xxd binutils \
                    binutils-m68k-linux-gnu \
                    python3 python3-numpy binwalk radare2 pulseaudio-utils
mkdir -p ~/.local/bin
ln -sf "$(command -v m68k-linux-gnu-objdump)" ~/.local/bin/m68k-elf-objdump
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

- **`binwalk` and `radare2` must go in before `make setup`.** The setup script
  installs them with Homebrew otherwise (`scripts/setup.sh:27`); with them
  already on PATH it skips that branch and never needs brew.
- **`binutils-m68k-linux-gnu` is not optional, and skipping brew is exactly why
  it is easy to miss.** `scripts/disasm.sh emac` shells out to
  `m68k-elf-objdump`, the only correct ColdFire decoder here. On the macOS
  route it arrives with `m68k-elf-gcc` from Homebrew (`scripts/setup.sh:31`),
  which this route never runs. Without it `scripts/disasm.sh emac` exits with
  "m68k-elf-objdump not found", and the only disassembler left is r2, **which
  silently invents code on this CPU**: 6,757 instructions below `0x40098000`
  that it cannot decode, 4,543 of them longer than two bytes, so the stream
  desynchronises. The Ubuntu package ships the same decoder under a different
  name, hence the symlink. Check it before trusting any disassembly:

  ```bash
  scripts/disasm.sh emac 0x40003664 8      # must print msacl, not "invalid"
  ```

  That span is the delay's EMAC loop, and `scripts/disasm.sh`'s own header
  states the expected output, so it is a real gate and not a smoke test.
- **`uv`** provisions `.venv` for the remixer. Without it `make remix` will not
  start and three checks in `make verify` silently `[SKIP]`.
- **`pulseaudio-utils`** is for audio — see *Changes needed*.

## Steps

Clone into the Linux filesystem, **not** `/mnt/c` — over the 9p bridge the
CMake build is slow, and a Windows-side clone loses the exec bit and can carry
CRLF endings that bash chokes on.

```bash
git clone https://github.com/sambanks/octabam.git ~/octabam
cd ~/octabam

make setup        # toolchain: assembler, emulator, firmware tool (~5 min)
make os           # your own copy of Elektron's OS 1.40C
make recon        # -> out/raw/section_3_MAIN_OS.bin
make bus          # -> out/mainos_bus.bin
make check        # the floor: build + cycle budget + verification
```

For the remixer:

```bash
make emu-setup    # uv sync --extra emu
make remix
```

Run `make remix` from **Windows Terminal** on the Ubuntu profile — it is a
Textual TUI and wants a real terminal.

Reach the tree from Windows at `\\wsl$\Ubuntu\home\<user>\octabam` — useful for
playing rendered wavs, and for copying a built image to a CF card, which is a
plain file copy from Explorer. VS Code: use the **WSL** extension.

## Changes needed

**One.** The remixer plays audio with `afplay`, which is macOS-only
(`tools/remix/app.py:2646`), so `r` renders but you hear nothing. WSLg already
runs a PulseAudio server wired to Windows audio; point `afplay` at it:

```bash
sudo tee /usr/local/bin/afplay >/dev/null <<'SH'
#!/bin/sh
exec paplay "$@"
SH
sudo chmod +x /usr/local/bin/afplay
```

`exec` matters: the remixer stops playback by killing that pid, and without it
you kill the wrapper while the sound plays on. No restart needed — `afplay` is
looked up at play time.

Nothing else in the repo needs changing.

---

Not covered here: flashing. `docs/FLASHING.md` is the guide, and none of it has
been done from a Windows host.
