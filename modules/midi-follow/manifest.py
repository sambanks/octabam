"""Pinned radiohagen source for native MIDI Follow."""
from pathlib import Path
import runpy

SOURCE = Path(__file__).resolve().parent / 'upstream/modules/midi-follow/manifest.py'
MODULE = runpy.run_path(str(SOURCE), run_name='remix_manifest_midi_follow')['MODULE']
