"""Pinned author source; reviewed alongside the matching author commit."""
import dataclasses
from pathlib import Path
import runpy
from remix.schema import Gate

SOURCE = Path(__file__).resolve().parent / '../midi-loopback/upstream/modules/midi-part-state/manifest.py'
MODULE = runpy.run_path(str(SOURCE), run_name='remix_manifest_midi_part_state')['MODULE']

# Cold-entry unit is independently linkable; enforce its author reference
# on every build. The mutually linked DRAM units use the combined oracle.
MODULE = dataclasses.replace(MODULE, linked=tuple(
    dataclasses.replace(unit, reference=(0x400d6b80,
        '4de11692e14103dde57ed86c303a7332998c912fb8156fcf90b21a6f0ce32ca2'))
    if unit.label == 'midipartentry' else unit for unit in MODULE.linked
))

MODULE = dataclasses.replace(MODULE, gates=(
    *MODULE.gates,
    Gate('tools/verify/verify_midi_part_boot.py', stage='image', venv=True),
))

# Detailed verification lives in developer notes, outside the README index.
MODULE = dataclasses.replace(MODULE, proof_note="")
