"""Harmony native-KEY control composition for the EVENTS/STORE migration."""
from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="harmony-follow-native-review", family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="Harmony native-KEY control composition for the EVENTS/STORE migration.",
    modules=("STORE", "MIDI HARMONY", "TRIG MODES", "EVENTS", "MIDI FOLLOW", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
