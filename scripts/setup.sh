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
if [ "${#need_brew[@]}" -gt 0 ]; then
  echo "   installing: ${need_brew[*]}"
  brew install "${need_brew[@]}"
else
  echo "   binwalk and radare2 already present."
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
    # MPYRI (immediate multiply, rounded) is unimplemented upstream in both
    # the interpreter and the JIT; Elektron's stock LO-FI uses it, so a
    # render of LO-FI aborted with "Not Implemented: MPYRI" (2 Sep 2026).
    EMUPATCH=$(pwd)/tools/dsp56300.patch
    if git -C vendor/dsp56300 apply --check "$EMUPATCH" 2>/dev/null; then
      git -C vendor/dsp56300 apply "$EMUPATCH" && echo "   emulator patch applied (MPYRI)"
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
