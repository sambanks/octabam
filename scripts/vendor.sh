#!/usr/bin/env bash
# The vendored sources this repo builds against: their pins, the local
# patches on them and the helpers that fetch and patch them. One place for
# both consumers -- scripts/setup.sh (the operator's Mac, which also builds)
# and CI (.github/workflows/ci.yml).
#
#   source scripts/vendor.sh          # pins + helpers
#   scripts/vendor.sh mc68k dsp56300  # fetch + patch those trees (no build)

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

# Musashi plus ColdFire mode, an HI08 host-port register file and the on-chip
# peripheral scaffolding -- the CPU half of tools/emu/ot_emu. Vendored, GPLv3, the
# same posture as vendor/dsp56300: tooling and patches are shared, built
# binaries never are. `git show 3ceba41:docs/history/COLDFIRE_PORT.md`.
# Pinned: the port was measured against this commit
# (`git show 3ceba41:docs/history/COLDFIRE_PORT.md`).
MC68K_PIN=4a6d0d17a1f2b30077ab726c27fe9bb770fa0456

# elektron-firmware-tool (mischa85): unpacks and repacks the OS container.
EFT_PIN=065d18f4195793e61891e387813488ee59f6d1ca

# Pinned: tools/patches/dsp56300.patch is against this commit and does not apply to
# a later one without re-basing. Moving the pin means re-basing the patch and
# re-running make check's bit-identity gates.
#
# Re-pinned 28 Oct 2026 from 8ccdd843 (21 Sep) to 8b731966 (66 commits
# later). Upstream now carries, and the patch dropped: the modulo AGU
# bounds compared signed (fdd98fc), the masked-interrupt peripheral service
# (dsp.cpp), `Peripherals56367::setIoExtension` (our unmapped-register
# hooks), a 32-entry DMA request-target table (our out-of-range DRS guard)
# and the dual-counter reload in the 2D transfer loop. Dropped without an
# upstream equivalent: the DMA same-value DCR renewal (no observed effect
# on the Octatrack run). Still ours: the assembler (one-word displaced
# move, two parallel moves), the setM-from-same-register fix, the
# host-stepped mode, the HDI08 transmit FIFO and bursts, the shared window.
DSP56300_PIN=8b731966f9792789adc39fe180a8cf68508f816a

# In a worktree vendor/ is a symlink to the main checkout's (AGENTS.md): the
# fetches, `git checkout` of the pins, the patches and the dsp_host staging
# below would rewrite it for every session on the machine. Refused here, so
# no entry point (make setup, ci-dsp, ci-emu, dsp-repatch) can do it by
# accident; run them from the main checkout.
refuse_shared_vendor() {
  if [ -L vendor ]; then
    echo "vendor.sh: vendor/ is a symlink to $(readlink vendor): fetching, checking out the pins and patching it would change every worktree's toolchain." >&2
    echo "           Run this from the main checkout (CI has its own vendor/)." >&2
    exit 3
  fi
}

pin_checkout() {  # dir url sha
  # A --no-checkout clone has HEAD at the remote's default branch with an empty
  # index and work tree; when the pin is that tip the HEAD test below is
  # false and nothing would be checked out.
  fresh=0
  [ -d "$1" ] || { git clone --no-checkout "$2" "$1"; fresh=1; }
  if [ "$fresh" = 1 ] || [ "$(git -C "$1" rev-parse HEAD 2>/dev/null)" != "$3" ]; then
    git -C "$1" fetch -q origin "$3"
    git -C "$1" checkout -q "$3"
  fi
  echo "   $1 at $(git -C "$1" rev-parse --short HEAD) (pinned)"
}
# apply_patch dir patch: apply, or accept already-applied, or fail loudly
# (a rejected patch reads as "already applied" otherwise).
apply_patch() {
  if git -C "$1" apply --check "$2" 2>/dev/null; then
    git -C "$1" apply "$2" && echo "   local patch applied: $(basename "$2")"
  elif git -C "$1" apply --check --reverse "$2" 2>/dev/null; then
    echo "   local patch already applied: $(basename "$2")"
  else
    echo "   [!] $(basename "$2") does NOT apply to $1 at $(git -C "$1" rev-parse --short HEAD)"
    echo "       (tried: git apply --check; git apply --check --reverse)"
    echo "       and is not already applied either. Fix: rm -rf $1; make setup"
    echo "       (vendor/dsp56300 with an older version of the patch: make dsp-repatch)"
    exit 1
  fi
}

vendor_mc68k() {
  pin_checkout vendor/mc68k https://github.com/joelanders/mc68k-md-mm "$MC68K_PIN"
}

# Two local changes are needed to reproduce this build:
#   - set_version() writes the full 10-char ELEK version field from 0x08;
#     upstream only writes from 0x0D, where 5 fit.
#   - EFT_EMIT_CONTAINER dumps the rebuilt container, which tools/build/make_bin.py
#     wraps to produce the CF card .bin.
vendor_eft() {
  pin_checkout vendor/elektron-firmware-tool https://github.com/mischa85/elektron-firmware-tool "$EFT_PIN"
  apply_patch vendor/elektron-firmware-tool "$(pwd)/tools/patches/elektron-firmware-tool.patch"
}

# The patch carries: the one-word displaced move; a data-ALU op with two
# parallel moves (XY, X:R, R:Y, class II) and a refusal where a move token
# has no encoding (before 4 Oct 2026 the non-parallel form was emitted and
# the moves dropped); the shared window, two-way for dsp_host (X with X, Y
# with Y) and three-way for the ColdFire port's DSP pair (P, X and Y one
# memory, as the chip has it); and the host-stepped mode the port drives
# the cores in (DO loops stepped, interrupts interpreted, an idle step); the
# pre-3cee91c9 DMA arming rule behind DSP::setDmaTriggerOnArm.
# From Tim Hastie's octa-panel (be68244, the port's --dsp-rt mode,
# O17-O22): the JIT cores on worker threads -- a transmit FIFO and
# lock-free rings on the HDI08, burst DMA to and from the host port, the
# writing instruction's PC on a JIT peripheral write, volatile P addresses
# declared up front -- and the JIT's M-register bit op (`bset #$f,m4` kept
# stale modulo words). A tree with an older version of this patch applied:
# `make dsp-repatch`.
vendor_dsp56300() {
  pin_checkout vendor/dsp56300 https://github.com/dsp56300/dsp56300.git "$DSP56300_PIN"
  git -C vendor/dsp56300 submodule update --init --depth 1 --recursive
  apply_patch vendor/dsp56300 "$(pwd)/tools/patches/dsp56300.patch"
  stage_dsp_host
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  set -euo pipefail
  cd "$(dirname "$0")/.."
  [ "$#" -gt 0 ] || { echo "usage: scripts/vendor.sh mc68k|eft|dsp56300 ..."; exit 2; }
  refuse_shared_vendor
  for t in "$@"; do "vendor_$t"; done
fi
