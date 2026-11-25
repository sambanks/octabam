"""Pinned author source (radiohagen's MIDI Loopback / MIDI Scenes bridge),
reviewed alongside the matching author commit.

The author's manifest pins the MIDI Scenes source of his own tree. Here the
bridge links against octabam's modules/midi-scenes/scenes.s, so the pin is
that file's hash. Changing scenes.s refuses the build until these producer
boundaries are re-audited:

- scn_pbi and scn_pp (the Part the mix plays) are at scn_state+288 and +292;
- the one `jsr MIDI_TX` (0x40010bc8) of the sequencer CC loop lies in
  scn_ccnote..scn_clear;
- the one `jsr CC_TX` (0x4009eec8) of the mixer lies in
  scn_morph..scn_invalidate (MIDI LOOPBACK's HAVE_SCENES_BRIDGE path).

tools/verify/verify_midi_loopback_scenes.py checks all three in the linked
runtime, then runs both producers for every track and route.
"""
import dataclasses
import hashlib
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE.parent / 'midi-loopback/upstream/modules/midi-loopback-scenes'
SCENES = HERE.parent / 'midi-scenes/scenes.s'
SCENES_SHA256 = 'c8eab7c18e1d2ae9b92215ab2a35528941276960a82b28780db1a179bf08c31d'


def boundaries(_modules, remix=None):
    if hashlib.sha256(SCENES.read_bytes()).hexdigest() != SCENES_SHA256:
        raise SystemExit('MIDI LOOPBACK SCENES: modules/midi-scenes/scenes.s changed; re-audit the '
                         'producer boundaries in modules/midi-loopback-scenes/manifest.py and re-pin')
    return ''


MODULE = runpy.run_path(str(UPSTREAM / 'manifest.py'),
                        run_name='remix_manifest_midi_loopback_scenes')['MODULE']
(_unit,) = MODULE.linked
MODULE = dataclasses.replace(
    MODULE,
    linked=(dataclasses.replace(_unit, source=str(UPSTREAM / 'bridge.s'), include=boundaries),),
    # The bridge is meaningless without both; with both it is mandatory.
    joins=('MIDI LOOPBACK', 'MIDI SCENES'),
    proof_note='Producer and routing checks under the port; hardware testing outstanding',
)
