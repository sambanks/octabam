"""Pinned radiohagen source; lifecycle is provided by EVENTS and STORE."""
from pathlib import Path
import runpy

SOURCE = Path(__file__).resolve().parent / "upstream/modules/midi-sram/manifest.py"
MODULE = runpy.run_path(str(SOURCE), run_name="remix_manifest_midi_sram")["MODULE"]
