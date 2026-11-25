"""The OCTABAM instrument with the collected MIDI modules."""
from dataclasses import replace
from remix import registry
from remix.schema import Evidence, Level

BASE = registry.remix('octabam')
REMIX = replace(BASE, name='midi', family='mods', evidence=(Evidence(Level.EMULATOR),),
                modules=(*BASE.modules, 'MIDI HARMONY', 'MIDI FOLLOW'),
                doc='OCTABAM with Harmony, Follow and Loopback; SCALES and Chords Factory remain available.')
