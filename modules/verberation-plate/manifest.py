"""VERB PLATE -- VERBERATION on PLATE REV's id, starting in PLATE mode: a full plate. Its code is VERBERATION's."""
import pathlib
import runpy

_ROWS = runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "verberation" / "rows.py"),
                       run_name="remix_manifest_verberation_plate")

MODULE = _ROWS["row"]("verberation-plate", "VERB PLATE", 1, "PLATE REV", 0x14, b"VBPL", b"Verb Plate",
                      "VERBERATION on PLATE REV's id, starting in PLATE mode: a full plate. Its code is VERBERATION's.")
