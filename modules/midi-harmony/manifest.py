"""Pinned radiohagen source; lifecycle is provided by EVENTS and STORE."""
from dataclasses import replace
from remix.schema import Evidence, Gate, Level, Linked
from pathlib import Path
import runpy

SOURCE = Path(__file__).resolve().parent / "upstream/modules/midi-harmony/manifest.py"
AUTHOR = runpy.run_path(str(SOURCE), run_name="remix_manifest_midi_harmony")["MODULE"]


def select(modules):
    selected = AUTHOR.select(modules)
    press = Linked("harmonypress", "modules/midi-harmony/held-press.s", dram=True)
    return {**selected, "linked": (*selected["linked"], press)}


# EVENTS owns the held-press detour. Its handler calls the pinned mhc_step_push.
# Retained storage is implemented locally and selected by STORE.
MODULE = replace(AUTHOR, select=select,
                 detours=tuple(d for d in AUTHOR.detours if d.symbol != "mhc_step_push"),
                 requires=("STORE", "EVENTS", "TRIG MODES"),
                 evidence=(Evidence(Level.EMULATOR, ref="verify_midi_harmony.py"),),
                 gates=(Gate("tools/verify/verify_midi_systems.py", stage="image", venv=True),
                        Gate("tools/verify/verify_harmony_reference.py", stage="image", venv=True),
                        Gate("tools/verify/verify_harmony_lifecycle.py", stage="image", venv=True), *AUTHOR.gates))
