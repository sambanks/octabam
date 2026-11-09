"""stock effects with KEYBUS and CHARACTER on FX1: CHARACTER's KEY reads T1..T8 from KEYBUS's words."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="character-key",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with KEYBUS and CHARACTER: CHARACTER's KEY reads T1..T8 from KEYBUS's shared key words.",
    modules=(
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "KEYBUS", "CHARACTER"),
    fallback="NONE",
)
