"""All twelve keys and seven modes in the native ARP SETUP KEY control."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="midi-scales", family="mods", proof=Proof.PORT,
    proof_note='',
    doc="All twelve keys and seven modes in the native ARP SETUP KEY control.",
    modules=("MIDI SCALES", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
