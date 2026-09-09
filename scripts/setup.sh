#!/usr/bin/env bash
# Install the toolchain this repo builds against. Idempotent -- safe to re-run.
#
# The thing that actually matters here is step 4: the DSP56300 assembler
# (dsp_asm) and emulator harness (dsp_host). Those are what let effects be
# assembled and auditioned locally instead of by flashing hardware.
set -euo pipefail

# Copy our sources into the vendor tree. Always overwrite: tools/dsp_host/ is
# the source of truth. Two diverging copies means an edit that never reaches
# the binary, which produces confidently wrong measurements.
stage_dsp_host() {
  mkdir -p vendor/dsp56300/source/dsp_host
  cp tools/dsp_host/dsp_asm.cpp tools/dsp_host/dsp_host.cpp \
     tools/dsp_host/CMakeLists.txt vendor/dsp56300/source/dsp_host/ 2>/dev/null || true
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
# peripheral scaffolding -- the CPU half of tools/ot_emu. Vendored, GPLv3, the
# same posture as vendor/dsp56300: tooling and patches are shared, built
# binaries never are. `docs/COLDFIRE_PORT.md`.
if [ ! -d vendor/mc68k ]; then
  git clone https://github.com/joelanders/mc68k-md-mm vendor/mc68k
else
  echo "   already cloned; git pull ..."
  git -C vendor/mc68k pull --ff-only || true
fi

echo
echo "== 2) elektron-firmware-tool (mischa85) =="
if [ ! -d vendor/elektron-firmware-tool ]; then
  git clone https://github.com/mischa85/elektron-firmware-tool vendor/elektron-firmware-tool
else
  echo "   already cloned; git pull ..."
  git -C vendor/elektron-firmware-tool pull --ff-only || true
fi

# Two local changes are needed to reproduce this build:
#   - set_version() writes the full 10-char ELEK version field from 0x08;
#     upstream only writes from 0x0D, where 5 fit.
#   - EFT_EMIT_CONTAINER dumps the rebuilt container, which tools/make_bin.py
#     wraps to produce the CF card .bin.
PATCH=$(pwd)/tools/elektron-firmware-tool.patch
if [ -f "$PATCH" ]; then
  if git -C vendor/elektron-firmware-tool apply --check "$PATCH" 2>/dev/null; then
    git -C vendor/elektron-firmware-tool apply "$PATCH" && echo "   local patch applied"
  else
    echo "   local patch already applied (or upstream changed: check $PATCH)"
  fi
fi

echo "   building ..."
if [ -f vendor/elektron-firmware-tool/Makefile ]; then
  make -C vendor/elektron-firmware-tool || echo "   [!] make failed — see vendor/elektron-firmware-tool/README"
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
# See docs/DSP.md and tools/dsp_modmap.py.
DIS=vendor/dsp56300/build/source/disassemble/dsp56kDisassemble
if [ ! -x "$DIS" ]; then
  if ! command -v cmake >/dev/null 2>&1; then
    echo "   [!] cmake not found — brew install cmake"
  else
    [ -d vendor/dsp56300 ] || git clone --depth 1 \
      https://github.com/dsp56300/dsp56300.git vendor/dsp56300
    git -C vendor/dsp56300 submodule update --init --depth 1 --recursive
    # The patch carries: MPYRI (unimplemented upstream in interpreter and
    # JIT; stock LO-FI uses it, 2 Sep 2026); the shared window, two-way for
    # dsp_host (X with X, Y with Y) and three-way for the ColdFire port's DSP
    # pair (P, X and Y one memory, as the chip has it); and the host-stepped
    # mode the port drives the cores in (DO loops stepped, interrupts
    # interpreted, peripherals serviced under a masked interrupt, an idle
    # step) plus hooks for Y-side registers it does not map (8 Sep 2026, O8).
    EMUPATCH=$(pwd)/tools/dsp56300.patch
    if git -C vendor/dsp56300 apply --check "$EMUPATCH" 2>/dev/null; then
      git -C vendor/dsp56300 apply "$EMUPATCH" && echo "   emulator patch applied (MPYRI, shared window, host-stepped cores)"
    else
      echo "   emulator patch already applied (or upstream changed: check $EMUPATCH)"
    fi
    stage_dsp_host
    cmake -S vendor/dsp56300 -B vendor/dsp56300/build -DCMAKE_BUILD_TYPE=Release \
      && cmake --build vendor/dsp56300/build \
           --target dsp56kDisassemble dsp_asm dsp_host -j8 \
      || echo "   [!] build failed — check vendor/dsp56300"
  fi
else
  echo "   already built: $DIS"
  stage_dsp_host
fi

echo
echo "== setup complete. Next:  make os  then  make bus =="
