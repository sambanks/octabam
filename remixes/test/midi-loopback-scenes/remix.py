"""MIDI Loopback with MIDI Scenes and the bridge that routes scene CCs, on the stock effects."""
from remix.schema import Remix

REMIX = Remix(
    name="midi-loopback-scenes", family="mods",
    doc="Stock effects plus MIDI Loopback, MIDI Scenes and their bridge: scene CCs follow each track's DEST.",
    modules=("STORE", "USB", "MIDI SCENES", "MIDI LOOPBACK", "MIDI LOOPBACK SCENES",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR",
             "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
