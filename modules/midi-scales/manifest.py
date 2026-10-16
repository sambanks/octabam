"""MIDI Scales: pinned, separately reviewable author source."""
import dataclasses
import pathlib
import runpy

_SOURCE = pathlib.Path(__file__).resolve().parent / 'upstream/modules/midi-scales/manifest.py'
MODULE = runpy.run_path(str(_SOURCE), run_name='remix_manifest_midi_scales')['MODULE']
# Standalone author build at its original placement; checked on every build.
# Follow/Harmony variants require their own references when contributed.
_REFERENCE = (0x40a955e0, 'e265a08d11b72cc6806c6ac5212969b828c28e2c34681ae088c686e51db8c806')
MODULE = dataclasses.replace(
    MODULE, author_url='https://github.com/radiohagen/octatrack-modules',
    linked=tuple(dataclasses.replace(unit, reference=_REFERENCE) for unit in MODULE.linked),
)

# Detailed verification lives in developer notes, outside the README index.
MODULE = dataclasses.replace(MODULE, proof_note="")
