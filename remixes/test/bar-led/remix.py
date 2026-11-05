"""stock effects with BAR LED: the tempo LED green on the pattern's 1. Its gate's remix."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="bar-led",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with BAR LED: the tempo LED flashes green on the pattern's 1 while playing.",
    modules=("BAR LED",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
