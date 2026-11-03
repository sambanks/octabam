"""Pinned radiohagen source; lifecycle is provided by EVENTS and STORE."""
from dataclasses import replace
from remix.schema import Gate
from pathlib import Path
import runpy

SOURCE = Path(__file__).resolve().parent / "upstream/modules/midi-harmony/manifest.py"
MODULE = runpy.run_path(str(SOURCE), run_name="remix_manifest_midi_harmony")["MODULE"]

MODULE = replace(MODULE, proof_note="Focused emulator checks; this integration has not been tested on hardware.",
                 gates=(Gate("tools/verify/verify_harmony_reference.py", stage="image", venv=True), *MODULE.gates))
