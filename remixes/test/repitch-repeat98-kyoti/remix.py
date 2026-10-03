"""stock effects with REPITCH_REPEAT98_KYOTI (ColdFire half, WIP): RPCH / RPS9 / RPSP and QUAN."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="repitch-repeat98-kyoti",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with REPITCH_REPEAT98_KYOTI (ColdFire half, WIP): RPCH / RPS9 / RPSP and QUAN.",
    modules=("REPITCH_REPEAT98_KYOTI",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
