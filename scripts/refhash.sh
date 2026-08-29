#!/usr/bin/env bash
#
# refhash.sh -- bit-identity baseline for the remix refactor.
#
# LOCAL DISCIPLINE, NOT CI. Every hash here depends on the operator's own copy
# of the stock OS (out/raw/section_3_MAIN_OS.bin), so the baseline is untracked
# and only means anything on the machine that saved it.
#
#   scripts/refhash.sh save     # on the tree you trust, BEFORE touching anything
#   ...refactor...
#   scripts/refhash.sh check    # every artifact and every build report must match
#
# Why this matrix: a refactor of build_bus.py breaks things that still build,
# still boot and still make sound. The cases pin the failure modes that have no
# other gate --
#
#   bus/plain        the two shipping layouts
#   render/*-delay   the DEV hatch, including the out-of-region delay record
#                    appended to the .mem dump
#   mode1            the ";_OVERRIDE" immediate-substitution path
#   noshim           the SHIMMER_BEGIN/END excision
#   marker           the MARKER splice (which requires NOSHIM -- so this case
#                    also pins the ORDER of excision vs splice)
#   burn             the BURN splice into the live engine. It DOES place
#                    (the Makefile's help text still says otherwise; what
#                    does not fit is the alias-probe combo in a plain layout)
#   delay-override   two delay overrides at once
#   hkb              the housekeeper flip
#
# Build stdout is hashed alongside the artifacts on purpose: verify_delay.py,
# verify_roll.py and verify_burn.py all parse the build report, so the report
# text is part of the build's API and a "harmless" rewording is a breaking
# change.

set -uo pipefail
cd "$(dirname "$0")/.."

CASES=(
  "bus|XBUS=1 SPEC=1"
  "plain|"
  "render|DEV=1 XBUS=1 SPEC=1"
  "render-delay|DEV=1 XBUS=1"
  "mode1|XBUS=1 SPEC=1 MODE=1"
  "noshim|XBUS=1 SPEC=1 NOSHIM=1"
  "marker|XBUS=1 NOSHIM=1 MARKER=1"
  "burn|XBUS=1 BURN=1"
  # XBUS with neither SPEC nor DEV is the one layout that renames the effects
  # to XVerb/NotUsed (and re-abbreviates them). Nothing else reaches that arm.
  "xbus-only|XBUS=1"
  "delay-override|DEV=1 XBUS=1 DMODE=2 DINT=7"
  "hkb|HKB=1 XBUS=1 SPEC=1"
  # Every remaining env-conditional effect NAME/table mutation gets a case.
  # The panel name is rewritten from six different places depending on the
  # flags, and a name is 13 bytes in a cloned descriptor -- exactly the kind
  # of thing that survives a refactor looking fine and ships the wrong string
  # to a unit whose running build you then cannot identify.
  # The three diagnostics that replace the reverb's engine. Under XBUS the
  # delay is stubbed, which leaves room for them, and they produce real
  # images -- so those cases pin the descriptor a probe build writes,
  # including the panel name that says which diagnostic is running.
  "xbus-probe|XBUS=1 PROBE=1"
  "xbus-xprobe|XBUS=1 XPROBE=1"
  "xbus-tprobe|XBUS=1 TPROBE=1"
  # The same three in a PLAIN layout, where the real delay overruns the
  # region. They pin the failure, which is a real thing to preserve: it is
  # the honest "no room" refusal, not a code defect.
  "probe|PROBE=1"
  "xprobe|XPROBE=1"
  "tprobe|TPROBE=1"
  "delayprobe-silence|XBUS=1 DELAYPROBE=silence"
  "delayprobe-send|XBUS=1 DELAYPROBE=send"
  "delayprobe-stock|XBUS=1 DELAYPROBE=stock"
  "notempo|XBUS=1 SPEC=1 NOTEMPO=1"
  "tempocave-replay|XBUS=1 SPEC=1 TEMPOCAVE=replay"
  "dfrz|DEV=1 XBUS=1 DFRZ=1"
  "dfrzat|DEV=1 XBUS=1 DFRZAT=3"
  "dnote|DEV=1 XBUS=1 DNOTE=84"
  "xbusbase|XBUS=1 SPEC=1 XBUS_BASE=35000"
)

# Everything build_bus.py can write. Cleared before each case so a stale
# artifact from the previous case is never mistaken for this one's output.
artifacts() {
  ls out/mainos_bus.bin \
     out/mainos_bus_dev.bin \
     out/mainos_bus_mode*.bin \
     out/mainos_bus_delayprobe_*.bin \
     out/dsp/mem_dev_A.mem 2>/dev/null | sort
}

sha() { shasum -a 256 "$1" | cut -d' ' -f1; }

# Three cases pin a FAILURE, and a Python traceback carries the source line
# number, which every refactor moves. Normalising those out keeps what the
# traceback actually asserts -- which exception, raised evaluating what -- and
# drops the one field that is guaranteed to churn. Nothing else is touched:
# the build report proper is compared verbatim, because tools parse it.
normalise() {
  sed -E -i '' -e 's|File "[^"]*", line [0-9]+|File "<src>", line <n>|g' "$1"
}

run_matrix() {
  local outdir="$1"
  rm -rf "$outdir"; mkdir -p "$outdir"
  local manifest="$outdir/manifest.txt"
  : > "$manifest"

  for spec in "${CASES[@]}"; do
    local name="${spec%%|*}" envs="${spec#*|}"
    rm -f out/mainos_bus.bin out/mainos_bus_dev.bin out/mainos_bus_mode*.bin \
          out/mainos_bus_delayprobe_*.bin out/dsp/mem_dev_A.mem
    local log="$outdir/$name.log" rc=0
    # shellcheck disable=SC2086 -- word splitting of $envs is the point
    env $envs python3 tools/build_bus.py > "$log" 2>&1 || rc=$?
    normalise "$log"
    {
      echo "case $name rc=$rc"
      while IFS= read -r f; do
        [ -n "$f" ] || continue
        echo "  $(sha "$f")  $f"
      done < <(artifacts)
      echo "  $(sha "$log")  <report>"
    } >> "$manifest"
    printf '  %-16s rc=%d\n' "$name" "$rc"
  done
}

restore() {
  # Leave the shipping artifact on disk, the way `make check` does.
  XBUS=1 SPEC=1 python3 tools/build_bus.py > /dev/null 2>&1 || true
}

case "${1:-}" in
  save)
    echo "refhash: saving baseline (${#CASES[@]} builds)"
    run_matrix out/refhash/baseline
    restore
    echo
    echo "  baseline -> out/refhash/baseline/manifest.txt"
    ;;
  check)
    [ -f out/refhash/baseline/manifest.txt ] || {
      echo "refhash: no baseline -- run 'scripts/refhash.sh save' on a tree you trust"; exit 2; }
    echo "refhash: checking against baseline (${#CASES[@]} builds)"
    run_matrix out/refhash/current
    restore
    echo
    if diff -u out/refhash/baseline/manifest.txt out/refhash/current/manifest.txt > out/refhash/manifest.diff; then
      rm -f out/refhash/manifest.diff
      echo "  ALL ${#CASES[@]} CASES BIT-IDENTICAL"
      exit 0
    fi
    echo "  MISMATCH -- the refactor is not behaviour-preserving"
    echo
    cat out/refhash/manifest.diff
    echo
    # A report-only mismatch is the common case and the manifest hash alone
    # does not say what changed, so diff the reports of the failing cases.
    for spec in "${CASES[@]}"; do
      local_name="${spec%%|*}"
      if ! cmp -s "out/refhash/baseline/$local_name.log" "out/refhash/current/$local_name.log"; then
        echo "--- report diff: $local_name ---"
        diff -u "out/refhash/baseline/$local_name.log" "out/refhash/current/$local_name.log" | head -60
      fi
    done
    exit 1
    ;;
  *)
    echo "usage: scripts/refhash.sh save|check"
    exit 2
    ;;
esac
