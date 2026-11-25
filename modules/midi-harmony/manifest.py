"""Pinned radiohagen source; lifecycle is provided by EVENTS and STORE."""
from dataclasses import replace
from remix.schema import Evidence, Gate, Level
from pathlib import Path
import runpy

SOURCE = Path(__file__).resolve().parent / "upstream/modules/midi-harmony/manifest.py"
MODULE = runpy.run_path(str(SOURCE), run_name="remix_manifest_midi_harmony")["MODULE"]

# Retained storage is implemented locally and selected by STORE.
MODULE = replace(MODULE, requires=("STORE", "EVENTS", "TRIG MODES"),
                 evidence=(Evidence(Level.EMULATOR, ref="verify_midi_harmony.py"),),
                 gates=(Gate("tools/verify/verify_midi_systems.py", stage="image", venv=True),
                        Gate("tools/verify/verify_harmony_reference.py", stage="image", venv=True),
                        Gate("tools/verify/verify_harmony_lifecycle.py", stage="image", venv=True), *MODULE.gates))
