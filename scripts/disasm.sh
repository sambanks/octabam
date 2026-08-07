#!/usr/bin/env bash
# Disassembly helper for the decompressed MAIN OS (ColdFire, m68k big-endian).
#
# This is the ColdFire side -- the OS itself. The audio effects run on the
# DSP56300 and are a different toolchain entirely: see tools/dsp_disasm_all.py
# and docs/DSP.md.
#
# Usage:
#   scripts/disasm.sh                 open r2 interactively on the raw image
#   scripts/disasm.sh strings         dump every string with its offset
#   scripts/disasm.sh pd 0x1000       run an r2 expression and exit
set -euo pipefail
cd "$(dirname "$0")/.."

RAW="${RAW:-out/raw/section_3_MAIN_OS.bin}"
[ -f "$RAW" ] || { echo "$RAW not found — run scripts/analyze.sh first." >&2; exit 1; }

# m68k big-endian covers most of the ColdFire ISA.
# Load base determined empirically (tools/find_base.py): 0x40000400
# (image in SDRAM at 0x40000000 + 0x400 of header/vectors). Data/BSS ~0x400bxxxx.
BASE="${BASE:-0x40000400}"
# -m maps the raw at the base (-B does not remap raw files in r2).
R2FLAGS=(-a m68k -b 32 -e cfg.bigendian=true -m "$BASE")

case "${1:-}" in
  strings)
    r2 -q "${R2FLAGS[@]}" -c 'e bin.str.raw=true; izz~...' "$RAW" 2>/dev/null || \
      strings -t x -n 6 "$RAW"
    ;;
  "")
    echo "Opening r2 (m68k BE). Useful commands:"
    echo "  aaa            analyse    |  pd 40      disassemble   |  izz  strings"
    echo "  afl            functions  |  s <addr>   seek          |  V    visual mode"
    exec r2 "${R2FLAGS[@]}" "$RAW"
    ;;
  *)
    r2 -q "${R2FLAGS[@]}" -c "$*" "$RAW"
    ;;
esac
