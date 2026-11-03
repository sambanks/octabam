"""Harmony, Follow, Scales and Loopback together with all stock effects."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="midi", family="mods", proof=Proof.PORT,
    proof_note='Combined emulator qualification; not tested on hardware',
    doc="Harmony, Follow, Scales and Loopback together with all stock effects.",
    modules=("STORE", "MIDI HARMONY", "EVENTS", "MIDI SCALES",  "MIDI FOLLOW", "MIDI LOOPBACK", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
