"""STUDIO HALL -- STUDIO VERB on DARK REV's id, starting in HALL mode: long, dark, slowly modulated. Its code is STUDIO VERB's."""
import pathlib
import runpy

_ROWS = runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "studioverb" / "rows.py"),
                       run_name="remix_manifest_studioverb_hall")

MODULE = _ROWS["row"]("studioverb-hall", "STUDIO HALL", 2, "DARK REV", 0x16, b"STHL", b"Studio Hall",
                      "STUDIO VERB on DARK REV's id, starting in HALL mode: long, dark, slowly modulated. Its code is STUDIO VERB's.")
