"""STORE + EUCLID FILL (euclid.work client) with the stock effects."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="euclid-fill",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="STORE + EUCLID FILL (euclid.work client) with the stock effects.",
    modules=("STORE", "EUCLID FILL",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
