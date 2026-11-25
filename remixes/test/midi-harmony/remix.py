"""Scale-degree notes, chords and accumulator with native KEY; no Follow."""
from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="midi-harmony", family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="Scale-degree notes, chords and accumulator with native KEY; no Follow.",
    modules=("STORE", "MIDI HARMONY", "TRIG MODES", "EVENTS", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
