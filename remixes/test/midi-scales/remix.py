"""All twelve keys and seven modes in the native ARP SETUP KEY control."""
from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="midi-scales", family="mods", evidence=(Evidence(Level.EMULATOR),),
    doc="All twelve keys and seven modes in the native ARP SETUP KEY control.",
    modules=("MIDI SCALES", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
