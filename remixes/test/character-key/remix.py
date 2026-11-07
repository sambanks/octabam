"""stock effects with SIDECHAIN_COMPRESSOR in COMPRESSOR's row and CHARACTER on FX1: CHARACTER's KEY reads T1..T8 from the side-chain keybus."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="character-key",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with SIDECHAIN_COMPRESSOR and CHARACTER: CHARACTER's KEY reads T1..T8 from the side-chain keybus.",
    modules=(
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "SIDECHAIN_COMPRESSOR", "LO-FI",
             "DELAY", "CHARACTER"),
    fallback="NONE",
)
