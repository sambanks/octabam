"""Harmony native-KEY control composition for the EVENTS/STORE migration."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="harmony-scales-provider", family="mods", proof=Proof.PORT,
    proof_note='',
    doc="Harmony native-KEY control composition for the EVENTS/STORE migration.",
    modules=("MIDI SCALES", "STORE", "MIDI SRAM", "MIDI HARMONY", "EVENTS", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
