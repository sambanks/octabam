"""Joined selection for Scenes and Loopback's explicit producer callbacks."""
from remix.schema import Category, Evidence, Gate, Kind, Level, Module

MODULE = Module(
    name='midi-loopback-scenes', key='MIDI LOOPBACK SCENES', kind=Kind.CF_PATCH,
    category=Category.MIDI_USB, author='radiohagen',
    author_url='https://github.com/radiohagen/octatrack-modules',
    doc='Route MIDI Scenes CC output using the source track’s Loopback destination.',
    requires=('MIDI LOOPBACK', 'MIDI SCENES', 'USB'),
    joins=('MIDI LOOPBACK', 'MIDI SCENES'),
    evidence=(Evidence(Level.EMULATOR, ref='verify_midi_loopback_scenes.py'),),
    gates=(Gate('tools/verify/verify_midi_loopback_scenes.py', venv=True, stage='image'),),
)
