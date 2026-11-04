"""stock effects with REC CS1 SKIP: the recorder's control-record update without its redundant CS1 writes."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="rec-cs1-skip",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with REC CS1 SKIP: the recorder's control-record update without its redundant CS1 writes.",
    modules=("REC CS1 SKIP",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
