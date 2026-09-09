#!/usr/bin/env bash
# Build a Unicorn whose ColdFire EMAC does fractional-mode multiplies the
# way the MCF5445x does (tools/patches/unicorn_emac_fractional.patch), and park the
# library where tools/emu/emu_bringup.py picks it up automatically.
#
# Why (docs/firmware/RTOS_FORK.md section 10.16, 7 Sep 2026): stock Unicorn 2.1.4
# computes a fractional `macl`/`macw` as an UNSIGNED product shifted right
# by 32; the hardware's is a signed product shifted right by 31 (the 2.62
# product left-shifted one bit, upper 40 bits accumulated). Every EMAC
# fractional result under emulation was therefore half of hardware's:
# the recorder length converter wrote 10,336 for Bryan's 20,672, the
# recorder's block walk stalled at 3,072 samples, and the sequencer's
# per-frame timing byte advanced 8 per 16-sample frame -- the "dropped
# trig at 128 BPM" of section 10.14 and its --arm-phase-fix lever.
#
# Output: .venv/lib/unicorn-emac/libunicorn.2.dylib (or .so.2). The
# Python bindings stay the stock pip package; emu_bringup exports
# LIBUNICORN_PATH to this directory when it exists, and refuses route A
# on a stock EMAC (emu_bringup.emac_selftest).
#
# Host note: build for the CPU your .venv's Python runs on. An x86_64
# (Rosetta) build with Xcode 26's clang produced a library that crashed
# on its first emu_start here (the stock PyPI wheel does not); the native
# arm64 build works. `make emu-setup` creates an arm64 .venv on Apple
# silicon for this reason.
set -euo pipefail
cd "$(dirname "$0")/.."

VER=2.1.4
SHA=00567a70e323f749b419cd86bee4f9115beab7ebba32194581c090cbb7c59cff
URL=https://files.pythonhosted.org/packages/b2/1b/b4248aa8422e86de690cf8e85cf8feae4c33405a097d1ebe71570bdaa6f5/unicorn-$VER.tar.gz
WORK=out/_unicorn_src
OUT=.venv/lib/unicorn-emac
PY=${PY:-.venv/bin/python3}

command -v cmake >/dev/null || { echo "cmake not found (brew install cmake)" >&2; exit 1; }
[ -x "$PY" ] || { echo "$PY not found -- run 'make emu-setup' first" >&2; exit 1; }
ARCH=$("$PY" -c 'import platform; print(platform.machine())')

mkdir -p "$WORK" "$OUT"
if [ ! -f "$WORK/unicorn-$VER.tar.gz" ]; then
  curl -fsSL -o "$WORK/unicorn-$VER.tar.gz" "$URL"
fi
echo "$SHA  $WORK/unicorn-$VER.tar.gz" | shasum -a 256 -c - >/dev/null
rm -rf "$WORK/unicorn-$VER"
tar xzf "$WORK/unicorn-$VER.tar.gz" -C "$WORK"
( cd "$WORK/unicorn-$VER" && patch -p1 < ../../../tools/patches/unicorn_emac_fractional.patch )

EXTRA=()
if [ "$(uname -s)" = Darwin ]; then
  EXTRA+=("-DCMAKE_OSX_ARCHITECTURES=$ARCH")
  export ARCHFLAGS="-arch $ARCH"
fi
cmake -B "$WORK/build" -S "$WORK/unicorn-$VER/src" -DUNICORN_ARCH=m68k \
      -DUNICORN_BUILD_TESTS=off -DCMAKE_BUILD_TYPE=Release "${EXTRA[@]}" >"$WORK/cmake.log" 2>&1
cmake --build "$WORK/build" -j"$(sysctl -n hw.ncpu 2>/dev/null || nproc)" >"$WORK/build.log" 2>&1
cp "$WORK"/build/libunicorn.2.* "$OUT"/ 2>/dev/null || cp "$WORK"/build/libunicorn.so.2 "$OUT"/
ls "$OUT"

LIBUNICORN_PATH="$OUT" "$PY" -c '
import sys; sys.path.insert(0, "tools"); import toolpath
import emu_bringup as eb
ok, detail = eb.emac_selftest()
print("EMAC self-test:", "OK" if ok else "FAILED", detail)
sys.exit(0 if ok else 1)'
