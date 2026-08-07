#!/usr/bin/env bash
# Download and unpack the official Octatrack OS from Elektron's support site.
#
# Nothing Elektron ships is redistributed by this repository -- you fetch your
# own copy here, and every build is derived reproducibly from it. Note the
# SHA256 this prints: it is what makes a build claim checkable by someone else.
set -euo pipefail
cd "$(dirname "$0")/.."

OS_VER="1.40C"
ZIP_URL="https://www.elektron.se/wp-content/uploads/2025/03/OCTATRACK_OS${OS_VER}_dist.zip"
README_URL="https://www.elektron.se/wp-content/uploads/2025/03/OCTATRACK_OS${OS_VER}_readme.pdf"
DL=downloads
ZIP="$DL/OCTATRACK_OS${OS_VER}_dist.zip"

mkdir -p "$DL"

echo "[fetch] downloading OS $OS_VER ..."
curl -fL --retry 3 --max-time 120 -o "$ZIP" "$ZIP_URL"
curl -fL --retry 3 --max-time 120 -o "$DL/OCTATRACK_OS${OS_VER}_readme.pdf" "$README_URL"

echo "[fetch] ZIP hash (record this -- it pins reproducibility):"
shasum -a 256 "$ZIP"

echo "[fetch] extracting ..."
unzip -o "$ZIP" -d "$DL/extracted"

echo "[fetch] firmware artifacts found:"
find "$DL/extracted" -type f \( -iname '*.bin' -o -iname '*.syx' \) -exec ls -la {} \;

echo
echo "[fetch] done. Next:  make recon   (or scripts/analyze.sh)"
