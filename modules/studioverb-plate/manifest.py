"""STUDIO PLATE -- STUDIO VERB on PLATE REV's id, starting in PLATE mode: a full plate. Its code is STUDIO VERB's."""
import pathlib
import runpy

_ROWS = runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "studioverb" / "rows.py"),
                       run_name="remix_manifest_studioverb_plate")

MODULE = _ROWS["row"]("studioverb-plate", "STUDIO PLATE", 1, "PLATE REV", 0x14, b"STPL", b"Studio Plate",
                      "STUDIO VERB on PLATE REV's id, starting in PLATE mode: a full plate. Its code is STUDIO VERB's.")
