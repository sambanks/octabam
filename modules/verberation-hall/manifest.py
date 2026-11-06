"""VERB HALL -- VERBERATION on DARK REV's id, starting in HALL mode: long, dark, slowly modulated. Its code is VERBERATION's."""
import pathlib
import runpy

_ROWS = runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "verberation" / "rows.py"),
                       run_name="remix_manifest_verberation_hall")

MODULE = _ROWS["row"]("verberation-hall", "VERB HALL", 2, "DARK REV", 0x16, b"VBHL", b"Verb Hall",
                      "VERBERATION on DARK REV's id, starting in HALL mode: long, dark, slowly modulated. Its code is VERBERATION's.")
