"""Combined MIDI playing modes using SCALES as the sole scale provider."""
from dataclasses import replace
from remix import registry

base = registry.remix('midi-chords')
REMIX = replace(base, name='midi-chords-scales',
                modules=tuple('SCALES' if key == 'MIDI SCALES' else key for key in base.modules),
                doc='Factory, Harmony and Follow with the SCALES catalogue.')
