"""Pinned author source; reviewed alongside the matching author commit."""
import dataclasses
from pathlib import Path
import runpy
from remix.schema import Gate

SOURCE = Path(__file__).resolve().parent / 'upstream/modules/midi-loopback/manifest.py'
MODULE = runpy.run_path(str(SOURCE), run_name='remix_manifest_midi_loopback')['MODULE']
# The cross-unit author runtime is linked and checked together. Independent
# Linked.reference links cannot resolve its mutual Part State/Loopback symbols.
MODULE = dataclasses.replace(MODULE, linked=tuple(
    dataclasses.replace(unit,
        include=(lambda modules, remix, source=unit.include: source(modules)))
    if unit.include else unit for unit in MODULE.linked
), gates=(
    Gate('tools/verify/verify_midi_loopback_reference.py', stage='image', venv=True),
    *MODULE.gates,
))

# Detailed verification lives in developer notes, outside the README index.
MODULE = dataclasses.replace(MODULE, proof_note="")
