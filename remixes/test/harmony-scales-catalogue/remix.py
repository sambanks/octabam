"""SCALES catalogue with Harmony and Factory, without Follow."""
from dataclasses import replace
from remix import registry
BASE = registry.remix('midi-chords-scales')
REMIX = replace(BASE, name='harmony-scales-catalogue',
                modules=tuple(m for m in BASE.modules if m != 'MIDI FOLLOW'),
                doc='Harmony and Factory with all SCALES choices and no Follow.')
