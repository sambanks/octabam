"""VERB HALL -- Not a separate reverb: a second chooser row for VERBERATION, on DARK REV's id, with MODE set to HALL (long, dark, slowly modulated), so a Part saved with DARK REV opens on it."""
import pathlib
import runpy

_ROWS = runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "verberation" / "rows.py"),
                       run_name="remix_manifest_verberation_hall")

MODULE = _ROWS["row"]("verberation-hall", "VERB HALL", 2, "DARK REV", 0x16, b"VBHL", b"Verb Hall",
                      "Not a separate reverb: a second chooser row for VERBERATION, on DARK REV's id, with MODE set to HALL (long, dark, slowly modulated), so a Part saved with DARK REV opens on it.")
