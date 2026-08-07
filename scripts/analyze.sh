#!/usr/bin/env bash
# Static recon of the Octatrack firmware artifacts you supplied.
# Runs entropy, binwalk, strings, and (if built) elektron-firmware-tool.
#
# This is the bootstrap step: it produces out/raw/section_3_MAIN_OS.bin, which
# every build script reads as its base image. Run scripts/fetch-os.sh first.
set -euo pipefail
cd "$(dirname "$0")/.."

EXTRACTED=downloads/extracted
OUT=out
mkdir -p "$OUT"

mapfile -t ARTIFACTS < <(find "$EXTRACTED" -type f \( -iname '*.bin' -o -iname '*.syx' \) 2>/dev/null)
if [ "${#ARTIFACTS[@]}" -eq 0 ]; then
  echo "[analyze] no .bin/.syx under $EXTRACTED — run scripts/fetch-os.sh first." >&2
  exit 1
fi

for f in "${ARTIFACTS[@]}"; do
  base=$(basename "$f")
  echo "############################################################"
  echo "# $base"
  echo "############################################################"
  ls -la "$f"
  echo "sha256: $(shasum -a 256 "$f" | awk '{print $1}')"
  echo

  echo "--- [1] Entropy (compressed/encrypted vs. plain code) ---"
  python3 tools/entropy.py "$f" --csv "$OUT/${base}.entropy.csv" --png "$OUT/${base}.entropy.png" || true
  echo

  echo "--- [2] binwalk (signatures, filesystems, magic) ---"
  if command -v binwalk >/dev/null 2>&1; then
    binwalk "$f" | tee "$OUT/${base}.binwalk.txt" || true
  else
    echo "    (binwalk not installed; run scripts/setup.sh)"
  fi
  echo

  echo "--- [3] Header (first 64 bytes) ---"
  xxd -l 64 "$f"
  echo

  echo "--- [4] Long strings (versions, menus, paths) ---"
  strings -n 6 "$f" | sort -u | head -40 | tee "$OUT/${base}.strings.txt" >/dev/null
  head -20 "$OUT/${base}.strings.txt"
  echo "    (full dump in $OUT/${base}.strings.txt)"
  echo

  # elektron-firmware-tool only applies to the .syx container.
  if [[ "$base" == *.syx ]]; then
    echo "--- [5] elektron-firmware-tool (layers/checksums/decompression) ---"
    EFT=vendor/elektron-firmware-tool/elektron-firmware-tool
    if [ -x "$EFT" ]; then
      "$EFT" "$f" 2>&1 | tee "$OUT/${base}.eft.txt" || \
        echo "    (tool exited non-zero; check its usage: $EFT --help)"
    else
      echo "    (elektron-firmware-tool not built; run scripts/setup.sh)"
    fi
    echo
  fi
done

echo "############################################################"
echo "# Summary"
echo "############################################################"
echo "Outputs in $OUT/:"
ls -la "$OUT"
cat <<'EOF'

How to read the results:
  * Entropy ~8.0 across the WHOLE payload -> strong encryption (hard).
  * Entropy ~8.0 in blocks only           -> compressed sections (tractable).
  * Mid entropy + readable strings        -> plain ColdFire code/tables.
  * binwalk finds gzip/lzma/zlib          -> decompress, then analyse the raw.
  * If elektron-firmware-tool extracts raw sections, THAT is the firmware to
    load into Ghidra/radare2 as m68k/ColdFire big-endian.

The extracted MAIN OS section is what `make bus` patches.
Disassembly notes: docs/history/NOTES.md
EOF
