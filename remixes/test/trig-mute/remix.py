"""stock effects with TRIG MUTE: mute a single trig without deleting it."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="trig-mute",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with TRIG MUTE: mute a single trig without deleting it.",
    modules=("TRIG MUTE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
