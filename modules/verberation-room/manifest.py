"""VERB ROOM -- Not a separate reverb: a second chooser row for VERBERATION, on SPRING REV's id, with MODE set to ROOM (small, bright and short), so a Part saved with SPRING REV opens on it."""
import pathlib
import runpy

_ROWS = runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "verberation" / "rows.py"),
                       run_name="remix_manifest_verberation_room")

MODULE = _ROWS["row"]("verberation-room", "VERB ROOM", 0, "SPRING REV", 0x15, b"VBRM", b"Verb Room",
                      "Not a separate reverb: a second chooser row for VERBERATION, on SPRING REV's id, with MODE set to ROOM (small, bright and short), so a Part saved with SPRING REV opens on it.")
