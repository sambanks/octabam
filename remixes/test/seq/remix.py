"""STORE + SEQ (euclid.work client) with the stock effects."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="seq",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="STORE + SEQ (euclid.work client) with the stock effects.",
    modules=("STORE", "SEQ",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
