"""Scale-degree notes, chords and accumulator with native KEY; no Follow."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="midi-harmony", family="mods", proof=Proof.PORT,
    proof_note='',
    doc="Scale-degree notes, chords and accumulator with native KEY; no Follow.",
    modules=("STORE", "MIDI HARMONY", "EVENTS", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
