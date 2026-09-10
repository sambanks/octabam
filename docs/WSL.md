# Getting started on WSL

The build is bash + Makefile + CMake and does not run on native Windows. It
runs inside WSL2. The steps below were verified on Ubuntu 26.04.1 on
3 Sep 2026; the *Limits* section says what has changed since.

## Dependencies

A working **WSL2** Ubuntu shell ([install
guide](https://learn.microsoft.com/windows/wsl/install)). WSL 2, not WSL 1.
Then, inside it:

```bash
sudo apt update
sudo apt install -y build-essential cmake git curl unzip xxd binutils \
                    binutils-m68k-linux-gnu \
                    python3 python3-numpy binwalk radare2 pulseaudio-utils
sudo ln -sf "$(command -v m68k-linux-gnu-objdump)" /usr/local/bin/m68k-elf-objdump
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

- **`binwalk` and `radare2` must go in before `make setup`.** The setup script
  installs them with Homebrew otherwise (`scripts/setup.sh:27`); with them
  already on PATH it skips that branch.
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
- **The symlink goes in `/usr/local/bin`, not `~/.local/bin`.** `~/.local/bin`
  is on PATH only in login shells. A script run as
  `wsl.exe -d Ubuntu -- bash script.sh` from Windows is not a login shell,
  does not see it, and hits the gate above even though the interactive shell
  passed it (observed 10 Sep 2026).
- **`uv`** provisions `.venv` for the remixer. Without it `make remix` will not
  start and three checks in `make verify` silently `[SKIP]`.
- **`pulseaudio-utils`** is for audio. See *Changes needed*.

## Steps

Clone into the Linux filesystem, **not** `/mnt/c`. Over the 9p bridge the
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

Run `make remix` from **Windows Terminal** on the Ubuntu profile. It is a
Textual TUI and wants a real terminal.

Reach the tree from Windows at `\\wsl$\Ubuntu\home\<user>\octabam`. That is
useful for playing rendered wavs, and for copying a built image to a CF card,
which is a plain file copy from Explorer. VS Code: use the **WSL** extension.

## Limits

The steps above were verified against the tree of 3 Sep 2026. Since
9 Sep 2026 the build treats the m68k cross-toolchain as a first-class
dependency. `scripts/setup.sh:31` adds `m68k-elf-gcc` to the Homebrew list
when it is missing, so on a machine without Homebrew `make setup` stops at
`brew install` with `brew: command not found`. Every remix with linked
ColdFire units (octakit, midi-scenes, hello-dram, scenes-kits) needs
`m68k-elf-as`, `ld`, `objcopy` and `nm`, and `tools/build/build_bus.py:1494`
refuses without them.

❌ **Retracted (10 Sep 2026).** The old claim here was that "whether
symlinking them as `m68k-elf-*` satisfies the build, and whether an `.s`
re-assembled that way still matches its author's bytes, has not been tried",
and that the route was proven for disassembly only. It has now been tried.
The answer is split: the apt tools satisfy this repository's own ColdFire
code, and they do not satisfy Octakit's.

### What was installed (10 Sep 2026, Ubuntu 26.04 under WSL2)

```bash
sudo apt install -y binutils-m68k-linux-gnu gcc-m68k-linux-gnu
for t in as ld objcopy nm objdump gcc; do
  sudo ln -sf "$(command -v m68k-linux-gnu-$t)" /usr/local/bin/m68k-elf-$t
done
```

That gives GNU binutils 2.46 and GCC 15.2.0. The links go in `/usr/local/bin`
because `~/.local/bin` is not on the PATH of a non-login shell, and the build
runs the tools through `subprocess`, which uses that PATH.

`scripts/setup.sh` was run by hand, minus Homebrew. Step 1 (binwalk, radare2,
`m68k-elf-gcc`) was skipped: binwalk and radare2 are still absent, and nothing
below needed them. Step 3 (Ghidra) is optional and was skipped. Steps 1b
(mc68k), 2 (elektron-firmware-tool) and 4 (dsp56300) were run as written.
`uv sync --extra emu` provisioned `.venv`, and `make emu-cf` built the
ColdFire port and reached the M6a gate.

Two provisioning traps, both measured:

- ✅ **`git clone --depth 1` of dsp56300 gets today's upstream tip, and
  `tools/patches/dsp56300.patch` does not apply to it.** The patch's base is
  `f5bf5cbf`. On the tip, `git apply` fails on `dsp.h` and `CMakeLists.txt`,
  `setup.sh` prints its "already applied (or upstream changed)" line, and the
  build then fails with `class dsp56k::Memory has no member named
  setSharedWindow`. Fix: `git -C vendor/dsp56300 fetch --unshallow origin`,
  then `git checkout --detach f5bf5cbf`, then submodules, then the patch.
- ✅ **The `upstream/` trees under `modules/` are git submodules and are not
  cloned by `setup.sh`.** Run `git submodule update --init --recursive`.
  `modules/octakit/upstream` (emuyia/ems-octakit) is public.
  `modules/midi-scenes/upstream` (sambanks/midisc) returns 404 to an
  authenticated `gh api`, so it cannot be fetched from this account. Over
  HTTPS with no credential helper, that clone hangs on a username prompt
  instead of failing. Set `GIT_TERMINAL_PROMPT=0` to get the error.

### What the oracles said

`make check` runs `tools/remix/selftest.py`, which builds every remix. Thirteen
remixes need one of the two upstream submodules, so no `make check` passes on
this machine yet, whatever `REMIX` is set to.

| Run | Exit | Why |
| --- | --- | --- |
| `make check REMIX=hello-dram` | 2 | Its own build and cycle count pass. The selftest then fails on 13 other remixes. |
| `make check REMIX=octakit` | 2 | Build fails: `m68k-elf-as` cannot assemble Octakit's `runtime.S`. |
| `make check REMIX=midi-scenes` | 2 | Build fails: the upstream submodule is not available to this account. |

✅ **The apt binutils produce this repository's pinned ColdFire bytes.** Run
individually, against a `hello-dram` build:

- `tools/build/label_fmt.py` passes. It re-assembles twelve caves with
  `m68k-elf-as -mcpu=5407` and compares them against the bytes `emit()`
  claims. This is the drift gate, and it is green.
- `tools/build/mode_names.py` passes.
- `tools/verify/verify_dram_boot.py` passes. The loader that these tools built
  boots to the handoff under the ColdFire port, ran once, and never reached
  its `fatal` hang. The DRAM reserve matches the linked runtime.
- `tools/verify/verify_slots.py`, `verify_grains.py`, `verify_menu.py` and
  `verify_labels.py` pass.
- `tools/verify/verify_replaces.py` fails, but only on the same 13 remixes.

❌ **The apt tools cannot build Octakit's runtime.** Two separate reasons:

1. ✅ `modules/octakit/upstream/runtime/firmware.json` pins
   `m68k-elf-gcc` version 16.1.0, and `tools/remix/runtime_build.py:371`
   compares the rebuilt runtime against the author's bytes. Ubuntu ships
   15.2.0. A different compiler version is a different code generator.
2. ✅ Binutils 2.46 refuses `runtime.S:438`, with `value of fffffbbe too
   large for field of 1 byte at 00000441`. The line is `bne.s
   gk_copy_payload_long_loop`, a branch six bytes backwards. The assembler
   never resolves an 8-bit branch to a `.global` label. It emits an
   `R_68K_PC8` relocation and writes the negated section offset into the
   displacement byte, which overflows once the label sits more than 127 bytes
   into the section. Minimal case, measured: the same loop assembles at
   offset 0 and fails after `.space 0x400`, and the identical loop with a
   local label assembles at any offset.

   🟡 Inferred: the author's `m68k-elf-as` resolves this branch locally, which
   is why Octakit builds for her. Falsifier: assemble `runtime.S` with a
   Homebrew `m68k-elf-as` of the pinned toolchain. If it fails there too, the
   source is at fault and Octakit's own build would be failing.

### Where this leaves the route

✅ Proven: disassembly (`scripts/disasm.sh emac`), `make emu-cf`, the DSP side
of the build (`scripts/refhash.sh save` saved all 26 configurations), and this
repository's own ColdFire code, including the DRAM loader, which boots under
the port.

❌ Not available: `make check`, until the two upstream submodules are
resolvable. Octakit needs `m68k-elf-gcc` 16.1.0 and an assembler that resolves
8-bit branches to global labels. Homebrew on Linux, or a cross-toolchain built
from source, are the untried options. midi-scenes needs read access to
`sambanks/midisc`.

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
you kill the wrapper while the sound plays on. No restart needed, because
`afplay` is looked up at play time.

Beyond the toolchain gap in *Limits*, nothing else in the repo needs changing.

---

Not covered here: flashing. `docs/remixer/FLASHING.md` is the guide, and none
of it has been done from a Windows host.
