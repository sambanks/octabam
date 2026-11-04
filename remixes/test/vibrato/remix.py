"""VIBRATO on FX1 beside the stock effects: PLATE REV gives up its words."""
from remix.schema import Proof, Remix

REMIX = Remix(
    family="effects",
    proof=Proof.CHECK,
    proof_note="",
    name="vibrato",
    doc="VIBRATO on FX1 beside the stock effects (all but PLATE REV).",
    modules=("VIBRATO",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "SPRING REV", "DARK REV"),
    fx1=("VIBRATO",
         "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
         "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
)
