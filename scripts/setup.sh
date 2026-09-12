#!/usr/bin/env bash
# Install the toolchain this repo builds against. Idempotent -- safe to re-run.
#
# The thing that actually matters here is step 4: the DSP56300 assembler
# (dsp_asm) and emulator harness (dsp_host). Those are what let effects be
# assembled and auditioned locally instead of by flashing hardware.
set -euo pipefail

# Copy our sources into the vendor tree. Always overwrite: tools/harness/dsp_host/ is
# the source of truth. Two diverging copies means an edit that never reaches
# the binary, which produces confidently wrong measurements.
stage_dsp_host() {
  mkdir -p vendor/dsp56300/source/dsp_host
  cp tools/harness/dsp_host/dsp_asm.cpp tools/harness/dsp_host/dsp_host.cpp \
     tools/harness/dsp_host/CMakeLists.txt vendor/dsp56300/source/dsp_host/ 2>/dev/null || true
  grep -q dsp_host vendor/dsp56300/source/CMakeLists.txt 2>/dev/null \
    || echo 'add_subdirectory(dsp_host)' >> vendor/dsp56300/source/CMakeLists.txt
}
cd "$(dirname "$0")/.."

echo "== 1) System tools (via Homebrew) =="
need_brew=()
command -v binwalk  >/dev/null 2>&1 || need_brew+=(binwalk)
command -v radare2  >/dev/null 2>&1 || need_brew+=(radare2)
# The m68k/ColdFire cross-toolchain (bottled, minutes to install). Since
# 9 Sep 2026 a first-class dependency: loader-appended runtimes
# (schema.Runtime -- modules/octakit) are COMPILED from source at build
# time, and every pinned ColdFire cave with a `.s` source is re-assembled
# and compared against its bytes when this is present. The build refuses
# with a clear message, not a traceback, when it is missing.
command -v m68k-elf-gcc >/dev/null 2>&1 || need_brew+=(m68k-elf-gcc)
if [ "${#need_brew[@]}" -gt 0 ]; then
  echo "   installing: ${need_brew[*]}"
  brew install "${need_brew[@]}"
else
  echo "   binwalk and radare2 already present."
fi

echo
echo "== 1b) mc68k (ColdFire core for the headless machine) =="
# Musashi plus ColdFire mode, an HI08 host-port register file and the on-chip
# peripheral scaffolding -- the CPU half of tools/emu/ot_emu. Vendored, GPLv3, the
# same posture as vendor/dsp56300: tooling and patches are shared, built
# binaries never are. `docs/firmware/COLDFIRE_PORT.md`.
# PINNED, like the two below: a `git pull` on every setup moves a
# contributor's tree to whatever upstream is that day, and the port was
# measured against this commit (docs/firmware/COLDFIRE_PORT.md).
MC68K_PIN=4a6d0d17a1f2b30077ab726c27fe9bb770fa0456
pin_checkout() {  # dir url sha
  [ -d "$1" ] || git clone --no-checkout "$2" "$1"
  if [ "$(git -C "$1" rev-parse HEAD 2>/dev/null)" != "$3" ]; then
    git -C "$1" fetch -q origin "$3"
    git -C "$1" checkout -q "$3"
  fi
  echo "   $1 at $(git -C "$1" rev-parse --short HEAD) (pinned)"
}
# apply_patch dir patch: apply, or accept already-applied, or FAIL LOUDLY.
# The old "already applied (or upstream changed)" line covered both a
# patched tree and a tree the patch REJECTED on, and a contributor's fresh
# clone hit the second twice on 12 Sep 2026 (dsp_host would not compile;
# make image found no container) before the message said which.
apply_patch() {
  if git -C "$1" apply --check "$2" 2>/dev/null; then
    git -C "$1" apply "$2" && echo "   local patch applied: $(basename "$2")"
  elif git -C "$1" apply --check --reverse "$2" 2>/dev/null; then
    echo "   local patch already applied: $(basename "$2")"
  else
    echo "   [!] $(basename "$2") does NOT apply to $1 at $(git -C "$1" rev-parse --short HEAD)"
    echo "       and is not already applied either. Fix: rm -rf $1; make setup"
    exit 1
  fi
}
pin_checkout vendor/mc68k https://github.com/joelanders/mc68k-md-mm "$MC68K_PIN"

echo
echo "== 2) elektron-firmware-tool (mischa85) =="
EFT_PIN=065d18f4195793e61891e387813488ee59f6d1ca
pin_checkout vendor/elektron-firmware-tool https://github.com/mischa85/elektron-firmware-tool "$EFT_PIN"

# Two local changes are needed to reproduce this build:
#   - set_version() writes the full 10-char ELEK version field from 0x08;
#     upstream only writes from 0x0D, where 5 fit.
#   - EFT_EMIT_CONTAINER dumps the rebuilt container, which tools/build/make_bin.py
#     wraps to produce the CF card .bin.
apply_patch vendor/elektron-firmware-tool "$(pwd)/tools/patches/elektron-firmware-tool.patch"

echo "   building ..."
if [ -f vendor/elektron-firmware-tool/Makefile ]; then
  make -C vendor/elektron-firmware-tool || { echo "   [!] elektron-firmware-tool build FAILED -- make image needs it"; exit 1; }
  # The binary must carry OUR container dump, or make image has nothing to
  # wrap; a build from an unpatched tree is silent about it until then.
  grep -q EFT_EMIT_CONTAINER vendor/elektron-firmware-tool/elektron-firmware-tool \
    || { echo "   [!] elektron-firmware-tool was built WITHOUT the local patch (no EFT_EMIT_CONTAINER)."; \
         echo "       Fix: rm -rf vendor/elektron-firmware-tool; make setup"; exit 1; }
else
  src=$(find vendor/elektron-firmware-tool -maxdepth 2 -name '*.c' | tr '\n' ' ')
  if [ -n "$src" ]; then
    echo "   no Makefile; compiling sources: $src"
    cc -O2 -o vendor/elektron-firmware-tool/elektron-firmware-tool $src || \
      echo "   [!] direct compile failed — inspect the repo manually"
  else
    echo "   [!] no C sources or Makefile found — check the repo"
  fi
fi

echo
echo "== 3) Ghidra (optional, manual) =="
if [ ! -d "/Applications/ghidra" ] && ! command -v ghidra >/dev/null 2>&1; then
  cat <<'EOF'
   Ghidra not detected. For ColdFire disassembly:
     brew install --cask ghidra      # needs JDK 17+ (brew install temurin)
   Ghidra has no perfect native ColdFire processor; the m68k module covers
   most of the ISA. Alternative: radare2/rizin with -a m68k.
   Only needed for OS archaeology, not for building effects.
EOF
fi

echo
echo "== 4) dsp56300 -- assembler, disassembler and emulator for the audio DSP =="
# The effects and timestretch run on a DSP56300, not the ColdFire. Neither
# Ghidra nor radare2 targets it; we use the Access Virus emulator's toolchain.
# See docs/firmware/DSP.md and tools/build/dsp_modmap.py.
DIS=vendor/dsp56300/build/source/disassemble/dsp56kDisassemble
ASM=vendor/dsp56300/build/source/dsp_host/dsp_asm
HOST=vendor/dsp56300/build/source/dsp_host/dsp_host
# All three, not just the disassembler: a build that got the disassembler
# and then failed on dsp_host used to read as "already built" on every
# re-run, and the failure only surfaced later as a traceback in make check
# (12 Sep 2026, a contributor's fresh clone).
if [ ! -x "$DIS" ] || [ ! -x "$ASM" ] || [ ! -x "$HOST" ]; then
  if ! command -v cmake >/dev/null 2>&1; then
    echo "   [!] cmake not found — brew install cmake — then re-run make setup (make check needs dsp_asm and dsp_host)"
    exit 1
  else
    # PINNED. The patch below is against this commit; upstream moved 105
    # commits past it by 12 Sep 2026 and the patch no longer applies there
    # (dsp.h, dsp_ops_alu.inl, jitops.h reject). A contributor's fresh
    # clone took that day's HEAD, the "already applied (or upstream
    # changed)" line below hid which, and dsp_host.cpp failed to compile
    # against an unpatched emulator (no setSharedWindow). Moving the pin
    # means re-basing the patch and re-running make check's bit-identity
    # gates -- dsp_host renders every effect on this emulator.
    DSP56300_PIN=c051afad31612c2d2c7a81a7ab23e1c5ac9e61af
    if [ ! -d vendor/dsp56300 ]; then
      git clone --no-checkout https://github.com/dsp56300/dsp56300.git vendor/dsp56300
    fi
    if [ "$(git -C vendor/dsp56300 rev-parse HEAD 2>/dev/null)" != "$DSP56300_PIN" ]; then
      git -C vendor/dsp56300 fetch -q origin "$DSP56300_PIN"
      git -C vendor/dsp56300 checkout -q "$DSP56300_PIN"
    fi
    git -C vendor/dsp56300 submodule update --init --depth 1 --recursive
    # The patch carries: MPYRI (unimplemented upstream in interpreter and
    # JIT; stock LO-FI uses it, 2 Sep 2026); the shared window, two-way for
    # dsp_host (X with X, Y with Y) and three-way for the ColdFire port's DSP
    # pair (P, X and Y one memory, as the chip has it); and the host-stepped
    # mode the port drives the cores in (DO loops stepped, interrupts
    # interpreted, peripherals serviced under a masked interrupt, an idle
    # step) plus hooks for Y-side registers it does not map (8 Sep 2026, O8).
    EMUPATCH=$(pwd)/tools/patches/dsp56300.patch
    apply_patch vendor/dsp56300 "$EMUPATCH"
    stage_dsp_host
    cmake -S vendor/dsp56300 -B vendor/dsp56300/build -DCMAKE_BUILD_TYPE=Release \
      && cmake --build vendor/dsp56300/build \
           --target dsp56kDisassemble dsp_asm dsp_host -j8 \
      || { echo "   [!] dsp56300 build FAILED -- make check cannot run without dsp_asm and dsp_host."; \
           echo "       Fix what cmake printed above, then: rm -rf vendor/dsp56300/build; make setup"; exit 1; }
  fi
else
  echo "   already built: $DIS, $ASM, $HOST"
  stage_dsp_host
fi

echo
echo "== setup complete. Next:  make os  then  make bus =="
