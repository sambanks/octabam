"""KEYBUS alone on the stock effects, for its gate."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="keybus",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="KEYBUS alone (every track's key level in eight shared words) on the stock effects.",
    modules=(
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "KEYBUS"),
    fallback="NONE",
)
