"""VERB PLATE -- VERBERATION on PLATE REV's id, in PLATE mode, with no chooser row in octabam-verbs (Remix.hidden): VERB PARTS reads its defaults to move a Part saved with PLATE REV onto VERBERATION."""
import pathlib
import runpy

_ROWS = runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "verberation" / "rows.py"),
                       run_name="remix_manifest_verberation_plate")

MODULE = _ROWS["row"]("verberation-plate", "VERB PLATE", 1, "PLATE REV", 0x14, b"VBPL", b"Verb Plate",
                      "VERBERATION on PLATE REV's id, in PLATE mode, with no chooser row in octabam-verbs (Remix.hidden): VERB PARTS reads its defaults to move a Part saved with PLATE REV onto VERBERATION.")
