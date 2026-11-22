"""VERB PLATE -- Not a separate reverb: a second chooser row for VERBERATION, on PLATE REV's id, with MODE set to PLATE (a full plate), so a Part saved with PLATE REV opens on it."""
import pathlib
import runpy

_ROWS = runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "verberation" / "rows.py"),
                       run_name="remix_manifest_verberation_plate")

MODULE = _ROWS["row"]("verberation-plate", "VERB PLATE", 1, "PLATE REV", 0x14, b"VBPL", b"Verb Plate",
                      "Not a separate reverb: a second chooser row for VERBERATION, on PLATE REV's id, with MODE set to PLATE (a full plate), so a Part saved with PLATE REV opens on it.")
