"""Pinned radiohagen source for native MIDI Follow."""
from dataclasses import replace
from pathlib import Path
import runpy
from remix.schema import Gate

SOURCE = Path(__file__).resolve().parent / 'upstream/modules/midi-follow/manifest.py'
MODULE = runpy.run_path(str(SOURCE), run_name='remix_manifest_midi_follow')['MODULE']

# Qualification belongs to this Octabam integration and its declared gates.
MODULE = replace(MODULE, proof_note=(
    "linked routing/register/response and eight-track stress checks; "
    "GRAV instruction/lifecycle and full-firmware captures (30 Oct 2026); "
    "earlier MKII MFOL29U/FA notes/releases and Part persistence (29 Oct 2026); "
    "current revision not hardware tested"
), gates=MODULE.gates + (
    Gate('tools/verify/verify_midi_follow_cpu.py', stage='image', venv=True),
))
