"""Pinned author source; reviewed alongside the matching author commit."""
import dataclasses
from pathlib import Path
import runpy
from remix.schema import Gate

SOURCE = Path(__file__).resolve().parent / 'upstream/modules/midi-loopback/manifest.py'
MODULE = runpy.run_path(str(SOURCE), run_name='remix_manifest_midi_loopback')['MODULE']
# The STORE service owns Part code; verify the client's own linked units.
MODULE = dataclasses.replace(MODULE, gates=(
    Gate('tools/verify/verify_midi_loopback_reference.py', stage='image', venv=True),
    *MODULE.gates,
), proof_note="STORE native Part/context and client machine checks pass; hardware testing outstanding")
