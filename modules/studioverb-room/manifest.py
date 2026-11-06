"""STUDIO ROOM -- STUDIO VERB on SPRING REV's id, starting in ROOM mode: small, bright and short. Its code is STUDIO VERB's."""
import pathlib
import runpy

_ROWS = runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "studioverb" / "rows.py"),
                       run_name="remix_manifest_studioverb_room")

MODULE = _ROWS["row"]("studioverb-room", "STUDIO ROOM", 0, "SPRING REV", 0x15, b"STRM", b"Studio Room",
                      "STUDIO VERB on SPRING REV's id, starting in ROOM mode: small, bright and short. Its code is STUDIO VERB's.")
