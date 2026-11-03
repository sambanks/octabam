"""Harmony native-KEY control composition for the EVENTS/STORE migration."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="harmony-follow-native-review", family="mods", proof=Proof.PORT,
    proof_note='',
    doc="Harmony native-KEY control composition for the EVENTS/STORE migration.",
    modules=("STORE", "MIDI SRAM", "MIDI HARMONY", "EVENTS", "MIDI FOLLOW", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
