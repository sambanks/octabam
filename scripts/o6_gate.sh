#!/usr/bin/env bash
# THE O6 FIDELITY GATE: does the C++ port's sequencer land the same trig, on
# the same frame, after the same number of ticks, as route A's?
#
#   scripts/o6_gate.sh [PROJECT] [SET] [NAME]
#
# Four steps, and the first two are what make the comparison mean anything:
#   1. stage ONE card image with route A's own staging, so both emulators read
#      identical media (tools/ot_emu/stage_card.py);
#   2. run route A -- the ORACLE -- and write its M6c facts;
#   3. run the port the same way and write its own;
#   4. diff them field by field, strictly (tools/ot_emu/oracle.py).
#
# ⚠️ Route A's run costs about two minutes and the port's about the same; this
# is not a per-commit check. `make check` does not run it. Set SKIP_ORACLE=1 to
# reuse an existing out/oracle/m6c.json when only the port has changed.
set -euo pipefail

PROJECT=${1:-out/_testproj}
SET=${2:-OCTABAM}
NAME=${3:-RIG}
PY=${PY:-.venv/bin/python3}
IMAGE=${IMAGE:-out/raw/section_3_MAIN_OS.bin}
FRAMES=${FRAMES:-400}
STEP=${STEP:-2}
MS=${MS:-20000}

mkdir -p out/oracle

echo "== staging the card (route A's own staging, so both read identical media)"
"$PY" tools/ot_emu/stage_card.py "$PROJECT" "$SET" "$NAME" \
    --tree out/_o6_tree_port --out out/o6_card.img

if [ "${SKIP_ORACLE:-0}" = 1 ] && [ -f out/oracle/m6c.json ]; then
    echo "== reusing out/oracle/m6c.json (SKIP_ORACLE=1)"
else
    echo "== route A (the oracle)"
    "$PY" tools/emu_rtos.py --project "$PROJECT" --set "$SET" --name "$NAME" \
        --tree out/_o6_tree --sequencer --internal-clock --poke-trig "$STEP" \
        --frames "$FRAMES" --ms "$MS" --golden out/oracle/m6c.json \
        | grep -v '^   ' | tail -20
fi

echo "== the port${DSP:+ (with the two DSP cores behind the host port, O8)}"
cmake --build out/emu -j8 >/dev/null
# DSP=1 puts the real DSP cores behind the host port (O8): the firmware boots
# them itself, and the frame handshake runs against them instead of the two
# stand-in replies. Both forms are gated against the same route A oracle.
./out/emu/ot_emu --image "$IMAGE" --card out/o6_card.img --set "$SET" --project "$NAME" \
    --sequencer --internal-clock --poke-trig "$STEP" --frames "$FRAMES" --load-ms "$MS" \
    ${DSP:+--dsp} --m6c-golden out/oracle/port_m6c.json | tail -30

echo "== the diff"
python3 tools/ot_emu/oracle.py out/oracle/m6c.json out/oracle/port_m6c.json
