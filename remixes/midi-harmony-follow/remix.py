"""MIDI Harmony, Scales and Follow together with all stock effects."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="midi-harmony-follow", family="mods", proof=Proof.PORT,
    proof_note='',
    doc="MIDI Harmony, Scales and Follow together with all stock effects.",
    modules=("STORE", "MIDI HARMONY", "EVENTS", "MIDI SCALES",  "MIDI FOLLOW", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
