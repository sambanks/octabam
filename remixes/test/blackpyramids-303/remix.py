"""BLACKPYRAMIDS_303 (BLKPYRAMD, a TB-303 voice as a track machine) with the stock effects, SPRING REV given up."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="blackpyramids-303",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="BLACKPYRAMIDS_303 (BLKPYRAMD, a TB-303 voice as a track machine) with the stock effects, SPRING REV given up.",
    modules=("BLACKPYRAMIDS_303",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "DARK REV"),
    fallback="NONE",
)
