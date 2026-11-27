#!/usr/bin/env bash
# Debian/Ubuntu (including WSL2): install the system tools with apt, build the
# m68k-elf cross-compiler with scripts/m68k-toolchain.sh, then run
# scripts/setup.sh. Idempotent. M68K_PREFIX overrides the toolchain prefix
# (default $HOME/.local/m68k-elf); add its bin/ to PATH for later shells.
# The gcc build dependencies are installed only when the toolchain is absent;
# OPTIONAL_TOOLS=0 leaves out binwalk and radare2; EXTRA_PACKAGES adds
# packages (CI: ccache).
set -euo pipefail
cd "$(dirname "$0")/.."

command -v apt-get >/dev/null 2>&1 \
  || { echo "setup-linux: apt-get not found; install the packages named in scripts/setup-linux.sh with your package manager, run scripts/m68k-toolchain.sh and scripts/setup.sh" >&2; exit 1; }

SUDO=""
[ "$(id -u)" -eq 0 ] || SUDO="sudo"
PREFIX="${M68K_PREFIX:-$HOME/.local/m68k-elf}"
pkgs=(lsof build-essential cmake git curl unzip xxd binutils python3 python3-numpy)
[ "${OPTIONAL_TOOLS:-1}" = 0 ] || pkgs+=(binwalk radare2)
scripts/m68k-toolchain.sh --check "$PREFIX" \
  || pkgs+=(pkgconf texinfo libgmp-dev libmpfr-dev libmpc-dev libisl-dev libzstd-dev zlib1g-dev)
# shellcheck disable=SC2206
pkgs+=(${EXTRA_PACKAGES:-})
apt_sources=()
if [[ ${RUNNER_ENVIRONMENT:-} == github-hosted && -f /etc/apt/sources.list.d/ubuntu.sources ]]; then
  # All required packages come from Ubuntu. An unrelated feed on the runner
  # can return 403 and prevent apt from installing even these archive packages.
  apt_sources=(-o Dir::Etc::sourcelist=/etc/apt/sources.list.d/ubuntu.sources -o Dir::Etc::sourceparts=-)
fi
$SUDO apt-get "${apt_sources[@]}" update
$SUDO apt-get "${apt_sources[@]}" install -y "${pkgs[@]}"
command -v uv >/dev/null 2>&1 \
  || echo "setup-linux: uv not installed; make emu-setup needs it (curl -LsSf https://astral.sh/uv/install.sh | sh)"

scripts/m68k-toolchain.sh "$PREFIX"
export PATH="$PREFIX/bin:$PATH"
echo "setup-linux: add $PREFIX/bin to PATH for later shells"

exec scripts/setup.sh
