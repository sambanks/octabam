"""stock effects with SIDECHAIN_COMPRESSOR in COMPRESSOR's row: KEY, KFLT, KGN and MON on page 2;
SPRING REV gives up its words for the DSP section, as in the standalone build."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="sidechain-compressor",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with SIDECHAIN_COMPRESSOR in COMPRESSOR's row: KEY, KFLT, KGN and MON on page 2.",
    modules=("SIDECHAIN_COMPRESSOR",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "LO-FI",
             "DELAY", "PLATE REV", "DARK REV"),
    fallback="NONE",
)
