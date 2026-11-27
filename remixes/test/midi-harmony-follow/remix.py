"""MIDI Harmony, Scales and Follow control composition without Loopback."""
from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="midi-harmony-follow", family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="MIDI Harmony, Scales and Follow control composition without Loopback.",
    modules=("STORE", "MIDI HARMONY", "TRIG MODES", "EVENTS", "MIDI SCALES",  "MIDI FOLLOW", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
