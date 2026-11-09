"""The OCTABAM instrument with the collected MIDI modules."""
from dataclasses import replace
from remix import registry
from remix.schema import Proof

BASE = registry.remix('octabam')
REMIX = replace(BASE, name='midi', family='mods', proof=Proof.PORT,
                modules=(*BASE.modules, 'MIDI HARMONY', 'MIDI FOLLOW', 'MIDI LOOPBACK'),
                doc='OCTABAM with Harmony, Follow and Loopback; SCALES and Chords Factory remain available.',
                proof_note='Combined software qualification in progress; no hardware acceptance')
