"""stock effects with PAGE LOOP: loop one page of one track, in time."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="page-loop",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with PAGE LOOP: loop one page of one track, in time.",
    modules=("PAGE LOOP",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
