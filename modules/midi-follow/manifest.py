"""Pinned radiohagen source for native MIDI Follow."""
from dataclasses import replace
from pathlib import Path
import runpy

SOURCE = Path(__file__).resolve().parent / 'upstream/modules/midi-follow/manifest.py'
MODULE = runpy.run_path(str(SOURCE), run_name='remix_manifest_midi_follow')['MODULE']

# Qualification belongs to this Octabam integration and its declared gates.
MODULE = replace(MODULE, proof_note=(
    "linked routing/register/response and eight-track stress checks; "
    "project-backed MIDI captures with native chords, TRIG/LIVE, arp and note releases "
    "(26 Oct 2026); hardware testing outstanding"
))
