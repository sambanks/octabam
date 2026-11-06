"""VERB ROOM -- VERBERATION on SPRING REV's id, starting in ROOM mode: small, bright and short. Its code is VERBERATION's."""
import pathlib
import runpy

_ROWS = runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "verberation" / "rows.py"),
                       run_name="remix_manifest_verberation_room")

MODULE = _ROWS["row"]("verberation-room", "VERB ROOM", 0, "SPRING REV", 0x15, b"VBRM", b"Verb Room",
                      "VERBERATION on SPRING REV's id, starting in ROOM mode: small, bright and short. Its code is VERBERATION's.")
